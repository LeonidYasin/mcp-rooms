"""Synthetic auth-drill logic with temporary DBs; no VPS/systemd/network/real keys."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest
from mcp_rooms.identity import IdentityStore
from mcp_rooms.store import RoomStore

ROOT=Path(__file__).resolve().parents[1]

def module():
    path=ROOT/'deploy/vps_rooms_auth_drill.py'
    spec=importlib.util.spec_from_file_location('auth_drill_contract',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result

def setup(tmp_path):
    d=tmp_path/'private';d.mkdir(mode=0o700)
    db=d/'live.db';out=d/'out';out.mkdir(mode=0o700)
    namespace={'__name__':'canary_ci_only'}
    exec(compile(module().CHILD,'synthetic_canary','exec'),namespace)
    namespace['DB']=str(db)
    auth=IdentityStore(RoomStore(db),namespace['RESOURCE'])
    user=auth.create_user('Untouched real-client surrogate')['user_id']
    _,token=auth.issue_token(user)
    calls=[]
    def probe(raw,expected_user,expected_status):
        principal=auth.authenticate(raw)
        calls.append(expected_status)
        if expected_status==200:
            assert principal is not None and principal.user_id==expected_user
        else:
            assert expected_status==401 and principal is None
    namespace['probe']=probe
    return namespace,auth,user,token,db,out,calls

def assert_original_untouched(auth,user,token,db):
    assert auth.authenticate(token).user_id==user
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT disabled FROM users WHERE id=?',(user,)).fetchone()==(0,)
        assert c.execute('SELECT COUNT(*) FROM users WHERE id<>? AND disabled=0',(user,)).fetchone()==(0,)
        assert c.execute('SELECT COUNT(*) FROM credentials WHERE user_id<>? AND revoked=0',(user,)).fetchone()==(0,)

def test_synthetic_revoke_rewind_reconcile_cleanup_preserves_original(tmp_path):
    ns,auth,user,token,db,out,calls=setup(tmp_path)
    report=ns['run'](out)
    assert report['result']=='ROOMS DISPOSABLE AUTH DRILL PASS'
    assert report['isolated_restore_revocation_rewind_observed']
    assert report['isolated_restore_disable_rewind_observed']
    assert report['synthetic_revocation_and_disable_reapplied_to_copy']
    assert report['second_principal_unaffected_by_first_key_revocation']
    assert report['all_synthetic_keys_revoked_and_users_disabled']
    assert calls==[200,200,200,401,200,200,401,200,401,401,401]
    assert_original_untouched(auth,user,token,db)
    ledger=json.loads((out/'canary-ledger.json').read_text())
    assert ledger['phase']=='cleanup_complete'
    assert len(ledger['user_ids'])==2 and len(ledger['credential_ids'])==3
    assert user not in ledger['user_ids']
    assert 'rm1_' not in json.dumps(report)
    assert 'rm1_' not in (out/'canary-ledger.json').read_text()
    assert token not in (out/'canary-ledger.json').read_text()
    assert (out/'before-revocation.db').exists() and (out/'isolated-restored.db').exists()

@pytest.mark.parametrize('stage',['probe','backup'])
def test_partial_failure_still_revokes_only_synthetic_keys(tmp_path,stage):
    ns,auth,user,token,db,out,calls=setup(tmp_path)
    def fail(*a,**kw):raise RuntimeError('injected_failure')
    ns['probe' if stage=='probe' else 'backup_database']=fail
    with pytest.raises(RuntimeError,match='injected_failure'):
        ns['run'](out)
    assert_original_untouched(auth,user,token,db)
    assert json.loads((out/'canary-ledger.json').read_text())['phase']=='cleanup_complete'

def test_pinned_recovery_checksum():
    assert module().RECOVERY_SHA256==hashlib.sha256((ROOT/'deploy/vps_rooms_recovery_drill.py').read_bytes()).hexdigest()

def test_reject_unknown_recovery_helper_before_import():
    with pytest.raises(RuntimeError,match='unexpected_recovery_helper_path'):
        module().load_recovery(Path('/tmp/drill.py'))

def test_synthetic_ttl_and_scope_are_bounded(tmp_path):
    ns,*_=setup(tmp_path)
    assert ns['TTL_SECONDS']==600
    assert "scopes=('rooms:read',)" in module().CHILD
