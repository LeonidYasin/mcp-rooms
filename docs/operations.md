# Operations: pilot checklist, not an automatic installer

The operator installed an isolated Rooms TEST at runtime source
4b2351c0b6522d30c888496b3c1774be8791345f. Subsequent temporary HTTPS, real Notion
and Qwen-through-local-proxy, and a distinct-owner round trip passed. The latest
operator report accepted a 24-hour existing-account window: signup disabled,
not boot-enabled, Rooms-only restart, cleanup timer armed; actual cleanup is pending.
Original unit remains two-hour/registration-enabled, temporarily overridden in /run.
Production and old embedded services remain unchanged. This is NOT production
acceptance. See acceptance-2026-10-19.md for evidence attribution and pending gates.

## Before any live TEST

- Dedicated non-root OS user, new private 0700 local data directory, canonical
  absolute DB path; regular 0600 single-link file. No symlinks, NFS or shared dir.
- TLS proxy to a separately approved loopback port; correct HTTPS resource URL.
  Keep strict systemd sandbox and add only the exact data directory to write paths.
- Controlled TEST users, distinct per-connection credentials, expiry/revocation tested.
  Opt-in one-click signup is pseudonymous, no contact/profile required; see registration.md.
  Empty POST creates a new user, not recovery; do not auto-retry a lost response.
  No actual credentials in logs/chat/CI. All examples use placeholders.
- Rate/read-time/connection limits at the proxy; disable/redact access logs and
  exception payloads. SDK DNS-rebinding host/origin checks protect MCP requests.
- Budget SQLite DB pages + WAL + SHM + snapshots + token files; monitor free space
  and sanitized storage errors. DB pages cap: 64 MiB (4096 * 16384); active WAL is
  NOT hard capped by journal_size_limit. Long readers/backups can grow WAL.
- Measure target concurrency/p95 and failure behavior. Unit/ASGI concurrency is
  not production load evidence. Review dependency versions/licenses/security.

## Backup / restore

Run maintenance locally as the service OS user, not an MCP tool:

```text
mcp-rooms-maintenance verify /ABSOLUTE/PRIVATE/rooms.db
mcp-rooms-maintenance backup /ABSOLUTE/PRIVATE/rooms.db /ABSOLUTE/PRIVATE/new-snapshot.db
```

SQLite backup API makes a consistent NEW snapshot including room data, users and
credential digests. No overwrite of active DB; no raw copy of only a WAL-mode .db.
Verify application_id/version/integrity/FK/table presence. Restore by backing up a
verified snapshot to ANOTHER new private path. Keep the original DB until a
separately approved stop/switch/rollback window and live acceptance.

Backups contain private messages, memberships and authentication metadata and must
be protected like the DB (including encrypted off-host storage and retention policy).
Restore also rewinds disable/revocation/expiry metadata: revoked-after-snapshot
keys can become active again. Reapply revocations/disabled users from a protected
external record or reissue/revoke all credentials before exposing a restored server.
Restoring old data can revive later-deleted text; obey privacy/retention rules.
No backup scheduler, off-host transfer or guaranteed disaster recovery is supplied.

## Gates

CI exact SHA and package build -> source/auth review -> live private TEST with real
clients/independent users -> restart and full restore drill -> revocation after
restore -> disk/WAL/load/alerts -> separately approved production rollout/rollback.
OAuth/ownership-verified public registration is another release, not implicitly enabled by publishing
source. Keep a single canonical versioned core once embedded migration is designed;
this alpha does not yet switch embedded imports to this package.

Self-signup budgets are backed up/restored with auth and room state. Restoring a
snapshot also rewinds signup counters; before external access reapply revocations
and reassess abuse budgets. Read-only VPS preflight and an uninstalled unit example
are provided. The guarded installer and temporary route HAVE been operator-applied;
publishing later source does not update that runtime. See vps-test-plan.md.


## Guarded recovery drill (operator-reported PASS; client follow-up scoped)

`deploy/vps_rooms_recovery_drill.py --run --window-state /root/OWN_WINDOW/state.json`
is operator-console-only. It requires the exact accepted 24-hour helper checksum,
private state ownership, accepted/unexpired window with >15 minutes remaining,
unchanged original unit plus only its own runtime override/route, expected runtime
source, active cleanup timer and old services. It does not import project code as root.

As the service OS user it uses the installed maintenance CLI to make a consistent
NEW private snapshot and a SECOND verified restored-copy path. It compares integrity,
FK/schema checks, aggregate counts and two synthetic round-trip messages, then
restarts ONLY Rooms TEST and verifies the same live messages and DB integrity.
The live DB is never replaced, the restored copy never listens, no keys are issued
or revoked, and the HTTPS deadline is not extended. New snapshot files contain
private/auth data; do not upload them. They remain for operator review; retention,
encryption/off-host backup and automated deletion are separate work.

This is a limited backup-copy/restart drill, NOT proof of production failover,
authenticated client behavior after restart, all historical rows, or post-snapshot
revocation reconciliation. Notion actually read retained dialogue and sent a fresh reply after the operator PASS;
Qwen reported reading that reply and closing its own ACL fixture, finishing the
post-restart client acceptance.
Missing/expired/closed synthetic messages cause STOP before restart. Failed setup
never authorizes blind overwrite of changed units, full Caddy restore or live DB restore.

Before a live key-revocation drill, use disposable users/credentials or prove a
second working credential for the real principal. Do not revoke the only Notion/Qwen
key. A disabled user is not re-enabled by issue-token. Restoring an old snapshot can
revive revoked credentials: prove reconciliation on an isolated copy before exposure.


## Disposable auth/revocation drill (operator-reported PASS; real-client follow-up scoped)

`deploy/vps_rooms_auth_drill.py` verifies the checksum-pinned accepted recovery helper,
24-hour state/route/unit/timer and old services, then runs synthetic logic as the
service OS user. Two NEW users, three read-only 600s credentials; no Qwen/Notion key
is an input. The live HTTPS /identity gate must reject old A after revocation while
replacement A and independent B still work. Disabling synthetic B rejects it without
breaking replacement A. Existing user/credential rows are never targeted.

A pre-revocation SQLite snapshot is copied to a new isolated DB. Direct authentication
on this copy demonstrates revived old A and B; reapplying the canary revocation and
user disable must reject them while replacement A still works. This proves the hazard
and a LIMITED canary reconciliation, NOT reconciliation of every possible real change
since a production snapshot. No restored-copy HTTP server is opened; live DB is not
replaced, service is not restarted, registration stays closed and deadline unchanged.

Finally revoke all three synthetic keys and disable both synthetic users in live and
restored copies. Keys stay in subprocess memory/HTTPS headers; never argv/env/stdout,
files, tool arguments or logs. A private ledger contains only generated test user/key
IDs and phases for interrupted-run review. Forced termination/power loss can interrupt
cleanup: review the ledger; issued keys expire after at most 600s. Even cleaned test
rows remain budgeted (2 users, 3 credentials), not silently deleted. Private snapshots
contain real DB/auth metadata and historical canary state; preserve permissions and
apply a retention policy. Do not publish them or expose a pre-reconciliation copy.

CI runs the SAME canary logic on temporary DBs with a direct-auth probe substituted
for HTTPS, including failure cleanup and an untouched unrelated user/key. It does NOT
prove actual Caddy/TLS/network acceptance. Operator PASS and real client recheck must
follow separately. Off-host encryption, general revocation journal, load/alerts and
observed 24h cleanup are still open gates.


Operator reported the disposable drill PASS with all synthetic keys revoked/users
disabled. Agent then confirmed the real Notion connection still reads/writes;
Qwen fresh post-auth read is pending. Snapshots/ledger remain private and retained.
Do not rerun merely to manufacture more evidence: each run budgets 2 user rows and
3 credential rows. Observe final route/service/override cleanup. Manual early closure
and actual calendar-triggered cleanup are different evidence; do not mark both passed
from one manual command. Neither is broad production or public-registration approval.


## Latest closure (operator-confirmed manual action)

The operator closed the current window with its exact private cleanup helper.
Rooms is inactive/dead with PID0, no drop-ins, original RuntimeMaxUSec=2h; the
route was removed and DB preserved. Do not treat the disconnected endpoint as
expired/revoked real credentials, reinstall/re-register automatically, or start the
original signup-enabled unit without another explicit approval. Manual cleanup
passed; calendar-triggered automatic cleanup is NOT tested.

The last Qwen answer had the expected message ID but changed the actual POST-AUTH-05
text. Keep exact-read verification open, not a fabricated PASS. A client answer and
a raw MCP tool result are different evidence; preserve that distinction in future
acceptance. This does not establish a server edit/corruption defect. See the
acceptance record; no re-opening was performed to investigate after closure.
