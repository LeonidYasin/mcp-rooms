"""Internal Linux subprocess supervisor, not a complete security sandbox.

No decoder import, credentials, paths, URLs or caller-selected commands. Transport,
principal checks, fleet admission and filesystem/network isolation are separate.
"""
from hashlib import sha256
import json
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
from .domain import DomainError
from .media_contract import MAX_INPUT_BYTES, MAX_OUTPUT_BYTES, OUTPUT_SIDE, NormalizedPhoto

WALL_SECONDS = 8
MAX_WIRE_BYTES = MAX_OUTPUT_BYTES + 2048
ERRORS = frozenset(('media_invalid_bytes', 'media_input_too_large',
                    'media_type_not_allowed', 'media_type_mismatch',
                    'media_dimensions_exceeded', 'media_animation_not_allowed',
                    'media_output_too_large', 'media_invalid_image',
                    'media_sandbox_unavailable','media_sandbox_policy_invalid','media_sandbox_probe_failed'))


def _launch():
    return subprocess.Popen(
        [sys.executable, '-I', '-B', '-m', 'mcp_rooms.media_worker_child'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        env={'LANG': 'C.UTF-8'}, cwd='/', close_fds=True, start_new_session=True)


def _launch_sandbox(policy, *, check=False):
    from .media_sandbox import NativeSandbox
    if not isinstance(policy,NativeSandbox):raise DomainError('media_sandbox_policy_invalid')
    return subprocess.Popen(
        [sys.executable,'-I','-B','-m','mcp_rooms.media_worker_child',
         '--sandbox-check' if check else '--sandbox',str(policy.protected_root)],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        env={'LANG':'C.UTF-8'},cwd='/',close_fds=True,start_new_session=True)


def _terminate(process):
    # Group cleanup also on successful exit: no surviving descendants expected.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=2)


def _exchange(process, request):
    deadline = time.monotonic() + WALL_SECONDS
    output = bytearray()
    offset = 0
    with selectors.DefaultSelector() as selector:
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE)
        selector.register(process.stdout, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DomainError('media_worker_timeout')
            for key, _ in selector.select(min(remaining, .1)):
                if key.fileobj is process.stdin:
                    try:
                        offset += os.write(process.stdin.fileno(), request[offset:offset + 65536])
                    except BrokenPipeError:
                        selector.unregister(process.stdin)
                        process.stdin.close()
                        continue
                    if offset == len(request):
                        selector.unregister(process.stdin)
                        process.stdin.close()
                else:
                    block = os.read(process.stdout.fileno(), 65536)
                    if not block:
                        selector.unregister(process.stdout)
                    elif len(output) + len(block) > MAX_WIRE_BYTES:
                        raise DomainError('media_worker_output_limit')
                    else:
                        output.extend(block)
        try:
            status = process.wait(timeout=max(.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise DomainError('media_worker_timeout') from None
        if status != 0 or offset != len(request):
            raise DomainError('media_worker_failed')
    return bytes(output)


def _parse(wire, mime):
    try:
        line, data = wire.split(b'\n', 1)
        if len(line) > 2047:
            raise ValueError
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError
                result[key] = value
            return result
        header = json.loads(line, object_pairs_hook=pairs)
        if type(header) is not dict or type(header.get('v')) is not int or header['v'] != 1:
            raise ValueError
        if set(header) == {'v', 'error'} and not data and header['error'] in ERRORS:
            raise DomainError(header['error'])
        if set(header) != {'v', 'size', 'sha256', 'width', 'height', 'source_format', 'content_type'}:
            raise ValueError
        if (type(header['size']) is not int or header['size'] != len(data)
                or not 0 < len(data) <= MAX_OUTPUT_BYTES
                or not data.startswith(b'\xff\xd8\xff') or not data.endswith(b'\xff\xd9')
                or header['sha256'] != sha256(data).hexdigest()
                or header['content_type'] != 'image/jpeg'
                or header['source_format'] != {'image/png': 'PNG', 'image/jpeg': 'JPEG'}[mime]):
            raise ValueError
        if any(type(header[k]) is not int or not 1 <= header[k] <= OUTPUT_SIDE
               for k in ('width', 'height')):
            raise ValueError
        return NormalizedPhoto(data, header['sha256'], header['width'], header['height'],
                               header['source_format'])
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise DomainError('media_worker_protocol') from None


class PhotoWorker:
    """One or two immediate slots (default two); no queue or fleet claim.

    Reuse one instance per app process. Do not expose creation/limits over an API.
    Results are internal bytes, not a persisted or publishable media manifest.
    """
    def __init__(self, *, max_parallel=2, sandbox=None):
        if type(max_parallel) is not int or max_parallel not in (1,2):
            raise DomainError('invalid_worker_parallelism')
        from .media_sandbox import NativeSandbox
        if sandbox is not None and not isinstance(sandbox,NativeSandbox):
            raise DomainError('media_sandbox_policy_invalid')
        self.sandbox=sandbox
        self.max_parallel = max_parallel
        self._slots = threading.BoundedSemaphore(max_parallel)

    def check_sandbox(self):
        from .media_sandbox import POLICY
        if self.sandbox is None:raise DomainError('media_sandbox_policy_invalid')
        if not self._slots.acquire(blocking=False):raise DomainError('media_worker_busy')
        process=None
        try:
            process=_launch_sandbox(self.sandbox,check=True)
            wire=_exchange(process,b'')
            if len(wire)>2048:raise DomainError('media_worker_protocol')
            def unique(items):
                value={}
                for key,item in items:
                    if key in value:raise ValueError
                    value[key]=item
                return value
            try:result=json.loads(wire,object_pairs_hook=unique)
            except (ValueError,UnicodeError,RecursionError):raise DomainError('media_worker_protocol') from None
            fields={'v','policy','abi','state_denied','db_denied','key_denied_or_absent',
                    'marker_denied','inet_denied','inet6_denied','unix_denied'}
            if (type(result) is dict and set(result)=={'v','error'} and type(result.get('v')) is int
                    and result['v']==1 and type(result.get('error')) is str and result['error'] in ERRORS):
                raise DomainError(result['error'])
            if (type(result) is not dict or set(result)!=fields or type(result['v']) is not int
                    or result['v']!=1 or result['policy']!=POLICY or type(result['abi']) is not int
                    or result['abi']<3 or not all(result[k] is True for k in fields-{'v','policy','abi'})):
                raise DomainError('media_worker_protocol')
            return {'policy':POLICY,'abi':result['abi'],'checked':True}
        except OSError:raise DomainError('media_sandbox_unavailable') from None
        finally:
            try:
                if process is not None:
                    try:_terminate(process)
                    finally:
                        if not process.stdin.closed:process.stdin.close()
                        process.stdout.close()
            finally:self._slots.release()

    def normalize(self, payload: bytes, declared_type: str) -> NormalizedPhoto:
        if sys.platform != 'linux' or sys.version_info < (3, 11):
            raise DomainError('media_worker_unsupported')
        if type(payload) is not bytes or not payload:
            raise DomainError('media_invalid_bytes')
        if len(payload) > MAX_INPUT_BYTES:
            raise DomainError('media_input_too_large')
        if type(declared_type) is not str or declared_type not in ('image/png', 'image/jpeg'):
            raise DomainError('media_type_not_allowed')
        if not self._slots.acquire(blocking=False):
            raise DomainError('media_worker_busy')
        process = None
        try:
            process = _launch() if self.sandbox is None else _launch_sandbox(self.sandbox)
            return _parse(_exchange(process, declared_type.encode('ascii') + b'\n' + payload), declared_type)
        except OSError:
            raise DomainError('media_worker_failed') from None
        finally:
            try:
                if process is not None:
                    try:
                        _terminate(process)
                    finally:
                        if not process.stdin.closed:
                            process.stdin.close()
                        process.stdout.close()
            finally:
                self._slots.release()
