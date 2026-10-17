"""Extracted storage/recovery tests: temporary files only, never VPS."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import uuid
import pytest
from mcp_rooms.store import RoomError, RoomStore
from mcp_rooms.maintenance import backup_database, verify_database
A, B = 'user:00000000-0000-0000-0000-000000000001', 'user:00000000-0000-0000-0000-000000000002'

def test_directory_alias_shared_permissions_and_hardlink_rejected(tmp_path):
    shared = tmp_path / 'shared'; shared.mkdir(mode=0o700)
    # mkdir's mode is masked by the operator's inherited umask (077 on VPS).
    # Construct the intentionally unsafe fixture explicitly; never relax umask.
    shared.chmod(0o755)
    assert shared.stat().st_mode & 0o777 == 0o755
    with pytest.raises(RoomError, match='unsafe_database_directory'):
        RoomStore(shared / 'r.db')
    private = tmp_path / 'private'; private.mkdir(mode=0o700)
    alias = tmp_path / 'alias'; alias.symlink_to(private, target_is_directory=True)
    with pytest.raises(RoomError, match='invalid_database_path'):
        RoomStore(alias / 'r.db')
    source = private / 'source.db'
    RoomStore(source)
    os.link(source, private / 'hardlink.db')
    with pytest.raises(RoomError, match='invalid_database_path'):
        RoomStore(source)


def test_database_budget_and_full_durability(tmp_path):
    store = RoomStore(tmp_path / 'r.db')
    with store._db() as db:
        assert db.execute('PRAGMA synchronous').fetchone()[0] == 2
        assert db.execute('PRAGMA max_page_count').fetchone()[0] == 16384
        assert db.execute('PRAGMA wal_autocheckpoint').fetchone()[0] == 256
    class TooSmall(RoomStore):
        MAX_PAGES = 1
    with pytest.raises(RoomError, match='room_storage_capacity'):
        TooSmall(store.path)


def test_same_owner_concurrent_retries_create_exactly_one_message(tmp_path):
    path = tmp_path / 'r.db'
    room = RoomStore(path).create(A, 'same-key')['room_id']
    def send(index):
        return RoomStore(path).send(A, room, 'same payload', 'same-key')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(send, range(12)))
    assert len({row['message']['id'] for row in results}) == 1
    assert sum(not row['replayed'] for row in results) == 1
    assert len(RoomStore(path).read(A, room)['messages']) == 1


def test_same_owner_concurrent_new_keys_obey_persisted_cadence(tmp_path):
    path = tmp_path / 'r.db'
    room = RoomStore(path).create(A, 'rate')['room_id']
    def send(index):
        try:
            RoomStore(path, clock=lambda: 1000000).send(A, room, 'x', str(index))
            return 'sent'
        except RoomError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(send, range(8)))
    assert results.count('sent') == 1
    assert results.count('rate_limited') == 7


def test_process_reopen_and_aborted_transaction(tmp_path):
    path = tmp_path / 'r.db'
    store = RoomStore(path)
    room = store.create(A, 'process')['room_id']
    message = store.send(A, room, 'committed', 'key')['message']
    crash = ('import os,sqlite3; c=sqlite3.connect(' + repr(str(path)) + '); '
             'c.execute("BEGIN IMMEDIATE"); '
             'c.execute("INSERT INTO actors(owner) VALUES (?)", ("user:00000000-0000-0000-0000-000000000063",)); os._exit(0)')
    subprocess.run([sys.executable, '-c', crash], check=True, timeout=15, capture_output=True)
    read = ('import json; from mcp_rooms.store import RoomStore; '
            's=RoomStore(' + repr(str(path)) + '); '
            'print(json.dumps(s.read("user:00000000-0000-0000-0000-000000000001", ' + repr(room) + ')))')
    output = subprocess.run([sys.executable, '-c', read], check=True, timeout=15,
                            capture_output=True, text=True)
    assert json.loads(output.stdout)['messages'][0]['id'] == message['id']
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT 1 FROM actors WHERE owner=?', ('user:00000000-0000-0000-0000-000000000063',)).fetchone() is None


def test_consistent_wal_backup_and_restore_to_new_path(tmp_path):
    path = tmp_path / 'r.db'
    store = RoomStore(path, clock=lambda: 1000000)
    room = store.create(A, 'backup')['room_id']
    store.join(B, room)
    first = store.send(A, room, 'hello', 'stable-key')['message']
    # Keep an active connection so the test really exercises a live WAL source.
    keeper = sqlite3.connect(path)
    try:
        keeper.execute('PRAGMA journal_mode=WAL')
        with sqlite3.connect(path) as writer:
            writer.execute('UPDATE actors SET last_send=1000000 WHERE owner=?', (A,))
        snapshot = tmp_path / 'snapshot.db'
        assert backup_database(path, snapshot)['counts']['messages'] == 1
    finally:
        keeper.close()
    assert snapshot.stat().st_mode & 0o777 == 0o600
    assert verify_database(snapshot)['ok']
    restored = tmp_path / 'restored.db'
    backup_database(snapshot, restored)
    recovered = RoomStore(restored, clock=lambda: 1000000)
    assert recovered.read(B, room)['messages'][0]['id'] == first['id']
    assert recovered.send(A, room, 'hello', 'stable-key')['replayed']
    with pytest.raises(RoomError, match='rate_limited'):
        recovered.send(A, room, 'different', 'new-key')
    with pytest.raises(FileExistsError):
        backup_database(path, snapshot)
    assert RoomStore(path).list(A)['rooms'][0]['id'] == room


def test_backup_refuses_alias_missing_source_and_invalid_schema(tmp_path):
    with pytest.raises(FileNotFoundError):
        backup_database(tmp_path / 'missing.db', tmp_path / 'out.db')
    assert not (tmp_path / 'out.db').exists()
    source = tmp_path / 'wrong.db'
    with sqlite3.connect(source) as db:
        db.execute('PRAGMA user_version=99')
    source.chmod(0o600)
    with pytest.raises(RoomError, match='unsupported_database_version'):
        backup_database(source, tmp_path / 'out.db')
    assert not (tmp_path / 'out.db').exists()
    private = tmp_path / 'private'; private.mkdir(mode=0o700)
    link = tmp_path / 'link'; link.symlink_to(private, target_is_directory=True)
    with pytest.raises(RoomError, match='invalid_database_path'):
        backup_database(source, link / 'out.db')
