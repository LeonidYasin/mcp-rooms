"""Reviewed operator-only NEW loopback TEST installer. Never run through remote MCP."""
import argparse
import fcntl
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from urllib.error import HTTPError

# Runtime source is a separately CI-accepted immutable commit, not a branch tip.
SOURCE = '4b2351c0b6522d30c888496b3c1774be8791345f'
USER = 'mcp-rooms-test'
HOME = Path('/home') / USER
UNIT = 'mcp-rooms-test.service'
UNIT_PATH = Path('/etc/systemd/system') / UNIT
RESOURCE = 'https://leonid-mcp.duckdns.org/rooms-test/mcp'
PORT = 8765
PROTECTED = ('mcp-server.service', 'mcp-test.service', 'caddy.service')
UNIT_TEXT = '''[Unit]
Description=MCP Rooms isolated loopback TEST
After=network-online.target

[Service]
Type=simple
User=mcp-rooms-test
Group=mcp-rooms-test
WorkingDirectory=/home/mcp-rooms-test/app
ExecStart=/home/mcp-rooms-test/venv/bin/mcp-rooms --db /home/mcp-rooms-test/data/rooms.db --resource https://leonid-mcp.duckdns.org/rooms-test/mcp --port 8765 --enable-registration
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/mcp-rooms-test/data
InaccessiblePaths=/root /home/mcp /home/mcp-test /etc/caddy
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
MemoryMax=256M
TasksMax=64
LimitNOFILE=512
RuntimeMaxSec=7200
Restart=no
'''
UNIT_HASH = hashlib.sha256(UNIT_TEXT.encode()).hexdigest()
TOOLS = {'rooms_create', 'rooms_list', 'rooms_join', 'rooms_leave', 'rooms_read',
         'rooms_send', 'rooms_delete_message', 'rooms_close', 'rooms_topics'}


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def capture(args):
    return subprocess.check_output(args, text=True, timeout=20,
                                   stderr=subprocess.DEVNULL).strip()


def service(unit):
    raw = capture(['systemctl', 'show', unit, '--no-pager',
                   '--property=LoadState,ActiveState,SubState,MainPID,User,WorkingDirectory'])
    return dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)


def verify_unit_definition():
    raw = capture(['systemctl', 'show', UNIT, '--no-pager',
                   '--property=FragmentPath,DropInPaths'])
    props = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
    require(props.get('FragmentPath') == str(UNIT_PATH) and not props.get('DropInPaths'),
            'new_unit_definition_changed_review_required')


def protected():
    value = {name: service(name) for name in PROTECTED}
    require(all(x.get('ActiveState') == 'active' and int(x.get('MainPID', '0')) > 0
                for x in value.values()), 'protected_service_not_running')
    return value


def port_free(raw):
    return all(len(p := line.split()) < 5 or p[3].rsplit(':', 1)[-1] != str(PORT)
               for line in raw.splitlines())


def preflight():
    require((3, 10) <= sys.version_info[:2] <= (3, 13), 'unsupported_python')
    for name in ('git', 'systemctl', 'systemd-run', 'runuser', 'ss', 'useradd'):
        require(shutil.which(name), 'missing_operator_tool')
    for lookup in (pwd.getpwnam, grp.getgrnam):
        try:
            lookup(USER)
        except KeyError:
            continue
        raise RuntimeError('candidate_user_or_group_exists')
    require(not os.path.lexists(HOME) and not os.path.lexists(UNIT_PATH), 'candidate_path_exists')
    require(service(UNIT).get('LoadState') == 'not-found', 'candidate_unit_exists')
    require(port_free(capture(['ss', '-H', '-ltn'])), 'candidate_port_busy')
    disk = shutil.disk_usage('/home')
    require(disk.free >= 2 * 1024**3 and disk.free / disk.total >= .10, 'disk_reserve_low')
    mem = next((int(x.split()[1]) for x in Path('/proc/meminfo').read_text().splitlines()
                if x.startswith('MemAvailable:')), 0)
    require(mem >= 512 * 1024, 'memory_reserve_low')
    # Importing stdlib bootstrap modules only; no project code executed as root.
    import importlib.util
    require(all(importlib.util.find_spec(x) for x in ('venv', 'ensurepip')), 'venv_missing')
    return protected()


def private_file(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600, 'unsafe_private_file')


def save_state(path, value):
    # Directory is root-owned 0700 and the only writer holds our exclusive lock.
    temporary = path.with_suffix('.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def load_state(path):
    path = Path(path)
    require(path.is_absolute() and path.name == 'state.json' and
            path.parent.parent == Path('/root') and
            path.parent.name.startswith('mcp-rooms-install-'), 'invalid_state_location')
    info = path.parent.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and
            stat.S_IMODE(info.st_mode) == 0o700, 'unsafe_state_directory')
    private_file(path)
    state = json.loads(path.read_text())
    require(state.get('format') == 1 and state.get('source_sha') == SOURCE and
            state.get('unit_hash') == UNIT_HASH, 'state_identity_mismatch')
    return state


def run(args, log, timeout=1200, env=None):
    subprocess.run(args, check=True, stdout=log, stderr=log, timeout=timeout, env=env)


def rollback(path, log):
    state = load_state(path)
    # Never delete a user/home/DB. Never restore a global configuration snapshot.
    # Refuse stopping a unit whose on-disk definition was changed since our install.
    if os.path.lexists(UNIT_PATH):
        info = UNIT_PATH.lstat()
        require(state.get('unit_created') and stat.S_ISREG(info.st_mode) and
                info.st_uid == 0 and info.st_nlink == 1 and
                hashlib.sha256(UNIT_PATH.read_bytes()).hexdigest() == UNIT_HASH,
                'unit_changed_manual_review_required')
        verify_unit_definition()
        run(['systemctl', 'stop', UNIT], log, 30)
        UNIT_PATH.unlink()
        run(['systemctl', 'daemon-reload'], log, 30)
    else:
        require(service(UNIT).get('ActiveState') != 'active', 'unit_missing_but_running_review')
    state['rolled_back'] = True
    save_state(path, state)
    return {'result': 'ROOMS TEST ROLLBACK', 'new_unit_removed': True,
            'user_home_database_preserved': True, 'caddy_changed': False,
            'protected_services_unchanged': protected() == state['protected_before']}


# Runs as the NEW service OS user. Never stdout/traceback credential values.
SMOKE = r'''
import json, sqlite3, stat, os
from urllib.request import Request, urlopen
from urllib.error import HTTPError
B='http://127.0.0.1:8765'
def http(path, method='GET', data=None, token=None):
    headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
    if token: headers['Authorization']='Bearer '+token
    req=Request(B+path, data=json.dumps(data).encode() if data is not None else None,
                method=method, headers=headers)
    try:
        with urlopen(req, timeout=10) as r:
            raw=r.read(131072); return r.status, json.loads(raw) if raw else None
    except HTTPError as e: return e.code, None

def check(ok):
    if not ok: raise RuntimeError('loopback_acceptance_failed')
def tool(key, name, **args):
    status,result=http('/mcp','POST',{'jsonrpc':'2.0','id':1,'method':'tools/call',
        'params':{'name':name,'arguments':args}},key)
    check(status==200 and 'result' in result)
    return json.loads(result['result']['content'][0]['text'])
try:
    check(http('/mcp','POST',{})[0]==401)
    check(http('/identity', token='invalid')[0]==401)
    status,a=http('/register','POST',{}); check(status==201)
    status,b=http('/register','POST',{}); check(status==201)
    ka,kb=a['server_key']['key'],b['server_key']['key']
    check(a['user_id']!=b['user_id'])
    status,catalog=http('/mcp','POST',{'jsonrpc':'2.0','id':1,'method':'tools/list'},ka)
    check(status==200)
    check({t['name'] for t in catalog['result']['tools']}=={
        'rooms_create','rooms_list','rooms_join','rooms_leave','rooms_read',
        'rooms_send','rooms_delete_message','rooms_close','rooms_topics'})
    room=tool(ka,'rooms_create',title='loopback acceptance')['room_id']
    check(tool(kb,'rooms_read',room_id=room).get('error')=='membership_required')
    check(tool(kb,'rooms_join',room_id=room)['ok'])
    first=tool(ka,'rooms_send',room_id=room,text='want: loopback check',client_message_id='a')
    check(first['ok'])
    check(tool(kb,'rooms_read',room_id=room)['messages'][0]['text']=='want: loopback check')
    check(tool(kb,'rooms_send',room_id=room,text='offer: acknowledgement',client_message_id='b')['ok'])
    check(len(tool(ka,'rooms_read',room_id=room)['messages'])==2)
    check(tool(ka,'rooms_send',room_id=room,text='want: loopback check',client_message_id='a')['message']['id']==first['message']['id'])
    check(tool(kb,'rooms_close',room_id=room).get('error')=='not_room_owner')
    status,new=http('/credentials','POST',{},ka); check(status==201)
    kn=new['key']; check(http('/identity',token=kn)[1]['user_id']==a['user_id'])
    check(http('/credentials/current','DELETE',token=ka)[0]==200)
    check(http('/identity',token=ka)[0]==401)
    check(tool(kn,'rooms_read',room_id=room)['ok'])
    check(tool(kn,'rooms_close',room_id=room)['ok'])
    # Leave no live smoke-test credentials behind. User/hash rows remain budgeted.
    check(http('/credentials/current','DELETE',token=kn)[0]==200)
    check(http('/credentials/current','DELETE',token=kb)[0]==200)
    path='/home/mcp-rooms-test/data/rooms.db'
    check(stat.S_IMODE(os.stat(path).st_mode)==0o600)
    with sqlite3.connect(path) as db:
        check(db.execute('PRAGMA application_id').fetchone()[0]==0x4D435252)
        check(db.execute('PRAGMA user_version').fetchone()[0]==2)
        check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
    print('LOOPBACK_ACCEPTANCE_PASS')
except Exception:
    print('LOOPBACK_ACCEPTANCE_FAILED'); raise SystemExit(1)
'''


def transient(unit, command, writable):
    return ['systemd-run', '--quiet', '--wait', '--pipe', '--collect', '--unit='+unit,
            '--property=User='+USER, '--property=Group='+USER,
            '--property=WorkingDirectory='+str(HOME), '--property=UMask=0077',
            '--property=NoNewPrivileges=yes', '--property=ProtectSystem=strict',
            '--property=ProtectHome=read-only', '--property=PrivateTmp=yes',
            '--property=ReadWritePaths='+str(writable),
            '--property=InaccessiblePaths=/root /home/mcp /home/mcp-test /etc/caddy',
            '--property=MemoryMax=512M', '--property=TasksMax=64',
            '--property=RuntimeMaxSec=1200', '--property=KillMode=control-group',
            '--setenv=HOME='+str(HOME), '--setenv=PYTHONNOUSERSITE=1',
            '--setenv=PIP_NO_INPUT=1', '--setenv=PIP_DISABLE_PIP_VERSION_CHECK=1',
            '--setenv=GIT_TERMINAL_PROMPT=0', '--setenv=GIT_CONFIG_NOSYSTEM=1',
            *command]


def install(path, state, log):
    before = state['protected_before']
    require(protected() == before, 'protected_state_changed')
    run(['useradd', '--system', '--user-group', '--create-home', '--home-dir', str(HOME),
         '--shell', '/usr/sbin/nologin', USER], log, 30)
    account = pwd.getpwnam(USER)
    require(account.pw_dir == str(HOME) and account.pw_uid != 0, 'new_account_mismatch')
    os.chmod(HOME, 0o700)
    state['user_created'] = True; save_state(path, state)
    data = HOME / 'data'; data.mkdir(mode=0o700)
    os.chown(data, account.pw_uid, account.pw_gid)
    # No root pip/project imports. Source fetch, install, tests and build all run
    # as the NEW user in a systemd filesystem/memory/time-limited transient unit.
    build = [
        'set -euo pipefail; umask 077',
        'git init -q app',
        'git -C app remote add origin https://github.com/LeonidYasin/mcp-rooms.git',
        'git -C app fetch --depth=1 origin '+SOURCE,
        'test "$(git -C app rev-parse FETCH_HEAD)" = '+SOURCE,
        'git -C app checkout --detach -q FETCH_HEAD',
        '/usr/bin/python3 -m venv venv',
        'venv/bin/python -m pip install --no-cache-dir "./app[test]"',
        '(cd app && ../venv/bin/python -m pytest -q && ../venv/bin/python -m build)',
        'venv/bin/python -m pip install --no-deps --force-reinstall app/dist/*.whl',
        'venv/bin/python -c "import mcp_rooms; assert \'/venv/\' in mcp_rooms.__file__"',
    ]
    build_unit = 'mcp-rooms-build-'+path.parent.name.rsplit('-', 1)[-1]+'.service'
    require(service(build_unit).get('LoadState') == 'not-found', 'build_unit_collision')
    state['transient_unit'] = build_unit; save_state(path, state)
    try:
        run(transient(build_unit, ['/bin/bash', '-c', '\n'.join(build)], HOME), log, 1230)
    finally:
        # Exact unique unit belongs to this install; never stop a broad unit pattern.
        if service(build_unit).get('ActiveState') in ('active', 'activating'):
            run(['systemctl', 'stop', build_unit], log, 30)
    require(protected() == before, 'protected_state_changed')
    require(port_free(capture(['ss', '-H', '-ltn'])), 'candidate_port_became_busy')
    require(service(UNIT).get('LoadState') == 'not-found', 'candidate_unit_appeared')
    fd = os.open(UNIT_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'w') as stream:
        state['unit_created'] = True; save_state(path, state)
        stream.write(UNIT_TEXT); stream.flush(); os.fsync(stream.fileno())
    os.chmod(UNIT_PATH, 0o644)
    run(['systemctl', 'daemon-reload'], log, 30)
    verify_unit_definition()
    run(['systemctl', 'start', UNIT], log, 30)
    for _ in range(30):
        try:
            with urlopen('http://127.0.0.1:8765/signup', timeout=2) as response:
                if response.status == 200: break
        except (OSError, HTTPError):
            time.sleep(1)
    else:
        raise RuntimeError('new_service_not_ready')
    runtime = service(UNIT)
    require(runtime.get('ActiveState') == 'active' and runtime.get('User') == USER,
            'new_service_identity_mismatch')
    # Reject any non-loopback listener on this port, including IPv6/wildcards.
    lines = capture(['ss', '-H', '-ltn']).splitlines()
    bindings = [v[3] for x in lines if len(v := x.split()) >= 5 and v[3].rsplit(':',1)[-1]==str(PORT)]
    require(bindings == ['127.0.0.1:8765'], 'unexpected_bind_address')
    gate = 'mcp-rooms-gate-'+path.parent.name.rsplit('-',1)[-1]+'.service'
    require(service(gate).get('LoadState') == 'not-found', 'gate_unit_collision')
    state['gate_unit'] = gate; save_state(path, state)
    try:
        run(transient(gate, [str(HOME/'venv/bin/python'), '-I', '-c', SMOKE], data), log, 90)
    finally:
        if service(gate).get('ActiveState') in ('active', 'activating'):
            run(['systemctl', 'stop', gate], log, 30)
    require(protected() == before, 'protected_state_changed')
    state['accepted'] = True; save_state(path, state)
    return {'result': 'MCP ROOMS LOOPBACK TEST READY', 'runtime_sha': SOURCE,
            'unit': UNIT, 'listen': '127.0.0.1:8765', 'room_tools': 8,
            'one_click_signup': True, 'loopback_two_users_and_rotation_gate': True,
            'database_integrity': True, 'smoke_keys_revoked': True,
            'public_endpoint': False, 'live_external_client_gate': False,
            'protected_service_states_unchanged': True, 'caddy_changed': False,
            'old_code_dependencies_databases_changed': False,
            'enabled_at_boot': False, 'runtime_limit_seconds': 7200,
            'private_state': str(path), 'private_log': str(path.parent/'install.log'),
            'rollback_command': '/usr/bin/python3 -I '+str(path.parent/'installer.py')+' --rollback '+str(path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--install', action='store_true')
    group.add_argument('--rollback')
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        print(json.dumps({'result':'STOP','reason':'operator_root_console_required'})); return 1
    os.umask(0o077)
    try:
        lock = os.open('/run/lock/mcp-rooms-test-install.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError:
        print(json.dumps({'result':'STOP','reason':'cannot_open_private_lock'})); return 1
    info = os.fstat(lock)
    if not (stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600):
        os.close(lock)
        print(json.dumps({'result':'STOP','reason':'unsafe_lock_file'})); return 1
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock)
        print(json.dumps({'result':'STOP','reason':'another_rooms_install_running'})); return 1
    try:
        if args.rollback:
            path = Path(args.rollback); load_state(path)
            with (path.parent/'rollback.log').open('a') as log:
                print(json.dumps(rollback(path, log)))
            return 0
        before = preflight()
        directory = Path(tempfile.mkdtemp(prefix='mcp-rooms-install-', dir='/root'))
        shutil.copyfile(__file__, directory/'installer.py')
        os.chmod(directory/'installer.py', 0o600)
        path = directory/'state.json'
        state = {'format':1,'source_sha':SOURCE,'unit_hash':UNIT_HASH,
                 'protected_before':before,'unit_created':False,'user_created':False}
        save_state(path, state)
        with (directory/'install.log').open('w') as log:
            try:
                report = install(path, state, log)
            except Exception as exc:
                log.write('INSTALL_FAILURE: '+type(exc).__name__+'\n')
                if isinstance(exc, RuntimeError):
                    log.write('GATE: '+str(exc)+'\n')
                log.flush()
                status = 'manual_review_required'
                try:
                    rollback(path, log); status = 'new_unit_removed_data_preserved'
                except Exception:
                    pass
                print(json.dumps({'result':'STOP','reason':'installation_or_gate_failed',
                                  'rollback':status,'private_log':str(directory/'install.log'),
                                  'private_state':str(path)}))
                return 1
        print(json.dumps(report)); return 0
    except Exception as exc:
        reason = str(exc) if isinstance(exc, RuntimeError) else 'preflight_or_rollback_failed_review_required'
        print(json.dumps({'result':'STOP','reason':reason})); return 1
    finally:
        os.close(lock)


if __name__ == '__main__':
    raise SystemExit(main())
