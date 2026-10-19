"""Local Flask test-client + fake upstream only. No Qwen/VPS/network/real keys."""
import ast
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
CLIENT=ROOT/'clients/qwen'
TOKEN='rm1_'+'a'*32+'.'+'b'*43  # synthetic shape only, never a real issued key
PRIVATE_TEXT='synthetic-private-message-canary'
PRIVATE_SESSION='synthetic-private-session-canary'

@pytest.fixture
def proxy():
    path=CLIENT/'mcp_proxy_v2.py'
    spec=importlib.util.spec_from_file_location('qwen_proxy_contract',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

class FakeResponse:
    def __init__(self,status=200,body=b'{"ok":true}',headers=None):
        self.status_code=status;self.body=body
        self.headers={'content-type':'application/json',**(headers or {})};self.closed=False
    def iter_content(self,chunk_size):yield self.body
    def close(self):self.closed=True

class FakeSession:
    def __init__(self,response,calls):self.response=response;self.calls=calls;self.closed=False
    def request(self,**kwargs):self.calls.append(kwargs);return self.response
    def close(self):self.closed=True

def setup(proxy,monkeypatch,response=None):
    calls=[];response=response or FakeResponse();session=FakeSession(response,calls)
    monkeypatch.setattr(proxy.req,'Session',lambda:session)
    app=proxy.make_app('rooms','https://rooms.example/mcp',{'Authorization':'Bearer '+TOKEN},debug=True)
    return app.test_client(),calls,response,session

def test_static_auth_forwarding_and_sanitized_trace(proxy,monkeypatch,capsys):
    client,calls,response,session=setup(proxy,monkeypatch)
    result=client.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/call',
        'params':{'name':'rooms_send','arguments':{'text':PRIVATE_TEXT}}},
        headers={'Authorization':'Bearer CLIENT_MUST_NOT_OVERRIDE','Mcp-Session-Id':PRIVATE_SESSION})
    assert result.status_code==200
    assert calls[0]['headers']['Authorization']=='Bearer '+TOKEN
    assert calls[0]['headers']['Mcp-Session-Id']==PRIVATE_SESSION
    assert calls[0]['allow_redirects'] is False
    assert response.closed and session.closed
    log=capsys.readouterr().out
    assert TOKEN not in log and PRIVATE_TEXT not in log and PRIVATE_SESSION not in log
    assert 'CLIENT_MUST_NOT_OVERRIDE' not in log
    assert '"static_authorization_present": true' in log
    assert '"rooms_token_format_ok": true' in log
    assert '"tool": "rooms_send"' in log

def test_qwen_missing_client_auth_is_expected(proxy,monkeypatch,capsys):
    client,calls,_,_=setup(proxy,monkeypatch)
    assert client.post('/mcp',json={'method':'initialize'}).status_code==200
    assert calls[0]['headers']['Authorization']=='Bearer '+TOKEN
    assert '"client_authorization_present": false' in capsys.readouterr().out

def test_redirect_not_followed_or_logged(proxy,monkeypatch,capsys):
    response=FakeResponse(302,headers={'Location':'https://elsewhere.example/?key='+TOKEN})
    client,calls,_,session=setup(proxy,monkeypatch,response)
    result=client.post('/mcp',json={'method':'initialize'})
    assert result.status_code==502
    assert result.json['error']=='upstream_redirect_blocked'
    assert len(calls)==1 and response.closed and session.closed
    log=capsys.readouterr().out
    assert TOKEN not in log and 'elsewhere.example' not in log

def test_network_exception_text_never_logged(proxy,monkeypatch,capsys):
    client,calls,_,session=setup(proxy,monkeypatch)
    def fail(**kwargs):raise ValueError('bad header '+TOKEN)
    monkeypatch.setattr(session,'request',fail)
    result=client.post('/mcp',json={'method':'initialize'})
    assert result.status_code==502 and result.json['error']=='upstream_request_failed'
    assert TOKEN not in capsys.readouterr().out

def test_large_request_rejected_before_upstream(proxy,monkeypatch):
    client,calls,_,_=setup(proxy,monkeypatch)
    assert client.post('/mcp',data=b'x'*65537).status_code==413
    assert calls==[]

def test_large_response_capped(proxy,monkeypatch):
    client,calls,response,session=setup(proxy,monkeypatch,FakeResponse(body=b'x'*(4*1024*1024+1)))
    assert client.post('/mcp',json={'method':'initialize'}).status_code==502
    assert response.closed and session.closed

def test_sse_closes_upstream(proxy,monkeypatch,capsys):
    client,calls,response,session=setup(proxy,monkeypatch,
        FakeResponse(body=b'data: {}\n\n',headers={'content-type':'text/event-stream'}))
    result=client.get('/mcp',buffered=True)
    assert result.status_code==200 and b'data:' in result.data
    result.close()
    assert response.closed and session.closed
    assert 'stream_closed' in capsys.readouterr().out

def test_auth_error_code_logged_without_error_body(proxy,monkeypatch,capsys):
    body=json.dumps({'error':'invalid_token','private':PRIVATE_TEXT}).encode()
    client,_,_,_=setup(proxy,monkeypatch,FakeResponse(401,body))
    assert client.post('/mcp',json={'method':'initialize'}).status_code==401
    log=capsys.readouterr().out
    assert 'invalid_token' in log and PRIVATE_TEXT not in log

def test_env_parses_static_header_without_echo(proxy,tmp_path,capsys):
    env=tmp_path/'.env';env.write_text('ROOMS_UPSTREAM=https://rooms.example/mcp\n'
        +'ROOMS_HEADERS="Authorization=Bearer '+TOKEN+'"\nROOMS_PORT=8790\n')
    config=proxy.load_servers(env)
    assert config['rooms']['headers']['Authorization']=='Bearer '+TOKEN
    assert config['rooms']['port']==8790
    assert TOKEN not in capsys.readouterr().out

def test_examples_contain_no_real_secret_and_scripts_parse():
    example=(CLIENT/'.env.example').read_text()
    assert 'REPLACE_LOCALLY' in example
    config=json.loads((CLIENT/'qwen-local.json').read_text())
    assert config['mcpServers']['rooms-via-local-proxy']['url']=='http://127.0.0.1:8790/mcp'
    assert 'Authorization' not in json.dumps(config)
    for name in ('mcp_proxy_v2.py','check_rooms_proxy.py'):ast.parse((CLIENT/name).read_text())
