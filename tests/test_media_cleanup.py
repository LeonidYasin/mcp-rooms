"""Operator-only synthetic dry-run/reclaim/recovery in temporary CI stores."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import os
import sqlite3
import threading
import pytest
from mcp_rooms import media_cleanup as m
from mcp_rooms import media_stage
from mcp_rooms.domain import DomainError
from test_media_stage import env, setup, upload, rows, fails, key


def expire(x):
    x.now[0] = max(r['expires_at'] for r in rows(x)) + m.GRACE_MS


def test_plan_is_read_only_and_redacted(env):
    x = env
    upload(x)
    before, files = rows(x), sorted(x.root.iterdir())
    cleanup = m.MediaCleanup(x.service)
    plan = cleanup.plan()
    assert plan['candidates'] == [] and plan['blockers'] == []
    assert rows(x) == before and sorted(x.root.iterdir()) == files
    assert str(x.root) not in str(plan) and '.jpg' not in str(plan)
    assert cleanup.apply(plan) == dict(ok=True, purged=[], receipts_deleted=False)
    assert rows(x) == before


def test_reclaim_quota_preserve_old_command(env, monkeypatch):
    x = env
    monkeypatch.setattr(media_stage, 'MAX_OWNER_BYTES', media_stage.MAX_OUTPUT_BYTES)
    command = key()
    first = upload(x, client_id=command)
    fails('media_admission_capacity', lambda: upload(x))
    expire(x)
    cleanup = m.MediaCleanup(x.service)
    plan = cleanup.plan()
    assert plan['candidates'] == [first['media_id']] and not plan['blockers']
    assert cleanup.apply(plan)['purged'] == [first['media_id']]
    assert rows(x)[0]['cleanup_state'] == 'purged' and not list(x.root.iterdir())
    fails('media_unavailable', lambda: upload(x, client_id=command))
    fails('media_unavailable', lambda: x.service.read(x.a, first['media_id']))
    second = upload(x)
    assert second['media_id'] != first['media_id'] and len(rows(x)) == 2
    assert len(list(x.root.iterdir())) == 1


def test_tombstones_have_separate_lifetime_cap(env, monkeypatch):
    x = env
    monkeypatch.setattr(media_stage, 'MAX_RECEIPTS', 1)
    upload(x)
    expire(x)
    cleanup = m.MediaCleanup(x.service)
    cleanup.apply(cleanup.plan())
    fails('media_receipt_capacity', lambda: upload(x))
    assert len(rows(x)) == 1 and not list(x.root.iterdir())


@pytest.mark.parametrize('kind', ['new-row','mtime','wrong-digest'])
def test_stale_plan_cannot_delete(env, kind):
    x = env
    upload(x)
    expire(x)
    cleanup = m.MediaCleanup(x.service)
    plan = cleanup.plan()
    if kind == 'new-row':
        upload(x)
    elif kind == 'mtime':
        path = next(x.root.iterdir())
        st = path.stat()
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1000000000))
    else:
        plan['digest'] = '0'*64
    before = rows(x)
    fails('media_cleanup_plan_stale', lambda: cleanup.apply(plan))
    assert rows(x) == before and list(x.root.iterdir())


@pytest.mark.parametrize('kind', ['orphan','unknown','symlink','hardlink','corrupt'])
def test_unsafe_or_unknown_files_block_without_deleting(env, kind):
    x = env
    upload(x)
    expire(x)
    path = next(x.root.iterdir())
    if kind == 'orphan':
        x.files.put(x.worker.normalize(b'synthetic', 'image/png'))
        expected = 'orphan_file'
    elif kind == 'unknown':
        (x.root / 'do-not-delete-private-note').write_bytes(b'not a photo')
        expected = 'unsafe_inventory'
    elif kind == 'symlink':
        path.unlink()
        path.symlink_to(x.root.parent / 'not-present')
        expected = 'unsafe_inventory'
    elif kind == 'hardlink':
        os.link(path, x.root.parent / 'outside-alias')
        expected = 'unsafe_inventory'
    else:
        path.write_bytes(b'x' * path.stat().st_size)
        expected = 'corrupt_derivative'
    cleanup = m.MediaCleanup(x.service)
    plan = cleanup.plan()
    assert expected in plan['blockers']
    before, names = rows(x), sorted(p.name for p in x.root.iterdir())
    fails('media_cleanup_blocked', lambda: cleanup.apply(plan))
    assert rows(x) == before and sorted(p.name for p in x.root.iterdir()) == names


def test_missing_active_blocks_expired_missing_retires(env):
    x = env
    result = upload(x)
    next(x.root.iterdir()).unlink()
    cleanup = m.MediaCleanup(x.service)
    assert 'missing_active_derivative' in cleanup.plan()['blockers']
    expire(x)
    plan = cleanup.plan()
    assert plan['missing'] == [result['media_id']] and not plan['blockers']
    cleanup.apply(plan)
    assert rows(x)[0]['cleanup_state'] == 'purged'


@pytest.mark.parametrize('point', ['unlink','fsync','db-finalize'])
def test_interrupted_cleanup_resumes_with_new_plan(env, monkeypatch, point):
    x = env
    result = upload(x)
    expire(x)
    cleanup = m.MediaCleanup(x.service)
    plan = cleanup.plan()
    def fail(*a, **kw):
        raise OSError('synthetic cleanup fault')
    with monkeypatch.context() as patch:
        if point == 'unlink':
            patch.setattr(os, 'unlink', fail)
        elif point == 'fsync':
            patch.setattr(os, 'fsync', fail)
        else:
            patch.setattr(cleanup, '_purged', fail)
        fails('media_storage_io', lambda: cleanup.apply(plan))
    assert rows(x)[0]['cleanup_state'] == 'purging'
    fails('media_cleanup_plan_stale', lambda: cleanup.apply(plan))
    new_plan = cleanup.plan()
    assert new_plan['blockers'] == []
    assert cleanup.apply(new_plan)['purged'] == [result['media_id']]
    assert rows(x)[0]['cleanup_state'] == 'purged' and not list(x.root.iterdir())


def test_partial_batch_retains_recoverable_progress(env, monkeypatch):
    x = env
    upload(x)
    upload(x)
    expire(x)
    cleanup = m.MediaCleanup(x.service)
    plan = cleanup.plan()
    unlink = os.unlink
    count = [0]
    def fail_second(*args, **kw):
        count[0] += 1
        if count[0] == 2:
            raise OSError('synthetic second delete failure')
        return unlink(*args, **kw)
    with monkeypatch.context() as patch:
        patch.setattr(os, 'unlink', fail_second)
        fails('media_storage_io', lambda: cleanup.apply(plan))
    assert sorted(r['cleanup_state'] for r in rows(x)) == ['purged','purging']
    assert len(list(x.root.iterdir())) == 1
    cleanup.apply(cleanup.plan())
    assert all(r['cleanup_state'] == 'purged' for r in rows(x)) and not list(x.root.iterdir())


@pytest.mark.parametrize('kind', ['future','expired','bad-schema','bad-shape'])
def test_invalid_plan_no_side_effects(env, kind):
    x = env
    upload(x)
    expire(x)
    cleanup = m.MediaCleanup(x.service)
    plan = cleanup.plan()
    expected = 'media_cleanup_plan_expired'
    if kind == 'future':
        plan['as_of'] += 1
    elif kind == 'expired':
        x.now[0] += m.PLAN_TTL_MS
    elif kind == 'bad-schema':
        plan['schema'] = True
        expected = 'media_cleanup_plan_invalid'
    else:
        plan['extra'] = 'not allowed'
        expected = 'media_cleanup_plan_invalid'
    before = rows(x)
    fails(expected, lambda: cleanup.apply(plan))
    assert rows(x) == before and len(list(x.root.iterdir())) == 1


def test_expired_pending_worker_cannot_write_after_reclamation(env):
    x = env
    entered, release = threading.Event(), threading.Event()
    def wait():
        entered.set()
        assert release.wait(10)
    x.worker.hook = wait
    with ThreadPoolExecutor(max_workers=2) as pool:
        task = pool.submit(upload, x)
        try:
            assert entered.wait(10)
            expire(x)
            cleanup = m.MediaCleanup(x.service)
            assert not cleanup.plan()['blockers']
            cleanup.apply(cleanup.plan())
        finally:
            release.set()
        fails('media_unavailable', task.result)
    assert rows(x)[0]['cleanup_state'] == 'purged' and not list(x.root.iterdir())


def test_cleanup_waits_for_file_and_manifest_commit_boundary(env, monkeypatch):
    x = env
    entered, release = threading.Event(), threading.Event()
    put = x.files._put_locked
    def delayed(photo):
        receipt = put(photo)
        entered.set()
        assert release.wait(10)
        return receipt
    monkeypatch.setattr(x.files, '_put_locked', delayed)
    cleanup = m.MediaCleanup(x.service)
    with ThreadPoolExecutor(max_workers=2) as pool:
        task = pool.submit(upload, x)
        try:
            assert entered.wait(10)
            expire(x)
            planner = pool.submit(cleanup.plan)
        finally:
            release.set()
        fails('media_unavailable', task.result)
        plan = planner.result()
    assert not plan['blockers'] and plan['file_count'] == 1
    assert rows(x)[0]['state'] == 'failed' and rows(x)[0]['blob_key']
    cleanup.apply(plan)
    assert rows(x)[0]['cleanup_state'] == 'purged' and not list(x.root.iterdir())


def test_new_reservation_during_apply_snapshot_recheck_blocks(env, monkeypatch):
    x = env
    upload(x)
    expire(x)
    cleanup = m.MediaCleanup(x.service)
    plan = cleanup.plan()
    snapshot = cleanup._snapshot
    def race(cutoff):
        result = snapshot(cutoff)
        x.service._reserve(x.a, x.draft_id, 1, key(), 'synthetic-reservation-digest')
        return result
    monkeypatch.setattr(cleanup, '_snapshot', race)
    fails('media_cleanup_plan_stale', lambda: cleanup.apply(plan))
    assert all(r['cleanup_state'] == 'live' for r in rows(x)) and len(list(x.root.iterdir())) == 1


def test_failed_decode_without_file_can_reclaim(env):
    x = env
    def fail():
        raise DomainError('media_invalid_image')
    x.worker.hook = fail
    fails('media_invalid_image', lambda: upload(x))
    expire(x)
    cleanup = m.MediaCleanup(x.service)
    cleanup.apply(cleanup.plan())
    assert rows(x)[0]['state'] == 'failed' and rows(x)[0]['cleanup_state'] == 'purged'


def test_purged_file_reappearing_is_never_deleted_automatically(env):
    x = env
    upload(x)
    path = next(x.root.iterdir())
    data = path.read_bytes()
    expire(x)
    cleanup = m.MediaCleanup(x.service)
    cleanup.apply(cleanup.plan())
    path.write_bytes(data)
    path.chmod(0o600)
    plan = cleanup.plan()
    assert 'purged_file_reappeared' in plan['blockers']
    fails('media_cleanup_blocked', lambda: cleanup.apply(plan))
    assert path.exists()


def legacy_v1(x):
    with x.store._db(write=True) as db:
        columns = [r['name'] for r in db.execute('PRAGMA table_info(media_stages)') if r['name'] not in
                   ('cleanup_state','cleanup_started_at','purged_at')]
        old_sql = db.execute("SELECT sql FROM sqlite_master WHERE name='media_stages'").fetchone()[0]
        begin = old_sql.index("cleanup_state TEXT")
        end = old_sql.index('UNIQUE(user_id,client_id)', begin)
        legacy = old_sql[:begin] + old_sql[end:]
        db.execute('DROP TABLE media_draft_photos')
        db.execute('DROP INDEX media_stages_owner')
        db.execute('ALTER TABLE media_stages RENAME TO legacy_copy')
        db.execute(legacy)
        cols = ','.join(columns)
        db.execute('INSERT INTO media_stages('+cols+') SELECT '+cols+' FROM legacy_copy')
        db.execute('DROP TABLE legacy_copy')
        db.execute('CREATE INDEX media_stages_owner ON media_stages(user_id)')
        db.execute('UPDATE media_stage_schema SET version=1')


def test_explicit_v1_migration_preserves_rows_and_files(env):
    x = env
    result = upload(x)
    data = x.service.read(x.a, result['media_id'])
    legacy_v1(x)
    fails('unsupported_media_schema', lambda: x.service.read(x.a, result['media_id']))
    x.service.initialize()
    x.service.initialize()
    assert rows(x)[0]['cleanup_state'] == 'live' and x.service.read(x.a, result['media_id']) == data
    with x.store._db() as db:
        assert db.execute('SELECT version FROM media_stage_schema').fetchone()[0] == 3
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_migration_failure_rolls_back_atomically(env, monkeypatch):
    x = env
    upload(x)
    legacy_v1(x)
    original = x.store._db
    class Proxy:
        def __init__(self, db): self.db = db
        def execute(self, sql, *a):
            if 'ADD COLUMN purged_at' in sql:
                raise sqlite3.OperationalError('synthetic migration fault')
            return self.db.execute(sql, *a)
    @contextmanager
    def faulty(*a, **kw):
        with original(*a, **kw) as db:
            yield Proxy(db)
    with monkeypatch.context() as patch:
        patch.setattr(x.store, '_db', faulty)
        with pytest.raises(sqlite3.OperationalError):
            x.service.initialize()
    with original() as db:
        assert db.execute('SELECT version FROM media_stage_schema').fetchone()[0] == 1
        assert 'cleanup_state' not in {r['name'] for r in db.execute('PRAGMA table_info(media_stages)')}
    x.service.initialize()
    assert rows(x)[0]['cleanup_state'] == 'live'
