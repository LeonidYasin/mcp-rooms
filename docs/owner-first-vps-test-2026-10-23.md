# Owner-first VPS TEST — loopback acceptance (2026-10-23)

Status: **LOOPBACK PASS**. Fresh isolated candidate installed, bootstrapped, started,
synthetic MCP flow completed, and restart/stop preservation verified on the
owner-approved 4 GiB VPS. HTTPS/Caddy was **not** changed or accepted. This is a
TEST record, not production approval.

## Scope and pins

- Accepted application source: `db32c6ddf8f3b57874180dce81908e0d43aaa2f0`.
- Main after owner merge: `258684311d2f4bb009e339f007978634211da8eb`
  ([PR #5](https://github.com/LeonidYasin/mcp-rooms/pull/5)).
- Pre-release:
  [operator-wheelhouse-db32c6d](https://github.com/LeonidYasin/mcp-rooms/releases/tag/operator-wheelhouse-db32c6d)
  (pre-release, not production, not latest).
- Bundle asset:
  `operator-wheelhouse-db32c6ddf8f3b57874180dce81908e0d43aaa2f0-linux-x86_64-py312.tar.gz`,
  SHA-256 `02ce8ecf7e68ca2f81ca3dd0fecf028610c8304ff0b488b770f4c2f6e2ca29fb`.
- Trusted lock SHA-256 supplied to install:
  `05f7fd5ba929c68b25b46649c25a8868834e50834d6cc0ba9addd15e411de536`.
- Canonical resource: `https://leonid-mcp.duckdns.org/rooms/mcp`.
- Synthetic acceptance harness (release asset, stdlib only):
  `vps_candidate_acceptance-db32c6d.py`,
  SHA-256 `804b731da8d707d01902df0b099baec32e45f16d0b3c27ea247f8a6dace4c934`.
  It reads the disposable synthetic key as root, never prints it, and uses only
  `127.0.0.1`.

## Install, bootstrap, start

The public bundle was downloaded on the VPS and verified before extraction. The
fresh-only installer was run with the pinned source/lock hashes and canonical
resource. Sanitized results:

- `install`: `ok:true`, `installed:true`, `profile_created:false`,
  `started:false`, `start_authorized:false`.
- `inspect`: `ok:true`, `checked:true`, `start_authorized:false`,
  `runtime_capacity_accepted:false`.
- Capacity: accepted; MemAvailable `3,196,616,704` bytes (~2.98 GiB);
  install/state free `16,040,239,104` bytes; `MemoryMax` 1 GiB,
  `RuntimeMaxSec` 7200 seconds.
- Bootstrap: `profile_created:true`, `key_read_or_returned:false`.
- Start: `started:true`, `runtime_capacity_accepted:true`; MainPID `3855`.
- Unit: `active/running`, user/group `mcp-rooms-candidate`, only
  `127.0.0.1:8766` listening; MCP without token `401`, web root `404`.

Authorization phrases and key material are intentionally omitted from this record.

## Synthetic MCP acceptance

The first authenticated loopback run reported:

- `mcp_tools`: 20.
- Phases: `initialize`, `tools_list_20`, `create`, `photo_upload`, `preview`,
  `consent`, `publish`, `public_card`, `public_photo`, `withdraw`,
  `withdraw_public_404`.
- Synthetic listing: `0f1a0a10-4e89-44a7-a338-3975504d45a4`.
- Publication revision: 1.
- `key_read:true`, `key_printed:false`.

This covers a synthetic PNG upload, exact preview, explicit consent, publication,
anonymous card/photo read, withdrawal, and public 404 after withdrawal.

## Restart / state preservation

The guarded controller stopped only the exact unit and preserved state:

- `stopped:true`, `state_preserved:true`, `profile_preserved:true`, old PID `3855`.
- Unit `inactive`; no listener on 8766; synthetic key file remained
  owner `mcp-rooms-candidate`, group `mcp-rooms-candidate`, mode `600`.

A separately authorized start created a new process:

- `started:true`, `runtime_capacity_accepted:true`.
- New MainPID `4222`; `active/running`; MCP without token `401`, root `404`.

The same harness then passed a second full synthetic flow after restart:

- Synthetic listing: `90229ad3-835a-41f4-ab9d-5d55e6c8743c`.
- Same 11 phases; 20 tools; publication revision 1;
  `key_read:true`, `key_printed:false`.

This verifies that stop/start preserves the candidate state and that the MCP,
photo, publication, and public-read path still works after restart.

## Boundary and next decision

- Caddy, HTTPS routes, systemd unit configuration, and existing host services were
  not changed. External HTTPS was not accepted. Earlier external requests to the
  canonical host returned Caddy `401` on all paths; that is not the candidate route.
- No real listing, real photo, real user credential, or production deployment was
  created. Both listings are synthetic and withdrawn.
- No peak RSS/cgroup runtime measurement was taken in this loopback gate; capacity
  acceptance and `MemoryMax`/`RuntimeMaxSec` are not a load or production budget.
- The bootstrap-issued synthetic owner key has a **3600-second TTL** (issued around
  00:07 MSK; expiry around 01:07 MSK). The service remains active after the restart
  test, but authenticated external testing after key expiry requires a separately
  approved new listing-scoped test credential or a fresh profile/key gate. Do not
  silently issue or reuse credentials.
- HTTPS/external MCP acceptance remains a separate owner approval and is not
  implied by this loopback PASS.

## Evidence

Sanitized command reports were collected locally from the owner console; raw
reports are not committed. No secrets are included. The relevant local reports
cover bundle download/verification, install/inspect, capacity/bootstrap, start,
loopback checks, synthetic flow, stop, restart, and the post-restart synthetic flow.
