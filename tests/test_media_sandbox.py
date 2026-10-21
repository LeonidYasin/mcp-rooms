"""Kernel enforcement proofs in Actions child processes, never in pytest parent."""
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from mcp_rooms import media_sandbox as s
from mcp_rooms import media_worker as m
from mcp_rooms.domain import DomainError
from test_media_worker import image

NATIVE=sys.platform=='linux' and sys.version_info>=(3,11)

@pytest.fixture
def state(tmp_path):
    root=tmp_path/'state';root.mkdir(mode=0o700)
    for name in ('owner.key','market.sqlite3','profile.json'):
        p=root/name;p.write_bytes(b'CI synthetic private bytes');p.chmod(0o600)
    return root


def test_fixed_bpf_policy_has_arch_x32_network_process_and_escape_guards():
    rows=s._filter_rows()
    assert rows[:3]==[(0x20,0,0,4),(0x15,1,0,s.AUDIT_ARCH_X86_64),(0x06,0,0,0x80000000)]
    assert rows[4]==(0x35,0,1,0x40000000)
    assert rows[6]==(0x35,0,1,450)
    for number in (16,72,73,90,91,92,93,94,132,188,189,190,197,198,199,235,260,261,268,280,41,53,56,59,62,101,129,297,310,311,322,425,426,427,438):
        assert number in s.DENIED_SYSCALLS and (0x15,0,1,number) in rows
    assert rows[-1]==(0x06,0,0,0x7fff0000)
    assert s.HANDLED_FS==(1<<15)-1


@pytest.mark.parametrize('value',[None,True,{},'/relative/not-absolute'])
def test_untrusted_policy_objects_rejected(value):
    if value is None:
        with pytest.raises(DomainError):m.PhotoWorker().check_sandbox()
    else:
        with pytest.raises(DomainError):m.PhotoWorker(sandbox=value)


def test_runtime_allowlist_cannot_contain_state(state,monkeypatch):
    monkeypatch.setattr(s.sysconfig,'get_paths',lambda:{k:str(state.parent) for k in ('stdlib','platstdlib','purelib','platlib')})
    with pytest.raises(DomainError,match='media_sandbox_policy_invalid'):s._runtime_roots(state)


def test_architecture_and_missing_kernel_fail_before_any_restriction(state,monkeypatch):
    monkeypatch.setattr(s.platform,'machine',lambda:'aarch64')
    with pytest.raises(DomainError,match='media_sandbox_unavailable'):s.enforce(s.NativeSandbox(state))
    # Only architecture-mismatch branch is executed in the pytest parent.
    assert (state/'owner.key').read_bytes()==b'CI synthetic private bytes'


def test_launch_contract_no_shell_env_fds_or_client_allowlist(state,monkeypatch):
    calls=[]
    monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**kw:calls.append((a,kw)))
    m._launch_sandbox(s.NativeSandbox(state),check=True)
    args,kw=calls[0]
    assert args[0]==[sys.executable,'-I','-B','-m','mcp_rooms.media_worker_child','--sandbox-check',str(state)]
    assert kw['env']=={'LANG':'C.UTF-8'} and kw['cwd']=='/'
    assert kw['close_fds'] and kw['start_new_session']
    assert kw['stderr']==subprocess.DEVNULL
    assert not kw.get('shell') and not kw.get('pass_fds') and 'preexec_fn' not in kw


@pytest.mark.skipif(not NATIVE,reason='Linux native sandbox requires Python>=3.11')
def test_real_kernel_probe_and_parent_remains_unrestricted(state):
    worker=m.PhotoWorker(max_parallel=1,sandbox=s.NativeSandbox(state))
    checked=worker.check_sandbox()
    assert checked['policy']==s.POLICY and checked['abi']>=3 and checked['checked'] is True
    assert (state/'owner.key').read_bytes()==b'CI synthetic private bytes'
    import socket
    sock=socket.socket();sock.close()  # Proves pytest parent did not inherit restrictions.


@pytest.mark.skipif(not NATIVE,reason='Linux native sandbox requires Python>=3.11')
@pytest.mark.parametrize('fmt,mime',[('PNG','image/png'),('JPEG','image/jpeg')])
def test_real_codec_after_filesystem_and_network_lockdown(state,fmt,mime):
    worker=m.PhotoWorker(max_parallel=1,sandbox=s.NativeSandbox(state))
    result=worker.normalize(image(fmt),mime)
    assert (result.width,result.height)==(20,10) and result.data.startswith(b'\xff\xd8\xff')
    assert result.source_format==fmt


@pytest.mark.skipif(not NATIVE,reason='Linux native sandbox requires Python>=3.11')
def test_external_secrets_read_write_process_signal_and_socketpair_denied(state,tmp_path):
    outside=tmp_path/'outside.key';outside.write_text('CI synthetic secret');outside.chmod(0o600)
    before=(state/'owner.key').stat()
    # Fixed synthetic CI program, not exposed as a runtime launcher/API.
    code=r'''
import ctypes as c, errno, json, os, pathlib, socket, sys
from mcp_rooms.media_sandbox import NativeSandbox,enforce
root=pathlib.Path(sys.argv[1]);outside=pathlib.Path(sys.argv[2])
enforce(NativeSandbox(root))
def blocked(fn):
    try:fn()
    except OSError as e:return e.errno in (errno.EPERM,errno.EACCES)
    return False
result={}
for path in (root/'owner.key',root/'market.sqlite3',root/'profile.json',outside):
    result[str(len(result))]=blocked(lambda p=path:p.read_bytes())
result['write']=blocked(lambda:outside.write_bytes(b'must-not-write'))
secret=root/'owner.key'
result['chmod']=blocked(lambda:os.chmod(secret,0o644))
result['chown']=blocked(lambda:os.chown(secret,-1,-1))
result['utime']=blocked(lambda:os.utime(secret,ns=(1,1)))
result['setxattr']=blocked(lambda:os.setxattr(secret,'user.synthetic',b'CI'))
result['removexattr']=blocked(lambda:os.removexattr(secret,'user.synthetic'))
result['socketpair']=blocked(socket.socketpair)
result['fork']=blocked(os.fork)
result['signal']=blocked(lambda:os.kill(os.getppid(),0))
libc=c.CDLL(None,use_errno=True);libc.syscall.restype=c.c_long
for n in (16,72,73,91,93,189,190,198,199,235,260,261,268,280,129,297,310,311,322,425,426,427,438,450,452,463,466):
    c.set_errno(0);rc=libc.syscall(c.c_long(n),0,0,0,0,0,0)
    result['sys'+str(n)]=rc==-1 and c.get_errno()==errno.EPERM
print(json.dumps(result))
'''
    result=subprocess.run([sys.executable,'-I','-B','-c',code,str(state),str(outside)],
                          capture_output=True,timeout=10,close_fds=True,env={'LANG':'C.UTF-8'})
    assert result.returncode==0,result.stderr.decode(errors='replace')[-1200:]
    checks=json.loads(result.stdout)
    assert len(checks)>=40 and all(v is True for v in checks.values())
    assert outside.read_text()=='CI synthetic secret'
    after=(state/'owner.key').stat()
    assert (after.st_mode,after.st_uid,after.st_gid,after.st_mtime_ns,after.st_ctime_ns)==(before.st_mode,before.st_uid,before.st_gid,before.st_mtime_ns,before.st_ctime_ns)
    assert (state/'owner.key').read_bytes()==b'CI synthetic private bytes'


@pytest.mark.skipif(not NATIVE,reason='Linux native sandbox requires Python>=3.11')
def test_kernel_unavailable_in_child_is_typed_no_fallback(state):
    code=r'''
import json,pathlib,sys
from mcp_rooms import media_sandbox as s
from mcp_rooms.domain import DomainError
s.SYS_CREATE=2147483647
try:s.enforce(s.NativeSandbox(pathlib.Path(sys.argv[1])))
except DomainError as e:print(json.dumps({'error':e.code}))
else:raise SystemExit('unexpected policy success')
'''
    result=subprocess.run([sys.executable,'-I','-B','-c',code,str(state)],capture_output=True,timeout=10)
    assert result.returncode==0
    assert json.loads(result.stdout)=={'error':'media_sandbox_unavailable'}


@pytest.mark.skipif(not NATIVE,reason='Linux native sandbox requires Python>=3.11')
@pytest.mark.parametrize('behavior,code',[
    ("import sys;sys.stdin.buffer.read();print('{\"v\":1,\"error\":\"media_sandbox_unavailable\"}')",'media_sandbox_unavailable'),
    ('import time;time.sleep(30)','media_worker_timeout'),
])
def test_sandbox_failure_reaps_releases_and_never_calls_plain_launcher(state,monkeypatch,behavior,code):
    children=[]
    def launch(*args,**kw):
        child=subprocess.Popen([sys.executable,'-I','-c',behavior],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL,close_fds=True,start_new_session=True)
        children.append(child);return child
    monkeypatch.setattr(m,'_launch_sandbox',launch)
    monkeypatch.setattr(m,'_launch',lambda:pytest.fail('plain fallback forbidden'))
    monkeypatch.setattr(m,'WALL_SECONDS',.25)
    worker=m.PhotoWorker(max_parallel=1,sandbox=s.NativeSandbox(state))
    for _ in range(2):
        with pytest.raises(DomainError,match=code):worker.normalize(b'synthetic','image/png')
    assert all(p.poll() is not None for p in children)
    assert worker._slots.acquire(False);worker._slots.release()


def test_policy_precedes_decoder_and_input():
    import inspect
    from mcp_rooms import media_worker_child
    source=inspect.getsource(media_worker_child.main)
    assert source.index('abi=enforce(policy)')<source.index('from .media_image import normalize_photo')<source.index('sys.stdin.buffer.readline')
