"""Unprivileged fresh offline installation/process rehearsal. NOT a VPS systemd installer.

Trusted operator tool only, no MCP endpoint. No root/account/unit/Caddy operations.
CI uses synthetic private targets. Real execution needs separate owner permission.
"""
import argparse
from contextlib import contextmanager
from hashlib import sha256
import fcntl
import http.client
import json
import os
from pathlib import Path
import platform
import re
import runpy
import select
import signal
import socket
import stat
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
FORMAT='mcp-rooms/lifecycle-rehearsal/v1'
PORT=8766
_CHILDREN={}


class LifecycleError(Exception):pass


def _host():
    if (sys.version_info[:2]!=(3,12) or platform.system()!='Linux' or platform.machine()!='x86_64'
            or not 0<os.getuid()==os.geteuid() or not 0<os.getgid()==os.getegid()
            or 0 in os.getgroups() or not hasattr(os,'pidfd_open')):
        raise LifecycleError('lifecycle_host_unsupported')
    caps=Path('/proc/self/status').read_text()
    for name in ('CapEff','CapPrm','CapInh','CapAmb'):
        match=re.search(r'^'+name+r':\s+([0-9a-fA-F]+)$',caps,re.M)
        if match is None or int(match[1],16)!=0:raise LifecycleError('lifecycle_privileges_refused')


def _directory(p):
    p=Path(p);st=p.lstat()
    if (not p.is_absolute() or p.resolve()!=p or not stat.S_ISDIR(st.st_mode)
            or st.st_uid!=os.geteuid() or stat.S_IMODE(st.st_mode)!=0o700):
        raise LifecycleError('lifecycle_private_directory_required')
    return st


def _read(p,limit=16384):
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
    try:
        st=os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or st.st_nlink!=1
                or stat.S_IMODE(st.st_mode)!=0o600 or not 0<st.st_size<=limit):
            raise LifecycleError('lifecycle_unsafe_file')
        data=os.read(fd,limit+1)
        after=os.fstat(fd);named=Path(p).lstat()
        if len(data)!=st.st_size or any(getattr(st,k)!=getattr(after,k) or getattr(after,k)!=getattr(named,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')):
            raise LifecycleError('lifecycle_changed_file')
        return data
    finally:os.close(fd)


def _pairs(items):
    value={}
    for k,v in items:
        if k in value:raise LifecycleError('lifecycle_invalid_receipt')
        value[k]=v
    return value


def _json(p):
    try:return json.loads(_read(p),object_pairs_hook=_pairs)
    except (ValueError,UnicodeError,RecursionError):raise LifecycleError('lifecycle_invalid_receipt') from None


def _write_new(p,value):
    data=(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    created=os.fstat(fd)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    except BaseException:
        try:
            named=p.lstat()
            if (named.st_dev,named.st_ino)==(created.st_dev,created.st_ino):p.unlink()
        except OSError:raise LifecycleError('lifecycle_marker_cleanup_required') from None
        raise


def _fingerprint(p):
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or st.st_nlink!=1 or st.st_mode&0o022 or not 1<=st.st_size<=48*1024*1024:
            raise LifecycleError('lifecycle_interpreter_mismatch')
        h=sha256()
        while True:
            b=os.read(fd,65536)
            if not b:break
            h.update(b)
        after=os.fstat(fd);named=p.lstat()
        for field in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink','st_mode'):
            if getattr(st,field)!=getattr(after,field) or getattr(after,field)!=getattr(named,field):
                raise LifecycleError('lifecycle_interpreter_mismatch')
        return {'device':st.st_dev,'inode':st.st_ino,'sha256':h.hexdigest(),'byte_size':st.st_size}
    finally:os.close(fd)


def _env():
    return {'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONUTF8':'1','PIP_CONFIG_FILE':'/dev/null'}


def _run(argv,timeout):
    try:
        subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                       env=_env(),cwd='/tmp',check=True,timeout=timeout,close_fds=True)
    except (subprocess.SubprocessError,OSError):raise LifecycleError('lifecycle_command_failed') from None


def _python(root):return root/'venv/bin/python'


def _argv(root,resource,action):
    return [str(_python(root)),'-I','-m','mcp_rooms.test_candidate',action,
            '--state',str(root/'profile'),'--resource',resource]


@contextmanager
def _lock(root):
    _directory(root);p=root/'operator.lock'
    fd=os.open(p,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size!=0 or st.st_nlink!=1 or st.st_uid!=os.geteuid() or stat.S_IMODE(st.st_mode)!=0o600:
            raise LifecycleError('lifecycle_unsafe_lock')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise LifecycleError('lifecycle_busy') from None
        yield
    finally:os.close(fd)


def _installed(root):
    st=_directory(root);m=_json(root/'install.json')
    if (type(m) is not dict or set(m)!={'format','source_sha','resource','uid','root_device','root_inode','interpreter','runtime_lock_sha256'}
            or m['format']!=FORMAT or type(m['source_sha']) is not str or re.fullmatch('[0-9a-f]{40}',m['source_sha']) is None
            or type(m['runtime_lock_sha256']) is not str or re.fullmatch('[0-9a-f]{64}',m['runtime_lock_sha256']) is None
            or type(m['uid']) is not int or m['uid']!=os.geteuid()
            or type(m['root_device']) is not int or type(m['root_inode']) is not int
            or (m['root_device'],m['root_inode'])!=(st.st_dev,st.st_ino)
            or m['interpreter']!=_fingerprint(_python(root))):
        raise LifecycleError('lifecycle_invalid_receipt')
    validator=runpy.run_path(str(ROOT/'tools/operator_plan.py'))['_resource']
    try:validator(m['resource'])
    except Exception:raise LifecycleError('lifecycle_invalid_receipt') from None
    return m


def install(bundle,root,source_sha,lock_sha,resource):
    """Fresh-only private rehearsal target; no profile/key/process until explicit next call."""
    _host();root=Path(root);bundle=Path(bundle)
    planner=runpy.run_path(str(ROOT/'tools/operator_plan.py'))
    planner['_resource'](resource)
    verifier=runpy.run_path(str(ROOT/'tools/operator_bundle.py'))['verify']
    verifier(bundle,source_sha,lock_sha)
    _directory(root.parent)
    if root.resolve()!=root or not root.is_absolute():raise LifecycleError('lifecycle_private_directory_required')
    if root==bundle or root in bundle.parents or bundle in root.parents:
        raise LifecycleError('lifecycle_overlap_refused')
    os.mkdir(root,0o700) # O_EXCL equivalent for directory; dangling aliases also refused.
    lockfd=os.open(root/'operator.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(lockfd)
    with _lock(root):
        _run([sys.executable,'-I','-m','venv','--copies',str(root/'venv')],90)
        _run([str(_python(root)),'-I','-m','pip','--isolated','install','--disable-pip-version-check',
              '--no-index','--only-binary=:all:','--find-links',str(bundle/'wheels'),
              '--require-hashes','-r',str(bundle/'install.lock')],180)
        _run([str(_python(root)),'-I','-m','pip','check'],30)
        verifier(bundle,source_sha,lock_sha) # No ready marker if inputs changed during install.
        st=_directory(root)
        receipt={'format':FORMAT,'source_sha':source_sha,'runtime_lock_sha256':lock_sha,
                 'resource':resource,'uid':os.geteuid(),'root_device':st.st_dev,'root_inode':st.st_ino,
                 'interpreter':_fingerprint(_python(root))}
        _write_new(root/'install.json',receipt)
    return {'installed':True,'profile_created':False,'started':False,'source_sha':source_sha}


def bootstrap(root):
    """Explicit credential-creating step; real use requires separate key issuance approval."""
    _host();root=Path(root)
    with _lock(root):
        m=_installed(root)
        if os.path.lexists(root/'profile'):raise LifecycleError('lifecycle_existing_profile')
        _run(_argv(root,m['resource'],'bootstrap'),60)
    return {'profile_created':True,'key_returned_or_read':False}


def _boot():return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def _identity(pid):
    # Linux comm can contain spaces/parentheses; split after its final ')'.
    data=Path(f'/proc/{pid}/stat').read_text();tail=data[data.rindex(')')+2:].split()
    status=Path(f'/proc/{pid}/status').read_text()
    uid=[int(v) for v in re.search(r'^Uid:\s+(.+)$',status,re.M)[1].split()]
    return {'pid':pid,'start_ticks':int(tail[19]),'uid':uid,
            'cmdline_sha256':sha256(Path(f'/proc/{pid}/cmdline').read_bytes()).hexdigest(),
            'boot_id':_boot()}


def _expected_cmd(root,resource):return sha256(b'\0'.join(a.encode() for a in _argv(root,resource,'serve'))+b'\0').hexdigest()


def _owned_listener(pid):
    # The checked PID, not merely some process on the same local port, owns a listen socket.
    sockets=set()
    for p in Path(f'/proc/{pid}/fd').iterdir():
        try:target=os.readlink(p)
        except FileNotFoundError:continue
        if target.startswith('socket:['):sockets.add(target[8:-1])
    for line in Path('/proc/net/tcp').read_text().splitlines()[1:]:
        fields=line.split()
        if fields[1]==f'0100007F:{PORT:04X}' and fields[3]=='0A' and fields[9] in sockets:return True
    return False


def _check_process(root,m,receipt):
    if type(receipt) is not dict or set(receipt)!={'identity','root_device','root_inode','source_sha'}:
        raise LifecycleError('lifecycle_process_mismatch')
    identity=receipt['identity']
    if (type(identity) is not dict or set(identity)!={'pid','start_ticks','uid','cmdline_sha256','boot_id'}
            or type(identity['pid']) is not int or identity['pid']<=1 or type(identity['start_ticks']) is not int
            or identity['uid']!=[os.geteuid()]*4 or type(identity['uid']) is not list
            or any(type(v) is not int for v in identity['uid'])
            or type(receipt['root_device']) is not int or type(receipt['root_inode']) is not int
            or identity['cmdline_sha256']!=_expected_cmd(root,m['resource'])
            or identity['boot_id']!=_boot() or receipt['source_sha']!=m['source_sha']
            or (receipt['root_device'],receipt['root_inode'])!=(m['root_device'],m['root_inode'])):
        raise LifecycleError('lifecycle_process_mismatch')
    return identity


def _pinned(root,m):
    receipt=_json(root/'process.json');expected=_check_process(root,m,receipt)
    try:fd=os.pidfd_open(expected['pid'],0)
    except ProcessLookupError:return None,expected
    try:
        try:actual=_identity(expected['pid'])
        except FileNotFoundError:
            os.close(fd);return None,expected
        if actual!=expected:raise LifecycleError('lifecycle_process_mismatch')
        return fd,expected
    except BaseException:os.close(fd);raise


def _transport():
    conn=http.client.HTTPConnection('127.0.0.1',PORT,timeout=1)
    try:
        conn.request('POST','/mcp',body=b'{}',headers={'Content-Type':'application/json'})
        response=conn.getresponse()
        # No key read/transmitted. A successful auth bypass is also a refusal.
        return response.status==401
    finally:conn.close()


def _terminate(fd,identity,timeout=15):
    try:signal.pidfd_send_signal(fd,signal.SIGTERM)
    except ProcessLookupError:pass
    if not select.select([fd],[],[],timeout)[0]:raise LifecycleError('lifecycle_stop_timeout')
    child=_CHILDREN.pop((identity['pid'],identity['start_ticks']),None)
    if child is not None:child.wait(timeout=1)


def _health(root,m):
    fd,identity=_pinned(root,m)
    if fd is None:raise LifecycleError('lifecycle_not_running')
    try:
        if select.select([fd],[],[],0)[0] or not _owned_listener(identity['pid']) or not _transport():
            raise LifecycleError('lifecycle_not_ready')
        return {'running':True,'owned_loopback_listener':True,'unauthenticated_http':401,
                'authenticated_acceptance':False,'resource_budget_accepted':False}
    finally:os.close(fd)


def start(root):
    _host();root=Path(root)
    with _lock(root):
        m=_installed(root)
        if os.path.lexists(root/'process.json'):
            old=_json(root/'process.json');fd,identity=_pinned(root,m)
            if fd is not None:
                try:
                    if not select.select([fd],[],[],0)[0]:raise LifecycleError('lifecycle_process_record_exists')
                finally:os.close(fd)
            # Preserve the stopped receipt before retiring only its current name.
            if _json(root/'process.json')!=old:raise LifecycleError('lifecycle_process_mismatch')
            _write_new(root/('stopped-'+str(identity['start_ticks'])+'.json'),old)
            (root/'process.json').unlink()
        _run(_argv(root,m['resource'],'check'),30)
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as probe:
            try:probe.bind(('127.0.0.1',PORT))
            except OSError:raise LifecycleError('lifecycle_port_busy') from None
        # Port probe is not a reservation. Listener ownership is rechecked after start.
        child=subprocess.Popen(_argv(root,m['resource'],'serve'),stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=_env(),cwd='/tmp',
            start_new_session=True,close_fds=True)
        fd=None;identity=None;receipt_created=False
        try:
            fd=os.pidfd_open(child.pid,0);identity=_identity(child.pid)
            if identity['uid']!=[os.geteuid()]*4 or identity['cmdline_sha256']!=_expected_cmd(root,m['resource']):
                raise LifecycleError('lifecycle_process_mismatch')
            _CHILDREN[(child.pid,identity['start_ticks'])]=child
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                if child.poll() is not None:raise LifecycleError('lifecycle_start_failed')
                if _owned_listener(child.pid):
                    try:
                        if _transport():break
                    except (OSError,http.client.HTTPException):pass
                time.sleep(0.05)
            else:raise LifecycleError('lifecycle_start_timeout')
            receipt={'identity':identity,'root_device':m['root_device'],'root_inode':m['root_inode'],'source_sha':m['source_sha']}
            _write_new(root/'process.json',receipt);receipt_created=True
            return _health(root,m)
        except BaseException:
            # Only the exact child retained via pidfd. No kill by a caller-provided PID.
            if fd is not None:
                _terminate(fd,identity or {'pid':child.pid,'start_ticks':-1})
            else:
                # No validated handle: do not signal an unpinned/reused PID.
                raise LifecycleError('lifecycle_start_recovery_required') from None
            if receipt_created:(root/'process.json').unlink(missing_ok=True)
            raise
        finally:
            if fd is not None:os.close(fd)


def health(root):
    _host();root=Path(root)
    with _lock(root):return _health(root,_installed(root))


def stop(root):
    _host();root=Path(root)
    with _lock(root):
        m=_installed(root);fd,identity=_pinned(root,m)
        if fd is None:return {'stopped':True,'already_exited':True,'state_preserved':True,'descendants_supervised':False}
        try:_terminate(fd,identity)
        finally:os.close(fd)
        return {'stopped':True,'already_exited':False,'state_preserved':True,'descendants_supervised':False}


def rollback(root):
    # No delete, data rewind, promotion, key revocation or online reinstallation.
    result=stop(root);return {**result,'rollback':'stop-only-preserve-all','data_rewound':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['install','bootstrap','start','health','stop','rollback'])
    p.add_argument('--root',required=True);p.add_argument('--bundle');p.add_argument('--source-sha')
    p.add_argument('--lock-sha256');p.add_argument('--resource');a=p.parse_args();os.umask(0o077)
    try:
        if a.action=='install':
            if not all((a.bundle,a.source_sha,a.lock_sha256,a.resource)):p.error('install requires bundle/source/lock/resource')
            result=install(a.bundle,a.root,a.source_sha,a.lock_sha256,a.resource)
        else:result=globals()[a.action](a.root)
        print(json.dumps({'ok':True,**result},sort_keys=True));return 0
    except Exception:
        # Fixed error only: raw pip/bootstrap output, private path/key/env never leaked.
        print(json.dumps({'ok':False,'error':'lifecycle_refused_review_private_state'}));return 1


if __name__=='__main__':raise SystemExit(main())
