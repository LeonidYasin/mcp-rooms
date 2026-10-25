"""Private responses R-01 between listing owner and another agent.

A new explicit namespace separate from PUBLICATION_TABLES; no startup migration.
Content is untrusted data, never instructions. Only the listing owner and the
response author see response bodies; the public web exposes only a bounded
per-response status label picked by the owner (allowlist) plus a count.
"""
import json
import uuid
from hashlib import sha256
from .domain import DomainError, identifier
from .draft_store import _bounded_integer
from .publication_guard import publication_schema
from .preview_contract import canonical_json

MAX_RESPONSE_TEXT = 4000
RESPONSE_PUBLIC_STATUS = frozenset({'opened', 'answered', 'closed', 'agreed', 'declined'})
RESPONSE_TABLES = frozenset({'response_schema', 'listing_responses', 'response_messages'})


def response_schema(db, *, required=True):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    found = names & RESPONSE_TABLES
    if not found and not required:
        return False
    if found != RESPONSE_TABLES:
        raise DomainError('unsupported_response_schema')
    rows = db.execute('SELECT singleton,version FROM response_schema').fetchall()
    if len(rows) != 1 or tuple(rows[0]) != (1, 2):
        raise DomainError('unsupported_response_schema')
    return True


class ResponseStore:
    def __init__(self, drafts, publisher):
        self.drafts, self.store = drafts, drafts.store
        self.publisher, self.files = publisher, publisher.files

    def initialize(self):
        with self.store._db(write=True) as db:
            self.drafts._schema(db)
            if response_schema(db, required=False):
                return
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if names & RESPONSE_TABLES:
                # Explicit owner-approval upgrade of an existing response namespace (v1 -> v2):
                # add the threaded-messages table and bump the version. Never a startup action.
                row = db.execute('SELECT version FROM response_schema WHERE singleton=1').fetchone()
                if not row or row['version'] != 1:
                    raise DomainError('unsupported_response_schema')
                db.execute('''CREATE TABLE response_messages(
                    id TEXT PRIMARY KEY,
                    response_id TEXT NOT NULL REFERENCES listing_responses(id) ON DELETE CASCADE,
                    author_user_id TEXT NOT NULL REFERENCES users(id),
                    marker INTEGER NOT NULL DEFAULT 0, text TEXT NOT NULL,
                    client_id TEXT NOT NULL, created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    UNIQUE(response_id,author_user_id,client_id))''')
                db.execute('UPDATE response_schema SET version=2 WHERE singleton=1')
                return
            db.execute('CREATE TABLE response_schema(singleton INTEGER PRIMARY KEY CHECK(singleton=1),version INTEGER NOT NULL)')
            db.execute('''CREATE TABLE listing_responses(
                id TEXT PRIMARY KEY,
                listing_id TEXT NOT NULL REFERENCES market_drafts(id),
                author_user_id TEXT NOT NULL REFERENCES users(id),
                owner_user_id TEXT NOT NULL REFERENCES users(id),
                status TEXT NOT NULL CHECK(status IN ('active','withdrawn')),
                text TEXT NOT NULL, digest TEXT NOT NULL,
                public_status TEXT,
                publication_revision INTEGER NOT NULL CHECK(publication_revision>0),
                client_id TEXT NOT NULL, updated_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL,
                CHECK((status='active' AND public_status IN (
                       'opened','answered','closed','agreed','declined')) OR status='withdrawn'),
                UNIQUE(listing_id,author_user_id))''')
            db.execute('''CREATE TABLE response_messages(
                id TEXT PRIMARY KEY,
                response_id TEXT NOT NULL REFERENCES listing_responses(id) ON DELETE CASCADE,
                author_user_id TEXT NOT NULL REFERENCES users(id),
                marker INTEGER NOT NULL DEFAULT 0, text TEXT NOT NULL,
                client_id TEXT NOT NULL, created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                UNIQUE(response_id,author_user_id,client_id))''')
            db.execute('INSERT INTO response_schema VALUES (1,2)')

    def _check_publication(self, db, listing_id, now):
        publication_schema(db)
        row = db.execute('SELECT user_id,epoch,expires_at FROM listing_publications '
                         'WHERE listing_id=? AND state=\'active\'', (listing_id,)).fetchone()
        if not row or not (now < row['expires_at']):
            raise DomainError('listing_unavailable')
        owner = db.execute('SELECT display_name FROM users WHERE id=? AND disabled=0',
                           (row['user_id'],)).fetchone()
        if owner is None:
            raise DomainError('listing_unavailable')
        return row

    def _retry(self, db, principal, client_id, operation, payload):
        return self.drafts._retry(db, principal, client_id, operation, payload)

    def _receipt(self, db, principal, client_id, operation, digest, result, now):
        self.drafts._receipt(db, principal, client_id, operation, digest, result, now)

    def respond(self, principal, listing_id, text, client_id):
        identifier(listing_id)
        identifier(client_id)
        if type(text) is not str or not 1 <= len(text) <= MAX_RESPONSE_TEXT:
            raise DomainError('invalid_response_text')
        payload = {'id': listing_id, 'text': text}
        digest = sha256(canonical_json(payload).encode()).hexdigest()
        with self.store._db(write=True) as db:
            response_schema(db)
            self.drafts._schema(db)
            now = self.store.clock()
            self.drafts._authorize(db, principal, 'listings:write', now)
            _, replay = self._retry(db, principal, client_id, 'respond', payload)
            if replay is not None:
                return {**replay, 'replayed': True}
            published = self._check_publication(db, listing_id, now)
            if published['user_id'] == principal.user_id:
                raise DomainError('cannot_respond_own_listing')
            existing = db.execute('SELECT id FROM listing_responses WHERE listing_id=? AND author_user_id=? AND status=\'active\'',
                                  (listing_id, principal.user_id)).fetchone()
            if existing:
                raise DomainError('response_already_exists')
            if db.execute('SELECT COUNT(*) FROM listing_responses '
                          'WHERE listing_id=? AND status=\'active\'', (listing_id,)).fetchone()[0] >= 500:
                raise DomainError('response_capacity')
            response_id = str(uuid.uuid4())
            expires = min(now + 86400000, published['expires_at'])
            db.execute('INSERT INTO listing_responses '
                       '(id,listing_id,author_user_id,owner_user_id,status,text,digest,public_status,'
                       'publication_revision,client_id,updated_at,expires_at,created_at) '
                       'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (response_id, listing_id, principal.user_id, published['user_id'],
                        'active', text, digest, 'opened', published['epoch'],
                        client_id, now, expires, now))
            result = {'id': response_id, 'listing_id': listing_id, 'status': 'active',
                      'public_status': 'opened', 'publication_revision': published['epoch'],
                      'created_at': now, 'expires_at': expires}
            self._receipt(db, principal, client_id, 'respond', digest, result, now)
            return {**result, 'replayed': False}

    def responses(self, principal, listing_id):
        identifier(listing_id)
        with self.store._db() as db:
            response_schema(db)
            self.drafts._schema(db)
            now = self.store.clock()
            self.drafts._authorize(db, principal, 'listings:read', now)
            self.drafts._owned(db, principal.user_id, listing_id, now)
            rows = db.execute('SELECT id,status,public_status,publication_revision,created_at,updated_at,text '
                              'FROM listing_responses WHERE listing_id=? AND owner_user_id=? AND status=\'active\' '
                              'ORDER BY created_at LIMIT 1000', (listing_id, principal.user_id)).fetchall()
            return {'listing_id': listing_id, 'responses': [dict(r) for r in rows]}

    def my_responses(self, principal, cursor=None, limit=20):
        _bounded_integer(limit, 1, 100, 'invalid_limit')
        with self.store._db() as db:
            response_schema(db)
            now = self.store.clock()
            self.drafts._authorize(db, principal, 'listings:read', now)
            rows = db.execute('SELECT id,listing_id,status,public_status,publication_revision,created_at,updated_at,text '
                              'FROM listing_responses WHERE author_user_id=? AND status=\'active\' '
                              'ORDER BY created_at DESC LIMIT ?', (principal.user_id, limit)).fetchall()
            return {'responses': [dict(r) for r in rows]}

    def respond_status(self, principal, listing_id, response_id, public_status, client_id):
        identifier(listing_id)
        identifier(response_id)
        identifier(client_id)
        if public_status not in RESPONSE_PUBLIC_STATUS:
            raise DomainError('invalid_public_status')
        payload = {'id': listing_id, 'response': response_id, 'public_status': public_status}
        digest = sha256(canonical_json(payload).encode()).hexdigest()
        with self.store._db(write=True) as db:
            response_schema(db)
            now = self.store.clock()
            self.drafts._authorize(db, principal, 'listings:write', now)
            self.drafts._owned(db, principal.user_id, listing_id, now)
            _, replay = self._retry(db, principal, client_id, 'respond_status', payload)
            if replay is not None:
                return {**replay, 'replayed': True}
            row = db.execute('SELECT * FROM listing_responses WHERE id=? AND listing_id=? AND owner_user_id=?',
                             (response_id, listing_id, principal.user_id)).fetchone()
            if not row or row['status'] != 'active' or not row['expires_at'] > now:
                raise DomainError('response_unavailable')
            db.execute('UPDATE listing_responses SET public_status=?,updated_at=? WHERE id=?',
                       (public_status, now, response_id))
            result = {'id': response_id, 'listing_id': listing_id,
                      'public_status': public_status, 'updated_at': now}
            self._receipt(db, principal, client_id, 'respond_status', digest, result, now)
            return {**result, 'replayed': False}

    def _participant(self, db, response_id, principal, now):
        identifier(response_id)
        row = db.execute('SELECT * FROM listing_responses WHERE id=?', (response_id,)).fetchone()
        if (not row or row['status'] != 'active' or not row['expires_at'] > now
                or row['author_user_id'] != principal.user_id and row['owner_user_id'] != principal.user_id):
            raise DomainError('response_unavailable')
        return row

    def reply(self, principal, response_id, text, client_id):
        identifier(response_id)
        identifier(client_id)
        if type(text) is not str or not 1 <= len(text) <= MAX_RESPONSE_TEXT:
            raise DomainError('invalid_response_text')
        payload = {'response': response_id, 'text': text}
        digest = sha256(canonical_json(payload).encode()).hexdigest()
        with self.store._db(write=True) as db:
            response_schema(db)
            now = self.store.clock()
            self.drafts._authorize(db, principal, 'listings:write', now)
            row = self._participant(db, response_id, principal, now)
            _, replay = self._retry(db, principal, client_id, 'reply', payload)
            if replay is not None:
                return {**replay, 'replayed': True}
            if db.execute('SELECT COUNT(*) FROM response_messages WHERE response_id=?',
                          (response_id,)).fetchone()[0] >= 2000:
                raise DomainError('thread_capacity')
            message_id = str(uuid.uuid4())
            db.execute('INSERT INTO response_messages '
                       '(id,response_id,author_user_id,text,client_id,created_at,expires_at) '
                       'VALUES (?,?,?,?,?,?,?)',
                       (message_id, response_id, principal.user_id, text, client_id, now,
                        min(now + 86400000, row['expires_at'])))
            db.execute('UPDATE listing_responses SET updated_at=? WHERE id=?', (now, response_id))
            result = {'id': message_id, 'response_id': response_id, 'created_at': now}
            self._receipt(db, principal, client_id, 'reply', digest, result, now)
            return {**result, 'replayed': False}

    def thread(self, principal, response_id, cursor=None, limit=50):
        identifier(response_id)
        _bounded_integer(limit, 1, 200, 'invalid_limit')
        with self.store._db() as db:
            response_schema(db)
            now = self.store.clock()
            self.drafts._authorize(db, principal, 'listings:read', now)
            self._participant(db, response_id, principal, now)
            rows = db.execute('SELECT id,author_user_id,text,created_at '
                              'FROM response_messages WHERE response_id=? '
                              'ORDER BY created_at,rowid LIMIT ?',
                              (response_id, limit)).fetchall()
            return {'response_id': response_id, 'messages': [dict(r) for r in rows]}

    def public_response_summary(self, listing_id):
        """Read-only public count + owner-chosen status labels; never authors/text."""
        identifier(listing_id)
        with self.store._db() as db:
            publication_schema(db)
            if not response_schema(db, required=False):
                raise DomainError('listing_unavailable')
            now = self.store.clock()
            published = self._check_publication(db, listing_id, now)
            rows = db.execute('SELECT public_status FROM listing_responses '
                              'WHERE listing_id=? AND owner_user_id=? AND status=\'active\'',
                              (listing_id, published['user_id'])).fetchall()
        counts = {}
        for (label,) in rows:
            counts[label] = counts.get(label, 0) + 1
        return {'listing_id': listing_id, 'count': len(rows),
                'labels': [{'label': k, 'count': counts[k]} for k in sorted(counts)]}