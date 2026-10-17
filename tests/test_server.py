"""Real SDK/ASGI HTTP calls with temporary SQLite; no sockets, VPS or external APIs."""
import json
import pytest
from starlette.testclient import TestClient
from mcp_rooms.identity import IdentityStore
from mcp_rooms.server import create_app
from mcp_rooms.store import RoomStore

RESOURCE = 'https://rooms.example/mcp'
HEADERS = {'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'}
NAMES = {'rooms_create', 'rooms_list', 'rooms_join', 'rooms_leave', 'rooms_send', 'rooms_read', 'rooms_delete_message', 'rooms_close'}


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / 'rooms.db'
    auth = IdentityStore(RoomStore(path), RESOURCE)
    a = auth.create_user('A')['user_id']; b = auth.create_user('B')['user_id']
    ma, ta = auth.issue_token(a); mb, tb = auth.issue_token(b)
    with TestClient(create_app(path, RESOURCE), base_url='https://rooms.example') as client:
        yield client, auth, a, b, ma, ta, mb, tb


def rpc(client, token, method, params=None):
    headers = dict(HEADERS)
    if token is not None:
        headers['Authorization'] = 'Bearer ' + token
    return client.post('/mcp', headers=headers,
                       json={'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})


def tool(client, token, name, **args):
    response = rpc(client, token, 'tools/call', {'name': name, 'arguments': args})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert 'error' not in payload, payload
    return json.loads(payload['result']['content'][0]['text'])


def test_auth_each_request_no_session_or_header_impersonation(setup):
    client, auth, a, b, ma, ta, mb, tb = setup
    assert rpc(client, None, 'tools/list').status_code == 401
    assert rpc(client, 'wrong', 'tools/list').status_code == 401
    headers = dict(HEADERS, **{'X-User-ID': a})
    assert client.post('/mcp', headers=headers, json={}).status_code == 401
    listed = rpc(client, ta, 'tools/list')
    assert listed.status_code == 200
    assert {t['name'] for t in listed.json()['result']['tools']} == NAMES
    me = client.get('/identity', headers={'Authorization': 'Bearer ' + ta})
    assert me.json()['owner'] == 'user:' + a
    assert ta not in me.text
    auth.revoke(ma['credential_id'])
    assert rpc(client, ta, 'tools/list').status_code == 401
    assert rpc(client, tb, 'tools/list').status_code == 200


def test_sdk_initialization_and_notification(setup):
    client, auth, a, b, ma, ta, mb, tb = setup
    response = rpc(client, ta, 'initialize', {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'acceptance', 'version': '1'}})
    assert response.status_code == 200
    assert 'tools' in response.json()['result']['capabilities']
    response = client.post('/mcp', headers=dict(HEADERS, Authorization='Bearer ' + ta),
                           json={'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    assert response.status_code == 202


def test_distinct_users_roundtrip_negative_acl_and_retry(setup):
    client, auth, a, b, ma, ta, mb, tb = setup
    room = tool(client, ta, 'rooms_create', title='acceptance')['room_id']
    assert tool(client, tb, 'rooms_read', room_id=room)['error'] == 'membership_required'
    assert tool(client, tb, 'rooms_send', room_id=room, text='no', client_message_id='no')['error'] == 'membership_required'
    first = tool(client, ta, 'rooms_send', room_id=room, text='A nonce', client_message_id='a')['message']
    assert tool(client, tb, 'rooms_join', room_id=room)['ok']
    assert tool(client, tb, 'rooms_read', room_id=room)['messages'][0]['id'] == first['id']
    payload = dict(room_id=room, text='B ack', client_message_id='b', reply_to=first['id'])
    reply = tool(client, tb, 'rooms_send', **payload)['message']
    assert reply['owner'] == 'user:' + b and reply['owner'] != first['owner']
    assert tool(client, tb, 'rooms_send', **payload)['replayed']
    assert tool(client, ta, 'rooms_read', room_id=room)['messages'][-1]['id'] == reply['id']
    assert tool(client, tb, 'rooms_delete_message', room_id=room, message_id=first['id'])['error'] == 'message_unavailable_or_not_yours'
    assert tool(client, tb, 'rooms_close', room_id=room)['error'] == 'not_room_owner'
    assert tool(client, tb, 'rooms_leave', room_id=room)['ok']
    assert tool(client, tb, 'rooms_read', room_id=room)['error'] == 'membership_required'
    assert tool(client, ta, 'rooms_close', room_id=room)['ok']


def test_scope_disabled_third_user_and_bounded_input(setup):
    client, auth, a, b, ma, ta, mb, tb = setup
    _, reader = auth.issue_token(a, scopes=['rooms:read'])
    assert tool(client, reader, 'rooms_list')['ok']
    assert tool(client, reader, 'rooms_create', title='no')['error'] == 'insufficient_scope'
    third = auth.create_user('C')['user_id']; _, tc = auth.issue_token(third)
    auth.disable(third)
    assert rpc(client, tc, 'tools/list').status_code == 401
    response = client.post('/mcp', headers=dict(HEADERS, Authorization='Bearer ' + ta), content='x' * 65537)
    assert response.status_code == 413
    response = client.post('/mcp?token=not-accepted', headers=dict(HEADERS, Authorization='Bearer ' + ta), json={})
    assert response.status_code == 400


def test_origin_and_host_rejected_by_sdk(setup):
    client, auth, a, b, ma, ta, mb, tb = setup
    payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}
    base = dict(HEADERS, Authorization='Bearer ' + ta)
    assert client.post('/mcp', headers=dict(base, Origin='https://evil.example'), json=payload).status_code in (400, 403, 421)
    assert client.post('/mcp', headers=dict(base, Host='evil.example'), json=payload).status_code in (400, 403, 421)


def test_concurrent_sdk_calls_do_not_mix_principals(setup):
    from concurrent.futures import ThreadPoolExecutor
    client, auth, a, b, ma, ta, mb, tb = setup
    def create(index):
        token, owner = (ta, a) if index % 2 == 0 else (tb, b)
        result = tool(client, token, 'rooms_create', title='concurrent-' + str(index))
        assert result['ok'] and result['owner'] == 'user:' + owner
        return result['room_id']
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(create, range(8)))
    assert len(set(ids)) == 8
