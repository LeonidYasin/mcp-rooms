"""Operator-run synthetic HTTP-auth/revocation/restore-rewind TEST; never real-client keys."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

RECOVERY_SHA256 = 'f18a94077f68fd76d49b0d596f1096de312a3e1b7f7cd0851832c3b00e51cd76'

CHILD = r'''"""Runs ONLY as the Rooms service user. Raw synthetic keys remain in process memory."""
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import sys
import uuid
from mcp_rooms.identity import IdentityStore
from mcp_rooms.store import RoomStore
from mcp_rooms.maintenance import backup_database, verify_database

DB = '/home/mcp-rooms-test/data/rooms.db'
HOST = 'leonid-mcp.duckdns.org'
RESOURCE = 'https://'+HOST+'/rooms-test/mcp'
TTL_SECONDS = 600

class LocalTLS(http.client.HTTPSConnection):
    def connect(self):
        raw=socket.create_connection(('127.0.0.1',443),timeout=self.timeout)
        try:self.sock=ssl.create_default_context().wrap_socket(raw,server_hostname=HOST)
        except BaseException:raw.close();raise

def require(ok, code):
    if not ok:raise RuntimeError(code)

def probe(token, user_id, expected):
    c=LocalTLS(HOST,timeout=15)
    try:
        c.request('GET','/rooms-test/identity',headers={'Host':HOST,'Authorization':'Bearer '+token})
        response=c.getresponse();raw=response.read(8193)
        require(len(raw)<=8192,'identity_response_limit')
        value=json.loads(raw)
        require(response.status==expected,'unexpected_identity_status')
        if expected==200:require(value.get('user_id')==user_id,'identity_user_mismatch')
        else:require(value.get('error')=='invalid_token','unexpected_identity_error')
    finally:c.close()

def run(directory):
    directory=Path(directory)
    auth=IdentityStore(RoomStore(DB),RESOURCE)
    users=[]; issued=[]; restored_auth=None
    ledger=directory/'canary-ledger.json'
    def save_ledger(phase):
        temp=ledger.with_suffix('.new')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump({'phase':phase,'user_ids':users,'credential_ids':issued,
                       'credential_ttl_seconds':TTL_SECONDS},stream)
            stream.flush();os.fsync(stream.fileno())
        os.replace(temp,ledger)
    def issue(user):
        metadata,token=auth.issue_token(user,ttl_seconds=TTL_SECONDS,scopes=('rooms:read',))
        issued.append(metadata['credential_id']);save_ledger('issued_synthetic_credential')
        return metadata,token
    success=False
    try:
        for suffix in ('A','B'):
            user=auth.create_user('Disposable auth drill '+suffix+' '+uuid.uuid4().hex[:12])['user_id']
            users.append(user);save_ledger('created_synthetic_user')
        old_meta,old_a=issue(users[0]);new_meta,new_a=issue(users[0]);b_meta,key_b=issue(users[1])
        probe(old_a,users[0],200);probe(new_a,users[0],200);probe(key_b,users[1],200)
        snapshot=directory/'before-revocation.db';restored=directory/'isolated-restored.db'
        backup_database(DB,snapshot)
        auth.revoke(old_meta['credential_id']);save_ledger('revoked_only_synthetic_old_key')
        probe(old_a,users[0],401);probe(new_a,users[0],200);probe(key_b,users[1],200)
        auth.disable(users[1]);save_ledger('disabled_only_synthetic_second_user')
        probe(key_b,users[1],401);probe(new_a,users[0],200)
        backup_database(snapshot,restored)
        require(verify_database(restored)['ok'],'restored_integrity_failed')
        restored_auth=IdentityStore(RoomStore(restored),RESOURCE)
        # Demonstrate the hazard on an isolated COPY, NEVER on the live DB.
        require(restored_auth.authenticate(old_a) is not None,'revocation_rewind_not_observed')
        require(restored_auth.authenticate(key_b) is not None,'disable_rewind_not_observed')
        restored_auth.revoke(old_meta['credential_id']);restored_auth.disable(users[1])
        require(restored_auth.authenticate(old_a) is None,'restored_old_key_not_rejected')
        require(restored_auth.authenticate(key_b) is None,'restored_disabled_user_not_rejected')
        require(restored_auth.authenticate(new_a) is not None,'restored_replacement_should_work')
        success=True
    finally:
        failures=0
        for target in (auth,restored_auth):
            if target is None:continue
            for cid in issued:
                try:target.revoke(cid)
                except Exception:failures+=1
            for user in users:
                try:target.disable(user)
                except Exception:failures+=1
        save_ledger('cleanup_complete' if failures==0 else 'cleanup_needs_review')
        require(failures==0,'synthetic_cleanup_needs_review_see_private_ledger')
    require(success,'auth_drill_incomplete')
    # Verify revocation through the LIVE HTTPS gate too, not only direct DB auth.
    probe(old_a,users[0],401);probe(new_a,users[0],401);probe(key_b,users[1],401)
    return {'result':'ROOMS DISPOSABLE AUTH DRILL PASS',
            'synthetic_users_created':2,'synthetic_credentials_issued':3,
            'credentials_scopes_read_only':True,'credential_fallback_ttl_seconds':TTL_SECONDS,
            'live_https_old_key_rejected':True,'replacement_same_user_remained_valid':True,
            'second_principal_unaffected_by_first_key_revocation':True,
            'disabled_synthetic_user_rejected':True,
            'isolated_restore_revocation_rewind_observed':True,
            'isolated_restore_disable_rewind_observed':True,
            'synthetic_revocation_and_disable_reapplied_to_copy':True,
            'all_synthetic_keys_revoked_and_users_disabled':True,
            'existing_client_keys_targeted':False,'live_database_overwritten':False,
            'restored_copy_exposed':False,'raw_keys_written_or_printed':False}

if __name__=='__main__':
    try:
        os.umask(0o077)
        print(json.dumps(run(sys.argv[1])))
    except Exception as exc:
        # No raw exception text/traceback/headers.
        print(json.dumps({'result':'STOP','reason':type(exc).__name__,
                          'private_ledger_review_required':True}))
        raise SystemExit(1)
'''


def require(ok,code):
    if not ok:raise RuntimeError(code)

def load_recovery(path):
    path=Path(path)
    require(path.is_absolute() and path.name=='drill.py' and path.parent.parent==Path('/root')
            and re.fullmatch(r'mcp-rooms-recovery\.[A-Za-z0-9]+',path.parent.name),
            'unexpected_recovery_helper_path')
    for entry,kind,mode in ((path.parent,stat.S_ISDIR,0o700),(path,stat.S_ISREG,0o600)):
        info=entry.lstat()
        require(kind(info.st_mode) and info.st_uid==0 and stat.S_IMODE(info.st_mode)==mode,
                'unsafe_recovery_helper_permissions')
    require(path.stat().st_nlink==1 and hashlib.sha256(path.read_bytes()).hexdigest()==RECOVERY_SHA256,
            'unexpected_recovery_helper_hash')
    spec=importlib.util.spec_from_file_location('pinned_recovery_helper',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true',required=True)
    parser.add_argument('--window-state',type=Path,required=True)
    parser.add_argument('--recovery-helper',type=Path,required=True)
    args=parser.parse_args()
    if os.geteuid()!=0:
        print(json.dumps({'result':'STOP','reason':'operator_root_console_required'}));return 1
    os.umask(0o077);lock=None;directory=None
    try:
        lock=os.open('/run/lock/mcp-rooms-route.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        info=os.fstat(lock)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_nlink==1
                and stat.S_IMODE(info.st_mode)==0o600,'unsafe_route_lock')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        recovery=load_recovery(args.recovery_helper)
        h,state=recovery.verify_helper(args.window_state)
        before_old=h.old_services();before_unit=recovery.window_checks(h,state)
        disk=recovery.shutil.disk_usage(recovery.HOME/'data')
        require(disk.free>=512*1024**2 and disk.free/disk.total>=0.10,'insufficient_snapshot_disk_reserve')
        directory=Path(recovery.as_user(['mktemp','-d',str(recovery.HOME/'data/auth-drill.XXXXXX')]))
        require(directory.parent==recovery.HOME/'data' and directory.resolve()==directory
                and re.fullmatch(r'auth-drill\.[A-Za-z0-9]+',directory.name),'unexpected_canary_directory')
        import pwd
        info=directory.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid==pwd.getpwnam(recovery.USER).pw_uid
                and stat.S_IMODE(info.st_mode)==0o700,'unsafe_canary_directory')
        raw=recovery.as_user([recovery.PYTHON,'-I','-c',CHILD,str(directory)],timeout=300)
        result=json.loads(raw)
        require(result.get('result')=='ROOMS DISPOSABLE AUTH DRILL PASS','synthetic_auth_drill_did_not_pass')
        require(h.old_services()==before_old,'old_service_states_changed')
        require(recovery.window_checks(h,state)==before_unit,'rooms_unit_changed_during_auth_drill')
        require(recovery.fingerprint(recovery.DB).get('found')==2,'diagnostic_messages_missing')
        result.update({'rooms_service_restarted':False,'old_service_states_unchanged':True,
                       'window_deadline_extended':False,'private_snapshot_directory':str(directory),
                       'real_clients_recheck_required':True})
        print(json.dumps(result));return 0
    except Exception as exc:
        reason=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
        print(json.dumps({'result':'STOP','reason':reason,
                          'private_snapshot_directory':str(directory) if directory else None,
                          'existing_client_keys_targeted':False,
                          'synthetic_ledger_review_required':directory is not None}))
        return 1
    finally:
        if lock is not None:os.close(lock)

if __name__=='__main__':raise SystemExit(main())
