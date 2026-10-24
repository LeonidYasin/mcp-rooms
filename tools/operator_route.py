"""Scoped /rooms HTTPS route for the owner-first candidate.

Operator-run on the root console only. This tool never installs, starts, enables or
restarts anything, never edits the Caddyfile, never rewrites a whole config and never
touches another service. It performs one conditional insert or one conditional delete
of its own uniquely marked route through the local Caddy admin API.

Pure planning helpers are importable and unit-tested without any host access.
"""
import argparse
import copy
import json
import re
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler

HOST='leonid-mcp.duckdns.org'
PREFIX='/rooms'
UPSTREAM='127.0.0.1:8766'
OPEN_AUTH='OPEN-ROOMS-CANDIDATE-ROUTE'
REMOVE_AUTH='REMOVE-ROOMS-CANDIDATE-ROUTE'
LIMIT=4*1024*1024
MARKER=re.compile(r'mcp-rooms-candidate-[0-9a-f]{16}')
ADMIN='http://127.0.0.1:2019/config/'


class RouteError(RuntimeError):
    pass


def require(ok,code):
    if not ok:raise RouteError(code)


def marker_for(source):
    if type(source) is not str or not re.fullmatch('[0-9a-f]{40}',source):
        raise RouteError('route_invalid_source')
    return 'mcp-rooms-candidate-'+source[:16]


def make_route(marker):
    require(isinstance(marker,str) and MARKER.fullmatch(marker) is not None,'route_invalid_marker')
    proxy={'handler':'reverse_proxy','upstreams':[{'dial':UPSTREAM}],
        'transport':{'protocol':'http','dial_timeout':3000000000,
            'response_header_timeout':15000000000,'read_timeout':15000000000,
            'write_timeout':15000000000,'max_conns_per_host':8}}
    app=[{'path':[PREFIX+'/mcp'],'method':['POST']},
         {'path':[PREFIX+'/identity',PREFIX+'/credentials',PREFIX+'/credentials/current'],
          'method':['GET','POST','DELETE']},
         {'path':[PREFIX+'/market',PREFIX+'/market/*'],'method':['GET']}]
    return {'@id':marker,
        'match':[{'host':[HOST],'path':[PREFIX,PREFIX+'/*']}],
        'terminal':True,
        'handle':[
            {'handler':'request_body','max_size':65536},
            {'handler':'subroute','routes':[
                {'match':app,
                 'handle':[{'handler':'rewrite','strip_path_prefix':PREFIX},proxy],'terminal':True},
                {'handle':[{'handler':'static_response','status_code':404,
                    'body':'Not found','headers':{'Cache-Control':['no-store']}}]}]}]}


def find_marker(value,marker,path=()):
    found=[]
    if isinstance(value,dict):
        if value.get('@id')==marker:found.append((path,value))
        for key,item in value.items():found.extend(find_marker(item,marker,path+(key,)))
    elif isinstance(value,list):
        for index,item in enumerate(value):found.extend(find_marker(item,marker,path+(index,)))
    return found


def prefix_referenced(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('path','strip_path_prefix'):
                for path in item if isinstance(item,list) else [item]:
                    if isinstance(path,str) and (path==PREFIX or path.startswith(PREFIX+'/')):
                        return True
            if prefix_referenced(item):return True
    elif isinstance(value,list):
        return any(prefix_referenced(item) for item in value)
    return False


def route_parts(config):
    servers=config.get('apps',{}).get('http',{}).get('servers',{})
    require(isinstance(servers,dict) and servers,'route_unexpected_servers')
    found=[]
    for key,server in servers.items():
        require(isinstance(server,dict),'route_unexpected_server')
        require(re.fullmatch('[A-Za-z0-9_-]+',key),'route_unsupported_server_key')
        routes=server.get('routes',[])
        require(isinstance(routes,list),'route_unexpected_routes')
        host_routes=[route for route in routes
            if isinstance(route,dict) and route.get('match')==[{'host':[HOST]}]]
        if not host_routes:continue
        require(len(host_routes)==1 and host_routes[0].get('terminal') is True,'route_ambiguous_host')
        listen=server.get('listen',[])
        require(any(item in (':443','0.0.0.0:443','[::]:443') for item in listen),'route_no_https_listener')
        found.append(('apps','http','servers',key,'routes',routes.index(host_routes[0])))
    require(len(found)==1,'route_expected_one_https_host')
    return found[0][:-1]


def plan_open(config,marker):
    require(not find_marker(config,marker),'route_already_present')
    require(not prefix_referenced(config),'route_prefix_already_used')
    result=copy.deepcopy(config)
    parts=route_parts(result)
    routes=result
    for part in parts:routes=routes[part]
    # Insert before the host catch-all so the narrow route wins and nothing else changes.
    routes.insert(0,make_route(marker))
    return result


def plan_remove(config,marker):
    found=find_marker(config,marker)
    require(len(found)==1,'route_own_route_not_unique')
    path,route=found[0]
    require(route==make_route(marker),'route_own_route_changed')
    result=copy.deepcopy(config)
    parent=result
    for part in path[:-1]:parent=parent[part]
    require(isinstance(parent,list),'route_own_route_not_list_item')
    del parent[path[-1]]
    require(not prefix_referenced(result),'route_prefix_left_without_marker')
    return result


def plan_diff(config,after):
    require(isinstance(config,dict) and isinstance(after,dict),'route_invalid_config')
    before=json.dumps(config,sort_keys=True,separators=(',',':'))
    now=json.dumps(after,sort_keys=True,separators=(',',':'))
    return {'changed_before_bytes':len(before),'changed_after_bytes':len(now),
            'identical':before==now}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args):
        return None


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def admin(method='GET',path='',payload=None,etag=None):
    headers={'Content-Type':'application/json'}
    if etag:headers['If-Match']=etag
    request=Request(ADMIN+path,data=canonical(payload) if payload is not None else None,
        headers=headers,method=method)
    try:
        with build_opener(NoRedirect()).open(request,timeout=20) as response:
            raw=response.read(LIMIT+1)
            require(len(raw)<=LIMIT,'route_admin_response_too_large')
            return (json.loads(raw) if raw else None),response.headers.get('ETag')
    except HTTPError as exc:
        if exc.code==412:raise RouteError('route_config_conflict_retry_with_fresh_read') from None
        raise RouteError('route_admin_request_rejected') from None


def fresh():
    config,etag=admin()
    require(isinstance(config,dict) and bool(etag),'route_missing_config_or_etag')
    return config,etag


def encode_path(parts):
    from urllib.parse import quote
    return '/'.join(quote(str(part),safe='') for part in parts)


def open_route(source,authorization):
    require(authorization==OPEN_AUTH,'route_open_authorization_required')
    marker=marker_for(source)
    for _ in range(4):
        config,etag=fresh()
        planned=plan_open(config,marker)
        try:
            admin('PUT',encode_path(route_parts(config)+(0,)),make_route(marker),etag)
        except RouteError as exc:
            if str(exc)=='route_config_conflict_retry_with_fresh_read':continue
            raise
        applied,_=fresh()
        require(find_marker(applied,marker)==[(route_parts(applied)+(0,),make_route(marker))],
            'route_insert_not_confirmed')
        require(plan_diff(config,applied)['identical'] is False,'route_insert_not_observed')
        return {'ok':True,'action':'opened','endpoint':'https://'+HOST+PREFIX+'/mcp',
            'card':'https://'+HOST+PREFIX+'/market/<id>','marker':marker,
            'upstream':UPSTREAM,'caddyfile_changed':False,'services_changed':False,
            'external_client_gate':False,'enabled_at_boot':False}
    raise RouteError('route_open_conflicts_retry_later')


def remove_route(source,authorization):
    require(authorization==REMOVE_AUTH,'route_remove_authorization_required')
    marker=marker_for(source)
    for _ in range(4):
        config,etag=fresh()
        found=find_marker(config,marker)
        if not found:
            require(not prefix_referenced(config),'route_prefix_exists_without_marker')
            return {'ok':True,'action':'absent','marker':marker,'caddyfile_changed':False}
        parts,_=found[0]
        require(parts==route_parts(config)+(0,),'route_own_route_moved')
        plan_remove(config,marker)
        try:
            admin('DELETE',encode_path(parts),etag=etag)
        except RouteError as exc:
            if str(exc)=='route_config_conflict_retry_with_fresh_read':continue
            raise
        remaining,_=fresh()
        require(not find_marker(remaining,marker),'route_delete_not_confirmed')
        return {'ok':True,'action':'removed','marker':marker,'caddyfile_changed':False,
            'other_routes_preserved':True}
    raise RouteError('route_remove_conflicts_retry_later')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--plan',action='store_true',help='read-only: print the exact route JSON')
    group.add_argument('--open',action='store_true',help='CAS-insert the narrow route')
    group.add_argument('--remove',action='store_true',help='CAS-delete only the own route')
    parser.add_argument('--source-sha',required=True)
    parser.add_argument('--authorization')
    args=parser.parse_args(argv)
    try:
        marker=marker_for(args.source_sha)
        if args.plan:
            config,_=fresh()
            print(json.dumps({'marker':marker,'route':make_route(marker),
                'diff':plan_diff(config,plan_open(config,marker)),'host':HOST,
                'prefix':PREFIX,'upstream':UPSTREAM},sort_keys=True))
            return 0
        if args.open:
            print(json.dumps(open_route(args.source_sha,args.authorization),sort_keys=True));return 0
        print(json.dumps(remove_route(args.source_sha,args.authorization),sort_keys=True));return 0
    except RouteError as exc:
        print(json.dumps({'ok':False,'error':str(exc)}));return 1
    except Exception:
        print(json.dumps({'ok':False,'error':'route_review_required'}));return 1


if __name__=='__main__':raise SystemExit(main())
