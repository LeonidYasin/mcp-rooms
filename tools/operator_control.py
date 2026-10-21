"""Guarded bootstrap/start/stop controller for one reviewed fresh candidate.

This never installs, enables, upgrades, deletes, restores, prints/reads owner keys,
or touches Caddy. Every real VPS action still needs separate owner approval and the
special password. Failed bootstrap leaves private state blocked for manual review.
"""
from contextlib import contextmanager
from hashlib import sha256
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import runpy
import socket
import stat
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
USER='mcp-rooms-candidate'
NAME=USER+'.service'
BOOTSTRAP=USER+'-bootstrap.service'
CHECK=USER+'-check.service'
BASE=Path('/opt')/USER
STATE=Path('/var/lib')/USER
PROFILE=STATE/'owner-first'
UNIT=Path('/etc/systemd/system')/NAME
LOCK=Path('/run/mcp-rooms-operator')/'control.lock'
FORMAT='mcp-rooms/fresh-install/v1'
BOOTSTRAP_AUTH='CREATE-FRESH-OWNER-PROFILE'
START_AUTH='START-OWNER-FIRST-CANDIDATE'
MEMORY_MAX=1024**3
HOST_MEMORY_FLOOR=2*1024**3
BASE_FREE_FLOOR=2*1024**3
STATE_FREE_FLOOR=4*1024**3
INSTALL_ALLOCATED_CEILING=1024**3
STATE_ALLOCATED_CEILING=1024**3
INODE_FREE_FLOOR=65536
ENV={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONUTF8':'1','PIP_CONFIG_FILE':'/dev/null'}


class ControlError(Exception):pass


def _installer():return runpy.run_path(str(ROOT/'tools/operator_install.py'))


def _pairs(items):
    value={}
    for key,item in items:
        if key in value:raise ControlError('control_invalid_receipt')
        value[key]=item
    return value


def _read_json(data):
    try:return json.loads(data,object_pairs_hook=_pairs)
    except (ValueError,UnicodeError,RecursionError):raise ControlError('control_invalid_receipt') from None


@contextmanager
def _lock(i):
    i['_chain'](LOCK.parent)
    fd=os.open(LOCK,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,0o600)
    try:
        st=os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_nlink!=1
                or stat.S_IMODE(st.st_mode)!=0o600 or st.st_size):
            raise ControlError('control_lock_refused')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ControlError('control_busy') from None
        yield
    finally:os.close(fd)


def _show():
    keys={'LoadState','ActiveState','SubState','MainPID','ControlGroup','FragmentPath',
          'DropInPaths','User','Group','KillMode','MemoryMax','TasksMax'}
    argv=['/usr/bin/systemctl','show',NAME,'--no-pager','--property='+','.join(sorted(keys))]
    try:
        result=subprocess.run(argv,env=ENV,cwd='/',stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=10)
        if result.returncode or len(result.stdout)>16384:raise ControlError('control_unit_observation_failed')
        values={}
        for line in result.stdout.splitlines():
            key,value=line.split('=',1)
            if key in values:raise ControlError('control_unit_observation_failed')
            values[key]=value
        if set(values)!=keys:raise ControlError('control_unit_observation_failed')
        return values
    except (OSError,ValueError,subprocess.SubprocessError):
        raise ControlError('control_unit_observation_failed') from None


def _usage(root,limit=16000):
    logical=allocated=entries=0
    for path in [root,*root.rglob('*')]:
        entries+=1
        if entries>limit:raise ControlError('control_disk_inventory_bound')
        st=path.lstat()
        if stat.S_ISREG(st.st_mode):logical+=st.st_size
        if not stat.S_ISLNK(st.st_mode):allocated+=st.st_blocks*512
    return logical,allocated


def _available_memory():
    try:return int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                        if line.startswith('MemAvailable:')))*1024
    except (OSError,StopIteration,ValueError):
        raise ControlError('control_capacity_observation_failed') from None


def _capacity():
    try:
        available=_available_memory()
        install_logical,install_allocated=_usage(BASE)
        state_logical,state_allocated=_usage(STATE)
        basefs=os.statvfs(BASE);statefs=os.statvfs(STATE)
    except OSError:raise ControlError('control_capacity_observation_failed') from None
    if available<HOST_MEMORY_FLOOR:raise ControlError('control_runtime_memory_floor')
    if install_allocated>INSTALL_ALLOCATED_CEILING:raise ControlError('control_install_footprint_ceiling')
    if state_allocated>STATE_ALLOCATED_CEILING:raise ControlError('control_state_retention_ceiling')
    base_free=basefs.f_bavail*basefs.f_frsize;state_free=statefs.f_bavail*statefs.f_frsize
    if base_free<max(BASE_FREE_FLOOR,install_allocated*4):raise ControlError('control_install_disk_floor')
    if state_free<STATE_FREE_FLOOR:raise ControlError('control_state_disk_floor')
    if basefs.f_favail<INODE_FREE_FLOOR or statefs.f_favail<INODE_FREE_FLOOR:
        raise ControlError('control_inode_floor')
    return {'accepted':True,'memory_available_bytes':available,'memory_max_bytes':MEMORY_MAX,
        'install_logical_bytes':install_logical,'install_allocated_bytes':install_allocated,
        'state_logical_bytes':state_logical,'state_allocated_bytes':state_allocated,
        'install_free_bytes':base_free,'state_free_bytes':state_free,
        'state_retention_ceiling_bytes':STATE_ALLOCATED_CEILING,'runtime_max_seconds':7200}


def _expected_cmd(receipt):
    release=BASE/'releases'/receipt['source_sha']
    return [str(release/'venv/bin/python').encode(),b'-I',b'-m',b'mcp_rooms.test_candidate',b'serve',
        b'--state',str(PROFILE).encode(),b'--resource',receipt['resource'].encode(),b'']


def _process(values,receipt):
    try:pid=int(values['MainPID'])
    except ValueError:raise ControlError('control_process_mismatch') from None
    if pid<=1:raise ControlError('control_process_mismatch')
    root=Path('/proc')/str(pid)
    try:
        before=root.stat();argv=(root/'cmdline').read_bytes().split(b'\0')
        status=(root/'status').read_text();cgroup=(root/'cgroup').read_text().splitlines();after=root.stat()
    except OSError:raise ControlError('control_process_mismatch') from None
    uid=receipt['identity']['uid']
    if (before.st_ino!=after.st_ino or before.st_uid!=uid or after.st_uid!=uid
            or argv!=_expected_cmd(receipt) or cgroup!=['0::'+values['ControlGroup']]):
        raise ControlError('control_process_mismatch')
    for field in ('CapEff','CapPrm','CapInh','CapAmb'):
        try:value=next(line.split()[1] for line in status.splitlines() if line.startswith(field+':'))
        except StopIteration:raise ControlError('control_process_mismatch') from None
        if int(value,16):raise ControlError('control_process_mismatch')
    group=Path('/sys/fs/cgroup'+values['ControlGroup'])
    if group.resolve()!=group or values['ControlGroup']!='/system.slice/'+NAME:
        raise ControlError('control_process_mismatch')
    try:pids=[int(value) for value in (group/'cgroup.procs').read_text().split()]
    except (OSError,ValueError):raise ControlError('control_process_mismatch') from None
    if pid not in pids:raise ControlError('control_process_mismatch')
    for child in pids:
        try:
            if (Path('/proc')/str(child)).stat().st_uid!=uid:raise ControlError('control_process_mismatch')
        except FileNotFoundError:continue
    return pid


def _validate(i,state):
    i['_host']();tools=i['_trusted']();python_hash=i['_python']();i['_chain'](BASE);i['_chain'](UNIT.parent)
    receipt=_read_json(i['_file'](BASE/'installation.json',16384))
    keys={'format','source_sha','lock_sha256','resource','tools','python_sha256','identity','base_device','base_inode',
          'inventory_sha256','unit_sha256','profile_created','start_authorized','runtime_capacity_accepted'}
    if (type(receipt) is not dict or set(receipt)!=keys or receipt['format']!=FORMAT
            or receipt['profile_created'] is not False or receipt['start_authorized'] is not False
            or receipt['runtime_capacity_accepted'] is not False or receipt['tools']!=tools
            or receipt['python_sha256']!=python_hash or receipt['identity']!=i['_account']()
            or receipt['base_device']!=BASE.stat().st_dev or receipt['base_inode']!=BASE.stat().st_ino
            or not re.fullmatch('[0-9a-f]{40}',str(receipt['source_sha']))):
        raise ControlError('control_installation_mismatch')
    expected=runpy.run_path(str(ROOT/'tools/operator_unit.py'))['render'](receipt['source_sha'],receipt['resource']).encode()
    if (sha256(i['_file'](UNIT)).hexdigest()!=receipt['unit_sha256'] or i['_file'](UNIT)!=expected
            or sha256(i['_file'](BASE/'inventory.json',4*1024**2)).hexdigest()!=receipt['inventory_sha256']
            or sha256(i['_inventory'](BASE/'releases'/receipt['source_sha'])).hexdigest()!=receipt['inventory_sha256']):
        raise ControlError('control_code_changed')
    st=STATE.lstat();identity=receipt['identity']
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid!=identity['uid'] or st.st_gid!=identity['gid']
            or stat.S_IMODE(st.st_mode)!=0o700):raise ControlError('control_state_changed')
    values=_show()
    if (values['LoadState']!='loaded' or values['FragmentPath']!=str(UNIT) or values['DropInPaths']
            or values['User']!=USER or values['Group']!=USER or values['KillMode']!='control-group'
            or values['MemoryMax']!=str(MEMORY_MAX) or values['TasksMax']!='64'):
        raise ControlError('control_unit_mismatch')
    if state=='inactive':
        if (values['ActiveState']!='inactive' or values['MainPID']!='0' or values['ControlGroup']):
            raise ControlError('control_unit_not_inactive')
    elif state=='active':
        if values['ActiveState']!='active':raise ControlError('control_unit_not_active')
        _process(values,receipt)
    else:raise ValueError('control_invalid_state')
    return receipt,values


def _run(argv,timeout=90):
    try:subprocess.run(argv,env=ENV,cwd='/',stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,check=True,timeout=timeout)
    except (OSError,subprocess.SubprocessError):raise ControlError('control_command_failed') from None


def _transient(i,name,argv,receipt,write):
    i['_absent_unit'](name)
    properties=['User='+USER,'Group='+USER,'NoNewPrivileges=yes','CapabilityBoundingSet=',
        'KillMode=control-group','TimeoutStopSec=10s','RuntimeMaxSec=90s','MemoryMax=1G','TasksMax=64',
        'CPUQuota=100%','ProtectSystem=strict','ProtectHome=yes','ProtectControlGroups=yes','PrivateTmp=yes',
        'PrivateDevices=yes','RestrictAddressFamilies=AF_UNIX','IPAddressDeny=any','ReadOnlyPaths='+str(BASE),
        'WorkingDirectory=/']
    if write:properties.append('ReadWritePaths='+str(STATE))
    command=['/usr/bin/systemd-run','--quiet','--wait','--collect','--service-type=exec','--unit='+name]
    command.extend('--property='+value for value in properties)
    command.extend(['--setenv=PATH=/usr/bin:/bin','--setenv=LANG=C.UTF-8','--setenv=PYTHONUTF8=1','--',*argv])
    _run(command)
    deadline=time.monotonic()+3
    while True:
        value=i['_show'](name)
        if value['LoadState']=='not-found' and value['MainPID']=='0' and not value['ControlGroup']:break
        if time.monotonic()>deadline:raise ControlError('control_transient_not_collected')
        time.sleep(.1)


def _candidate_argv(receipt,action):
    release=BASE/'releases'/receipt['source_sha']
    return [str(release/'venv/bin/python'),'-I','-m','mcp_rooms.test_candidate',action,
        '--state',str(PROFILE),'--resource',receipt['resource']]


def _profile(receipt):
    try:st=PROFILE.lstat();photos=(PROFILE/'photos').lstat();marker=(PROFILE/'profile.json').lstat()
    except OSError:raise ControlError('control_profile_missing') from None
    uid=receipt['identity']['uid'];gid=receipt['identity']['gid']
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid!=uid or st.st_gid!=gid or stat.S_IMODE(st.st_mode)!=0o700
            or not stat.S_ISDIR(photos.st_mode) or photos.st_uid!=uid or photos.st_gid!=gid
            or stat.S_IMODE(photos.st_mode)!=0o700 or not stat.S_ISREG(marker.st_mode)
            or marker.st_uid!=uid or marker.st_gid!=gid or marker.st_nlink!=1 or stat.S_IMODE(marker.st_mode)!=0o600):
        raise ControlError('control_profile_mismatch')


def capacity():
    i=_installer()
    with _lock(i):
        _validate(i,'inactive')
        return _capacity()


def bootstrap(authorization):
    if authorization!=BOOTSTRAP_AUTH:raise ControlError('control_bootstrap_authorization_required')
    i=_installer()
    with _lock(i):
        receipt,_=_validate(i,'inactive');measurement=_capacity()
        if os.path.lexists(PROFILE):raise ControlError('control_existing_profile')
        _validate(i,'inactive')
        _transient(i,BOOTSTRAP,_candidate_argv(receipt,'bootstrap'),receipt,True)
        _profile(receipt)
        _transient(i,CHECK,_candidate_argv(receipt,'check'),receipt,True)
        return {'profile_created':True,'key_read_or_returned':False,'runtime_capacity_accepted':measurement['accepted']}


def _ready(receipt,timeout=25):
    deadline=time.monotonic()+timeout
    try:host=urlsplit(receipt['resource']).netloc.encode('ascii')
    except (KeyError,UnicodeError,ValueError):raise ControlError('control_installation_mismatch') from None
    if not host or b'\r' in host or b'\n' in host:raise ControlError('control_installation_mismatch')
    request=(b'POST /mcp HTTP/1.1\r\nHost: '+host+
        b'\r\nContent-Type: application/json\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}')
    while time.monotonic()<deadline:
        try:
            with socket.create_connection(('127.0.0.1',8766),timeout=1) as stream:
                stream.sendall(request);line=stream.makefile('rb',buffering=0).readline(256)
                if line.startswith(b'HTTP/1.1 401 '):return
        except OSError:pass
        time.sleep(.1)
    raise ControlError('control_start_timeout')


def _stop_owned(i,receipt):
    _validate(i,'active')
    _run(['/usr/bin/systemctl','stop',NAME],25)
    _,values=_validate(i,'inactive')
    group=Path('/sys/fs/cgroup/system.slice')/NAME
    if group.exists() and (group/'cgroup.procs').read_text().strip():raise ControlError('control_stop_incomplete')
    return values


def _cleanup_failed_start(i,receipt):
    """Stop only the exact reviewed unit/cgroup; never search or kill by port/name."""
    values=_show()
    if (values['FragmentPath']!=str(UNIT) or values['DropInPaths']
            or values['User']!=USER or values['Group']!=USER
            or values['KillMode']!='control-group'):
        raise ControlError('control_start_recovery_required')
    try:pid=int(values['MainPID'])
    except ValueError:raise ControlError('control_start_recovery_required') from None
    if pid>1:_process(values,receipt)
    elif values['ControlGroup']:
        group=Path('/sys/fs/cgroup'+values['ControlGroup'])
        if group.resolve()!=group or values['ControlGroup']!='/system.slice/'+NAME:
            raise ControlError('control_start_recovery_required')
        try:pids=[int(value) for value in (group/'cgroup.procs').read_text().split()]
        except (OSError,ValueError):raise ControlError('control_start_recovery_required') from None
        uid=receipt['identity']['uid']
        for child in pids:
            try:
                if (Path('/proc')/str(child)).stat().st_uid!=uid:
                    raise ControlError('control_start_recovery_required')
            except FileNotFoundError:continue
    _run(['/usr/bin/systemctl','stop',NAME],25)
    _,after=_validate(i,'inactive')
    return after


def start(authorization):
    if authorization!=START_AUTH:raise ControlError('control_start_authorization_required')
    i=_installer()
    with _lock(i):
        receipt,_=_validate(i,'inactive');measurement=_capacity();_profile(receipt)
        _transient(i,CHECK,_candidate_argv(receipt,'check'),receipt,True)
        _validate(i,'inactive')
        try:
            _run(['/usr/bin/systemctl','start',NAME],35)
            _validate(i,'active');_ready(receipt);_validate(i,'active')
        except Exception as original:
            try:
                _cleanup_failed_start(i,receipt)
            except Exception:raise ControlError('control_start_recovery_required') from original
            raise
        return {'started':True,'runtime_capacity_accepted':measurement['accepted'],'source_sha':receipt['source_sha']}


def stop():
    i=_installer()
    with _lock(i):
        receipt,values=_validate(i,'active')
        _stop_owned(i,receipt)
        return {'stopped':True,'state_preserved':True,'profile_preserved':True,
            'source_sha':receipt['source_sha'],'pid':int(values['MainPID'])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['capacity','bootstrap','start','stop'])
    parser.add_argument('--authorization');args=parser.parse_args();os.umask(0o077)
    try:
        if args.action=='capacity':result=capacity()
        elif args.action=='bootstrap':result=bootstrap(args.authorization)
        elif args.action=='start':result=start(args.authorization)
        else:result=stop()
        print(json.dumps({'ok':True,**result},sort_keys=True));return 0
    except ControlError as exc:print(json.dumps({'ok':False,'error':str(exc)}));return 1
    except Exception:print(json.dumps({'ok':False,'error':'control_review_required'}));return 1


if __name__=='__main__':raise SystemExit(main())
