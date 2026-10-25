"""Eight room operations over a verified principal. No external identity lookup."""
import logging
import sqlite3
from .store import RoomError
from .identity import Principal

LOG = logging.getLogger(__name__)
READ = frozenset({'list', 'read', 'topics'})
ACTIONS = READ | frozenset({'create', 'join', 'leave', 'send', 'delete_message', 'close'})


def storage_error(exc):
    code = getattr(exc, 'sqlite_errorcode', 0)
    code = (code & 255) if type(code) is int else 0
    LOG.warning('storage_failure sqlite_primary_code=%d', code)
    if code in (5, 6):
        return {'ok': False, 'error': 'room_storage_busy', 'retryable': True, 'retry_after_ms': 250}
    if code == 13:
        return {'ok': False, 'error': 'room_storage_capacity', 'retryable': False}
    return {'ok': False, 'error': 'room_storage_unavailable'}


def execute(store, principal, action, **args):
    try:
        if not isinstance(principal, Principal):
            raise RoomError('authentication_required')
        if action not in ACTIONS:
            raise RoomError('method_unavailable')
        if ('rooms:read' if action in READ else 'rooms:write') not in principal.scopes:
            raise RoomError('insufficient_scope')
        # owner is NEVER accepted from tool arguments, even internal callers.
        if 'owner' in args or 'user_id' in args or 'principal' in args:
            raise RoomError('invalid_arguments')
        result = getattr(store, action)(principal.owner, **args)
        return {'ok': True, **result}
    except RoomError as exc:
        return {'ok': False, 'error': exc.code, **exc.details}
    except sqlite3.Error as exc:
        return storage_error(exc)
    except OSError:
        return {'ok': False, 'error': 'room_storage_unavailable'}
    except Exception:
        return {'ok': False, 'error': 'room_request_failed'}
