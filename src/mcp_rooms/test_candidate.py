"""Operator-only fresh TEST profile. Not a VPS installer, migration or admin MCP.

No execution on VPS is authorized by the presence of this module/entry point.
"""
import argparse
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import fcntl
from .domain import DomainError
from .identity import IdentityStore, LISTING_SCOPES, resource_url, write_private_token
from .store import RoomStore
from .draft_store import DraftStore, TABLES
from .media_stage import MediaStageStore, _TABLES
from .media_files import PrivatePhotoFiles
from .media_worker import PhotoWorker
from .photo_drafts import PhotoDraftStore
from .publication_store import PublicationStore
from .publication_guard import PUBLICATION_TABLES
from .market_adapter import MarketAdapter
from .server import create_app

PROFILE = 'mcp-rooms/owner-first-test/v1'
BASE = {'actors','rooms','members','messages','users','credentials','enrollments','signup_budgets'}
REQUIRED = BASE | set(TABLES) | _TABLES | PUBLICATION_TABLES
DB = 'market.sqlite3'
MARKER = 'profile.json'
TTL_SECONDS = 3600


def _directory(path):
    info=path.stat(follow_symlinks=False)
    if (path.resolve()!=path or not stat.S_ISDIR(info.st_mode)
            or info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700):
        raise DomainError('candidate_unsafe_directory')


def _root(value):
    path=Path(value)
    if not path.is_absolute() or path.resolve()!=path:
        raise DomainError('candidate_unsafe_directory')
    _directory(path.parent)
    return path


def _file(path,maximum,*,empty=False):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
                or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1
                or not (0 if empty else 1)<=info.st_size<=maximum):
            raise DomainError('candidate_unsafe_file')
        return os.read(fd,maximum+1) if maximum<=4096 else None
    finally:os.close(fd)


def _schema_hash(db):
    rows=[tuple(row) for row in db.execute('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name')]
    return sha256(json.dumps(rows,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()


def _database(path,expected_hash=None):
    _file(path,RoomStore.MAX_PAGES*4096)
    # Reject aliases/shared sidecars BEFORE SQLite can follow/open them.
    for suffix,bound in [('-wal',128*1024*1024),('-shm',1024*1024)]:
        sidecar=Path(str(path)+suffix)
        if os.path.lexists(sidecar):_file(sidecar,bound,empty=True)
    if os.path.lexists(str(path)+'-journal'):
        raise DomainError('candidate_database_mismatch')
    # mode=ro, no RoomStore or sidecar initialization before validation.
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5)
    db.row_factory=sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF')
        db.execute('BEGIN')
        if (db.execute('PRAGMA application_id').fetchone()[0]!=RoomStore.APPLICATION_ID
                or db.execute('PRAGMA user_version').fetchone()[0]!=2
                or db.execute('PRAGMA page_size').fetchone()[0]!=4096
                or db.execute('PRAGMA journal_mode').fetchone()[0]!='wal'):
            raise DomainError('candidate_database_mismatch')
        tables={row[0] for row in db.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
        if tables != REQUIRED|{'sqlite_sequence'}:
            raise DomainError('candidate_database_mismatch')
        for table,ver in [('market_schema',2),('media_stage_schema',3),('publication_schema',1)]:
            rows=db.execute('SELECT singleton,version FROM '+table).fetchall()
            if len(rows)!=1 or tuple(rows[0])!=(1,ver):
                raise DomainError('candidate_database_mismatch')
        digest=_schema_hash(db)
        if expected_hash is not None and digest!=expected_hash:
            raise DomainError('candidate_database_mismatch')
        if ([r[0] for r in db.execute('PRAGMA quick_check')]!=['ok']
                or db.execute('PRAGMA foreign_key_check').fetchone() is not None):
            raise DomainError('candidate_database_mismatch')
        return digest
    finally:db.close()


def _pairs(items):
    result={}
    for k,v in items:
        if k in result:raise DomainError('candidate_invalid_marker')
        result[k]=v
    return result


def check(state,resource):
    """Read-only schema/path validation; no credential read or automatic repair."""
    resource=resource_url(resource)
    root=_root(state);_directory(root);_directory(root/'photos')
    _file(root/'profile.lock',0,empty=True)
    try:
        marker=json.loads(_file(root/MARKER,4096),object_pairs_hook=_pairs)
    except (ValueError,UnicodeError,RecursionError):
        raise DomainError('candidate_invalid_marker') from None
    if (type(marker) is not dict or set(marker)!={'profile','schema','resource','schema_hash'}
            or marker['profile']!=PROFILE or type(marker['schema']) is not int or marker['schema']!=1
            or marker['resource']!=resource or type(marker['schema_hash']) is not str
            or not re.fullmatch('[0-9a-f]{64}',marker['schema_hash'])):
        raise DomainError('candidate_invalid_marker')
    _database(root/DB,marker['schema_hash'])
    return root


def _write_json(path,value):
    payload=(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode('ascii')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(payload);stream.flush();os.fsync(stream.fileno())
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)


def bootstrap(state,resource):
    """Explicit NEW directory only. Failure leaves blocked private state for review.

    No raw key in result/stdout. If private delivery/marker creation fails, revoke
    issued credential and disable new user. Never delete an existing tree or retry
    initialization over it. A storage failure during compensation still requires
    operator review; no ready marker remains and keys have a one-hour fallback TTL.
    """
    resource=resource_url(resource);root=_root(state)
    # Refuse existing directories, files and dangling links without touching them.
    os.mkdir(root,0o700)
    auth=uid=metadata=None
    try:
        _directory(root)
        (root/'photos').mkdir(mode=0o700)
        store=RoomStore(root/DB)
        auth=IdentityStore(store,resource,allow_listing_scopes=True)
        drafts=DraftStore(store,resource);drafts.initialize()
        with PrivatePhotoFiles(root/'photos') as files:
            stages=MediaStageStore(drafts,files,PhotoWorker(max_parallel=1));stages.initialize()
            PublicationStore(PhotoDraftStore(stages)).initialize()
        digest=_database(root/DB)
        uid=auth.create_user('Owner-first TEST')['user_id']
        metadata,raw=auth.issue_token(uid,ttl_seconds=TTL_SECONDS,scopes=sorted(LISTING_SCOPES))
        try:write_private_token(root/'owner.key',raw)
        finally:raw=None
        fd=os.open(root/'profile.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:os.fsync(fd)
        finally:os.close(fd)
        _write_json(root/MARKER,dict(profile=PROFILE,schema=1,resource=resource,schema_hash=digest))
        return {'profile':PROFILE,'secret_written_to_private_file':True,'key_ttl_seconds':TTL_SECONDS}
    except BaseException:
        # Compensations are independent: a marker unlink failure must not skip revoke.
        recovery_failed=False
        try:(root/MARKER).unlink(missing_ok=True)
        except OSError:recovery_failed=True
        if auth is not None:
            if metadata is not None:
                try:auth.revoke(metadata['credential_id'])
                except Exception:recovery_failed=True
            if uid is not None:
                try:auth.disable(uid)
                except Exception:recovery_failed=True
        if recovery_failed:
            raise DomainError('candidate_bootstrap_recovery_required') from None
        raise



def _native_support():
    if sys.platform!='linux' or sys.version_info<(3,11):
        raise DomainError('candidate_native_runtime_required')
    try:installed=version('Pillow')
    except PackageNotFoundError:installed=None
    if installed!='13.0.0':raise DomainError('candidate_native_runtime_required')


class Candidate:
    def __init__(self,app,files,worker,lock):
        self.app,self.files,self.worker,self.lock=app,files,worker,lock
    def close(self):
        try:self.files.close()
        finally:
            if self.lock is not None:
                os.close(self.lock);self.lock=None
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def compose(state,resource):
    """One cooperating process per private profile; no DDL/key read/issuance here."""
    _native_support()
    root=_root(state);_directory(root)
    _file(root/'profile.lock',0,empty=True)
    lock=os.open(root/'profile.lock',os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    files=None
    try:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise DomainError('candidate_already_running') from None
        root=check(root,resource)
        store=RoomStore(root/DB,initialize=False)
        drafts=DraftStore(store,resource)
        files=PrivatePhotoFiles(root/'photos')
        from .media_sandbox import NativeSandbox
        worker=PhotoWorker(max_parallel=1,sandbox=NativeSandbox(root))
        worker.check_sandbox()  # Fail closed before constructing/exposing any app.
        stages=MediaStageStore(drafts,files,worker)
        photos=PhotoDraftStore(stages);publisher=PublicationStore(photos)
        adapter=MarketAdapter(drafts,photos,publisher)
        app=create_app(store.path,resource,market=adapter,media_http=True,
                       public_market=True,media_upload_slots=1)
        return Candidate(app,files,worker,lock)
    except BaseException:
        try:
            if files is not None:files.close()
        finally:os.close(lock)
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['bootstrap','check','serve'])
    parser.add_argument('--state',required=True,help='Fresh absolute directory below an owner-only0700 parent')
    parser.add_argument('--resource',required=True,help='Exact canonical HTTPS URL ending /mcp')
    args=parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.action=='bootstrap':result=bootstrap(args.state,args.resource)
        elif args.action=='check':
            check(args.state,args.resource);result={'profile':PROFILE,'checked':True}
        else:
            import logging
            logging.getLogger('mcp').setLevel(logging.WARNING)
            import uvicorn
            with compose(args.state,args.resource) as candidate:
                uvicorn.run(candidate.app,host='127.0.0.1',port=8766,workers=1,
                            access_log=False,proxy_headers=False)
            return 0
        print(json.dumps({'ok':True,**result}));return 0
    except DomainError as exc:
        print(json.dumps({'ok':False,'error':exc.code}));return 1
    except (OSError,sqlite3.Error):
        print(json.dumps({'ok':False,'error':'candidate_storage_error'}));return 1
    except Exception:
        print(json.dumps({'ok':False,'error':'candidate_unavailable'}));return 1


if __name__=='__main__':raise SystemExit(main())
