"""Anonymous read-only web catalog of OPEN rooms by topic tree. Temp SQLite only, no creds, no mutations."""
import json
import pytest
from starlette.testclient import TestClient
from mcp_rooms.identity import IdentityStore
from mcp_rooms.server import create_app
from mcp_rooms.store import RoomStore

RESOURCE = 'https://rooms.example/mcp'
HEADERS = {'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'}


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / 'rooms.db'
    auth = IdentityStore(RoomStore(path), RESOURCE)
    a = auth.create_user('A')['user_id']
    ma, ta = auth.issue_token(a)
    app = create_app(path, RESOURCE, public_rooms=True)
    with TestClient(app, base_url='https://rooms.example') as client:
        yield app, client, ta


def rpc(client, token, method, params=None):
    return client.post('/mcp', headers=dict(HEADERS, Authorization='Bearer ' + token),
                       json={'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})


def tool(client, token, name, **args):
    payload = rpc(client, token, 'tools/call', {'name': name, 'arguments': args}).json()
    assert 'error' not in payload, payload
    return json.loads(payload['result']['content'][0]['text'])


def test_public_rooms_shows_open_only_and_escapes(setup):
    app, client, ta = setup
    tool(client, ta, 'rooms_create', title='Открытый такси чат <script>', topic_id='taxi', visibility='open')
    tool(client, ta, 'rooms_create', title='Приватная доставка', topic_id='delivery', visibility='private')
    tool(client, ta, 'rooms_create', title='Легаси без темы')
    body = client.get('/rooms').text
    assert 'Открытый такси чат &lt;script&gt;' in body
    assert '<script>' not in body
    assert 'Приватная доставка' not in body
    assert 'Легаси' not in body


def test_public_rooms_topic_filter_and_sections(setup):
    app, client, ta = setup
    tool(client, ta, 'rooms_create', title='Такси открыт', topic_id='taxi', visibility='open')
    tool(client, ta, 'rooms_create', title='Работа открыт', topic_id='jobs', visibility='open')
    tool(client, ta, 'rooms_create', title='Такси приват', topic_id='taxi', visibility='private')
    taxi = client.get('/rooms/topic/taxi').text
    assert 'Такси открыт' in taxi and 'Работа открыт' not in taxi and 'Такси приват' not in taxi
    assert 'rooms/topic/taxi' in client.get('/rooms').text


def test_public_rooms_unknown_path_is_404_and_valid_topic_200(setup):
    app, client, ta = setup
    tool(client, ta, 'rooms_create', title='x', topic_id='taxi', visibility='open')
    assert client.get('/rooms/nope').status_code == 404  # not a topic route
    assert client.get('/rooms/topic/nosuch').status_code == 200  # valid topic id, no open rooms


def test_public_rooms_host_and_method_gates(setup):
    app, client, ta = setup
    tool(client, ta, 'rooms_create', title='x', topic_id='taxi', visibility='open')
    assert client.post('/rooms').status_code == 405
    assert client.get('/rooms', headers={'Host': '127.0.0.1:8765'}).status_code == 421
