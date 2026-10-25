"""Actions-only offline install and real loopback lifecycle, synthetic state/keys only."""
from hashlib import sha256
import http.client
import json
import os
from pathlib import Path
import resource
import runpy
import socket
import sys
import tempfile
import uuid

ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'tools/operator_lifecycle.py'))
RESOURCE='https://candidate.invalid/rooms-test/mcp'
os.umask(0o077)


def rpc(raw,method,params):
    c=http.client.HTTPConnection('127.0.0.1',8766,timeout=10)
    try:
        c.request('POST','/mcp',body=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}),
            headers={'Authorization':'Bearer '+raw,'Content-Type':'application/json',
                     'Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2025-11-25'})
        response=c.getresponse();assert response.status==200
        body=response.read(1024*1024+1);assert len(body)<=1024*1024
        result=json.loads(body)['result']
        return result
    finally:c.close()


with tempfile.TemporaryDirectory(prefix='rooms-lifecycle-ci-') as parent:
    Path(parent).chmod(0o700);root=Path(parent)/'fresh'
    lock=sha256((ROOT/'operator/runtime-linux-x86_64-py312.lock').read_bytes()).hexdigest()
    installed=m['install'](Path(sys.argv[1]),root,sys.argv[2],lock,RESOURCE)
    assert installed['installed'] and not installed['profile_created'] and not (root/'profile').exists()
    m['bootstrap'](root)
    # Reading the ephemeral test key is confined to this CI client, never controller output.
    raw=(root/'profile/owner.key').read_text().strip()
    key_hash=sha256((root/'profile/owner.key').read_bytes()).hexdigest()
    started=False
    # A pre-existing listener is preserved; no process receipt is created.
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as occupied:
        occupied.bind(('127.0.0.1',8766));occupied.listen(1)
        try:m['start'](root)
        except m['LifecycleError'] as exc:assert str(exc)=='lifecycle_port_busy'
        else:raise AssertionError('occupied port was not refused')
        assert occupied.fileno()>=0 and not (root/'process.json').exists()
    # Failure AFTER native app has started but BEFORE readiness commit must reap
    # only its pinned child, preserve state and free the rehearsal listener.
    functions=m['start'].__globals__;writer=functions['_write_new']
    def interrupted(path,value):
        if path.name=='process.json':raise OSError('synthetic ready commit interruption')
        return writer(path,value)
    functions['_write_new']=interrupted
    try:
        try:m['start'](root)
        except OSError:pass
        else:raise AssertionError('interrupted start unexpectedly succeeded')
    finally:functions['_write_new']=writer
    assert not (root/'process.json').exists() and (root/'profile/market.sqlite3').exists()
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as freed:
        freed.bind(('127.0.0.1',8766))
    try:
        first=m['start'](root);started=True
        assert first['owned_loopback_listener'] and first['unauthenticated_http']==401
        assert first['authenticated_acceptance'] is False
        record=json.loads((root/'process.json').read_text());first_pid=record['identity']['pid']
        response=rpc(raw,'initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'lifecycle-ci','version':'1'}})
        assert response['serverInfo']['name']=='MCP Rooms'
        tools=rpc(raw,'tools/list',{})['tools'];assert len(tools)==29
        created=rpc(raw,'tools/call',{'name':'listings_create','arguments':{'client_id':str(uuid.uuid4()),'category_id':'things',
            'content':{'title':'Synthetic lifecycle item','description':'Not a real offer','category':'things','kind':'offer','modes':['shipping']}}})
        created=json.loads(created['content'][0]['text']);assert created['ok']
        listing_id=created['listing']['id']
        idle=Path(f'/proc/{first_pid}/status').read_text()
        idle_rss=int(next(line.split()[1] for line in idle.splitlines() if line.startswith('VmRSS:')))
        stopped=m['stop'](root);started=False;assert stopped['stopped'] and stopped['state_preserved']
        assert (root/'profile/market.sqlite3').exists() and (root/'profile/owner.key').exists()
        assert sha256((root/'profile/owner.key').read_bytes()).hexdigest()==key_hash
        second=m['start'](root);started=True
        assert second['owned_loopback_listener']
        assert len(list(root.glob('stopped-*.json')))==1
        read=rpc(raw,'tools/call',{'name':'listings_get','arguments':{'listing_id':listing_id}})
        assert json.loads(read['content'][0]['text'])['ok']
        result=m['rollback'](root);started=False
        assert result['stopped'] and result['data_rewound'] is False
        assert (root/'profile/market.sqlite3').exists() and (root/'venv').is_dir()
        assert sha256((root/'profile/owner.key').read_bytes()).hexdigest()==key_hash
        print('LIFECYCLE SMOKE PASS: '+json.dumps({'source_sha':sys.argv[2],'offline_install':True,
            'real_loopback_start_stop_restart':True,'authenticated_synthetic_mcp':True,
            'listing_and_key_preserved':True,'rollback':'stop-only','root_or_systemd':False,
            'occupied_port_preserved':True,'interrupted_start_reaped':True,
            'resource_budget_accepted':False,'idle_parent_rss_kib_point_sample':idle_rss,
            'max_single_reaped_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss},sort_keys=True))
    finally:
        raw=None
        if started:m['stop'](root)
