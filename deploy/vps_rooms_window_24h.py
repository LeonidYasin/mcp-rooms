"""Operator-run 24-hour Rooms TEST window; existing accounts only. No production restart."""
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
        {'path':full(['/identity','/mcp']),'method':['GET']},
        {'path':full(['/credentials','/mcp']),'method':['POST']},
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
                     'handle':[{'handler':'static_response','status_code':404,
                                'headers':{'Cache-Control':['no-store']}}]},
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
    restore_rooms_window(state)
    unschedule(path,state)
    state['removed']=True; save(path,state)
    return {'result':'ROOMS HTTPS ROUTE CLEANUP','state':'removed_or_already_absent',
            'other_routes_restored_or_overwritten':False,'caddyfile_changed':False,
            'rooms_database_preserved':True,'rooms_service_stopped':True,'runtime_override_removed':True}


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


UNIT = 'mcp-rooms-test.service'
UNIT_PATH = Path('/etc/systemd/system') / UNIT
UNIT_SHA256 = '1ad0e8b3aca4a0272b93a247429ea5fdcbc47ba57bf4761e53b965424e0143e3'
DROPIN_DIR = Path('/run/systemd/system/mcp-rooms-test.service.d')
DROPIN_TEXT = """[Service]
RuntimeMaxSec=90000
ExecStart=
ExecStart=/home/mcp-rooms-test/venv/bin/mcp-rooms --db /home/mcp-rooms-test/data/rooms.db --resource https://leonid-mcp.duckdns.org/rooms-test/mcp --port 8765
"""


def unit_props(unit):
    raw=command(['systemctl','show',unit,'--no-pager',
        '--property=LoadState,ActiveState,SubState,MainPID,User,Group,WorkingDirectory,FragmentPath,DropInPaths,UnitFileState,Result,ActiveEnterTimestampMonotonic,RuntimeMaxUSec'])
    return dict(line.split('=',1) for line in raw.splitlines() if '=' in line)


def old_services():
    result={name:unit_props(name) for name in PROTECTED if name!=UNIT}
    require(all(v.get('ActiveState')=='active' and int(v.get('MainPID','0'))>0
                for v in result.values()), 'old_service_not_active_stop_for_review')
    return result


def check_original_unit():
    info=UNIT_PATH.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_nlink==1
            and not (info.st_mode & 0o022), 'unsafe_original_unit')
    require(hashlib.sha256(UNIT_PATH.read_bytes()).hexdigest()==UNIT_SHA256,
            'original_rooms_unit_changed_stop_for_review')


def window_dropin(state):
    return DROPIN_DIR/(state['marker']+'.conf')


def verify_dropin_directory():
    info=DROPIN_DIR.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid==0
            and not (info.st_mode & 0o022), 'unsafe_runtime_dropin_directory')


def restore_rooms_window(state):
    # Called only after our route is confirmed absent. Preserve all DB/key files.
    require(state.get('window_format')==1, 'not_a_24h_window_state')
    check_original_unit()
    path=window_dropin(state)
    props=unit_props(UNIT)
    require(props.get('FragmentPath')==str(UNIT_PATH), 'rooms_fragment_changed')
    if os.path.lexists(DROPIN_DIR): verify_dropin_directory()
    require(props.get('DropInPaths','') in ('',str(path)), 'rooms_dropins_changed')
    if os.path.lexists(path):
        info=path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_nlink==1
                and not (info.st_mode & 0o022) and path.read_text()==DROPIN_TEXT,
                'own_dropin_changed_manual_review')
        # Do not act if another on-disk override appeared without daemon-reload.
        require(not any(p.name.endswith('.conf') and p!=path for p in DROPIN_DIR.iterdir()),
                'other_runtime_dropin_appeared')
        command(['systemctl','stop',UNIT])
        path.unlink()
        command(['systemctl','daemon-reload'])
        require(not unit_props(UNIT).get('DropInPaths'), 'rooms_dropin_restore_failed')
    else:
        require(not props.get('DropInPaths'), 'missing_dropin_still_loaded')
        if not state.get('dropin_created'):
            return  # Setup stopped before this window touched the Rooms unit.
    require(unit_props(UNIT).get('ActiveState') not in ('active','activating'),
            'rooms_still_active_after_cleanup')


def add():
    before_old=old_services()
    check_original_unit()
    rooms=unit_props(UNIT)
    require(rooms.get('LoadState')=='loaded' and rooms.get('FragmentPath')==str(UNIT_PATH)
            and rooms.get('User')=='mcp-rooms-test' and rooms.get('Group')=='mcp-rooms-test'
            and rooms.get('WorkingDirectory')=='/home/mcp-rooms-test/app'
            and not rooms.get('DropInPaths'), 'unexpected_rooms_unit_or_overrides')
    require(rooms.get('UnitFileState') in ('static','disabled'), 'rooms_boot_enablement_changed')
    require(rooms.get('ActiveState') in ('active','inactive','failed'), 'rooms_transition_in_progress')
    require(rooms.get('ActiveState')!='failed' or rooms.get('Result')=='timeout',
            'rooms_failed_for_reason_other_than_runtime_timeout')
    if os.path.lexists(DROPIN_DIR):
        verify_dropin_directory()
        require(not any(p.name.endswith('.conf') for p in DROPIN_DIR.iterdir()),
                'runtime_dropin_already_exists')
    actual=command(['runuser','-u','mcp-rooms-test','--','git','--no-optional-locks',
                    '-C','/home/mcp-rooms-test/app','rev-parse','HEAD'])
    require(actual==SOURCE,'unexpected_runtime_source')
    dirty=command(['runuser','-u','mcp-rooms-test','--','git','--no-optional-locks',
                  '-C','/home/mcp-rooms-test/app','status','--porcelain','--untracked-files=normal'])
    require(not dirty,'rooms_checkout_has_local_changes')
    config,etag=fresh()
    parts=route_list(config)  # Refuses any existing rooms-test route; no takeover.
    for target in ('/mcp','/test/mcp'):
        require(tls(target,'POST','{}',{'Content-Type':'application/json'})[0]==401,
                'unexpected_old_anonymous_boundary')
    marker='mcp-rooms-route-'+uuid.uuid4().hex
    directory=Path(tempfile.mkdtemp(prefix='mcp-rooms-https-',dir=ROOT))
    script=directory/'route.py'
    shutil.copyfile(__file__,script); os.chmod(script,0o600)
    path=directory/'state.json'
    deadline=datetime.now(timezone.utc)+timedelta(hours=24)
    state={'format':1,'window_format':1,'marker':marker,'route':make_route(marker),
           'deadline_calendar':deadline.strftime('%Y-%m-%d %H:%M:%S UTC'),
           'deadline_iso':deadline.isoformat(),'caddyfile_sha256':caddyfile_digest(),
           'protected_old_before':before_old,'dropin_created':False}
    save(path,state)
    save(directory/'baseline.json',{'config':config,'etag':etag})
    try:
        # Arm persistent cleanup BEFORE changing either the service or HTTPS route.
        schedule(path,state)
        if not os.path.lexists(DROPIN_DIR): DROPIN_DIR.mkdir(mode=0o755)
        verify_dropin_directory()
        dropin=window_dropin(state)
        fd=os.open(dropin,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
        with os.fdopen(fd,'w') as stream:
            stream.write(DROPIN_TEXT); stream.flush(); os.fsync(stream.fileno())
        state['dropin_created']=True; save(path,state)
        command(['systemctl','daemon-reload'])
        require(unit_props(UNIT).get('DropInPaths')==str(dropin),'new_dropin_not_effective')
        require(old_services()==before_old,'old_services_changed_before_restart')
        command(['systemctl','restart',UNIT],timeout=60)
        for _ in range(30):
            if unit_props(UNIT).get('ActiveState')=='active':
                try:
                    connection=http.client.HTTPConnection('127.0.0.1',8765,timeout=2)
                    connection.request('GET','/identity')
                    response=connection.getresponse(); body=response.read(4096)
                    connection.close()
                    if response.status==401 and json.loads(body).get('error')=='invalid_token': break
                except Exception: pass
            time.sleep(1)
        else: raise RuntimeError('rooms_not_ready_after_restart')
        require(old_services()==before_old,'old_service_state_changed')
        require(caddyfile_digest()==state['caddyfile_sha256'],'caddyfile_changed')
        # Use a fresh CAS base; concurrent unrelated route edits are preserved.
        baseline,etag=fresh(); parts=route_list(baseline)
        admin('PUT',api_path(parts+(0,)),state['route'],etag)
        applied,_=fresh()
        require(without_marker(applied,marker)==baseline,'unexpected_concurrent_config_change')
        checks=[('/signup','GET',None,404),('/signup.js','GET',None,404),
                ('/register','POST','{}',404),('/identity','GET',None,401),
                ('/mcp','POST','{}',401),('/run_python','GET',None,404)]
        for suffix,method,body,expected in checks:
            status,headers,data=tls(PREFIX+suffix,method,body,{'Content-Type':'application/json'})
            require(status==expected,'local_tls_window_gate_failed')
            if suffix in ('/identity','/mcp'):
                require(json.loads(data).get('error')=='invalid_token','unexpected_auth_boundary')
        for target in ('/mcp','/test/mcp'):
            require(tls(target,'POST','{}',{'Content-Type':'application/json'})[0]==401,
                    'old_anonymous_boundary_changed')
        require(old_services()==before_old,'old_services_changed_after_route')
        require(caddyfile_digest()==state['caddyfile_sha256'],'caddyfile_changed_after_route')
        require(command(['systemctl','is-active',marker+'-cleanup.timer'])=='active',
                'cleanup_timer_not_active')
        state['accepted']=True; save(path,state)
        return {'result':'MCP ROOMS 24H WINDOW READY',
                'endpoint':'https://'+HOST+PREFIX+'/mcp','runtime_sha':SOURCE,
                'cleanup_deadline_utc':deadline.isoformat(),
                'registration_enabled':False,'existing_keys_preserved':True,
                'only_rooms_service_restarted':True,'protected_service_states_unchanged':True,
                'local_tls_gate':True,'external_authenticated_client_gate':False,
                'cleanup_persistent_timer_armed':True,'hard_security_expiry':False,
                'loopback_runtime_fallback_seconds':90000,'boot_enabled':False,
                'code_or_dependencies_updated':False,'private_state':str(path),
                'cleanup_command':'/usr/bin/python3 -I '+str(script)+' --remove --state '+str(path)}
    except Exception:
        cleanup='manual_review_required'
        try: remove(path); cleanup='own_route_removed_rooms_stopped_override_removed'
        except Exception: pass
        return {'result':'STOP','reason':'24h_window_setup_or_gate_failed',
                'cleanup':cleanup,'private_state':str(path),
                'cleanup_command':'/usr/bin/python3 -I '+str(script)+' --remove --state '+str(path)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--open-24h',action='store_true'); group.add_argument('--remove',action='store_true')
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
