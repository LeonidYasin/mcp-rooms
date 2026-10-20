"""CI-only synthetic ASGI browser session bridge. No live cookies or account signup."""
from types import SimpleNamespace
import anyio
import pytest
from starlette.testclient import TestClient
from mcp_rooms import browser_http as bh
from mcp_rooms.browser_sessions import BrowserSessions
from mcp_rooms.domain import DomainError
from mcp_rooms.server import create_app
from test_market_server import market, create
from test_media_http import direct
from test_server import RESOURCE, rpc


@pytest.fixture
def web(market):
    x=market;sessions=BrowserSessions(x.drafts);sessions.initialize()
    gate=create_app(x.store.path,RESOURCE,market=x.adapter,media_http=True,browser_sessions=sessions)
    with TestClient(gate,base_url='https://rooms.example') as client:
        yield SimpleNamespace(**{**vars(x),'sessions':sessions,'client':client,'gate':gate})


def headers(x,token=None,**extra):
    return {'Origin':'https://rooms.example','Authorization':'Bearer '+(token or x.ta),
            'Content-Type':'application/json',**extra}


def login(x,**kwargs):
    return x.client.post(bh.PATH,headers=headers(x),json=kwargs)


def test_explicit_composition_and_no_startup_migration(market):
    x=market
    assert x.client.post(bh.PATH,headers=headers(x),json={}).status_code==404
    with pytest.raises(DomainError,match='browser_binding_mismatch'):
        create_app(x.store.path.parent/'absent.db',RESOURCE,browser_sessions=True)
    assert not (x.store.path.parent/'absent.db').exists()
    sessions=BrowserSessions(x.drafts)
    with pytest.raises(DomainError,match='browser_migration_required'):
        create_app(x.store.path,RESOURCE,market=x.adapter,browser_sessions=sessions)
    with x.store._db() as db:
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='browser_sessions'").fetchone()


def test_login_cookie_bootstrap_and_no_secret_json(web):
    x=web;r=login(x);assert r.status_code==201,r.text
    body=r.json();raw=x.client.cookies.get(bh.COOKIE)
    assert body['scopes']==['listings:read'] and body['owner']=='user:'+x.a
    assert raw.startswith('bs1_') and raw not in r.text and x.ta not in r.text
    assert not {'credential_id','cookie','key','session_id'} & body.keys()
    attrs=r.headers['set-cookie']
    for flag in ('HttpOnly','Secure','SameSite=strict','Path=/','Max-Age='):assert flag in attrs
    assert 'Domain=' not in attrs and '__Host-' in attrs
    result=x.client.get(bh.PATH,headers={'Origin':'https://rooms.example'})
    assert result.status_code==200 and result.json()==body
    assert result.headers['cache-control']=='no-store' and result.headers['x-content-type-options']=='nosniff'
    assert 'access-control-allow-origin' not in result.headers and 'set-cookie' not in result.headers


def test_explicit_scope_subset_and_session_namespace(web):
    x=web;r=login(x,scopes=['listings:read','listings:write'])
    assert r.status_code==201 and r.json()['scopes']==['listings:read','listings:write']
    raw=x.client.cookies.get(bh.COOKIE)
    assert rpc(x.client,raw,'tools/list').status_code==401
    assert x.client.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/list'}).status_code==401
    assert x.client.get('/identity').status_code==401
    assert x.client.post('/admin/mcp').status_code==404
    # An agent route is not silently made cookie-authenticated.
    lid=create(x)['listing']['id']
    assert x.client.post('/listings/'+lid+'/photos',content=b'no implicit browser upload').status_code==401


def test_logout_csrf_and_parent_key_survives(web):
    x=web;r=login(x);csrf=r.json()['csrf_token'];raw=x.client.cookies.get(bh.COOKIE)
    for h in ({'Origin':'https://rooms.example'}, {'Origin':'https://rooms.example','X-CSRF-Token':'0'*64}):
        assert x.client.delete(bh.PATH,headers=h).status_code==403
    r=x.client.delete(bh.PATH,headers={'Origin':'https://rooms.example','X-CSRF-Token':csrf})
    assert r.status_code==200 and r.json()['revoked'] and x.client.cookies.get(bh.COOKIE) is None
    assert x.auth.authenticate(x.ta) and rpc(x.client,x.ta,'tools/list').status_code==200
    with pytest.raises(DomainError,match='browser_session_required'):x.sessions.resolve(raw)


@pytest.mark.parametrize('origin',[None,'null','https://other.example','https://sub.rooms.example'])
def test_login_origin_before_auth_and_body(web,origin):
    x=web;h=headers(x)
    if origin is None:h.pop('Origin')
    else:h['Origin']=origin
    assert direct(x,bh.PATH,[],list(h.items()))[0]==403


def test_no_origin_get_requires_exact_same_origin_fetch_metadata(web):
    x=web;login(x)
    assert x.client.get(bh.PATH).status_code==403
    h={'Sec-Fetch-Site':'same-origin','Sec-Fetch-Mode':'same-origin','Sec-Fetch-Dest':'empty'}
    assert x.client.get(bh.PATH,headers=h).status_code==200
    h['Sec-Fetch-Site']='same-site'
    assert x.client.get(bh.PATH,headers=h).status_code==403


@pytest.mark.parametrize('extra',[
    {'Sec-Fetch-Site':'cross-site'},{'Sec-Fetch-Site':'same-site'},
    {'Sec-Fetch-Mode':'navigate'}, {'Origin':'https://rooms.example.evil.test'},
])
def test_fetch_metadata_denials(web,extra):
    x=web
    assert direct(x,bh.PATH,[],list(headers(x,**extra).items()))[0]==403


def test_clear_insecure_transport_even_forwarded_https(web):
    x=web
    insecure_gate=create_app(x.store.path,RESOURCE,market=x.adapter,browser_sessions=x.sessions)
    with TestClient(insecure_gate,base_url='http://rooms.example') as client:
        r=client.post(bh.PATH,headers=headers(x,**{'X-Forwarded-Proto':'https'}),json={})
        assert r.status_code==400 and r.json()['error']=='browser_https_required'
    h=list(headers(x).items())
    h.append(('Host','localhost:8765'))
    assert direct(x,bh.PATH,[],h)[0] in (400,421)


def test_existing_cookie_requires_logout_no_silent_account_switch(web):
    x=web;first=login(x);assert first.status_code==201
    assert x.client.post(bh.PATH,headers=headers(x,x.tb),json={}).status_code==409
    assert x.client.get(bh.PATH,headers={'Origin':'https://rooms.example'}).json()['user_id']==x.a


def test_csrf_bound_to_session_and_duplicates_rejected(web):
    x=web;one=login(x);raw=x.client.cookies.get(bh.COOKIE);x.client.cookies.clear()
    two=login(x)
    assert one.json()['csrf_token']!=two.json()['csrf_token']
    h={'Origin':'https://rooms.example','X-CSRF-Token':one.json()['csrf_token']}
    assert x.client.delete(bh.PATH,headers=h).status_code==403
    h=[('Origin','https://rooms.example'),('Cookie',bh.COOKIE+'='+raw+'; '+bh.COOKIE+'='+raw)]
    assert direct(x,bh.PATH,[],h,method='GET')[0]==400
    h=[('Origin','https://rooms.example'),('Cookie',bh.COOKIE+'='+raw),('Cookie','unrelated=x')]
    assert direct(x,bh.PATH,[],h,method='GET')[0]==400


@pytest.mark.parametrize('change',['revoke','disable','idle'])
def test_parent_or_session_invalidates_bootstrap_and_clears_cookie(web,change):
    x=web;login(x)
    if change=='revoke':x.auth.revoke(x.ma['credential_id'])
    elif change=='disable':x.auth.disable(x.a)
    else:x.now[0]+=900000
    r=x.client.get(bh.PATH,headers={'Origin':'https://rooms.example'})
    assert r.status_code==401 and 'Max-Age=0' in r.headers['set-cookie']
    assert x.client.cookies.get(bh.COOKIE) is None


def test_logout_after_parent_revocation_remains_possible(web):
    x=web;r=login(x);x.auth.revoke(x.ma['credential_id'])
    assert x.client.delete(bh.PATH,headers={'Origin':'https://rooms.example',
        'X-CSRF-Token':r.json()['csrf_token']}).status_code==200


@pytest.mark.parametrize('payload',[
    {'scopes':['rooms:read']},{'scopes':['admin:write']},{'scopes':[]},
    {'scopes':['listings:read','listings:read']},{'scopes':'listings:read'},
    {'user_id':'pretend'},{'ttl_seconds':7776000},{'scopes':['listings:read'],'owner':'pretend'},
])
def test_no_client_authority_or_unknown_login_arguments(web,payload):
    x=web;r=x.client.post(bh.PATH,headers=headers(x),json=payload)
    assert r.status_code==400 and 'set-cookie' not in r.headers


def test_room_only_key_cannot_make_market_session(web):
    x=web;r=x.client.post(bh.PATH,headers=headers(x,x.tr),json={})
    assert r.status_code==403 and 'set-cookie' not in r.headers


def test_duplicate_json_and_encoding_transport(web):
    x=web
    for data in (b'{"scopes":["listings:read"],"scopes":["listings:write"]}',b'\xff',b'{}x'):
        r=x.client.post(bh.PATH,headers=headers(x),content=data)
        assert r.status_code==400
    assert x.client.post(bh.PATH,headers=headers(x),json={}).status_code==429  # per-key budget


def test_auth_before_body_and_mixed_credentials_rejected(web):
    x=web
    assert direct(x,bh.PATH,[],[('Origin','https://rooms.example'),('Authorization','Bearer invalid')])[0]==401
    login(x)
    assert x.client.get(bh.PATH,headers=headers(x)).status_code==400
    assert x.client.delete(bh.PATH,headers=headers(x)).status_code==400


@pytest.mark.parametrize('extra,status',[
    ({'Content-Type':'text/plain'},415),({'Content-Length':'1025'},413),
    ({'Content-Length':'01'},400),({'Transfer-Encoding':'gzip'},400),
    ({'Content-Encoding':'gzip'},400),
])
def test_login_header_rejections_before_body(web,extra,status):
    x=web
    assert direct(x,bh.PATH,[],list(headers(x,**extra).items()))[0]==status


def test_stream_limit_disconnect_mismatch_and_timeout(web,monkeypatch):
    x=web;monkeypatch.setattr(bh,'MAX_BODY',8)
    events=[{'type':'http.request','body':b'12345','more_body':True},
            {'type':'http.request','body':b'6789','more_body':False}]
    assert direct(x,bh.PATH,events,list(headers(x).items()))[0]==413
    assert direct(x,bh.PATH,[{'type':'http.disconnect'}],list(headers(x).items()))[0]==400
    assert direct(x,bh.PATH,[{'type':'http.request','body':b'{}'}],list(headers(x,**{'Content-Length':'3'}).items()))[0]==400
    # Refresh fixed window so malformed attempt tests do not hide timeout handling.
    x.gate.browser_http.budget.window=None
    monkeypatch.setattr(bh,'BODY_TIMEOUT_SECONDS',0.01)
    async def slow():
        await anyio.sleep(1)
        return {'type':'http.request','body':b'{}'}
    assert direct(x,bh.PATH,[slow],list(headers(x).items()))[0]==408


def test_revoked_while_receiving_body_cannot_create_cookie(web):
    x=web
    async def revoke():
        x.auth.revoke(x.ma['credential_id'])
        return {'type':'http.request','body':b'{}'}
    assert direct(x,bh.PATH,[revoke],list(headers(x).items()))[0]==401
    with x.store._db() as db:assert db.execute('SELECT COUNT(*) FROM browser_sessions').fetchone()[0]==0


def test_bounded_login_budgets_and_reset(web):
    x=web;budget=x.gate.browser_http.budget;clock=[1.0];budget.clock=lambda:clock[0]
    for _ in range(3):
        assert login(x).status_code==201;x.client.cookies.clear()
    r=login(x);assert r.status_code==429 and r.headers['retry-after']=='60'
    clock[0]+=60
    assert login(x).status_code==201


def test_invalid_key_global_budget(web):
    x=web
    for _ in range(20):
        assert x.client.post(bh.PATH,headers=headers(x,'invalid'),json={}).status_code==401
    assert x.client.post(bh.PATH,headers=headers(x,'invalid'),json={}).status_code==429


def test_bounded_route_admission(web):
    x=web;slots=x.gate.browser_http.slots
    for _ in range(8):assert slots.acquire(blocking=False)
    try:assert login(x).status_code==429
    finally:
        for _ in range(8):slots.release()
    assert login(x).status_code==201


def test_unknown_method_no_cors_and_no_body_reads(web):
    x=web
    status,_=direct(x,bh.PATH,[],[('Origin','https://rooms.example')],method='OPTIONS')
    assert status==405
    login(x)
    assert x.client.request('GET',bh.PATH,headers={'Origin':'https://rooms.example'},content=b'{}').status_code==400


def test_transport_send_failure_releases_admission_without_second_response(web):
    x=web;login(x);raw=x.client.cookies.get(bh.COOKIE);starts=[]
    async def run():
        async def receive():raise AssertionError('GET must not read body')
        async def send(event):
            if event['type']=='http.response.start':starts.append(event)
            else:raise TimeoutError('synthetic send timeout')
        await x.gate({'type':'http','method':'GET','scheme':'https','path':bh.PATH,'query_string':b'',
            'headers':[(b'host',b'rooms.example'),(b'origin',b'https://rooms.example'),
                       (b'cookie',(bh.COOKIE+'='+raw).encode())]},receive,send)
    with pytest.raises(TimeoutError):anyio.run(run)
    assert len(starts)==1
    assert x.client.get(bh.PATH,headers={'Origin':'https://rooms.example'}).status_code==200
