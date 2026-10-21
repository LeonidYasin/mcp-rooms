"""Installed-package Actions smoke. Synthetic keys/images; no sockets, files retained or VPS."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
from PIL import Image
from starlette.testclient import TestClient
import mcp_rooms
from mcp_rooms.test_candidate import bootstrap, compose

RESOURCE='https://candidate.invalid/mcp'


def rpc(client,raw,name,args):
    response=client.post('/mcp',headers={'Authorization':'Bearer '+raw,
        'Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2025-11-25'},
        json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args}})
    assert response.status_code==200
    result=json.loads(response.json()['result']['content'][0]['text'])
    assert result['ok'],result.get('error','unknown')
    return result


def smoke():
    import uuid
    key=lambda:str(uuid.uuid4())
    assert not Path(mcp_rooms.__file__).resolve().is_relative_to(Path(__file__).resolve().parents[1])
    with tempfile.TemporaryDirectory(prefix='synthetic-market-candidate-') as parent:
        Path(parent).chmod(0o700)
        state=Path(parent)/'fresh';bootstrap(state,RESOURCE)
        raw=(state/'owner.key').read_text().strip()
        with compose(state,RESOURCE) as candidate:
            with TestClient(candidate.app,base_url='https://candidate.invalid') as c:
                listing=rpc(c,raw,'listings_create',dict(client_id=key(),category_id='things',content=dict(title='CI synthetic item',description='Not an actual offer',category='things',kind='offer',modes=['shipping'])))
                lid=listing['listing']['id']
                with Image.new('RGB',(40,30),'green') as im,BytesIO() as out:
                    im.save(out,format='PNG');image=out.getvalue()
                uploaded=c.post('/listings/'+lid+'/photos',headers={'Authorization':'Bearer '+raw,
                    'Content-Type':'image/png','X-Expected-Revision':'1','Idempotency-Key':key()},content=image)
                assert uploaded.status_code==201
                mid=uploaded.json()['media_id']
                rpc(c,raw,'listings_set_photos',dict(listing_id=lid,expected_revision=1,client_id=key(),media_ids=[mid]))
                preview=rpc(c,raw,'listings_preview',dict(listing_id=lid))
                consent=rpc(c,raw,'listings_confirm_publication',dict(listing_id=lid,expected_revision=2,preview_digest=preview['digest'],consent=True,client_id=key()))
                published=rpc(c,raw,'listings_publish',dict(listing_id=lid,intent_id=consent['intent_id'],client_id=key()))
                card=c.get('/market/'+lid);assert card.status_code==200 and 'CI synthetic item' in card.text
                photo=c.get(f'/market/{lid}/photos/{published["publication_revision"]}/{mid}.jpg')
                assert photo.status_code==200
                with Image.open(BytesIO(photo.content)) as decoded:
                    decoded.load();assert decoded.format=='JPEG' and decoded.size==(40,30)
                    assert not decoded.getexif()
                rpc(c,raw,'listings_withdraw',dict(listing_id=lid,expected_publication_revision=1,client_id=key()))
                assert c.get('/market/'+lid).status_code==404
                assert c.get(f'/market/{lid}/photos/1/{mid}.jpg').status_code==404
        raw=None
    print('CANDIDATE SMOKE PASS: installed wheel; real native synthetic photo; MCP consent/public/withdraw; no sockets or VPS')


if __name__=='__main__':smoke()
