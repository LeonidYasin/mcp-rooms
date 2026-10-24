"""Pure planning tests for the scoped candidate HTTPS route. No host access."""
from copy import deepcopy
import json
from pathlib import Path
import runpy
import pytest

ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'tools/operator_route.py'))
Error=m['RouteError'];HOST=m['HOST'];PREFIX=m['PREFIX'];UPSTREAM=m['UPSTREAM']
SHA='a'*40
MARKER='mcp-rooms-candidate-'+SHA[:16]


def config():
    return {'apps':{'http':{'servers':{'srv0':{'listen':[':443'],'routes':[
        {'match':[{'host':[HOST]}],'terminal':True,'handle':[
            {'handler':'static_response','status_code':404}]}]}}}}}


def test_marker_is_deterministic_and_source_checked():
    assert m['marker_for'](SHA)==MARKER==m['marker_for'](SHA)
    assert m['marker_for']('b'*40)!=MARKER
    for bad in ('', 'A'*40, 'a'*39, 'a'*41, None, 7):
        with pytest.raises(Error,match='route_invalid_source'):m['marker_for'](bad)


def test_route_is_narrow_and_strips_only_the_prefix():
    route=m['make_route'](MARKER)
    assert route['@id']==MARKER and route['terminal'] is True
    assert route['match']==[{'host':[HOST],'path':[PREFIX,PREFIX+'/*']}]
    body,subroute=route['handle']
    assert body=={'handler':'request_body','max_size':65536}
    inner=subroute['routes']
    rewrite=[step for step in inner[0]['handle'] if step['handler']=='rewrite']
    proxy=[step for step in inner[0]['handle'] if step['handler']=='reverse_proxy']
    assert rewrite==[{'handler':'rewrite','strip_path_prefix':PREFIX}]
    assert proxy[0]['upstreams']==[{'dial':UPSTREAM}]
    assert proxy[0]['transport']['max_conns_per_host']==8
    assert inner[-1]['handle'][0]['status_code']==404
    assert 'authentication' not in json.dumps(route) and 'basicauth' not in json.dumps(route)


def test_only_expected_paths_and_methods_reach_the_candidate():
    inner=m['make_route'](MARKER)['handle'][1]['routes'][0]['match']
    assert inner==[{'path':[PREFIX+'/mcp'],'method':['POST']},
        {'path':[PREFIX+'/identity',PREFIX+'/credentials',PREFIX+'/credentials/current'],
         'method':['GET','POST','DELETE']},
        {'path':[PREFIX+'/market',PREFIX+'/market/*'],'method':['GET']}]
    assert all(path.startswith(PREFIX) for rule in inner for path in rule['path'])


def test_plan_open_inserts_before_the_catch_all_and_changes_nothing_else():
    before=config();after=m['plan_open'](before,MARKER)
    routes=after['apps']['http']['servers']['srv0']['routes']
    assert routes[0]==m['make_route'](MARKER)
    assert routes[1:]==before['apps']['http']['servers']['srv0']['routes']
    assert before==config() and after!=before
    assert m['plan_diff'](before,after)['identical'] is False


def test_plan_open_refuses_existing_marker_or_prefix():
    with pytest.raises(Error,match='route_already_present'):
        m['plan_open'](m['plan_open'](config(),MARKER),MARKER)
    taken=config()
    taken['apps']['http']['servers']['srv0']['routes'].insert(0,{'match':[
        {'path':[PREFIX+'/other']}],'handle':[{'handler':'static_response'}]})
    with pytest.raises(Error,match='route_prefix_already_used'):
        m['plan_open'](taken,MARKER)


def test_plan_remove_is_the_exact_inverse_and_refuses_foreign_changes():
    before=config();opened=m['plan_open'](before,MARKER)
    assert m['plan_remove'](opened,MARKER)==before
    with pytest.raises(Error,match='route_own_route_not_unique'):
        m['plan_remove'](before,MARKER)
    changed=m['plan_open'](before,MARKER)
    changed['apps']['http']['servers']['srv0']['routes'][0]['handle'][0]['max_size']=1024
    with pytest.raises(Error,match='route_own_route_changed'):
        m['plan_remove'](changed,MARKER)


def test_plan_remove_refuses_a_nested_foreign_marker():
    nested=config()
    nested['apps']['http']['servers']['srv0']['routes'][0]['handle'].append({'@id':MARKER})
    with pytest.raises(Error,match='route_own_route_changed'):
        m['plan_remove'](nested,MARKER)


@pytest.mark.parametrize('broken,code',[
    ({'apps':{'http':{'servers':{}}}},'route_unexpected_servers'),
    ({'apps':{'http':{'servers':{'a':{'listen':[':443'],'routes':[{'match':[{'host':['other']}]}]}}}}},
     'route_expected_one_https_host'),
    ({'apps':{'http':{'servers':{'a':{'listen':[':8080'],'routes':[{'match':[{'host':[HOST]}],'terminal':True}]}}}}},
     'route_no_https_listener'),
    ({'apps':{'http':{'servers':{'a':{'listen':[':443'],'routes':[
        {'match':[{'host':[HOST]}],'terminal':True},{'match':[{'host':[HOST]}],'terminal':True}]}}}}},
     'route_ambiguous_host')])
def test_route_parts_refuses_ambiguous_hosts(broken,code):
    with pytest.raises(Error,match=code):m['route_parts'](broken)


def test_two_https_servers_for_the_host_are_refused():
    config_=config()
    extra={'listen':[':443'],'routes':[{'match':[{'host':[HOST]}],'terminal':True}]}
    config_['apps']['http']['servers']['srv1']=extra
    with pytest.raises(Error,match='route_expected_one_https_host'):m['route_parts'](config_)


@pytest.mark.parametrize('action,auth,code',[
    ('open_route',None,'route_open_authorization_required'),
    ('open_route','wrong','route_open_authorization_required'),
    ('remove_route',None,'route_remove_authorization_required'),
    ('remove_route',m['OPEN_AUTH'],'route_remove_authorization_required')])
def test_authorization_precedes_any_host_contact(action,auth,code,monkeypatch):
    def deny(*a,**k):raise AssertionError('unexpected host contact')
    monkeypatch.setitem(m,'admin',deny);monkeypatch.setitem(m,'fresh',deny)
    with pytest.raises(Error,match=code):m[action](SHA,auth)


def test_pure_planners_never_touch_the_network(monkeypatch):
    def deny(*a,**k):raise AssertionError('unexpected host contact')
    monkeypatch.setitem(m,'admin',deny);monkeypatch.setitem(m,'fresh',deny)
    before=config();opened=m['plan_open'](before,MARKER)
    assert deepcopy(opened)!=before and m['plan_remove'](opened,MARKER)==before
