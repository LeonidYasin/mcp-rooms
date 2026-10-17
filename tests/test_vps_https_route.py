"""Pure/mocked route lifecycle tests. No Caddy, systemd, root writes or network."""
import copy
import importlib.util
import json
from pathlib import Path
from urllib.error import HTTPError
import pytest

spec=importlib.util.spec_from_file_location('vps_https_route',Path(__file__).parents[1]/'deploy/vps_https_route.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
MARKER='mcp-rooms-route-'+'a'*32


def baseline():
    return {'apps':{'http':{'servers':{'srv0':{'listen':[':443'],'routes':[
        {'match':[{'host':[m.HOST]}],'terminal':True,'handle':[{'handler':'subroute','routes':[
            {'match':[{'header':{'X-Api-Key':['SYNTHETIC_PRIVATE_KEY']}}],
             'handle':[{'handler':'reverse_proxy','upstreams':[{'dial':'127.0.0.1:3001'}]}]},
            {'handle':[{'handler':'static_response','status_code':401}]}]}]}
    ]}}}}}


def state():
    return {'format':1,'marker':MARKER,'route':m.make_route(MARKER),
            'deadline_calendar':'2026-10-18 00:00:00 UTC','deadline_iso':'2026-10-18T00:00:00+00:00',
            'caddyfile_sha256':'unchanged'}


def with_route():
    config=baseline();config['apps']['http']['servers']['srv0']['routes'].insert(0,m.make_route(MARKER))
    return config


def test_route_scoped_host_prefix_paths_methods_and_bounds():
    route=m.make_route(MARKER)
    assert route['match']==[{'host':[m.HOST],'path':['/rooms-test','/rooms-test/*']}]
    assert route['terminal'] is True
    assert route['handle'][0]=={'handler':'request_body','max_size':65536}
    inner=route['handle'][1]['routes']
    assert inner[0]['handle'][0]['headers']['Location']==['/rooms-test/signup']
    allowed=inner[1]['match']
    assert all(path.startswith('/rooms-test/') for group in allowed for path in group['path'])
    assert not any('run_python' in path for group in allowed for path in group['path'])
    assert inner[-1]['handle'][0]['status_code']==404
    proxy=inner[1]['handle'][1]
    assert proxy['upstreams']==[{'dial':'127.0.0.1:8765'}]
    assert proxy['transport']['max_conns_per_host']==8
    assert 'X-Api-Key' not in json.dumps(route)


def test_choose_server_does_not_mutate_or_expose_old_auth():
    config=baseline();saved=copy.deepcopy(config)
    assert m.route_list(config)==('apps','http','servers','srv0','routes')
    assert config==saved
    assert m.without_marker(with_route(),MARKER)==saved
    assert m.find_marker(with_route(),MARKER)[0][0][-1]==0
    assert m.api_path(('apps','http','servers','srv0','routes',0))=='apps/http/servers/srv0/routes/0'


@pytest.mark.parametrize('change', ['prefix','logging','serverlog','regex','host','listener'])
def test_ambiguous_or_unsafe_existing_config_refused(change):
    config=baseline();server=config['apps']['http']['servers']['srv0']
    if change=='prefix':server['routes'].insert(0,m.make_route(MARKER))
    elif change=='logging':config['logging']={}
    elif change=='serverlog':server['logs']={}
    elif change=='regex':server['routes'][0]['handle'][0]['routes'][0]['match'][0]['path_regexp']={'pattern':'.*'}
    elif change=='host':server['routes'][0]['match'][0]['header']={'X-Test':['yes']}
    elif change=='listener':server['listen']=[':80']
    with pytest.raises(RuntimeError):m.route_list(config)


def test_cleanup_uses_fresh_scoped_delete_preserves_concurrent_changes(monkeypatch):
    config=with_route();config['apps']['http']['servers']['srv0']['routes'].append({'concurrent':'KEEP'})
    calls=[]
    monkeypatch.setattr(m,'load',lambda p:state())
    monkeypatch.setattr(m,'fresh',lambda:(copy.deepcopy(config),'FRESH_ETAG'))
    def admin(method,path='',payload=None,etag=None):
        assert method=='DELETE' and path=='apps/http/servers/srv0/routes/0' and etag=='FRESH_ETAG'
        assert payload is None
        calls.append(method);del config['apps']['http']['servers']['srv0']['routes'][0]
    monkeypatch.setattr(m,'admin',admin)
    monkeypatch.setattr(m,'unschedule',lambda *a:calls.append('unschedule'))
    monkeypatch.setattr(m,'save',lambda *a:None)
    result=m.remove(Path('/unused/state.json'))
    assert calls==['DELETE','unschedule']
    assert config['apps']['http']['servers']['srv0']['routes'][-1]=={'concurrent':'KEEP'}
    assert not result['other_routes_restored_or_overwritten']


def test_cleanup_changed_own_route_never_deletes(monkeypatch):
    config=with_route();config['apps']['http']['servers']['srv0']['routes'][0]['terminal']=False
    monkeypatch.setattr(m,'load',lambda p:state());monkeypatch.setattr(m,'fresh',lambda:(config,'etag'))
    def forbidden(*a,**kw):raise AssertionError('no mutation')
    monkeypatch.setattr(m,'admin',forbidden);monkeypatch.setattr(m,'unschedule',forbidden)
    with pytest.raises(RuntimeError,match='own_route_changed'):m.remove(Path('/unused/state.json'))


def test_cleanup_missing_marker_but_prefix_remains_requires_review(monkeypatch):
    config=with_route();del config['apps']['http']['servers']['srv0']['routes'][0]['@id']
    monkeypatch.setattr(m,'load',lambda p:state());monkeypatch.setattr(m,'fresh',lambda:(config,'etag'))
    with pytest.raises(RuntimeError,match='prefix_exists_without_our_marker'):m.remove(Path('/unused/state.json'))


def test_cleanup_retries_conflict_using_new_etag(monkeypatch):
    config=with_route();attempts=[];reads=[]
    monkeypatch.setattr(m,'load',lambda p:state())
    def fresh():reads.append(1);return copy.deepcopy(config),'etag-'+str(len(reads))
    monkeypatch.setattr(m,'fresh',fresh)
    def admin(method,path='',payload=None,etag=None):
        attempts.append(etag)
        if len(attempts)==1:raise RuntimeError('config_conflict_retry_with_fresh_read')
        del config['apps']['http']['servers']['srv0']['routes'][0]
    monkeypatch.setattr(m,'admin',admin)
    monkeypatch.setattr(m,'unschedule',lambda *a:None);monkeypatch.setattr(m,'save',lambda *a:None)
    m.remove(Path('/unused/state.json'))
    assert attempts==['etag-1','etag-2']


def test_schedule_persistent_exact_owned_deadline_no_old_units():
    definitions=m.cleanup_definitions(state(),Path('/root/mcp-rooms-https-test/state.json'))
    timer=definitions[MARKER+'-cleanup.timer'];service=definitions[MARKER+'-cleanup.service']
    assert 'Persistent=true' in timer and 'OnCalendar=2026-10-18 00:00:00 UTC' in timer
    assert '--remove --state /root/mcp-rooms-https-test/state.json' in service
    assert 'Restart=on-failure' in service and 'After=caddy.service' in service
    assert 'systemctl restart' not in service and '/load' not in service


def test_open_arms_cleanup_before_single_scoped_mutation_no_signup(monkeypatch):
    calls=[]
    monkeypatch.setattr(m,'caddyfile_digest',lambda:'unchanged')
    monkeypatch.setattr(m,'services',lambda:{'same':True})
    monkeypatch.setattr(m,'schedule',lambda *a:calls.append('schedule'))
    def admin(method,path,payload,etag):
        assert method=='PUT' and path=='apps/http/servers/srv0/routes/0' and etag=='etag'
        calls.append('PUT')
    monkeypatch.setattr(m,'admin',admin)
    monkeypatch.setattr(m,'fresh',lambda:(with_route(),'new-etag'))
    def tls(path,method='GET',body=None,headers=None):
        assert body!='{}' or path.endswith('/mcp')
        assert not (path.endswith('/register') and body=='{}')
        status=400 if path.endswith('/register') else 404 if path.endswith('/run_python') else 401 if path.endswith('/mcp') or path.endswith('/identity') else 200
        return status,{'cache-control':'no-store'},b''
    monkeypatch.setattr(m,'tls',tls);monkeypatch.setattr(m,'save',lambda *a:None)
    result=m.open_route(Path('/root/mcp-rooms-https-test/state.json'),state(),{'same':True},baseline(),'etag',('apps','http','servers','srv0','routes'))
    assert calls==['schedule','PUT']
    assert result['local_tls_route_gate'] and not result['external_client_gate']
    assert not result['registration_performed_by_helper']


def test_admin_412_is_sanitized_no_response_body(monkeypatch):
    class Opener:
        def open(self,*a,**kw):raise HTTPError('http://127.0.0.1:2019/config/',412,'SYNTHETIC_SECRET',{},None)
    monkeypatch.setattr(m,'build_opener',lambda *a:Opener())
    with pytest.raises(RuntimeError,match='config_conflict_retry_with_fresh_read') as error:
        m.admin('PUT','test',{},'etag')
    assert 'SYNTHETIC_SECRET' not in str(error.value)


def test_nonroot_never_opens_lock_or_network(monkeypatch,capsys):
    monkeypatch.setattr(m.os,'geteuid',lambda:1000)
    def forbidden(*a,**kw):raise AssertionError('no privileged work')
    monkeypatch.setattr(m.os,'open',forbidden);monkeypatch.setattr(m,'admin',forbidden)
    assert m.main(['--open-30m'])==1
    assert 'operator_root_console_required' in capsys.readouterr().out
