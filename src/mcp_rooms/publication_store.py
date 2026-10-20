"""Opt-in transactional publication core. No HTTP/MCP route or credential issuance.

All public getters are INTERNAL adapter primitives, not an enabled web server.
Private editors are frozen while active; withdraw first, then edit and reconfirm.
"""
from hashlib import sha256
import json
import re
from .domain import DomainError, identifier
from .draft_store import _bounded_integer
from .preview_contract import canonical_json
from .publication_guard import PUBLICATION_TABLES, publication_schema, require_unpublished
from .publication_preview import PUBLICATION_SCHEMA, publication_preview, public_card


class PublicationStore:
    def __init__(self, photos):
        self.photos, self.stages = photos, photos.stages
        self.drafts, self.store, self.files = photos.drafts, photos.store, photos.files

    def initialize(self):
        """Explicit additive namespace, in the same private DB/snapshot."""
        with self.store._db(write=True) as db:
            self.drafts._schema(db)
            self.stages._schema(db)
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if names & PUBLICATION_TABLES:
                publication_schema(db)
                return
            db.execute('CREATE TABLE publication_schema(singleton INTEGER PRIMARY KEY CHECK(singleton=1),version INTEGER NOT NULL)')
            db.execute('''CREATE TABLE listing_publications(
                listing_id TEXT PRIMARY KEY REFERENCES market_drafts(id),
                user_id TEXT NOT NULL REFERENCES users(id),
                state TEXT NOT NULL CHECK(state IN ('active','withdrawn')),
                epoch INTEGER NOT NULL CHECK(epoch>0), revision INTEGER NOT NULL,
                source_hash TEXT NOT NULL, projection TEXT NOT NULL,
                updated_at INTEGER NOT NULL, expires_at INTEGER NOT NULL)''')
            db.execute('''CREATE TABLE publication_consents(
                user_id TEXT NOT NULL REFERENCES users(id), intent_id TEXT NOT NULL,
                listing_id TEXT NOT NULL REFERENCES market_drafts(id), revision INTEGER NOT NULL,
                epoch INTEGER NOT NULL CHECK(epoch>=0), digest TEXT NOT NULL,
                resource TEXT NOT NULL, schema TEXT NOT NULL, created_at INTEGER NOT NULL,
                valid_until INTEGER NOT NULL, consumed_at INTEGER,
                PRIMARY KEY(user_id,intent_id), CHECK(created_at<valid_until))''')
            db.execute('''CREATE TABLE publication_audit(
                id INTEGER PRIMARY KEY, listing_id TEXT NOT NULL REFERENCES market_drafts(id),
                user_id TEXT NOT NULL REFERENCES users(id), credential_id TEXT NOT NULL,
                client_id TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('publish','withdraw')),
                epoch INTEGER NOT NULL, created_at INTEGER NOT NULL,
                intent_id TEXT, preview_digest TEXT,
                CHECK((action='publish' AND intent_id IS NOT NULL AND preview_digest IS NOT NULL)
                   OR (action='withdraw' AND intent_id IS NULL AND preview_digest IS NULL)),
                UNIQUE(user_id,client_id))''')
            db.execute('INSERT INTO publication_schema VALUES (1,1)')

    def _base(self, db, actor, listing_id, scope):
        publication_schema(db)
        now, draft = self.photos._base(db, actor, listing_id, scope)
        require_unpublished(db, listing_id, now)
        row = db.execute('SELECT * FROM listing_publications WHERE listing_id=?', (listing_id,)).fetchone()
        if row and row['user_id'] != actor.user_id:
            raise DomainError('publication_unavailable')
        epoch = row['epoch'] if row else 0
        if epoch >= 2**63-1:
            raise DomainError('publication_revision_capacity')
        rows = self.photos._links(db, actor, draft)
        self.photos._live(rows, draft, now)
        return now, draft, rows, epoch

    def _document(self, db, draft, rows, epoch):
        private = self.photos._document(db, draft, rows)
        return publication_preview(private['record'], private['category_path'], self.drafts.resource,
                                   private['photos'], epoch)

    def preview(self, actor, listing_id):
        with self.files._guard():
            with self.store._db() as db:
                before = self._base(db, actor, listing_id, 'listings:read')
            self.photos._verify(before[2])
            with self.store._db() as db:
                now, draft, rows, epoch = self._base(db, actor, listing_id, 'listings:read')
                if (draft, rows, epoch) != before[1:]:
                    raise DomainError('preview_conflict')
                return self._document(db, draft, rows, epoch)

    def confirm(self, actor, listing_id, *, expected_revision, preview_digest, consent, client_id):
        if consent is not True:
            raise DomainError('publication_consent_required')
        identifier(client_id)
        _bounded_integer(expected_revision, 1, 2**63-1, 'invalid_revision')
        if type(preview_digest) is not str or not re.fullmatch('[0-9a-f]{64}', preview_digest):
            raise DomainError('invalid_preview_digest')
        payload = dict(id=listing_id, revision=expected_revision, digest=preview_digest,
                       schema=PUBLICATION_SCHEMA, resource=self.drafts.resource, consent=True)
        with self.files._guard():
            with self.store._db() as db:
                publication_schema(db)
                now = self.store.clock()
                self.drafts._authorize(db, actor, 'listings:publish', now)
                _, replay = self.drafts._retry(db, actor, client_id, 'live_publication_consent', payload)
                if replay is not None:
                    return {**replay, 'replayed':True}
                before = self._base(db, actor, listing_id, 'listings:publish')
                if before[1]['revision'] != expected_revision:
                    raise DomainError('revision_conflict')
            self.photos._verify(before[2])
            with self.store._db(write=True) as db:
                now, draft, rows, epoch = self._base(db, actor, listing_id, 'listings:publish')
                digest, replay = self.drafts._retry(db, actor, client_id, 'live_publication_consent', payload)
                if replay is not None:
                    return {**replay, 'replayed':True}
                if (draft, rows, epoch) != before[1:] or self._document(db, draft, rows, epoch)['digest'] != preview_digest:
                    raise DomainError('preview_conflict')
                result = dict(kind='live_publication_consent', schema=PUBLICATION_SCHEMA,
                    intent_id=client_id, listing_id=listing_id, revision=draft['revision'],
                    publication_epoch=epoch, preview_digest=preview_digest, resource=self.drafts.resource,
                    recorded_at=now, valid_until=min([now+300000,draft['expires_at']]+[r['expires_at'] for r in rows]),
                    published=False)
                db.execute('INSERT INTO publication_consents VALUES (?,?,?,?,?,?,?,?,?,?,NULL)',
                    (actor.user_id, client_id, listing_id, draft['revision'], epoch, preview_digest,
                     self.drafts.resource, PUBLICATION_SCHEMA, now, result['valid_until']))
                self.drafts._receipt(db, actor, client_id, 'live_publication_consent', digest, result, now)
                return {**result, 'replayed':False}

    def _consent(self, db, actor, listing_id, intent_id, draft, rows, epoch, now):
        row = db.execute('SELECT * FROM publication_consents WHERE user_id=? AND intent_id=?',
                         (actor.user_id, intent_id)).fetchone()
        if (not row or row['listing_id'] != listing_id or row['revision'] != draft['revision']
                or row['epoch'] != epoch or row['schema'] != PUBLICATION_SCHEMA
                or row['resource'] != self.drafts.resource or row['consumed_at'] is not None
                or not row['created_at'] <= now < row['valid_until']
                or row['digest'] != self._document(db, draft, rows, epoch)['digest']):
            raise DomainError('publication_consent_unavailable')
        return dict(row)

    def publish(self, actor, listing_id, *, intent_id, client_id):
        identifier(listing_id); identifier(intent_id); identifier(client_id)
        payload = dict(id=listing_id, intent_id=intent_id, resource=self.drafts.resource)
        with self.files._guard():
            with self.store._db() as db:
                publication_schema(db)
                self.drafts._authorize(db, actor, 'listings:publish', self.store.clock())
                _, replay = self.drafts._retry(db, actor, client_id, 'publish_listing', payload)
                if replay is not None:
                    return {**replay, 'replayed':True}
                before = self._base(db, actor, listing_id, 'listings:publish')
                self._consent(db, actor, listing_id, intent_id, before[1], before[2], before[3], before[0])
            self.photos._verify(before[2])
            with self.store._db(write=True) as db:
                now = self.store.clock()
                self.drafts._authorize(db, actor, 'listings:publish', now)
                digest, replay = self.drafts._retry(db, actor, client_id, 'publish_listing', payload)
                if replay is not None:
                    return {**replay, 'replayed':True}
                now, draft, rows, epoch = self._base(db, actor, listing_id, 'listings:publish')
                if (draft, rows, epoch) != before[1:]:
                    raise DomainError('preview_conflict')
                self._consent(db, actor, listing_id, intent_id, draft, rows, epoch, now)
                document = self._document(db, draft, rows, epoch)
                card = public_card(document['record'], document['category_path'], document['photos'], epoch+1, now)
                source_hash = sha256(canonical_json(document['record']).encode()).hexdigest()
                db.execute('''INSERT INTO listing_publications VALUES (?,?, 'active',?,?,?,?,?,?)
                    ON CONFLICT(listing_id) DO UPDATE SET state='active',epoch=excluded.epoch,
                    revision=excluded.revision,source_hash=excluded.source_hash,projection=excluded.projection,
                    updated_at=excluded.updated_at,expires_at=excluded.expires_at''',
                    (listing_id,actor.user_id,epoch+1,draft['revision'],source_hash,canonical_json(card),now,draft['expires_at']))
                used = db.execute('UPDATE publication_consents SET consumed_at=? WHERE user_id=? AND intent_id=? AND consumed_at IS NULL',
                                  (now,actor.user_id,intent_id))
                if used.rowcount != 1:
                    raise DomainError('publication_consent_unavailable')
                result = dict(listing_id=listing_id, publication_revision=epoch+1, state='active', published_at=now)
                self.drafts._receipt(db,actor,client_id,'publish_listing',digest,result,now)
                self._audit(db,actor,listing_id,client_id,'publish',epoch+1,now,
                            intent_id=intent_id,preview_digest=document['digest'])
                return {**result,'replayed':False}

    @staticmethod
    def _audit(db, actor, listing_id, client_id, action, epoch, now, *, intent_id=None, preview_digest=None):
        db.execute('INSERT INTO publication_audit(listing_id,user_id,credential_id,client_id,action,epoch,created_at,intent_id,preview_digest) VALUES (?,?,?,?,?,?,?,?,?)',
                   (listing_id,actor.user_id,actor.credential_id,client_id,action,epoch,now,intent_id,preview_digest))

    def withdraw(self, actor, listing_id, *, expected_publication_revision, client_id):
        identifier(listing_id); identifier(client_id)
        _bounded_integer(expected_publication_revision,1,2**63-2,'invalid_revision')
        payload = dict(id=listing_id, publication_revision=expected_publication_revision,resource=self.drafts.resource)
        with self.store._db(write=True) as db:
            publication_schema(db)
            now = self.store.clock()
            self.drafts._authorize(db,actor,'listings:publish',now)
            digest,replay = self.drafts._retry(db,actor,client_id,'withdraw_listing',payload)
            if replay is not None:
                return {**replay,'replayed':True}
            row = db.execute('SELECT * FROM listing_publications WHERE listing_id=? AND user_id=?', (listing_id,actor.user_id)).fetchone()
            if not row or row['state'] != 'active':
                raise DomainError('publication_unavailable')
            if row['epoch'] != expected_publication_revision:
                raise DomainError('revision_conflict')
            if now < row['updated_at']:
                raise DomainError('invalid_timestamp')
            db.execute("UPDATE listing_publications SET state='withdrawn',epoch=epoch+1,updated_at=? WHERE listing_id=?", (now,listing_id))
            result = dict(listing_id=listing_id,publication_revision=row['epoch']+1,state='withdrawn')
            self.drafts._receipt(db,actor,client_id,'withdraw_listing',digest,result,now)
            self._audit(db,actor,listing_id,client_id,'withdraw',row['epoch']+1,now)
            return {**result,'replayed':False}

    def _public_snapshot(self, db, listing_id):
        publication_schema(db)
        self.drafts._schema(db); self.stages._schema(db)
        now = self.store.clock()
        row = db.execute('SELECT p.* FROM listing_publications p JOIN users u ON u.id=p.user_id WHERE p.listing_id=? AND p.state=\'active\' AND u.disabled=0', (listing_id,)).fetchone()
        if not row or not row['updated_at'] <= now < row['expires_at']:
            raise DomainError('listing_unavailable')
        draft = self.drafts._owned(db,row['user_id'],listing_id,now)
        if draft['status'] != 'draft' or draft['revision'] != row['revision']:
            raise DomainError('listing_unavailable')
        record = json.loads(canonical_json(self.drafts._record(draft)))
        if sha256(canonical_json(record).encode()).hexdigest() != row['source_hash']:
            raise DomainError('listing_unavailable')
        self.drafts._category(db,draft['category_id'],record['listing']['content']['category'])
        # _links needs only user_id; never a synthetic Principal accepted for auth.
        from types import SimpleNamespace
        rows = self.photos._links(db,SimpleNamespace(user_id=row['user_id']),dict(draft))
        self.photos._live(rows,dict(draft),now)
        private = self.photos._document(db,dict(draft),rows)
        card = public_card(record,private['category_path'],private['photos'],row['epoch'],row['updated_at'])
        if canonical_json(card) != row['projection']:
            raise DomainError('listing_unavailable')
        return dict(row), rows, card

    def _read_public(self, listing_id, media_id=None, epoch=None):
        identifier(listing_id)
        if media_id is not None:
            identifier(media_id)
            _bounded_integer(epoch,1,2**63-1,'invalid_revision')
        with self.files._guard():
            try:
                with self.store._db() as db:
                    before = self._public_snapshot(db,listing_id)
                    if media_id is not None and before[0]['epoch'] != epoch:
                        raise DomainError('listing_unavailable')
                if media_id is None:
                    self.photos._verify(before[1])
                    result = before[2]
                else:
                    selected = next((r for r in before[1] if r['id'] == media_id),None)
                    if selected is None:
                        raise DomainError('listing_unavailable')
                    result = self.files._read_locked(self.stages._receipt(selected))
                with self.store._db() as db:
                    after = self._public_snapshot(db,listing_id)
                    if after != before:
                        raise DomainError('listing_unavailable')
                return result
            except DomainError:
                # Same result for private/missing/withdrawn/disabled/corrupt data.
                raise DomainError('listing_unavailable') from None

    def public_get(self, listing_id):
        """Allowlisted JSON DATA, not HTML; adapters must escape and use no-store."""
        return self._read_public(listing_id)

    def public_photo(self, listing_id, publication_revision, media_id):
        """No arbitrary path/key. Public availability is rechecked after file I/O."""
        return self._read_public(listing_id,media_id,publication_revision)
