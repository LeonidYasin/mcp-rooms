"""Opt-in private derivative files; NOT owner authorization or a media manifest.

Only trusted application code may construct/use this object with an operator-owned
root. Never expose blob keys or filesystem operations via HTTP/MCP. Linux only.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import os
from pathlib import Path
import re
import stat
import sys
import threading
import uuid
from .domain import DomainError
from .media_contract import MAX_OUTPUT_BYTES, OUTPUT_SIDE, NormalizedPhoto

MAX_FILES = 256
MAX_TOTAL_BYTES = 32 * 1024 * 1024
_KEY = re.compile(r'[0-9a-f]{32}\.jpg\Z')


@dataclass(frozen=True)
class StoredDerivative:
    """Internal receipt. Blob key is private, not a URL/media_id or access token."""
    blob_key: str
    sha256: str
    byte_size: int
    width: int
    height: int


def _file_ok(info):
    return (stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
            and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600
            and 0 < info.st_size <= MAX_OUTPUT_BYTES)


def _directory_ok(info):
    return (stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) == 0o700)


class PrivatePhotoFiles:
    """Fixed root, exclusive creation, durable bytes, bounded scan and integrity.

    Root must already exist with mode0700. No directory repair/chmod, migrations,
    deletion API, background cleanup or default server startup integration.
    Quotas cover logical derivative sizes, NOT block allocation/backups/other roots.
    Cooperating instances serialize with flock plus a per-instance thread lock.
    Same-uid hostile processes and privileged operators are outside this boundary.
    """
    def __init__(self, root):
        self._fd = None
        self._lock = threading.Lock()
        if sys.platform != 'linux':
            raise DomainError('media_files_unsupported')
        self._root = Path(root)
        if not self._root.is_absolute() or self._root.resolve() != self._root:
            raise DomainError('media_storage_unsafe')
        try:
            parent = self._root.parent.stat()
            if not _directory_ok(parent):
                raise DomainError('media_storage_unsafe')
            fd = os.open(self._root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            self._fd = fd
            self._check_root()
        except (OSError, DomainError):
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None
            raise DomainError('media_storage_unsafe') from None

    def _check_root(self):
        if self._fd is None:
            raise DomainError('media_storage_closed')
        actual = os.fstat(self._fd)
        named = self._root.lstat()
        if (not _directory_ok(actual) or not _directory_ok(named)
                or (actual.st_dev, actual.st_ino) != (named.st_dev, named.st_ino)
                or self._root.resolve() != self._root
                or not _directory_ok(self._root.parent.stat())):
            raise DomainError('media_storage_unsafe')

    @contextmanager
    def _guard(self):
        with self._lock:
            try:
                self._check_root()
                fcntl.flock(self._fd, fcntl.LOCK_EX)
                try:
                    self._check_root()
                    yield
                finally:
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
            except OSError:
                raise DomainError('media_storage_io') from None

    def close(self):
        with self._lock:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _inventory(self):
        count = total = 0
        with os.scandir(self._fd) as entries:
            for entry in entries:
                count += 1
                if count > MAX_FILES:
                    raise DomainError('media_storage_quota')
                if not _KEY.fullmatch(entry.name):
                    raise DomainError('media_storage_unsafe')
                info = entry.stat(follow_symlinks=False)
                if not _file_ok(info):
                    raise DomainError('media_storage_unsafe')
                total += info.st_size
                if total > MAX_TOTAL_BYTES:
                    raise DomainError('media_storage_quota')
        return count, total

    def put(self, photo):
        # Only an internal normalizer/worker result, not arbitrary request bytes.
        if (type(photo) is not NormalizedPhoto or type(photo.data) is not bytes
                or not 0 < len(photo.data) <= MAX_OUTPUT_BYTES
                or not photo.data.startswith(b'\xff\xd8\xff') or not photo.data.endswith(b'\xff\xd9')
                or photo.sha256 != sha256(photo.data).hexdigest()
                or photo.content_type != 'image/jpeg' or photo.source_format not in ('PNG', 'JPEG')
                or any(type(v) is not int or not 1 <= v <= OUTPUT_SIDE for v in (photo.width, photo.height))):
            raise DomainError('media_derivative_invalid')
        with self._guard():
            count, total = self._inventory()
            if count >= MAX_FILES or total + len(photo.data) > MAX_TOTAL_BYTES:
                raise DomainError('media_storage_quota')
            key = uuid.uuid4().hex + '.jpg'
            fd = None
            created = False
            try:
                fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                             | os.O_CLOEXEC | os.O_NONBLOCK, 0o600, dir_fd=self._fd)
                created = True
                # Restrictive umask may remove owner permissions: set on our new fd only.
                os.fchmod(fd, 0o600)
                offset = 0
                while offset < len(photo.data):
                    written = os.write(fd, photo.data[offset:])
                    if written <= 0:
                        raise OSError('short write')
                    offset += written
                os.fsync(fd)
                info = os.fstat(fd)
                if not _file_ok(info) or info.st_size != len(photo.data):
                    raise DomainError('media_storage_unsafe')
                os.close(fd)
                fd = None
                os.fsync(self._fd)
                # Only now may a later layer commit a re-authorized SQLite manifest.
                return StoredDerivative(key, photo.sha256, len(photo.data), photo.width, photo.height)
            except BaseException:
                if fd is not None:
                    os.close(fd)
                if created:
                    # Roll back only this newly generated key. A process crash can still
                    # leave an orphan; reconciliation, not an ACID claim, handles that.
                    try:
                        os.unlink(key, dir_fd=self._fd)
                        os.fsync(self._fd)
                    except OSError:
                        pass
                raise

    def read(self, receipt):
        """Internal integrity read. Caller MUST authorize persisted owner/manifest first."""
        if (type(receipt) is not StoredDerivative or type(receipt.blob_key) is not str
                or not _KEY.fullmatch(receipt.blob_key)
                or type(receipt.byte_size) is not int or not 0 < receipt.byte_size <= MAX_OUTPUT_BYTES
                or type(receipt.sha256) is not str or not re.fullmatch('[0-9a-f]{64}', receipt.sha256)):
            raise DomainError('media_derivative_invalid')
        with self._guard():
            fd = os.open(receipt.blob_key, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                         | os.O_CLOEXEC, dir_fd=self._fd)
            try:
                before = os.fstat(fd)
                if not _file_ok(before) or before.st_size != receipt.byte_size:
                    raise DomainError('media_storage_integrity')
                data = bytearray()
                while True:
                    block = os.read(fd, min(65536, receipt.byte_size + 1 - len(data)))
                    if not block:
                        break
                    data.extend(block)
                    if len(data) > receipt.byte_size:
                        raise DomainError('media_storage_integrity')
                after = os.fstat(fd)
                if (not _file_ok(after) or after.st_size != len(data)
                        or after.st_mtime_ns != before.st_mtime_ns
                        or after.st_ctime_ns != before.st_ctime_ns
                        or len(data) != receipt.byte_size or sha256(data).hexdigest() != receipt.sha256):
                    raise DomainError('media_storage_integrity')
                return bytes(data)
            finally:
                os.close(fd)
