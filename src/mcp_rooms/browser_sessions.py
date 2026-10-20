"""Private browser session core. No HTTP/cookies, login, registration or migrations on request.

Only a trusted adapter may supply Principal. Cookies are separate credentials with
short absolute/idle expiry and fresh parent authority checks, never MCP Bearers.
"""
from dataclasses import dataclass, field
from hashlib import sha256
import hmac
import json
import re
import secrets
import sqlite3
import uuid
from .domain import DomainError, Principal
from .identity import LISTING_SCOPES

AUDIENCE = 'mcp-rooms/browser/v1'
TOKEN = re.compile(r'bs1_([0-9a-f]{32})\.([A-Za-z0-9_-]{43})')
IDLE_MS = 900000
MAX_TTL_SECONDS = 3600
MAX_ROWS = 2048
MAX_OWNER_ROWS = 16
TABLES = {'browser_session_schema', 'browser_sessions'}


@dataclass(frozen=True)
class BrowserContext:
    principal: Principal
    session_id: str
    expires_at: int
    csrf_token: str = field(repr=False)


@dataclass(frozen=True)
class IssuedSession:
    context: BrowserContext
    cookie: str = field(repr=False)


def _csrf(raw):
    # One-way domain-separated value: same-origin bootstrap can return this without
    # revealing the HttpOnly cookie. HTTP Origin/CSRF policy remains adapter work.
    return hmac.new(raw.encode('ascii'), b'mcp-rooms/browser/csrf/v1', sha256).hexdigest()


def _scopes(values):
    if (type(values) not in (list, tuple, frozenset) or not values
            or any(type(s) is not str or s not in LISTING_SCOPES for s in values)
            or len(set(values)) != len(values)):
        raise DomainError('invalid_browser_scopes')
    return sorted(values)


class BrowserSessions:
    """Explicit additive schema, digest-only storage, bounded retained rows.

    Retired rows count toward lifetime caps until a separately reviewed cleanup.
    No default app wiring, implicit account issuance, background task or renewal.
    """
    def __init__(self, drafts):
        self.drafts, self.store, self.resource = drafts, drafts.store, drafts.resource

    def initialize(self):
        with self.store._db(write=True) as db:
            self.drafts._schema(db)
            found = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} & TABLES
            if found:
                self._schema(db)
                return
            db.execute('CREATE TABLE browser_session_schema(singleton INTEGER PRIMARY KEY CHECK(singleton=1),version INTEGER NOT NULL)')
            db.execute('''CREATE TABLE browser_sessions(
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                credential_id TEXT NOT NULL REFERENCES credentials(id),
                digest TEXT NOT NULL UNIQUE, resource TEXT NOT NULL, audience TEXT NOT NULL,
                scopes TEXT NOT NULL, created_at INTEGER NOT NULL,
                last_seen INTEGER NOT NULL, expires_at INTEGER NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)),
                CHECK(created_at<=last_seen AND last_seen<expires_at))''')
            db.execute('CREATE INDEX browser_sessions_owner ON browser_sessions(user_id)')
            db.execute('INSERT INTO browser_session_schema VALUES (1,1)')

    @staticmethod
    def _schema(db):
        try:
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} & TABLES
            rows = db.execute('SELECT singleton,version FROM browser_session_schema').fetchall()
        except sqlite3.OperationalError:
            raise DomainError('browser_migration_required') from None
        if names != TABLES or len(rows) != 1 or tuple(rows[0]) != (1, 1):
            raise DomainError('unsupported_browser_schema')

    def _now(self):
        now = self.store.clock()
        if type(now) is not int or not 0 <= now <= 2**63 - 1 - MAX_TTL_SECONDS*1000:
            raise DomainError('invalid_timestamp')
        return now

    def _authority(self, db, actor, scopes, now):
        for scope in scopes:
            self.drafts._authorize(db, actor, scope, now)
        row = db.execute('SELECT expires_at FROM credentials WHERE id=?', (actor.credential_id,)).fetchone()
        return row['expires_at']*1000

    def create(self, actor, *, scopes=('listings:read',), ttl_seconds=3600):
        selected = _scopes(scopes)
        if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= MAX_TTL_SECONDS:
            raise DomainError('invalid_browser_lifetime')
        with self.store._db(write=True) as db:
            self._schema(db)
            now = self._now()
            parent_expiry = self._authority(db, actor, selected, now)
            if db.execute('SELECT COUNT(*) FROM browser_sessions').fetchone()[0] >= MAX_ROWS:
                raise DomainError('browser_session_capacity')
            if db.execute('SELECT COUNT(*) FROM browser_sessions WHERE user_id=?', (actor.user_id,)).fetchone()[0] >= MAX_OWNER_ROWS:
                raise DomainError('browser_owner_session_capacity')
            sid = uuid.uuid4().hex
            raw = 'bs1_'+sid+'.'+secrets.token_urlsafe(32)
            expires = min(now+ttl_seconds*1000, parent_expiry)
            db.execute('''INSERT INTO browser_sessions
                (id,user_id,credential_id,digest,resource,audience,scopes,created_at,last_seen,expires_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)''', (sid,actor.user_id,actor.credential_id,
                sha256(raw.encode('ascii')).hexdigest(),self.resource,AUDIENCE,json.dumps(selected),now,now,expires))
            context = BrowserContext(Principal(actor.user_id,actor.credential_id,frozenset(selected)),sid,expires,_csrf(raw))
        return IssuedSession(context, raw)

    def _lookup(self, db, raw):
        match = TOKEN.fullmatch(raw) if type(raw) is str else None
        if not match:
            raise DomainError('browser_session_required')
        row = db.execute('SELECT * FROM browser_sessions WHERE id=?', (match.group(1),)).fetchone()
        digest = sha256(raw.encode('ascii')).hexdigest()
        matches = hmac.compare_digest(digest,row['digest'] if row else '0'*64)
        if not row or not matches or row['resource'] != self.resource or row['audience'] != AUDIENCE:
            raise DomainError('browser_session_required')
        return row

    @staticmethod
    def _require_csrf(raw, csrf_token):
        if (type(csrf_token) is not str or not re.fullmatch('[0-9a-f]{64}',csrf_token)
                or not hmac.compare_digest(_csrf(raw),csrf_token)):
            raise DomainError('browser_csrf_required')

    def resolve(self, raw, *, mutating=False, csrf_token=None):
        if type(mutating) is not bool:
            raise DomainError('invalid_browser_operation')
        # Updating idle activity and validating the parent are one transaction.
        with self.store._db(write=True) as db:
            self._schema(db)
            row = self._lookup(db,raw)
            now = self._now()
            if (row['revoked'] or now < row['last_seen'] or now < row['created_at']
                    or now >= row['expires_at'] or now >= row['last_seen']+IDLE_MS):
                raise DomainError('browser_session_required')
            try:
                selected = _scopes(json.loads(row['scopes']))
            except (TypeError, ValueError, DomainError):
                raise DomainError('browser_session_required') from None
            actor = Principal(row['user_id'],row['credential_id'],frozenset(selected))
            self._authority(db,actor,selected,now)
            if mutating:
                self._require_csrf(raw,csrf_token)
            db.execute('UPDATE browser_sessions SET last_seen=? WHERE id=?',(now,row['id']))
            return BrowserContext(actor,row['id'],row['expires_at'],_csrf(raw))

    def logout(self, raw, *, csrf_token):
        """Revoke this browser session only, even if parent already expired/revoked.

        Requires possession + CSRF; never revokes an MCP key or another session.
        """
        with self.store._db(write=True) as db:
            self._schema(db)
            row = self._lookup(db,raw)
            self._require_csrf(raw,csrf_token)
            db.execute('UPDATE browser_sessions SET revoked=1 WHERE id=?',(row['id'],))
        return {'ok':True,'revoked':True}
