"""Opt-in photo-aware private editing/preview/intent; no transport or publication."""
import json
import re
from .domain import DomainError, identifier
from .draft_store import _bounded_integer
from .media_stage import POLICY, TTL_MS
from .photo_preview import PHOTO_PREVIEW_SCHEMA, make_photo_preview
from .preview_contract import canonical_json
from .publication_guard import require_unpublished


class PhotoDraftStore:
    def __init__(self, stages):
        self.stages, self.drafts = stages, stages.drafts
        self.store, self.files = stages.store, stages.files

    def _base(self, db, actor, listing_id, scope):
        self.drafts._schema(db)
        self.stages._schema(db)
        now = self.store.clock()
        self.drafts._authorize(db, actor, scope, now)
        row = self.drafts._owned(db, actor.user_id, listing_id, now)
        if row['status'] != 'draft':
            raise DomainError('draft_not_editable')
        if now < row['updated_at']:
            raise DomainError('invalid_timestamp')
        self.drafts._category(db, row['category_id'], json.loads(row['content'])['category'])
        return now, dict(row)

    def _links(self, db, actor, row):
        links = db.execute('SELECT position,media_id FROM media_draft_photos WHERE draft_id=? ORDER BY position', (row['id'],)).fetchall()
        ids = [link['media_id'] for link in links]
        if len(ids) > 8 or [link['position'] for link in links] != list(range(len(ids))):
            raise DomainError('photo_manifest_conflict')
        if json.loads(row['content']).get('media_ids') != ids:
            raise DomainError('photo_manifest_conflict')
        return self._media(db, actor, row, ids)

    def _media(self, db, actor, draft, ids):
        result = []
        for media_id in ids:
            row = db.execute('SELECT * FROM media_stages WHERE id=? AND user_id=?', (media_id, actor.user_id)).fetchone()
            if (not row or row['draft_id'] != draft['id'] or row['resource'] != self.drafts.resource
                    or row['state'] != 'staged'):
                raise DomainError('media_unavailable')
            result.append(dict(row))
        return result

    def _live(self, rows, draft, now):
        for row in rows:
            self.stages._live(row, now)
            if row['revision'] != draft['revision'] or row['expires_at'] > draft['expires_at']:
                raise DomainError('photo_manifest_conflict')
            if row['policy'] != POLICY:
                raise DomainError('media_unavailable')

    def _verify(self, rows):
        # Caller holds root guard. No SQLite transaction spans checksum I/O.
        for row in rows:
            self.files._read_locked(self.stages._receipt(row))

    @staticmethod
    def _photos(rows):
        return [dict(media_id=r['id'], sha256=r['sha256'], width=r['width'], height=r['height'],
                     byte_size=r['byte_size'], content_type='image/jpeg', policy=r['policy'],
                     expires_at=r['expires_at']) for r in rows]

    def _document(self, db, draft, rows):
        path, category_id = [], draft['category_id']
        while category_id is not None:
            row = db.execute('SELECT * FROM topics WHERE id=?', (category_id,)).fetchone()
            if row is None:
                raise DomainError('category_unavailable')
            path.append({field: row[field] for field in ('id', 'parent_id', 'root', 'title')})
            if row['id'] == row['root']:
                break
            category_id = row['parent_id']
        record = json.loads(canonical_json(self.drafts._record(draft)))
        return make_photo_preview(record, list(reversed(path)), self.drafts.resource, self._photos(rows))

    @staticmethod
    def _ids(value):
        if type(value) is not tuple or len(value) > 8:
            raise DomainError('invalid_media')
        for item in value:
            identifier(item)
        if len(set(value)) != len(value):
            raise DomainError('duplicate_media')
        return value

    def set_photos(self, actor, listing_id, media_ids, *, expected_revision, client_id):
        ids = self._ids(media_ids)
        payload = dict(id=listing_id, media_ids=list(ids), expected_revision=expected_revision,
                       resource=self.drafts.resource)
        return self._mutate(actor, listing_id, expected_revision, client_id,
                            'set_photos', payload, ids, None, None)

    def update_content(self, actor, listing_id, content, *, category_id, expected_revision, client_id):
        # IDs can only be changed through set_photos, not hidden in content JSON.
        plain = self.drafts._content(content)
        payload = dict(id=listing_id, content=plain, category_id=category_id,
                       expected_revision=expected_revision, resource=self.drafts.resource)
        return self._mutate(actor, listing_id, expected_revision, client_id,
                            'photo_update_content', payload, None, plain, category_id)

    def _mutate(self, actor, listing_id, revision, client_id, operation, payload, ids, plain, category_id):
        identifier(listing_id)
        identifier(client_id)
        _bounded_integer(revision, 1, 2**63-2, 'invalid_revision')
        with self.files._guard():
            with self.store._db() as db:
                now, draft = self._base(db, actor, listing_id, 'listings:write')
                _, replay = self.drafts._retry(db, actor, client_id, operation, payload)
                if replay is not None:
                    return {**replay, 'replayed': True}  # historical receipt, not current intent
                require_unpublished(db, listing_id, now)
                if draft['revision'] != revision:
                    raise DomainError('revision_conflict')
                old = self._links(db, actor, draft)
                target = self._media(db, actor, draft, ids) if ids is not None else old
                self._live(target, draft, now)
                if plain is not None:
                    self.drafts._category(db, category_id, plain['category'])
            self._verify(target)
            with self.store._db(write=True) as db:
                now, fresh = self._base(db, actor, listing_id, 'listings:write')
                digest, replay = self.drafts._retry(db, actor, client_id, operation, payload)
                if replay is not None:
                    return {**replay, 'replayed': True}
                require_unpublished(db, listing_id, now)
                if fresh != draft or self._links(db, actor, fresh) != old:
                    raise DomainError('revision_conflict')
                current = self._media(db, actor, fresh, [r['id'] for r in target])
                if current != target:
                    raise DomainError('photo_manifest_conflict')
                self._live(current, fresh, now)
                next_content = json.loads(fresh['content']) if plain is None else dict(plain)
                next_content['media_ids'] = [r['id'] for r in target]
                category = fresh['category_id'] if category_id is None else category_id
                self.drafts._category(db, category, next_content['category'])
                changed = db.execute("UPDATE market_drafts SET content=?,category_id=?,revision=revision+1,updated_at=? WHERE id=? AND user_id=? AND revision=? AND status='draft'",
                    (canonical_json(next_content), category, now, listing_id, actor.user_id, revision))
                if changed.rowcount != 1:
                    raise DomainError('revision_conflict')
                db.execute('DELETE FROM media_draft_photos WHERE draft_id=?', (listing_id,))
                for position, row in enumerate(target):
                    db.execute('INSERT INTO media_draft_photos VALUES (?,?,?)', (listing_id, position, row['id']))
                    # Explicit first attachment promotes retention to the fixed
                    # draft deadline; retries do not keep extending this deadline.
                    db.execute('UPDATE media_stages SET revision=?,expires_at=? WHERE id=?',
                               (revision+1, fresh['expires_at'], row['id']))
                removed = {r['id'] for r in old} - {r['id'] for r in target}
                for media_id in removed:
                    db.execute("UPDATE media_stages SET revision=?,expires_at=MIN(expires_at,?) WHERE id=? AND cleanup_state='live'",
                               (revision+1, now+TTL_MS, media_id))
                saved = dict(self.drafts._owned(db, actor.user_id, listing_id, now))
                photos = self._links(db, actor, saved)
                result = {**json.loads(canonical_json(self.drafts._record(saved))),
                          'photos': self._photos(photos)}
                self.drafts._receipt(db, actor, client_id, operation, digest, result, now)
            return {**result, 'replayed': False}

    def preview(self, actor, listing_id):
        with self.files._guard():
            with self.store._db() as db:
                now, draft = self._base(db, actor, listing_id, 'listings:read')
                rows = self._links(db, actor, draft)
                self._live(rows, draft, now)
            self._verify(rows)
            with self.store._db() as db:
                now, fresh = self._base(db, actor, listing_id, 'listings:read')
                current = self._links(db, actor, fresh)
                if draft != fresh or rows != current:
                    raise DomainError('preview_conflict')
                self._live(current, fresh, now)
                return self._document(db, fresh, current)

    def confirm_intent(self, actor, listing_id, *, expected_revision, preview_digest, client_id):
        identifier(client_id)
        _bounded_integer(expected_revision, 1, 2**63-1, 'invalid_revision')
        if type(preview_digest) is not str or not re.fullmatch('[0-9a-f]{64}', preview_digest):
            raise DomainError('invalid_preview_digest')
        payload = dict(id=listing_id, revision=expected_revision, preview_digest=preview_digest,
                       schema=PHOTO_PREVIEW_SCHEMA, resource=self.drafts.resource)
        with self.files._guard():
            with self.store._db() as db:
                now, draft = self._base(db, actor, listing_id, 'listings:publish')
                _, replay = self.drafts._retry(db, actor, client_id, 'photo_publication_intent', payload)
                if replay is not None:
                    return {**replay, 'replayed': True}
                if draft['revision'] != expected_revision:
                    raise DomainError('revision_conflict')
                rows = self._links(db, actor, draft)
                self._live(rows, draft, now)
            self._verify(rows)
            with self.store._db(write=True) as db:
                now, fresh = self._base(db, actor, listing_id, 'listings:publish')
                digest, replay = self.drafts._retry(db, actor, client_id, 'photo_publication_intent', payload)
                if replay is not None:
                    return {**replay, 'replayed': True}
                current = self._links(db, actor, fresh)
                if fresh != draft or rows != current:
                    raise DomainError('preview_conflict')
                self._live(current, fresh, now)
                document = self._document(db, fresh, current)
                if document['digest'] != preview_digest:
                    raise DomainError('preview_conflict')
                result = dict(kind='private_photo_intent', schema=PHOTO_PREVIEW_SCHEMA,
                    resource=self.drafts.resource, intent_id=client_id, listing_id=listing_id,
                    revision=fresh['revision'], preview_digest=preview_digest, recorded_at=now,
                    valid_until=min([now+300000, fresh['expires_at']]+[r['expires_at'] for r in rows]),
                    published=False)
                self.drafts._receipt(db, actor, client_id, 'photo_publication_intent', digest, result, now)
                return {**result, 'replayed': False}

    def get_intent(self, actor, listing_id, intent_id):
        identifier(intent_id)
        with self.files._guard():
            with self.store._db() as db:
                now, draft = self._base(db, actor, listing_id, 'listings:publish')
                receipt = db.execute("SELECT result FROM market_commands WHERE user_id=? AND client_id=? AND operation='photo_publication_intent'", (actor.user_id, intent_id)).fetchone()
                if not receipt:
                    raise DomainError('publication_intent_unavailable')
                intent = json.loads(receipt['result'])
                rows = self._links(db, actor, draft)
                self._live(rows, draft, now)
            self._verify(rows)
            with self.store._db() as db:
                now, fresh = self._base(db, actor, listing_id, 'listings:publish')
                current = self._links(db, actor, fresh)
                self._live(current, fresh, now)
                if (fresh != draft or current != rows or intent.get('kind') != 'private_photo_intent'
                        or intent.get('schema') != PHOTO_PREVIEW_SCHEMA
                        or intent.get('resource') != self.drafts.resource or intent.get('intent_id') != intent_id
                        or intent.get('listing_id') != listing_id or intent.get('revision') != fresh['revision']
                        or not intent['recorded_at'] <= now < intent['valid_until']
                        or intent.get('preview_digest') != self._document(db, fresh, current)['digest']):
                    raise DomainError('publication_intent_unavailable')
                return intent
