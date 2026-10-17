# Operations: pilot checklist, not an automatic installer

This repo has NOT been deployed to the existing VPS. Do not change production,
existing embedded TEST, Caddy or GitHub connections just to run package tests.

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
are provided; a guarded installer/public route has NOT been applied. See vps-test-plan.md.
