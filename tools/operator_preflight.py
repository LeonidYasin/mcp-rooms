"""Read-only operator-console preflight for the fresh owner-first candidate.

No install, bootstrap, start, key/DB/Caddy read, package change, service restart or
configuration write. Every VPS invocation still needs separate owner approval and the
special password. A PASS authorizes no later stage; pending observations stay pending.
"""
import argparse
import ctypes as c
import json
import os
from pathlib import Path
import platform
import pwd
import grp
import stat
import subprocess
import sys

USER='mcp-rooms-candidate'
NAME=USER+'.service'
BUILD=USER+'-build.service'
BASE=Path('/opt')/USER
STATE=Path('/var/lib')/USER
UNIT=Path('/etc/systemd/system')/NAME
RUN_LOCK=Path('/run/mcp-rooms-operator')
UNIT_DIRS=('/etc/systemd/system','/run/systemd/system','/usr/lib/systemd/system','/lib/systemd/system')
PYTHON=Path('/usr/bin/python3.12')
LIB=Path('/usr/lib/python3.12')
CGROUP=Path('/sys/fs/cgroup/cgroup.controllers')
MEMINFO=Path('/proc/meminfo')
SECCOMP=Path('/proc/sys/kernel/seccomp/actions_avail')
TCP=(Path('/proc/net/tcp'),Path('/proc/net/tcp6'))
PORT=8766
PROTECTED=('mcp-server.service','mcp-test.service','caddy.service','x-ui.service')
HOST_MEMORY_FLOOR=2*1024**3
BASE_FREE_FLOOR=2*1024**3
STATE_FREE_FLOOR=4*1024**3
INODE_FREE_FLOOR=65536
LANDLOCK_ABI_FLOOR=3
SECCOMP_ACTIONS=frozenset({'kill_process','errno'})
SECCOMP_SYSCALL=317
SECCOMP_SET_MODE_FILTER=1
SECCOMP_RET_ALLOW=0x7fff0000
PR_SET_NO_NEW_PRIVS=38
BPF_RET_K=0x06
ENV={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONUTF8':'1'}


class _SockFilter(c.Structure):
    _fields_=(('code',c.c_ushort),('jt',c.c_ubyte),('jf',c.c_ubyte),('k',c.c_uint32))


class _SockFprog(c.Structure):
    _fields_=(('len',c.c_ushort),('filter',c.POINTER(_SockFilter)))


class PreflightError(Exception):pass


def _host():
    if os.geteuid()!=0 or os.getuid()!=0:
        raise PreflightError('preflight_root_console_required')
    if platform.system()!='Linux' or platform.machine()!='x86_64':
        raise PreflightError('preflight_host_refused')
    if not CGROUP.is_file():
        raise PreflightError('preflight_cgroup_v2_required')
    return {'root_console':True,'linux_x86_64':True,'cgroup_v2':True}


def _trusted_dir(path,code):
    path=Path(path)
    try:
        if not path.is_absolute() or path.resolve()!=path:raise PreflightError(code)
        st=path.lstat()
    except PreflightError:raise
    except OSError:raise PreflightError(code) from None
    if not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:
        raise PreflightError(code)


def _trusted_file(path):
    try:st=path.lstat()
    except OSError:raise PreflightError('preflight_python_untrusted') from None
    if (not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022
            or st.st_nlink!=1 or path.resolve()!=path):
        raise PreflightError('preflight_python_untrusted')


def _python():
    _trusted_file(PYTHON)
    _trusted_dir(LIB,'preflight_python_untrusted')
    probe='import sys;raise SystemExit(0 if sys.version_info[:2]==(3,12) else 1)'
    try:
        result=subprocess.run([str(PYTHON),'-I','-c',probe],env=ENV,cwd='/',
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
    except (OSError,subprocess.SubprocessError):
        raise PreflightError('preflight_python_probe_failed') from None
    if result.returncode:raise PreflightError('preflight_python_version_mismatch')
    return {'trusted':True,'version':'3.12'}


def _ancestors():
    _trusted_dir(BASE.parent,'preflight_untrusted_ancestor')
    _trusted_dir(STATE.parent,'preflight_untrusted_ancestor')
    _trusted_dir(UNIT.parent,'preflight_untrusted_ancestor')
    _trusted_dir(RUN_LOCK.parent,'preflight_untrusted_ancestor')
    return {'install_parent':True,'state_parent':True,'unit_parent':True,'run_parent':True}


def _libc():
    libc=c.CDLL(None,use_errno=True)
    libc.syscall.restype=c.c_long
    return libc


def _landlock():
    try:
        abi=int(_libc().syscall(c.c_long(444),c.c_void_p(),c.c_size_t(0),c.c_uint(1)))
    except (OSError,AttributeError,ValueError,TypeError):
        raise PreflightError('preflight_landlock_unavailable') from None
    if abi<0:raise PreflightError('preflight_landlock_unavailable')
    if abi<LANDLOCK_ABI_FLOOR:raise PreflightError('preflight_landlock_abi_insufficient')
    return {'abi':abi,'floor':LANDLOCK_ABI_FLOOR}


def _seccomp_filter():
    try:pid=os.fork()
    except (AttributeError,OSError):
        raise PreflightError('preflight_seccomp_unavailable') from None
    if pid==0:
        try:
            libc=_libc()
            if libc.prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0)!=0:os._exit(1)
            flt=(_SockFilter*1)(_SockFilter(BPF_RET_K,0,0,SECCOMP_RET_ALLOW))
            prog=_SockFprog(1,flt)
            result=libc.syscall(c.c_long(SECCOMP_SYSCALL),c.c_uint(SECCOMP_SET_MODE_FILTER),
                c.c_size_t(0),c.c_void_p(c.addressof(prog)))
            os._exit(0 if result==0 else 1)
        except BaseException:
            os._exit(2)
    try:_,status=os.waitpid(pid,0)
    except (AttributeError,OSError):
        raise PreflightError('preflight_seccomp_unavailable') from None
    if not os.WIFEXITED(status) or os.WEXITSTATUS(status)!=0:
        raise PreflightError('preflight_seccomp_unavailable')
    return True


def _seccomp():
    try:actions=frozenset(SECCOMP.read_text().split())
    except (OSError,UnicodeError):
        raise PreflightError('preflight_seccomp_unavailable') from None
    if not SECCOMP_ACTIONS<=actions:raise PreflightError('preflight_seccomp_unavailable')
    _seccomp_filter()
    return {'filter_supported':True,'required_actions':sorted(SECCOMP_ACTIONS)}


def _identity():
    for getter in (pwd.getpwnam,grp.getgrnam):
        try:getter(USER)
        except KeyError:continue
        raise PreflightError('preflight_candidate_identity_exists')
    return {'exists':False}


def _show(name,keys):
    argv=['/usr/bin/systemctl','show',name,'--no-pager','--property='+','.join(keys)]
    try:
        result=subprocess.run(argv,env=ENV,cwd='/',stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=10)
        if len(result.stdout)>16384:raise PreflightError('preflight_unit_observation_failed')
        values={}
        for line in result.stdout.splitlines():
            key,value=line.split('=',1)
            if key in values:raise PreflightError('preflight_unit_observation_failed')
            values[key]=value
        if set(values)!=set(keys):
            raise PreflightError('preflight_unit_observation_failed')
        if result.returncode and not(result.returncode==1 and values['LoadState']=='not-found'):
            raise PreflightError('preflight_unit_observation_failed')
        return values
    except PreflightError:raise
    except (OSError,ValueError,subprocess.SubprocessError):
        raise PreflightError('preflight_unit_observation_failed') from None


def _absent_unit(name):
    values=_show(name,['LoadState','ActiveState','MainPID','ControlGroup','FragmentPath','DropInPaths'])
    if (values['LoadState']!='not-found' or values['MainPID']!='0' or values['ControlGroup']
            or values['FragmentPath'] or values['DropInPaths']):
        raise PreflightError('preflight_candidate_unit_exists')
    for root in UNIT_DIRS:
        for suffix in ('','.d'):
            path=Path(root)/(name+suffix)
            if path.exists() or path.is_symlink():
                raise PreflightError('preflight_candidate_unit_exists')
    return {'loaded':False,'files':False}


def _paths():
    for path in (BASE,STATE,UNIT,RUN_LOCK):
        if path.exists() or path.is_symlink():
            raise PreflightError('preflight_candidate_path_exists')
    return {'candidate_service':_absent_unit(NAME),'candidate_build':_absent_unit(BUILD),
        'paths_absent':True}


def _listeners():
    ports=set();seen=False
    for path in TCP:
        try:lines=path.read_text().splitlines()
        except OSError:continue
        seen=True
        for line in lines[1:]:
            parts=line.split()
            if len(parts)<4:raise PreflightError('preflight_port_observation_failed')
            try:port=int(parts[1].rsplit(':',1)[1],16)
            except (ValueError,IndexError):
                raise PreflightError('preflight_port_observation_failed') from None
            if parts[3]=='0A':ports.add(port)
    if not seen:raise PreflightError('preflight_port_observation_failed')
    return ports


def _port():
    if PORT in _listeners():raise PreflightError('preflight_candidate_port_in_use')
    return {'port':PORT,'free':True}


def _available_memory():
    try:
        line=next(value for value in MEMINFO.read_text().splitlines() if value.startswith('MemAvailable:'))
        return int(line.split()[1])*1024
    except (OSError,UnicodeError,StopIteration,ValueError,IndexError):
        raise PreflightError('preflight_capacity_observation_failed') from None


def _capacity():
    available=_available_memory()
    try:
        base=os.statvfs(BASE.parent);state=os.statvfs(STATE.parent)
    except OSError:raise PreflightError('preflight_capacity_observation_failed') from None
    if available<HOST_MEMORY_FLOOR:raise PreflightError('preflight_memory_floor')
    base_free=base.f_bavail*base.f_frsize;state_free=state.f_bavail*state.f_frsize
    if base_free<BASE_FREE_FLOOR:raise PreflightError('preflight_install_disk_floor')
    if state_free<STATE_FREE_FLOOR:raise PreflightError('preflight_state_disk_floor')
    if base.f_favail<INODE_FREE_FLOOR or state.f_favail<INODE_FREE_FLOOR:
        raise PreflightError('preflight_inode_floor')
    return {'memory_available_bytes':available,'install_free_bytes':base_free,
        'state_free_bytes':state_free,'inode_free_floor':INODE_FREE_FLOOR}


def _protected(units):
    result={}
    for unit in units:
        values=_show(unit,['LoadState','ActiveState','SubState','MainPID'])
        if values['LoadState']!='loaded' or values['ActiveState']!='active':
            raise PreflightError('preflight_protected_service_not_active')
        result[unit]={'loaded':True,'active':True,'sub_state':values['SubState'],
            'main_pid':values['MainPID']}
    return result


def preflight(protected=PROTECTED):
    host=_host();checks={'host':host};blockers=[]
    def run(name,fn):
        try:checks[name]=fn()
        except PreflightError as exc:blockers.append(str(exc))
    run('python',_python);run('ancestors',_ancestors);run('landlock',_landlock)
    run('seccomp',_seccomp);run('candidate_identity',_identity);run('candidate_paths',_paths)
    run('candidate_port',_port);run('capacity',_capacity)
    run('protected_services',lambda:_protected(protected))
    ready=not blockers
    return {'ok':ready,'result':'PREFLIGHT','checks':checks,'blockers':sorted(blockers),
        'ready_for_separately_approved_install':ready,'installation_authorized':False,
        'config_changed':False,'services_restarted':False,'packages_installed':False,
        'database_opened':False,'credentials_read':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protected-unit',action='append',dest='protected')
    args=parser.parse_args();os.umask(0o077)
    try:
        result=preflight(tuple(args.protected) if args.protected else PROTECTED)
        print(json.dumps(result,sort_keys=True));return 0 if result['ok'] else 2
    except PreflightError as exc:
        print(json.dumps({'ok':False,'result':'STOP','error':str(exc),
            'installation_authorized':False,'config_changed':False,'services_restarted':False}))
        return 1
    except Exception:
        print(json.dumps({'ok':False,'result':'STOP','error':'preflight_review_required',
            'installation_authorized':False,'config_changed':False,'services_restarted':False}))
        return 1


if __name__=='__main__':raise SystemExit(main())
