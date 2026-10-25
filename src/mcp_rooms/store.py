"""SQLite room core. No HTTP, models, credentials, background tasks or global connection."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
import uuid


# Compatibility aliases: existing clients/tests keep the same exception identity.
from .domain import DomainError as RoomError, identifier as _id, text as _text

# Base topic catalog seed (unified tree source for rooms; the marketplace categories are
# eventually folded into it). Root has parent_id None. Slugs, not UUIDs.
TOPIC_SEED = (
    ('market', None, 'Маркет и товары'),
    ('market-goods', 'market', 'Товары и услуги'),
    ('market-used', 'market', 'Б/у вещи'),
    ('transport', None, 'Транспорт'),
    ('taxi', 'transport', 'Такси'),
    ('delivery', 'transport', 'Доставка и курьеры'),
    ('hiring', None, 'Найм и работа'),
    ('jobs', 'hiring', 'Предложения работы'),
    ('resumes', 'hiring', 'Резюме и вакансии'),
    ('finance', None, 'Финансы и стартапы'),
    ('investors', 'finance', 'Поиск инвесторов'),
    ('startups', 'finance', 'Стартапы'),
    ('realestate', None, 'Недвижимость'),
    ('home', 'realestate', 'Жильё'),
    ('commercial', 'realestate', 'Коммерческая'),
    ('misc', None, 'Разное'),
)

_VISIBLE = frozenset({'private', 'open'})


def _topic_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', value):
        raise RoomError('invalid_topic_id')
    return value


@dataclass(frozen=True)
class Limits:
    rooms: int = 100
    rooms_per_owner: int = 5
    principals: int = 1000
    memberships_per_owner: int = 20
    members_per_room: int = 100
    messages: int = 20000
    messages_per_room: int = 1000
    text: int = 500
    cadence_ms: int = 10000
    ttl_ms: int = 86400000


def _limit(value):
    if type(value) is not int or not 1 <= value <= 100:
        raise RoomError('invalid_limit')
    return value


def _cursor(value, scope):
    if value is None:
        return 0
    if not isinstance(value, str) or len(value) > 80 or not value.startswith(scope + ':'):
        raise RoomError('invalid_cursor')
    sequence = value[len(scope) + 1:]
    if not re.fullmatch(r'0|[1-9][0-9]{0,18}', sequence) or int(sequence) > 9223372036854775807:
        raise RoomError('invalid_cursor')
    return int(sequence)


def private_path(path):
    """Admin-controlled local path; reject aliases and shared/wrong-owner parents."""
    path = Path(path)
    if (not path.is_absolute() or path.resolve() != path or
            not path.parent.is_dir()):
        raise RoomError('invalid_database_path')
    parent = path.parent.stat()
    if parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) & 0o077:
        raise RoomError('unsafe_database_directory')
    return path


class RoomStore:
    # SQLite database pages only: 64 MiB at the required 4096-byte page size.
    # WAL/SHM/backups still require an operator filesystem budget and monitoring.
    MAX_PAGES = 16384
    APPLICATION_ID = 0x4D435252  # MCRR: standalone, NOT the embedded database

    def __init__(self, path, clock=None, limits=Limits(), *, initialize=True):
        if type(initialize) is not bool:
            raise RoomError('invalid_initialize_policy')
        self._existing_only = not initialize
        self.path = private_path(path)
        self.clock = clock or (lambda: int(time.time() * 1000))
        self.limits = limits
        if not self.path.is_absolute() or not self.path.parent.is_dir() or self.path.is_symlink():
            raise RoomError('invalid_database_path')
        if not initialize:
            self._open_existing()
            return
        # Admin-controlled, private directory required. Never accept a path from tool arguments.
        flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
        fd = os.open(self.path, flags, 0o600)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                    info.st_uid != os.geteuid()):
                raise RoomError('invalid_database_path')
            if info.st_size:
                # Reject an embedded/foreign database BEFORE changing its mode,
                # journal, schema or application_id. Never auto-migrate identity.
                existing = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=5)
                try:
                    self._validate_identity(existing)
                finally:
                    existing.close()
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        with self._db(write=True, initialize=True) as db:
            self._validate_identity(db)
            for statement in (
                'CREATE TABLE IF NOT EXISTS actors (owner TEXT PRIMARY KEY, last_send INTEGER)',
                'CREATE TABLE IF NOT EXISTS rooms (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, owner TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, created_at INTEGER NOT NULL)',
                'CREATE TABLE IF NOT EXISTS members (room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE, owner TEXT NOT NULL, PRIMARY KEY(room_id, owner))',
                'CREATE INDEX IF NOT EXISTS members_owner ON members(owner)',
                'CREATE TABLE IF NOT EXISTS messages (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE, owner TEXT NOT NULL, text TEXT NOT NULL, digest TEXT NOT NULL, client_id TEXT NOT NULL, reply_to TEXT, deleted INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, UNIQUE(room_id, owner, client_id))',
                'CREATE INDEX IF NOT EXISTS messages_room_seq ON messages(room_id, seq)',
                'CREATE INDEX IF NOT EXISTS messages_expiry ON messages(expires_at)',
            ):
                db.execute(statement)
            db.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, display_name TEXT NOT NULL, disabled INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS credentials (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), digest TEXT NOT NULL UNIQUE, resource TEXT NOT NULL, scopes TEXT NOT NULL, expires_at INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE INDEX IF NOT EXISTS credentials_user ON credentials(user_id)')
            db.execute('PRAGMA application_id=' + str(self.APPLICATION_ID))
            # Additive v1->v2 standalone migration; never touches embedded owners.
            db.execute('CREATE TABLE IF NOT EXISTS enrollments (bootstrap_digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), credential_id TEXT NOT NULL UNIQUE REFERENCES credentials(id), contact_kind TEXT NOT NULL, created_at INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS signup_budgets (scope TEXT NOT NULL, bucket INTEGER NOT NULL, used INTEGER NOT NULL, expires_at INTEGER NOT NULL, PRIMARY KEY(scope,bucket))')
            # Additive base topic catalog; rooms table and user_version are UNCHANGED.
            # room_topics is a side table (room -> topic/visibility, fixed at create).
            db.execute('CREATE TABLE IF NOT EXISTS topics (id TEXT PRIMARY KEY, parent_id TEXT REFERENCES topics(id), title TEXT NOT NULL)')
            db.execute("CREATE TABLE IF NOT EXISTS room_topics (room_id TEXT PRIMARY KEY REFERENCES rooms(id) ON DELETE CASCADE, topic_id TEXT NOT NULL REFERENCES topics(id), visibility TEXT NOT NULL CHECK(visibility IN ('private','open')))")
            if db.execute('SELECT COUNT(*) FROM topics').fetchone()[0] == 0:
                db.executemany('INSERT INTO topics VALUES (?,?,?)', TOPIC_SEED)
            db.execute('PRAGMA user_version=2')

    def _open_existing(self):
        """No creation, chmod, initialization or migration; candidate checks more schemas."""
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600
                    or not 0 < info.st_size <= self.MAX_PAGES * 4096):
                raise RoomError('invalid_database_path')
            db = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=5)
            try:
                db.execute('PRAGMA query_only=ON')
                self._validate_identity(db)
                if (db.execute('PRAGMA user_version').fetchone()[0] != 2
                        or db.execute('PRAGMA application_id').fetchone()[0] != self.APPLICATION_ID
                        or db.execute('PRAGMA page_size').fetchone()[0] != 4096):
                    raise RoomError('existing_database_required')
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not {'actors','rooms','members','messages','users','credentials','enrollments','signup_budgets'} <= tables:
                    raise RoomError('existing_database_required')
                current = self.path.stat(follow_symlinks=False)
                if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
                    raise RoomError('invalid_database_path')
            finally:
                db.close()
        finally:
            os.close(fd)

    @classmethod
    def _validate_identity(cls, db):
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1, 2):
            raise RoomError('unsupported_database_version')
        app_id = db.execute('PRAGMA application_id').fetchone()[0]
        existing = db.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone()
        if app_id != cls.APPLICATION_ID and (app_id != 0 or existing or version != 0):
            raise RoomError('unsupported_database_identity')

    @contextmanager
    def _db(self, write=False, initialize=False):
        if initialize and self._existing_only:
            raise RoomError('existing_database_required')
        if self._existing_only:
            db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=5, isolation_level=None)
        else:
            db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA busy_timeout=5000')
            db.execute('PRAGMA synchronous=FULL')
            if db.execute('PRAGMA page_size').fetchone()[0] != 4096:
                raise RoomError('unsupported_database_page_size')
            if db.execute('PRAGMA max_page_count=' + str(self.MAX_PAGES)).fetchone()[0] > self.MAX_PAGES:
                raise RoomError('room_storage_capacity')
            db.execute('PRAGMA wal_autocheckpoint=256')
            db.execute('PRAGMA journal_size_limit=1048576')
            if initialize:
                db.execute('PRAGMA journal_mode=WAL')
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _actor(self, db, owner):
        if not isinstance(owner, str) or not re.fullmatch(r'user:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', owner):
            raise RoomError('invalid_principal')
        if not db.execute('SELECT 1 FROM actors WHERE owner=?', (owner,)).fetchone():
            if db.execute('SELECT COUNT(*) FROM actors').fetchone()[0] >= self.limits.principals:
                raise RoomError('principal_capacity')
            db.execute('INSERT INTO actors(owner) VALUES (?)', (owner,))

    def _room(self, db, room_id):
        row = db.execute('SELECT * FROM rooms WHERE id=?', (_id(room_id),)).fetchone()
        if not row:
            raise RoomError('room_unavailable')
        return row

    def _member(self, db, room_id, owner):
        self._room(db, room_id)
        if not db.execute('SELECT 1 FROM members WHERE room_id=? AND owner=?', (room_id, owner)).fetchone():
            raise RoomError('membership_required')

    @staticmethod
    def _message(row):
        return {k: row[k] for k in ('id', 'room_id', 'owner', 'text', 'reply_to', 'deleted', 'created_at', 'expires_at')}

    def create(self, owner, title, description='', topic_id=None, visibility=None):
        title = _text(title, 80)
        description = _text(description, 300) if description != '' else ''
        have_meta = topic_id is not None or visibility is not None
        if topic_id is not None:
            _topic_id(topic_id)
        if visibility is not None and visibility not in _VISIBLE:
            raise RoomError('invalid_visibility')
        if have_meta and topic_id is None:
            raise RoomError('topic_required')
        room_id, now = str(uuid.uuid4()), self.clock()
        with self._db(write=True) as db:
            self._actor(db, owner)
            if db.execute('SELECT COUNT(*) FROM rooms').fetchone()[0] >= self.limits.rooms:
                raise RoomError('room_capacity')
            if db.execute('SELECT COUNT(*) FROM rooms WHERE owner=?', (owner,)).fetchone()[0] >= self.limits.rooms_per_owner:
                raise RoomError('owner_room_capacity')
            self._join_capacity(db, owner)
            db.execute('INSERT INTO rooms(id,owner,title,description,created_at) VALUES (?,?,?,?,?)', (room_id, owner, title, description, now))
            db.execute('INSERT INTO members VALUES (?,?)', (room_id, owner))
            if have_meta:
                if not db.execute('SELECT 1 FROM topics WHERE id=?', (topic_id,)).fetchone():
                    raise RoomError('topic_unavailable')
                db.execute("INSERT INTO room_topics(room_id,topic_id,visibility) VALUES (?,?,?)", (room_id, topic_id, visibility or "private"))
        result = {'room_id': room_id, 'owner': owner, 'title': title,
                  'visibility': (visibility or 'private') if have_meta else 'public_to_enrolled_users'}
        if have_meta:
            result['topic_id'] = topic_id
        return result

    def list(self, owner, cursor=None, limit=20, topic=None):
        after, limit = _cursor(cursor, 'rooms'), _limit(limit)
        topic_filter, params = '', []
        if topic is not None:
            _topic_id(topic)
            topic_filter = ' AND EXISTS(SELECT 1 FROM room_topics rt WHERE rt.room_id=r.id AND rt.topic_id=?)'
            params.append(topic)
        with self._db() as db:
            rows = db.execute(
                'SELECT r.*, rt.topic_id AS topic_id, rt.visibility AS visibility, '
                'EXISTS(SELECT 1 FROM members m WHERE m.room_id=r.id AND m.owner=?) AS joined '
                'FROM rooms r LEFT JOIN room_topics rt ON rt.room_id=r.id '
                'WHERE r.seq>?' + topic_filter + ' ORDER BY r.seq LIMIT ?',
                (owner, after, *params, limit + 1)).fetchall()
        selected = rows[:limit]
        return {'rooms': [{k: row[k] for k in ('id', 'owner', 'title', 'description', 'created_at', 'joined', 'topic_id', 'visibility')} for row in selected],
                'next_cursor': 'rooms:' + str(selected[-1]['seq'] if selected else after), 'has_more': len(rows) > limit}

    def topics(self, owner, parent_id=None):
        """Bounded catalog children for the united topic tree; read-only scope."""
        where, params = 'parent_id IS ?', [None]
        if parent_id is not None:
            _topic_id(parent_id)
            where, params = 'parent_id = ?', [parent_id]
        with self._db() as db:
            rows = db.execute('SELECT id, parent_id, title FROM topics WHERE ' + where + ' ORDER BY id LIMIT 101', params).fetchall()
        if len(rows) > 100:
            raise RoomError('topic_capacity')
        return {'topics': [dict(row) for row in rows]}

    def _join_capacity(self, db, owner):
        if db.execute('SELECT COUNT(*) FROM members WHERE owner=?', (owner,)).fetchone()[0] >= self.limits.memberships_per_owner:
            raise RoomError('membership_capacity')

    def public_topics(self, parent_id=None):
        """Anonymous bounded-1-level browse of the united topic tree; no principal."""
        where, params = 'parent_id IS ?', [None]
        if parent_id is not None:
            _topic_id(parent_id)
            where, params = 'parent_id = ?', [parent_id]
        with self._db() as db:
            rows = db.execute('SELECT id, parent_id, title FROM topics WHERE ' + where + ' ORDER BY id LIMIT 101', params).fetchall()
        if len(rows) > 100: raise RoomError('topic_capacity')
        return {'topics': [dict(row) for row in rows]}

    def public_open_rooms(self, topic=None):
        """Anonymous read-only projection of OPEN rooms; fail-closed: private/legacy rooms and
        owner UUIDs are never exposed, only room_topics.visibility='open' rows (closed rooms are
        removed from rooms/room_topics and therefore absent). Bounded to 50 newest open rooms."""
        if topic is not None:
            _topic_id(topic)
        with self._db() as db:
            sections = [
                {'id': s['id'], 'title': s['title'], 'count': s['n']}
                for s in db.execute(
                    'SELECT t.id, t.title, COUNT(rt.room_id) AS n FROM room_topics rt '
                    'JOIN topics t ON t.id=rt.topic_id WHERE rt.visibility=? '
                    'GROUP BY t.id, t.title ORDER BY t.title',
                    ('open',)).fetchall()
            ]
            where, args = ('', []) if topic is None else (' AND rt.topic_id=?', [topic])
            rooms = db.execute(
                'SELECT r.id, r.title, rt.topic_id AS topic_id, t.title AS topic_title, r.created_at '
                'FROM room_topics rt JOIN rooms r ON r.id=rt.room_id JOIN topics t ON t.id=rt.topic_id '
                'WHERE rt.visibility=?' + where + ' ORDER BY r.seq DESC LIMIT 51', ('open', *args)).fetchall()
        return {'sections': sections, 'rooms': [dict(x) for x in rooms][:50]}

    def _open_room(self, db, room_id):
        """Open-room row for public reads, or None (closed room). Fail-closed by construction:
        only room_topics.visibility='open' rows are visible; private/legacy/closed rooms return None."""
        row = db.execute(
            'SELECT r.id, r.title, r.created_at, rt.topic_id, t.title AS topic_title '
            'FROM room_topics rt JOIN rooms r ON r.id=rt.room_id JOIN topics t ON t.id=rt.topic_id '
            'WHERE rt.room_id=? AND rt.visibility=?', (room_id, 'open')).fetchone()
        return dict(row) if row else None

    def public_open_room(self, room_id):
        """Anonymous metadata for one OPEN room; private/legacy rooms are indistinguishable from
        missing (fail closed). No owner UUID, no member counts, no private data."""
        _id(room_id)
        with self._db() as db:
            room = self._open_room(db, room_id)
        if room is None:
            raise RoomError('room_unavailable')
        return {'room': room}

    def public_open_room_messages(self, room_id, cursor=None, limit=20):
        """Anonymous bounded read-only history of one OPEN room. Fail-closed: private/legacy rooms
        are reported unavailable. Only safe fields (id, text, created_at) are exposed; owner UUID and
        reply linkage never. Deleted/tombstoned messages are excluded. Bounded by limit + cursor."""
        _id(room_id)
        after, limit, now = _cursor(cursor, room_id), _limit(limit), self.clock()
        with self._db() as db:
            if self._open_room(db, room_id) is None:
                raise RoomError('room_unavailable')
            rows = db.execute(
                'SELECT id, seq, text, created_at FROM messages WHERE room_id=? AND seq>? AND expires_at>? '
                'AND deleted=0 ORDER BY seq LIMIT ?', (room_id, after, now, limit + 1)).fetchall()
        selected = list(rows[:limit])
        return {'room_id': room_id,
                'messages': [{'id': m['id'], 'text': m['text'], 'created_at': m['created_at']} for m in selected],
                'next_cursor': room_id + ':' + str(selected[-1]['seq'] if selected else after),
                'has_more': len(rows) > limit, 'retention': 'active_window_only',
                'ttl_ms': self.limits.ttl_ms, 'untrusted_content': True}

    def join(self, owner, room_id):
        with self._db(write=True) as db:
            self._room(db, room_id)
            if db.execute('SELECT 1 FROM members WHERE room_id=? AND owner=?', (room_id, owner)).fetchone():
                return {'joined': True, 'already_joined': True}
            self._actor(db, owner)
            self._join_capacity(db, owner)
            if db.execute('SELECT COUNT(*) FROM members WHERE room_id=?', (room_id,)).fetchone()[0] >= self.limits.members_per_room:
                raise RoomError('room_member_capacity')
            db.execute('INSERT INTO members VALUES (?,?)', (room_id, owner))
        return {'joined': True, 'already_joined': False}

    def leave(self, owner, room_id):
        with self._db(write=True) as db:
            if self._room(db, room_id)['owner'] == owner:
                raise RoomError('owner_must_close_room')
            db.execute('DELETE FROM members WHERE room_id=? AND owner=?', (room_id, owner))
        return {'left': True}

    def close(self, owner, room_id):
        with self._db(write=True) as db:
            if self._room(db, room_id)['owner'] != owner:
                raise RoomError('not_room_owner')
            db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
        return {'closed': True, 'history_deleted': True}

    def send(self, owner, room_id, text, client_message_id, reply_to=None):
        text = _text(text, self.limits.text)
        if not isinstance(client_message_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', client_message_id):
            raise RoomError('invalid_client_message_id')
        if reply_to is not None:
            _id(reply_to)
        digest = hashlib.sha256(json.dumps([text, reply_to], ensure_ascii=False).encode()).hexdigest()
        now = self.clock()
        with self._db(write=True) as db:
            self._member(db, room_id, owner)
            db.execute('DELETE FROM messages WHERE expires_at<=?', (now,))
            old = db.execute('SELECT * FROM messages WHERE room_id=? AND owner=? AND client_id=?', (room_id, owner, client_message_id)).fetchone()
            if old:
                if old['digest'] != digest:
                    raise RoomError('idempotency_conflict')
                return {'message': self._message(old), 'replayed': True}
            if reply_to and not db.execute('SELECT 1 FROM messages WHERE id=? AND room_id=? AND deleted=0', (reply_to, room_id)).fetchone():
                raise RoomError('reply_unavailable')
            last = db.execute('SELECT last_send FROM actors WHERE owner=?', (owner,)).fetchone()
            if not last:
                raise RoomError('invalid_principal')
            if last[0] is not None and now - last[0] < self.limits.cadence_ms:
                raise RoomError('rate_limited', retry_after_ms=self.limits.cadence_ms - (now - last[0]))
            if db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] >= self.limits.messages:
                raise RoomError('message_capacity')
            if db.execute('SELECT COUNT(*) FROM messages WHERE room_id=?', (room_id,)).fetchone()[0] >= self.limits.messages_per_room:
                raise RoomError('room_message_capacity')
            message_id = str(uuid.uuid4())
            db.execute('INSERT INTO messages(id,room_id,owner,text,digest,client_id,reply_to,created_at,expires_at) VALUES (?,?,?,?,?,?,?,?,?)',
                       (message_id, room_id, owner, text, digest, client_message_id, reply_to, now, now + self.limits.ttl_ms))
            db.execute('UPDATE actors SET last_send=? WHERE owner=?', (now, owner))
            row = db.execute('SELECT * FROM messages WHERE id=?', (message_id,)).fetchone()
        return {'message': self._message(row), 'replayed': False}

    def read(self, owner, room_id, cursor=None, limit=20):
        _id(room_id)
        after, limit, now = _cursor(cursor, room_id), _limit(limit), self.clock()
        with self._db() as db:
            self._member(db, room_id, owner)
            rows = db.execute('SELECT * FROM messages WHERE room_id=? AND seq>? AND expires_at>? ORDER BY seq LIMIT ?', (room_id, after, now, limit + 1)).fetchall()
        selected = rows[:limit]
        return {'messages': [self._message(row) for row in selected],
                'next_cursor': room_id + ':' + str(selected[-1]['seq'] if selected else after),
                'has_more': len(rows) > limit, 'history_complete': False, 'retention': 'active_window_only',
                'ttl_ms': self.limits.ttl_ms, 'durable': True, 'untrusted_content': True}

    def delete_message(self, owner, room_id, message_id):
        _id(message_id)
        with self._db(write=True) as db:
            self._member(db, room_id, owner)
            row = db.execute('SELECT * FROM messages WHERE room_id=? AND id=? AND owner=? AND expires_at>?', (room_id, message_id, owner, self.clock())).fetchone()
            if not row:
                raise RoomError('message_unavailable_or_not_yours')
            db.execute("UPDATE messages SET text='', deleted=1 WHERE id=?", (message_id,))
        return {'deleted': True, 'tombstone': True}
