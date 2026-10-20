"""Opt-in owner-authorized private staging. No transport, attach or publication.

Principal must come from an authenticating adapter, never request JSON. Listing
scopes are not issued by current enrollment. All slow work is outside SQLite tx.
"""
from hashlib import sha256
import json
import sqlite3
import uuid
from .domain import DomainError, identifier
from .draft_store import _bounded_integer
from .media_contract import MAX_INPUT_BYTES, MAX_OUTPUT_BYTES
from .preview_contract import canonical_json

POLICY = 'jpeg-normalizer-v1'
TTL_MS = 600000
MAX_ROWS = 128
MAX_OWNER_ROWS = 16
MAX_BYTES = 32 * 1024 * 1024
MAX_OWNER_BYTES = 16 * 1024 * 1024
MAX_RECEIPTS = 512
MAX_OWNER_RECEIPTS = 128
_BASE_TABLES = {'media_stage_schema', 'media_stages'}
_TABLES = _BASE_TABLES | {'media_draft_photos'}


class MediaStageStore:
    """Internal service. Inject one trusted file store and reused decode worker.

    Expired/failed rows keep quota until explicit reviewed maintenance. Purged
    tombstones retain idempotency receipts; their separate lifetime cap is bounded.
    """
    def __init__(self, drafts, files, worker):
        self.drafts, self.store = drafts, drafts.store
        self.files, self.worker = files, worker

    def initialize(self):
        with self.store._db(write=True) as db:
            self.drafts._schema(db)
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            found = names & _TABLES
            if found:
                if not _BASE_TABLES <= found:
                    raise DomainError('unsupported_media_schema')
                version = self._schema(db, allow_legacy=True)
                if found != (_BASE_TABLES if version < 3 else _TABLES):
                    raise DomainError('unsupported_media_schema')
                if version == 1:
                    db.execute("ALTER TABLE media_stages ADD COLUMN cleanup_state TEXT NOT NULL DEFAULT 'live' CHECK(cleanup_state IN ('live','purging','purged'))")
                    db.execute('ALTER TABLE media_stages ADD COLUMN cleanup_started_at INTEGER')
                    db.execute('ALTER TABLE media_stages ADD COLUMN purged_at INTEGER')
                if version < 3:
                    self._create_photo_links(db)
                    db.execute('UPDATE media_stage_schema SET version=3 WHERE singleton=1')
                return
            db.execute('CREATE TABLE media_stage_schema(singleton INTEGER PRIMARY KEY CHECK(singleton=1),version INTEGER NOT NULL)')
            db.execute('''CREATE TABLE media_stages(
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                draft_id TEXT NOT NULL REFERENCES market_drafts(id), revision INTEGER NOT NULL,
                client_id TEXT NOT NULL, digest TEXT NOT NULL, resource TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('reserved','staged','failed')),
                reserved_bytes INTEGER NOT NULL CHECK(reserved_bytes>0),
                created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
                policy TEXT NOT NULL, blob_key TEXT, sha256 TEXT, byte_size INTEGER,
                width INTEGER, height INTEGER,
                cleanup_state TEXT NOT NULL DEFAULT 'live' CHECK(cleanup_state IN ('live','purging','purged')),
                cleanup_started_at INTEGER, purged_at INTEGER,
                UNIQUE(user_id,client_id), CHECK(created_at<expires_at),
                CHECK(state!='staged' OR (blob_key IS NOT NULL AND sha256 IS NOT NULL
                    AND byte_size>0 AND width>0 AND height>0)))''')
            db.execute('CREATE INDEX media_stages_owner ON media_stages(user_id)')
            self._create_photo_links(db)
            db.execute('INSERT INTO media_stage_schema VALUES (1,3)')

    @staticmethod
    def _create_photo_links(db):
        db.execute('''CREATE TABLE media_draft_photos(
            draft_id TEXT NOT NULL REFERENCES market_drafts(id),
            position INTEGER NOT NULL CHECK(position>=0 AND position<8),
            media_id TEXT NOT NULL UNIQUE REFERENCES media_stages(id),
            PRIMARY KEY(draft_id,position))''')

    @staticmethod
    def _schema(db, *, allow_legacy=False):
        try:
            rows = db.execute('SELECT singleton,version FROM media_stage_schema').fetchall()
        except sqlite3.OperationalError:
            raise DomainError('media_migration_required') from None
        if (len(rows) != 1 or rows[0][0] != 1
                or rows[0][1] not in ((1, 2, 3) if allow_legacy else (3,))):
            raise DomainError('unsupported_media_schema')
        return rows[0][1]

    def _gate(self, db, actor, draft_id, revision, scope):
        self.drafts._schema(db)
        self._schema(db)
        now = self.store.clock()
        self.drafts._authorize(db, actor, scope, now)
        draft = self.drafts._owned(db, actor.user_id, draft_id, now)
        if draft['status'] != 'draft':
            raise DomainError('draft_not_editable')
        if draft['revision'] != revision:
            raise DomainError('revision_conflict')
        if now < draft['updated_at']:
            raise DomainError('invalid_timestamp')
        self.drafts._category(db, draft['category_id'])
        return now, draft

    def _live(self, row, now):
        if now < row['created_at']:
            raise DomainError('invalid_timestamp')
        if (row['cleanup_state'] != 'live' or row['expires_at'] <= now or row['policy'] != POLICY
                or row['resource'] != self.drafts.resource):
            raise DomainError('media_unavailable')
        if row['state'] == 'reserved':
            raise DomainError('media_upload_pending')
        if row['state'] != 'staged':
            raise DomainError('media_processing_failed')

    @staticmethod
    def _public(row, replayed=False):
        # Public-safe shape only; still internal API, never expose the blob key.
        return dict(media_id=row['id'], draft_id=row['draft_id'], revision=row['revision'],
                    sha256=row['sha256'], byte_size=row['byte_size'], width=row['width'],
                    height=row['height'], content_type='image/jpeg', policy=row['policy'],
                    expires_at=row['expires_at'], state='staged', visibility='private',
                    replayed=replayed)

    @staticmethod
    def _receipt(row):
        from .media_files import StoredDerivative
        return StoredDerivative(row['blob_key'], row['sha256'], row['byte_size'],
                                row['width'], row['height'])

    def _reserve(self, actor, draft_id, revision, client_id, digest):
        with self.store._db(write=True) as db:
            now, draft = self._gate(db, actor, draft_id, revision, 'listings:write')
            row = db.execute('SELECT * FROM media_stages WHERE user_id=? AND client_id=?',
                             (actor.user_id, client_id)).fetchone()
            if row:
                if row['digest'] != digest:
                    raise DomainError('idempotency_conflict')
                self._live(row, now)
                return dict(row), True
            total_receipts = db.execute('SELECT COUNT(*) FROM media_stages').fetchone()[0]
            owner_receipts = db.execute('SELECT COUNT(*) FROM media_stages WHERE user_id=?', (actor.user_id,)).fetchone()[0]
            if total_receipts >= MAX_RECEIPTS or owner_receipts >= MAX_OWNER_RECEIPTS:
                raise DomainError('media_receipt_capacity')
            for owner, count_cap, bytes_cap in ((None, MAX_ROWS, MAX_BYTES),
                                               (actor.user_id, MAX_OWNER_ROWS, MAX_OWNER_BYTES)):
                where, params = (" WHERE cleanup_state!='purged'", ()) if owner is None else (" WHERE cleanup_state!='purged' AND user_id=?", (owner,))
                count, used = db.execute('SELECT COUNT(*),COALESCE(SUM(reserved_bytes),0) FROM media_stages'+where, params).fetchone()
                if count >= count_cap or used + MAX_OUTPUT_BYTES > bytes_cap:
                    raise DomainError('media_admission_capacity')
            media_id = str(uuid.uuid4())
            expires = min(now + TTL_MS, draft['expires_at'])
            db.execute('''INSERT INTO media_stages(id,user_id,draft_id,revision,client_id,digest,resource,state,
                reserved_bytes,created_at,expires_at,policy) VALUES (?,?,?,?,?,?,?,'reserved',?,?,?,?)''',
                (media_id, actor.user_id, draft_id, revision, client_id, digest, self.drafts.resource,
                 MAX_OUTPUT_BYTES, now, expires, POLICY))
            return dict(db.execute('SELECT * FROM media_stages WHERE id=?', (media_id,)).fetchone()), False

    def _failed(self, media_id, receipt):
        # Internal terminal transition of the already-authorized reservation only.
        # Never release budget here: files/DB are not a single transaction.
        try:
            with self.store._db(write=True) as db:
                self._schema(db)
                if receipt is None:
                    db.execute("UPDATE media_stages SET state='failed' WHERE id=? AND state='reserved' AND cleanup_state='live'", (media_id,))
                else:
                    db.execute("UPDATE media_stages SET state='failed',blob_key=?,sha256=?,byte_size=?,width=?,height=? WHERE id=? AND state='reserved' AND cleanup_state='live'",
                               (receipt.blob_key, receipt.sha256, receipt.byte_size,
                                receipt.width, receipt.height, media_id))
        except (sqlite3.Error, DomainError):
            # A crash/error can leave RESERVED; no implicit retry or budget release.
            pass

    def stage(self, actor, draft_id, *, expected_revision, client_id, payload, declared_type):
        identifier(draft_id)
        identifier(client_id)
        _bounded_integer(expected_revision, 1, 2**63-2, 'invalid_revision')
        if type(payload) is not bytes or not payload:
            raise DomainError('media_invalid_bytes')
        if len(payload) > MAX_INPUT_BYTES:
            raise DomainError('media_input_too_large')
        if type(declared_type) is not str or declared_type not in ('image/png', 'image/jpeg'):
            raise DomainError('media_type_not_allowed')
        digest = sha256(canonical_json(dict(draft_id=draft_id, revision=expected_revision,
            input_sha256=sha256(payload).hexdigest(), length=len(payload), mime=declared_type,
            policy=POLICY, resource=self.drafts.resource)).encode()).hexdigest()
        row, replay = self._reserve(actor, draft_id, expected_revision, client_id, digest)
        if replay:
            # Re-read committed bytes with fresh persisted authorization, not a stale receipt.
            self._read(actor, row['id'], 'listings:write')
            return self._public(row, True)
        receipt = None
        try:
            normalized = self.worker.normalize(payload, declared_type)
            # Lock order is ROOT -> short DB transaction. Cleanup takes the same
            # guard, so an expired in-flight decode can never write after purge.
            with self.files._guard():
                try:
                    with self.store._db() as db:
                        now, _ = self._gate(db, actor, draft_id, expected_revision, 'listings:write')
                        self._reservation(db, row['id'], actor.user_id, digest, now)
                    receipt = self.files._put_locked(normalized)
                    with self.store._db(write=True) as db:
                        now, _ = self._gate(db, actor, draft_id, expected_revision, 'listings:write')
                        self._reservation(db, row['id'], actor.user_id, digest, now)
                        db.execute("UPDATE media_stages SET state='staged',blob_key=?,sha256=?,byte_size=?,width=?,height=? WHERE id=? AND state='reserved' AND cleanup_state='live'",
                                   (receipt.blob_key, receipt.sha256, receipt.byte_size,
                                    receipt.width, receipt.height, row['id']))
                        result = dict(db.execute('SELECT * FROM media_stages WHERE id=?', (row['id'],)).fetchone())
                except Exception:
                    # Persist a known failed derivative before releasing the root
                    # lock. An actual crash can still leave an orphan for review.
                    self._failed(row['id'], receipt)
                    raise
            return self._public(result)
        except Exception:
            if receipt is None:
                self._failed(row['id'], None)
            raise

    def _reservation(self, db, media_id, user_id, digest, now):
        row = db.execute('SELECT * FROM media_stages WHERE id=? AND user_id=?', (media_id, user_id)).fetchone()
        if row and now < row['created_at']:
            raise DomainError('invalid_timestamp')
        if (not row or row['state'] != 'reserved' or row['cleanup_state'] != 'live'
                or row['expires_at'] <= now or row['digest'] != digest
                or row['policy'] != POLICY or row['resource'] != self.drafts.resource):
            raise DomainError('media_unavailable')

    def read(self, actor, media_id):
        """Internal authenticated read; no HTTP headers, public serving or attachment."""
        return self._read(actor, media_id, 'listings:read')

    def _read(self, actor, media_id, _scope):
        identifier(media_id)
        if _scope not in ('listings:read', 'listings:write'):
            raise DomainError('insufficient_scope')
        with self.store._db() as db:
            self.drafts._schema(db)
            self._schema(db)
            self.drafts._authorize(db, actor, _scope, self.store.clock())
            row = db.execute('SELECT * FROM media_stages WHERE id=? AND user_id=?', (media_id, actor.user_id)).fetchone()
            if not row:
                raise DomainError('media_unavailable')
            now, _ = self._gate(db, actor, row['draft_id'], row['revision'], _scope)
            self._live(row, now)
            row = dict(row)
        data = self.files.read(self._receipt(row))
        # Revocation/expiry/archive during filesystem I/O must not return the bytes.
        with self.store._db() as db:
            now, _ = self._gate(db, actor, row['draft_id'], row['revision'], _scope)
            fresh = db.execute('SELECT * FROM media_stages WHERE id=? AND user_id=?', (media_id, actor.user_id)).fetchone()
            if not fresh or dict(fresh) != row:
                raise DomainError('media_unavailable')
            self._live(fresh, now)
        return data
