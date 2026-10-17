"""Automatic users, fake contacts and synthetic secrets only; no email/SMS services."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import sqlite3
import uuid
import pytest
from starlette.testclient import TestClient
from mcp_rooms.identity import IdentityStore
from mcp_rooms.enrollment import Enrollment
from mcp_rooms.store import RoomStore, RoomError, Limits
from mcp_rooms.server import create_app
from mcp_rooms.maintenance import backup_database

RESOURCE = 'https://rooms.example/rooms-test/mcp'


def secret(index=1):
    # Predictable synthetic test values are NEVER usable examples for real users.
    return str(uuid.UUID(int=index, version=4))


def data(index=1, server=False, contact='synthetic@example.invalid'):
    return {'contact': contact, 'bootstrap_uuid': secret(index), 'issue_server_key': server}


@pytest.fixture
def setup(tmp_path):
    now = [1000000]
    store = RoomStore(tmp_path / 'rooms.db', clock=lambda: now[0])
    auth = IdentityStore(store, RESOURCE)
    return store, auth, Enrollment(auth), now


def test_automatic_uuid_or_issued_key_same_user_no_pii_or_raw_secret_stored(setup):
    store, auth, enroll, now = setup
    result = enroll.register(data(server=True))
    assert result['contact'] == {'kind': 'email', 'verified': False, 'stored': False}
    first = auth.authenticate(secret())
    second = auth.authenticate(result['server_key']['key'])
    assert first.user_id == second.user_id == result['user_id']
    assert first.owner != 'user:' + secret()
    assert first.credential_id != second.credential_id
    with store._db() as db:
        dump = '\n'.join(db.iterdump())
    for private in (secret(), 'synthetic@example.invalid', result['server_key']['key']):
        assert private not in dump
    replay = enroll.register(data(server=True))
    assert replay['already_registered'] and replay['user_id'] == result['user_id']
    assert replay['server_key'] is None
    with store._db() as db:
        assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM credentials').fetchone()[0] == 2


def test_contact_is_not_recovery_unique_login_or_ownership(setup):
    store, auth, enroll, now = setup
    a = enroll.register(data(1)); b = enroll.register(data(2))
    assert a['user_id'] != b['user_id']  # same unverified contact cannot claim A
    # Contact deliberately not persisted/bound; possession of the secret is identity.
    replay = enroll.register(data(1, contact='+19995550123'))
    assert replay['user_id'] == a['user_id'] and replay['already_registered']
    assert auth.authenticate('synthetic@example.invalid+' + secret()) is None


@pytest.mark.parametrize('payload', [None, [], {}, {'contact': 'bad', 'bootstrap_uuid': secret()},
    {'contact': 'x@example.invalid', 'bootstrap_uuid': str(uuid.UUID(int=1))},
    {'contact': '+19995550123', 'bootstrap_uuid': str(uuid.UUID(int=0xabcdef, version=4)).upper()},
    {**data(), 'owner': 'user:attacker'}, {**data(), 'issue_server_key': 'yes'},
    {**data(), 'contact': 'x@example.invalid\n'}, {**data(), 'contact': 123}])
def test_invalid_registration_has_no_side_effects(setup, payload):
    store, auth, enroll, now = setup
    with pytest.raises(RoomError):
        enroll.register(payload)
    with store._db() as db:
        assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM signup_budgets').fetchone()[0] == 0


def test_disabled_expired_revoked_never_reenroll_to_take_over(setup):
    store, auth, enroll, now = setup
    result = enroll.register(data())
    auth.revoke(result['bootstrap_credential_id'])
    assert auth.authenticate(secret()) is None
    with pytest.raises(RoomError, match='registration_unavailable'):
        enroll.register(data())
    b = enroll.register(data(2)); auth.disable(b['user_id'])
    with pytest.raises(RoomError, match='registration_unavailable'):
        enroll.register(data(2))
    enroll.register(data(3)); now[0] += 604800000
    assert auth.authenticate(secret(3)) is None
    with pytest.raises(RoomError, match='registration_unavailable'):
        enroll.register(data(3))


def test_concurrent_same_secret_creates_one_user(setup):
    store, auth, enroll, now = setup
    with ThreadPoolExecutor(max_workers=6) as workers:
        results = list(workers.map(lambda _: enroll.register(data()), range(8)))
    assert len({r['user_id'] for r in results}) == 1
    assert sum(not r['already_registered'] for r in results) == 1
    with store._db() as db:
        assert db.execute('SELECT COUNT(*) FROM credentials').fetchone()[0] == 1
        assert db.execute('SELECT used FROM signup_budgets WHERE scope=?', ('minute',)).fetchone()[0] == 1


def test_persisted_global_signup_limit_and_snapshot(setup, tmp_path):
    store, auth, enroll, now = setup
    for index in range(1, 6): enroll.register(data(index))
    with pytest.raises(RoomError, match='registration_rate_limited') as exc:
        Enrollment(IdentityStore(RoomStore(store.path, clock=lambda: now[0]), RESOURCE)).register(data(6))
    assert exc.value.details['retry_after_ms'] > 0
    assert enroll.register(data())['already_registered']  # retry doesn't consume budget
    snap = tmp_path / 'snapshot.db'; backup_database(store.path, snap)
    recovered = Enrollment(IdentityStore(RoomStore(snap, clock=lambda: now[0]), RESOURCE))
    with pytest.raises(RoomError, match='registration_rate_limited'):
        recovered.register(data(6))
    now[0] += 60000
    assert recovered.register(data(6))['ok']


def test_total_user_capacity_and_additive_v1_upgrade(setup):
    store, auth, enroll, now = setup
    registered = enroll.register(data())
    with store._db(write=True) as db:
        db.execute('DROP TABLE enrollments'); db.execute('DROP TABLE signup_budgets')
        db.execute('PRAGMA user_version=1')
    upgraded = RoomStore(store.path, clock=lambda: now[0], limits=replace(Limits(), principals=1))
    assert IdentityStore(upgraded, RESOURCE).authenticate(secret()).user_id == registered['user_id']
    with pytest.raises(RoomError, match='user_capacity'):
        Enrollment(IdentityStore(upgraded, RESOURCE)).register(data(2))
    with upgraded._db() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 2


def test_http_signup_closed_by_default_and_origin_no_cache(tmp_path):
    path = tmp_path / 'closed.db'
    with TestClient(create_app(path, RESOURCE), base_url='https://rooms.example') as client:
        assert client.get('/signup').status_code == 403
        assert client.post('/register', json=data()).status_code == 403
    with TestClient(create_app(path, RESOURCE, True), base_url='https://rooms.example') as client:
        page = client.get('/signup')
        assert page.status_code == 200 and 'script-src' in page.headers['content-security-policy']
        assert 'Authorization' not in page.text
        assert client.get('/signup.js').status_code == 200
        assert client.post('/register', json=data(), headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.post('/register', json=data(), headers={'Host': 'evil.example'}).status_code == 421
        assert client.post('/register', content='x' * 4097, headers={'Content-Type': 'application/json'}).status_code == 413
        assert client.post('/register', content='x').status_code == 415
        assert client.post('/register', content='{', headers={'Content-Type': 'application/json'}).status_code == 400
        response = client.post('/register', json=data(server=True))
        assert response.status_code == 201 and response.headers['cache-control'] == 'no-store'
        assert 'synthetic@example.invalid' not in response.text and secret() not in response.text
        payload = response.json(); issued = payload['server_key']['key']
        h = {'Authorization': 'Bearer ' + secret()}
        rpc_headers = dict(h, Accept='application/json, text/event-stream')
        created = client.post('/mcp', headers=rpc_headers, json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'rooms_create','arguments':{'title':'automatic user'}}})
        assert created.status_code == 200
        created_room = json.loads(created.json()['result']['content'][0]['text'])
        assert created_room['ok'] and created_room['owner'] == payload['owner']
        me = client.get('/identity', headers=h)
        assert me.status_code == 200 and me.json()['user_id'] == payload['user_id']
        replay = client.post('/register', json=data(server=True))
        assert replay.status_code == 200 and replay.json()['server_key'] is None
        extra = client.post('/credentials', headers=h, json={})
        assert extra.status_code == 201 and extra.headers['cache-control'] == 'no-store'
        other = {'Authorization': 'Bearer ' + extra.json()['key']}
        assert client.get('/identity', headers=other).json()['user_id'] == payload['user_id']
        assert client.delete('/credentials/current', headers=h).status_code == 200
        assert client.get('/identity', headers=h).status_code == 401
        assert client.get('/identity', headers=other).status_code == 200
        assert client.post('/register', json=data()).status_code == 409


def test_self_issued_credentials_cannot_escalate_read_only_scope(tmp_path):
    path = tmp_path / 'scope.db'; auth = IdentityStore(RoomStore(path), RESOURCE)
    uid = auth.create_user('A')['user_id']; _, token = auth.issue_token(uid, scopes=['rooms:read'])
    with TestClient(create_app(path, RESOURCE), base_url='https://rooms.example') as client:
        h = {'Authorization': 'Bearer ' + token}
        assert client.post('/credentials', headers=h, json={'user_id': 'somebody'}).status_code == 400
        response = client.post('/credentials', headers=h, json={})
        assert response.status_code == 201
        assert auth.authenticate(response.json()['key']).scopes == frozenset({'rooms:read'})
