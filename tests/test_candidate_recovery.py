"""Offline synthetic recovery only; no sockets/VPS/real keys or backup artifacts."""
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import pytest
from mcp_rooms import recovery as m
from mcp_rooms import test_candidate as candidate
from mcp_rooms.domain import DomainError
from mcp_rooms.store import RoomStore
from mcp_rooms.identity import IdentityStore, LISTING_SCOPES
from mcp_rooms.draft_store import DraftStore
from mcp_rooms.media_files import PrivatePhotoFiles
from mcp_rooms.media_stage import MediaStageStore
from mcp_rooms.photo_drafts import PhotoDraftStore
from mcp_rooms.publication_store import PublicationStore
from test_media_stage import Worker
from test_draft_store import key, content, RESOURCE


@pytest.fixture
def env(tmp_path):
    tmp_path.chmod(0o700)
    root=tmp_path/'original';candidate.bootstrap(root,RESOURCE)
    store=RoomStore(root/candidate.DB,initialize=False)
    auth=IdentityStore(store,RESOURCE,allow_listing_scopes=True)
    raw_a=(root/'owner.key').read_text().strip();a=auth.authenticate(raw_a)
    principals=[a];raw=[raw_a]
    for name in ('B','C'):
        uid=auth.create_user(name)['user_id']
        _,token=auth.issue_token(uid,ttl_seconds=3600,scopes=sorted(LISTING_SCOPES))
        principals.append(auth.authenticate(token));raw.append(token)
    files=PrivatePhotoFiles(root/'photos');drafts=DraftStore(store,RESOURCE)
    stages=MediaStageStore(drafts,files,Worker());photos=PhotoDraftStore(stages);pub=PublicationStore(photos)
    lid=drafts.create(a,content(title='Synthetic recovery fixture'),category_id='toilets',client_id=key())['listing']['id']
    photo=stages.stage(a,lid,expected_revision=1,client_id=key(),payload=b'synthetic',declared_type='image/png')
    photos.set_photos(a,lid,(photo['media_id'],),expected_revision=1,client_id=key())
    preview=pub.preview(a,lid)
    consent=pub.confirm(a,lid,expected_revision=2,preview_digest=preview['digest'],consent=True,client_id=key())
    pub.publish(a,lid,intent_id=consent['intent_id'],client_id=key())
    # Second private, unattached derivative and a withdrawn publication.
    other=drafts.create(a,content(),category_id='toilets',client_id=key())['listing']['id']
    stages.stage(a,other,expected_revision=1,client_id=key(),payload=b'unattached',declared_type='image/png')
    p=pub.preview(a,other);c=pub.confirm(a,other,expected_revision=1,preview_digest=p['digest'],consent=True,client_id=key())
    pub.publish(a,other,intent_id=c['intent_id'],client_id=key())
    pub.withdraw(a,other,expected_publication_revision=1,client_id=key())
    x=SimpleNamespace(root=root,store=store,auth=auth,actors=principals,raw=raw,files=files,
                      pub=pub,lid=lid,mid=photo['media_id'],parent=tmp_path)
    yield x
    files.close()


def take(x):
    backup=x.parent/'snapshot';m.snapshot(x.root,backup,RESOURCE);return backup


def restored_auth(path):
    return IdentityStore(RoomStore(path/candidate.DB,initialize=False),RESOURCE,allow_listing_scopes=True)


def stable(root):
    # WAL/SHM creation by SQLite RO inspection is not a payload mutation.
    return {p.relative_to(root).as_posix():(p.stat().st_mode,sha256(p.read_bytes()).hexdigest())
            for p in root.rglob('*') if p.is_file() and not p.name.endswith(('-wal','-shm'))}


def test_consistent_snapshot_restore_files_counts_quarantine_and_no_key_delivery(env,capsys):
    x=env;before=stable(x.root);backup=take(x)
    assert stable(x.root)==before
    b=m.verify(backup,RESOURCE);assert b['photo_files']==2 and b['quarantined']
    target=x.parent/'restored';report=m.restore(backup,x.root,target,RESOURCE)
    assert report['counts']==b['counts'] and report['photo_files']==2
    assert m.verify(target,RESOURCE)==report and stable(x.root)==before
    assert not (backup/'owner.key').exists() and not (target/'owner.key').exists()
    for root in (backup,target):
        assert not (root/candidate.MARKER).exists()
        assert root.stat().st_mode&0o777==0o700
        for p in root.rglob('*'):
            assert p.stat().st_mode&0o777==(0o700 if p.is_dir() else 0o600)
        with pytest.raises((DomainError,OSError)):candidate.check(root,RESOURCE)
    assert not capsys.readouterr().out
    assert all(token not in (backup/m.READY).read_text()+(target/m.READY).read_text() for token in x.raw)
    with sqlite3.connect(target/candidate.DB) as db:
        assert db.execute("SELECT COUNT(*) FROM listing_publications WHERE state='active'").fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM publication_consents WHERE consumed_at IS NULL').fetchone()[0]==0
        assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    auth=restored_auth(target)
    assert all(auth.authenticate(token) is not None for token in x.raw)


def test_current_revoke_disable_scope_expiry_and_replacement_do_not_rewind(env):
    x=env;backup=take(x);a,b,c=x.actors
    x.auth.revoke(a.credential_id);x.auth.disable(c.user_id)
    _,replacement=x.auth.issue_token(a.user_id,ttl_seconds=3600,scopes=sorted(LISTING_SCOPES))
    with x.store._db(write=True) as db:
        db.execute('UPDATE credentials SET scopes=?,expires_at=expires_at-100 WHERE id=?',(json.dumps(['listings:read']),b.credential_id))
    before=stable(x.root);target=x.parent/'restored'
    m.restore(backup,x.root,target,RESOURCE)
    auth=restored_auth(target)
    assert auth.authenticate(x.raw[0]) is None and auth.authenticate(x.raw[2]) is None
    assert auth.authenticate(replacement) is None  # Never import a new key from current into old backup.
    assert auth.authenticate(x.raw[1]).scopes==frozenset({'listings:read'})
    assert stable(x.root)==before and x.auth.authenticate(replacement) is not None
    with sqlite3.connect(target/candidate.DB) as db, sqlite3.connect(x.root/candidate.DB) as current:
        assert db.execute('SELECT expires_at FROM credentials WHERE id=?',(b.credential_id,)).fetchone()==current.execute('SELECT expires_at FROM credentials WHERE id=?',(b.credential_id,)).fetchone()


@pytest.mark.parametrize('change',['revoked_in_backup','disabled_in_backup','missing_credential','digest','resource','expired','empty_scope_intersection','missing_user'])
def test_auth_only_narrows_and_other_principal_stays_valid(env,change):
    x=env;a,b,c=x.actors
    if change=='revoked_in_backup':x.auth.revoke(a.credential_id)
    if change=='disabled_in_backup':x.auth.disable(a.user_id)
    backup=take(x)
    with x.store._db(write=True) as db:
        if change=='revoked_in_backup':db.execute('UPDATE credentials SET revoked=0 WHERE id=?',(a.credential_id,))
        elif change=='disabled_in_backup':db.execute('UPDATE users SET disabled=0 WHERE id=?',(a.user_id,))
        elif change=='missing_credential':db.execute('DELETE FROM credentials WHERE id=?',(a.credential_id,))
        elif change=='digest':db.execute('UPDATE credentials SET digest=? WHERE id=?',('0'*64,a.credential_id))
        elif change=='resource':db.execute('UPDATE credentials SET resource=? WHERE id=?',('https://other.invalid/mcp',a.credential_id))
        elif change=='expired':db.execute('UPDATE credentials SET expires_at=0 WHERE id=?',(a.credential_id,))
        elif change=='empty_scope_intersection':db.execute('UPDATE credentials SET scopes=? WHERE id=?',(json.dumps(['rooms:read']),a.credential_id))
        elif change=='missing_user':
            db.execute('DELETE FROM credentials WHERE user_id=?',(c.user_id,));db.execute('DELETE FROM users WHERE id=?',(c.user_id,))
    target=x.parent/'restored';m.restore(backup,x.root,target,RESOURCE);auth=restored_auth(target)
    assert auth.authenticate(x.raw[2] if change=='missing_user' else x.raw[0]) is None
    assert auth.authenticate(x.raw[1]) is not None


@pytest.mark.parametrize('target_kind',['existing','symlink','hardlink','nested_source','nested_backup','shared_parent'])
def test_destinations_refused_without_overwrite(env,target_kind):
    x=env;backup=take(x);target=x.parent/'target'
    if target_kind=='existing':target.mkdir(mode=0o700);(target/'sentinel').write_text('preserve')
    elif target_kind=='symlink':target.symlink_to(x.root,target_is_directory=True)
    elif target_kind=='hardlink':os.link(x.root/candidate.DB,target)
    elif target_kind=='nested_source':target=x.root/'nested'
    elif target_kind=='nested_backup':target=backup/'nested'
    elif target_kind=='shared_parent':
        parent=x.parent/'shared';parent.mkdir(mode=0o755);parent.chmod(0o755);target=parent/'never'
    before=stable(x.root)
    with pytest.raises((DomainError,OSError)):m.restore(backup,x.root,target,RESOURCE)
    assert stable(x.root)==before
    if target_kind=='existing':assert (target/'sentinel').read_text()=='preserve'


@pytest.mark.parametrize('change',['photo_missing','photo_corrupt','photo_symlink','photo_hardlink','photo_mode','unknown_photo','marker_missing','marker_duplicate','future_schema','bad_resource','db_corrupt','db_alias','nonempty_wal','extra_file'])
def test_changed_or_unsealed_backup_never_restores(env,change):
    x=env;backup=take(x);photo=next((backup/'photos').iterdir());marker=backup/m.READY
    if change=='photo_missing':photo.unlink()
    elif change=='photo_corrupt':photo.write_bytes(b'\xff\xd8\xffcorrupt\xff\xd9')
    elif change=='photo_symlink':photo.unlink();photo.symlink_to(next((x.root/'photos').iterdir()))
    elif change=='photo_hardlink':os.link(photo,backup/'photos'/('f'*32+'.jpg'))
    elif change=='photo_mode':photo.chmod(0o644)
    elif change=='unknown_photo':(backup/'photos'/'not-a-photo').write_bytes(b'x')
    elif change=='marker_missing':marker.unlink()
    elif change=='marker_duplicate':marker.write_text('{"schema":1,"schema":1}')
    elif change in ('future_schema','bad_resource'):
        j=json.loads(marker.read_text());j['schema' if change=='future_schema' else 'resource']=2 if change=='future_schema' else 'https://other.invalid/mcp';marker.write_text(json.dumps(j))
    elif change=='db_corrupt':(backup/candidate.DB).write_bytes(b'broken')
    elif change=='db_alias':os.link(backup/candidate.DB,backup/'alias')
    elif change=='nonempty_wal':
        p=backup/(candidate.DB+'-wal');p.write_bytes(b'unhashed WAL');p.chmod(0o600)
    elif change=='extra_file':(backup/'owner.key').write_text('must-not-export')
    before=stable(x.root);target=x.parent/'restored'
    with pytest.raises((DomainError,OSError,sqlite3.Error)):m.restore(backup,x.root,target,RESOURCE)
    assert not target.exists() and stable(x.root)==before


@pytest.mark.parametrize('failure',['copy','backup','seal','reconcile'])
def test_interrupted_output_has_no_ready_marker_and_cannot_retry(env,monkeypatch,failure):
    x=env;backup=take(x);target=x.parent/'restored';before=stable(x.root)
    def stop(*a,**kw):raise OSError('synthetic interrupt')
    with monkeypatch.context() as patch:
        patch.setattr(m,{'copy':'_copy_photos','backup':'backup_database','seal':'_write_json','reconcile':'_reconcile'}[failure],stop)
        with pytest.raises(DomainError,match='media_storage_io'):m.restore(backup,x.root,target,RESOURCE)
    assert target.is_dir() and not (target/m.READY).exists() and not (target/candidate.MARKER).exists()
    with pytest.raises((DomainError,OSError)):m.verify(target,RESOURCE)
    with pytest.raises(FileExistsError):m.restore(backup,x.root,target,RESOURCE)
    assert stable(x.root)==before


@pytest.mark.parametrize('which',['profile','snapshot'])
def test_busy_profile_or_backup_lock_refuses_before_target(env,which):
    x=env;backup=take(x);root=x.root if which=='profile' else backup
    with (root/'profile.lock').open('rb') as fd:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(DomainError,match='recovery_profile_busy'):m.restore(backup,x.root,x.parent/'restored',RESOURCE)
    assert not (x.parent/'restored').exists()


def test_wrong_or_missing_current_authority_never_serves(env):
    x=env;backup=take(x);other=x.parent/'other';candidate.bootstrap(other,RESOURCE)
    with pytest.raises(DomainError,match='recovery_wrong_authority'):m.restore(backup,other,x.parent/'restored',RESOURCE)
    with pytest.raises((DomainError,OSError)):m.restore(backup,x.parent/'missing',x.parent/'restored',RESOURCE)
    assert not (x.parent/'restored').exists()


@pytest.mark.parametrize('state',['reserved','purging','missing','wrong_link','bad_projection','orphan'])
def test_source_media_integrity_failures_are_not_silently_repaired(env,state):
    x=env
    with x.store._db(write=True) as db:
        if state=='reserved':db.execute("UPDATE media_stages SET state='reserved' WHERE id=?",(x.mid,))
        elif state=='purging':db.execute("UPDATE media_stages SET cleanup_state='purging' WHERE id=?",(x.mid,))
        elif state=='wrong_link':db.execute('UPDATE media_draft_photos SET position=7 WHERE media_id=?',(x.mid,))
        elif state=='bad_projection':db.execute("UPDATE listing_publications SET projection='{}' WHERE listing_id=?",(x.lid,))
    if state=='missing':next((x.root/'photos').iterdir()).unlink()
    if state=='orphan':
        p=x.root/'photos'/('f'*32+'.jpg');p.write_bytes(b'\xff\xd8\xffCI orphan\xff\xd9');p.chmod(0o600)
        backup=take(x);assert m.verify(backup,RESOURCE)['photo_files']==3;return
    before=stable(x.root)
    with pytest.raises(DomainError):m.snapshot(x.root,x.parent/'snapshot',RESOURCE)
    assert stable(x.root)==before and not (x.parent/'snapshot').exists()


def test_stale_consent_and_publication_not_resurrected_and_cli_no_secrets(env,capsys):
    x=env;backup=take(x)
    x.pub.withdraw(x.actors[0],x.lid,expected_publication_revision=1,client_id=key())
    target=x.parent/'restored'
    assert m.main(['restore','--snapshot',str(backup),'--current',str(x.root),'--destination',str(target),'--resource',RESOURCE])==0
    output=capsys.readouterr().out
    assert 'quarantined' in output and all(raw not in output for raw in x.raw)
    auth=restored_auth(target);drafts=DraftStore(auth.store,RESOURCE)
    with PrivatePhotoFiles(target/'photos') as files:
        pub=PublicationStore(PhotoDraftStore(MediaStageStore(drafts,files,Worker())))
        with pytest.raises(DomainError,match='listing_unavailable'):pub.public_get(x.lid)
    assert m.main(['verify','--source',str(x.parent/'missing'),'--resource',RESOURCE])==1
    assert 'recovery_storage_error' in capsys.readouterr().out


@pytest.mark.parametrize('target',['credentials','content','projection','photo_item'])
def test_malformed_persisted_documents_refuse_without_ready(env,target):
    x=env;backup=take(x) if target=='credentials' else None
    with x.store._db(write=True) as db:
        if target=='credentials':db.execute("UPDATE credentials SET scopes='null' WHERE id=?",(x.actors[0].credential_id,))
        elif target=='content':db.execute("UPDATE market_drafts SET content='null' WHERE id=?",(x.lid,))
        elif target=='projection':db.execute("UPDATE listing_publications SET projection='null' WHERE listing_id=?",(x.lid,))
        else:db.execute('UPDATE listing_publications SET projection=? WHERE listing_id=?',(json.dumps({'id':x.lid,'photos':[None]}),x.lid))
    dest=x.parent/'result'
    with pytest.raises(DomainError):
        if backup:m.restore(backup,x.root,dest,RESOURCE)
        else:m.snapshot(x.root,dest,RESOURCE)
    assert not (dest/m.READY).exists() and not (dest/candidate.MARKER).exists()


def test_sqlite_writer_freeze_is_held_while_copying_photos(env,monkeypatch):
    x=env;original=m._copy_photos;seen=[]
    def checked(*args):
        db=sqlite3.connect(x.root/candidate.DB,timeout=0)
        try:
            with pytest.raises(sqlite3.OperationalError,match='locked'):db.execute('BEGIN IMMEDIATE')
            seen.append(True)
        finally:db.close()
        return original(*args)
    monkeypatch.setattr(m,'_copy_photos',checked)
    take(x);assert seen==[True]


@pytest.mark.parametrize('operation',['snapshot','restore'])
def test_ready_write_then_fsync_failure_removes_marker(env,monkeypatch,operation):
    x=env;backup=take(x);target=x.parent/'interrupted';before=stable(x.root)
    original=m._write_json
    def failed(path,value):
        original(path,value)
        raise OSError('synthetic final fsync failure')
    monkeypatch.setattr(m,'_write_json',failed)
    with pytest.raises(DomainError,match='media_storage_io'):
        if operation=='snapshot':m.snapshot(x.root,target,RESOURCE)
        else:m.restore(backup,x.root,target,RESOURCE)
    assert not (target/m.READY).exists() and not (target/candidate.MARKER).exists()
    assert stable(x.root)==before


def test_snapshot_includes_committed_wal_not_just_main_database(env):
    x=env
    db=sqlite3.connect(x.root/candidate.DB)
    try:
        db.execute('PRAGMA wal_autocheckpoint=0')
        db.execute('UPDATE users SET display_name=? WHERE id=?',('CI committed WAL state',x.actors[1].user_id));db.commit()
        assert (x.root/(candidate.DB+'-wal')).stat().st_size>0
        backup=take(x)
        with sqlite3.connect(backup/candidate.DB) as copied:
            assert copied.execute('SELECT display_name FROM users WHERE id=?',(x.actors[1].user_id,)).fetchone()[0]=='CI committed WAL state'
    finally:db.close()
