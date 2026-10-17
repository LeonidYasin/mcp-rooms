"""Only temporary SQLite files and fake identities; no live services or credentials."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
import uuid
import pytest
from mcp_rooms.store import RoomStore, RoomError, Limits

A, B, C = 'user:00000000-0000-0000-0000-000000000001', 'user:00000000-0000-0000-0000-000000000002', 'user:00000000-0000-0000-0000-000000000003'


@pytest.fixture
def setup(tmp_path):
    now = [1000000]
    store = RoomStore(tmp_path / 'rooms.db', clock=lambda: now[0])
    room = store.create(A, 'Разработка')['room_id']
    return store, room, now


def error(code, fn):
    with pytest.raises(RoomError) as exc:
        fn()
    assert exc.value.code == code


def test_two_owners_membership_replies_and_durability(setup):
    store, room, now = setup
    error('membership_required', lambda: store.read(B, room))
    error('membership_required', lambda: store.send(B, room, 'hello', 'key'))
    assert store.join(B, room)['joined']
    assert store.join(B, room)['already_joined']
    first = store.send(A, room, 'Привет 👋', 'first')['message']
    reply = store.send(B, room, 'Здравствуйте', 'reply', first['id'])['message']
    assert [r['owner'] for r in store.read(A, room)['messages']] == [A, B]
    assert reply['reply_to'] == first['id']
    reopened = RoomStore(store.path, clock=lambda: now[0])
    assert len(reopened.read(B, room)['messages']) == 2
    assert store.path.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(store.path) as db:
        assert db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
        assert db.execute('PRAGMA user_version').fetchone()[0] == 2


def test_ownership_tombstone_close_and_leave(setup):
    store, room, now = setup
    store.join(B, room)
    first = store.send(A, room, 'text', 'key')['message']
    error('message_unavailable_or_not_yours', lambda: store.delete_message(B, room, first['id']))
    error('not_room_owner', lambda: store.close(B, room))
    assert store.delete_message(A, room, first['id'])['tombstone']
    assert store.send(A, room, 'text', 'key')['message']['text'] == ''
    assert store.read(B, room)['messages'][0]['deleted'] == 1
    store.leave(B, room)
    error('membership_required', lambda: store.read(B, room))
    error('owner_must_close_room', lambda: store.leave(A, room))
    assert store.close(A, room)['history_deleted']
    error('room_unavailable', lambda: store.read(B, room))
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM members').fetchone()[0] == 0


def test_idempotency_and_rate_limit_persist_across_instances(setup):
    store, room, now = setup
    first = store.send(A, room, 'е\u0308ж', 'key')['message']
    other = RoomStore(store.path, clock=lambda: now[0])
    assert other.send(A, room, 'ёж', 'key')['message']['id'] == first['id']
    error('idempotency_conflict', lambda: other.send(A, room, 'changed', 'key'))
    error('rate_limited', lambda: other.send(A, room, 'new', 'new'))
    room2 = store.create(A, 'Другая')['room_id']
    error('rate_limited', lambda: other.send(A, room2, 'same owner', 'key'))
    now[0] += 10000
    assert other.send(A, room2, 'new', 'key')['replayed'] is False


def test_pagination_room_scoping_and_retention(setup):
    store, room, now = setup
    for index in range(3):
        store.send(A, room, str(index), str(index))
        now[0] += 10000
    page = store.read(A, room, limit=2)
    assert page['has_more'] and len(page['messages']) == 2
    reopened = RoomStore(store.path, clock=lambda: now[0])
    assert len(reopened.read(A, room, cursor=page['next_cursor'])['messages']) == 1
    room2 = store.create(A, 'other')['room_id']
    error('invalid_cursor', lambda: store.read(A, room2, cursor=page['next_cursor']))
    for cursor in ['bad', room + ':-1', room + ':01', room + ':99999999999999999999']:
        error('invalid_cursor', lambda: store.read(A, room, cursor=cursor))
    now[0] += 86400000
    assert store.read(A, room)['messages'] == []
    assert store.read(A, room)['history_complete'] is False
    assert store.send(A, room, 'new window', '0')['replayed'] is False
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 1


def test_reply_cannot_cross_rooms_or_target_deleted_message(setup):
    store, room, now = setup
    other = store.create(A, 'other')['room_id']
    message = store.send(A, room, 'text', 'a')['message']['id']
    now[0] += 10000
    error('reply_unavailable', lambda: store.send(A, other, 'reply', 'b', message))
    store.delete_message(A, room, message)
    error('reply_unavailable', lambda: store.send(A, room, 'reply', 'b', message))


def test_input_validation_and_listing_cursor(setup):
    store, room, now = setup
    for text in ['', ' ', 'x' * 501, '\x00text', 123]:
        error('invalid_text', lambda: store.send(A, room, text, 'key'))
    for value in [0, 101, True, 1.5, '20']:
        error('invalid_limit', lambda: store.read(A, room, limit=value))
    error('invalid_client_message_id', lambda: store.send(A, room, 'x', '../bad'))
    room2 = store.create(A, 'second')['room_id']
    page = store.list(B, limit=1)
    assert page['rooms'][0]['joined'] == 0 and page['has_more']
    assert store.list(B, cursor=page['next_cursor'])['rooms'][0]['id'] == room2
    error('invalid_cursor', lambda: store.list(A, cursor=room + ':0'))


def test_message_capacity_is_atomic_and_does_not_silently_evict(tmp_path):
    limits = replace(Limits(), messages=1, messages_per_room=1)
    store = RoomStore(tmp_path / 'r.db', limits=limits)
    room = store.create(A, 'one')['room_id']
    store.join(B, room)
    store.send(A, room, 'first', '1')
    error('message_capacity', lambda: store.send(B, room, 'second', '2'))
    assert store.read(B, room)['messages'][0]['text'] == 'first'


@pytest.mark.parametrize('field,code', [('rooms', 'room_capacity'), ('rooms_per_owner', 'owner_room_capacity'),
                                        ('memberships_per_owner', 'membership_capacity')])
def test_room_and_membership_caps(tmp_path, field, code):
    store = RoomStore(tmp_path / 'r.db', limits=replace(Limits(), **{field: 1}))
    store.create(A, 'first')
    error(code, lambda: store.create(A, 'second'))
    assert len(store.list(A)['rooms']) == 1


def test_principal_and_room_member_caps(tmp_path):
    store = RoomStore(tmp_path / 'r.db', limits=replace(Limits(), principals=1))
    room = store.create(A, 'first')['room_id']
    error('principal_capacity', lambda: store.join(B, room))
    other = RoomStore(tmp_path / 'other.db', limits=replace(Limits(), members_per_room=1))
    room = other.create(A, 'one')['room_id']
    error('room_member_capacity', lambda: other.join(B, room))


def test_concurrent_workers_respect_global_room_capacity(tmp_path):
    path = tmp_path / 'r.db'
    limits = replace(Limits(), rooms=3)
    RoomStore(path, limits=limits)
    def create(index):
        try:
            return RoomStore(path, limits=limits).create('user:' + str(uuid.UUID(int=index)), 'room')['room_id']
        except RoomError as exc:
            assert exc.code == 'room_capacity'
            return None
    with ThreadPoolExecutor(max_workers=6) as workers:
        results = list(workers.map(create, range(1, 7)))
    assert len([row for row in results if row]) == 3
    assert len(RoomStore(path).list(A)['rooms']) == 3


def test_bad_paths_and_unsupported_schema(tmp_path):
    error('invalid_database_path', lambda: RoomStore('relative.db'))
    target = tmp_path / 'target.db'
    link = tmp_path / 'link.db'
    target.touch(); link.symlink_to(target)
    error('invalid_database_path', lambda: RoomStore(link))
    with sqlite3.connect(target) as db:
        db.execute('PRAGMA user_version=99')
    error('unsupported_database_version', lambda: RoomStore(target))


