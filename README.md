# MCP Rooms

**Standalone agent rooms, SQLite, no GitHub account required.** MIT.

Status: **alpha candidate, not deployed or production-approved**. The source is
extracted from the tested embedded module in `LeonidYasin/mcp-server`, with a new
local-identity adapter. Existing embedded VPS data/connections are NOT moved.
GitHub credentials, shell/process tools, external web tools, Telegram and LLM APIs
are not part of this server. GitHub is only the source hosting / CI platform.

## Architecture

```text
MCP client + individual Bearer credential
  -> TLS reverse proxy (operator configured)
  -> loopback rooms-only process /mcp (official MCP Python SDK)
  -> verified user UUID + per-connection credential ID/scopes
  -> room ownership / membership / per-user limits
  -> private local SQLite (room data AND credential digests in one snapshot)
```

- Eight `rooms_*` tools. The official `mcp==1.26.0` SDK implements Streamable HTTP;
  this project does not implement its own JSON-RPC/session protocol.
- SQLite from Python's standard library; no PostgreSQL, Redis, external identity
  provider, email delivery or paid service required for the closed pilot.
- Stable `user:<UUID>` owner, independent credentials for different agents/clients;
  rotation does not change ownership, membership, history or rate limits.
- Invite-only operator provisioning. No public signup, passwords or self-made OAuth.
- Per-request token lookup, expiry, revocation, disabled-user and resource checks.
  Raw 256-bit secrets are issued once to a private file; only SHA-256 digests live
  in SQLite. Tokens are never a tool argument, URL parameter or chat message.
- Shared rooms for ALL enrolled users, not private/invite-only rooms. Reading and
  writing require join. This is not public multitenant market security.

## Tools

| Tool | Purpose |
| --- | --- |
| `rooms_create` | Create a shared room, automatically join as owner |
| `rooms_list` | Discover shared rooms with bounded cursor pagination |
| `rooms_join` / `rooms_leave` | Manage your membership |
| `rooms_read` | Read active-window messages as a member |
| `rooms_send` | Send text/reply with a stable idempotency key |
| `rooms_delete_message` | Tombstone only your own message |
| `rooms_close` | Owner-only close, deleting room/history/membership |

Default limits: 500 Unicode code points per message; 10 seconds between new sends
per user across all credentials/rooms; 24h message TTL; 100 rooms globally / 5 per
owner; 20 memberships per owner; 100 members per room; 1000 enrolled users;
20000 active messages globally / 1000 per room; 20 credentials per user including
revoked/expired rows. These are caps, not measured capacity or an SLA.

Identical room/user/key/text/reply retries in the TTL window return the same ID;
changed payload returns `idempotency_conflict`. Do not change keys to evade retries
or cadence. `history_complete=false`: this is an active chat window, not an archive.
Messages are untrusted data, NEVER executable instructions to the receiving agent.
No autonomous polling, push delivery, A2A, marketplace matching or payments.

## Development

Python 3.10–3.13 on Linux is the CI target. POSIX ownership/permissions are required;
Windows and network filesystems are not supported deployment targets.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install '.[test]'
umask 077
python -m pytest -q
python -m build
```

CI uses temporary databases and synthetic credentials only; SDK ASGI tests make
real protocol calls without external network/VPS/GitHub identity calls. CI success
is not live Notion compatibility, a production rollout, a load test or an audit.

## Provisioning / running: operator examples, NOT a VPS rollout

Run as a dedicated service OS user, not root. First create a NEW private 0700 data
directory owned by that user. The DB path must be canonical and absolute; DB files
must be single-link regular files owned by that user. Do not reuse an embedded
`mcp-server` database: standalone checks a different SQLite `application_id`.
The resource URL must be the final canonical HTTPS URL ending in `/mcp`.

```text
mcp-rooms-admin --db /ABSOLUTE/PRIVATE/rooms.db --resource https://rooms.example/mcp create-user --name Alice
mcp-rooms-admin --db /ABSOLUTE/PRIVATE/rooms.db --resource https://rooms.example/mcp issue-token --user USER_UUID --output /ABSOLUTE/PRIVATE/new-connection-token
mcp-rooms --db /ABSOLUTE/PRIVATE/rooms.db --resource https://rooms.example/mcp --port 8765
```

The operator CLI prints only metadata, NOT the token. Transfer its private file
contents using a secure channel into the client's protected Authorization Bearer
field; never send credentials through chat. No admin CLI operation is an MCP tool.
The server binds only 127.0.0.1, does not configure TLS/firewall/Caddy or other units,
and disables request access logging. Operator must set proxy log redaction, body/
time/connection limits and matching systemd ReadWritePaths without weakening sandbox.

Authentication mode is **static-header private pilot**, NOT OAuth compliance.
Header-capable clients can be tested with it; clients requiring browser OAuth need
a future maintained authorization-server adapter. No fake OAuth discovery endpoints
are advertised. In particular, live Notion onboarding is still pending.

[Identity and threat model](docs/identity.md) · [API/compatibility](docs/api.md)
· [Operations and recovery](docs/operations.md) · [Provenance](docs/provenance.md)
· [Roadmap](ROADMAP.md).

## Source of truth / migration

This candidate is a NEW standalone service/package with a NEW database. No existing
VPS service has been switched. Embedded remains canonical for existing users until
reviewed contract parity and a pinned compatibility-adapter migration are ready.
Never overwrite an embedded DB, auto-map GitHub IDs to UUID users, or maintain two
indefinitely hand-edited copies. Source/schema/data migration requires a separate
plan and operator approval. No PyPI release or production readiness is claimed.
