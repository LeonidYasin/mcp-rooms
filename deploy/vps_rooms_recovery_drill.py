"""Operator-only backup -> restore to NEW path -> restart ONLY the existing Rooms TEST.
No restore onto the live DB, no key revocation, no root import of project code.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

HELPER_SHA256 = 'dfdf115eb77258af5a5f63419a6c48413be6645acd375834608b84d0b88b879b'
UNIT = 'mcp-rooms-test.service'
USER = 'mcp-rooms-test'
HOME = Path('/home/mcp-rooms-test')
DB = HOME/'data/rooms.db'
MAINTENANCE = str(HOME/'venv/bin/mcp-rooms-maintenance')
PYTHON = str(HOME/'venv/bin/python3')
# Only synthetic diagnostic messages, not arbitrary user data.
CANARIES = ['7d0a41e2-7971-430c-b03f-5ab19837e149',
            'd6b0be35-6d85-4a40-b601-983762803653']
FINGERPRINT = r'''
import hashlib,json,sqlite3,sys
from pathlib import Path
p=Path(sys.argv[1]); ids=json.loads(sys.argv[2])
c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=5)
try:
 rows=c.execute('SELECT id,room_id,owner,text,reply_to,deleted FROM messages WHERE id IN (?,?) ORDER BY id',ids).fetchall()
 raw=json.dumps(rows,ensure_ascii=True,separators=(',',':')).encode()
 print(json.dumps({'found':len(rows),'digest':hashlib.sha256(raw).hexdigest()}))
finally:c.close()
'''

def require(ok, code):
    if not ok: raise RuntimeError(code)

def capture(args, timeout=90):
    return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL,timeout=timeout).strip()

def as_user(args, timeout=90):
    return capture(['runuser','-u',USER,'--',*args],timeout)

def fingerprint(path):
    value=json.loads(as_user([PYTHON,'-I','-c',FINGERPRINT,str(path),json.dumps(CANARIES)]))
    require(value.get('found')==2,'diagnostic_messages_missing_stop_before_restart')
    return value

def verify_helper(state_path):
    require(state_path.is_absolute() and state_path.name=='state.json'
            and state_path.parent.parent==Path('/root')
            and re.fullmatch(r'mcp-rooms-https-[A-Za-z0-9_-]+',state_path.parent.name),
            'invalid_window_state_location')
    directory=state_path.parent.lstat()
    require(stat.S_ISDIR(directory.st_mode) and directory.st_uid==0
            and stat.S_IMODE(directory.st_mode)==0o700,'unsafe_window_directory')
    helper=state_path.parent/'route.py'; info=helper.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_nlink==1
            and stat.S_IMODE(info.st_mode)==0o600,'unsafe_window_helper')
    require(hashlib.sha256(helper.read_bytes()).hexdigest()==HELPER_SHA256,
            'unexpected_window_helper_do_not_bypass')
    spec=importlib.util.spec_from_file_location('reviewed_rooms_window',helper)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # Pinned operator helper, NOT project/server code.
    state=module.load(state_path)
    require(state.get('window_format')==1 and state.get('accepted')
            and not state.get('removed'),'window_not_accepted_or_already_closed')
    remaining=(datetime.fromisoformat(state['deadline_iso'])-datetime.now(timezone.utc)).total_seconds()
    require(remaining>900,'window_has_less_than_15_minutes_left')
    return module,state

def window_checks(h,state):
    h.check_original_unit()
    props=h.unit_props(UNIT)
    dropin=h.window_dropin(state)
    h.verify_dropin_directory()
    info=dropin.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_nlink==1
            and not info.st_mode & 0o022 and dropin.read_text()==h.DROPIN_TEXT,
            'window_dropin_changed')
    require(props.get('FragmentPath')==str(h.UNIT_PATH)
            and props.get('DropInPaths')==str(dropin)
            and props.get('User')==USER and props.get('WorkingDirectory')==str(HOME/'app')
            and props.get('ActiveState')=='active' and int(props.get('MainPID','0'))>0,
            'unexpected_rooms_service')
    require(not any(p.name.endswith('.conf') and p!=dropin for p in h.DROPIN_DIR.iterdir()),
            'other_runtime_dropin_appeared')
    require(capture(['systemctl','is-active',state['marker']+'-cleanup.timer'])=='active',
            'cleanup_timer_not_active')
    require(h.caddyfile_digest()==state['caddyfile_sha256'],'caddyfile_changed')
    config,_=h.fresh(); found=h.find_marker(config,state['marker'])
    require(len(found)==1 and found[0][1]==state['route'],'window_route_changed')
    actual=as_user(['git','--no-optional-locks','-C',str(HOME/'app'),'rev-parse','HEAD'])
    require(actual==h.SOURCE,'runtime_source_changed')
    return props

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window-state',type=Path,required=True)
    parser.add_argument('--run',action='store_true',required=True)
    args=parser.parse_args()
    if os.geteuid()!=0:
        print(json.dumps({'result':'STOP','reason':'operator_root_console_required'})); return 1
    os.umask(0o077)
    lock=None; directory=None; phase='preflight'; restarted=False
    try:
        lock=os.open('/run/lock/mcp-rooms-route.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        info=os.fstat(lock)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_nlink==1
                and stat.S_IMODE(info.st_mode)==0o600,'unsafe_route_lock')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        h,state=verify_helper(args.window_state)
        before_old=h.old_services(); before_unit=window_checks(h,state)
        initial=fingerprint(DB)
        directory=Path(as_user(['mktemp','-d',str(HOME/'data/recovery-drill.XXXXXX')]))
        require(directory.parent==HOME/'data' and directory.resolve()==directory
                and re.fullmatch(r'recovery-drill\.[A-Za-z0-9]+',directory.name),'unexpected_snapshot_directory')
        import pwd
        info=directory.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid==pwd.getpwnam(USER).pw_uid
                and stat.S_IMODE(info.st_mode)==0o700,'unsafe_snapshot_directory')
        phase='backup_restore_to_new_paths'
        snapshot=directory/'snapshot.db'; restored=directory/'restored.db'
        backup=json.loads(as_user([MAINTENANCE,'backup',str(DB),str(snapshot)]))
        restore=json.loads(as_user([MAINTENANCE,'backup',str(snapshot),str(restored)]))
        verification=json.loads(as_user([MAINTENANCE,'verify',str(restored)]))
        require(backup.get('ok') and restore.get('ok') and verification.get('ok')
                and backup['counts']==restore['counts']==verification['counts'],
                'snapshot_restore_integrity_or_counts_failed')
        require(fingerprint(snapshot)==initial and fingerprint(restored)==initial,
                'snapshot_diagnostic_messages_changed')
        require(h.old_services()==before_old,'old_services_changed_before_restart')
        require(window_checks(h,state)==before_unit,'rooms_service_changed_before_restart')
        require(fingerprint(DB)==initial,'live_diagnostic_messages_changed_before_restart')
        phase='restart_only_rooms_test'
        restarted=True
        capture(['systemctl','restart',UNIT],timeout=60)
        for _ in range(30):
            try:
                props=h.unit_props(UNIT)
                if props.get('ActiveState')=='active':
                    status,_,body=h.tls(h.PREFIX+'/identity')
                    if status==401 and json.loads(body).get('error')=='invalid_token': break
            except Exception: pass
            time.sleep(1)
        else: raise RuntimeError('rooms_not_ready_after_restart')
        after_unit=window_checks(h,state)
        require(after_unit['MainPID']!=before_unit['MainPID'],'restart_pid_did_not_change')
        require(fingerprint(DB)==initial,'diagnostic_messages_changed_after_restart')
        require(json.loads(as_user([MAINTENANCE,'verify',str(DB)])).get('ok'),
                'live_database_integrity_failed')
        require(h.old_services()==before_old,'old_service_states_changed')
        print(json.dumps({'result':'ROOMS RECOVERY DRILL PASS',
            'backup_consistent_sqlite_api':True,'restore_to_new_private_path':True,
            'live_database_overwritten':False,'restored_copy_exposed':False,
            'snapshot_counts_match':True,'two_diagnostic_messages_preserved':True,
            'rooms_test_restarted':True,'old_service_states_unchanged':True,
            'cleanup_deadline_extended':False,'credentials_revoked_or_issued':False,
            'authenticated_client_recheck_required':True,'revocation_rewind_drill':False,
            'encrypted_offhost_backup':False,'private_snapshot_directory':str(directory)}))
        return 0
    except Exception as exc:
        reason=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
        print(json.dumps({'result':'STOP','phase':phase,'reason':reason,
                          'rooms_restart_attempted':restarted,
                          'private_snapshot_directory':str(directory) if directory else None,
                          'live_database_overwritten':False}))
        return 1
    finally:
        if lock is not None: os.close(lock)

if __name__=='__main__': raise SystemExit(main())
