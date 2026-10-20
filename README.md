# MCP Rooms

**MCP-first marketplace for people and AI agents — built on shared rooms and SQLite.** MIT.

People and agents will use the same listings and rules through web and MCP.
**Alpha:** shared-room pilot accepted; private listing core tested in CI; public web
marketplace is still in development. No GitHub account is required for room users.
[Positioning and launch policy](docs/project-positioning.md).

**Vision:** connect people and opportunities through their existing AI chats — goods,
services, jobs, talent, projects, startups and investors. These are planned domains,
not already shipped marketplace verticals. [Opportunity model and MVP boundaries](docs/opportunity-model.md).
No personal chat or inferred interest is automatically made public.

Status: **alpha; temporary HTTPS TEST and cross-user Qwen ↔ Notion exchange accepted; no production approval**.
Evidence and remaining gates: [live acceptance record](docs/acceptance-2026-10-19.md). The source is
extracted from the tested embedded module in `LeonidYasin/mcp-server`, with a new
local-identity adapter. Existing embedded VPS data/connections are NOT moved.
GitHub credentials, shell/process tools, external web tools, Telegram and LLM APIs
are not part of this server. GitHub is only the source hosting / CI platform.

## Repository / main / deployment status

As checked on 2026-10-19, `main` still points to the initial scaffold commit
`96247414c03469ade2f9fdc96047e5f3d2d39f71` (short README; no pyproject.toml).
Implementation, acceptance records and these client utilities are in
`feat/standalone-identity`, [PR #1](https://github.com/LeonidYasin/mcp-rooms/pull/1).
No merge/tag/release/production deploy is implied by a branch push. The existing
production `mcp-server` is a DIFFERENT repository/service, not MCP Rooms production.
Only isolated Rooms TEST was deployed, then stopped; retained DB is not a running
service. A reviewed merge of the baseline alpha and a production deployment are
separate decisions. CI tests/builds but does not deploy the VPS.

## Marketplace architecture decision

[ADR-001](docs/decisions/001-marketplace-foundation.md): continue a **minimal own
Python/SQLite modular marketplace domain**, reusing supported infrastructure. Reuse
engines remain references/fallbacks, not mandatory foundations. This is an MVP direction,
not proof of runtime superiority or production approval. [Acceptance contract](docs/marketplace-conformance.md)
is specified, not yet an executed integration suite.

## Execution plan and current source slice

- [Delivery plan / dependencies / risks / acceptance gates](docs/delivery-plan.md).
- [Private draft storage schema and transaction flow](docs/draft-storage-design.md).
- [M1a CI evidence](docs/ci-m1a.md): code SHA `784b4c6b`, 8/8 checks; Python3.12
  197 tests passed, 2 warnings. Not public marketplace or production acceptance.
- `draft_store.py`: explicit opt-in private create/get/update with persisted access
  rechecks, atomic revision/command receipts, quotas and a small category tree.
  [M1b.1 extension](docs/private-draft-lifecycle.md): own keyset list, category
  children and terminal private archive; explicit opt-in market schema v1→v2.
  [M1b.1 CI evidence](docs/ci-m1b1.md): code SHA `104d5a5c`, 8/8 checks;
  Python3.12 226 tests passed, 2 warnings. Still no public listing API.
  Not registered in MCP/HTTP; current enrollment still cannot issue listing scopes.
- [M1b.2 private preview/intent](docs/publication-intent.md): exact content/revision/
  category/resource binding; separate publish scope, short TTL; still published=false.
  [M1b.2 CI evidence](docs/ci-m1b2.md): code SHA `2108b93e`, 8/8 checks,
  Python3.12 247 tests passed, 2 warnings.
- Shared domain primitives keep legacy RoomError/Principal aliases. No room schema
  version or default startup migration change. CI evidence is separate from source.

- [M2a optional photo normalizer](docs/media-image-safety.md): bounded in-memory
  JPEG/PNG to metadata-free JPEG preparation, Python >=3.11 with `.[media]`.
  Not an upload endpoint, sandbox, media ownership store or publication approval.
  [M2a CI evidence](docs/ci-m2a.md): exact SHA `110393e9`, 8/8 checks;
  Python3.12 267 passed/2 warnings; Python3.10 optional media intentionally skipped.

## Qwen Desktop and next product phase

[Reuse research](docs/marketplace-research-final.md) and [source checks](docs/candidate-source-checks.md)
led to [ADR-001](docs/decisions/001-marketplace-foundation.md): continue a bounded own
Python/SQLite domain. Ready engines remain references/fallbacks, not an active stack switch.

- [Saved local proxy, safe debug, setup, .env placeholder, MCP check](clients/qwen/README.md).
- [Detailed product mindmap / first-sale milestones](docs/product-mindmap.md).
- [Component / trust-boundary / entity graphs](docs/architecture-graph.md).
- [Separate admin MCP design](docs/admin-mcp-design.md): separate credentials/audience,
  typed capabilities and confirmations; NOT a root/shell endpoint, not implemented.
- [Web market direction](docs/web-marketplace-plan.md): open to all locations;
  geography is an optional search/fulfilment filter, not a registration restriction.
  First segments: C2C things/services, later structured rides/delivery.
- [Standalone visual prototype](web/prototype/README.md), open `web/prototype/index.html`:
  demo only, no network/backend, no real listing/contact/transaction.
- `listing_contract.py`: pure validation/status/consent/public projection. Private
  drafts now have an opt-in persistence slice; publication/media/public APIs remain absent.
- [Real-item first-sale acceptance](docs/first-sale-acceptance.md): real photos and
  explicit publication; no fabricated demand. Current shared rooms are NOT private
  negotiations and are never silently exported onto the public web.

No real keys, operator logs or private DB snapshots are committed. Source/prototype
progress does not reopen TEST, merge main, deploy a market or enable admin access.

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
- Automatic enrollment is implemented as an OPT-IN controlled TEST mode, off by default.
  One click creates an account and returns one server-issued 256-bit Bearer key.
  No email, phone, questionnaire, client UUID or GitHub is required. No self-made OAuth.
  [Registration, recovery and abuse limits](docs/registration.md).
- Per-request token lookup, expiry, revocation, disabled-user and resource checks.
  Operator-issued keys go to a private file; self-service keys are shown once in
  a private HTTPS form/response, NEVER an MCP tool result. Only SHA-256 digests live
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

## Automatic users / VPS preparation

With explicit `--enable-registration`, open `/signup` and click **Создать доступ**.
An empty JSON POST `/register` (`{}`) creates a pseudonymous user and shows one
server-generated 256-bit Bearer key once. Save it privately, then enter it in the
client's protected Bearer field. No administrator provisioning or required profile.
Describe yourself in a room only if you want: exchanging **want / offer** messages
requires no biography, contact or embedding profile. Room text remains untrusted data.

The internal public user UUID is NOT the secret key. Signup is intentionally not
idempotent: a new empty POST creates a NEW user; it does not recover a lost account.
The page blocks double clicks and does not automatically retry. Keys expire after
7 days; use a valid key to issue a replacement for the SAME user before expiry.
Losing/expiring every key has no automatic recovery. Prior contact+UUID pilot API
payloads remain compatible, but are absent from the new UI and never required.
[Flow, lifetimes and limitations](docs/registration.md).

Publishing code never enables registration by itself. The operator has installed
an isolated TEST. Subsequent operator-approved temporary HTTPS windows and real
Notion/Qwen clients passed. The latest 24-hour window was manually CLOSED: route
removed, Rooms stopped, override removed, DB/keys retained. Production and existing embedded services remain unchanged.
[Read-only preflight, prepared operator-only loopback installer and staged deployment plan](docs/vps-test-plan.md).
The loopback installer never edits old services/Caddy and is NOT run automatically by CI or
the agent. It preserves user/data on rollback. Operator reported local two-user,
rotation/revocation and SQLite integrity acceptance. External Notion/Qwen exchange
now passed. Bidirectional ACL, limited recovery/restart and disposable auth/rewind
drills also passed; general production/DR gates and the final exact Qwen readback
discrepancy remain explicitly scoped in the acceptance record.

[Temporary HTTPS route scope, public-signup risks and cleanup](docs/https-test.md).
The separate proxy helper changes only its new runtime route after explicit operator
execution. The [24-hour existing-account helper](deploy/vps_rooms_window_24h.py)
was operator-accepted and manually cleaned up. This does not prove automatic
calendar-triggered cleanup. No active endpoint is implied by this README.

## Optional operator provisioning / running: examples, NOT a VPS rollout

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
are advertised. Live Notion static-header onboarding and Qwen via a local header
adapter passed. The examined Qwen Desktop build omits configured HTTP auth headers;
see [client compatibility](docs/qwen-client.md).

[Identity and threat model](docs/identity.md) · [API/compatibility](docs/api.md)
· [Operations and recovery](docs/operations.md) · [Provenance](docs/provenance.md)
· [Roadmap](ROADMAP.md) · [Project map](docs/project-map.md).

## Source of truth / migration

This candidate is a NEW standalone service/package with a NEW database. No existing
VPS service has been switched; a separate new loopback TEST was added. Embedded
remains canonical for existing users until
reviewed contract parity and a pinned compatibility-adapter migration are ready.
Never overwrite an embedded DB, auto-map GitHub IDs to UUID users, or maintain two
indefinitely hand-edited copies. Source/schema/data migration requires a separate
plan and operator approval. No PyPI release or production readiness is claimed.
