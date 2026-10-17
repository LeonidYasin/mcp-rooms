"""Local invite-only identity. No network calls, passwords, or MCP admin methods."""
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import uuid
from urllib.parse import urlsplit
from .store import RoomError, RoomStore, _id, _text, private_path

SCOPES = frozenset({'rooms:read', 'rooms:write'})
TOKEN = re.compile(r'rm1_([0-9a-f]{32})\.([A-Za-z0-9_-]{43})')
UUID_BEARER = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}')


@dataclass(frozen=True)
class Principal:
    user_id: str
    credential_id: str
    scopes: frozenset[str]

    @property
    def owner(self):
        return 'user:' + self.user_id


def resource_url(value):
    if not isinstance(value, str):
        raise RoomError('invalid_resource')
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise RoomError('invalid_resource') from None
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None
            or not re.fullmatch(r'(?:/[A-Za-z0-9_-]+)*/mcp', parsed.path)
            or parsed.query or parsed.fragment or value != value.strip()
            or any(ord(c) < 33 or ord(c) > 126 for c in value)
            or (port is not None and not 1 <= port <= 65535)):
        raise RoomError('invalid_resource')
    return value


class IdentityStore:
    """Use the SAME SQLite database/snapshot as room membership and cadence."""
    def __init__(self, store: RoomStore, resource: str):
        self.store, self.resource = store, resource_url(resource)

    def create_user(self, display_name):
        name, uid = _text(display_name, 80), str(uuid.uuid4())
        with self.store._db(write=True) as db:
            if db.execute('SELECT COUNT(*) FROM users').fetchone()[0] >= self.store.limits.principals:
                raise RoomError('user_capacity')
            db.execute('INSERT INTO users(id,display_name,created_at) VALUES (?,?,?)',
                       (uid, name, self.store.clock()))
        return {'user_id': uid, 'owner': 'user:' + uid, 'display_name': name}

    def issue_token(self, user_id, ttl_seconds=604800, scopes=('rooms:read', 'rooms:write')):
        """Operator API ONLY. Raw secret returned in-process for private-file delivery."""
        _id(user_id)
        if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 7776000:
            raise RoomError('invalid_token_lifetime')
        if not isinstance(scopes, (tuple, list)) or not scopes or not all(
                isinstance(x, str) and x in SCOPES for x in scopes):
            raise RoomError('invalid_scopes')
        scopes = sorted(set(scopes))
        cid = uuid.uuid4().hex
        raw = 'rm1_' + cid + '.' + secrets.token_urlsafe(32)
        digest = hashlib.sha256(raw.encode('ascii')).hexdigest()
        expires = self.store.clock() // 1000 + ttl_seconds
        with self.store._db(write=True) as db:
            user = db.execute('SELECT disabled FROM users WHERE id=?', (user_id,)).fetchone()
            if not user or user['disabled']:
                raise RoomError('user_unavailable')
            # Lifetime count cap deliberately includes expired/revoked keys.
            if db.execute('SELECT COUNT(*) FROM credentials WHERE user_id=?', (user_id,)).fetchone()[0] >= 20:
                raise RoomError('credential_capacity')
            db.execute('INSERT INTO credentials(id,user_id,digest,resource,scopes,expires_at) VALUES (?,?,?,?,?,?)',
                       (cid, user_id, digest, self.resource, json.dumps(scopes), expires))
        return {'credential_id': cid, 'expires_at': expires, 'scopes': scopes}, raw

    def authenticate(self, raw):
        if not isinstance(raw, str):
            return None
        original, own_uuid = TOKEN.fullmatch(raw), UUID_BEARER.fullmatch(raw)
        if not original and not own_uuid:
            return None
        digest = hashlib.sha256(raw.encode('ascii')).hexdigest()
        with self.store._db() as db:
            query = 'SELECT c.*,u.disabled FROM credentials c JOIN users u ON u.id=c.user_id WHERE '
            if original:
                row = db.execute(query + 'c.id=?', (original.group(1),)).fetchone()
            else:
                row = db.execute(query + 'c.digest=?', (digest,)).fetchone()
        matches = hmac.compare_digest(digest, row['digest'] if row else '0' * 64)
        if (not row or not matches or row['disabled'] or row['revoked']
                or row['expires_at'] <= self.store.clock() // 1000
                or row['resource'] != self.resource):
            return None
        scopes = json.loads(row['scopes'])
        if not isinstance(scopes, list) or not scopes or any(s not in SCOPES for s in scopes):
            return None
        return Principal(row['user_id'], cid, frozenset(scopes))

    def revoke(self, credential_id):
        if not isinstance(credential_id, str) or not re.fullmatch(r'[0-9a-f]{32}', credential_id):
            raise RoomError('invalid_credential_id')
        with self.store._db(write=True) as db:
            result = db.execute('UPDATE credentials SET revoked=1 WHERE id=?', (credential_id,))
            if not result.rowcount:
                raise RoomError('credential_unavailable')
        return {'revoked': True, 'credential_id': credential_id}

    def disable(self, user_id):
        _id(user_id)
        with self.store._db(write=True) as db:
            result = db.execute('UPDATE users SET disabled=1 WHERE id=?', (user_id,))
            if not result.rowcount:
                raise RoomError('user_unavailable')
        return {'disabled': True, 'user_id': user_id}


def write_private_token(path, raw):
    """Never stdout. Fail on existing file/alias/shared directory, fsync on success."""
    path = private_path(Path(path))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'w', encoding='ascii') as out:
        out.write(raw + '\n')
        out.flush()
        os.fsync(out.fileno())
    directory = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
