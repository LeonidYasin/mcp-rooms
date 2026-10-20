"""CI-only synthetic subprocess/codec fixtures. Never real credentials or photos."""
from hashlib import sha256
from io import BytesIO
import json
import subprocess
import sys
import threading
import pytest
from mcp_rooms import media_worker as m
from mcp_rooms.domain import DomainError

pytestmark = pytest.mark.skipif(sys.platform != 'linux' or sys.version_info < (3, 11),
                                reason='Linux media worker requires Python >=3.11')


def image(fmt='PNG'):
    from PIL import Image
    with Image.new('RGB', (20, 10), 'red') as source, BytesIO() as out:
        source.save(out, format=fmt)
        return out.getvalue()


def error(code, fn):
    with pytest.raises(DomainError) as caught:
        fn()
    assert caught.value.code == code


@pytest.mark.parametrize('fmt,mime', [('PNG', 'image/png'), ('JPEG', 'image/jpeg')])
def test_real_installed_child(fmt, mime):
    result = m.PhotoWorker().normalize(image(fmt), mime)
    assert result.sha256 == sha256(result.data).hexdigest()
    assert result.source_format == fmt and (result.width, result.height) == (20, 10)
    from PIL import Image
    with Image.open(BytesIO(result.data)) as decoded:
        decoded.load()
        assert decoded.format == 'JPEG'


def test_real_child_decode_error():
    error('media_type_mismatch', lambda: m.PhotoWorker().normalize(b'bad', 'image/png'))


@pytest.mark.parametrize('payload,mime,code', [
    (b'', 'image/png', 'media_invalid_bytes'),
    (bytearray(b'x'), 'image/png', 'media_invalid_bytes'),
    (b'x' * (m.MAX_INPUT_BYTES + 1), 'image/png', 'media_input_too_large'),
    (b'x', 'image/svg+xml', 'media_type_not_allowed'),
])
def test_reject_before_spawn(monkeypatch, payload, mime, code):
    monkeypatch.setattr(m, '_launch', lambda: pytest.fail('must not launch'))
    error(code, lambda: m.PhotoWorker().normalize(payload, mime))


def test_clean_launch_contract(monkeypatch):
    monkeypatch.setenv('SYNTHETIC_SECRET', 'must-not-forward')
    calls = []
    monkeypatch.setattr(m.subprocess, 'Popen', lambda *a, **kw: calls.append((a, kw)))
    m._launch()
    args, kw = calls[0]
    assert args[0] == [sys.executable, '-I', '-B', '-m', 'mcp_rooms.media_worker_child']
    assert kw['env'] == {'LANG': 'C.UTF-8'}
    assert kw['start_new_session'] and kw['close_fds']
    assert not kw.get('shell') and 'preexec_fn' not in kw
    assert kw['stderr'] == subprocess.DEVNULL


def harness(monkeypatch, code):
    children = []
    def launch():
        child = subprocess.Popen([sys.executable, '-I', '-c', code], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 start_new_session=True, close_fds=True, env={'LANG': 'C.UTF-8'})
        children.append(child)
        return child
    monkeypatch.setattr(m, '_launch', launch)
    return children


@pytest.mark.parametrize('code,expected', [
    ('import sys; sys.stdin.buffer.read(); sys.exit(3)', 'media_worker_failed'),
    ('import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b"bad")', 'media_worker_protocol'),
    ('import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b"x"*2200000)', 'media_worker_output_limit'),
    ('import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b\'{"v":1,"error":"secret"}\\n\')', 'media_worker_protocol'),
])
def test_faults_reaped_and_slots_released(monkeypatch, code, expected):
    children = harness(monkeypatch, code)
    worker = m.PhotoWorker()
    for _ in range(3):
        error(expected, lambda: worker.normalize(b'x', 'image/png'))
    assert all(child.poll() is not None for child in children)


def test_wall_deadline_and_reap(monkeypatch):
    children = harness(monkeypatch, 'import time; time.sleep(30)')
    monkeypatch.setattr(m, 'WALL_SECONDS', .25)
    error('media_worker_timeout', lambda: m.PhotoWorker().normalize(b'x', 'image/png'))
    assert children[0].poll() is not None


def test_no_queue(monkeypatch):
    worker = m.PhotoWorker()
    assert worker._slots.acquire(False) and worker._slots.acquire(False)
    monkeypatch.setattr(m, '_launch', lambda: pytest.fail('must reject admission'))
    try:
        error('media_worker_busy', lambda: worker.normalize(b'x', 'image/png'))
    finally:
        worker._slots.release()
        worker._slots.release()


def frame(**changes):
    data = b'\xff\xd8\xfffake\xff\xd9'
    header = dict(v=1, size=len(data), sha256=sha256(data).hexdigest(), width=1,
                  height=1, source_format='PNG', content_type='image/jpeg')
    header.update(changes)
    return json.dumps(header).encode() + b'\n' + data


@pytest.mark.parametrize('change', [dict(size=1), dict(width=True), dict(height=1601),
                                   dict(sha256='wrong'), dict(v=True), dict(extra=1),
                                   dict(source_format='JPEG')])
def test_protocol_rejects(change):
    error('media_worker_protocol', lambda: m._parse(frame(**change), 'image/png'))


@pytest.mark.parametrize('wire', [b'{"v":1,"v":1}\n', b'[]\n',
                                 b'{"v":1,"error":"media_invalid_image"}\nextra',
                                 b'x'*2049+b'\n'])
def test_protocol_invalid_frame(wire):
    error('media_worker_protocol', lambda: m._parse(wire, 'image/png'))


def test_no_decoder_import_in_supervisor():
    probe = subprocess.run([sys.executable, '-I', '-c',
        'import sys; import mcp_rooms.media_worker; assert "PIL" not in sys.modules'],
        capture_output=True, timeout=10)
    assert probe.returncode == 0


def test_child_limits_precede_codec_import():
    # Structural gate plus real codec child tests; not OS sandbox acceptance.
    import inspect
    from mcp_rooms import media_worker_child
    source = inspect.getsource(media_worker_child.main)
    for name in ('RLIMIT_AS', 'RLIMIT_CPU', 'RLIMIT_FSIZE', 'RLIMIT_CORE', 'RLIMIT_NOFILE', 'RLIMIT_NPROC'):
        assert source.index(name) < source.index('from .media_image import')
