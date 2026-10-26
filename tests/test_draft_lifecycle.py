"""M1b private lifecycle only: synthetic SQLite fixtures, never network/deploy."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import threading
import uuid
import pytest
from mcp_rooms.domain import DomainError
from mcp_rooms.draft_store import DraftStore
from test_draft_store import setup, content, create, counts, key


def test_private_archive_is_terminal_versioned_and_idempotent(setup):
    store, auth, drafts, a, b, now = setup
    first = create(drafts, a)['listing']
    client = key()
    result = drafts.archive(a, first['id'], expected_revision=1, client_id=client)
    assert result['listing']['status'] == 'archived'
    assert result['listing']['visibility'] == 'private'
    assert result['listing']['revision'] == 2
    assert result['listing']['content'] == first['content']
    assert drafts.archive(a, first['id'], expected_revision=1, client_id=client) == {**result, 'replayed': True}
    assert drafts.get(a, first['id'])['listing'] == result['listing']
    with pytest.raises(DomainError, match='draft_not_editable'):
        drafts.update(a, first['id'], content(), category_id='toilets', expected_revision=2, client_id=key())
    with pytest.raises(DomainError, match='draft_not_editable'):
        drafts.archive(a, first['id'], expected_revision=2, client_id=key())
    assert counts(store) == (1, 2)


def test_archive_foreign_and_missing_indistinguishable(setup):
    store, auth, drafts, a, b, now = setup
    first = create(drafts, a)['listing']
    for lid in (first['id'], key()):
        with pytest.raises(DomainError, match='draft_unavailable'):
            drafts.archive(b, lid, expected_revision=1, client_id=key())
    assert drafts.get(a, first['id'])['listing'] == first
    assert counts(store) == (1, 1)


def test_archive_stale_revision_and_reuse_key_conflicts(setup):
    store, auth, drafts, a, b, now = setup
    first = create(drafts, a)['listing']
    with pytest.raises(DomainError, match='revision_conflict'):
        drafts.archive(a, first['id'], expected_revision=2, client_id=key())
    client = key()
    drafts.archive(a, first['id'], expected_revision=1, client_id=client)
    with pytest.raises(DomainError, match='idempotency_conflict'):
        drafts.archive(a, first['id'], expected_revision=2, client_id=client)
    with pytest.raises(DomainError, match='idempotency_conflict'):
        drafts.create(a, content(), category_id='toilets', client_id=client)


def test_archive_rollback_when_receipt_write_fails(setup, monkeypatch):
    store, auth, drafts, a, b, now = setup
    first = create(drafts, a)['listing']
    def fail(*args):
        raise sqlite3.OperationalError('synthetic failure')
    with monkeypatch.context() as patch:
        patch.setattr(drafts, '_receipt', fail)
        with pytest.raises(sqlite3.OperationalError):
            drafts.archive(a, first['id'], expected_revision=1, client_id=key())
    assert drafts.get(a, first['id'])['listing'] == first
    assert counts(store) == (1, 1)


def test_historical_create_receipt_does_not_resurrect_archive(setup):
    store, auth, drafts, a, b, now = setup
    client = key()
    first = drafts.create(a, content(), category_id='toilets', client_id=client)
    drafts.archive(a, first['listing']['id'], expected_revision=1, client_id=key())
    replay = drafts.create(a, content(), category_id='toilets', client_id=client)
    assert replay['listing']['status'] == 'draft' and replay['replayed']
    assert drafts.get(a, first['listing']['id'])['listing']['status'] == 'archived'
    assert counts(store) == (1, 2)


def test_own_pagination_tie_break_stable_without_foreign_rows(setup):
    store, auth, drafts, a, b, now = setup
    expected = sorted(create(drafts, a)['listing']['id'] for _ in range(5))
    create(drafts, b)
    ids, cursor = [], None
    while True:
        page = drafts.list_own(a, cursor=cursor, limit=2)
        ids.extend(item['listing']['id'] for item in page['items'])
        if not page['has_more']:
            assert page['next_cursor'] is None
            break
        cursor = page['next_cursor']
    assert ids == expected and len(set(ids)) == 5
    assert len(drafts.list_own(b)['items']) == 1


def test_paging_is_not_snapshot_update_does_not_move_creation_key(setup):
    store, auth, drafts, a, b, now = setup
    first = create(drafts, a)['listing']
    now[0] += 1
    second = create(drafts, a)['listing']
    page = drafts.list_own(a, limit=1)
    assert page['items'][0]['listing']['id'] == first['id']
    now[0] += 1
    drafts.update(a, first['id'], content(title='Обновлено'), category_id='toilets', expected_revision=1, client_id=key())
    drafts.archive(a, second['id'], expected_revision=1, client_id=key())
    tail = drafts.list_own(a, limit=1, cursor=page['next_cursor'])
    assert tail == {'items': [], 'has_more': False, 'next_cursor': None}
    assert drafts.list_own(a, status='archived')['items'][0]['listing']['id'] == second['id']


@pytest.mark.parametrize('limit', [0, -1, 51, True, 1.0, '1'])
def test_list_limit_validation(setup, limit):
    _, _, drafts, a, *_ = setup
    with pytest.raises(DomainError, match='invalid_limit'):
        drafts.list_own(a, limit=limit)


@pytest.mark.parametrize('cursor', ['', 1, {}, 'market:garbage', 'x'*181])
def test_list_malformed_cursor(setup, cursor):
    _, _, drafts, a, *_ = setup
    with pytest.raises(DomainError, match='invalid_cursor'):
        drafts.list_own(a, cursor=cursor)


def test_cursor_actor_status_and_numeric_bounds(setup):
    store, auth, drafts, a, b, now = setup
    create(drafts, a)
    create(drafts, a)
    cursor = drafts.list_own(a, limit=1)['next_cursor']
    with pytest.raises(DomainError, match='invalid_cursor'):
        drafts.list_own(b, cursor=cursor)
    with pytest.raises(DomainError, match='invalid_cursor'):
        drafts.list_own(a, status='archived', cursor=cursor)
    for stamp in ('01', '-1', str(2**63), '1e3'):
        with pytest.raises(DomainError, match='invalid_cursor'):
            drafts.list_own(a, cursor=f'market:{a.user_id}:draft:{stamp}:{key()}')
    for status in ('active', '', None, [], True):
        with pytest.raises(DomainError, match='invalid_draft_status'):
            drafts.list_own(a, status=status)


def test_no_expired_results_and_archive_not_eraser(setup):
    store, auth, drafts, a, b, now = setup
    first = create(drafts, a)['listing']
    drafts.archive(a, first['id'], expected_revision=1, client_id=key())
    assert drafts.list_own(a)['items'] == []
    assert len(drafts.list_own(a, status='archived')['items']) == 1
    with store._db(write=True) as db:
        db.execute('UPDATE credentials SET expires_at=? WHERE id=?', (first['expires_at']//1000+60, a.credential_id))
    now[0] = first['expires_at']
    assert drafts.list_own(a, status='archived')['items'] == []
    # Content/receipts retained physically pending separately reviewed retention.
    assert counts(store) == (1, 2)


def test_category_children_and_hidden_parent(setup):
    store, auth, drafts, a, b, now = setup
    roots = drafts.categories(a)['categories']
    assert [x['id'] for x in roots] == ['services', 'things']
    assert drafts.categories(a, parent_id='plumbing')['categories'][0]['id'] == 'toilets'
    assert drafts.categories(a, parent_id='toilets')['categories'] == []
    with store._db(write=True) as db:
        db.execute("UPDATE topics SET active=0 WHERE id='home-repair'")
    for parent in ('home-repair', 'plumbing', 'toilets', 'unknown'):
        with pytest.raises(DomainError, match='category_unavailable'):
            drafts.categories(a, parent_id=parent)
    with pytest.raises(DomainError, match='invalid_category'):
        drafts.categories(a, parent_id='../things')
    assert drafts.categories(a, parent_id='things')['categories'] == []


def test_all_new_reads_and_archive_recheck_revocation(setup):
    store, auth, drafts, a, b, now = setup
    first = create(drafts, a)['listing']
    auth.revoke(a.credential_id)
    for call in (lambda: drafts.list_own(a), lambda: drafts.categories(a),
                 lambda: drafts.archive(a, first['id'], expected_revision=1, client_id=key())):
        with pytest.raises(DomainError, match='authentication_required'):
            call()
    assert counts(store) == (1, 1)


def test_archive_update_race_cannot_edit_archived_row(setup):
    store, auth, drafts, a, b, now = setup
    lid = create(drafts, a)['listing']['id']
    barrier = threading.Barrier(2)
    def command(operation):
        barrier.wait(timeout=10)
        try:
            if operation == 'archive':
                return drafts.archive(a, lid, expected_revision=1, client_id=key())
            return drafts.update(a, lid, content(title='Гонка'), category_id='toilets', expected_revision=1, client_id=key())
        except DomainError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(command, ('archive', 'update')))
    assert sum(isinstance(x, dict) for x in results) == 1
    assert any(x in ('revision_conflict', 'draft_not_editable') for x in results if isinstance(x, str))
    assert drafts.get(a, lid)['listing']['revision'] == 2
    assert counts(store) == (1, 2)


def test_schema_query_failure_not_misreported_as_missing_migration():
    class BrokenDB:
        def execute(self, *args):
            raise sqlite3.OperationalError('database is locked')
    with pytest.raises(sqlite3.OperationalError, match='database is locked'):
        DraftStore._schema(BrokenDB())


def test_category_read_bound_does_not_silently_truncate(setup):
    store, auth, drafts, a, b, now = setup
    with store._db(write=True) as db:
        db.executemany('INSERT INTO topics(id,parent_id,title,root,active) VALUES (?,?,?,?,?)',
                       [(f'cat{i}', 'market', f'Category {i}', f'cat{i}', 1) for i in range(101)])
    with pytest.raises(DomainError, match='category_capacity'):
        drafts.categories(a)


def test_uuid_shaped_invalid_cursor_has_consistent_error(setup):
    store, auth, drafts, a, b, now = setup
    with pytest.raises(DomainError, match='invalid_cursor'):
        drafts.list_own(a, cursor=f'market:{a.user_id}:draft:1:{"-"*36}')
