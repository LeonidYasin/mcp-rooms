"""Optional publication namespace checks shared by private editors; no migrations."""
from .domain import DomainError

PUBLICATION_TABLES = frozenset({'publication_schema', 'listing_publications',
                               'publication_consents', 'publication_audit'})


def publication_schema(db, *, required=True):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    found = names & PUBLICATION_TABLES
    if not found and not required:
        return False
    if found != PUBLICATION_TABLES:
        raise DomainError('unsupported_publication_schema')
    rows = db.execute('SELECT singleton,version FROM publication_schema').fetchall()
    if len(rows) != 1 or tuple(rows[0]) != (1, 1):
        raise DomainError('unsupported_publication_schema')
    return True


def require_unpublished(db, listing_id, now):
    if not publication_schema(db, required=False):
        return
    row = db.execute('SELECT state,updated_at,expires_at FROM listing_publications WHERE listing_id=?', (listing_id,)).fetchone()
    if row:
        if now < row['updated_at']:
            raise DomainError('invalid_timestamp')
        if row['state'] == 'active' and now < row['expires_at']:
            raise DomainError('unpublish_before_edit')
