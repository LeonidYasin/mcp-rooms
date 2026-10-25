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


def test_public_open_rooms_fail_closed_on_private_and_legacy(store):
    store.create(A, 'Открыта', topic_id='taxi', visibility='open')
    store.create(A, 'Скрыта', topic_id='delivery', visibility='private')
    store.create(A, 'Без темы')
    index = store.public_open_rooms()
    assert {r['title'] for r in index['rooms']} == {'Открыта'}
    assert all('owner' not in r and 'visibility' not in r and 'joined' not in r for r in index['rooms'])


def test_public_open_rooms_filter_by_topic(store):
    store.create(A, 'Такси', topic_id='taxi', visibility='open')
    store.create(A, 'Доставка', topic_id='delivery', visibility='open')
    got = store.public_open_rooms(topic='taxi')['rooms']
    assert len(got) == 1 and got[0]['topic_id'] == 'taxi'
    error('invalid_topic_id', lambda: store.public_open_rooms(topic='bad id'))


def test_public_topics_anonymous_browse(store):
    assert 'taxi' in {t['id'] for t in store.public_topics(parent_id='transport')['topics']}
    assert all(t['parent_id'] is None for t in store.public_topics()['topics'])


# --- Slice C: public open-room reads (fail closed) ---

def test_public_open_room_meta_fail_closed(store):
    rid = store.create(A, 'Open', topic_id='taxi', visibility='open')['room_id']
    priv = store.create(A, 'Priv', topic_id='delivery', visibility='private')['room_id']
    leg = store.create(A, 'Legacy')['room_id']
    r = store.public_open_room(rid)
    assert r['room']['title'] == 'Open' and r['room']['topic_id'] == 'taxi'
    assert 'owner' not in r['room']
    for cid in (priv, leg, 'user:ffffffff-ffff-ffff-ffff-ffffffffffff'):
        error('room_unavailable', lambda: store.public_open_room(cid))


def test_public_open_room_messages_bounded_fail_closed(store):
    rid = store.create(A, 'Open', topic_id='taxi', visibility='open')['room_id']
    priv = store.create(A, 'Priv', topic_id='delivery', visibility='private')['room_id']
    for i in range(5):
        store.send(A, rid, f'hello {i}', f'c{i}')
    store.send(A, priv, 'secret', 'cs')
    error('room_unavailable', lambda: store.public_open_room_messages(priv))
    feed = store.public_open_room_messages(rid, limit=2)
    assert len(feed['messages']) == 2 and feed['has_more'] is True
    assert all('owner' not in m and 'reply_to' not in m and 'digest' not in m for m in feed['messages'])
    assert feed['messages'][0]['text'] == 'hello 0'
    feed2 = store.public_open_room_messages(rid, cursor=feed['next_cursor'], limit=10)
    assert [m['text'] for m in feed['messages']] + [m['text'] for m in feed2['messages']] == [f'hello {i}' for i in range(5)]


def test_public_open_room_messages_exclude_deleted(store):
    rid = store.create(A, 'Open', topic_id='taxi', visibility='open')['room_id']
    keep_id = store.send(A, rid, 'keep', 'c1')['message']['id']
    del_id = store.send(A, rid, 'bye', 'c2')['message']['id']
    store.delete_message(A, rid, del_id)
    texts = [m['text'] for m in store.public_open_room_messages(rid)['messages']]
    assert texts == ['keep']
