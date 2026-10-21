"""Linux x86_64 Landlock ABI>=3 + seccomp child policy, before any image decode.

No shell, namespaces helper, sudo or operator/client-selected allowlist. The policy
is defense-in-depth, not a VM or a general native-code containment certification.
Never apply this module's restrictions inside the parent service process.
"""
import ctypes as c
from dataclasses import dataclass
import errno
import os
from pathlib import Path
import platform
import stat
import sys
import sysconfig
from .domain import DomainError

POLICY = 'landlock3-seccomp-x86_64/v1'
# Stable Linux x86_64 syscall ABI. Reject other architectures/x32 rather than guess.
SYS_CREATE, SYS_ADD, SYS_RESTRICT = 444, 445, 446
HANDLED_FS = (1 << 15) - 1  # ABI3: execute..refer + truncate (bits0..14).
READ_FILE, READ_DIR = 1 << 2, 1 << 3
PR_SET_NO_NEW_PRIVS, PR_SET_SECCOMP = 38, 22
AUDIT_ARCH_X86_64 = 0xC000003E
# Network, io_uring bypass, exec/process creation/interference, namespace/mount,
# handle-based filesystem access, kernel BPF and userfaultfd. This is a denylist,
# NOT a claim that all remaining kernel attack surface is eliminated.
FUTURE_SYSCALL_FLOOR = 450  # Deny new syscalls until individually reviewed.
DENIED_SYSCALLS = frozenset({
    16,72,73,90,91,92,93,94,132,188,189,190,197,198,199,235,260,261,268,280,
    # ABI3 does not mediate chmod/chown/xattr/utime/ioctl/fcntl/flock; seccomp must.
    41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,  # all classic socket operations
    56,57,58,59,62,101,129,141,142,144,155,161,165,166,200,203,234,297,302,314,448,     # process, ptrace, mount, signal
    105,106,113,114,116,117,119,122,123,126,169,175,176,246,
    272,288,299,303,304,307,308,310,311,312,313,320,            # namespaces, socket variants, handles, process_vm
    321,322,323,424,425,426,427,434,435,438,440,    # bpf, execat, uffd, io_uring, pidfd, clone3
})


@dataclass(frozen=True)
class NativeSandbox:
    """Trusted state path only, never a request field or a mutable read allowlist."""
    protected_root: Path
    def __post_init__(self):
        value=Path(self.protected_root)
        if not value.is_absolute() or value.resolve()!=value:
            raise DomainError('media_sandbox_policy_invalid')
        info=value.stat(follow_symlinks=False)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid()
                or stat.S_IMODE(info.st_mode)!=0o700):
            raise DomainError('media_sandbox_policy_invalid')
        object.__setattr__(self,'protected_root',value)


def _runtime_roots(protected):
    # Installed Python stdlib/site packages (including Pillow.libs), and fixed
    # system library directories only. No /home, /tmp, /run, /proc, /etc tree or /.
    paths=sysconfig.get_paths()
    values={paths[k] for k in ('stdlib','platstdlib','purelib','platlib')}
    values.update(('/lib/x86_64-linux-gnu','/usr/lib/x86_64-linux-gnu','/lib64','/usr/lib64'))
    values.add('/etc/ld.so.cache')
    roots=[]
    for value in sorted(values):
        path=Path(value)
        if not path.exists():continue
        path=path.resolve(strict=True)
        if (path==Path('/') or path==protected or path.is_relative_to(protected)
                or protected.is_relative_to(path)):
            raise DomainError('media_sandbox_policy_invalid')
        if path not in roots:roots.append(path)
    if not roots:raise DomainError('media_sandbox_policy_invalid')
    return tuple(roots)


class _Ruleset(c.Structure):
    _fields_=[('handled_access_fs',c.c_uint64)]


class _PathRule(c.Structure):
    _pack_=1
    _fields_=[('allowed_access',c.c_uint64),('parent_fd',c.c_int32)]


class _Filter(c.Structure):
    _fields_=[('code',c.c_uint16),('jt',c.c_ubyte),('jf',c.c_ubyte),('k',c.c_uint32)]


class _Program(c.Structure):
    _fields_=[('len',c.c_ushort),('filter',c.POINTER(_Filter))]


def _filter_rows():
    kill,deny,allow=0x80000000,0x00050000|errno.EPERM,0x7fff0000
    # BPF load arch, branch if x86_64, kill foreign ABI; load syscall, kill x32.
    rows=[(0x20,0,0,4),(0x15,1,0,AUDIT_ARCH_X86_64),(0x06,0,0,kill),
          (0x20,0,0,0),(0x35,0,1,0x40000000),(0x06,0,0,kill),
          (0x35,0,1,FUTURE_SYSCALL_FLOOR),(0x06,0,0,deny)]
    for number in sorted(DENIED_SYSCALLS):
        rows.extend(((0x15,0,1,number),(0x06,0,0,deny)))
    rows.append((0x06,0,0,allow))
    return rows


def enforce(policy):
    """Irreversible restriction of THIS child. Return only after both policies work."""
    if (not isinstance(policy,NativeSandbox) or sys.platform!='linux'
            or platform.machine()!='x86_64' or sys.maxsize<=2**32):
        raise DomainError('media_sandbox_unavailable')
    # No privileged decoder: no saved-root identity or inherited/ambient caps.
    uid=os.getuid()
    if uid==0 or os.getresuid()!=(uid,uid,uid):
        raise DomainError('media_sandbox_unavailable')
    try:
        caps={line.split(':',1)[0]:line.split(':',1)[1].strip()
              for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('Cap')}
        if any(int(caps[k],16)!=0 for k in ('CapEff','CapPrm','CapInh','CapAmb')):
            raise DomainError('media_sandbox_unavailable')
    except (OSError,ValueError,KeyError):
        raise DomainError('media_sandbox_unavailable') from None
    roots=_runtime_roots(policy.protected_root)
    libc=c.CDLL(None,use_errno=True)
    libc.syscall.restype=c.c_long
    abi=libc.syscall(c.c_long(SYS_CREATE),c.c_void_p(),c.c_size_t(0),c.c_uint(1))
    if abi<3:raise DomainError('media_sandbox_unavailable')
    ruleset=libc.syscall(c.c_long(SYS_CREATE),c.byref(_Ruleset(HANDLED_FS)),c.c_size_t(c.sizeof(_Ruleset)),c.c_uint(0))
    if ruleset<0:raise DomainError('media_sandbox_unavailable')
    try:
        for path in roots:
            fd=os.open(path,os.O_PATH|os.O_CLOEXEC)
            try:
                info=os.fstat(fd)
                if stat.S_ISDIR(info.st_mode):rights=READ_FILE|READ_DIR
                elif stat.S_ISREG(info.st_mode):rights=READ_FILE
                else:raise DomainError('media_sandbox_policy_invalid')
                rule=_PathRule(rights,fd)
                if libc.syscall(c.c_long(SYS_ADD),c.c_int(ruleset),c.c_int(1),c.byref(rule),c.c_uint(0))!=0:
                    raise DomainError('media_sandbox_unavailable')
            finally:os.close(fd)
        if libc.prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0)!=0:
            raise DomainError('media_sandbox_unavailable')
        if libc.syscall(c.c_long(SYS_RESTRICT),c.c_int(ruleset),c.c_uint(0))!=0:
            raise DomainError('media_sandbox_unavailable')
    finally:os.close(ruleset)
    rows=_filter_rows();filters=(_Filter*len(rows))(*(_Filter(*row) for row in rows))
    program=_Program(len(rows),filters)
    if libc.prctl(PR_SET_SECCOMP,2,c.byref(program),0,0)!=0:
        raise DomainError('media_sandbox_unavailable')
    # PR_GET_NO_NEW_PRIVS / PR_GET_SECCOMP: filter must be present, no soft mode.
    if libc.prctl(39,0,0,0,0)!=1 or libc.prctl(21,0,0,0,0)!=2:
        raise DomainError('media_sandbox_unavailable')
    return int(abi)


def probe(policy,abi):
    """Fixed startup health probes; never returns private bytes or caller test code."""
    import socket
    def denied(path,optional=False):
        try:
            fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC)
        except OSError as exc:
            return exc.errno in (errno.EACCES,errno.EPERM) or (optional and exc.errno==errno.ENOENT)
        else:os.close(fd);return False
    result={'v':1,'policy':POLICY,'abi':abi,
            'state_denied':denied(policy.protected_root),
            'db_denied':denied(policy.protected_root/'market.sqlite3'),
            'key_denied_or_absent':denied(policy.protected_root/'owner.key',True),
            'marker_denied':denied(policy.protected_root/'profile.json')}
    for name,family in [('inet',socket.AF_INET),('inet6',socket.AF_INET6),('unix',socket.AF_UNIX)]:
        try:sock=socket.socket(family,socket.SOCK_STREAM)
        except OSError as exc:result[name+'_denied']=exc.errno==errno.EPERM
        else:sock.close();result[name+'_denied']=False
    if not all(value is True for name,value in result.items() if name not in {'v','policy','abi'}):
        raise DomainError('media_sandbox_probe_failed')
    return result
