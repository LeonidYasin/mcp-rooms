"""Offline operator recovery rehearsal. Never overwrites or serves a restored copy.

Requires the original profile as current security authority. If it is lost, refuse;
this is not an independent disaster-recovery/revocation-ledger implementation.
"""
import argparse
from contextlib import contextmanager, nullcontext
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from .domain import DomainError
from .identity import resource_url, SCOPES, LISTING_SCOPES
from .maintenance import backup_database
from .media_files import PrivatePhotoFiles, _KEY, MAX_FILES, MAX_TOTAL_BYTES
from .media_contract import MAX_OUTPUT_BYTES, OUTPUT_SIDE
from .media_stage import MAX_RECEIPTS, POLICY as MEDIA_POLICY
from .photo_drafts import PhotoDraftStore
from .draft_store import DraftStore
from .publication_preview import public_card
from .preview_contract import canonical_json
from .store import RoomStore
from .test_candidate import (DB, MARKER, REQUIRED, check, _root, _directory, _file,
                             _database, _write_json, _pairs)

POLICY = 'mcp-rooms/offline-quarantine/v1'
READY = 'recovery.json'  # Deliberately NOT candidate profile.json.
MAX_MANIFEST = 128 * 1024
DB_BOUND = RoomStore.MAX_PAGES * 4096


def _read(path, maximum):
    """Pinned, bounded regular file. No alias/device/shared file or mutable read."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1
                or not 0 < before.st_size <= maximum):
            raise DomainError('recovery_unsafe_file')
        data = bytearray()
        while len(data) <= maximum:
            block = os.read(fd, min(65536, maximum + 1 - len(data)))
            if not block: break
            data.extend(block)
        after, named = os.fstat(fd), path.lstat()
        fields = ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
        if (len(data) != before.st_size
                or any(getattr(before,k) != getattr(after,k) or getattr(after,k) != getattr(named,k) for k in fields)):
            raise DomainError('recovery_changed_file')
        return bytes(data)
    finally: os.close(fd)


def _digest(path, maximum):
    # DB <=64MiB; hashing is bounded, no data leaves the process. Photo <=2MiB.
    data = _read(path, maximum)
    return {'sha256': sha256(data).hexdigest(), 'byte_size': len(data)}


def _write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def _separate(*paths):
    for i,a in enumerate(paths):
        for b in paths[i+1:]:
            if a == b or a.is_relative_to(b) or b.is_relative_to(a):
                raise DomainError('recovery_overlapping_paths')


@contextmanager
def _lock(root):
    _directory(root)
    before = root.stat()
    _file(root/'profile.lock', 0, empty=True)
    fd = os.open(root/'profile.lock', os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise DomainError('recovery_profile_busy') from None
        _directory(root)
        if (before.st_dev,before.st_ino) != (root.stat().st_dev,root.stat().st_ino):
            raise DomainError('recovery_unsafe_directory')
        yield
    finally: os.close(fd)


@contextmanager
def _frozen(root, resource):
    """Profile lock -> photo flock -> SQLite writer reservation; no source writes."""
    with _lock(root):
        check(root, resource)
        with PrivatePhotoFiles(root/'photos') as files, files._guard():
            db = sqlite3.connect((root/DB).as_uri()+'?mode=rw', uri=True, timeout=5)
            db.row_factory = sqlite3.Row
            try:
                db.execute('PRAGMA trusted_schema=OFF')
                db.execute('BEGIN IMMEDIATE')
                # Another readonly connection can back up the committed WAL view
                # while this empty write transaction excludes all other DB writers.
                yield db
            finally:
                db.rollback(); db.close()


def _new(root):
    os.mkdir(root, 0o700)  # Existing/failed target is never repaired or reused.
    _directory(root)
    (root/'photos').mkdir(mode=0o700)
    _write(root/'profile.lock', b'')


def _origin(root):
    st = root.stat()
    return {'device': st.st_dev, 'inode': st.st_ino}


def _audit(root, resource, *, already_locked=False):
    """Schema/integrity, derivative bytes, ordered links and publication projections.

    Orphan derivatives are preserved, never auto-deleted. Incomplete upload/cleanup
    states require separate reviewed maintenance, not a snapshot advertised as ready.
    """
    _database(root/DB)
    with PrivatePhotoFiles(root/'photos') as files, (nullcontext() if already_locked else files._guard()):
        files._inventory()
        inventory = []
        for path in sorted((root/'photos').iterdir()):
            data = _read(path, MAX_OUTPUT_BYTES)
            if not data.startswith(b'\xff\xd8\xff') or not data.endswith(b'\xff\xd9'):
                raise DomainError('recovery_bad_derivative')
            inventory.append({'blob_key': path.name, 'sha256': sha256(data).hexdigest(), 'byte_size': len(data)})
        by_key = {p['blob_key']:p for p in inventory}
        db = sqlite3.connect((root/DB).as_uri()+'?mode=ro', uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA query_only=ON'); db.execute('PRAGMA trusted_schema=OFF'); db.execute('BEGIN')
            counts = {name:db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in sorted(REQUIRED)}
            stages = {r['id']:dict(r) for r in db.execute('SELECT * FROM media_stages')}
            if len(stages) > MAX_RECEIPTS: raise DomainError('recovery_media_mismatch')
            used = set()
            for row in stages.values():
                if row['state']=='reserved' or row['cleanup_state']=='purging':
                    raise DomainError('recovery_incomplete_media')
                if row['blob_key'] is None or row['cleanup_state']=='purged': continue
                key = row['blob_key']; item = by_key.get(key)
                if (key in used or item is None or row['policy']!=MEDIA_POLICY or row['resource']!=resource
                        or item['sha256']!=row['sha256'] or item['byte_size']!=row['byte_size']
                        or any(type(row[k]) is not int or not 1<=row[k]<=OUTPUT_SIDE for k in ('width','height'))):
                    raise DomainError('recovery_media_mismatch')
                used.add(key)
            drafts = {r['id']:dict(r) for r in db.execute('SELECT * FROM market_drafts')}
            links_by_draft = {}
            for row in db.execute('SELECT * FROM media_draft_photos ORDER BY draft_id,position'):
                links_by_draft.setdefault(row['draft_id'], []).append(dict(row))
            if set(links_by_draft)-set(drafts): raise DomainError('recovery_media_mismatch')
            ordered = {}
            for lid,draft in drafts.items():
                links = links_by_draft.get(lid, [])
                ids = [p['media_id'] for p in links]
                content = json.loads(draft['content'])
                if (len(ids)>8 or [p['position'] for p in links]!=list(range(len(ids)))
                        or content.get('media_ids')!=ids):
                    raise DomainError('recovery_media_mismatch')
                rows = []
                for mid in ids:
                    row = stages.get(mid)
                    if (not row or row['draft_id']!=lid or row['user_id']!=draft['user_id']
                            or row['state']!='staged' or row['revision']!=draft['revision']
                            or row['resource']!=resource or row['cleanup_state']!='live'
                            or row['expires_at']>draft['expires_at']):
                        raise DomainError('recovery_media_mismatch')
                    rows.append(row)
                ordered[lid]=rows
            categories = {r['id']:dict(r) for r in db.execute('SELECT * FROM market_categories')}
            now = int(time.time()*1000)
            for pub in db.execute('SELECT * FROM listing_publications'):
                card = json.loads(pub['projection']); lid=pub['listing_id']
                if card.get('id')!=lid or type(card.get('photos')) is not list or len(card['photos'])>8:
                    raise DomainError('recovery_publication_mismatch')
                for p in card['photos']:
                    row = stages.get(p.get('media_id'))
                    if (not row or row['draft_id']!=lid or row['user_id']!=pub['user_id']
                            or any(p.get(k)!=row[k] for k in ('sha256','byte_size','width','height'))):
                        raise DomainError('recovery_publication_mismatch')
                if pub['state']!='active' or pub['expires_at']<=now: continue
                draft=drafts[lid]; path=[]; cid=draft['category_id']; seen=set()
                while cid is not None:
                    if cid in seen or cid not in categories: raise DomainError('recovery_publication_mismatch')
                    seen.add(cid); category=categories[cid]
                    path.append({k:category[k] for k in ('id','parent_id','root','title')}); cid=category['parent_id']
                record=json.loads(canonical_json(DraftStore._record(draft)))
                expected=public_card(record,list(reversed(path)),PhotoDraftStore._photos(ordered[lid]),pub['epoch'],pub['updated_at'])
                if (draft['user_id']!=pub['user_id'] or draft['revision']!=pub['revision']
                        or sha256(canonical_json(record).encode()).hexdigest()!=pub['source_hash']
                        or canonical_json(expected)!=pub['projection']):
                    raise DomainError('recovery_publication_mismatch')
            return {'files':inventory, 'counts':counts}
        except (ValueError, TypeError, KeyError, RecursionError):
            raise DomainError('recovery_media_mismatch') from None
        finally: db.close()


def _manifest(root, resource, kind, origin, schema_hash, security=None):
    _database(root/DB,schema_hash)
    audit = _audit(root, resource)
    return {'schema':1, 'policy':POLICY, 'kind':kind, 'resource':resource,
            'schema_hash':schema_hash, 'origin':origin, 'database':_digest(root/DB,DB_BOUND),
            **audit, 'security':security}


def _seal(root, manifest):
    """Ready last. Failed final fsync cannot leave a success marker knowingly."""
    try:
        _write_json(root/READY, manifest)
    except BaseException:
        try: (root/READY).unlink(missing_ok=True)
        except OSError: raise DomainError('recovery_marker_cleanup_required') from None
        raise


def _verify(root, resource, *, kind=None):
    _directory(root); _directory(root/'photos')
    allowed={DB,'photos','profile.lock',READY,DB+'-wal',DB+'-shm'}
    if set(p.name for p in root.iterdir())-allowed: raise DomainError('recovery_unexpected_file')
    # Sealed artifacts never depend on un-hashed WAL payloads.
    wal=root/(DB+'-wal')
    if os.path.lexists(wal): _file(wal,0,empty=True)
    try: m=json.loads(_read(root/READY,MAX_MANIFEST),object_pairs_hook=_pairs)
    except (ValueError,UnicodeError,RecursionError): raise DomainError('recovery_invalid_manifest') from None
    fields={'schema','policy','kind','resource','schema_hash','origin','database','files','counts','security'}
    if (type(m) is not dict or set(m)!=fields or type(m['schema']) is not int or m['schema']!=1
            or m['policy']!=POLICY or m['kind'] not in ('snapshot','restored')
            or (kind is not None and m['kind']!=kind) or m['resource']!=resource
            or type(m['schema_hash']) is not str or not re.fullmatch('[0-9a-f]{64}',m['schema_hash'])
            or type(m['origin']) is not dict or set(m['origin'])!={'device','inode'}
            or any(type(v) is not int or v<0 for v in m['origin'].values())
            or (m['kind']=='snapshot' and m['security'] is not None)
            or (m['kind']=='restored' and m['security']!={'current_authority_checked':True,'publications_withdrawn':True,'quarantined':True})):
        raise DomainError('recovery_invalid_manifest')
    _database(root/DB,m['schema_hash'])
    actual=_manifest(root,resource,m['kind'],m['origin'],m['schema_hash'],m['security'])
    if canonical_json(actual)!=canonical_json(m): raise DomainError('recovery_manifest_mismatch')
    return m


def _copy_photos(source, destination, files):
    if len(files)>MAX_FILES or sum(p['byte_size'] for p in files)>MAX_TOTAL_BYTES:
        raise DomainError('recovery_media_mismatch')
    for p in files:
        if type(p['blob_key']) is not str or not _KEY.fullmatch(p['blob_key']):
            raise DomainError('recovery_media_mismatch')
        data=_read(source/'photos'/p['blob_key'],MAX_OUTPUT_BYTES)
        if len(data)!=p['byte_size'] or sha256(data).hexdigest()!=p['sha256']:
            raise DomainError('recovery_changed_file')
        _write(destination/'photos'/p['blob_key'],data)
    fd=os.open(destination/'photos',os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def _report(m):
    return {'ok':True,'kind':m['kind'],'quarantined':True,'counts':m['counts'],
            'photo_files':len(m['files']),'photo_bytes':sum(p['byte_size'] for p in m['files'])}


def snapshot(source, destination, resource):
    resource=resource_url(resource); source=_root(source); destination=_root(destination)
    _separate(source,destination)
    with _frozen(source,resource):
        before=_audit(source,resource,already_locked=True)
        schema_hash=_database(source/DB)
        _new(destination)
        backup_database(source/DB,destination/DB)
        _copy_photos(source,destination,before['files'])
        result=_manifest(destination,resource,'snapshot',_origin(source),schema_hash)
        if any(result[k]!=before[k] for k in ('counts','files')): raise DomainError('recovery_manifest_mismatch')
        _seal(destination,result)
        return _report(result)


def _scopes(raw):
    try: value=json.loads(raw)
    except (ValueError,TypeError): raise DomainError('recovery_security_invalid') from None
    if (type(value) is not list or not value or any(type(s) is not str or s not in SCOPES|LISTING_SCOPES for s in value)):
        raise DomainError('recovery_security_invalid')
    return set(value)


def _reconcile(path, current, resource):
    """Only narrowing. Current is a locked original DB connection, never JSON export."""
    users={r['id']:dict(r) for r in current.execute('SELECT * FROM users')}
    creds={r['id']:dict(r) for r in current.execute('SELECT * FROM credentials')}
    db=sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=5)
    db.row_factory=sqlite3.Row
    try:
        db.execute('PRAGMA trusted_schema=OFF'); db.execute('PRAGMA foreign_keys=ON'); db.execute('BEGIN IMMEDIATE')
        for row in db.execute('SELECT * FROM users').fetchall():
            now=users.get(row['id'])
            if (row['disabled'] not in (0,1) or (now and now['disabled'] not in (0,1))):
                raise DomainError('recovery_security_invalid')
            if row['disabled'] or not now or now['disabled'] or row['created_at']!=now['created_at']:
                db.execute('UPDATE users SET disabled=1 WHERE id=?',(row['id'],))
        for row in db.execute('SELECT * FROM credentials').fetchall():
            now=creds.get(row['id']); old_scopes=_scopes(row['scopes'])
            if row['revoked'] not in (0,1): raise DomainError('recovery_security_invalid')
            same=now is not None and all(row[k]==now[k] for k in ('user_id','digest','resource')) and row['resource']==resource
            if not same:
                db.execute('UPDATE credentials SET revoked=1 WHERE id=?',(row['id'],)); continue
            if now['revoked'] not in (0,1) or any(type(x) is not int or x<0 for x in (row['expires_at'],now['expires_at'])):
                raise DomainError('recovery_security_invalid')
            scopes=old_scopes&_scopes(now['scopes'])
            db.execute('UPDATE credentials SET revoked=?,expires_at=?,scopes=? WHERE id=?',
                (int(bool(row['revoked'] or now['revoked'] or not scopes)),min(row['expires_at'],now['expires_at']),json.dumps(sorted(scopes)),row['id']))
        # Never resurrect a withdrawn/expired/revised publication or old consent.
        # All restored public exposure requires fresh consent after future promotion.
        db.execute("UPDATE listing_publications SET state='withdrawn'")
        db.execute('UPDATE publication_consents SET consumed_at=COALESCE(consumed_at,created_at)')
        db.commit()
        if db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]!=0:
            raise DomainError('recovery_checkpoint_failed')
    except BaseException:
        db.rollback(); raise
    finally: db.close()


def restore(backup, current, destination, resource):
    """Rehearsal only: original current authority required; output never compose-ready."""
    resource=resource_url(resource)
    backup,current,destination=(_root(p) for p in (backup,current,destination))
    _separate(backup,current,destination)
    with _frozen(current,resource) as authority, _lock(backup):
        m=_verify(backup,resource,kind='snapshot')
        if m['origin']!=_origin(current) or m['schema_hash']!=_database(current/DB):
            raise DomainError('recovery_wrong_authority')
        _new(destination)
        backup_database(backup/DB,destination/DB)
        _copy_photos(backup,destination,m['files'])
        initial=_audit(destination,resource)
        if any(initial[k]!=m[k] for k in ('counts','files')): raise DomainError('recovery_manifest_mismatch')
        _reconcile(destination/DB,authority,resource)
        result=_manifest(destination,resource,'restored',m['origin'],m['schema_hash'],
            {'current_authority_checked':True,'publications_withdrawn':True,'quarantined':True})
        _seal(destination,result)
        return _report(result)


def verify(source, resource):
    resource=resource_url(resource); source=_root(source)
    with _lock(source): return _report(_verify(source,resource))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    for action in ('snapshot','restore','verify'):
        p=sub.add_parser(action); p.add_argument('--resource',required=True)
        if action=='restore':
            p.add_argument('--snapshot',required=True); p.add_argument('--current',required=True)
        else: p.add_argument('--source',required=True)
        if action!='verify': p.add_argument('--destination',required=True)
    args=parser.parse_args(argv); os.umask(0o077)
    try:
        if args.action=='snapshot': result=snapshot(args.source,args.destination,args.resource)
        elif args.action=='restore': result=restore(args.snapshot,args.current,args.destination,args.resource)
        else: result=verify(args.source,args.resource)
    except DomainError as exc:
        print(json.dumps({'ok':False,'error':exc.code})); return 1
    except (OSError,sqlite3.Error):
        print(json.dumps({'ok':False,'error':'recovery_storage_error'})); return 1
    print(json.dumps(result,sort_keys=True)); return 0


if __name__=='__main__': raise SystemExit(main())
