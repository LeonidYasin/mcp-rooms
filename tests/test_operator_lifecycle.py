"""Filesystem/transaction fixtures; real installation/processes only in Actions smoke."""
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import runpy
import stat
import pytest
ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'tools/operator_lifecycle.py'))
g=m['install'].__globals__;Error=m['LifecycleError']
RESOURCE='https://candidate.invalid/rooms-test/mcp'


@pytest.fixture
def layout(tmp_path,monkeypatch):
    tmp_path.chmod(0o700);bundle=tmp_path/'bundle';bundle.mkdir(mode=0o700)
    root=tmp_path/'new';calls=[]
    monkeypatch.setitem(g,'_host',lambda:None)
    def verify(*a,**kw):
        assert a[1:] == ('a'*40,'b'*64) and kw=={}
        calls.append('verify');return {'ok':True}
    def resource(v):
        if v!=RESOURCE:raise ValueError('bad resource')
    def trusted(path):
        if str(path).endswith('operator_plan.py'):return {'_resource':resource}
        return {'verify':verify}
    monkeypatch.setattr(g['runpy'],'run_path',trusted)
    def runner(argv,timeout):
        calls.append(list(argv))
        if 'venv' in argv:
            p=root/'venv/bin';p.mkdir(parents=True,mode=0o700)
            (p/'python').write_bytes(b'synthetic interpreter');(p/'python').chmod(0o700)
    monkeypatch.setitem(g,'_run',runner)
    return root,bundle,calls


def install(layout):
    root,bundle,calls=layout
    return m['install'](bundle,root,'a'*40,'b'*64,RESOURCE)


def test_fresh_offline_install_ready_last_and_no_profile(layout):
    result=install(layout);root,bundle,calls=layout
    assert result=={'installed':True,'profile_created':False,'started':False,'source_sha':'a'*40}
    assert m['_installed'](root)['source_sha']=='a'*40
    assert not (root/'profile').exists() and not (root/'process.json').exists()
    assert calls[0]==calls[-1]=='verify'
    pip=next(c for c in calls if type(c) is list and 'install' in c)
    assert '--no-index' in pip and '--require-hashes' in pip and '--only-binary=:all:' in pip
    assert '--copies' in next(c for c in calls if type(c) is list and 'venv' in c)
    with pytest.raises(FileExistsError):install(layout)


@pytest.mark.parametrize('failure',[1,2,3,4])
def test_interrupted_install_has_no_ready_marker_no_retry(layout,monkeypatch,failure):
    root,bundle,calls=layout;runner=g['_run'];count=0
    def fail(*a):
        nonlocal count
        count+=1
        if count==failure:raise Error('synthetic interrupted')
        runner(*a)
    if failure<4:monkeypatch.setitem(g,'_run',fail)
    else:
        old=g['_write_new']
        def write(*a):raise OSError('synthetic marker failure')
        monkeypatch.setitem(g,'_write_new',write)
    with pytest.raises((Error,OSError)):install(layout)
    assert root.is_dir() and not (root/'install.json').exists()
    with pytest.raises(FileExistsError):install(layout)


@pytest.mark.parametrize('kind',['directory','file','link','dangling'])
def test_existing_target_never_overwritten(layout,kind):
    root,bundle,_=layout
    if kind=='directory':root.mkdir(mode=0o700);(root/'sentinel').write_text('preserve')
    elif kind=='file':root.write_text('preserve')
    elif kind=='link':root.symlink_to(bundle,target_is_directory=True)
    else:root.symlink_to(root.parent/'absent')
    before=os.readlink(root) if root.is_symlink() else None
    with pytest.raises((Error,OSError)):install(layout)
    if before is not None:assert os.readlink(root)==before
    elif kind=='file':assert root.read_text()=='preserve'
    else:assert (root/'sentinel').read_text()=='preserve'


def test_shared_parent_refused_before_creation(layout):
    root,bundle,_=layout;root.parent.chmod(0o755)
    with pytest.raises(Error):install(layout)
    assert not root.exists()


def test_bundle_refusal_never_becomes_installation(layout,monkeypatch):
    root,_,_=layout
    def refuse(*a,**kw):raise ValueError('synthetic corrupt bundle')
    monkeypatch.setattr(g['runpy'],'run_path',lambda p:{'_resource':lambda v:v,'verify':refuse})
    with pytest.raises(ValueError):install(layout)
    assert not root.exists()


@pytest.mark.parametrize('change',['source','uid','inode','interpreter','resource','extra','mode','hardlink','symlink'])
def test_receipt_and_interpreter_identity_refused(layout,change):
    install(layout);root,_,_=layout;p=root/'install.json';value=json.loads(p.read_text())
    if change=='source':value['source_sha']='short'
    elif change=='uid':value['uid']=-1
    elif change=='inode':value['root_inode']+=1
    elif change=='interpreter':(root/'venv/bin/python').write_bytes(b'changed')
    elif change=='resource':value['resource']='https://unreviewed.invalid/other/mcp'
    elif change=='extra':value['token']='synthetic rejected'
    elif change=='mode':p.chmod(0o644)
    elif change=='hardlink':os.link(p,root/'alias')
    elif change=='symlink':p.rename(root/'elsewhere');p.symlink_to(root/'elsewhere')
    if change not in ('interpreter','mode','hardlink','symlink'):p.write_text(json.dumps(value))
    with pytest.raises((Error,OSError)):m['_installed'](root)


def test_operator_lock_is_exclusive(layout):
    install(layout);root,_,_=layout
    with m['_lock'](root):
        with pytest.raises(Error,match='lifecycle_busy'):
            with m['_lock'](root):pass


def test_bootstrap_is_explicit_and_existing_profile_refused(layout,monkeypatch):
    install(layout);root,_,calls=layout
    assert not any(type(c) is list and 'bootstrap' in c for c in calls)
    result=m['bootstrap'](root);assert result=={'profile_created':True,'key_returned_or_read':False}
    argv=calls[-1];assert 'bootstrap' in argv and '--resource' in argv
    (root/'profile').mkdir(mode=0o700)
    with pytest.raises(Error,match='lifecycle_existing_profile'):m['bootstrap'](root)


def test_start_refuses_existing_record_without_spawning(layout,monkeypatch):
    install(layout);root,_,_=layout;(root/'process.json').write_text('do not replace')
    with pytest.raises((Error,ValueError)):m['start'](root)
    assert (root/'process.json').read_text()=='do not replace'


@pytest.mark.parametrize('change',['pid','ticks','uid','boot','command','source','root','extra'])
def test_untrusted_process_record_refused_before_pidfd(layout,change):
    install(layout);root,_,_=layout;receipt=m['_installed'](root)
    value={'identity':{'pid':12345,'start_ticks':10,'uid':[os.geteuid()]*4,'cmdline_sha256':m['_expected_cmd'](root,RESOURCE),'boot_id':m['_boot']()},'root_device':receipt['root_device'],'root_inode':receipt['root_inode'],'source_sha':'a'*40}
    if change=='pid':value['identity']['pid']=True
    elif change=='ticks':value['identity']['start_ticks']='10'
    elif change=='uid':value['identity']['uid']=[-1]*4
    elif change=='boot':value['identity']['boot_id']='other boot'
    elif change=='command':value['identity']['cmdline_sha256']='c'*64
    elif change=='source':value['source_sha']='c'*40
    elif change=='root':value['root_inode']+=1
    elif change=='extra':value['kill_pid']=23456
    with pytest.raises(Error,match='lifecycle_process_mismatch'):m['_check_process'](root,receipt,value)


def test_rollback_is_stop_only_never_rewinds_or_deletes(layout,monkeypatch):
    install(layout);root,_,_=layout
    (root/'sentinel').write_text('keep DB/state/key/logs')
    monkeypatch.setitem(g,'stop',lambda p:{'stopped':True,'state_preserved':True})
    result=m['rollback'](root)
    assert result['rollback']=='stop-only-preserve-all' and result['data_rewound'] is False
    assert (root/'sentinel').read_text()=='keep DB/state/key/logs' and (root/'install.json').exists()


def test_clean_environment_never_inherits_tokens(monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN','synthetic forbidden');monkeypatch.setenv('PYTHONPATH','/untrusted')
    assert m['_env']()=={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONUTF8':'1','PIP_CONFIG_FILE':'/dev/null'}


def test_marker_fsync_failure_removes_only_own_marker(layout,monkeypatch):
    root,bundle,_=layout;root.mkdir(mode=0o700)
    def fail(fd):raise OSError('synthetic fsync failure')
    monkeypatch.setattr(g['os'],'fsync',fail)
    with pytest.raises(OSError):m['_write_new'](root/'marker',{'test':True})
    assert not (root/'marker').exists()
    (root/'marker').write_text('existing marker')
    with pytest.raises(FileExistsError):m['_write_new'](root/'marker',{'test':True})
    assert (root/'marker').read_text()=='existing marker'


def valid_process(root):
    receipt=m['_installed'](root)
    return {'identity':{'pid':999999,'start_ticks':10,'uid':[os.geteuid()]*4,
            'cmdline_sha256':m['_expected_cmd'](root,RESOURCE),'boot_id':m['_boot']()},
            'root_device':receipt['root_device'],'root_inode':receipt['root_inode'],'source_sha':'a'*40}


def test_reused_pid_never_signalled(layout,monkeypatch):
    install(layout);root,_,_=layout;record=valid_process(root)
    m['_write_new'](root/'process.json',record);actual=deepcopy(record['identity']);actual['start_ticks']+=1
    fd=os.open('/dev/null',os.O_RDONLY)
    monkeypatch.setattr(g['os'],'pidfd_open',lambda pid,flags:fd)
    monkeypatch.setitem(g,'_identity',lambda pid:actual)
    signals=[];monkeypatch.setattr(g['signal'],'pidfd_send_signal',lambda *a:signals.append(a))
    with pytest.raises(Error,match='lifecycle_process_mismatch'):m['stop'](root)
    assert signals==[] and (root/'process.json').exists()
    with pytest.raises(OSError):os.fstat(fd)


def test_stop_timeout_does_not_force_kill_or_delete_state(layout,monkeypatch):
    sent=[]
    monkeypatch.setattr(g['signal'],'pidfd_send_signal',lambda *a:sent.append(a))
    monkeypatch.setattr(g['select'],'select',lambda *a:([],[],[]))
    with pytest.raises(Error,match='lifecycle_stop_timeout'):m['_terminate'](123,{'pid':999999,'start_ticks':10},timeout=0)
    assert sent==[(123,g['signal'].SIGTERM)]


def test_stop_already_exited_preserves_profile_and_receipt(layout,monkeypatch):
    install(layout);root,_,_=layout;record=valid_process(root)
    m['_write_new'](root/'process.json',record)
    monkeypatch.setitem(g,'_pinned',lambda *a:(None,record['identity']))
    result=m['stop'](root)
    assert result['already_exited'] and result['state_preserved'] and not result['descendants_supervised']
    assert (root/'process.json').exists()


def test_active_record_prevents_second_start(layout,monkeypatch):
    install(layout);root,_,_=layout;record=valid_process(root)
    m['_write_new'](root/'process.json',record);fd=os.open('/dev/null',os.O_RDONLY)
    monkeypatch.setitem(g,'_pinned',lambda *a:(fd,record['identity']))
    monkeypatch.setattr(g['select'],'select',lambda *a:([],[],[]))
    with pytest.raises(Error,match='lifecycle_process_record_exists'):m['start'](root)
    assert not list(root.glob('stopped-*'))
    assert m['_json'](root/'process.json')==record
