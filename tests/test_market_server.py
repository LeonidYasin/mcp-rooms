"""Official SDK over in-process ASGI in CI; synthetic keys/data, no sockets or VPS."""
from dataclasses import replace
import json
import time
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import pytest
from starlette.testclient import TestClient
from mcp_rooms.identity import IdentityStore, LISTING_SCOPES
from mcp_rooms.store import RoomStore, RoomError
from mcp_rooms.draft_store import DraftStore
from mcp_rooms.media_files import PrivatePhotoFiles
from mcp_rooms.media_stage import MediaStageStore
from mcp_rooms.photo_drafts import PhotoDraftStore
from mcp_rooms.publication_store import PublicationStore
from mcp_rooms.market_adapter import MarketAdapter
from mcp_rooms.server import create_app
from test_media_stage import Worker
from test_draft_store import key
from test_server import RESOURCE, rpc, tool, NAMES

MARKET_NAMES={'listings_create','listings_get','listings_list_own','listings_categories','listings_update',
    'listings_set_photos','listings_archive','listings_preview','listings_confirm_publication',
    'listings_publish','listings_withdraw','listings_publication_status'}
CONTENT=dict(title='Synthetic item',description='Synthetic acceptance only; not a real sale.',
             category='things',kind='offer',modes=['shipping'])


@pytest.fixture
def market(tmp_path):
    now=[int(time.time()*1000)]
    store=RoomStore(tmp_path/'rooms.db',clock=lambda:now[0])
    auth=IdentityStore(store,RESOURCE,allow_listing_scopes=True)
    a=auth.create_user('A')['user_id']; b=auth.create_user('B')['user_id']
    ma,ta=auth.issue_token(a,scopes=sorted(LISTING_SCOPES))
    mb,tb=auth.issue_token(b,scopes=sorted(LISTING_SCOPES))
    mr,tr=auth.issue_token(a)
    drafts=DraftStore(store,RESOURCE); drafts.initialize()
    root=tmp_path/'derivatives';root.mkdir(mode=0o700)
    files=PrivatePhotoFiles(root)
    stages=MediaStageStore(drafts,files,Worker());stages.initialize()
    photos=PhotoDraftStore(stages);publisher=PublicationStore(photos);publisher.initialize()
    adapter=MarketAdapter(drafts,photos,publisher)
    with TestClient(create_app(store.path,RESOURCE,True,market=adapter),base_url='https://rooms.example') as client:
        yield SimpleNamespace(store=store,auth=auth,a=a,b=b,ma=ma,ta=ta,mb=mb,tb=tb,mr=mr,tr=tr,
            now=now,drafts=drafts,root=root,files=files,stages=stages,photos=photos,publisher=publisher,adapter=adapter,client=client)
    files.close()


def create(x,token=None,**kw):
    return tool(x.client,token or x.ta,'listings_create',content={**CONTENT,**kw},category_id='toilets',client_id=key())


def confirm(x,lid,preview=None):
    p=preview or tool(x.client,x.ta,'listings_preview',listing_id=lid)
    return tool(x.client,x.ta,'listings_confirm_publication',listing_id=lid,
        expected_revision=p['record']['listing']['revision'],preview_digest=p['digest'],consent=True,client_id=key())


def test_opt_in_twenty_tools_no_admin_or_upload_methods(market):
    x=market
    listed=rpc(x.client,x.ta,'tools/list').json()['result']['tools']
    assert {t['name'] for t in listed}==NAMES|MARKET_NAMES
    for t in listed:
        if t['name'] in MARKET_NAMES:
            schema=t['inputSchema']['properties']
            assert not {'owner','user_id','principal','resource','path','filename'} & schema.keys()
    assert x.client.post('/listings',headers={'Authorization':'Bearer '+x.ta},json={}).status_code==404
    assert x.client.post('/upload',headers={'Authorization':'Bearer '+x.ta},content=b'not-an-upload').status_code==404


def test_default_app_and_issuer_stay_rooms_only(market):
    x=market; default=IdentityStore(x.store,RESOURCE)
    assert default.authenticate(x.ta) is None and default.authenticate(x.tr)
    with pytest.raises(RoomError,match='invalid_scopes'):
        default.issue_token(x.a,scopes=['listings:read'])
    with TestClient(create_app(x.store.path,RESOURCE),base_url='https://rooms.example') as client:
        assert rpc(client,x.ta,'tools/list').status_code==401
        assert {t['name'] for t in rpc(client,x.tr,'tools/list').json()['result']['tools']}==NAMES


def test_actual_bearer_draft_workflow_and_cross_user_acl(market):
    x=market
    result=create(x);lid=result['listing']['id']
    assert result['ok'] and result['listing']['owner']=='user:'+x.a
    assert tool(x.client,x.ta,'listings_get',listing_id=lid)['listing']==result['listing']
    assert tool(x.client,x.tb,'listings_get',listing_id=lid)['error']=='draft_unavailable'
    assert tool(x.client,x.tb,'listings_publication_status',listing_id=lid)['error']=='draft_unavailable'
    own=tool(x.client,x.ta,'listings_list_own')
    assert len(own['listings'])==1
    categories=tool(x.client,x.ta,'listings_categories',parent_id='plumbing')
    assert categories['ok']
    updated=tool(x.client,x.ta,'listings_update',listing_id=lid,content={**CONTENT,'title':'Updated synthetic'},category_id='toilets',expected_revision=1,client_id=key())
    assert updated['ok'] and updated['listing']['revision']==2
    stale=tool(x.client,x.ta,'listings_update',listing_id=lid,content=CONTENT,category_id='toilets',expected_revision=1,client_id=key())
    assert stale['error']=='revision_conflict'


def test_real_sdk_photo_consent_publish_withdraw_and_status(market):
    x=market;lid=create(x)['listing']['id'];actor=x.auth.authenticate(x.ta)
    # Bytes staged only through trusted test fixture, not an HTTP/MCP upload route.
    photo=x.stages.stage(actor,lid,expected_revision=1,client_id=key(),payload=b'synthetic-original',declared_type='image/png')
    attached=tool(x.client,x.ta,'listings_set_photos',listing_id=lid,media_ids=[photo['media_id']],expected_revision=1,client_id=key())
    assert attached['ok'] and attached['listing']['revision']==2
    p=tool(x.client,x.ta,'listings_preview',listing_id=lid)
    assert p['card_preview']['photos'][0]['media_id']==photo['media_id']
    c=confirm(x,lid,p);assert c['ok'] and c['published'] is False
    command=key()
    first=tool(x.client,x.ta,'listings_publish',listing_id=lid,intent_id=c['intent_id'],client_id=command)
    assert first['ok'] and first['publication_revision']==1
    assert x.publisher.public_get(lid)['title']==CONTENT['title']
    denied=tool(x.client,x.ta,'listings_archive',listing_id=lid,expected_revision=2,client_id=key())
    assert denied['error']=='unpublish_before_edit'
    assert tool(x.client,x.tb,'listings_withdraw',listing_id=lid,expected_publication_revision=1,client_id=key())['error']=='publication_unavailable'
    assert tool(x.client,x.ta,'listings_withdraw',listing_id=lid,expected_publication_revision=1,client_id=key())['ok']
    retry=tool(x.client,x.ta,'listings_publish',listing_id=lid,intent_id=c['intent_id'],client_id=command)
    assert retry['replayed'] and retry['state']=='active'  # Historical receipt only.
    status=tool(x.client,x.ta,'listings_publication_status',listing_id=lid)
    assert status['publication']['state']=='withdrawn' and status['publication']['publication_revision']==2
    assert tool(x.client,x.ta,'listings_archive',listing_id=lid,expected_revision=2,client_id=key())['ok']


def test_rooms_and_read_keys_do_not_gain_market_write_or_publish(market):
    x=market;lid=create(x)['listing']['id']
    assert tool(x.client,x.tr,'listings_get',listing_id=lid)['error']=='insufficient_scope'
    assert create(x,x.tr)['error']=='insufficient_scope'
    _,read=x.auth.issue_token(x.a,scopes=['listings:read'])
    assert tool(x.client,read,'listings_get',listing_id=lid)['ok']
    assert create(x,read)['error']=='insufficient_scope'
    p=tool(x.client,read,'listings_preview',listing_id=lid)
    assert tool(x.client,read,'listings_confirm_publication',listing_id=lid,expected_revision=1,
        preview_digest=p['digest'],consent=True,client_id=key())['error']=='insufficient_scope'
    assert tool(x.client,x.ta,'rooms_list')['error']=='insufficient_scope'


def test_enrollment_does_not_implicitly_grant_listings(market):
    x=market; response=x.client.post('/register',json={})
    assert response.status_code==201
    raw=response.json()['server_key']['key']
    actor=x.auth.authenticate(raw)
    assert actor.scopes==frozenset({'rooms:read','rooms:write'})
    assert create(x,raw)['error']=='insufficient_scope'


@pytest.mark.parametrize('change',['revoke','disable','expiry','resource','scope'])
def test_persisted_grants_checked_on_each_request(market,change):
    x=market;lid=create(x)['listing']['id'];expected=401
    if change=='revoke':x.auth.revoke(x.ma['credential_id'])
    elif change=='disable':x.auth.disable(x.a)
    elif change=='expiry':x.now[0]=x.ma['expires_at']*1000
    elif change=='resource':
        with x.store._db(write=True) as db:db.execute("UPDATE credentials SET resource='https://other.example/mcp' WHERE id=?",(x.ma['credential_id'],))
    else:
        with x.store._db(write=True) as db:db.execute("UPDATE credentials SET scopes='[\"rooms:read\"]' WHERE id=?",(x.ma['credential_id'],))
        expected=200
    response=rpc(x.client,x.ta,'tools/call',{'name':'listings_get','arguments':{'listing_id':lid}})
    assert response.status_code==expected
    if expected==200:assert json.loads(response.json()['result']['content'][0]['text'])['error']=='insufficient_scope'


def test_concurrent_connections_do_not_mix_market_owners(market):
    x=market
    def action(i):
        token,owner=(x.ta,x.a) if i%2==0 else (x.tb,x.b)
        result=create(x,token,title='Concurrent '+str(i))
        assert result['ok'] and result['listing']['owner']=='user:'+owner
        return result['listing']['id']
    with ThreadPoolExecutor(max_workers=4) as pool:ids=list(pool.map(action,range(8)))
    assert len(set(ids))==8


def test_content_rejects_impersonation_and_coercion(market):
    x=market
    for change in ({'owner':'user:'+x.b},{'media_ids':[key()]},{'price_minor':True},{'title':123}):
        response=rpc(x.client,x.ta,'tools/call',{'name':'listings_create','arguments':
            {'content':{**CONTENT,**change},'category_id':'toilets','client_id':key()}})
        assert response.status_code==200
        assert response.json()['result'].get('isError') is True
    with x.store._db() as db:assert db.execute('SELECT COUNT(*) FROM market_drafts').fetchone()[0]==0


def test_adapter_direct_calls_recheck_and_deny_injected_actor_fields(market,monkeypatch,caplog):
    x=market;actor=x.auth.authenticate(x.ta)
    assert x.adapter.execute(actor,'create',content=CONTENT,category_id='toilets',client_id=key(),user_id=x.b)['error']=='invalid_arguments'
    assert x.adapter.execute(actor,'run_python')['error']=='method_unavailable'
    assert x.adapter.execute(None,'categories')['error']=='authentication_required'
    def fail(*a,**kw):raise OSError('PRIVATE-PATH-AND-KEY '+x.ta)
    monkeypatch.setattr(x.drafts,'get',fail)
    result=x.adapter.execute(actor,'get',listing_id=key())
    assert result['error']=='market_storage_unavailable' and x.ta not in str(result)+caplog.text


def test_wrong_bundle_or_resource_cannot_bind_to_app(market,tmp_path):
    x=market
    for path,resource in ((tmp_path/'other.db',RESOURCE),(x.store.path,'https://other.example/mcp')):
        with pytest.raises(RoomError,match='market_binding_mismatch'):create_app(path,resource,market=x.adapter)
    with pytest.raises(RoomError,match='market_binding_mismatch'):create_app(x.store.path,RESOURCE,market=object())


def test_missing_namespace_refused_without_startup_migration(market):
    x=market
    with x.store._db(write=True) as db:db.execute('DROP TABLE publication_audit')
    with pytest.raises(RoomError,match='unsupported_publication_schema'):create_app(x.store.path,RESOURCE,market=x.adapter)
    with x.store._db() as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='publication_audit'").fetchone()
