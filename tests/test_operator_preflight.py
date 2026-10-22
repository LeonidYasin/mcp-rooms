"""Pure read-only preflight tests; no real VPS/systemd effects run here."""
from types import SimpleNamespace
from pathlib import Path
import json
import os
import runpy
import pytest

ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'tools/operator_preflight.py'));g=m['preflight'].__globals__
Error=m['PreflightError']
subprocess_devnull=object()


class FakeLibc:
    def __init__(self,value):self.value=value
    def syscall(self,*args):
        if isinstance(self.value,Exception):raise self.value
        return self.value


class FakeOs:
    def __init__(self,status):self.status=status
    def fork(self):return 4242
    def waitpid(self,pid,options):return pid,self.status
    def WIFEXITED(self,status):return True
    def WEXITSTATUS(self,status):return status>>8
    def _exit(self,code):raise SystemExit(code)


def fakefs(free=8*1024**3,inodes=100000):
    return SimpleNamespace(f_bavail=free//4096,f_frsize=4096,f_favail=inodes)


def test_host_requires_root_console(monkeypatch):
    monkeypatch.setitem(g,'os',SimpleNamespace(geteuid=lambda:1000,getuid=lambda:1000))
    with pytest.raises(Error,match='preflight_root_console_required'):m['_host']()


@pytest.mark.parametrize('system,machine,code',[('Darwin','x86_64','preflight_host_refused'),
    ('Linux','aarch64','preflight_host_refused')])
def test_host_refuses_foreign_platform(monkeypatch,system,machine,code):
    monkeypatch.setitem(g,'os',SimpleNamespace(geteuid=lambda:0,getuid=lambda:0))
    monkeypatch.setitem(g,'platform',SimpleNamespace(system=lambda:system,machine=lambda:machine))
    monkeypatch.setitem(g,'CGROUP',ROOT/'pyproject.toml')
    with pytest.raises(Error,match=code):m['_host']()


def test_host_requires_cgroup_v2(monkeypatch,tmp_path):
    monkeypatch.setitem(g,'os',SimpleNamespace(geteuid=lambda:0,getuid=lambda:0))
    monkeypatch.setitem(g,'platform',SimpleNamespace(system=lambda:'Linux',machine=lambda:'x86_64'))
    monkeypatch.setitem(g,'CGROUP',tmp_path/'missing')
    with pytest.raises(Error,match='preflight_cgroup_v2_required'):m['_host']()


def test_python_probe_requires_exact_trusted_version(monkeypatch,tmp_path):
    monkeypatch.setitem(g,'PYTHON',tmp_path/'python3.12');monkeypatch.setitem(g,'LIB',tmp_path/'lib')
    monkeypatch.setitem(g,'_trusted_file',lambda path:None)
    monkeypatch.setitem(g,'_trusted_dir',lambda path,code:None)
    monkeypatch.setitem(g,'subprocess',SimpleNamespace(run=lambda *a,**k:SimpleNamespace(returncode=0),
        DEVNULL=subprocess_devnull,SubprocessError=OSError))
    assert m['_python']()=={'trusted':True,'version':'3.12'}
    monkeypatch.setitem(g,'subprocess',SimpleNamespace(run=lambda *a,**k:SimpleNamespace(returncode=1),
        DEVNULL=subprocess_devnull,SubprocessError=OSError))
    with pytest.raises(Error,match='preflight_python_version_mismatch'):m['_python']()




def test_trusted_path_checks_fail_closed(monkeypatch,tmp_path):
    with pytest.raises(Error,match='preflight_untrusted_ancestor'):
        m['_trusted_dir'](tmp_path/'missing','preflight_untrusted_ancestor')
    with pytest.raises(Error,match='preflight_python_untrusted'):
        m['_trusted_file'](tmp_path/'missing')


@pytest.mark.parametrize('value,code',[(6,None),(2,'preflight_landlock_abi_insufficient'),
    (-1,'preflight_landlock_unavailable'),(OSError('private'),'preflight_landlock_unavailable')])
def test_landlock_abi_probe(monkeypatch,value,code):
    monkeypatch.setitem(g,'_libc',lambda:FakeLibc(value))
    if code is None:assert m['_landlock']()['abi']==6
    else:
        with pytest.raises(Error,match=code):m['_landlock']()


def test_seccomp_requires_real_actions_and_filter_probe(monkeypatch,tmp_path):
    actions=tmp_path/'actions';monkeypatch.setitem(g,'SECCOMP',actions)
    monkeypatch.setitem(g,'os',FakeOs(0))
    actions.write_text('kill_process kill_thread trap errno user_notif trace log allow\n')
    assert m['_seccomp']()['filter_supported'] is True
    actions.write_text('kill_process\n')
    with pytest.raises(Error,match='preflight_seccomp_unavailable'):m['_seccomp']()
    actions.write_text('kill_process kill_thread trap errno user_notif trace log allow\n')
    monkeypatch.setitem(g,'os',FakeOs(256))
    with pytest.raises(Error,match='preflight_seccomp_unavailable'):m['_seccomp']()
    actions.unlink()
    with pytest.raises(Error,match='preflight_seccomp_unavailable'):m['_seccomp']()


def test_seccomp_filter_probe_really_installs_allow_filter():
    if not os.uname().sysname=='Linux' or os.uname().machine!='x86_64':
        pytest.skip('x86_64 Linux only')
    assert m['_seccomp_filter']() is True


def test_candidate_identity_must_be_absent(monkeypatch):
    def name(value):
        return SimpleNamespace(pw_uid=1)
    def missing(value):raise KeyError(value)
    monkeypatch.setitem(g,'pwd',SimpleNamespace(getpwnam=missing))
    monkeypatch.setitem(g,'grp',SimpleNamespace(getgrnam=missing))
    assert m['_identity']()=={'exists':False}
    monkeypatch.setitem(g,'grp',SimpleNamespace(getgrnam=name))
    with pytest.raises(Error,match='preflight_candidate_identity_exists'):m['_identity']()


def test_candidate_paths_and_units_must_be_absent(monkeypatch,tmp_path):
    monkeypatch.setitem(g,'BASE',tmp_path/'base');monkeypatch.setitem(g,'STATE',tmp_path/'state')
    monkeypatch.setitem(g,'UNIT',tmp_path/'unit');monkeypatch.setitem(g,'RUN_LOCK',tmp_path/'run')
    monkeypatch.setitem(g,'_absent_unit',lambda name:{'loaded':False,'files':False})
    assert m['_paths']()['paths_absent'] is True
    (tmp_path/'state').mkdir()
    with pytest.raises(Error,match='preflight_candidate_path_exists'):m['_paths']()


def test_unit_absence_checks_loader_and_files(monkeypatch,tmp_path):
    units=tmp_path/'units';units.mkdir();monkeypatch.setitem(g,'UNIT_DIRS',(str(units),))
    absent={'LoadState':'not-found','ActiveState':'inactive','MainPID':'0','ControlGroup':'',
        'FragmentPath':'','DropInPaths':''}
    monkeypatch.setitem(g,'_show',lambda name,keys:dict(absent))
    assert m['_absent_unit']('x.service')=={'loaded':False,'files':False}
    loaded=dict(absent);loaded['LoadState']='loaded'
    monkeypatch.setitem(g,'_show',lambda name,keys:loaded)
    with pytest.raises(Error,match='preflight_candidate_unit_exists'):m['_absent_unit']('x.service')
    monkeypatch.setitem(g,'_show',lambda name,keys:dict(absent))
    (units/'x.service').write_text('[Unit]\n')
    with pytest.raises(Error,match='preflight_candidate_unit_exists'):m['_absent_unit']('x.service')


def test_show_refuses_duplicate_or_incomplete_rows(monkeypatch):
    keys=['LoadState','ActiveState','MainPID','ControlGroup','FragmentPath','DropInPaths']
    raw=''.join(key+'=x\n' for key in keys)
    monkeypatch.setitem(g,'subprocess',SimpleNamespace(run=lambda *a,**k:SimpleNamespace(returncode=0,stdout=raw),
        DEVNULL=subprocess_devnull,SubprocessError=OSError,PIPE=-1))
    assert m['_show']('x.service',keys)['LoadState']=='x'
    dup=raw+'LoadState=x\n'
    monkeypatch.setitem(g,'subprocess',SimpleNamespace(run=lambda *a,**k:SimpleNamespace(returncode=0,stdout=dup),
        DEVNULL=subprocess_devnull,SubprocessError=OSError,PIPE=-1))
    with pytest.raises(Error,match='preflight_unit_observation_failed'):m['_show']('x.service',keys)
    monkeypatch.setitem(g,'subprocess',SimpleNamespace(run=lambda *a,**k:SimpleNamespace(returncode=0,stdout='LoadState=x\n'),
        DEVNULL=subprocess_devnull,SubprocessError=OSError,PIPE=-1))
    with pytest.raises(Error,match='preflight_unit_observation_failed'):m['_show']('x.service',keys)


def test_listener_parser_reads_only_listen_ports(monkeypatch,tmp_path):
    table=tmp_path/'tcp'
    table.write_text('  sl  local_address rem_address   st\n'
        '   0: 0100007F:223E 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0\n'
        '   1: 0100007F:1F90 00000000:0000 01 00000000:00000000 00:00000000 00000000 0 0\n')
    monkeypatch.setitem(g,'TCP',(table,))
    assert m['_listeners']()=={8766}
    monkeypatch.setitem(g,'TCP',(tmp_path/'missing',))
    with pytest.raises(Error,match='preflight_port_observation_failed'):m['_listeners']()
    bad=tmp_path/'bad';bad.write_text('header\nbroken\n')
    monkeypatch.setitem(g,'TCP',(bad,))
    with pytest.raises(Error,match='preflight_port_observation_failed'):m['_listeners']()


def test_candidate_port_refused_when_listening(monkeypatch):
    monkeypatch.setitem(g,'_listeners',lambda:{8766})
    with pytest.raises(Error,match='preflight_candidate_port_in_use'):m['_port']()
    monkeypatch.setitem(g,'_listeners',lambda:{80})
    assert m['_port']()=={'port':8766,'free':True}


@pytest.fixture
def capacity(monkeypatch,tmp_path):
    base=tmp_path/'opt'/'candidate';state=tmp_path/'var'/'candidate'
    monkeypatch.setitem(g,'BASE',base);monkeypatch.setitem(g,'STATE',state)
    monkeypatch.setitem(g,'_available_memory',lambda:3*1024**3)
    monkeypatch.setattr(g['os'],'statvfs',lambda path:fakefs())
    return base,state


def test_capacity_accepts_full_floors(capacity):
    value=m['_capacity']()
    assert value['memory_available_bytes']==3*1024**3
    assert value['install_free_bytes']==8*1024**3 and value['state_free_bytes']==8*1024**3


@pytest.mark.parametrize('kind,code',[('memory','preflight_memory_floor'),
    ('base','preflight_install_disk_floor'),('state','preflight_state_disk_floor'),
    ('inodes','preflight_inode_floor')])
def test_capacity_refuses_each_floor(capacity,monkeypatch,kind,code):
    base,state=capacity
    if kind=='memory':monkeypatch.setitem(g,'_available_memory',lambda:2*1024**3-1)
    elif kind=='base':monkeypatch.setattr(g['os'],'statvfs',lambda p:fakefs(2*1024**3-1) if p==base.parent else fakefs())
    elif kind=='state':monkeypatch.setattr(g['os'],'statvfs',lambda p:fakefs(4*1024**3-1) if p==state.parent else fakefs())
    else:monkeypatch.setattr(g['os'],'statvfs',lambda p:fakefs(inodes=65535))
    with pytest.raises(Error,match=code):m['_capacity']()


def test_memory_observation_failure_is_typed(monkeypatch,tmp_path):
    monkeypatch.setitem(g,'MEMINFO',tmp_path/'missing')
    with pytest.raises(Error,match='preflight_capacity_observation_failed'):m['_available_memory']()


def test_capacity_statvfs_failure_is_typed(capacity,monkeypatch):
    def refused(path):raise OSError('private detail')
    monkeypatch.setattr(g['os'],'statvfs',refused)
    with pytest.raises(Error,match='preflight_capacity_observation_failed'):m['_capacity']()


def test_protected_services_must_stay_active(monkeypatch):
    def show(name,keys):
        if name=='dead.service':return {'LoadState':'loaded','ActiveState':'inactive','SubState':'dead','MainPID':'0'}
        return {'LoadState':'loaded','ActiveState':'active','SubState':'running','MainPID':'10'}
    monkeypatch.setitem(g,'_show',show)
    value=m['_protected'](('mcp-server.service','caddy.service'))
    assert value['mcp-server.service']=={'loaded':True,'active':True,'sub_state':'running','main_pid':'10'}
    with pytest.raises(Error,match='preflight_protected_service_not_active'):m['_protected'](('dead.service',))


def test_default_protected_set_includes_vpn_panel():
    assert m['PROTECTED']==('mcp-server.service','mcp-test.service','caddy.service','x-ui.service')


def happy(monkeypatch):
    calls=[]
    monkeypatch.setitem(g,'_host',lambda:(calls.append('host') or {'root_console':True}))
    for name in ('_python','_ancestors','_landlock','_seccomp','_identity','_paths','_port','_capacity'):
        def value(name=name):
            calls.append(name);return {'checked':True}
        monkeypatch.setitem(g,name,value)
    def protected(units):
        calls.append('protected');return {unit:{'active':True} for unit in units}
    monkeypatch.setitem(g,'_protected',protected)
    return calls


def test_preflight_aggregates_read_only_checks(monkeypatch):
    calls=happy(monkeypatch)
    result=m['preflight']()
    assert result['ok'] is True and result['blockers']==[] and result['checks']['host']['root_console'] is True
    assert result['ready_for_separately_approved_install'] is True
    assert result['installation_authorized'] is False and result['config_changed'] is False
    assert result['services_restarted'] is False and result['packages_installed'] is False
    assert result['database_opened'] is False and result['credentials_read'] is False
    assert calls==['host','_python','_ancestors','_landlock','_seccomp','_identity','_paths','_port','_capacity','protected']


def test_preflight_collects_safe_blockers_and_continues(monkeypatch):
    calls=happy(monkeypatch)
    def refused():raise Error('preflight_landlock_unavailable')
    def capacity_refused():raise Error('preflight_memory_floor')
    monkeypatch.setitem(g,'_landlock',refused);monkeypatch.setitem(g,'_capacity',capacity_refused)
    result=m['preflight']()
    assert result['ok'] is False
    assert result['blockers']==['preflight_landlock_unavailable','preflight_memory_floor']
    assert result['ready_for_separately_approved_install'] is False
    assert calls[-1]=='protected'


def test_nonroot_stops_before_any_observation(monkeypatch):
    monkeypatch.setitem(g,'os',SimpleNamespace(geteuid=lambda:1000,getuid=lambda:1000))
    def explode(*args):raise AssertionError('observed without root')
    for name in ('_python','_ancestors','_landlock','_seccomp','_identity','_paths','_port','_capacity'):
        monkeypatch.setitem(g,name,explode)
    with pytest.raises(Error,match='preflight_root_console_required'):m['preflight']()


def test_main_prints_sanitized_json_and_exit_codes(monkeypatch,capsys):
    happy(monkeypatch);monkeypatch.setitem(g,'sys',SimpleNamespace(argv=['operator_preflight.py']))
    monkeypatch.setitem(g,'argparse',SimpleNamespace(ArgumentParser=lambda **k:_Parser()))
    assert m['main']()==0
    assert json.loads(capsys.readouterr().out)['ok'] is True


class _Parser:
    def add_argument(self,*args,**kwargs):pass
    def parse_args(self):return SimpleNamespace(protected=None)


def test_main_never_discloses_unexpected_errors(monkeypatch,capsys):
    happy(monkeypatch)
    monkeypatch.setitem(g,'_capacity',lambda:(_ for _ in ()).throw(RuntimeError('private detail')))
    monkeypatch.setitem(g,'sys',SimpleNamespace(argv=['operator_preflight.py']))
    monkeypatch.setitem(g,'argparse',SimpleNamespace(ArgumentParser=lambda **k:_Parser()))
    assert m['main']()==1
    text=capsys.readouterr().out
    assert 'private detail' not in text and json.loads(text)['error']=='preflight_review_required'
