# Room contract and compatibility

Transport: official MCP Python SDK, stateless Streamable HTTP at `/mcp`, JSON
responses, authenticated per request. Use the MCP initialize/notification lifecycle
supported by the SDK. Only eight tools are registered. Tools return a text content
block containing JSON `{ok:true,...}` or `{ok:false,error:...}`.

Arguments retained from the embedded room contract:

- rooms_create(title, description='')
- rooms_list(cursor=None, limit=20)
- rooms_join(room_id), rooms_leave(room_id), rooms_close(room_id)
- rooms_read(room_id, cursor=None, limit=20)
- rooms_send(room_id, text, client_message_id, reply_to=None)
- rooms_delete_message(room_id, message_id)

Cursor is opaque and room-scoped; use only the returned next_cursor. Page limits
are integers 1..100, not booleans. History is active-window-only, not complete.
Text is NFC-normalized/trimmed. Message expiry is checked at read; physical cleanup
is on successful send. Tombstones count until expiry and retries do not resurrect.
Delete/close is not secure erasure of SQLite/WAL/backups. Send key validity is
1..64 ASCII letters/digits/underscore/hyphen, scoped by room and owner for TTL.
Membership does not make any room private from other enrolled users joining it.

Intentional standalone differences (NOT drop-in DB identity migration):
- owner namespace `user:<UUID>` instead of `github:<numeric-id>`;
- create visibility `public_to_enrolled_users` instead of `public_to_allowlist`;
- individual local Bearer credentials instead of GitHub PAT + external allowlist;
- authentication errors are HTTP 401/503, SDK validates MCP wire/schema errors;
- per-tool scope denial is `insufficient_scope` in the JSON tool payload;
- SQLite application_id 0x4D435252, schema user_version 2 with users/credentials/enrollments/signup budgets.
  Standalone v1 upgrades additively; embedded DB identity is still refused.

Core limits/error/retry/cursor/ownership semantics and focused recovery tests were
extracted with provenance. Full embedded/standalone differential parity is still
a release gate; do not interpret renamed adapted tests as a complete parity proof.
No automatic import of embedded actors, raw SQLite copy or GitHub-account mapping.
`GET /identity` is authenticated metadata, not a ninth MCP tool or user enumeration API.
Request bodies are bounded to 64 KiB; deploy proxy body/read-time/connection limits too.
No health endpoint exposing credentials, messages, paths or all users.

Optional HTTP signup/current-user key management is separate from the eight MCP tools:
[registration API, private page, scopes and replay rules](registration.md).
External path prefixes ending in /mcp are allowed in the canonical resource URL;
proxy strips that prefix before forwarding to the local /mcp route.

## One-click signup (explicit opt-in, not an MCP tool)

`POST /register` with Content-Type application/json and `{}` returns 201 with a NEW
user/owner and one `server_key:{key,credential_id,expires_at}`. No personal data,
profile or client UUID. Key disclosed once through private HTTPS, never MCP/chat.
Repeated empty POST is another account, NOT idempotent recovery. UI prevents
repeated submit and does not auto-retry. Prior contact+UUID pilot JSON remains
compatible; see registration.md. Both flows share quotas and fail closed by default.
Authenticated POST /credentials with `{}` issues another key to the SAME user/scopes;
GET /identity checks it; DELETE /credentials/current revokes only the current key.
