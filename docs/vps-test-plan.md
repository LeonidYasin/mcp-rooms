# Isolated VPS TEST: preparation, not deployment authorization

Target host: existing operator-managed Ubuntu VPS. Keep mcp-server.service,
mcp-test.service, Caddy and existing databases/credentials unchanged. No execution
through run_python/run_command/SSH/background; operator runs any root script only
from their own console after reviewing exact scope and pinned checksum.

## Proposed isolated resources (not yet created)

- New OS user/group: mcp-rooms-test, no sudo or access to existing MCP homes.
- New checkout/venv/data under /home/mcp-rooms-test, private 0700 data directory.
- New unit mcp-rooms-test.service, loopback 127.0.0.1:8765, 2-hour runtime limit,
  not enabled at boot. See deploy/mcp-rooms-test.service.example (NOT installed).
- New SQLite database with standalone application_id; no existing DB copied/opened.
- Proposed canonical external resource: https://leonid-mcp.duckdns.org/rooms-test/mcp.
  Prefix /rooms-test is stripped by a FUTURE separately reviewed Caddy route.
  Public signup would be /rooms-test/signup; it is NOT opened by this preparation.
- Authentication only rooms-issued Bearer (client UUID or server-issued key), not
  GitHub PAT. New endpoint must never forward local user tokens to GitHub or main MCP.

## Stage 1: read-only operator preflight

Run ONLY pinned deploy/vps_preflight.py after CI. It reads versions, selected systemd
properties/PIDs, listening port numbers, disk/memory reserve and candidate path/user
existence. It never opens any DB, reads credentials/Caddy configuration, creates an
OS user, installs packages, writes service config, starts/restarts units or changes
firewall/proxy. Wrapper download creates a private script copy, not a deployment.

Blockers include occupied port, pre-existing target user/path/unit, insufficient
reserve or inactive existing services. Existing candidates must be inspected,
never deleted/overwritten automatically. Preflight requires root ONLY for the
operator's bounded local checks, not for running the rooms service.

## Stage 2: guarded loopback installation — NOT implemented/applied yet

After actual preflight review, prepare a pinned installer with private log/state,
exclusive lock, exact existing PID/config checks, minimal new user/paths and rollback
that affects only resources it created. Build/test as new service user in an
isolated venv; no installs into old venvs. Start ONLY the new unit and confirm:
8 tools; new app/schema; signup off/on as intended; enrollment and UUID/server-key
identity tests; no-auth/expiry/revoke/disabled/ownership/rotation negatives; actual
write access inside systemd sandbox. Compare old service PIDs unchanged. No secrets
printed in operator reports, and no real key issuance through MCP tool output.

## Stage 3: temporary external route / real client gate

Separate approval and fresh sanitized Caddy inspection. A public signup route cannot
be secured by merely pretending contact is a verified identity. Select an access/
abuse policy BEFORE opening it. Guard exact prefix, size/time/connection limits,
header/log redaction, preserved old routes/PIDs and CAS cleanup preserving concurrent
Caddy changes. Do not replace Caddyfile or restore a stale whole runtime snapshot.
Use a bounded cleanup mechanism with manual fallback; reboot/autosave caveat applies.

Test real independent new users/clients and token rotation. Never enroll automatically
on an unknown Bearer token in tools/list or tools/call; use explicit signup form.
This avoids registry probes minting users silently. Existing TEST connections stay.

## Stage 4: release/operations

Auth/source/dependency review, full parity decision, restart/restore/auth-revocation
rewind drills, filesystem/WAL/backup budget, off-host recovery, alerts and measured
capacity. Separately approved merge/release/production rollout/rollback. Publishing
source or downloading a preflight script closes none of these automatically.
