# Isolated VPS TEST: preparation, not deployment authorization

## Latest accepted evidence (2026-10-19)

Temporary external HTTPS and real Notion/Qwen clients now passed. The latest operator
report accepted `deploy/vps_rooms_window_24h.py`: 24-hour HTTPS access, registration
DISABLED, existing keys preserved, only Rooms TEST restarted, protected services
unchanged, persistent cleanup timer armed. Reported deadline: 2026-10-20T22:56:46Z.
This is a historical acceptance record, NOT a claim the route is currently open.
The underlying installed code is still 4b2351c0; navigation fix is source-only.
The earlier 30-minute public-signup helper described below remains a legacy option,
NOT the recommended window for extended client troubleshooting. Do not rerun the
installer or keep renewing short windows to diagnose a client missing auth headers.
See [acceptance and open gates](acceptance-2026-10-19.md), [Qwen](qwen-client.md),
and [operations](operations.md). Do not merge/deploy production on this evidence alone.

## Historical preparation / original helper

Target host: existing operator-managed Ubuntu VPS. Keep mcp-server.service,
mcp-test.service, Caddy and existing databases/credentials unchanged. No execution
through run_python/run_command/SSH/background; operator runs any root script only
from their own console after reviewing exact scope and pinned checksum.

## Isolated resources (operator reported installation; external route pending)

- New OS user/group: mcp-rooms-test, no sudo or access to existing MCP homes.
- New checkout/venv/data under /home/mcp-rooms-test, private 0700 data directory.
- New unit mcp-rooms-test.service, loopback 127.0.0.1:8765, 2-hour runtime limit,
  not enabled at boot. deploy/mcp-rooms-test.service.example is a reference template;
  the installer created the exact unit, not an automatic boot-enabled deployment.
- New SQLite database with standalone application_id; no existing DB copied/opened.
- Proposed canonical external resource: https://leonid-mcp.duckdns.org/rooms-test/mcp.
  Prefix /rooms-test is stripped by a FUTURE separately reviewed Caddy route.
  Public signup would be /rooms-test/signup; it is NOT opened by this preparation.
- Authentication uses rooms-issued Bearer (one-click server key by default), not
  GitHub PAT. New endpoint must never forward local user tokens to GitHub or main MCP.

## Stage 1: read-only operator preflight

Run ONLY pinned deploy/vps_preflight.py after CI. It reads versions/venv bootstrap availability, selected systemd
properties/PIDs, listening port numbers, disk/memory reserve and candidate path/user
existence. It never opens any DB, reads credentials/Caddy configuration, creates an
OS user, installs packages, writes service config, starts/restarts units or changes
firewall/proxy. Wrapper download creates a private script copy, not a deployment.

Blockers include occupied port, pre-existing target user/path/unit, insufficient
reserve or inactive existing services. Existing candidates must be inspected,
never deleted/overwritten automatically. Preflight requires root ONLY for the
operator's bounded local checks, not for running the rooms service.

Operator supplied a clean report for the previous pinned preflight: Python 3.12.3,
8765 free, candidate user/home/unit absent, 15332 MiB disk and 1165 MiB available
memory, protected services active. This is a point-in-time report, NOT an installed
service or public-route approval. Recheck fresh state immediately before mutation.

## Stage 2: guarded loopback installation — operator reported PASS

`deploy/vps_install_test.py` is an explicit operator-root-console installer, not an
agent remote execution tool. Review and checksum-pin its exact revision first.
It installs runtime source pinned independently to CI-accepted commit
`4b2351c0b6522d30c888496b3c1774be8791345f`, NEVER the current branch tip. Installer
CI covers pure/mocked OS behavior and runs the actual loopback acceptance script
against an in-process ASGI app; it does not claim real systemd/VPS acceptance.

Scope of `--install`:
- Root-only exclusive lock and fresh resource/protected-state preflight; requires
  at least 512 MiB available RAM and 2 GiB / 10% free disk. Reject existing user,
  group, home, unit or occupied 8765; no overwrites or automatic user deletion.
- Private root-owned state/log/installer copy; creates only the NEW `mcp-rooms-test`
  account/home/data/venv/app and exact new unit. NO apt, root pip, old venv updates,
  existing DB opens, Caddy edits, firewall changes or reboots.
- Fetch exact source, venv/pip, tests, wheel/sdist build and installed-package check
  as NEW non-root service user in a filesystem/memory/time-bounded transient
  systemd unit. No project import or build as root. Dependencies come from package
  indexes with declared constraints, not an audited frozen dependency lock.
- A new installed-wheel loopback service, registration enabled, strict sandbox,
  127.0.0.1:8765 only, RuntimeMaxSec=7200, no enable-at-boot. Reject extra unit
  drop-ins/foreign fragment. systemctl daemon-reload is used; old units are not restarted.
- Live local HTTP smoke gate as the NEW user: unauthenticated rejection, exactly
  eight tools, TWO independent one-click users, join/read/write and owner negatives,
  want/offer exchange, idempotent retry, same-user rotate/revoke and SQLite integrity.
  Gate keys stay only in process memory and are revoked on success; test user/hash
  rows remain budgeted. The temporary room is closed. This is NOT an external
  HTTPS/Notion/two-chat test. Gate creates two users against the global signup budget.
- Compare old service selected properties/PIDs unchanged. Reports contain no keys.

On caught failure, attempt conservative rollback: stop/remove only our exact new
unit if unchanged. If unit ownership/hash/fragment/drop-ins differ, STOP for review;
never force-remove changed resources. Preserve new user/home/database/logs for
inspection. A later rerun therefore stops on existing resources rather than erasing
state. Manual rollback command is emitted in a successful report and uses the
root-private installer copy/state. Rollback does not restore a whole systemd/Caddy
snapshot and does not delete user data. A crash/power loss/forced interruption still
needs manual review; runtime limits do not remove files/accounts or roll back setup.

Do not paste private logs wholesale. On STOP return only sanitized result first;
inspect specific error categories if needed. Successful loopback install is not
permission to open the public route, merge the draft PR or deploy production.

### Operator-reported acceptance

Supplied result `MCP ROOMS LOOPBACK TEST READY` confirmed source
4b2351c0b6522d30c888496b3c1774be8791345f, new unit mcp-rooms-test.service,
127.0.0.1:8765, 8 tools, one-click signup, two independent local users and rotation,
SQLite integrity, smoke keys revoked, old selected service states unchanged and
no Caddy/old code/dependency/database changes. Runtime limit 7200s; not boot-enabled.
This is operator evidence, not an independent agent-side live verification. Agent
has NOT used remote execution. External client gate and public endpoint are false.
Do not rerun --install: existing user/home/unit will correctly cause STOP.

## Stage 3: temporary external route / real client gate

Separate approval and fresh sanitized Caddy inspection. Prepared helper
`deploy/vps_proxy_inspect.py` is root-console read-only except creating a private
0700 directory / 0600 snapshot. It reads Caddy admin config at loopback 2019,
does NOT follow redirects, and prints only bounded route structure, known paths,
loopback upstream ports, booleans for auth conditions, selected service properties
and elapsed TEST uptime. No auth header values, response bodies, unknown paths,
hostnames or upstream addresses are printed. Full snapshot may contain existing
Caddy secrets: NEVER paste/upload it or restore it wholesale over newer config.
The report is evidence, not a future patch base: reload config/ETag immediately
before any conditional mutation. Truncated/ambiguous/changed config requires review.
Inspector neither opens a route nor enrolls users nor restarts services. Review
remaining TEST runtime; do not silently restart it to renew time limits.

A public signup route cannot
be secured by one-click registration quotas alone. No phone/email/profile is required
for exchanging want/offer messages; questionnaires are not security proof. Select an access/
abuse policy BEFORE opening it. Guard exact prefix, size/time/connection limits,
header/log redaction, preserved old routes/PIDs and CAS cleanup preserving concurrent
Caddy changes. Do not replace Caddyfile or restore a stale whole runtime snapshot.
Use a bounded cleanup mechanism with manual fallback; reboot/autosave caveat applies.

Test real independent new users/clients and token rotation. Never enroll automatically
on an unknown Bearer token in tools/list or tools/call; use explicit signup form.
This avoids registry probes minting users silently. Existing TEST connections stay.

Prepared explicit 30-minute route helper and exposure/cleanup limitations are in
[HTTPS TEST scope](https-test.md). Operator supplied the fresh inspector report;
opening remains a separate root-console action. No route is opened by this commit.

## Stage 4: release/operations

Auth/source/dependency review, full parity decision, restart/restore/auth-revocation
rewind drills, filesystem/WAL/backup budget, off-host recovery, alerts and measured
capacity. Separately approved merge/release/production rollout/rollback. Publishing
source or downloading a preflight script closes none of these automatically.
