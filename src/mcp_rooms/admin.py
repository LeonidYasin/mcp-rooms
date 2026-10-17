"""Operator CLI. Never registered as an MCP tool; secrets go ONLY to a private file."""
import argparse
import json
import os
import sqlite3
from .identity import IdentityStore, write_private_token
from .store import RoomStore, RoomError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--resource', required=True, help='Canonical HTTPS /mcp URL')
    commands = parser.add_subparsers(dest='action', required=True)
    user = commands.add_parser('create-user'); user.add_argument('--name', required=True)
    issue = commands.add_parser('issue-token')
    issue.add_argument('--user', required=True); issue.add_argument('--output', required=True)
    issue.add_argument('--ttl', type=int, default=604800)
    issue.add_argument('--scope', choices=['rooms:read', 'rooms:write'], action='append')
    revoke = commands.add_parser('revoke-token'); revoke.add_argument('--credential', required=True)
    disable = commands.add_parser('disable-user'); disable.add_argument('--user', required=True)
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        auth = IdentityStore(RoomStore(args.db), args.resource)
        if args.action == 'create-user':
            result = auth.create_user(args.name)
        elif args.action == 'issue-token':
            result, raw = auth.issue_token(args.user, args.ttl, args.scope or ('rooms:read', 'rooms:write'))
            try:
                write_private_token(args.output, raw)
            except Exception:
                auth.revoke(result['credential_id'])
                raise
            result['secret_written_to_private_file'] = True
        elif args.action == 'revoke-token':
            result = auth.revoke(args.credential)
        else:
            result = auth.disable(args.user)
    except RoomError as exc:
        print(json.dumps({'ok': False, 'error': exc.code})); return 1
    except (OSError, sqlite3.Error):
        print(json.dumps({'ok': False, 'error': 'operator_storage_error'})); return 1
    print(json.dumps({'ok': True, **result}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
