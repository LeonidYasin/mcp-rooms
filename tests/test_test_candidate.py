"""Fresh synthetic profiles only, in Actions. No VPS/systemd/network sockets."""
import json
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import sys
import pytest
from starlette.testclient import TestClient
from mcp_rooms import test_candidate as m
from mcp_rooms.domain import DomainError
from mcp_rooms.identity import IdentityStore, LISTING_SCOPES
from mcp_rooms.store import RoomStore
from mcp_rooms.media_worker import PhotoWorker
from mcp_rooms.media_http import MediaHTTP
from test_server import RESOURCE, rpc, tool, NAMES
from test_market_server import MARKET_NAMES
from test_draft_store import key

NATIVE=sys.platform=='linux' and sys.version_info>=(3,11)

@pytest.fixture
def profile(tmp_path):
    tmp_path.chmod(0o700)
    root=tmp_path/'fresh-test'
    result=m.bootstrap(root,RESOURCE)
    assert result['key_ttl_seconds']==3600
    yield root


def auth(root):
    return IdentityStore(RoomStore(root/m.DB,initialize=False),RESOURCE,allow_listing_scopes=True)


def test_fresh_profile_minimum_grants_private_files_and_no_raw_output(profile,capsys):
    root=profile;assert m.check(root,RESOURCE)==root
    raw=(root/'owner.key').read_text().strip()
    actor=auth(root).authenticate(raw)
    assert actor.scopes==LISTING_SCOPES
    assert raw not in (root/m.MARKER).read_text()
    assert not capsys.readouterr().out
    for name in (m.DB,m.MARKER,'owner.key','profile.lock'):
        assert (root/name).stat().st_mode&0o777==0o600
    for path in (root,root/'photos'):assert path.stat().st_mode&0o777==0o700
    with sqlite3.connect(root/m.DB) as db:
        assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM credentials').fetchone()[0]==1
        assert db.execute("SELECT COUNT(*) FROM sqlite_schema WHERE name LIKE 'browser_%'").fetchone()[0]==0


def test_existing_profile_never_reinitialized(profile):
    before={p.name:sha256(p.read_bytes()).hexdigest() for p in profile.iterdir() if p.is_file()}
    with pytest.raises(FileExistsError):m.bootstrap(profile,RESOURCE)
    assert {p.name:sha256(p.read_bytes()).hexdigest() for p in profile.iterdir() if p.is_file()}==before


@pytest.mark.parametrize('change',['missing_marker','duplicate_marker','future_marker','resource','missing_db','db_link',
                                  'db_mode','marker_mode','directory_mode','photos_link','lock_link',
                                  'room_version','market_version','media_version','publication_version',
                                  'missing_table','new_trigger','new_index'])
def test_bad_state_fails_without_repair(profile,change,tmp_path):
    root=profile
    if change=='missing_marker':(root/m.MARKER).unlink()
    elif change=='duplicate_marker':(root/m.MARKER).write_text('{"profile":"x","profile":"y"}')
    elif change=='future_marker':
        j=json.loads((root/m.MARKER).read_text());j['schema']=2;(root/m.MARKER).write_text(json.dumps(j))
    elif change=='resource':
        with pytest.raises(DomainError):m.check(root,'https://other.invalid/mcp')
        return
    elif change=='missing_db':(root/m.DB).unlink()
    elif change=='db_link':os.link(root/m.DB,root/'db-alias')
    elif change=='db_mode':(root/m.DB).chmod(0o644)
    elif change=='marker_mode':(root/m.MARKER).chmod(0o644)
    elif change=='directory_mode':root.chmod(0o755)
    elif change=='photos_link':
        (root/'photos').rename(root/'photos-moved');(root/'photos').symlink_to(root/'photos-moved')
    elif change=='lock_link':os.link(root/'profile.lock',root/'lock-alias')
    else:
        sql={'room_version':'PRAGMA user_version=1','market_version':'UPDATE market_schema SET version=1',
             'media_version':'UPDATE media_stage_schema SET version=2',
             'publication_version':'UPDATE publication_schema SET version=2',
             'missing_table':'DROP TABLE publication_audit',
             'new_trigger':'CREATE TRIGGER extra AFTER UPDATE ON users BEGIN SELECT 1; END',
             'new_index':'CREATE INDEX extra ON users(display_name)'}[change]
        with sqlite3.connect(root/m.DB) as db:db.execute(sql)
    # SQLite mode=ro may create WAL/SHM sidecars; that is NOT a schema/data repair.
    # Hash stable payloads rather than dumping a DB/private delivery key on failure.
    def snapshot():
        return {p.name:(p.lstat().st_mode,sha256(p.read_bytes()).hexdigest())
                for p in root.iterdir() if p.is_file() and not p.is_symlink()
                and not p.name.endswith(('-wal','-shm'))}
    before=snapshot()
    with pytest.raises((DomainError,OSError,sqlite3.Error)):m.check(root,RESOURCE)
    after=snapshot()
    assert after==before


def test_bad_resource_and_shared_parent_do_not_create_target(tmp_path):
    target=tmp_path/'never-created'
    with pytest.raises(DomainError):m.bootstrap(target,'http://bad.invalid/mcp')
    assert not target.exists()
    tmp_path.chmod(0o755)
    with pytest.raises(DomainError):m.bootstrap(target,RESOURCE)
    assert not target.exists()


def test_existing_only_store_never_creates_migrates_or_chmods(tmp_path):
    path=tmp_path/'missing.db'
    with pytest.raises(OSError):RoomStore(path,initialize=False)
    assert not path.exists()
    store=RoomStore(path)
    with store._db(write=True) as db:db.execute('PRAGMA user_version=1')
    with pytest.raises(DomainError):RoomStore(path,initialize=False)
    with sqlite3.connect(path) as db:assert db.execute('PRAGMA user_version').fetchone()[0]==1


def test_existing_only_store_does_not_recreate_deleted_database(profile):
    store=RoomStore(profile/m.DB,initialize=False)
    (profile/m.DB).unlink()
    with pytest.raises(sqlite3.Error):
        with store._db():pass
    assert not (profile/m.DB).exists()


@pytest.mark.parametrize('point',['delivery','marker'])
def test_bootstrap_delivery_failure_revokes_disables_and_leaves_no_ready_marker(tmp_path,monkeypatch,point):
    root=tmp_path/'failed-new'
    if point=='delivery':
        original=m.write_private_token
        def fail(path,raw):original(path,raw);raise OSError('synthetic delivery failure')
        monkeypatch.setattr(m,'write_private_token',fail)
    else:
        original=m._write_json
        def fail(path,value):original(path,value);raise OSError('synthetic final sync failure')
        monkeypatch.setattr(m,'_write_json',fail)
    with pytest.raises(OSError):m.bootstrap(root,RESOURCE)
    assert root.exists() and not (root/m.MARKER).exists()
    assert auth(root).authenticate((root/'owner.key').read_text().strip()) is None
    with sqlite3.connect(root/m.DB) as db:
        assert db.execute('SELECT disabled FROM users').fetchone()[0]==1
        assert db.execute('SELECT revoked FROM credentials').fetchone()[0]==1


@pytest.mark.parametrize('value',[0,3,True,'1',None])
def test_parallelism_not_client_configurable(value):
    with pytest.raises(DomainError):PhotoWorker(max_parallel=value)
    with pytest.raises(DomainError):MediaHTTP(None,upload_slots=value)


@pytest.mark.skipif(not NATIVE,reason='Native candidate needs Linux Python>=3.11')
def test_single_process_and_one_worker_upload_slot(profile):
    with m.compose(profile,RESOURCE) as candidate:
        assert candidate.worker.max_parallel==1
        assert candidate.worker._slots.acquire(blocking=False)
        assert not candidate.worker._slots.acquire(blocking=False)
        candidate.worker._slots.release()
        assert candidate.app.media_http.uploads.total==1
        assert not candidate.app.registration_enabled
        assert candidate.app.browser_http is None
        with pytest.raises(DomainError,match='candidate_already_running'):m.compose(profile,RESOURCE)
    with m.compose(profile,RESOURCE):pass


@pytest.mark.skipif(not NATIVE,reason='Native candidate needs Linux Python>=3.11')
def test_compose_no_startup_ddl_or_issuance_or_key_read(profile,monkeypatch):
    statements=[];connect=sqlite3.connect
    def traced(*a,**kw):
        db=connect(*a,**kw);db.set_trace_callback(statements.append);return db
    monkeypatch.setattr(sqlite3,'connect',traced)
    def forbidden(*a,**kw):pytest.fail('startup mutation or credential read')
    for cls,name in [(m.DraftStore,'initialize')]+[(m.MediaStageStore,'initialize'),(m.PublicationStore,'initialize'),(m.IdentityStore,'issue_token')]:
        monkeypatch.setattr(cls,name,forbidden)
    (profile/'owner.key').unlink()  # compose must not need the bootstrap delivery file.
    with m.compose(profile,RESOURCE):pass
    assert not any(s.lstrip().upper().startswith(('CREATE ','ALTER ','DROP ','INSERT ','UPDATE ','DELETE ')) for s in statements)


@pytest.mark.skipif(not NATIVE,reason='Native candidate needs Linux Python>=3.11')
def test_candidate_real_sdk_is_owner_only_and_registration_closed(profile):
    raw=(profile/'owner.key').read_text().strip()
    with m.compose(profile,RESOURCE) as candidate:
        with TestClient(candidate.app,base_url='https://rooms.example') as c:
            names={x['name'] for x in rpc(c,raw,'tools/list').json()['result']['tools']}
            assert names==NAMES|MARKET_NAMES
            assert tool(c,raw,'rooms_list')['error']=='insufficient_scope'
            assert c.post('/register',json={}).status_code==403
            assert c.post('/browser/session',json={}).status_code==404
            result=tool(c,raw,'listings_create',content=dict(title='Synthetic',description='Only CI',category='things',kind='offer',modes=['shipping']),category_id='things',client_id=key())
            assert result['ok']
            candidate.app.auth.revoke(auth(profile).authenticate(raw).credential_id)
            assert rpc(c,raw,'tools/list').status_code==401


def test_cli_check_sanitized_failure_and_no_serve_side_effect(tmp_path,capsys):
    assert m.main(['check','--state',str(tmp_path/'absent'),'--resource',RESOURCE])==1
    out=capsys.readouterr().out
    assert json.loads(out)=={'ok':False,'error':'candidate_storage_error'}
    assert str(tmp_path) not in out and 'Traceback' not in out


def test_compensation_failure_is_explicit_and_other_cleanup_still_runs(tmp_path,monkeypatch):
    original=m.write_private_token
    def fail(path,raw):original(path,raw);raise OSError('synthetic private failure')
    def revoke_fail(*args):raise OSError('synthetic revoke failure')
    monkeypatch.setattr(m,'write_private_token',fail)
    monkeypatch.setattr(m.IdentityStore,'revoke',revoke_fail)
    root=tmp_path/'failed'
    with pytest.raises(DomainError,match='candidate_bootstrap_recovery_required'):m.bootstrap(root,RESOURCE)
    assert not (root/m.MARKER).exists()
    with sqlite3.connect(root/m.DB) as db:assert db.execute('SELECT disabled FROM users').fetchone()[0]==1


def test_cli_unexpected_error_sanitized(tmp_path,capsys,monkeypatch):
    def fail(*args):raise RuntimeError('secret and private path')
    monkeypatch.setattr(m,'check',fail)
    assert m.main(['check','--state',str(tmp_path/'x'),'--resource',RESOURCE])==1
    assert json.loads(capsys.readouterr().out)=={'ok':False,'error':'candidate_unavailable'}


@pytest.mark.parametrize('suffix',['-wal','-shm'])
@pytest.mark.parametrize('alias',['symlink','hardlink'])
def test_sqlite_sidecar_alias_rejected_before_sqlite_open(profile,tmp_path,suffix,alias):
    target=tmp_path/'protected';target.write_bytes(b'untouched synthetic file');target.chmod(0o600)
    side=profile/(m.DB+suffix)
    side.unlink(missing_ok=True)
    if alias=='symlink':side.symlink_to(target)
    else:os.link(target,side)
    with pytest.raises((DomainError,OSError)):m.check(profile,RESOURCE)
    assert target.read_bytes()==b'untouched synthetic file'


def test_hot_journal_requires_explicit_review_not_startup_recovery(profile):
    journal=profile/(m.DB+'-journal');journal.write_bytes(b'synthetic journal marker');journal.chmod(0o600)
    with pytest.raises(DomainError,match='candidate_database_mismatch'):m.check(profile,RESOURCE)
    assert journal.read_bytes()==b'synthetic journal marker'


@pytest.mark.skipif(not NATIVE,reason='Linux native candidate requires Python>=3.11')
def test_sandbox_startup_failure_releases_profile_lock_without_plain_fallback(profile,monkeypatch):
    def fail(self):raise DomainError('media_sandbox_unavailable')
    with monkeypatch.context() as patch:
        patch.setattr(PhotoWorker,'check_sandbox',fail)
        with pytest.raises(DomainError,match='media_sandbox_unavailable'):m.compose(profile,RESOURCE)
    with m.compose(profile,RESOURCE) as candidate:
        assert candidate.app is not None
