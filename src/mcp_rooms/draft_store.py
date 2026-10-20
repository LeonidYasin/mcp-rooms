"""Opt-in private draft slice; NOT wired into MCP, HTTP or enrollment.

initialize() is an explicit additive migration on an existing standalone RoomStore.
IdentityStore does not issue listing scopes yet. Synthetic CI credentials exercise
this internal boundary; no public path may construct Principal from request fields.
Each transaction rechecks persisted actor/credential/resource/scopes before reads,
mutations AND retries. This does not verify a raw Bearer secret: adapters must use
an authenticating gate first. No live migrations, media claims or publication here.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import re
import uuid
from .domain import DomainError, Principal, identifier
from .identity import resource_url
from .listing_contract import Listing, ListingContent, create_draft

SCHEMA_VERSION = 1
TABLES = ('market_schema', 'market_categories', 'market_drafts', 'market_commands')
CATEGORIES = (
    ('things', None, 'things', 'Вещи'),
    ('home-repair', 'things', 'things', 'Дом и ремонт'),
    ('plumbing', 'home-repair', 'things', 'Сантехника'),
    ('toilets', 'plumbing', 'things', 'Унитазы'),
    ('services', None, 'services', 'Услуги'),
)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _bounded_integer(value, minimum, maximum, code):
    if type(value) is not int or not minimum <= value <= maximum:
        raise DomainError(code)
    return value


@dataclass(frozen=True)
class DraftLimits:
    total: int = 500
    per_owner: int = 25
    commands: int = 2000
    commands_per_owner: int = 100

    def __post_init__(self):
        for name in ('total', 'per_owner', 'commands', 'commands_per_owner'):
            _bounded_integer(getattr(self, name), 1, 10000, 'invalid_draft_limits')


class DraftStore:
    """Internal application/persistence boundary, no arbitrary SQL or path input."""
    def __init__(self, store, resource, limits=DraftLimits()):
        self.store, self.resource, self.limits = store, resource_url(resource), limits
        if not isinstance(limits, DraftLimits):
            raise DomainError('invalid_draft_limits')

    def initialize(self):
        """Explicit opt-in, additive namespace version; unchanged room user_version."""
        with self.store._db(write=True) as db:
            names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            existing = names.intersection(TABLES)
            if existing:
                if existing != set(TABLES):
                    raise DomainError('unsupported_market_schema')
                self._schema(db)
                return
            # New sidecar tables in the SAME DB/snapshot; no drop/rewrite of room data.
            db.execute('CREATE TABLE market_schema (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL)')
            db.execute('CREATE TABLE market_categories (id TEXT PRIMARY KEY, parent_id TEXT REFERENCES market_categories(id), root TEXT NOT NULL, title TEXT NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)))')
            db.execute('CREATE TABLE market_drafts (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), category_id TEXT NOT NULL REFERENCES market_categories(id), content TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0), created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, CHECK(created_at<=updated_at AND updated_at<expires_at))')
            db.execute('CREATE INDEX market_drafts_owner ON market_drafts(user_id)')
            db.execute('CREATE TABLE market_commands (user_id TEXT NOT NULL REFERENCES users(id), client_id TEXT NOT NULL, operation TEXT NOT NULL, digest TEXT NOT NULL, result TEXT NOT NULL, created_at INTEGER NOT NULL, PRIMARY KEY(user_id,client_id))')
            db.executemany('INSERT INTO market_categories VALUES (?,?,?,?,1)', CATEGORIES)
            db.execute('INSERT INTO market_schema VALUES (1,?)', (SCHEMA_VERSION,))

    @staticmethod
    def _schema(db):
        try:
            rows = db.execute('SELECT singleton,version FROM market_schema').fetchall()
        except Exception as exc:
            # Translate only absent/incompatible namespace, not arbitrary auth errors.
            import sqlite3
            if isinstance(exc, sqlite3.OperationalError):
                raise DomainError('market_migration_required') from None
            raise
        if len(rows) != 1 or rows[0]['singleton'] != 1 or rows[0]['version'] != SCHEMA_VERSION:
            raise DomainError('unsupported_market_schema')

    def _authorize(self, db, principal, scope, now):
        if (not isinstance(principal, Principal) or type(principal.scopes) is not frozenset
                or not isinstance(principal.credential_id, str)
                or not re.fullmatch('[0-9a-f]{32}', principal.credential_id)):
            raise DomainError('authentication_required')
        identifier(principal.user_id)
        row = db.execute('SELECT c.user_id,c.resource,c.scopes,c.expires_at,c.revoked,u.disabled FROM credentials c JOIN users u ON u.id=c.user_id WHERE c.id=?', (principal.credential_id,)).fetchone()
        if (not row or row['user_id'] != principal.user_id or row['resource'] != self.resource
                or row['disabled'] or row['revoked'] or row['expires_at'] <= now // 1000):
            raise DomainError('authentication_required')
        try:
            actual = json.loads(row['scopes'])
        except (ValueError, TypeError):
            raise DomainError('authentication_required') from None
        if not isinstance(actual, list) or not all(isinstance(x, str) for x in actual):
            raise DomainError('authentication_required')
        if scope not in principal.scopes or scope not in actual:
            raise DomainError('insufficient_scope')

    @staticmethod
    def _category(db, category_id, root=None):
        if not isinstance(category_id, str) or not re.fullmatch('[a-z][a-z0-9-]{0,63}', category_id):
            raise DomainError('invalid_category')
        row = db.execute('SELECT * FROM market_categories WHERE id=?', (category_id,)).fetchone()
        if not row or not row['active'] or (root is not None and row['root'] != root):
            raise DomainError('category_unavailable')
        # Check bounded ancestry as well, so disabling a parent disables descendants.
        seen = set()
        while row:
            if row['id'] in seen or len(seen) >= 8 or not row['active']:
                raise DomainError('category_unavailable')
            seen.add(row['id'])
            if row['parent_id'] is None:
                return category_id
            row = db.execute('SELECT * FROM market_categories WHERE id=?', (row['parent_id'],)).fetchone()
            if row is None:
                raise DomainError('category_unavailable')
        raise DomainError('category_unavailable')

    @staticmethod
    def _content(content):
        if not isinstance(content, ListingContent):
            raise DomainError('invalid_content')
        # Media service has not been implemented; never claim arbitrary references.
        if content.media_ids:
            raise DomainError('media_not_available')
        return asdict(content)

    @staticmethod
    def _record(row):
        c = json.loads(row['content'])
        c['modes'], c['media_ids'] = tuple(c['modes']), tuple(c['media_ids'])
        listing = Listing(row['id'], 'user:' + row['user_id'], ListingContent(**c),
                          'draft', 'private', row['revision'], row['created_at'],
                          row['updated_at'], row['expires_at'])
        return {'listing': asdict(listing), 'category_id': row['category_id']}

    @staticmethod
    def _owned(db, user_id, listing_id, now):
        identifier(listing_id)
        row = db.execute('SELECT * FROM market_drafts WHERE id=? AND user_id=?', (listing_id, user_id)).fetchone()
        if not row or row['expires_at'] <= now:
            raise DomainError('draft_unavailable')
        return row

    def _retry(self, db, principal, client_id, operation, payload):
        identifier(client_id)
        digest = hashlib.sha256(_json(payload).encode('utf-8')).hexdigest()
        row = db.execute('SELECT * FROM market_commands WHERE user_id=? AND client_id=?', (principal.user_id, client_id)).fetchone()
        if row:
            if row['operation'] != operation or row['digest'] != digest:
                raise DomainError('idempotency_conflict')
            return digest, json.loads(row['result'])
        if db.execute('SELECT COUNT(*) FROM market_commands').fetchone()[0] >= self.limits.commands:
            raise DomainError('market_command_capacity')
        if db.execute('SELECT COUNT(*) FROM market_commands WHERE user_id=?', (principal.user_id,)).fetchone()[0] >= self.limits.commands_per_owner:
            raise DomainError('owner_command_capacity')
        return digest, None

    @staticmethod
    def _receipt(db, principal, client_id, operation, digest, result, now):
        db.execute('INSERT INTO market_commands VALUES (?,?,?,?,?,?)',
                   (principal.user_id, client_id, operation, digest, _json(result), now))

    def create(self, principal, content, *, category_id, client_id):
        payload = {'content': self._content(content), 'category_id': category_id}
        with self.store._db(write=True) as db:
            self._schema(db)
            now = self.store.clock()
            self._authorize(db, principal, 'listings:write', now)
            digest, replay = self._retry(db, principal, client_id, 'create', payload)
            if replay is not None:
                return {**replay, 'replayed': True}
            self._category(db, category_id, content.category)
            if db.execute('SELECT COUNT(*) FROM market_drafts').fetchone()[0] >= self.limits.total:
                raise DomainError('draft_capacity')
            if db.execute('SELECT COUNT(*) FROM market_drafts WHERE user_id=?', (principal.user_id,)).fetchone()[0] >= self.limits.per_owner:
                raise DomainError('owner_draft_capacity')
            listing = create_draft(principal, str(uuid.uuid4()), content, now)
            db.execute('INSERT INTO market_drafts VALUES (?,?,?,?,?,?,?,?)',
                       (listing.id, principal.user_id, category_id, _json(payload['content']),
                        listing.revision, now, now, listing.expires_at))
            result = self._record(self._owned(db, principal.user_id, listing.id, now))
            # Wire-neutral canonical receipt (JSON tuples become arrays consistently).
            result = json.loads(_json(result))
            self._receipt(db, principal, client_id, 'create', digest, result, now)
            return {**result, 'replayed': False}

    def update(self, principal, listing_id, content, *, category_id, expected_revision, client_id):
        identifier(listing_id)
        _bounded_integer(expected_revision, 1, 2**63-2, 'invalid_revision')
        payload = {'id': listing_id, 'content': self._content(content),
                   'category_id': category_id, 'expected_revision': expected_revision}
        with self.store._db(write=True) as db:
            self._schema(db)
            now = self.store.clock()
            self._authorize(db, principal, 'listings:write', now)
            digest, replay = self._retry(db, principal, client_id, 'update', payload)
            if replay is not None:
                return {**replay, 'replayed': True}
            row = self._owned(db, principal.user_id, listing_id, now)
            if row['revision'] != expected_revision:
                raise DomainError('revision_conflict')
            if now < row['updated_at']:
                raise DomainError('invalid_timestamp')
            self._category(db, category_id, content.category)
            result = db.execute('UPDATE market_drafts SET content=?,category_id=?,revision=revision+1,updated_at=? WHERE id=? AND user_id=? AND revision=?',
                                (_json(payload['content']), category_id, now, listing_id, principal.user_id, expected_revision))
            if result.rowcount != 1:
                raise DomainError('revision_conflict')
            result = json.loads(_json(self._record(self._owned(db, principal.user_id, listing_id, now))))
            self._receipt(db, principal, client_id, 'update', digest, result, now)
            return {**result, 'replayed': False}

    def get(self, principal, listing_id):
        with self.store._db() as db:
            self._schema(db)
            now = self.store.clock()
            self._authorize(db, principal, 'listings:read', now)
            return json.loads(_json(self._record(self._owned(db, principal.user_id, listing_id, now))))
