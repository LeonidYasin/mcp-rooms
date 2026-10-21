"""Reviewed fresh-only offline installation, NOT a deployment/start controller.

Root-owned trusted tools + reviewed wheelhouse only. No bootstrap, key access,
start/enable/Caddy/upgrade/delete/restore. Failed installations remain blocked.
Every real VPS invocation requires separate owner approval and special password.
"""
from contextlib import contextmanager
from hashlib import sha256
import argparse
import fcntl
import grp
import json
import os
from pathlib import Path
import platform
import pwd
import re
import runpy
import stat
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
ROOT_UID=0
USER='mcp-rooms-candidate'
NAME=USER+'.service'
BUILD=USER+'-build.service'
BASE=Path('/opt')/USER
STATE=Path('/var/lib')/USER
UNIT=Path('/etc/systemd/system')/NAME
LOCK=Path('/run/mcp-rooms-operator')
PYTHON=Path('/usr/bin/python3.12')
FORMAT='mcp-rooms/fresh-install/v1'
TOOLS=('tools/operator_install.py','tools/operator_bundle.py','tools/operator_plan.py',
       'tools/operator_unit.py','operator/runtime-linux-x86_64-py312.lock')
ENV={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONUTF8':'1','PIP_CONFIG_FILE':'/dev/null'}


class InstallError(Exception):pass


def _host():
    if (os.geteuid()!=0 or os.getuid()!=0 or sys.version_info[:2]!=(3,12)
            or platform.system()!='Linux' or platform.machine()!='x86_64'
            or not Path('/sys/fs/cgroup/cgroup.controllers').is_file()):
        raise InstallError('install_host_refused')


def _chain(path):
    path=Path(path)
    if not path.is_absolute() or path.resolve()!=path:raise InstallError('install_aliased_path')
    for p in reversed((path,*path.parents)):
        st=p.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid!=ROOT_UID or st.st_mode&0o022:
            raise InstallError('install_untrusted_ancestor')


def _file(path,maximum=48*1024**2,*,allow_empty=False):
    path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=ROOT_UID or st.st_mode&0o022 or st.st_nlink!=1 or not (0 if allow_empty else 1)<=st.st_size<=maximum:
            raise InstallError('install_unsafe_file')
        data=bytearray()
        while len(data)<=maximum:
            b=os.read(fd,min(65536,maximum+1-len(data)))
            if not b:break
            data.extend(b)
        after,named=os.fstat(fd),path.lstat()
        fields=('st_dev','st_ino','st_mode','st_uid','st_gid','st_nlink','st_size','st_ctime_ns','st_mtime_ns')
        if len(data)!=st.st_size or any(getattr(st,k)!=getattr(after,k) or getattr(after,k)!=getattr(named,k) for k in fields):
            raise InstallError('install_changed_file')
        return bytes(data)
    finally:os.close(fd)


def _trusted():
    _chain(ROOT)
    for name in ('tools','operator'):_chain(ROOT/name)
    return {p:sha256(_file(ROOT/p)).hexdigest() for p in TOOLS}


def _python():
    _chain(PYTHON.parent)
    if PYTHON.resolve()!=PYTHON:raise InstallError('install_python_alias')
    # Trust the OS-owned runtime, not a service-writable interpreter or toolcache.
    _chain(Path('/usr/lib/python3.12'))
    return sha256(_file(PYTHON)).hexdigest()


def _run(argv,timeout=150):
    try:
        subprocess.run(argv,env=ENV,cwd='/',stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=timeout)
    except (OSError,subprocess.SubprocessError):raise InstallError('install_command_failed') from None


def _show(name):
    args=['/usr/bin/systemctl','show',name,'--no-pager',
        '--property=LoadState,ActiveState,MainPID,ControlGroup,FragmentPath,DropInPaths']
    try:
        c=subprocess.run(args,env=ENV,cwd='/',stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,text=True,timeout=10)
        if len(c.stdout)>16384:raise InstallError('install_unit_observation_failed')
        values={}
        for line in c.stdout.splitlines():
            k,v=line.split('=',1)
            if k in values:raise InstallError('install_unit_observation_failed')
            values[k]=v
        keys={'LoadState','ActiveState','MainPID','ControlGroup','FragmentPath','DropInPaths'}
        if set(values)!=keys or (c.returncode and not(c.returncode==1 and values['LoadState']=='not-found')):
            raise InstallError('install_unit_observation_failed')
        return values
    except (OSError,ValueError,subprocess.SubprocessError):raise InstallError('install_unit_observation_failed') from None


def _absent_unit(name):
    p=_show(name)
    if p['LoadState']!='not-found' or p['MainPID']!='0' or p['ControlGroup'] or p['FragmentPath'] or p['DropInPaths']:
        raise InstallError('install_existing_unit')
    for root in ('/etc/systemd/system','/run/systemd/system','/usr/lib/systemd/system','/lib/systemd/system'):
        for suffix in ('','.d'):
            p=Path(root)/(name+suffix)
            if p.exists() or p.is_symlink():raise InstallError('install_existing_unit')


def _absent_account():
    for getter in (pwd.getpwnam,grp.getgrnam):
        try:getter(USER)
        except KeyError:continue
        raise InstallError('install_existing_identity')


def _account():
    try:u=pwd.getpwnam(USER);g=grp.getgrnam(USER)
    except KeyError:raise InstallError('install_identity_changed') from None
    if (u.pw_uid<=0 or u.pw_gid!=g.gr_gid or g.gr_gid<=0 or u.pw_dir!=str(STATE)
            or u.pw_shell!='/usr/sbin/nologin' or set(os.getgrouplist(USER,g.gr_gid))!={g.gr_gid} or g.gr_mem):
        raise InstallError('install_identity_changed')
    return {'uid':u.pw_uid,'gid':g.gr_gid}


def _capacity():
    # Conservative BUILD floor only, not runtime-service capacity acceptance.
    lines=Path('/proc/meminfo').read_text().splitlines()
    available=int(next(v.split()[1] for v in lines if v.startswith('MemAvailable:')))*1024
    if available<768*1024**2:raise InstallError('install_build_memory_floor')
    for parent,floor in ((BASE.parent,2*1024**3),(STATE.parent,512*1024**2)):
        s=os.statvfs(parent)
        if s.f_bavail*s.f_frsize<floor:raise InstallError('install_disk_floor')


@contextmanager
def _lock():
    _chain(LOCK.parent)
    try:LOCK.mkdir(mode=0o700)
    except FileExistsError:pass
    _chain(LOCK)
    if stat.S_IMODE(LOCK.stat().st_mode)!=0o700:raise InstallError('install_lock_refused')
    fd=os.open(LOCK/'install.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,0o600)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=ROOT_UID or st.st_nlink!=1 or stat.S_IMODE(st.st_mode)!=0o600 or st.st_size:
            raise InstallError('install_lock_refused')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise InstallError('install_busy') from None
        yield
    finally:os.close(fd)


def _directory(path,mode):
    path.mkdir(mode=mode)  # Exclusive creation, never adopt an existing path.
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:os.fchmod(fd,mode)
    finally:os.close(fd)


def _new(path,data,mode=0o600):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,mode)
    # On error preserve the partial new file as a blocked target, never unlink it.
    with os.fdopen(fd,'wb') as f:
        os.fchmod(f.fileno(),mode)  # Explicit mode; CLI deliberately sets umask 077.
        f.write(data);f.flush();os.fsync(f.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def _dump(value):return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def _seal(root):
    # Build cgroup is empty first: ownership changes do NOT revoke open write FDs.
    for p in [root,*root.rglob('*')]:
        st=p.lstat()
        if stat.S_ISLNK(st.st_mode):
            if not p.resolve().is_relative_to(root):raise InstallError('install_code_link_escape')
            os.lchown(p,ROOT_UID,0);continue
        if not(stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode)) or (p.is_file() and st.st_nlink!=1):
            raise InstallError('install_unsafe_code_entry')
        os.chown(p,ROOT_UID,0);p.chmod(0o755 if p.is_dir() or st.st_mode&0o111 else 0o644)


def _inventory(root):
    rows=[];total=0
    for p in sorted([root,*root.rglob('*')]):
        if len(rows)>=12000:raise InstallError('install_inventory_bound')
        rel=str(p.relative_to(root));st=p.lstat()
        if len(rel)>1024 or any(ord(c)<32 for c in rel) or st.st_uid!=ROOT_UID:
            raise InstallError('install_unsafe_code_entry')
        row={'path':rel,'device':st.st_dev,'inode':st.st_ino,'mode':stat.S_IMODE(st.st_mode)}
        if stat.S_ISLNK(st.st_mode):
            if not p.resolve().is_relative_to(root):raise InstallError('install_code_link_escape')
            row.update(kind='link',target=os.readlink(p))
        elif stat.S_ISDIR(st.st_mode):
            if st.st_mode&0o022:raise InstallError('install_unsafe_code_entry')
            row['kind']='directory'
        elif stat.S_ISREG(st.st_mode):
            data=_file(p,allow_empty=True);total+=len(data)
            if total>384*1024**2:raise InstallError('install_inventory_bound')
            row.update(kind='file',size=len(data),sha256=sha256(data).hexdigest())
        else:raise InstallError('install_unsafe_code_entry')
        rows.append(row)
    data=_dump(rows)
    if len(data)>4*1024**2:raise InstallError('install_inventory_bound')
    return data


def _build(argv,venv,identity):
    _capacity();_absent_unit(BUILD)
    if _account()!=identity:raise InstallError('install_identity_changed')
    _run(['/usr/bin/systemd-run','--quiet','--wait','--collect','--service-type=exec',
        '--unit='+BUILD,'--property=User='+USER,'--property=Group='+USER,
        '--property=NoNewPrivileges=yes','--property=CapabilityBoundingSet=',
        '--property=KillMode=control-group','--property=TimeoutStopSec=5s',
        '--property=RuntimeMaxSec=120s','--property=MemoryMax=512M','--property=TasksMax=32',
        '--property=CPUQuota=100%','--property=ProtectSystem=strict','--property=ProtectHome=yes',
        '--property=ProtectControlGroups=yes','--property=PrivateTmp=yes',
        '--property=RestrictAddressFamilies=AF_UNIX','--property=IPAddressDeny=any',
        '--property=ReadWritePaths='+str(venv),'--property=WorkingDirectory=/',
        '--setenv=PATH=/usr/bin:/bin','--setenv=LANG=C.UTF-8','--setenv=PYTHONUTF8=1',
        '--setenv=PIP_CONFIG_FILE=/dev/null','--',*argv])
    # A surviving unprivileged installer could retain write FDs through chown.
    # Only seal/hash after the entire transient build cgroup has gone away.
    deadline=time.monotonic()+3
    while True:
        p=_show(BUILD)
        if p['LoadState']=='not-found' and p['MainPID']=='0' and not p['ControlGroup']:break
        if time.monotonic()>deadline:raise InstallError('install_build_not_collected')
        time.sleep(.1)


def _inputs(bundle,source,lock_hash,resource):
    if not isinstance(source,str) or not re.fullmatch('[0-9a-f]{40}',source):raise InstallError('install_source_required')
    if not isinstance(lock_hash,str) or not re.fullmatch('[0-9a-f]{64}',lock_hash):raise InstallError('install_lock_required')
    _host();tools=_trusted();python_hash=_python();bundle=Path(bundle)
    _chain(bundle)
    actual=sha256(_file(ROOT/'operator/runtime-linux-x86_64-py312.lock')).hexdigest()
    if actual!=lock_hash:raise InstallError('install_lock_mismatch')
    verified=runpy.run_path(str(ROOT/'tools/operator_bundle.py'))['verify'](bundle,source,lock_hash)
    rendered=runpy.run_path(str(ROOT/'tools/operator_unit.py'))['render'](source,resource)
    return tools,python_hash,verified,rendered.encode()


def install(bundle,source,lock_hash,resource):
    tools,python_hash,verified,unit=_inputs(bundle,source,lock_hash,resource)
    with _lock():
        for p in (BASE.parent,STATE.parent,UNIT.parent):_chain(p)
        _capacity();_absent_account();_absent_unit(NAME);_absent_unit(BUILD)
        for p in (BASE,STATE):
            if p.exists() or p.is_symlink():raise InstallError('install_existing_target')
        # No destructive compensation. Any partial identity/path blocks a retry.
        _run(['/usr/sbin/useradd','--system','--user-group','--no-create-home','--home-dir',str(STATE),'--shell','/usr/sbin/nologin',USER])
        identity=_account()
        _absent_unit(NAME);_capacity()
        _directory(BASE,0o755);_directory(BASE/'releases',0o755)
        release=BASE/'releases'/source;_directory(release,0o755)
        STATE.mkdir(mode=0o700);os.chown(STATE,identity['uid'],identity['gid'])
        venv=release/'venv';venv.mkdir(mode=0o700);os.chown(venv,identity['uid'],identity['gid'])
        wheels=BASE/'wheelhouse';_directory(wheels,0o755);_directory(wheels/'wheels',0o755)
        # Copy only already verified bounded wheel/lock bytes, no archive extraction.
        import shutil
        for original in sorted((Path(bundle)/'wheels').iterdir()):
            _new(wheels/'wheels'/original.name,_file(original),0o644)
        _new(wheels/'install.lock',_file(Path(bundle)/'install.lock'),0o644)
        _build([str(PYTHON),'-I','-m','venv','--copies',str(venv)],venv,identity)
        python=venv/'bin/python'
        _build([str(python),'-I','-m','pip','--isolated','install','--disable-pip-version-check',
            '--no-index','--no-deps','--only-binary=:all:','--find-links',str(wheels/'wheels'),
            '--require-hashes','-r',str(wheels/'install.lock')],venv,identity)
        _build([str(python),'-I','-m','pip','check'],venv,identity)
        _seal(release);inventory=_inventory(release)
        if tools!=_trusted() or python_hash!=_python() or identity!=_account():raise InstallError('install_trust_changed')
        runpy.run_path(str(ROOT/'tools/operator_bundle.py'))['verify'](Path(bundle),source,lock_hash)
        _absent_unit(NAME);_capacity();_chain(UNIT.parent)
        _new(UNIT,unit,0o644)
        _run(['/usr/bin/systemd-analyze','verify',str(UNIT)])
        _run(['/usr/bin/systemctl','daemon-reload'])
        p=_show(NAME)
        if p['FragmentPath']!=str(UNIT) or p['DropInPaths'] or p['MainPID']!='0' or p['ActiveState']!='inactive':
            raise InstallError('install_loaded_unit_changed')
        _new(BASE/'inventory.json',inventory)
        receipt={'format':FORMAT,'source_sha':source,'lock_sha256':lock_hash,'resource':resource,
            'tools':tools,'python_sha256':python_hash,'identity':identity,
            'base_device':BASE.stat().st_dev,'base_inode':BASE.stat().st_ino,
            'inventory_sha256':sha256(inventory).hexdigest(),'unit_sha256':sha256(unit).hexdigest(),
            'profile_created':False,'start_authorized':False,'runtime_capacity_accepted':False}
        _new(BASE/'installation.json',_dump(receipt)) # ready-last, no bootstrap/start
        return {'installed':True,'profile_created':False,'started':False,'start_authorized':False,'source_sha':source}


def _pairs(items):
    value={}
    for k,v in items:
        if k in value:raise InstallError('install_invalid_receipt')
        value[k]=v
    return value


def inspect():
    _host();tools=_trusted();python_hash=_python()
    with _lock():
        _chain(BASE);_chain(UNIT.parent)
        try:receipt=json.loads(_file(BASE/'installation.json',16384),object_pairs_hook=_pairs)
        except (ValueError,UnicodeError,RecursionError):raise InstallError('install_invalid_receipt') from None
        keys={'format','source_sha','lock_sha256','resource','tools','python_sha256','identity','base_device','base_inode',
              'inventory_sha256','unit_sha256','profile_created','start_authorized','runtime_capacity_accepted'}
        if (type(receipt) is not dict or set(receipt)!=keys or receipt['format']!=FORMAT
                or receipt['profile_created'] is not False or receipt['start_authorized'] is not False
                or receipt['runtime_capacity_accepted'] is not False or receipt['tools']!=tools
                or receipt['python_sha256']!=python_hash or receipt['identity']!=_account()
                or receipt['base_device']!=BASE.stat().st_dev or receipt['base_inode']!=BASE.stat().st_ino
                or not re.fullmatch('[0-9a-f]{40}',str(receipt['source_sha']))):
            raise InstallError('install_receipt_mismatch')
        expected=runpy.run_path(str(ROOT/'tools/operator_unit.py'))['render'](receipt['source_sha'],receipt['resource']).encode()
        if (sha256(_file(UNIT)).hexdigest()!=receipt['unit_sha256'] or _file(UNIT)!=expected
                or sha256(_file(BASE/'inventory.json',4*1024**2)).hexdigest()!=receipt['inventory_sha256']
                or sha256(_inventory(BASE/'releases'/receipt['source_sha'])).hexdigest()!=receipt['inventory_sha256']):
            raise InstallError('install_code_changed')
        p=_show(NAME)
        if p['FragmentPath']!=str(UNIT) or p['DropInPaths'] or p['MainPID']!='0' or p['ActiveState']!='inactive':
            raise InstallError('install_unit_not_inactive')
        st=STATE.lstat();identity=receipt['identity']
        if not stat.S_ISDIR(st.st_mode) or st.st_uid!=identity['uid'] or st.st_gid!=identity['gid'] or stat.S_IMODE(st.st_mode)!=0o700:
            raise InstallError('install_state_changed')
        return {'checked':True,'start_authorized':False,'runtime_capacity_accepted':False,'source_sha':receipt['source_sha']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['install','inspect'])
    for name in ('bundle','source-sha','lock-sha256','resource'):parser.add_argument('--'+name)
    a=parser.parse_args();os.umask(0o077)
    try:
        if a.action=='install':
            if not all((a.bundle,a.source_sha,a.lock_sha256,a.resource)):raise InstallError('install_arguments_required')
            result=install(Path(a.bundle),a.source_sha,a.lock_sha256,a.resource)
        else:result=inspect()
        print(json.dumps({'ok':True,**result}));return 0
    except InstallError as exc:print(json.dumps({'ok':False,'error':str(exc)}));return 1
    except Exception:print(json.dumps({'ok':False,'error':'install_review_required'}));return 1


if __name__=='__main__':raise SystemExit(main())
