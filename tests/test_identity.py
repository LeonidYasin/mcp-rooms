"""Synthetic local principals only. Never issue real credentials or call GitHub."""
import hashlib
import json
import os
import sqlite3
import uuid
import pytest
from mcp_rooms.identity import IdentityStore, write_private_token, resource_url
from mcp_rooms.store import RoomStore, RoomError
from mcp_rooms.service import execute
from mcp_rooms.maintenance import backup_database

RESOURCE = 'https://rooms.example/mcp'


@pytest.fixture
def setup(tmp_path):
    now = [1000000]
    store = RoomStore(tmp_path / 'rooms.db', clock=lambda: now[0])
    auth = IdentityStore(store, RESOURCE)
    a = auth.create_user('Alice')['user_id']
    b = auth.create_user('Bob')['user_id']
    ma, ta = auth.issue_token(a)
    mb, tb = auth.issue_token(b)
    return store, auth, a, b, ma, ta, mb, tb, now


def test_no_github_users_multiple_credentials_rotation_share_cadence(setup):
    store, auth, a, b, ma, ta, mb, tb, now = setup
    second, other_key = auth.issue_token(a)
    pa, pb = auth.authenticate(ta), auth.authenticate(tb)
    assert pa.owner == 'user:' + a and pa.owner != pb.owner
    assert auth.authenticate(other_key).owner == pa.owner
    assert auth.authenticate(other_key).credential_id != pa.credential_id
    room = execute(store, pa, 'create', title='room')['room_id']
    first = execute(store, pa, 'send', room_id=room, text='hello', client_message_id='key')
    auth.revoke(ma['credential_id'])
    assert auth.authenticate(ta) is None
    rotated = auth.authenticate(other_key)
    assert execute(store, rotated, 'read', room_id=room)['messages'][0]['id'] == first['message']['id']
    assert execute(store, rotated, 'send', room_id=room, text='hello', client_message_id='key')['replayed']
    assert execute(store, rotated, 'send', room_id=room, text='new', client_message_id='new')['error'] == 'rate_limited'
    assert execute(store, pb, 'read', room_id=room)['error'] == 'membership_required'


def test_unknown_tampered_expired_revoked_disabled_and_resource_are_denied(setup):
    store, auth, a, b, ma, ta, mb, tb, now = setup
    assert auth.authenticate('rm1_' + uuid.uuid4().hex + '.' + 'x' * 43) is None
    assert auth.authenticate(ta[:-1] + ('A' if ta[-1] != 'A' else 'B')) is None
    assert IdentityStore(store, 'https://elsewhere.example/mcp').authenticate(ta) is None
    auth.disable(b)
    assert auth.authenticate(tb) is None
    with pytest.raises(RoomError, match='user_unavailable'):
        auth.issue_token(b)
    now[0] += 604800000
    assert auth.authenticate(ta) is None


@pytest.mark.parametrize('token', [None, '', 'user:any', 'github:1', 123, True, 'a' * 10000, 'rm1_x.y'])
def test_malformed_does_not_touch_db(setup, monkeypatch, token):
    _, auth, *_ = setup
    def forbidden(*args, **kwargs):
        pytest.fail('Malformed credentials must not touch storage')
    monkeypatch.setattr(auth.store, '_db', forbidden)
    assert auth.authenticate(token) is None


def test_secret_not_stored_and_file_never_overwritten(setup, tmp_path):
    store, auth, a, b, ma, ta, mb, tb, now = setup
    with sqlite3.connect(store.path) as db:
        row = db.execute('SELECT digest FROM credentials WHERE id=?', (ma['credential_id'],)).fetchone()
        assert row[0] == hashlib.sha256(ta.encode()).hexdigest()
    assert ta.encode() not in store.path.read_bytes()
    output = tmp_path / 'secret'
    write_private_token(output, ta)
    assert output.stat().st_mode & 0o777 == 0o600
    assert output.read_text().strip() == ta
    with pytest.raises(FileExistsError):
        write_private_token(output, tb)
    link = tmp_path / 'alias'; link.symlink_to(output)
    with pytest.raises(RoomError, match='invalid_database_path'):
        write_private_token(link, tb)


def test_scopes_no_impersonation_and_no_admin_service_actions(setup):
    store, auth, a, b, ma, ta, mb, tb, now = setup
    _, readkey = auth.issue_token(a, scopes=['rooms:read'])
    reader = auth.authenticate(readkey)
    assert execute(store, reader, 'list')['ok']
    assert execute(store, reader, 'create', title='no')['error'] == 'insufficient_scope'
    assert execute(store, auth.authenticate(ta), 'create', title='x', owner='user:' + b)['error'] == 'invalid_arguments'
    assert execute(store, auth.authenticate(ta), 'issue_token')['error'] == 'method_unavailable'
    assert execute(store, None, 'list')['error'] == 'authentication_required'


def test_backup_restores_identity_revocations_membership_keys_and_cadence(setup, tmp_path):
    store, auth, a, b, ma, ta, mb, tb, now = setup
    newer, nt = auth.issue_token(a)
    pa, pb = auth.authenticate(nt), auth.authenticate(tb)
    room = execute(store, pa, 'create', title='recover')['room_id']
    execute(store, pb, 'join', room_id=room)
    first = execute(store, pa, 'send', room_id=room, text='saved', client_message_id='same')['message']
    auth.revoke(ma['credential_id'])
    snap = tmp_path / 'snapshot.db'
    assert backup_database(store.path, snap)['counts']['users'] == 2
    restored = tmp_path / 'restored.db'; backup_database(snap, restored)
    reopened = RoomStore(restored, clock=lambda: now[0])
    recovered = IdentityStore(reopened, RESOURCE)
    assert recovered.authenticate(ta) is None
    assert recovered.authenticate(nt).owner == pa.owner
    assert execute(reopened, recovered.authenticate(tb), 'read', room_id=room)['messages'][0]['id'] == first['id']
    assert execute(reopened, recovered.authenticate(nt), 'send', room_id=room, text='saved', client_message_id='same')['replayed']
    assert execute(reopened, recovered.authenticate(nt), 'send', room_id=room, text='other', client_message_id='other')['error'] == 'rate_limited'


def test_unsafe_embedded_db_is_not_migrated(tmp_path):
    path = tmp_path / 'embedded.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE actors (owner TEXT PRIMARY KEY)')
        db.execute('INSERT INTO actors VALUES (?)', ('github:123',))
        db.execute('PRAGMA user_version=1')
    with pytest.raises(RoomError, match='unsupported_database_identity'):
        RoomStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT owner FROM actors').fetchone()[0] == 'github:123'
        assert db.execute('PRAGMA application_id').fetchone()[0] == 0


@pytest.mark.parametrize('resource', ['http://rooms.example/mcp', 'https://x/mcp?token=x', 'https://a:b@x/mcp', 'https://x/other', 'https://x/mcp#fragment', None])
def test_invalid_resource(resource):
    with pytest.raises(RoomError, match='invalid_resource'):
        resource_url(resource)


def test_storage_errors_are_sanitized(setup, monkeypatch, caplog):
    store, auth, a, b, ma, ta, mb, tb, now = setup
    principal = auth.authenticate(ta)
    def fail(*args, **kwargs):
        exc = sqlite3.OperationalError('SECRET ' + ta)
        exc.sqlite_errorcode = 5
        raise exc
    monkeypatch.setattr(store, 'list', fail)
    result = execute(store, principal, 'list')
    assert result['error'] == 'room_storage_busy' and result['retryable']
    assert ta not in str(result) + caplog.text and 'SECRET' not in str(result) + caplog.text
