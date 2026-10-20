"""Internal operator-reviewed retention. No HTTP/MCP/CLI/admin credential bypass.

Only explicitly injected stores are touched. Unknown/orphan/unsafe files BLOCK
apply: they are reported, never automatically deleted or adopted as photos.
"""
from hashlib import sha256
import os
import re
from .domain import DomainError
from .media_files import _KEY, _file_ok, MAX_FILES, MAX_TOTAL_BYTES
from .media_stage import MAX_RECEIPTS
from .preview_contract import canonical_json

GRACE_MS = 60000
PLAN_TTL_MS = 300000


class MediaCleanup:
    """Use only from a trusted operator boundary, never as a user capability.

    Root lock precedes DB lock. No write transaction spans checksum/unlink/fsync.
    A root is exclusively dedicated to this one database; unrelated blobs block.
    """
    def __init__(self, stages):
        self.stages, self.store, self.files = stages, stages.store, stages.files

    def _rows(self, db):
        self.stages._schema(db)
        rows = [dict(r) for r in db.execute('SELECT * FROM media_stages ORDER BY id LIMIT ?', (MAX_RECEIPTS + 1,))]
        if len(rows) > MAX_RECEIPTS:
            raise DomainError('media_cleanup_capacity')
        return rows

    @staticmethod
    def _eligible(row, cutoff):
        return (row['cleanup_state'] != 'purged' and row['expires_at'] + GRACE_MS <= cutoff
                and row['created_at'] <= cutoff)

    def _snapshot(self, cutoff):
        with self.store._db() as db:
            rows = self._rows(db)
        candidates = [r['id'] for r in rows if self._eligible(r, cutoff)]
        references = {}
        blockers = []
        for row in rows:
            phase = row['cleanup_state']
            if (row['created_at'] > cutoff or (phase in ('purging', 'purged') and
                    (type(row['cleanup_started_at']) is not int or
                     not row['created_at'] <= row['cleanup_started_at'] <= cutoff)) or
                    (phase == 'purged' and (type(row['purged_at']) is not int or
                     not row['cleanup_started_at'] <= row['purged_at'] <= cutoff))):
                blockers.append('invalid_cleanup_timestamp')
            key = row['blob_key']
            if key:
                if type(key) is not str or not _KEY.fullmatch(key) or key in references:
                    blockers.append('invalid_or_duplicate_manifest_key')
                else:
                    references[key] = row
        inventory = []
        present = set()
        total_bytes = 0
        # A bounded stat/checksum inventory; never follows links or decodes images.
        with os.scandir(self.files._fd) as entries:
            for entry in entries:
                if len(inventory) >= MAX_FILES:
                    raise DomainError('media_cleanup_capacity')
                info = entry.stat(follow_symlinks=False)
                total_bytes += max(0, info.st_size)
                if total_bytes > MAX_TOTAL_BYTES:
                    raise DomainError('media_cleanup_capacity')
                present.add(entry.name)
                marker = dict(name=entry.name, dev=info.st_dev, ino=info.st_ino,
                              size=info.st_size, mode=info.st_mode, uid=info.st_uid,
                              links=info.st_nlink, mtime=info.st_mtime_ns, ctime=info.st_ctime_ns)
                inventory.append(marker)
                if not _KEY.fullmatch(entry.name) or not _file_ok(info):
                    blockers.append('unsafe_inventory')
                    continue
                row = references.get(entry.name)
                if row is None:
                    blockers.append('orphan_file')
                elif row['cleanup_state'] == 'purged':
                    blockers.append('purged_file_reappeared')
                else:
                    try:
                        data = self.files._read_locked(self.stages._receipt(row))
                        marker['digest'] = sha256(data).hexdigest()
                    except (DomainError, OSError, TypeError, ValueError):
                        blockers.append('corrupt_derivative')
        missing = []
        for row in rows:
            if row['blob_key'] and row['blob_key'] not in present and row['cleanup_state'] != 'purged':
                missing.append(row['id'])
                if row['id'] not in candidates:
                    blockers.append('missing_active_derivative')
            # A RESERVED row with unknown file key is reclaimable only if no
            # orphan exists. Delayed workers must recheck under this same guard.
        root = os.fstat(self.files._fd)
        database = os.stat(self.store.path, follow_symlinks=False)
        snapshot = dict(root=[root.st_dev, root.st_ino, root.st_mode, root.st_uid],
                        database=[database.st_dev, database.st_ino],
                        rows=rows, inventory=sorted(inventory, key=lambda v:v['name']),
                        cutoff=cutoff, candidates=candidates, missing=missing,
                        blockers=sorted(set(blockers)))
        return snapshot

    @staticmethod
    def _digest(snapshot):
        return sha256(canonical_json(snapshot).encode('utf-8', 'surrogatepass')).hexdigest()

    def plan(self):
        """Read-only dry run. Returned report contains IDs/counts, no paths/keys/data."""
        with self.files._guard():
            now = self.store.clock()
            snapshot = self._snapshot(now)
            return dict(schema=1, as_of=now, digest=self._digest(snapshot),
                        candidates=snapshot['candidates'], blockers=snapshot['blockers'],
                        missing=snapshot['missing'], file_count=len(snapshot['inventory']),
                        receipt_count=len(snapshot['rows']))

    def _purged(self, media_id):
        with self.store._db(write=True) as db:
            self.stages._schema(db)
            row = db.execute('SELECT * FROM media_stages WHERE id=?', (media_id,)).fetchone()
            now = self.store.clock()
            if not row or row['cleanup_state'] != 'purging' or now < row['cleanup_started_at']:
                raise DomainError('media_cleanup_changed')
            db.execute("UPDATE media_stages SET cleanup_state='purged',purged_at=? WHERE id=? AND cleanup_state='purging'", (now, media_id))

    def apply(self, plan):
        """Explicit application of a reviewed exact snapshot; not an auth token.

        Changed/expired/blocked plan is rejected before any destructive change.
        On mid-apply failure retain PURGING and budget; obtain a new plan to resume.
        """
        if (type(plan) is not dict or set(plan) != {'schema','as_of','digest','candidates',
                'blockers','missing','file_count','receipt_count'}
                or type(plan['schema']) is not int or plan['schema'] != 1
                or type(plan['as_of']) is not int or type(plan['digest']) is not str
                or not re.fullmatch('[0-9a-f]{64}', plan['digest'])):
            raise DomainError('media_cleanup_plan_invalid')
        with self.files._guard():
            now = self.store.clock()
            if not plan['as_of'] <= now < plan['as_of'] + PLAN_TTL_MS:
                raise DomainError('media_cleanup_plan_expired')
            snapshot = self._snapshot(plan['as_of'])
            if (snapshot['blockers'] or plan['blockers']):
                raise DomainError('media_cleanup_blocked')
            if (self._digest(snapshot) != plan['digest'] or snapshot['candidates'] != plan['candidates']
                    or snapshot['missing'] != plan['missing']
                    or len(snapshot['inventory']) != plan['file_count']
                    or len(snapshot['rows']) != plan['receipt_count']):
                raise DomainError('media_cleanup_plan_stale')
            candidates = [r for r in snapshot['rows'] if r['id'] in snapshot['candidates']]
            # Re-read under a short write transaction: reservations may have been
            # created while checksumming, even though file writes are locked out.
            with self.store._db(write=True) as db:
                if self._rows(db) != snapshot['rows']:
                    raise DomainError('media_cleanup_plan_stale')
                current = self.store.clock()
                if current < now or current >= plan['as_of'] + PLAN_TTL_MS:
                    raise DomainError('media_cleanup_plan_expired')
                for row in candidates:
                    if not self._eligible(row, current):
                        raise DomainError('media_cleanup_changed')
                    db.execute("UPDATE media_stages SET cleanup_state='purging',cleanup_started_at=COALESCE(cleanup_started_at,?) WHERE id=? AND cleanup_state!='purged'", (current, row['id']))
            purged = []
            for row in candidates:
                key = row['blob_key']
                if key:
                    try:
                        os.unlink(key, dir_fd=self.files._fd)
                    except FileNotFoundError:
                        pass
                # Durably establish absence before quota is released. Do this
                # also when resuming after unlink/fsync but before DB commit.
                os.fsync(self.files._fd)
                self._purged(row['id'])
                purged.append(row['id'])
            return dict(ok=True, purged=purged, receipts_deleted=False)
