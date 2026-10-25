"""Slice A: rooms topic_id + fixed-at-creation visibility, united topic catalog.

Only temporary SQLite files and fake identities; no live services or credentials.
"""
import pytest
from mcp_rooms.store import RoomStore, RoomError

A = 'user:00000000-0000-0000-0000-000000000001'
B = 'user:00000000-0000-0000-0000-000000000002'


def error(code, fn):
    with pytest.raises(RoomError) as exc:
        fn()
    assert exc.value.code == code


@pytest.fixture
def store(tmp_path):
    return RoomStore(tmp_path / 'rooms.db')


def test_seeded_topic_tree(store):
    root = store.topics(A)['topics']
    assert {t['id'] for t in root} >= {'market', 'transport', 'hiring', 'finance', 'realestate', 'misc'}
    children = {t['id'] for t in store.topics(A, parent_id='transport')['topics']}
    assert {'taxi', 'delivery'} <= children


def test_create_with_topic_and_visibility(store):
    r = store.create(A, 'Такси у дома', topic_id='taxi', visibility='open')
    assert r['topic_id'] == 'taxi' and r['visibility'] == 'open'
    row = store.list(A)['rooms'][0]
    assert row['topic_id'] == 'taxi' and row['visibility'] == 'open'


def test_create_defaults_to_private_when_only_topic(store):
    r = store.create(A, 'Тематическая', topic_id='market')
    assert r['visibility'] == 'private'
    assert store.list(A)['rooms'][0]['visibility'] == 'private'


def test_create_legacy_no_topic(store):
    r = store.create(A, 'Любая')
    assert r['visibility'] == 'public_to_enrolled_users'
    row = store.list(A)['rooms'][0]
    assert row['topic_id'] is None and row['visibility'] is None


def test_create_rejects_invalid_topic(store):
    error('topic_unavailable', lambda: store.create(A, 'x', topic_id='nope'))


def test_create_rejects_visibility_without_topic(store):
    error('topic_required', lambda: store.create(A, 'x', visibility='open'))


def test_create_rejects_invalid_visibility(store):
    error('invalid_visibility', lambda: store.create(A, 'x', topic_id='taxi', visibility='staff'))


def test_create_rejects_invalid_topic_id_shape(store):
    error('invalid_topic_id', lambda: store.create(A, 'x', topic_id='bad id!!'))


def test_list_filters_by_topic(store):
    open_taxi = store.create(A, 'Такси', topic_id='taxi', visibility='open')['room_id']
    store.create(A, 'Доставка', topic_id='delivery', visibility='open')
    private_taxi = store.create(B, 'Частная', topic_id='taxi', visibility='private')['room_id']
    got = {r['id'] for r in store.list(A, topic='taxi')['rooms']}
    assert got == {open_taxi, private_taxi}


def test_list_shows_rooms_of_other_owner_by_topic(store):
    store.create(B, 'Инвесторы', topic_id='investors', visibility='open')
    got = store.list(A, topic='investors')['rooms']
    assert len(got) == 1 and got[0]['owner'] == B


def test_topics_browse_capacity_and_exact_parent(store):
    assert all(t['parent_id'] is None for t in store.topics(A)['topics'])
    taxi = store.topics(A, parent_id='taxi')['topics']
    assert taxi == []
