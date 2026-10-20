"""Synthetic owner-bound photo editing; never public publication or a live DB."""
from dataclasses import replace
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from mcp_rooms.photo_drafts import PhotoDraftStore
from mcp_rooms.photo_preview import PHOTO_PREVIEW_SCHEMA
from mcp_rooms.domain import DomainError
from mcp_rooms.media_cleanup import MediaCleanup, GRACE_MS
from mcp_rooms.media_stage import TTL_MS
from test_media_stage import env, setup, upload, rows, fails, key
from test_draft_store import create, content
from test_publication_intent import publisher


@pytest.fixture
def photos(env):
    x = env
    x.a = publisher(x.store, x.a)
    x.editor = PhotoDraftStore(x.service)
    return x


def attach(x, ids, revision=1, client=None, actor=None):
    return x.editor.set_photos(actor or x.a, x.draft_id, tuple(ids), expected_revision=revision, client_id=client or key())


def intent(x, preview, client=None):
    return x.editor.confirm_intent(x.a, x.draft_id, expected_revision=preview['record']['listing']['revision'],
                                  preview_digest=preview['digest'], client_id=client or key())


def test_attach_is_atomic_versioned_and_readable(photos):
    x = photos
    media = upload(x)
    result = attach(x, [media['media_id']])
    listing = result['listing']
    assert listing['revision'] == 2 and listing['content']['media_ids'] == [media['media_id']]
    assert listing['visibility'] == 'private' and listing['status'] == 'draft'
    row = rows(x)[0]
    assert row['revision'] == 2 and row['expires_at'] == listing['expires_at'] > media['expires_at']
    assert x.service.read(x.a, media['media_id']).startswith(b'\xff\xd8\xff')
    assert x.drafts.get(x.a, x.draft_id)['listing'] == listing
    assert len(list(x.root.iterdir())) == 1 and x.worker.calls == 1
    with x.store._db() as db:
        assert db.execute('SELECT version FROM media_stage_schema').fetchone()[0] == 3
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_replay_no_version_or_retention_extension(photos):
    x = photos
    media = upload(x)
    client = key()
    first = attach(x, [media['media_id']], client=client)
    x.now[0] += 1
    assert attach(x, [media['media_id']], client=client) == {**first, 'replayed': True}
    assert x.drafts.get(x.a, x.draft_id)['listing']['revision'] == 2
    assert rows(x)[0]['expires_at'] == first['listing']['expires_at']
    fails('idempotency_conflict', lambda: attach(x, [], revision=1, client=client))


def test_reorder_changes_preview_and_invalidates_photo_intent(photos):
    x = photos
    first, second = upload(x), upload(x, payload=b'different-original')
    ids = [first['media_id'], second['media_id']]
    attach(x, ids)
    before = x.editor.preview(x.a, x.draft_id)
    consent = intent(x, before)
    assert x.editor.get_intent(x.a, x.draft_id, consent['intent_id'])['published'] is False
    attach(x, list(reversed(ids)), revision=2)
    after = x.editor.preview(x.a, x.draft_id)
    assert after['digest'] != before['digest']
    assert [p['media_id'] for p in after['photos']] == list(reversed(ids))
    fails('publication_intent_unavailable', lambda: x.editor.get_intent(x.a, x.draft_id, consent['intent_id']))
    fails('revision_conflict', lambda: intent(x, before))


def test_private_photo_preview_never_means_publication(photos):
    x = photos
    media = upload(x)
    attach(x, [media['media_id']])
    preview = x.editor.preview(x.a, x.draft_id)
    assert preview['schema'] == PHOTO_PREVIEW_SCHEMA
    assert preview['private_photos_verified'] is True
    assert preview['publication_enabled'] is False and preview['media_ready'] is False
    assert preview['photos'][0]['sha256'] == media['sha256']
    assert '.jpg' not in json.dumps(preview) and 'blob_key' not in json.dumps(preview)
    assert 'credential_id' not in json.dumps(preview)
    consent = intent(x, preview)
    assert consent['published'] is False
    assert consent['valid_until'] == x.now[0]+300000
    assert x.drafts.get(x.a, x.draft_id)['listing']['status'] == 'draft'


def test_legacy_preview_and_editor_refuse_photo_unaware_writes(photos):
    x = photos
    old = x.drafts.preview(x.a, x.draft_id)
    previous = x.drafts.confirm_publication_intent(x.a, x.draft_id, expected_revision=1,
        preview_digest=old['digest'], client_id=key())
    media = upload(x)
    attach(x, [media['media_id']])
    fails('photo_preview_required', lambda: x.drafts.preview(x.a, x.draft_id))
    fails('photo_preview_required', lambda: x.drafts.confirm_publication_intent(x.a, x.draft_id,
        expected_revision=2, preview_digest=old['digest'], client_id=key()))
    fails('publication_intent_unavailable', lambda: x.drafts.get_publication_intent(x.a, x.draft_id, previous['intent_id']))
    fails('photo_editor_required', lambda: x.drafts.update(x.a, x.draft_id, content(title='Wrong editor'),
        category_id='toilets', expected_revision=2, client_id=key()))
    assert x.drafts.get(x.a, x.draft_id)['listing']['revision'] == 2


def test_photo_aware_text_edit_preserves_order_and_rebinds_revision(photos):
    x = photos
    media = upload(x)
    attach(x, [media['media_id']])
    consent = intent(x, x.editor.preview(x.a, x.draft_id))
    result = x.editor.update_content(x.a, x.draft_id, content(title='Уточнённый текст'),
        category_id='toilets', expected_revision=2, client_id=key())
    assert result['listing']['revision'] == 3
    assert result['listing']['content']['media_ids'] == [media['media_id']]
    assert result['listing']['content']['title'] == 'Уточнённый текст'
    assert x.service.read(x.a, media['media_id'])
    fails('publication_intent_unavailable', lambda: x.editor.get_intent(x.a, x.draft_id, consent['intent_id']))


@pytest.mark.parametrize('kind', ['foreign-user','other-draft','expired','purged','wrong-resource','stale-source'])
def test_unusable_media_cannot_attach(photos, kind):
    x = photos
    media = upload(x)
    actor = x.a
    expected = 'media_unavailable'
    if kind == 'foreign-user':
        actor = x.b
        expected = 'draft_unavailable'
    elif kind == 'other-draft':
        other = create(x.drafts, x.a)['listing']['id']
        with x.store._db(write=True) as db:
            db.execute('UPDATE media_stages SET draft_id=? WHERE id=?', (other, media['media_id']))
    elif kind == 'expired':
        x.now[0] = media['expires_at']
    elif kind == 'purged':
        x.now[0] = media['expires_at'] + GRACE_MS
        cleanup = MediaCleanup(x.service)
        cleanup.apply(cleanup.plan())
    elif kind == 'wrong-resource':
        with x.store._db(write=True) as db:
            db.execute("UPDATE media_stages SET resource='https://wrong.example/mcp' WHERE id=?", (media['media_id'],))
    else:
        with x.store._db(write=True) as db:
            db.execute('UPDATE media_stages SET revision=0 WHERE id=?', (media['media_id'],))
        expected = 'photo_manifest_conflict'
    fails(expected, lambda: attach(x, [media['media_id']], actor=actor))
    assert x.drafts.get(x.a, x.draft_id)['listing']['revision'] == 1


@pytest.mark.parametrize('value,code', [([], 'invalid_media'), (('bad',), 'invalid_id'),
    (tuple('x' for _ in range(9)), 'invalid_media')])
def test_invalid_photo_list(photos, value, code):
    x = photos
    fails(code, lambda: x.editor.set_photos(x.a, x.draft_id, value, expected_revision=1, client_id=key()))


def test_duplicates_and_stale_draft_revision(photos):
    x = photos
    media = upload(x)
    fails('duplicate_media', lambda: attach(x, [media['media_id']]*2))
    fails('revision_conflict', lambda: attach(x, [media['media_id']], revision=99))


def test_detach_can_remove_corrupt_photo_without_serving_it(photos):
    x = photos
    media = upload(x)
    attach(x, [media['media_id']])
    next(x.root.iterdir()).write_bytes(b'corrupt')
    fails('media_storage_integrity', lambda: x.editor.preview(x.a, x.draft_id))
    result = attach(x, [], revision=2)
    assert result['listing']['content']['media_ids'] == [] and result['photos'] == []
    assert rows(x)[0]['expires_at'] == x.now[0]+TTL_MS
    assert x.editor.preview(x.a, x.draft_id)['photos'] == []


def test_detach_and_reattach_within_explicit_staging_grace(photos):
    x = photos
    media = upload(x)
    attach(x, [media['media_id']])
    attach(x, [], revision=2)
    assert rows(x)[0]['revision'] == 3
    attach(x, [media['media_id']], revision=3)
    assert x.drafts.get(x.a, x.draft_id)['listing']['revision'] == 4


def test_active_attachment_survives_original_upload_ttl_cleanup(photos):
    x = photos
    media = upload(x)
    attach(x, [media['media_id']])
    x.now[0] = media['expires_at']+GRACE_MS
    cleanup = MediaCleanup(x.service)
    assert cleanup.plan()['candidates'] == []
    cleanup.apply(cleanup.plan())
    assert x.editor.preview(x.a, x.draft_id)['photos'] and len(list(x.root.iterdir())) == 1
    attach(x, [], revision=2)
    x.now[0] += TTL_MS+GRACE_MS
    cleanup.apply(cleanup.plan())
    assert rows(x)[0]['cleanup_state'] == 'purged' and not list(x.root.iterdir())


@pytest.mark.parametrize('operation', ['attach','preview','intent'])
def test_revocation_during_file_verification_rechecked(photos, monkeypatch, operation):
    x = photos
    media = upload(x)
    if operation != 'attach':
        attach(x, [media['media_id']])
    preview = x.editor.preview(x.a, x.draft_id) if operation == 'intent' else None
    read = x.files._read_locked
    def revoke(receipt):
        data = read(receipt)
        x.auth.revoke(x.a.credential_id)
        return data
    monkeypatch.setattr(x.files, '_read_locked', revoke)
    if operation == 'attach':
        action = lambda: attach(x, [media['media_id']])
    elif operation == 'preview':
        action = lambda: x.editor.preview(x.a, x.draft_id)
    else:
        action = lambda: intent(x, preview)
    fails('authentication_required', action)
    with x.store._db() as db:
        assert db.execute("SELECT COUNT(*) FROM market_commands WHERE operation='photo_publication_intent'").fetchone()[0] == 0
        if operation == 'attach':
            assert db.execute('SELECT COUNT(*) FROM media_draft_photos').fetchone()[0] == 0


def test_tampered_dual_manifest_fails_closed(photos):
    x = photos
    media = upload(x)
    attach(x, [media['media_id']])
    with x.store._db(write=True) as db:
        db.execute('DELETE FROM media_draft_photos')
    fails('photo_manifest_conflict', lambda: x.editor.preview(x.a, x.draft_id))


def test_receipt_capacity_failure_rolls_back_entire_attachment(photos):
    x = photos
    media = upload(x)
    x.drafts.limits = replace(x.drafts.limits, commands_per_owner=1)
    fails('owner_command_capacity', lambda: attach(x, [media['media_id']]))
    assert rows(x)[0]['revision'] == 1
    assert x.drafts.get(x.a, x.draft_id)['listing']['revision'] == 1
    with x.store._db() as db:
        assert db.execute('SELECT COUNT(*) FROM media_draft_photos').fetchone()[0] == 0


def test_intent_scope_and_expiry_replay_not_live_authority(photos):
    x = photos
    media = upload(x)
    attach(x, [media['media_id']])
    preview = x.editor.preview(x.a, x.draft_id)
    weak = replace(x.a, scopes=frozenset({'listings:read','listings:write'}))
    fails('insufficient_scope', lambda: x.editor.confirm_intent(weak, x.draft_id, expected_revision=2,
        preview_digest=preview['digest'], client_id=key()))
    client = key()
    first = intent(x, preview, client)
    x.now[0] = first['valid_until']
    assert intent(x, preview, client) == {**first, 'replayed': True}
    fails('publication_intent_unavailable', lambda: x.editor.get_intent(x.a, x.draft_id, first['intent_id']))


def test_simultaneous_photo_writes_one_revision_wins(photos):
    x = photos
    media = upload(x)
    barrier = threading.Barrier(2)
    def mutate(_):
        barrier.wait()
        try:
            return attach(x, [media['media_id']])
        except DomainError as e:
            return e.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(mutate, [1,2]))
    assert sum(isinstance(r, dict) for r in results) == 1
    assert results.count('revision_conflict') == 1
    assert x.drafts.get(x.a, x.draft_id)['listing']['revision'] == 2


def test_bad_preview_digest_no_intent(photos):
    x = photos
    media = upload(x)
    attach(x, [media['media_id']])
    preview = x.editor.preview(x.a, x.draft_id)
    altered = {**preview, 'digest':'0'*64}
    fails('preview_conflict', lambda: intent(x, altered))
    with x.store._db() as db:
        assert not db.execute("SELECT 1 FROM market_commands WHERE operation='photo_publication_intent'").fetchone()


def test_eight_photos_fit_candidate_owner_budget(photos):
    x = photos
    ids = [upload(x, payload=('synthetic-'+str(i)).encode())['media_id'] for i in range(8)]
    result = attach(x, ids)
    assert result['listing']['content']['media_ids'] == ids and len(result['photos']) == 8
    assert [p['media_id'] for p in x.editor.preview(x.a, x.draft_id)['photos']] == ids


def test_foreign_preview_and_intent_cannot_read_private_photo_draft(photos):
    x = photos
    media = upload(x)
    attach(x, [media['media_id']])
    preview = x.editor.preview(x.a, x.draft_id)
    consent = intent(x, preview)
    fails('draft_unavailable', lambda: x.editor.preview(x.b, x.draft_id))
    b = publisher(x.store, x.b)
    fails('draft_unavailable', lambda: x.editor.get_intent(b, x.draft_id, consent['intent_id']))


def legacy_v2(x):
    """Synthetic predecessor schema; never run against a live database."""
    with x.store._db(write=True) as db:
        db.execute('DROP TABLE media_draft_photos')
        db.execute('UPDATE media_stage_schema SET version=2')


def test_explicit_v2_migration_preserves_media_and_room_identifiers(photos):
    x = photos
    media = upload(x)
    before = rows(x)
    with x.store._db() as db:
        room_ids = tuple(db.execute('PRAGMA '+q).fetchone()[0] for q in ('application_id','user_version'))
    legacy_v2(x)
    fails('unsupported_media_schema', lambda: x.editor.preview(x.a, x.draft_id))
    x.service.initialize()
    x.service.initialize()
    assert rows(x) == before and x.service.read(x.a, media['media_id'])
    with x.store._db() as db:
        assert db.execute('SELECT version FROM media_stage_schema').fetchone()[0] == 3
        assert not db.execute('SELECT * FROM media_draft_photos').fetchall()
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        assert tuple(db.execute('PRAGMA '+q).fetchone()[0] for q in ('application_id','user_version')) == room_ids
    assert attach(x, [media['media_id']])['listing']['revision'] == 2


def test_v2_link_creation_failure_rolls_back_schema(photos, monkeypatch):
    x = photos
    upload(x)
    before = rows(x)
    legacy_v2(x)
    original = x.service._create_photo_links
    def fail_after_create(db):
        original(db)
        raise RuntimeError('synthetic post-DDL migration fault')
    with monkeypatch.context() as patch:
        patch.setattr(x.service, '_create_photo_links', fail_after_create)
        with pytest.raises(RuntimeError):
            x.service.initialize()
    assert rows(x) == before
    with x.store._db() as db:
        assert db.execute('SELECT version FROM media_stage_schema').fetchone()[0] == 2
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='media_draft_photos'").fetchone()
    x.service.initialize()
    assert x.editor.preview(x.a, x.draft_id)['photos'] == []


def test_partial_v3_schema_is_not_silently_recreated(photos):
    x = photos
    with x.store._db(write=True) as db:
        db.execute('DROP TABLE media_draft_photos')
    fails('unsupported_media_schema', x.service.initialize)
    with x.store._db() as db:
        assert db.execute('SELECT version FROM media_stage_schema').fetchone()[0] == 3
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='media_draft_photos'").fetchone()
