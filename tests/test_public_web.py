"""In-process synthetic CI; never deploy or issue real credentials."""
import pytest
from starlette.testclient import TestClient
from mcp_rooms.server import create_app
from mcp_rooms.store import RoomError
from mcp_rooms.public_web import render_card, STYLE_HASH
from test_market_server import market, create, confirm
from test_server import RESOURCE, tool
from test_draft_store import key


@pytest.fixture
def web(market):
    x=market
    with TestClient(create_app(x.store.path,RESOURCE,market=x.adapter,public_market=True),
                    base_url='https://rooms.example') as client:
        yield x,client


def publish(x,**changes):
    lid=create(x,**changes)['listing']['id']
    actor=x.auth.authenticate(x.ta)
    photo=x.stages.stage(actor,lid,expected_revision=1,client_id=key(),payload=b'synthetic',declared_type='image/png')
    assert tool(x.client,x.ta,'listings_set_photos',listing_id=lid,media_ids=[photo['media_id']],expected_revision=1,client_id=key())['ok']
    intent=confirm(x,lid)
    result=tool(x.client,x.ta,'listings_publish',listing_id=lid,intent_id=intent['intent_id'],client_id=key())
    assert result['ok']
    return lid,photo['media_id'],result['publication_revision']


def test_mcp_publish_anonymous_card_photo_and_withdraw(web):
    x,c=web;lid,mid,epoch=publish(x,price_minor=123456,currency='RUB',locality='Synthetic city')
    path='/market/'+lid
    response=c.get(path,headers={'Sec-Fetch-Site':'cross-site','Sec-Fetch-Mode':'navigate','Sec-Fetch-Dest':'document'})
    assert response.status_code==200
    assert '1 234,56 RUB' in response.text and 'Synthetic city' in response.text
    assert 'viewport' in response.text and 'loading="lazy"' in response.text
    assert not response.cookies and 'set-cookie' not in response.headers
    for secret in (x.ta,x.a,x.ma['credential_id']):assert secret not in response.text
    url=f'{path}/photos/{epoch}/{mid}.jpg'
    assert url in response.text
    photo=c.get(url);assert photo.status_code==200 and photo.headers['content-type']=='image/jpeg'
    assert photo.content==x.publisher.public_photo(lid,epoch,mid)
    assert c.get(f'{path}/photos/{epoch+1}/{mid}.jpg').status_code==404
    assert tool(x.client,x.tb,'listings_withdraw',listing_id=lid,expected_publication_revision=epoch,client_id=key())['error']=='publication_unavailable'
    assert c.get(path).status_code==200
    assert tool(x.client,x.ta,'listings_withdraw',listing_id=lid,expected_publication_revision=epoch,client_id=key())['ok']
    assert c.get(path).status_code==c.get(url).status_code==404


def test_private_unknown_missing_corrupt_and_disabled_are_uniform(web):
    x,c=web;private=create(x)['listing']['id']
    missing=c.get('/market/'+key())
    assert missing.status_code==404
    assert c.get('/market/'+private).content==missing.content
    lid,mid,epoch=publish(x)
    x.auth.disable(x.a)
    for path in ('/market/'+lid,f'/market/{lid}/photos/{epoch}/{mid}.jpg'):
        response=c.get(path);assert response.status_code==404 and response.content==missing.content


def test_untrusted_plain_text_and_security_headers(web):
    x,c=web;lid,_,_=publish(x,title='<script>bad()</script>',description='<img src=x onerror=bad()> & https://evil.example')
    response=c.get('/market/'+lid)
    assert response.status_code==200
    assert '<script>' not in response.text and '<img src=x' not in response.text
    assert '&lt;script&gt;' in response.text and '&lt;img src=x' in response.text
    assert '<a href="https://evil.example' not in response.text
    for name,value in {'cache-control':'no-store','x-content-type-options':'nosniff',
                       'referrer-policy':'no-referrer','cross-origin-resource-policy':'same-origin'}.items():
        assert response.headers[name]==value
    assert STYLE_HASH in response.headers['content-security-policy']
    assert 'unsafe-inline' not in response.headers['content-security-policy']
    assert 'access-control-allow-origin' not in response.headers
    assert 'noindex' in response.headers['x-robots-tag']


@pytest.mark.parametrize('method',['POST','PUT','PATCH','DELETE','HEAD','OPTIONS'])
def test_read_only_even_with_valid_bearer(web,method):
    x,c=web;lid,_,_=publish(x)
    response=c.request(method,'/market/'+lid,headers={'Authorization':'Bearer '+x.ta},json={'owner':x.a})
    assert response.status_code==405 and response.headers['allow']=='GET'
    assert x.publisher.public_get(lid)


@pytest.mark.parametrize('path',['/market','/market/','/market/search','/market/../../identity','/market/'+('a'*500)])
def test_no_feed_search_traversal_or_error_details(web,path):
    x,c=web;response=c.get(path)
    assert response.status_code in (401,404)
    assert x.a not in response.text and 'Traceback' not in response.text


def test_opt_in_and_binding(market):
    x=market;lid,_,_=publish(x)
    assert x.client.get('/market/'+lid).status_code==404
    for kwargs in ({'public_market':True},{'market':x.adapter,'public_market':1}):
        with pytest.raises(RoomError,match='market_binding_mismatch'):
            create_app(x.store.path,RESOURCE,**kwargs)


def test_public_does_not_accept_wrong_host_or_query_or_enable_cookie_writes(web):
    x,c=web;lid,_,_=publish(x);path='/market/'+lid
    assert c.get(path,headers={'Host':'127.0.0.1:8765'}).status_code==421
    assert c.get(path+'?token=not-a-key').status_code==400
    # Credentials (including invalid ones) do not affect public data or grant private access.
    assert c.get(path,headers={'Authorization':'Bearer invalid','Cookie':'__Host-mcp-rooms-session=invalid'}).status_code==200
    assert c.get('/identity',headers={'Cookie':'__Host-mcp-rooms-session=invalid'}).status_code==401
    assert c.post('/browser/session',json={}).status_code==404


def test_global_budget_and_immediate_admission(web):
    x,c=web;lid,_,_=publish(x);path='/market/'+lid
    handler=c.app.public_market
    with handler.admission.slot('public'),handler.admission.slot('public'):
        assert c.get(path).status_code==429
    assert c.get(path).status_code==200
    with handler.lock:handler.count=120
    assert c.get(path).status_code==429


def test_sanitized_unexpected_failure(web,monkeypatch):
    x,c=web;lid,_,_=publish(x)
    def fail(*args):raise RuntimeError('private database path and secret')
    monkeypatch.setattr(x.publisher,'public_get',fail)
    response=c.get('/market/'+lid)
    assert response.status_code==503 and 'secret' not in response.text


def test_missing_file_after_publication(web):
    x,c=web;lid,mid,epoch=publish(x)
    # Simulated damaged file: public core must fail closed, not render stale card.
    for file in x.root.iterdir():
        if file.is_file() and not file.name.startswith('.'):
            file.unlink()
    assert c.get('/market/'+lid).status_code==404
    assert c.get(f'/market/{lid}/photos/{epoch}/{mid}.jpg').status_code==404


def test_prefix_links_are_derived_only_from_trusted_resource(web):
    x,c=web;lid,_,_=publish(x)
    card=x.publisher.public_get(lid)
    html=render_card(card,'/rooms-test')
    assert 'src="/rooms-test/market/' in html
    assert 'src="/market/' not in html


def test_fulfilment_modes_are_visible(web):
    x,c=web
    lid,_,_=publish(x,modes=['pickup','shipping','online'],locality='Synthetic town')
    response=c.get('/market/'+lid)
    assert response.status_code==200 and 'Самовывоз · Доставка · Онлайн' in response.text


def test_v1_consent_cannot_authorize_v2_publication(web):
    x,c=web;lid=create(x)['listing']['id']
    intent=confirm(x,lid)
    with x.store._db(write=True) as db:
        db.execute("UPDATE publication_consents SET schema='mcp-rooms/live-publication-consent/v1' WHERE intent_id=?",(intent['intent_id'],))
    result=tool(x.client,x.ta,'listings_publish',listing_id=lid,intent_id=intent['intent_id'],client_id=key())
    assert result['error']=='publication_consent_unavailable'
    assert c.get('/market/'+lid).status_code==404
