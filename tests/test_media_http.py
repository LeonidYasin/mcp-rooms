"""CI-only synthetic ASGI acceptance; never a live upload or VPS operation."""
from types import SimpleNamespace
import anyio
import pytest
from starlette.testclient import TestClient
from mcp_rooms import media_http as mh
from mcp_rooms.domain import DomainError
from mcp_rooms.server import create_app
from mcp_rooms.store import RoomError
from test_market_server import market, create
from test_draft_store import key
from test_server import RESOURCE, tool


@pytest.fixture
def http(market):
    x = market
    gate = create_app(x.store.path, RESOURCE, market=x.adapter, media_http=True)
    with TestClient(gate, base_url='https://rooms.example') as client:
        yield SimpleNamespace(**{**vars(x), 'client': client, 'gate': gate})


def headers(x, **extra):
    return {'Authorization': 'Bearer '+x.ta, 'Content-Type': 'image/png',
            'X-Expected-Revision': '1', 'Idempotency-Key': key(), **extra}


def path(lid, mid=None):
    return '/listings/'+lid+'/photos'+('/'+mid if mid else '')


def upload(x, lid, data=b'synthetic-original', **extra):
    return x.client.post(path(lid), headers=headers(x, **extra), content=data)


def direct(x, url, events, hdrs, method='POST'):
    sent = []
    async def run():
        async def receive():
            if not events:
                raise AssertionError('body must not be read')
            event = events.pop(0)
            if callable(event):
                return await event()
            return event
        async def send(event):
            sent.append(event)
        await x.gate({'type':'http','asgi':{'version':'3.0'},'http_version':'1.1',
            'scheme':'https','server':('rooms.example',443),'client':('127.0.0.1',1234),
            'method':method,'path':url,'raw_path':url.encode(),'query_string':b'',
            'headers':[(b'host',b'rooms.example')]+[(k.lower().encode(),v.encode()) for k,v in hdrs]}, receive, send)
    anyio.run(run)
    return sent[0]['status'], b''.join(e.get('body',b'') for e in sent[1:])


def test_opt_in_and_config_fail_closed(market):
    x=market;lid=create(x)['listing']['id']
    assert upload(x,lid).status_code==404
    for value in (True, 'yes', 1):
        with pytest.raises(RoomError):
            create_app(x.store.path.parent/'must-not-exist.db', RESOURCE, media_http=value)
    assert not (x.store.path.parent/'must-not-exist.db').exists()


def test_upload_replay_private_read_and_mcp_attachment(http):
    x=http;lid=create(x)['listing']['id'];h=headers(x)
    first=x.client.post(path(lid),headers=h,content=b'synthetic-original')
    assert first.status_code==201
    r=first.json();mid=r['media_id']
    assert r['visibility']=='private' and r['content_type']=='image/jpeg' and r['replayed'] is False
    assert not {'blob_key','path','key','user_id','original'} & r.keys()
    replay=x.client.post(path(lid),headers=h,content=b'synthetic-original')
    assert replay.status_code==200 and replay.json()['media_id']==mid and replay.json()['replayed']
    assert len(list(x.root.iterdir())) >= 1
    assert x.client.post(path(lid),headers=h,content=b'changed').status_code==409
    record=tool(x.client,x.ta,'listings_get',listing_id=lid)
    assert record['listing']['content']['media_ids']==[]
    assert tool(x.client,x.ta,'listings_publication_status',listing_id=lid)['publication']['state']=='never_published'
    read=x.client.get(path(lid,mid),headers={'Authorization':'Bearer '+x.ta})
    assert read.status_code==200 and read.content.startswith(b'\xff\xd8')
    assert read.headers['cache-control']=='no-store' and read.headers['x-content-type-options']=='nosniff'
    attached=tool(x.client,x.ta,'listings_set_photos',listing_id=lid,media_ids=[mid],expected_revision=1,client_id=key())
    assert attached['ok'] and attached['listing']['revision']==2
    assert x.client.get(path(lid,mid),headers={'Authorization':'Bearer '+x.ta}).status_code==200
    assert tool(x.client,x.ta,'listings_preview',listing_id=lid)['card_preview']['photos'][0]['media_id']==mid


@pytest.mark.parametrize('who,status',[('none',401),('room',403),('foreign',404),('stale',409)])
def test_reject_before_receiving_body(http,who,status):
    x=http;lid=create(x)['listing']['id'];h=headers(x)
    if who=='none':h.pop('Authorization')
    if who=='room':h['Authorization']='Bearer '+x.tr
    if who=='foreign':h['Authorization']='Bearer '+x.tb
    if who=='stale':h['X-Expected-Revision']='2'
    assert direct(x,path(lid),[],list(h.items()))[0]==status
    assert x.stages.worker.calls==0


@pytest.mark.parametrize('extra,status',[
    ({'Content-Type':'multipart/form-data; boundary=x'},415),
    ({'Content-Type':'application/json'},415),
    ({'Content-Encoding':'gzip'},415),
    ({'Content-Disposition':'attachment; filename=secret.png'},415),
    ({'X-Expected-Revision':'01'},400),
    ({'X-Expected-Revision':'9223372036854775807'},400),
    ({'Idempotency-Key':'not-a-uuid'},400),
    ({'Content-Length':'0'},400),
    ({'Content-Length':str(mh.MAX_INPUT_BYTES+1)},413),
    ({'Transfer-Encoding':'gzip'},400),
])
def test_header_rejections_without_body(http,extra,status):
    x=http;lid=create(x)['listing']['id']
    assert direct(x,path(lid),[],list(headers(x,**extra).items()))[0]==status
    assert x.gate.media_http.uploads.active==0


@pytest.mark.parametrize('extra',[
    [('Content-Length','1'),('Content-Length','1')],
    [('Content-Length','1'),('Transfer-Encoding','chunked')],
    [('Content-Type','image/jpeg')],
    [('Idempotency-Key',key())],
])
def test_duplicate_or_conflicting_headers(http,extra):
    x=http;lid=create(x)['listing']['id']
    status,_=direct(x,path(lid),[],list(headers(x).items())+extra)
    assert status in (400,415)


def test_chunked_and_body_length_failures(http,monkeypatch):
    x=http;lid=create(x)['listing']['id']
    h=list(headers(x).items())+[('Transfer-Encoding','chunked')]
    events=[{'type':'http.request','body':b'synthetic-','more_body':True},
            {'type':'http.request','body':b'original','more_body':False}]
    assert direct(x,path(lid),events,h)[0]==201
    monkeypatch.setattr(mh,'MAX_INPUT_BYTES',16)
    assert direct(x,path(lid),[{'type':'http.request','body':b'x'*17}],list(headers(x).items()))[0]==413
    for events,extra in [([{'type':'http.disconnect'}],{}),
                         ([{'type':'http.request','body':b''}],{}),
                         ([{'type':'http.request','body':b'x'}],{'Content-Length':'2'})]:
        assert direct(x,path(lid),events,list(headers(x,**extra).items()))[0]==400
    assert x.gate.media_http.uploads.active==0


def test_body_timeout_releases_admission(http,monkeypatch):
    x=http;lid=create(x)['listing']['id'];monkeypatch.setattr(mh,'BODY_TIMEOUT_SECONDS',0.01)
    async def slow():
        await anyio.sleep(1)
        return {'type':'http.request','body':b'x'}
    assert direct(x,path(lid),[slow],list(headers(x).items()))[0]==408
    assert x.gate.media_http.uploads.active==0


def test_revocation_during_body_prevents_file_write(http):
    x=http;lid=create(x)['listing']['id']
    async def revoke():
        x.auth.revoke(x.ma['credential_id'])
        return {'type':'http.request','body':b'synthetic-original'}
    assert direct(x,path(lid),[revoke],list(headers(x).items()))[0]==401
    assert x.stages.worker.calls==0


def test_read_owner_scope_route_binding_expiry_and_integrity(http):
    x=http;lid=create(x)['listing']['id'];other=create(x)['listing']['id']
    mid=upload(x,lid).json()['media_id']
    for token,status in [(None,401),(x.tr,403),(x.tb,404)]:
        h={'Authorization':'Bearer '+token} if token else {}
        assert x.client.get(path(lid,mid),headers=h).status_code==status
    assert x.client.get(path(other,mid),headers={'Authorization':'Bearer '+x.ta}).status_code==404
    x.now[0]+=600001
    assert x.client.get(path(lid,mid),headers={'Authorization':'Bearer '+x.ta}).status_code==404


def test_read_rechecks_revocation_after_file_io(http,monkeypatch):
    x=http;lid=create(x)['listing']['id'];mid=upload(x,lid).json()['media_id']
    original=x.files.read
    def revoke(receipt):
        data=original(receipt);x.auth.revoke(x.ma['credential_id']);return data
    monkeypatch.setattr(x.files,'read',revoke)
    response=x.client.get(path(lid,mid),headers={'Authorization':'Bearer '+x.ta})
    assert response.status_code==401 and b'synthetic-derivative' not in response.content


def test_admission_owner_global_bounds_and_release(http):
    x=http;lid=create(x)['listing']['id'];ad=x.gate.media_http.uploads
    with ad.slot(x.a):
        r=upload(x,lid);assert r.status_code==429 and r.headers['retry-after']=='1'
        with ad.slot(x.b):
            with pytest.raises(mh.HTTPFailure):
                with ad.slot('third'):pass
    assert ad.active==0 and ad.owners=={}
    assert upload(x,lid).status_code==201


@pytest.mark.parametrize('code,status',[('media_worker_timeout',504),('media_worker_failed',503),
    ('media_invalid_image',400),('media_worker_busy',429)])
def test_worker_errors_sanitized_and_release(http,code,status):
    x=http;lid=create(x)['listing']['id']
    def fail(*args):raise DomainError(code,private_path='/not-for-client')
    x.stages.worker.normalize=fail
    r=upload(x,lid)
    assert r.status_code==status and '/not-for-client' not in r.text
    assert x.gate.media_http.uploads.active==0


def test_actual_native_worker_http_ci_only(http):
    import sys
    if sys.version_info<(3,11):pytest.skip('native worker requires Python >=3.11')
    from io import BytesIO
    Image=pytest.importorskip('PIL.Image')
    from mcp_rooms.media_worker import PhotoWorker
    x=http;x.stages.worker=PhotoWorker();lid=create(x)['listing']['id']
    data=BytesIO();Image.new('RGB',(25,12),(30,80,120)).save(data,format='PNG')
    r=upload(x,lid,data.getvalue());assert r.status_code==201,r.text
    result=x.client.get(path(lid,r.json()['media_id']),headers={'Authorization':'Bearer '+x.ta})
    assert result.status_code==200
    with Image.open(BytesIO(result.content)) as image:
        assert image.format=='JPEG' and not image.getexif() and image.size==(25,12)
    assert upload(x,lid,b'not an image').status_code==400


def test_read_only_credential_cannot_upload_and_origin_gate(http):
    x=http;lid=create(x)['listing']['id']
    _,raw=x.auth.issue_token(x.a,scopes=['listings:read'])
    h=headers(x,Authorization='Bearer '+raw)
    assert direct(x,path(lid),[],list(h.items()))[0]==403
    h=headers(x,Origin='https://foreign.example')
    assert direct(x,path(lid),[],list(h.items()))[0]==403


def test_active_publication_blocks_upload_before_body(http):
    from test_market_server import confirm
    x=http;lid=create(x)['listing']['id']
    c=confirm(x,lid)
    assert tool(x.client,x.ta,'listings_publish',listing_id=lid,intent_id=c['intent_id'],client_id=key())['ok']
    assert direct(x,path(lid),[],list(headers(x).items()))[0]==409


def test_incremental_limit_checks_accumulated_bytes(http,monkeypatch):
    x=http;lid=create(x)['listing']['id'];monkeypatch.setattr(mh,'MAX_INPUT_BYTES',16)
    events=[{'type':'http.request','body':b'x'*10,'more_body':True},
            {'type':'http.request','body':b'x'*7,'more_body':False}]
    assert direct(x,path(lid),events,list(headers(x).items()))[0]==413
    assert x.stages.worker.calls==0


def test_private_read_corruption_and_unknown_uniform(http,monkeypatch):
    x=http;lid=create(x)['listing']['id'];mid=upload(x,lid).json()['media_id']
    def broken(receipt):raise DomainError('media_storage_integrity',path='/private/root')
    monkeypatch.setattr(x.files,'read',broken)
    auth={'Authorization':'Bearer '+x.ta}
    a=x.client.get(path(lid,mid),headers=auth)
    b=x.client.get(path(lid,key()),headers=auth)
    assert a.status_code==b.status_code==404 and a.json()==b.json()
    assert '/private/root' not in a.text


def test_method_and_path_allowlist(http):
    x=http;lid=create(x)['listing']['id']
    assert x.client.get(path(lid),headers=headers(x)).status_code==405
    assert x.client.post(path(lid,key()),headers=headers(x),content=b'x').status_code==405
    assert x.client.get(path(lid,key())+'?key=never',headers=headers(x)).status_code==400
    assert x.client.post(path(lid)+'/../elsewhere',headers=headers(x),content=b'x').status_code==404


def test_send_error_does_not_attempt_second_response_and_releases_slot(http):
    x=http;lid=create(x)['listing']['id'];mid=upload(x,lid).json()['media_id'];starts=[]
    async def run():
        async def receive():raise AssertionError('GET must not read body')
        async def send(event):
            if event['type']=='http.response.start':starts.append(event)
            else:raise OSError('synthetic disconnected transport')
        scope={'type':'http','method':'GET','path':path(lid,mid),'query_string':b'',
               'headers':[(b'host',b'rooms.example'),(b'authorization',('Bearer '+x.ta).encode())]}
        await x.gate(scope,receive,send)
    with pytest.raises(OSError):anyio.run(run)
    assert len(starts)==1 and x.gate.media_http.reads.active==0
