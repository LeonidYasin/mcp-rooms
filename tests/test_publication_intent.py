"""Private preview/intent contracts only. No publication, media or live keys."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import sqlite3
import threading
import pytest
from mcp_rooms.domain import DomainError
from mcp_rooms.preview_contract import canonical_json, PREVIEW_SCHEMA
from test_draft_store import setup, create, content, counts, key


def publisher(store, principal):
    scopes = principal.scopes | {'listings:publish'}
    with store._db(write=True) as db:
        db.execute('UPDATE credentials SET scopes=? WHERE id=?',
                   (json.dumps(sorted(scopes)), principal.credential_id))
    return replace(principal, scopes=frozenset(scopes))


def confirm(drafts, actor, listing_id, preview, client_id=None):
    return drafts.confirm_publication_intent(actor, listing_id,
        expected_revision=preview['record']['listing']['revision'],
        preview_digest=preview['digest'], client_id=client_id or key())


def test_preview_exact_data_digest_is_stable_and_not_html(setup):
    store, auth, drafts, a, b, now = setup
    first = drafts.create(a, content(description='<script>untrusted</script>'), category_id='toilets', client_id=key())['listing']
    preview = drafts.preview(a, first['id'])
    assert preview == drafts.preview(a, first['id'])
    assert preview['record']['listing'] == first
    assert [x['id'] for x in preview['category_path']] == ['things', 'home-repair', 'plumbing', 'toilets']
    assert preview['media_ready'] is False and preview['publication_enabled'] is False
    document = {k: v for k, v in preview.items() if k != 'digest'}
    assert preview['digest'] == hashlib.sha256((PREVIEW_SCHEMA+'\0'+canonical_json(document)).encode('utf-8')).hexdigest()
    assert preview['record']['listing']['content']['description'] == '<script>untrusted</script>'
    assert 'credential_id' not in canonical_json(preview)


def test_private_intent_preserves_draft_and_expires(setup):
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    first = create(drafts, a)['listing']
    result = confirm(drafts, a, first['id'], drafts.preview(a, first['id']))
    assert result['published'] is False and result['kind'] == 'publication_intent'
    assert result['valid_until'] == now[0] + 300000
    assert drafts.get_publication_intent(a, first['id'], result['intent_id']) == {k: v for k, v in result.items() if k != 'replayed'}
    assert drafts.get(a, first['id'])['listing'] == first
    assert counts(store) == (1, 2)
    now[0] = result['valid_until']
    with pytest.raises(DomainError, match='publication_intent_unavailable'):
        drafts.get_publication_intent(a, first['id'], result['intent_id'])


def test_replay_does_not_extend_deadline_or_refresh_approval(setup):
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    lid = create(drafts, a)['listing']['id']
    preview, client = drafts.preview(a, lid), key()
    first = confirm(drafts, a, lid, preview, client)
    now[0] += 300000
    replay = confirm(drafts, a, lid, preview, client)
    assert replay == {**first, 'replayed': True}
    with pytest.raises(DomainError, match='publication_intent_unavailable'):
        drafts.get_publication_intent(a, lid, client)
    assert counts(store) == (1, 2)


def test_publish_scope_is_separate_in_snapshot_and_persisted_policy(setup):
    store, auth, drafts, a, b, now = setup
    lid = create(drafts, a)['listing']['id']
    preview = drafts.preview(a, lid)
    with pytest.raises(DomainError, match='insufficient_scope'):
        confirm(drafts, a, lid, preview)
    with pytest.raises(DomainError, match='insufficient_scope'):
        confirm(drafts, replace(a, scopes=a.scopes | {'listings:publish'}), lid, preview)
    a = publisher(store, a)
    with pytest.raises(DomainError, match='insufficient_scope'):
        confirm(drafts, replace(a, scopes=frozenset({'listings:read'})), lid, preview)
    with pytest.raises(DomainError, match='invalid_scopes'):
        auth.issue_token(a.user_id, scopes=('listings:publish',))
    assert counts(store) == (1, 1)


@pytest.mark.parametrize('digest', ['', None, 1, 'f'*63, 'F'*64, 'x'*64])
def test_invalid_digest_format(setup, digest):
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    lid = create(drafts, a)['listing']['id']
    with pytest.raises(DomainError, match='invalid_preview_digest'):
        drafts.confirm_publication_intent(a, lid, expected_revision=1, preview_digest=digest, client_id=key())


def test_wrong_digest_and_stale_revision_do_not_create_intent(setup):
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    lid = create(drafts, a)['listing']['id']
    preview = drafts.preview(a, lid)
    with pytest.raises(DomainError, match='preview_conflict'):
        drafts.confirm_publication_intent(a, lid, expected_revision=1, preview_digest='0'*64, client_id=key())
    drafts.update(a, lid, content(title='Новая версия'), category_id='toilets', expected_revision=1, client_id=key())
    with pytest.raises(DomainError, match='revision_conflict'):
        confirm(drafts, a, lid, preview)
    assert counts(store) == (1, 2)


def test_edit_invalidates_existing_intent(setup):
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    lid = create(drafts, a)['listing']['id']
    intent = confirm(drafts, a, lid, drafts.preview(a, lid))
    drafts.update(a, lid, content(title='Изменённая цена', price_minor=10000, currency='RUB'),
                  category_id='toilets', expected_revision=1, client_id=key())
    with pytest.raises(DomainError, match='publication_intent_unavailable'):
        drafts.get_publication_intent(a, lid, intent['intent_id'])
    fresh = drafts.preview(a, lid)
    assert fresh['digest'] != intent['preview_digest']
    assert confirm(drafts, a, lid, fresh)['revision'] == 2


def test_taxonomy_change_without_revision_also_invalidates_preview(setup):
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    lid = create(drafts, a)['listing']['id']
    preview = drafts.preview(a, lid)
    intent = confirm(drafts, a, lid, preview)
    with store._db(write=True) as db:
        db.execute("UPDATE topics SET title='Другая рубрика' WHERE id='plumbing'")
    assert drafts.get(a, lid)['listing']['revision'] == 1
    with pytest.raises(DomainError, match='preview_conflict'):
        confirm(drafts, a, lid, preview)
    with pytest.raises(DomainError, match='publication_intent_unavailable'):
        drafts.get_publication_intent(a, lid, intent['intent_id'])


def test_foreign_preview_confirm_and_receipt_unavailable(setup):
    store, auth, drafts, a, b, now = setup
    a, b = publisher(store, a), publisher(store, b)
    lid = create(drafts, a)['listing']['id']
    preview = drafts.preview(a, lid)
    intent = confirm(drafts, a, lid, preview)
    for wrong_id in (lid, key()):
        for call in (lambda: drafts.preview(b, wrong_id),
                     lambda: confirm(drafts, b, wrong_id, preview),
                     lambda: drafts.get_publication_intent(b, wrong_id, intent['intent_id'])):
            with pytest.raises(DomainError, match='draft_unavailable'):
                call()
    with pytest.raises(DomainError, match='publication_intent_unavailable'):
        drafts.get_publication_intent(a, lid, key())


def test_archive_invalidates_intent_without_publishing(setup):
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    lid = create(drafts, a)['listing']['id']
    preview = drafts.preview(a, lid)
    intent = confirm(drafts, a, lid, preview)
    drafts.archive(a, lid, expected_revision=1, client_id=key())
    with pytest.raises(DomainError, match='publication_intent_unavailable'):
        drafts.get_publication_intent(a, lid, intent['intent_id'])
    with pytest.raises(DomainError, match='draft_not_editable'):
        confirm(drafts, a, lid, preview)
    with pytest.raises(DomainError, match='draft_not_editable'):
        drafts.preview(a, lid)


def test_confirm_receipt_failure_is_atomic(setup, monkeypatch):
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    first = create(drafts, a)['listing']
    preview = drafts.preview(a, first['id'])
    def fail(*args):
        raise sqlite3.OperationalError('synthetic failure')
    monkeypatch.setattr(drafts, '_receipt', fail)
    with pytest.raises(sqlite3.OperationalError):
        confirm(drafts, a, first['id'], preview)
    assert counts(store) == (1, 1)
    assert drafts.get(a, first['id'])['listing'] == first


def test_intent_deadline_is_clipped_to_draft_expiry_and_clock_rollback_denied(setup):
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    lid = create(drafts, a)['listing']['id']
    with store._db(write=True) as db:
        db.execute('UPDATE market_drafts SET expires_at=? WHERE id=?', (now[0]+1000, lid))
    intent = confirm(drafts, a, lid, drafts.preview(a, lid))
    assert intent['valid_until'] == now[0]+1000
    now[0] -= 1
    with pytest.raises(DomainError, match='publication_intent_unavailable'):
        drafts.get_publication_intent(a, lid, intent['intent_id'])


def test_revocation_blocks_replay_and_fresh_intent_read(setup):
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    lid = create(drafts, a)['listing']['id']
    preview, client = drafts.preview(a, lid), key()
    confirm(drafts, a, lid, preview, client)
    auth.revoke(a.credential_id)
    for call in (lambda: confirm(drafts, a, lid, preview, client),
                 lambda: drafts.get_publication_intent(a, lid, client),
                 lambda: drafts.preview(a, lid)):
        with pytest.raises(DomainError, match='authentication_required'):
            call()


def test_concurrent_identical_confirmation_one_receipt(setup):
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    lid = create(drafts, a)['listing']['id']
    preview, client, barrier = drafts.preview(a, lid), key(), threading.Barrier(2)
    def send(_):
        barrier.wait(timeout=10)
        return confirm(drafts, a, lid, preview, client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, (1, 2)))
    assert sorted(x['replayed'] for x in results) == [False, True]
    assert results[0]['intent_id'] == results[1]['intent_id']
    assert counts(store) == (1, 2)


def test_reused_key_other_preview_or_operation_conflicts(setup):
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    lid = create(drafts, a)['listing']['id']
    preview, client = drafts.preview(a, lid), key()
    confirm(drafts, a, lid, preview, client)
    with pytest.raises(DomainError, match='idempotency_conflict'):
        confirm(drafts, a, lid, {**preview, 'digest': '0'*64}, client)
    with pytest.raises(DomainError, match='idempotency_conflict'):
        drafts.archive(a, lid, expected_revision=1, client_id=client)


def test_preview_and_intent_cannot_transfer_to_another_resource(setup):
    from mcp_rooms.draft_store import DraftStore
    store, auth, drafts, a, b, now = setup
    a = publisher(store, a)
    lid = create(drafts, a)['listing']['id']
    preview, client = drafts.preview(a, lid), key()
    confirm(drafts, a, lid, preview, client)
    other_resource = 'https://other.example/mcp'
    with store._db(write=True) as db:
        db.execute('UPDATE credentials SET resource=? WHERE id=?', (other_resource, a.credential_id))
    other = DraftStore(store, other_resource)
    assert other.preview(a, lid)['digest'] != preview['digest']
    with pytest.raises(DomainError, match='publication_intent_unavailable'):
        other.get_publication_intent(a, lid, client)
    with pytest.raises(DomainError, match='idempotency_conflict'):
        confirm(other, a, lid, other.preview(a, lid), client)
