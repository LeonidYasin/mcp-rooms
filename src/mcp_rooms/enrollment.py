"""Opt-in one-click pseudonymous enrollment; no profile or contact required."""
import hashlib
import json
import re
import secrets
import uuid
from .identity import UUID_BEARER
from .store import RoomError

# Fixed UTC windows, global across workers/restarts; NOT proof against Sybil/DoS.
BUDGETS = (('minute', 60000, 5), ('hour', 3600000, 30), ('day', 86400000, 100))


def contact_kind(value):
    if not isinstance(value, str) or value != value.strip() or len(value) > 254:
        raise RoomError('invalid_contact')
    if re.fullmatch(r'\+[1-9][0-9]{7,14}', value):
        return 'phone'
    # Deliberately a conservative ASCII pilot syntax, not an RFC mail verifier.
    if re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+', value):
        return 'email'
    raise RoomError('invalid_contact')


class Enrollment:
    def __init__(self, auth):
        self.auth = auth

    def register(self, payload):
        simple = isinstance(payload, dict) and not payload
        # Keep the previous pilot payload for compatibility, not as a UI requirement.
        if not simple:
            if (not isinstance(payload, dict) or not {'contact', 'bootstrap_uuid'} <= payload.keys()
                    or not payload.keys() <= {'contact', 'bootstrap_uuid', 'issue_server_key'}
                    or type(payload.get('issue_server_key', False)) is not bool):
                raise RoomError('invalid_registration')
            kind = contact_kind(payload['contact'])
            raw = payload['bootstrap_uuid']
            if not isinstance(raw, str) or not UUID_BEARER.fullmatch(raw):
                raise RoomError('invalid_bootstrap_uuid')
        else:
            # Fresh independent account on each explicit POST. No hidden profile,
            # contact-based recovery or user-selected owner/scopes.
            cid = uuid.uuid4().hex
            raw = 'rm1_' + cid + '.' + secrets.token_urlsafe(32)
            kind = None
        digest = hashlib.sha256(raw.encode('ascii')).hexdigest()
        store = self.auth.store
        now = store.clock()
        expires = now // 1000 + 604800
        issued = None
        with store._db(write=True) as db:
            old = db.execute('SELECT e.*,c.revoked,c.expires_at,c.resource,u.disabled FROM enrollments e JOIN credentials c ON c.id=e.credential_id JOIN users u ON u.id=e.user_id WHERE e.bootstrap_digest=?', (digest,)).fetchone()
            if old:
                if (old['revoked'] or old['disabled'] or old['expires_at'] <= now // 1000
                        or old['resource'] != self.auth.resource):
                    raise RoomError('registration_unavailable')
                # Knowing the existing UUID proves possession, NOT contact ownership.
                # Never reissue/reveal a previously generated server key on replay.
                return self._result(old['user_id'], old['credential_id'], old['expires_at'], old['contact_kind'], True, None)
            if db.execute('SELECT 1 FROM credentials WHERE digest=?', (digest,)).fetchone():
                raise RoomError('registration_unavailable')
            if db.execute('SELECT COUNT(*) FROM users').fetchone()[0] >= store.limits.principals:
                raise RoomError('user_capacity')
            db.execute('DELETE FROM signup_budgets WHERE expires_at<=?', (now,))
            retry = 0
            for scope, period, maximum in BUDGETS:
                bucket = now // period
                row = db.execute('SELECT used FROM signup_budgets WHERE scope=? AND bucket=?', (scope, bucket)).fetchone()
                if row and row[0] >= maximum:
                    retry = max(retry, (bucket + 1) * period - now)
            if retry:
                raise RoomError('registration_rate_limited', retry_after_ms=retry)
            for scope, period, maximum in BUDGETS:
                bucket = now // period
                db.execute('INSERT INTO signup_budgets(scope,bucket,used,expires_at) VALUES (?,?,1,?) ON CONFLICT(scope,bucket) DO UPDATE SET used=used+1', (scope, bucket, (bucket + 1) * period))
            uid = str(uuid.uuid4())
            if not simple:
                cid = uuid.uuid4().hex
            db.execute('INSERT INTO users(id,display_name,created_at) VALUES (?,?,?)', (uid, 'member-' + uid[:8], now))
            scopes = json.dumps(['rooms:read', 'rooms:write'])
            db.execute('INSERT INTO credentials(id,user_id,digest,resource,scopes,expires_at) VALUES (?,?,?,?,?,?)', (cid, uid, digest, self.auth.resource, scopes, expires))
            if simple:
                issued = {'key': raw, 'credential_id': cid, 'expires_at': expires}
            else:
                db.execute('INSERT INTO enrollments VALUES (?,?,?,?,?)', (digest, uid, cid, kind, now))
            if not simple and payload.get('issue_server_key', False):
                scid = uuid.uuid4().hex
                secret = 'rm1_' + scid + '.' + secrets.token_urlsafe(32)
                db.execute('INSERT INTO credentials(id,user_id,digest,resource,scopes,expires_at) VALUES (?,?,?,?,?,?)', (scid, uid, hashlib.sha256(secret.encode('ascii')).hexdigest(), self.auth.resource, scopes, expires))
                issued = {'key': secret, 'credential_id': scid, 'expires_at': expires}
        if simple:
            return {'ok': True, 'user_id': uid, 'owner': 'user:' + uid,
                    'already_registered': False, 'server_key': issued}
        return self._result(uid, cid, expires, kind, False, issued)

    @staticmethod
    def _result(uid, cid, expires, kind, replay, issued):
        return {'ok': True, 'user_id': uid, 'owner': 'user:' + uid,
                'bootstrap_credential_id': cid, 'bootstrap_expires_at': expires,
                'contact': {'kind': kind, 'verified': False, 'stored': False},
                'already_registered': replay, 'server_key': issued,
                'bootstrap_remains_active': True}
