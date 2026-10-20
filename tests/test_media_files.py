"""Synthetic bytes only; internal file mechanics, NOT owner/manifest acceptance."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
import stat
import sys
import pytest
from mcp_rooms import media_files as m
from mcp_rooms.domain import DomainError
from mcp_rooms.media_contract import NormalizedPhoto

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux dirfd/flock storage')


@pytest.fixture
def root(tmp_path):
    tmp_path.chmod(0o700)
    folder = tmp_path / 'derivatives'
    folder.mkdir(mode=0o700)
    return folder


def photo(data=b'\xff\xd8\xffsynthetic\xff\xd9'):
    # Tests the trusted-value boundary, not JPEG validity; real pipeline below.
    return NormalizedPhoto(data, sha256(data).hexdigest(), 20, 10, 'PNG')


def fails(code, fn):
    with pytest.raises(DomainError) as e:
        fn()
    assert e.value.code == code


def test_durable_reopen_and_mode(root):
    with m.PrivatePhotoFiles(root) as files:
        receipt = files.put(photo())
        assert files.read(receipt) == photo().data
        assert len(list(root.iterdir())) == 1
        assert stat.S_IMODE((root / receipt.blob_key).stat().st_mode) == 0o600
        assert '/' not in receipt.blob_key and 'synthetic' not in receipt.blob_key
    with m.PrivatePhotoFiles(root) as reopened:
        assert reopened.read(receipt) == photo().data


def test_no_content_hash_dedup(root):
    with m.PrivatePhotoFiles(root) as files:
        a, b = files.put(photo()), files.put(photo())
        assert a.blob_key != b.blob_key and a.sha256 == b.sha256
        assert files.read(a) == files.read(b)


@pytest.mark.parametrize('kind', ['relative', 'symlink', 'shared-root', 'shared-parent', 'missing', 'file', 'dotdot'])
def test_bad_roots(root, kind):
    target = root
    if kind == 'relative':
        target = Path('relative')
    elif kind == 'symlink':
        target = root.parent / 'alias'
        target.symlink_to(root, target_is_directory=True)
    elif kind == 'shared-root':
        root.chmod(0o750)
    elif kind == 'shared-parent':
        root.parent.chmod(0o755)
    elif kind == 'missing':
        target = root / 'missing'
    elif kind == 'file':
        target = root.parent / 'file'
        target.write_bytes(b'not-directory')
    elif kind == 'dotdot':
        target = root / '..' / root.name
    fails('media_storage_unsafe', lambda: m.PrivatePhotoFiles(target))


def test_closed_and_replaced_root(root):
    files = m.PrivatePhotoFiles(root)
    old = root.with_name('old')
    root.rename(old)
    root.mkdir(mode=0o700)
    fails('media_storage_unsafe', lambda: files.put(photo()))
    assert not list(root.iterdir()) and not list(old.iterdir())
    files.close()
    files.close()
    fails('media_storage_closed', lambda: files.put(photo()))


@pytest.mark.parametrize('kind', ['unknown', 'directory', 'symlink', 'hardlink', 'shared'])
def test_inventory_rejects_unsafe_files(root, kind):
    path = root / ('a'*32 + '.jpg')
    if kind == 'unknown':
        (root / 'operator-note').write_bytes(b'leave unchanged')
    elif kind == 'directory':
        path.mkdir()
    elif kind == 'symlink':
        path.symlink_to(root.parent / 'missing')
    else:
        path.write_bytes(b'x')
        path.chmod(0o600)
        if kind == 'hardlink':
            os.link(path, root.parent / 'link')
        else:
            path.chmod(0o640)
    before = set(root.iterdir())
    with m.PrivatePhotoFiles(root) as files:
        fails('media_storage_unsafe', lambda: files.put(photo()))
    assert set(root.iterdir()) == before


@pytest.mark.parametrize('change', [dict(sha256='wrong'), dict(width=True), dict(height=1601),
                                   dict(data=b'bad'), dict(content_type='text/html')])
def test_invalid_derivative(root, change):
    with m.PrivatePhotoFiles(root) as files:
        fails('media_derivative_invalid', lambda: files.put(replace(photo(), **change)))
    assert not list(root.iterdir())


@pytest.mark.parametrize('key', ['../secret', '/etc/passwd', 'a'*32+'.jpg/extra', 'x', 'A'*32+'.jpg'])
def test_invalid_key_never_opened(root, key):
    with m.PrivatePhotoFiles(root) as files:
        receipt = files.put(photo())
        fails('media_derivative_invalid', lambda: files.read(replace(receipt, blob_key=key)))


@pytest.mark.parametrize('kind', ['same-size', 'truncated', 'hardlink', 'mode'])
def test_read_integrity(root, kind):
    with m.PrivatePhotoFiles(root) as files:
        receipt = files.put(photo())
        path = root / receipt.blob_key
        if kind == 'same-size':
            path.write_bytes(b'x' * receipt.byte_size)
        elif kind == 'truncated':
            path.write_bytes(b'x')
        elif kind == 'hardlink':
            os.link(path, root.parent / 'alias')
        else:
            path.chmod(0o644)
        fails('media_storage_integrity', lambda: files.read(receipt))


def test_symlink_missing_fifo_fail_closed(root):
    with m.PrivatePhotoFiles(root) as files:
        receipt = files.put(photo())
        path = root / receipt.blob_key
        path.unlink()
        fails('media_storage_io', lambda: files.read(receipt))
        path.symlink_to(root.parent / 'secret')
        fails('media_storage_io', lambda: files.read(receipt))
        path.unlink()
        os.mkfifo(path, mode=0o600)
        fails('media_storage_integrity', lambda: files.read(receipt))


def test_quota_survives_reopen(root, monkeypatch):
    monkeypatch.setattr(m, 'MAX_FILES', 2)
    with m.PrivatePhotoFiles(root) as files:
        files.put(photo())
        files.put(photo())
        fails('media_storage_quota', lambda: files.put(photo()))
    with m.PrivatePhotoFiles(root) as files:
        fails('media_storage_quota', lambda: files.put(photo()))
    assert len(list(root.iterdir())) == 2


def test_byte_quota(root, monkeypatch):
    monkeypatch.setattr(m, 'MAX_TOTAL_BYTES', len(photo().data))
    with m.PrivatePhotoFiles(root) as files:
        files.put(photo())
        fails('media_storage_quota', lambda: files.put(photo()))


def test_two_instances_share_admission(root, monkeypatch):
    monkeypatch.setattr(m, 'MAX_FILES', 1)
    with m.PrivatePhotoFiles(root) as first, m.PrivatePhotoFiles(root) as second:
        def put(files):
            try:
                return files.put(photo())
            except DomainError as e:
                return e.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(put, [first, second]))
        assert results.count('media_storage_quota') == 1
    assert len(list(root.iterdir())) == 1


def test_failed_write_and_short_write(root, monkeypatch):
    original = os.write
    with m.PrivatePhotoFiles(root) as files:
        def full(*args):
            raise OSError('synthetic disk full')
        with monkeypatch.context() as patch:
            patch.setattr(os, 'write', full)
            fails('media_storage_io', lambda: files.put(photo()))
        assert not list(root.iterdir())
        with monkeypatch.context() as patch:
            patch.setattr(os, 'write', lambda fd, data: original(fd, data[:2]))
            receipt = files.put(photo())
        assert files.read(receipt) == photo().data


def test_file_fsync_failure_rolls_back(root, monkeypatch):
    with m.PrivatePhotoFiles(root) as files:
        def broken(fd):
            raise OSError('synthetic fsync failure')
        with monkeypatch.context() as patch:
            patch.setattr(os, 'fsync', broken)
            fails('media_storage_io', lambda: files.put(photo()))
        assert not list(root.iterdir())


def test_real_worker_to_private_file(root):
    if sys.version_info < (3, 11):
        pytest.skip('optional codec requires Python >=3.11')
    from io import BytesIO
    from PIL import Image
    from mcp_rooms.media_worker import PhotoWorker
    with Image.new('RGB', (30, 15), 'blue') as source, BytesIO() as output:
        source.save(output, format='PNG')
        normalized = PhotoWorker().normalize(output.getvalue(), 'image/png')
    with m.PrivatePhotoFiles(root) as files:
        receipt = files.put(normalized)
        with Image.open(BytesIO(files.read(receipt))) as decoded:
            decoded.load()
            assert decoded.format == 'JPEG' and decoded.size == (30, 15)
