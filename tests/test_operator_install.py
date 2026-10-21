"""Pure installer fixtures. Actual root/unit installation tested only in Actions."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import runpy
import pytest
ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'tools/operator_install.py'));g=m['install'].__globals__;Error=m['InstallError']
SHA='a'*40;HASH='b'*64;RESOURCE='https://candidate.invalid/a/mcp'


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    base=tmp_path/'base';state=tmp_path/'state';unit=tmp_path/'unit.service'
    bundle=tmp_path/'bundle';(bundle/'wheels').mkdir(parents=True)
    (bundle/'wheels/a.whl').write_bytes(b'fixture');(bundle/'install.lock').write_bytes(b'fixture')
    calls=[];identity={'uid':os.geteuid(),'gid':os.getegid()}
    for key,value in [('BASE',base),('STATE',state),('UNIT',unit),('ROOT_UID',os.geteuid())]:monkeypatch.setitem(g,key,value)
    monkeypatch.setitem(g,'_inputs',lambda *a:({'fixture':'trusted'},HASH,{},b'fixture unit'))
    monkeypatch.setitem(g,'_host',lambda:None);monkeypatch.setitem(g,'_chain',lambda p:None)
    monkeypatch.setitem(g,'_trusted',lambda:{'fixture':'trusted'});monkeypatch.setitem(g,'_python',lambda:HASH)
    monkeypatch.setitem(g,'_capacity',lambda:None);monkeypatch.setitem(g,'_absent_account',lambda:None)
    monkeypatch.setitem(g,'_absent_unit',lambda n:None);monkeypatch.setitem(g,'_account',lambda:identity)
    monkeypatch.setattr(os,'chown',lambda *a,**k:None)
    @contextmanager
    def lock():yield
    monkeypatch.setitem(g,'_lock',lock)
    def build(argv,venv,who):
        calls.append(argv)
        (venv/'bin').mkdir(exist_ok=True)
        (venv/'bin/python').write_bytes(b'synthetic interpreter')
    monkeypatch.setitem(g,'_build',build);monkeypatch.setitem(g,'_seal',lambda p:None)
    monkeypatch.setitem(g,'_run',lambda argv,*a:calls.append(argv))
    monkeypatch.setitem(g,'_show',lambda name:{'LoadState':'loaded','ActiveState':'inactive','MainPID':'0',
        'ControlGroup':'','FragmentPath':str(unit),'DropInPaths':''})
    monkeypatch.setattr(g['runpy'],'run_path',lambda p:{'verify':lambda *a:None,'render':lambda *a:'fixture unit'})
    return base,state,unit,bundle,calls


def install(f):return m['install'](f[3],SHA,HASH,RESOURCE)


def test_install_ready_last_no_profile_start_or_bootstrap(fixture):
    base,state,unit,_,calls=fixture
    result=install(fixture)
    assert result=={'installed':True,'profile_created':False,'started':False,'start_authorized':False,'source_sha':SHA}
    assert not (state/'owner-first').exists()
    assert (base/'installation.json').stat().st_mode&0o777==0o600
    assert m['inspect']()['start_authorized'] is False
    commands=[' '.join(v) for v in calls]
    assert any('--no-index --no-deps --only-binary=:all:' in v for v in commands)
    assert not any(' bootstrap ' in v or ' start ' in v or ' enable ' in v for v in commands)
    before=(base/'installation.json').read_bytes()
    with pytest.raises(Error,match='install_existing_target'):install(fixture)
    assert (base/'installation.json').read_bytes()==before


@pytest.mark.parametrize('kind',['base','state','base_link','state_link'])
def test_existing_targets_preserved(fixture,kind):
    base,state,*_=fixture;target=base if kind.startswith('base') else state
    if kind.endswith('link'):target.symlink_to(target.parent/'missing')
    else:target.mkdir();(target/'sentinel').write_text('preserve')
    with pytest.raises(Error,match='install_existing_target'):install(fixture)
    assert target.is_symlink() or (target/'sentinel').read_text()=='preserve'


@pytest.mark.parametrize('stage',[1,2,3])
def test_interrupted_build_is_blocked_and_has_no_ready_receipt(fixture,monkeypatch,stage):
    count=0;old=g['_build']
    def fail(*args):
        nonlocal count
        count+=1
        if count==stage:raise Error('fixture interrupted')
        return old(*args)
    monkeypatch.setitem(g,'_build',fail)
    with pytest.raises(Error):install(fixture)
    assert not (fixture[0]/'installation.json').exists()
    with pytest.raises(Error,match='install_existing_target'):install(fixture)
    assert fixture[1].exists()


@pytest.mark.parametrize('target',['unit','inventory.json','installation.json'])
def test_marker_failure_preserves_new_partial_target(fixture,monkeypatch,target):
    old=g['_new']
    def fail(path,data,mode=0o600):
        if (target=='unit' and path==fixture[2]) or path.name==target:
            path.write_bytes(b'partial');raise OSError('fixture write interrupted')
        return old(path,data,mode)
    monkeypatch.setitem(g,'_new',fail)
    with pytest.raises(OSError):install(fixture)
    p=fixture[2] if target=='unit' else fixture[0]/target
    assert p.read_bytes()==b'partial'
    with pytest.raises(Error):install(fixture)


@pytest.mark.parametrize('mutation',['code','unit','inventory','receipt','uid','tools','python','dropin','active','state_mode'])
def test_inspect_rejects_drift(fixture,monkeypatch,mutation):
    install(fixture);base,state,unit,*_=fixture
    if mutation=='code':(base/'releases'/SHA/'venv/bin/python').write_bytes(b'changed')
    elif mutation=='unit':unit.write_bytes(b'changed')
    elif mutation=='inventory':(base/'inventory.json').write_bytes(b'changed')
    elif mutation=='receipt':(base/'installation.json').write_bytes(b'{"format":"bad"}')
    elif mutation=='uid':monkeypatch.setitem(g,'_account',lambda:{'uid':12345,'gid':12345})
    elif mutation=='tools':monkeypatch.setitem(g,'_trusted',lambda:{'fixture':'changed'})
    elif mutation=='python':monkeypatch.setitem(g,'_python',lambda:'c'*64)
    elif mutation in ('dropin','active'):
        old=g['_show'];p=old('anything')
        p['DropInPaths' if mutation=='dropin' else 'MainPID']='changed'
        monkeypatch.setitem(g,'_show',lambda n:p)
    elif mutation=='state_mode':state.chmod(0o755)
    with pytest.raises((Error,ValueError)):m['inspect']()


def test_loaded_unit_drift_prevents_receipt(fixture,monkeypatch):
    old=g['_show'];p=old('anything');p['DropInPaths']='foreign.conf'
    monkeypatch.setitem(g,'_show',lambda n:p)
    with pytest.raises(Error,match='install_loaded_unit_changed'):install(fixture)
    assert not (fixture[0]/'installation.json').exists() and fixture[2].exists()


def test_trust_change_before_unit_write_refused(fixture,monkeypatch):
    monkeypatch.setitem(g,'_trusted',lambda:{'fixture':'changed'})
    with pytest.raises(Error,match='install_trust_changed'):install(fixture)
    assert not fixture[2].exists()


def test_unsafe_code_link_and_group_writes_rejected(fixture):
    install(fixture);base,*_=fixture;release=base/'releases'/SHA
    (release/'escape').symlink_to('/etc/passwd')
    with pytest.raises(Error,match='install_code_link_escape'):m['_inventory'](release)
    (release/'escape').unlink();(release/'venv/bin/python').chmod(0o666)
    with pytest.raises(Error):m['_inventory'](release)


def test_duplicate_receipt_keys_refused():
    with pytest.raises(Error):m['_pairs']([('a',1),('a',2)])


def test_exclusive_new_explicit_mode_survives_private_umask(tmp_path):
    path=tmp_path/'wheel'
    old=os.umask(0o077)
    try:m['_new'](path,b'fixture',0o644)
    finally:os.umask(old)
    assert path.stat().st_mode & 0o777 == 0o644
    with pytest.raises(FileExistsError):m['_new'](path,b'replacement',0o644)
    assert path.read_bytes()==b'fixture'
