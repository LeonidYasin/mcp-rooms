"""Operator-run 30-minute HTTPS route. Exact-prefix CAS insert/delete; no old route restore."""
import argparse
import copy
from datetime import datetime, timezone, timedelta
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import stat
import subprocess
import tempfile
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

HOST = 'leonid-mcp.duckdns.org'
PREFIX = '/rooms-test'
SOURCE = '4b2351c0b6522d30c888496b3c1774be8791345f'
PROTECTED = ('mcp-server.service', 'mcp-test.service', 'caddy.service', 'mcp-rooms-test.service')
LIMIT = 4 * 1024 * 1024
ROOT = Path('/root')
SYSTEMD = Path('/etc/systemd/system')
CADDYFILE = Path('/etc/caddy/Caddyfile')


def require(ok, code):
    if not ok: raise RuntimeError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args): return None


def admin(method='GET', path='', payload=None, etag=None):
    url = 'http://127.0.0.1:2019/config/' + path
    headers = {'Content-Type':'application/json'}
    if etag: headers['If-Match'] = etag
    request = Request(url, data=canonical(payload) if payload is not None else None,
                      headers=headers, method=method)
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            raw = response.read(LIMIT+1)
            require(len(raw)<=LIMIT, 'admin_response_too_large')
            return (json.loads(raw) if raw else None), response.headers.get('ETag')
    except HTTPError as exc:
        if exc.code == 412: raise RuntimeError('config_conflict_retry_with_fresh_read') from None
        raise RuntimeError('caddy_admin_request_rejected') from None


def fresh():
    config, etag = admin()
    require(isinstance(config,dict) and bool(etag), 'missing_config_or_etag')
    return config, etag


def command(args, timeout=30):
    return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL,timeout=timeout).strip()


def services():
    result = {}
    for unit in PROTECTED:
        text = command(['systemctl','show',unit,'--no-pager',
                        '--property=ActiveState,SubState,MainPID,User,WorkingDirectory,ActiveEnterTimestampMonotonic,RuntimeMaxUSec'])
        props = dict(line.split('=',1) for line in text.splitlines() if '=' in line)
        require(props.get('ActiveState')=='active' and int(props.get('MainPID','0'))>0,
                'required_service_inactive_do_not_auto_restart')
        result[unit] = props
    return result


def caddyfile_digest():
    return hashlib.sha256(CADDYFILE.read_bytes()).hexdigest()


def make_route(marker):
    full = lambda values:[PREFIX+x for x in values]
    allowed = [
        {'path':full(['/signup','/signup.js','/identity','/mcp']),'method':['GET']},
        {'path':full(['/register','/credentials','/mcp']),'method':['POST']},
        {'path':full(['/credentials/current','/mcp']),'method':['DELETE']},
    ]
    proxy = {'handler':'reverse_proxy','upstreams':[{'dial':'127.0.0.1:8765'}],
             'transport':{'protocol':'http','dial_timeout':3000000000,
                          'response_header_timeout':15000000000,
                          'read_timeout':15000000000,'write_timeout':15000000000,
                          'max_conns_per_host':8}}
    return {'@id':marker,'match':[{'host':[HOST],'path':[PREFIX,PREFIX+'/*']}],
            'terminal':True,'handle':[{'handler':'request_body','max_size':65536},
                {'handler':'subroute','routes':[
                    {'match':[{'path':[PREFIX],'method':['GET']}],
                     'handle':[{'handler':'static_response','status_code':308,
                                'headers':{'Location':[PREFIX+'/signup'],'Cache-Control':['no-store']}}]},
                    {'match':allowed,'handle':[{'handler':'rewrite','strip_path_prefix':PREFIX},proxy], 'terminal':True},
                    {'handle':[{'handler':'static_response','status_code':404,
                                'body':'Not found','headers':{'Cache-Control':['no-store']}}]}
                ]}]}


def find_marker(value, marker, path=()):
    result = []
    if isinstance(value,dict):
        if value.get('@id')==marker: result.append((path,value))
        for key,item in value.items(): result.extend(find_marker(item,marker,path+(key,)))
    elif isinstance(value,list):
        for index,item in enumerate(value): result.extend(find_marker(item,marker,path+(index,)))
    return result


def prefix_referenced(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('path','strip_path_prefix'):
                if any(isinstance(p,str) and (p==PREFIX or p.startswith(PREFIX+'/'))
                       for p in (item if isinstance(item,list) else [item])):
                    return True
            if prefix_referenced(item): return True
    elif isinstance(value,list):
        return any(prefix_referenced(item) for item in value)
    return False


def route_list(config):
    servers = config.get('apps',{}).get('http',{}).get('servers',{})
    require(isinstance(servers,dict),'unexpected_http_servers')
    # No request access logging policy changes to any old server. Stop for review.
    require('logging' not in config and all('logs' not in s for s in servers.values()),
            'logging_config_needs_redaction_review')
    found = []
    for key,server in servers.items():
        if not isinstance(server,dict): continue
        for route in server.get('routes',[]):
            matches = route.get('match',[]) if isinstance(route,dict) else []
            if any(isinstance(m,dict) and m=={'host':[HOST]} for m in matches):
                require(matches==[{'host':[HOST]}] and route.get('terminal') is True,
                        'ambiguous_host_route')
                require(re.fullmatch('[A-Za-z0-9_-]+',key), 'unsupported_server_key')
                require(any(x in (':443','0.0.0.0:443','[::]:443') for x in server.get('listen',[])),
                        'https_listener_needs_review')
                found.append(key)
    require(len(found)==1,'expected_one_https_host_server')
    # Prefix must not already be explicitly routed/re-written anywhere.
    def scan(value):
        if isinstance(value,dict):
            require('path_regexp' not in value,'regexp_path_requires_manual_review')
            for key,item in value.items():
                if key in ('path','strip_path_prefix'):
                    for path in item if isinstance(item,list) else [item]:
                        require(not isinstance(path,str) or not (path==PREFIX or path.startswith(PREFIX+'/')),
                                'rooms_prefix_already_present')
                scan(item)
        elif isinstance(value,list):
            for item in value: scan(item)
    scan(config)
    return ('apps','http','servers',found[0],'routes')


def api_path(parts):
    return '/'.join(quote(str(x),safe='') for x in parts)


def without_marker(config,marker):
    result = copy.deepcopy(config)
    found = find_marker(result,marker)
    require(len(found)==1,'own_route_not_unique')
    path,_ = found[0]; parent=result
    for item in path[:-1]: parent=parent[item]
    require(isinstance(parent,list),'own_route_no_longer_array_item')
    del parent[path[-1]]
    return result


def save(path,state):
    temp=path.with_suffix('.new')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(state,stream); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp,path)


def load(path):
    path=Path(path)
    require(path.is_absolute() and path.name=='state.json' and path.parent.parent==ROOT
            and re.fullmatch(r'mcp-rooms-https-[A-Za-z0-9_-]+',path.parent.name),'invalid_state_location')
    for entry,kind,mode in ((path.parent,stat.S_ISDIR,0o700),(path,stat.S_ISREG,0o600)):
        info=entry.lstat()
        require(kind(info.st_mode) and info.st_uid==0 and stat.S_IMODE(info.st_mode)==mode,
                'unsafe_state_permissions')
        if entry==path: require(info.st_nlink==1,'unsafe_state_links')
    state=json.loads(path.read_text())
    require(state.get('format')==1 and re.fullmatch(r'mcp-rooms-route-[a-f0-9]{32}',state.get('marker','')),
            'invalid_state_identity')
    require(state.get('route')==make_route(state['marker']),'unexpected_route_definition')
    return state


def cleanup_definitions(state,path):
    name=state['marker']+'-cleanup'
    deadline=state['deadline_calendar']
    require(re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC',deadline),'invalid_deadline')
    service='''[Unit]
Description=Remove only the temporary MCP Rooms HTTPS route
After=caddy.service
StartLimitIntervalSec=0
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 -I {script} --remove --state {state}
TimeoutStartSec=120
Restart=on-failure
RestartSec=30s
UMask=0077
'''.format(script=path.parent/'route.py',state=path)
    timer='''[Unit]
Description=Temporary MCP Rooms route cleanup deadline
[Timer]
OnCalendar={deadline}
Persistent=true
AccuracySec=1s
Unit={name}.service
[Install]
WantedBy=timers.target
'''.format(deadline=deadline,name=name)
    return {name+'.service':service,name+'.timer':timer}


def schedule(path,state):
    definitions=cleanup_definitions(state,path)
    for name,text in definitions.items():
        target=SYSTEMD/name
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
        with os.fdopen(fd,'w') as stream: stream.write(text); stream.flush(); os.fsync(stream.fileno())
    command(['systemctl','daemon-reload'])
    timer=state['marker']+'-cleanup.timer'
    command(['systemctl','enable','--now',timer])
    require(command(['systemctl','is-active',timer])=='active','cleanup_timer_not_active')


def unschedule(path,state):
    definitions=cleanup_definitions(state,path)
    # Validate ALL existing files before deleting either. Never stop our currently
    # executing oneshot service from inside itself.
    existing=[]
    for name,text in definitions.items():
        file=SYSTEMD/name
        if os.path.lexists(file):
            info=file.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_nlink==1
                    and file.read_bytes()==text.encode(),'cleanup_unit_changed_review_required')
            existing.append(file)
    timer=SYSTEMD/(state['marker']+'-cleanup.timer')
    if timer in existing: command(['systemctl','disable','--now',timer.name])
    for file in existing: file.unlink()
    if existing: command(['systemctl','daemon-reload'])


def remove(path):
    state=load(path)
    for _ in range(4):
        config,etag=fresh(); found=find_marker(config,state['marker'])
        require(len(found)<=1,'own_route_not_unique')
        if not found:
            require(not prefix_referenced(config),'prefix_exists_without_our_marker_manual_review')
            break
        parts,route=found[0]
        require(route==state['route'],'own_route_changed_manual_review_required')
        try: admin('DELETE',api_path(parts),etag=etag)
        except RuntimeError as exc:
            if str(exc)=='config_conflict_retry_with_fresh_read': continue
            raise
        remaining,_=fresh()
        require(not find_marker(remaining,state['marker']),'route_delete_not_confirmed')
        break
    else: raise RuntimeError('cleanup_conflicts_retry_later')
    unschedule(path,state)
    state['removed']=True; save(path,state)
    return {'result':'ROOMS HTTPS ROUTE CLEANUP','state':'removed_or_already_absent',
            'other_routes_restored_or_overwritten':False,'caddyfile_changed':False,
            'rooms_database_preserved':True}


class LocalTLS(http.client.HTTPSConnection):
    def connect(self):
        raw=socket.create_connection(('127.0.0.1',443),timeout=self.timeout)
        try: self.sock=ssl.create_default_context().wrap_socket(raw,server_hostname=HOST)
        except BaseException: raw.close(); raise


def tls(path,method='GET',body=None,headers=None):
    connection=LocalTLS(HOST,timeout=20)
    try:
        connection.request(method,path,body=body,headers={'Host':HOST,**(headers or {})})
        response=connection.getresponse(); data=response.read(131073)
        require(len(data)<=131072,'tls_response_too_large')
        return response.status,dict((k.lower(),v) for k,v in response.getheaders()),data
    finally: connection.close()


def open_route(path,state,before,baseline,etag,parts):
    require(caddyfile_digest()==state['caddyfile_sha256'],'caddyfile_changed_before_apply')
    require(services()==before,'protected_service_state_changed')
    # Cleanup is armed BEFORE the potentially ambiguous mutating request.
    schedule(path,state)
    admin('PUT',api_path(parts+(0,)),state['route'],etag)
    applied,_=fresh()
    require(without_marker(applied,state['marker'])==baseline,'unexpected_concurrent_config_change')
    checks=[(PREFIX+'/signup','GET',None,200),(PREFIX+'/signup.js','GET',None,200),
            (PREFIX+'/mcp','POST','{}',401),(PREFIX+'/identity','GET',None,401),
            (PREFIX+'/register','POST','[]',400),(PREFIX+'/run_python','GET',None,404)]
    for target,method,body,expected in checks:
        status,headers,_=tls(target,method,body,{'Content-Type':'application/json'})
        require(status==expected,'local_tls_route_gate_failed')
        if target.endswith('/signup'): require(headers.get('cache-control')=='no-store','signup_cache_policy_failed')
    for target in ('/mcp','/test/mcp'):
        require(tls(target,'POST','{}',{'Content-Type':'application/json'})[0]==401,'old_anonymous_boundary_changed')
    require(services()==before,'protected_service_state_changed')
    require(caddyfile_digest()==state['caddyfile_sha256'],'caddyfile_changed_during_apply')
    state['accepted']=True; save(path,state)
    return {'result':'MCP ROOMS HTTPS TEST READY','endpoint':'https://'+HOST+PREFIX+'/mcp',
            'signup':'https://'+HOST+PREFIX+'/signup','runtime_sha':SOURCE,
            'local_tls_route_gate':True,'external_client_gate':False,
            'signup_public_during_test':True,'signup_quota_is_not_anti_bot':True,
            'cleanup_deadline_utc':state['deadline_iso'],'cleanup_persistent_timer_armed':True,
            'cleanup_is_not_a_hard_security_expiry':True,'protected_service_states_unchanged':True,
            'old_config_except_inserted_route_unchanged_at_apply':True,'caddyfile_changed':False,
            'registration_performed_by_helper':False,'private_state':str(path),
            'cleanup_command':'/usr/bin/python3 -I '+str(path.parent/'route.py')+' --remove --state '+str(path)}


def add():
    before=services()
    rooms=before['mcp-rooms-test.service']
    require(rooms.get('User')=='mcp-rooms-test' and rooms.get('WorkingDirectory')=='/home/mcp-rooms-test/app'
            and rooms.get('RuntimeMaxUSec')=='2h','unexpected_rooms_unit')
    started=int(rooms.get('ActiveEnterTimestampMonotonic','0'))/1000000
    require(started>0 and 7200-(time.monotonic()-started)>2100,'not_enough_rooms_runtime_do_not_auto_restart')
    actual=command(['runuser','-u','mcp-rooms-test','--','git','--no-optional-locks','-C','/home/mcp-rooms-test/app','rev-parse','HEAD'])
    require(actual==SOURCE,'unexpected_runtime_source')
    config,etag=fresh(); parts=route_list(config)
    for target in ('/mcp','/test/mcp'):
        require(tls(target,'POST','{}',{'Content-Type':'application/json'})[0]==401,'unexpected_old_anonymous_boundary')
    marker='mcp-rooms-route-'+uuid.uuid4().hex
    directory=Path(tempfile.mkdtemp(prefix='mcp-rooms-https-',dir=ROOT))
    shutil.copyfile(__file__,directory/'route.py'); os.chmod(directory/'route.py',0o600)
    path=directory/'state.json'
    deadline=datetime.now(timezone.utc)+timedelta(minutes=30)
    state={'format':1,'marker':marker,'route':make_route(marker),
           'deadline_calendar':deadline.strftime('%Y-%m-%d %H:%M:%S UTC'),
           'deadline_iso':deadline.isoformat(),'caddyfile_sha256':caddyfile_digest(),'protected_before':before}
    save(path,state)
    # Private evidence only. NEVER used as a whole-config rollback payload.
    save(directory/'baseline.json',{'config':config,'etag':etag})
    try: return open_route(path,state,before,config,etag,parts)
    except Exception:
        cleanup='manual_review_required'
        try: remove(path); cleanup='own_route_removed'
        except Exception: pass
        return {'result':'STOP','reason':'https_route_or_gate_failed','cleanup':cleanup,
                'private_state':str(path),'cleanup_command':'/usr/bin/python3 -I '+str(directory/'route.py')+' --remove --state '+str(path)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--open-30m',action='store_true'); group.add_argument('--remove',action='store_true')
    parser.add_argument('--state',type=Path)
    args=parser.parse_args(argv)
    if os.geteuid()!=0:
        print(json.dumps({'result':'STOP','reason':'operator_root_console_required'})); return 1
    if args.remove and not args.state: parser.error('--remove requires --state')
    os.umask(0o077)
    lock=None
    try:
        lock=os.open('/run/lock/mcp-rooms-route.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        info=os.fstat(lock)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_nlink==1
                and stat.S_IMODE(info.st_mode)==0o600,'unsafe_lock')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        report=remove(args.state) if args.remove else add()
        print(json.dumps(report)); return 1 if report['result']=='STOP' else 0
    except Exception as exc:
        reason=str(exc) if isinstance(exc,RuntimeError) else 'route_operation_failed_sanitized'
        print(json.dumps({'result':'STOP','reason':reason})); return 1
    finally:
        if lock is not None: os.close(lock)


if __name__=='__main__': raise SystemExit(main())
