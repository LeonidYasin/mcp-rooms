"""Private one-shot Linux child. Never a user-facing command or network server."""
import json
import sys


def main():
    # Before importing Pillow/normalizer. No preexec_fn in a threaded parent.
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    from .media_contract import MAX_INPUT_BYTES
    from .domain import DomainError
    from .media_worker import ERRORS
    # Parse only trusted supervisor arguments; policy precedes all decoder imports
    # and input bytes. Failure returns a typed error, never an unprotected retry.
    if sys.argv[1:]:
        try:
            if len(sys.argv)!=3 or sys.argv[1] not in ('--sandbox','--sandbox-check'):
                raise DomainError('media_sandbox_policy_invalid')
            from pathlib import Path
            from .media_sandbox import NativeSandbox, enforce, probe
            policy=NativeSandbox(Path(sys.argv[2]))
            abi=enforce(policy)
            if sys.argv[1]=='--sandbox-check':
                sys.stdout.buffer.write(json.dumps(probe(policy,abi),separators=(',',':')).encode()+b'\n')
                return 0
        except (DomainError,OSError) as exc:
            code=exc.code if isinstance(exc,DomainError) else 'media_sandbox_unavailable'
            sys.stdout.buffer.write(json.dumps({'v':1,'error':code}).encode()+b'\n')
            return 0
    from .media_image import normalize_photo
    line = sys.stdin.buffer.readline(128)
    if line not in (b'image/png\n', b'image/jpeg\n'):
        return 2
    payload = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    try:
        result = normalize_photo(payload, line[:-1].decode('ascii'))
    except DomainError as error:
        code = error.code if error.code in ERRORS else 'media_worker_failed'
        sys.stdout.buffer.write(json.dumps({'v': 1, 'error': code}).encode() + b'\n')
        return 0
    header = dict(v=1, size=len(result.data), sha256=result.sha256,
                  width=result.width, height=result.height,
                  source_format=result.source_format, content_type=result.content_type)
    sys.stdout.buffer.write(json.dumps(header, separators=(',', ':')).encode() + b'\n')
    sys.stdout.buffer.write(result.data)
    return 0


if __name__ == '__main__':
    sys.exit(main())
