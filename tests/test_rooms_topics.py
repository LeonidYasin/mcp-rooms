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


def test_web_rooms_fail_closed_on_private_and_legacy(store):
    store.create(A, 'Открыта', topic_id='taxi', visibility='open')
    store.create(A, 'Скрыта', topic_id='delivery', visibility='private')
    store.create(A, 'Без темы')
    index = store.web_rooms()
    assert {r['title'] for r in index['rooms']} == {'Открыта'}
    assert all('owner' not in r and 'visibility' not in r and 'joined' not in r for r in index['rooms'])


def test_web_rooms_filter_by_topic(store):
    store.create(A, 'Такси', topic_id='taxi', visibility='open')
    store.create(A, 'Доставка', topic_id='delivery', visibility='open')
    got = store.web_rooms(topic='taxi')['rooms']
    assert len(got) == 1 and got[0]['topic_id'] == 'taxi'
    error('invalid_topic_id', lambda: store.web_rooms(topic='bad id'))


def test_public_topics_anonymous_browse(store):
    assert 'taxi' in {t['id'] for t in store.public_topics(parent_id='transport')['topics']}
    assert all(t['parent_id'] is None for t in store.public_topics()['topics'])

# --- Slice C: public open-room reads (fail closed) ---

@pytest.fixture
def cstore(tmp_path):
    now = [1000000]
    return RoomStore(tmp_path / 'rooms.db', clock=lambda: now[0]), now


def test_web_room_meta_fail_closed(store):
    rid = store.create(A, 'Open', topic_id='taxi', visibility='open')['room_id']
    priv = store.create(A, 'Priv', topic_id='delivery', visibility='private')['room_id']
    leg = store.create(A, 'Legacy')['room_id']
    r = store.web_room(rid)
    assert r['room']['title'] == 'Open' and r['room']['topic_id'] == 'taxi'
    assert 'owner' not in r['room']
    error('room_unavailable', lambda: store.web_room(priv))
    error('room_unavailable', lambda: store.web_room(leg))
    error('room_unavailable', lambda: store.web_room('00000000-0000-0000-0000-0000000000ee'))


def test_web_room_messages_bounded_fail_closed(cstore):
    store, now = cstore
    rid = store.create(A, 'Open', topic_id='taxi', visibility='open')['room_id']
    priv = store.create(A, 'Priv', topic_id='delivery', visibility='private')['room_id']
    for i in range(5):
        store.send(A, rid, f'hello {i}', f'c{i}')
        now[0] += 10000
    error('room_unavailable', lambda: store.web_room_messages(priv))
    feed = store.web_room_messages(rid, limit=2)
    assert len(feed['messages']) == 2 and feed['has_more'] is True
    assert all('owner' not in m and 'reply_to' not in m and 'digest' not in m for m in feed['messages'])
    assert feed['messages'][0]['text'] == 'hello 0'
    feed2 = store.web_room_messages(rid, cursor=feed['next_cursor'], limit=10)
    assert [m['text'] for m in feed['messages']] + [m['text'] for m in feed2['messages']] == [f'hello {i}' for i in range(5)]


def test_web_room_messages_exclude_deleted(cstore):
    store, now = cstore
    rid = store.create(A, 'Open', topic_id='taxi', visibility='open')['room_id']
    store.send(A, rid, 'keep', 'c1')
    now[0] += 10000
    store.send(A, rid, 'bye', 'c2')
    now[0] += 10000
    del_id = store.read(A, rid)['messages'][-1]['id']
    store.delete_message(A, rid, del_id)
    texts = [m['text'] for m in store.web_room_messages(rid)['messages']]
    assert texts == ['keep']


def test_private_room_same_code_path_web_flag_only(store, monkeypatch):
    """Owner direction: private rooms run the exact same store/web read code as open rooms;
    the ONLY difference is the single WEB_VISIBLE decision point."""
    from mcp_rooms import store as store_mod
    priv = store.create(A, 'Приват', topic_id='taxi', visibility='private')['room_id']
    # not web-exposed by default
    error('room_unavailable', lambda: store.web_room(priv))
    # flipping the single flag serves the same room through the same code (no special-casing)
    monkeypatch.setattr(store_mod, 'WEB_VISIBLE', ('open', 'private'))
    assert store.web_room(priv)['room']['title'] == 'Приват'
    assert any(r['id'] == priv for r in store.web_rooms()['rooms'])
    assert store.web_room_messages(priv)['messages'] == []

# --- Phase 1 "Единый каталог": root/active + market listing subtree + _topic validator ---
# Additive Phase 1 of the market_categories -> base topic-tree consolidation. market_categories
# itself keeps working (unchanged); topics gains listing attributes and the folded-in market
# subtree under 'market'. No behavior change for rooms with only seeded active topics.

def test_market_listing_subtree_seeded(store):
    market = {t['id'] for t in store.topics(A, parent_id='market')['topics']}
    assert {'things', 'services', 'market-goods', 'market-used'} <= market
    assert {t['id'] for t in store.topics(A, parent_id='things')['topics']} == {'home-repair'}
    assert {t['id'] for t in store.topics(A, parent_id='home-repair')['topics']} == {'plumbing'}
    assert {t['id'] for t in store.topics(A, parent_id='plumbing')['topics']} == {'toilets'}


def test_topic_roots_and_active_backfilled(store):
    with store._db() as db:
        rows = {r['id']: r for r in db.execute('SELECT id, parent_id, root, active FROM topics')}
    assert rows['transport']['root'] == 'transport'
    assert rows['taxi']['root'] == 'transport'
    assert rows['market-goods']['root'] == 'market' and rows['market-used']['root'] == 'market'
    assert rows['toilets']['root'] == 'things' and rows['services']['root'] == 'services'
    assert rows['market']['root'] == 'market'
    assert all(v['active'] == 1 for v in rows.values())


def test_create_with_folded_market_topic(store):
    r = store.create(A, 'Унитаз любой', topic_id='toilets', visibility='open')
    assert r['topic_id'] == 'toilets'
    assert store.list(A)['rooms'][0]['topic_id'] == 'toilets'


def test_topic_validator_root_active_and_ancestry(store):
    with store._db(write=True) as db:
        assert store._topic(db, 'toilets') == 'toilets'
        assert store._topic(db, 'toilets', root='things') == 'toilets'
        error('topic_unavailable', lambda: store._topic(db, 'toilets', root='services'))
        error('topic_unavailable', lambda: store._topic(db, 'nope'))
        # deactivating an ancestor makes descendants unavailable
        db.execute("UPDATE topics SET active=0 WHERE id='plumbing'")
        assert store._topic(db, 'market') == 'market'  # unrelated branch untouched
        error('topic_unavailable', lambda: store._topic(db, 'toilets'))
        assert store._topic(db, 'things') == 'things'  # parent itself stays active


def test_create_rejects_inactive_topic(store):
    with store._db(write=True) as db:
        db.execute("UPDATE topics SET active=0 WHERE id='services'")
    error('topic_unavailable', lambda: store.create(A, 'x', topic_id='services'))


def test_browse_validates_parent_and_serves_active_children(store):
    with store._db(write=True) as db:
        db.execute("UPDATE topics SET active=0 WHERE id='things'")
    error('topic_unavailable', lambda: store.topics(A, parent_id='things'))
    error('topic_unavailable', lambda: store.topics(A, parent_id='automobile'))
    error('topic_unavailable', lambda: store.public_topics(parent_id='automobile'))
    assert {'market', 'transport'} <= {t['id'] for t in store.topics(A)['topics']}
    assert 'taxi' in {t['id'] for t in store.public_topics(parent_id='transport')['topics']}


def test_additive_migration_adds_columns_and_market_subtree(tmp_path):
    import sqlite3
    path = tmp_path / 'old.db'
    db = sqlite3.connect(str(path))
    db.execute('PRAGMA application_id=' + str(RoomStore.APPLICATION_ID))
    db.execute('PRAGMA user_version=2')
    db.execute('CREATE TABLE topics (id TEXT PRIMARY KEY, parent_id TEXT REFERENCES topics(id), title TEXT NOT NULL)')
    db.executemany('INSERT INTO topics VALUES (?,?,?)', [
        ('market', None, 'Маркет и товары'), ('market-goods', 'market', 'Товары и услуги'),
        ('transport', None, 'Транспорт'), ('taxi', 'transport', 'Такси'),
    ])
    db.commit(); db.close()
    store = RoomStore(path)
    with store._db() as db:
        cols = {r['name'] for r in db.execute('PRAGMA table_info(topics)')}
        assert {'root', 'active'} <= cols
        roots = {r['id']: r['root'] for r in db.execute('SELECT id, root FROM topics')}
        assert roots['taxi'] == 'transport' and roots['market-goods'] == 'market'
        assert roots['toilets'] == 'things' and roots['services'] == 'services'
        assert roots['market'] == 'market'
        all_ids = {r['id'] for r in db.execute('SELECT id FROM topics')}
        assert {'things', 'home-repair', 'plumbing', 'toilets', 'services'} <= all_ids
    # idempotent on a second open: nothing left unrooted, columns stable
    again = RoomStore(path)
    with again._db() as db:
        assert db.execute('SELECT COUNT(*) FROM topics WHERE root IS NULL').fetchone()[0] == 0
        assert {'root', 'active'} <= {r['name'] for r in db.execute('PRAGMA table_info(topics)')}
