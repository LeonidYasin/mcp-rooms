"""Explicit opt-in private binary transport; no public serving, URL fetch or migration."""
from contextlib import contextmanager
from functools import partial
import re
import sqlite3
import threading
import anyio
from starlette.responses import JSONResponse, Response
from .domain import DomainError, identifier
from .media_contract import MAX_INPUT_BYTES

UUID = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
ROUTE = re.compile(r'/listings/(' + UUID + r')/photos(?:/(' + UUID + r'))?')
BODY_TIMEOUT_SECONDS = 10
PRIVATE_HEADERS = {
    'Cache-Control': 'no-store', 'Pragma': 'no-cache',
    'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
    'Cross-Origin-Resource-Policy': 'same-origin',
    'Content-Security-Policy': "default-src 'none'; sandbox; frame-ancestors 'none'",
}


class HTTPFailure(Exception):
    def __init__(self, code, status):
        self.code, self.status = code, status


class Admission:
    """Immediate per-app/process admission, not a fleet or OS memory guarantee."""
    def __init__(self, total, per_owner):
        self.total, self.per_owner = total, per_owner
        self.lock, self.owners, self.active = threading.Lock(), {}, 0

    @contextmanager
    def slot(self, owner):
        with self.lock:
            if self.active >= self.total or self.owners.get(owner, 0) >= self.per_owner:
                raise HTTPFailure('media_http_busy', 429)
            self.active += 1
            self.owners[owner] = self.owners.get(owner, 0) + 1
        try:
            yield
        finally:
            with self.lock:
                self.active -= 1
                self.owners[owner] -= 1
                if not self.owners[owner]:
                    del self.owners[owner]


async def binary_body(receive, length):
    body = bytearray()
    with anyio.fail_after(BODY_TIMEOUT_SECONDS):
        while True:
            event = await receive()
            if event['type'] != 'http.request':
                raise HTTPFailure('disconnected', 400)
            chunk = event.get('body', b'')
            # Bound BEFORE copying a chunk into the accumulated buffer.
            if len(chunk) > MAX_INPUT_BYTES - len(body):
                raise HTTPFailure('media_input_too_large', 413)
            body.extend(chunk)
            if not event.get('more_body', False):
                break
    if not body or (length is not None and len(body) != length):
        raise HTTPFailure('invalid_body_length', 400)
    return bytes(body)


class MediaHTTP:
    def __init__(self, market):
        self.stages = market.photos.stages
        self.uploads, self.reads = Admission(2, 1), Admission(4, 2)

    @staticmethod
    def match(path):
        return ROUTE.fullmatch(path)

    def preflight(self, actor, listing_id, revision):
        with self.stages.store._db() as db:
            self.stages._gate(db, actor, listing_id, revision, 'listings:write')

    def bound_read(self, actor, listing_id, media_id):
        def binding():
            with self.stages.store._db() as db:
                self.stages.drafts._authorize(db, actor, 'listings:read', self.stages.store.clock())
                row = db.execute('SELECT draft_id FROM media_stages WHERE id=? AND user_id=?',
                                 (media_id, actor.user_id)).fetchone()
                if not row or row['draft_id'] != listing_id:
                    raise DomainError('media_unavailable')
        binding()
        data = self.stages.read(actor, media_id)
        binding()
        return data

    @staticmethod
    def upload_headers(scope):
        def values(name):
            return [v.decode('latin1') for k, v in scope.get('headers', []) if k.lower() == name]
        types = values(b'content-type')
        if len(types) != 1 or types[0] not in ('image/jpeg', 'image/png'):
            raise HTTPFailure('media_type_not_allowed', 415)
        if values(b'content-encoding') or values(b'content-disposition'):
            raise HTTPFailure('media_encoding_not_allowed', 415)
        lengths, transfer = values(b'content-length'), values(b'transfer-encoding')
        if len(lengths) > 1 or (transfer and (transfer != ['chunked'] or lengths)):
            raise HTTPFailure('invalid_body_framing', 400)
        length = None
        if lengths:
            if not re.fullmatch(r'0|[1-9][0-9]{0,9}', lengths[0]):
                raise HTTPFailure('invalid_body_length', 400)
            length = int(lengths[0])
            if length > MAX_INPUT_BYTES:
                raise HTTPFailure('media_input_too_large', 413)
            if length == 0:
                raise HTTPFailure('invalid_body_length', 400)
        revisions, keys = values(b'x-expected-revision'), values(b'idempotency-key')
        if (len(revisions) != 1 or not re.fullmatch(r'[1-9][0-9]{0,18}', revisions[0])
                or int(revisions[0]) > 2**63 - 2 or len(keys) != 1):
            raise HTTPFailure('invalid_upload_preconditions', 400)
        try:
            identifier(keys[0])
        except DomainError:
            raise HTTPFailure('invalid_upload_preconditions', 400) from None
        return types[0], length, int(revisions[0]), keys[0]

    @staticmethod
    def domain_error(exc, reading):
        code = exc.code
        if code == 'authentication_required':
            return code, 401
        if code == 'insufficient_scope':
            return code, 403
        if reading:
            return 'media_unavailable', 404
        if code in {'draft_unavailable', 'media_unavailable'}:
            return 'media_unavailable', 404
        if code in {'revision_conflict', 'draft_not_editable', 'unpublish_before_edit',
                    'idempotency_conflict', 'media_upload_pending', 'media_processing_failed'}:
            return code, 409
        if code == 'media_input_too_large':
            return code, 413
        if code in {'media_admission_capacity', 'media_receipt_capacity', 'media_storage_quota', 'media_worker_busy'}:
            return code, 429
        if code == 'media_worker_timeout':
            return code, 504
        if code in {'media_invalid_bytes', 'media_type_not_allowed', 'media_type_mismatch',
                    'media_dimensions_exceeded', 'media_animation_not_allowed',
                    'media_output_too_large', 'media_invalid_image'}:
            return code, 400
        return 'media_unavailable', 503

    async def handle(self, scope, receive, send, actor, matched):
        listing_id, media_id = matched.groups()
        reading = media_id is not None
        response = None
        try:
            if scope['method'] != ('GET' if reading else 'POST'):
                response = JSONResponse({'error': 'method_not_allowed'}, status_code=405,
                    headers={**PRIVATE_HEADERS, 'Allow': 'GET' if reading else 'POST'})
            else:
                admission = self.reads if reading else self.uploads
                with admission.slot(actor.user_id):
                    if reading:
                        data = await anyio.to_thread.run_sync(partial(self.bound_read, actor, listing_id, media_id))
                        response = Response(data, media_type='image/jpeg', headers=PRIVATE_HEADERS)
                    else:
                        mime, length, revision, client_id = self.upload_headers(scope)
                        await anyio.to_thread.run_sync(partial(self.preflight, actor, listing_id, revision))
                        payload = await binary_body(receive, length)
                        result = await anyio.to_thread.run_sync(partial(self.stages.stage, actor, listing_id,
                            expected_revision=revision, client_id=client_id, payload=payload, declared_type=mime))
                        response = JSONResponse({'ok': True, **result}, status_code=200 if result['replayed'] else 201,
                                                headers=PRIVATE_HEADERS)
                    # Keep admission until response is sent, not merely constructed.
                    return await response(scope, receive, send)
        except HTTPFailure as exc:
            code, status = exc.code, exc.status
        except DomainError as exc:
            code, status = self.domain_error(exc, reading)
        except TimeoutError:
            code, status = 'request_timeout', 408
        except (OSError, sqlite3.Error):
            code, status = 'media_unavailable', 503
        except Exception:
            code, status = 'media_unavailable', 500
        if response is not None:
            return await response(scope, receive, send)
        headers = {**PRIVATE_HEADERS, **({'Retry-After': '1'} if code == 'media_http_busy' else {})}
        return await JSONResponse({'ok': False, 'error': code}, status_code=status,
                                  headers=headers)(scope, receive, send)
