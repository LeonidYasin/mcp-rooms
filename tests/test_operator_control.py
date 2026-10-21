"""Pure guarded-controller tests; real root/systemd effects run only in Actions."""
from contextlib import contextmanager
from types import SimpleNamespace
import os
from pathlib import Path
import runpy
import pytest

ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'tools/operator_control.py'));g=m['start'].__globals__;Error=m['ControlError']
SHA='a'*40


@pytest.fixture
def control(tmp_path,monkeypatch):
    profile=tmp_path/'state'/'owner-first';profile.parent.mkdir()
    monkeypatch.setitem(g,'PROFILE',profile)
    calls=[];receipt={'source_sha':SHA,'resource':'https://candidate.invalid/a/mcp','identity':{'uid':1,'gid':1}}
    installer={}
    @contextmanager
    def lock(i):calls.append('lock');yield
    monkeypatch.setitem(g,'_installer',lambda:installer);monkeypatch.setitem(g,'_lock',lock)
    def validate(i,state):calls.append('validate:'+state);return receipt,{'MainPID':'123'}
    monkeypatch.setitem(g,'_validate',validate)
    monkeypatch.setitem(g,'_capacity',lambda:(calls.append('capacity') or {'accepted':True}))
    monkeypatch.setitem(g,'_profile',lambda r:calls.append('profile'))
    monkeypatch.setitem(g,'_candidate_argv',lambda r,a:['candidate',a])
    def transient(i,name,argv,r,write):calls.append(('transient',name,tuple(argv),write))
    monkeypatch.setitem(g,'_transient',transient)
    monkeypatch.setitem(g,'_run',lambda argv,*a:calls.append(('run',tuple(argv))))
    monkeypatch.setitem(g,'_ready',lambda *a:calls.append('ready'))
    monkeypatch.setitem(g,'_cleanup_failed_start',lambda i,r:calls.append('cleanup'))
    monkeypatch.setitem(g,'_stop_owned',lambda i,r:calls.append('stop-owned'))
    return profile,calls,receipt


def test_capacity_validates_exact_inactive_install(control):
    result=m['capacity']()
    assert result['accepted'] and control[1]==['lock','validate:inactive','capacity']


@pytest.mark.parametrize('action,wrong,code',[('bootstrap','wrong','control_bootstrap_authorization_required'),
    ('start','wrong','control_start_authorization_required')])
def test_explicit_authorization_precedes_any_observation(control,action,wrong,code):
    with pytest.raises(Error,match=code):m[action](wrong)
    assert control[1]==[]


def test_bootstrap_is_explicit_fresh_only_and_never_reads_or_returns_key(control,monkeypatch):
    profile,calls,_=control
    old=g['_transient']
    def create(i,name,argv,r,write):
        old(i,name,argv,r,write)
        if name==g['BOOTSTRAP']:
            profile.mkdir();(profile/'photos').mkdir();(profile/'profile.json').write_text('{}')
    monkeypatch.setitem(g,'_transient',create)
    result=m['bootstrap'](g['BOOTSTRAP_AUTH'])
    assert result=={'profile_created':True,'key_read_or_returned':False,'runtime_capacity_accepted':True}
    assert ('transient',g['BOOTSTRAP'],('candidate','bootstrap'),True) in calls
    assert ('transient',g['CHECK'],('candidate','check'),True) in calls
    assert not any('key' in str(value).lower() for value in calls)


def test_existing_profile_refused_without_command(control):
    profile,calls,_=control;profile.mkdir()
    with pytest.raises(Error,match='control_existing_profile'):m['bootstrap'](g['BOOTSTRAP_AUTH'])
    assert not any(isinstance(value,tuple) and value[0]=='transient' for value in calls)


def test_interrupted_bootstrap_remains_blocked_for_review(control,monkeypatch):
    profile,calls,_=control
    def interrupted(*args):profile.mkdir();raise Error('fixture_interrupted')
    monkeypatch.setitem(g,'_transient',interrupted)
    with pytest.raises(Error,match='fixture_interrupted'):m['bootstrap'](g['BOOTSTRAP_AUTH'])
    before=list(profile.iterdir())
    with pytest.raises(Error,match='control_existing_profile'):m['bootstrap'](g['BOOTSTRAP_AUTH'])
    assert list(profile.iterdir())==before


def test_start_rechecks_before_effect_and_commits_only_after_readiness(control):
    result=m['start'](g['START_AUTH']);calls=control[1]
    assert result=={'started':True,'runtime_capacity_accepted':True,'source_sha':SHA}
    assert calls[:5]==['lock','validate:inactive','capacity','profile',
        ('transient',g['CHECK'],('candidate','check'),True)]
    assert calls[5:] == ['validate:inactive',('run',('/usr/bin/systemctl','start',g['NAME'])),
        'validate:active','ready','validate:active']


def test_interrupted_start_cleans_only_owned_target_then_returns_original(control,monkeypatch):
    monkeypatch.setitem(g,'_ready',lambda *a:(_ for _ in ()).throw(Error('fixture_interrupted')))
    with pytest.raises(Error,match='fixture_interrupted'):m['start'](g['START_AUTH'])
    assert control[1][-1]=='cleanup'


def test_cleanup_refusal_becomes_manual_recovery(control,monkeypatch):
    monkeypatch.setitem(g,'_ready',lambda *a:(_ for _ in ()).throw(Error('fixture_interrupted')))
    monkeypatch.setitem(g,'_cleanup_failed_start',lambda *a:(_ for _ in ()).throw(Error('foreign')))
    with pytest.raises(Error,match='control_start_recovery_required'):m['start'](g['START_AUTH'])


def test_stop_validates_active_identity_and_preserves_state(control):
    result=m['stop']()
    assert result=={'stopped':True,'state_preserved':True,'profile_preserved':True,
        'source_sha':SHA,'pid':123}
    assert control[1]==['lock','validate:active','stop-owned']


def test_stop_drift_never_invokes_systemctl(control,monkeypatch):
    monkeypatch.setitem(g,'_validate',lambda *a:(_ for _ in ()).throw(Error('control_unit_mismatch')))
    with pytest.raises(Error,match='control_unit_mismatch'):m['stop']()
    assert not any(isinstance(value,tuple) and value[0]=='run' for value in control[1])


def fakefs(free=8*1024**3,inodes=100000):
    return SimpleNamespace(f_bavail=free//4096,f_frsize=4096,f_favail=inodes)


@pytest.fixture
def capacity_fixture(monkeypatch):
    monkeypatch.setitem(g,'_available_memory',lambda:3*1024**3)
    monkeypatch.setitem(g,'_usage',lambda root:(1000,2000) if root==g['BASE'] else (3000,4000))
    monkeypatch.setattr(g['os'],'statvfs',lambda root:fakefs())


def test_capacity_accepts_full_install_and_state_measurements(capacity_fixture):
    value=m['_capacity']()
    assert value['accepted'] and value['memory_max_bytes']==1024**3
    assert value['install_allocated_bytes']==2000 and value['state_allocated_bytes']==4000
    assert value['runtime_max_seconds']==7200 and value['state_retention_ceiling_bytes']==1024**3


@pytest.mark.parametrize('kind,code',[('memory','control_runtime_memory_floor'),
    ('install_size','control_install_footprint_ceiling'),('state_size','control_state_retention_ceiling'),
    ('base_free','control_install_disk_floor'),('state_free','control_state_disk_floor'),
    ('inodes','control_inode_floor')])
def test_capacity_refuses_each_adopted_boundary(capacity_fixture,monkeypatch,kind,code):
    if kind=='memory':monkeypatch.setitem(g,'_available_memory',lambda:2*1024**3-1)
    elif kind=='install_size':monkeypatch.setitem(g,'_usage',lambda root:(1,1024**3+1) if root==g['BASE'] else (1,1))
    elif kind=='state_size':monkeypatch.setitem(g,'_usage',lambda root:(1,1) if root==g['BASE'] else (1,1024**3+1))
    elif kind=='base_free':monkeypatch.setattr(g['os'],'statvfs',lambda root:fakefs(1024**3) if root==g['BASE'] else fakefs())
    elif kind=='state_free':monkeypatch.setattr(g['os'],'statvfs',lambda root:fakefs(3*1024**3) if root==g['STATE'] else fakefs())
    else:monkeypatch.setattr(g['os'],'statvfs',lambda root:fakefs(inodes=65535))
    with pytest.raises(Error,match=code):m['_capacity']()


def test_capacity_observation_failure_is_typed(capacity_fixture,monkeypatch):
    monkeypatch.setattr(g['os'],'statvfs',lambda root:(_ for _ in ()).throw(OSError('private detail')))
    with pytest.raises(Error,match='control_capacity_observation_failed'):m['_capacity']()


def test_expected_command_is_exact_and_has_no_key_path():
    receipt={'source_sha':SHA,'resource':'https://candidate.invalid/a/mcp'}
    argv=m['_expected_cmd'](receipt)
    assert argv[0].endswith(b'/venv/bin/python') and argv[-1]==b''
    assert b'owner.key' not in b'\0'.join(argv)


def test_duplicate_receipt_keys_refused():
    with pytest.raises(Error,match='control_invalid_receipt'):m['_pairs']([('a',1),('a',2)])
