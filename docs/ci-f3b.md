# F3b CI evidence — offline DB+photos recovery quarantine

Accepted application source:
[`6820fc513a34c1d129ca9843f6cc04cbb357a0f2`](https://github.com/LeonidYasin/mcp-rooms/commit/6820fc513a34c1d129ca9843f6cc04cbb357a0f2).
Docs checkpoints do not change accepted runtime SHA. [Contract/limits](recovery-candidate.md).

## Exact-source checks

- [Push CI, attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39529108080): matrix3.10–3.13, full pytest, wheel/sdist/install and candidate+recovery smoke success.
- [Same-source PR CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39529114591): matrix success.
- Python3.12: **761 passed, 2 warnings**,52 additional cases over F3a709.
- Python3.10: **700 passed, 42 skipped, 2 warnings**; all52 recovery cases run there too. Existing native-only exclusions unchanged.
- Installed-wheel recovery smoke on3.11/3.12/3.13: actual native derivative from HTTP/MCP publish/withdraw journey, consistent SQLite+photo snapshot, new quarantined restored copy, counts/integrity and no compose marker/key delivery file. Retrieved3.12 log: `RECOVERY SMOKE PASS: installed wheel; DB + native photo; isolated quarantine; no serving`. Existing `CANDIDATE SMOKE PASS` remains.
- [Docs QA/build/deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39529108189):15 diagrams, local links/assets, mobile overflow/search/screenshots passed at this source.
- Aggregate inspected:14 success,1 skipped,0 failure/pending. Skip is not a test pass or permission to merge/deploy.

Artifact listed on [push CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39529108080):
`owner-first-candidate-6820fc513a34c1d129ca9843f6cc04cbb357a0f2-py312`, ID12315025908,468.6KB,
not expired at inspection. Wheel/sdist/SHA256SUMS only, retention14days. No temporary
DB, recovery manifest, photos, real/private keys, populated env or logs are uploaded.
Not a signature, dependency lock, release or VPS install package.

## Accepted bounded behavior

Operator-only `mcp-rooms-recovery` snapshot/restore/verify. Process flock → derivative
root flock → SQLite empty writer reservation, backup API from committed WAL, fixed
private profile/schema/resource validation and bounded file/hash/count/ordered link/
active publication projection verification. Explicit test proves another SQLite
writer is blocked during photo copying and committed WAL data enters the snapshot.
Orphan derivatives preserved; incomplete uploads/purge/corruption refuse without repair.

New private targets only; no overlap/reuse/symlink/hardlink/shared parent. Partial
failure has no ready marker, retry over old target denied. Final ready-write followed
by simulated fsync failure removes marker. Original stable payload/modes retained.

Restore requires the locked original profile's current security state and matching
resource/schema/device+inode origin. No stale exported JSON as authority. Existing
revoked/disabled stays revoked/disabled; current revocation/disable/missing identity/
credential mismatch applied. Scopes intersect, expiry only decreases; no replacement
credential is imported/issued. Unrelated authorized principal remains usable in
internal restored-copy CI checks. Malformed current authority fails closed.

All recovered publications withdrawn and old consent consumed; no restoration of
public exposure merely because it was active at snapshot time. Snapshot/restored
copies get recovery.json, never candidate profile.json or owner.key. Candidate
validation refuses them; restore never composes an app or binds a listener.

All execution in Actions, synthetic state only; local text/AST work only. No VPS
command/probe/changes, real key issuance/real photos/publication, main merge/tag/
release or production update occurred. Default rooms-only CLI unchanged.

## Failures retained, not hidden

Initial source `4a122dd9915d4da063fc4d7f05ca94e70bf6564f`, push run
[39528840110](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39528840110),
reported5 failed/748 passed on3.12. The shared-parent fixture used mkdir0755 under
umask077, so it actually created0700 and did not exercise the intended unsafe
parent; fixed with explicit chmod0755. Four injected I/O interruptions expected
raw OSError, but the existing PrivatePhotoFiles guard sanitizes it as typed
`media_storage_io`. Tests now assert this exact typed refusal; no-ready/no-retry/
unchanged-source assertions remain, not removed or skipped. Early existing-target
refusal occurs before opening source. Added final-fsync and committed-WAL proofs.

Static refinement `f9e92bd9ffa88b2a023692b2373b81a8dc2ddd77` also introduced
streaming DB hashes and strict persisted JSON shape checks; it is not accepted
in place of the final exact source above.

## Explicit exclusions

This is a **same-host offline recovery rehearsal**, not independent full disaster
recovery. If original current security authority is lost/unavailable, refuse. No
external anti-rollback ledger, signed/encrypted/off-host backup or restored-profile
promotion API. Snapshot checksums do not authenticate a malicious operator's data.
Current security is checked at one locked checkpoint, not forever after unlock.

Copies stay quarantined. Promotion/cutover requires a separate reviewed fresh
security checkpoint, no old profile-marker copying or silent public resurrection.
F3c pinned dependencies/operator package, capacity/disk/retention/stop/rollback and
separate owner-approved preflight/loopback/HTTPS gates remain.
