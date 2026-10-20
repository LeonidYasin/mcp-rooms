"""Private synthetic DB/keys/files in CI only. No scope issuance or endpoints."""
from dataclasses import replace
from hashlib import sha256
import json
from types import SimpleNamespace
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from mcp_rooms import media_stage as m
from mcp_rooms.media_contract import NormalizedPhoto
from mcp_rooms.media_files import PrivatePhotoFiles
from mcp_rooms.domain import DomainError
from test_draft_store import setup, create, content, key, RESOURCE


class Worker:
    calls = 0
    hook = None
    def normalize(self, payload, mime):
        self.calls += 1
        if self.hook:
            self.hook()
        data = b'\xff\xd8\xffsynthetic-derivative\xff\xd9'
        return NormalizedPhoto(data, sha256(data).hexdigest(), 20, 10, 'PNG')


@pytest.fixture
def env(setup, tmp_path):
    store, auth, drafts, a, b, now = setup
    root = tmp_path / 'derivatives'
    root.mkdir(mode=0o700)
    files = PrivatePhotoFiles(root)
    worker = Worker()
    service = m.MediaStageStore(drafts, files, worker)
    service.initialize()
    draft_id = create(drafts, a)['listing']['id']
    x = SimpleNamespace(store=store, auth=auth, drafts=drafts, a=a, b=b, now=now,
                        root=root, files=files, worker=worker, service=service, draft_id=draft_id)
    yield x
    files.close()


def upload(x, actor=None, **kw):
    args = dict(expected_revision=1, client_id=key(), payload=b'original-synthetic', declared_type='image/png')
    args.update(kw)
    return x.service.stage(actor or x.a, x.draft_id, **args)


def fails(code, fn):
    with pytest.raises(DomainError) as e:
        fn()
    assert e.value.code == code


def rows(x):
    with x.store._db() as db:
        return [dict(r) for r in db.execute('SELECT * FROM media_stages')]


def test_opt_in_initialize_reopen_no_room_migration(env):
    x = env
    with x.store._db() as db:
        before = tuple(db.execute('PRAGMA '+q).fetchone()[0] for q in ('application_id','user_version'))
    result = upload(x)
    reopened = m.MediaStageStore(x.drafts, x.files, Worker())
    reopened.initialize()
    assert reopened.read(x.a, result['media_id']).startswith(b'\xff\xd8\xff')
    assert result['visibility'] == 'private' and result['state'] == 'staged'
    assert 'blob_key' not in result and 'owner' not in result
    assert result['revision'] == 1 and x.drafts.get(x.a, x.draft_id)['listing']['revision'] == 1
    with x.store._db() as db:
        assert tuple(db.execute('PRAGMA '+q).fetchone()[0] for q in ('application_id','user_version')) == before
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_replay_no_decode_write_or_deadline_extension(env):
    x = env
    command = key()
    first = upload(x, client_id=command)
    x.now[0] += 100
    second = upload(x, client_id=command)
    assert second == {**first, 'replayed': True}
    assert x.worker.calls == 1 and len(list(x.root.iterdir())) == 1


@pytest.mark.parametrize('change', [dict(payload=b'different'), dict(declared_type='image/jpeg')])
def test_replay_digest_conflict(env, change):
    x = env
    command = key()
    upload(x, client_id=command)
    fails('idempotency_conflict', lambda: upload(x, client_id=command, **change))
    assert x.worker.calls == 1


def test_foreign_owner_cannot_stage_or_read(env):
    x = env
    photo = upload(x)
    fails('draft_unavailable', lambda: upload(x, x.b))
    fails('media_unavailable', lambda: x.service.read(x.b, photo['media_id']))
    fails('media_unavailable', lambda: x.service.read(x.b, key()))
    assert x.worker.calls == 1 and len(rows(x)) == 1


@pytest.mark.parametrize('kind', ['revoked', 'disabled', 'resource', 'expired', 'scope', 'forged'])
def test_auth_before_replay_or_bytes(env, kind):
    x = env
    command = key()
    result = upload(x, client_id=command)
    actor = x.a
    code = 'authentication_required'
    with x.store._db(write=True) as db:
        if kind == 'revoked':
            db.execute('UPDATE credentials SET revoked=1 WHERE id=?', (actor.credential_id,))
        elif kind == 'disabled':
            db.execute('UPDATE users SET disabled=1 WHERE id=?', (actor.user_id,))
        elif kind == 'resource':
            db.execute("UPDATE credentials SET resource='https://other.example/mcp' WHERE id=?", (actor.credential_id,))
        elif kind == 'expired':
            db.execute('UPDATE credentials SET expires_at=0 WHERE id=?', (actor.credential_id,))
        elif kind == 'scope':
            db.execute("UPDATE credentials SET scopes='[]' WHERE id=?", (actor.credential_id,))
            code = 'insufficient_scope'
        else:
            actor = replace(actor, user_id=x.b.user_id)
    fails(code, lambda: upload(x, actor, client_id=command))
    fails(code, lambda: x.service.read(actor, result['media_id']))
    assert x.worker.calls == 1


@pytest.mark.parametrize('kind,code', [('revoke','authentication_required'),
    ('archive','draft_not_editable'),('revision','revision_conflict'),
    ('category','category_unavailable'),('expiry','media_unavailable')])
def test_change_during_decode_never_commits_staged(env, kind, code):
    x = env
    def change():
        if kind == 'revoke':
            x.auth.revoke(x.a.credential_id)
        elif kind == 'archive':
            x.drafts.archive(x.a, x.draft_id, expected_revision=1, client_id=key())
        elif kind == 'revision':
            x.drafts.update(x.a, x.draft_id, content(title='Changed'), category_id='toilets', expected_revision=1, client_id=key())
        elif kind == 'category':
            with x.store._db(write=True) as db:
                db.execute("UPDATE market_categories SET active=0 WHERE id='things'")
        else:
            x.now[0] += m.TTL_MS
    x.worker.hook = change
    fails(code, lambda: upload(x))
    row = rows(x)[0]
    assert row['state'] == 'failed' and row['blob_key'] is None
    assert not list(x.root.iterdir())  # fresh pre-write gate rejects changed rights


def test_no_write_lock_held_during_worker(env):
    x = env
    def change():
        with x.store._db(write=True) as db:
            db.execute('UPDATE users SET display_name=display_name WHERE id=?', (x.a.user_id,))
    x.worker.hook = change
    assert upload(x)['state'] == 'staged'


def test_read_rechecks_after_filesystem_io(env, monkeypatch):
    x = env
    result = upload(x)
    original = x.files.read
    def read(receipt):
        data = original(receipt)
        x.auth.revoke(x.a.credential_id)
        return data
    monkeypatch.setattr(x.files, 'read', read)
    fails('authentication_required', lambda: x.service.read(x.a, result['media_id']))


def test_corrupt_committed_bytes_fail_including_replay(env):
    x = env
    command = key()
    result = upload(x, client_id=command)
    path = next(x.root.iterdir())
    path.write_bytes(b'x' * path.stat().st_size)
    fails('media_storage_integrity', lambda: x.service.read(x.a, result['media_id']))
    fails('media_storage_integrity', lambda: upload(x, client_id=command))
    assert x.worker.calls == 1


def test_failure_terminal_retry_does_not_retry_decode(env, monkeypatch):
    x = env
    command = key()
    def fail():
        raise DomainError('media_invalid_image')
    x.worker.hook = fail
    fails('media_invalid_image', lambda: upload(x, client_id=command))
    fails('media_processing_failed', lambda: upload(x, client_id=command))
    assert rows(x)[0]['state'] == 'failed' and not list(x.root.iterdir())
    assert x.worker.calls == 1


def test_expiry_no_retry_or_read(env):
    x = env
    command = key()
    result = upload(x, client_id=command)
    x.now[0] = result['expires_at']
    fails('media_unavailable', lambda: upload(x, client_id=command))
    fails('media_unavailable', lambda: x.service.read(x.a, result['media_id']))


@pytest.mark.parametrize('which', ['MAX_ROWS','MAX_OWNER_ROWS','MAX_BYTES','MAX_OWNER_BYTES'])
def test_budgets_count_failed_and_expired_rows(env, monkeypatch, which):
    x = env
    monkeypatch.setattr(m, which, 1 if 'ROWS' in which else m.MAX_OUTPUT_BYTES)
    result = upload(x)
    x.now[0] = result['expires_at']
    fails('media_admission_capacity', lambda: upload(x))
    assert x.worker.calls == 1 and len(rows(x)) == 1


def test_pending_concurrent_retry_no_second_decode(env):
    x = env
    command = key()
    entered, release = threading.Event(), threading.Event()
    def wait():
        entered.set()
        assert release.wait(10)
    x.worker.hook = wait
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(upload, x, client_id=command)
        try:
            assert entered.wait(10)
            fails('media_upload_pending', lambda: upload(x, client_id=command))
        finally:
            release.set()
        assert future.result()['state'] == 'staged'
    assert x.worker.calls == 1 and len(list(x.root.iterdir())) == 1


@pytest.mark.parametrize('kind', ['partial','future'])
def test_schema_refuses_unknown_without_repair(env, kind):
    x = env
    with x.store._db(write=True) as db:
        if kind == 'partial':
            db.execute('DROP TABLE media_stages')
        else:
            db.execute('UPDATE media_stage_schema SET version=99')
    fails('unsupported_media_schema', x.service.initialize)


def test_media_not_attached_and_no_scope_issuance(env):
    x = env
    result = upload(x)
    fails('media_not_available', lambda: x.drafts.update(x.a, x.draft_id,
        content(media_ids=(result['media_id'],)), category_id='toilets', expected_revision=1, client_id=key()))
    with x.store._db() as db:
        assert json.loads(db.execute('SELECT scopes FROM credentials WHERE id=?', (x.a.credential_id,)).fetchone()[0]) == ['listings:read','listings:write']


def test_real_worker_files_manifest(env):
    import sys
    if sys.version_info < (3, 11):
        pytest.skip('optional codec requires Python >=3.11')
    from io import BytesIO
    from PIL import Image
    from mcp_rooms.media_worker import PhotoWorker
    x = env
    x.service.worker = PhotoWorker()
    with Image.new('RGB', (24, 12), 'green') as source, BytesIO() as output:
        source.save(output, format='PNG')
        result = upload(x, payload=output.getvalue())
    with Image.open(BytesIO(x.service.read(x.a, result['media_id']))) as decoded:
        decoded.load()
        assert decoded.size == (24, 12) and decoded.format == 'JPEG'


@pytest.mark.parametrize('change,code', [(dict(payload=b''),'media_invalid_bytes'),
    (dict(payload=bytearray(b'x')),'media_invalid_bytes'),
    (dict(payload=b'x'*(m.MAX_INPUT_BYTES+1)),'media_input_too_large'),
    (dict(declared_type='image/svg+xml'),'media_type_not_allowed'),
    (dict(expected_revision=True),'invalid_revision')])
def test_invalid_input_before_reservation(env, change, code):
    x = env
    fails(code, lambda: upload(x, **change))
    assert not rows(x) and x.worker.calls == 0


def test_revoke_after_file_write_before_commit(env, monkeypatch):
    x = env
    put = x.files._put_locked
    def revoke(photo):
        receipt = put(photo)
        x.auth.revoke(x.a.credential_id)
        return receipt
    monkeypatch.setattr(x.files, '_put_locked', revoke)
    fails('authentication_required', lambda: upload(x))
    assert rows(x)[0]['state'] == 'failed' and len(list(x.root.iterdir())) == 1


def test_resource_persisted_not_retargeted_by_adapter(env):
    from mcp_rooms.draft_store import DraftStore
    x = env
    photo = upload(x)
    other = 'https://other.example/mcp'
    with x.store._db(write=True) as db:
        db.execute('UPDATE credentials SET resource=? WHERE id=?', (other, x.a.credential_id))
    rebound = m.MediaStageStore(DraftStore(x.store, other), x.files, x.worker)
    fails('media_unavailable', lambda: rebound.read(x.a, photo['media_id']))


def test_no_implicit_migration(env):
    x = env
    with x.store._db(write=True) as db:
        db.execute('DROP TABLE media_stages')
        db.execute('DROP TABLE media_stage_schema')
    fails('media_migration_required', lambda: upload(x))
    assert x.worker.calls == 0
