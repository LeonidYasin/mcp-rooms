# F2 CI evidence — fresh owner-first profile and installed candidate smoke

Accepted application source:
[`86e5a3dccfc2637f6a97c0f5f7dcd60f646fc433`](https://github.com/LeonidYasin/mcp-rooms/commit/86e5a3dccfc2637f6a97c0f5f7dcd60f646fc433).
Subsequent documentation checkpoints do not change the accepted runtime SHA.
[Profile contract and limitations](test-candidate.md).

## Exact-source verification

- [Push application CI, attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39523861037): success, Python3.10–3.13, full suite, wheel/sdist and installed-package verification.
- [PR application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39523866042): same-source matrix success.
- Python3.12: **686 passed, 2 warnings**;41 additional cases over F1.
- Python3.10: **633 passed, 34 skipped, 2 warnings**. Three new native candidate cases skip there; native profile/installed smoke requires Linux Python>=3.11, not core3.10 support.
- Installed-package native smoke passed on3.11/3.12/3.13. Retrieved3.12 log: `CANDIDATE SMOKE PASS: installed wheel; real native synthetic photo; MCP consent/public/withdraw; no sockets or VPS`.
- [Documentation build/QA/deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39523860961):15 diagrams, local links/assets, mobile overflow, Cyrillic search and screenshots passed.
- Aggregate at inspection:14 successful checks,1 skipped,0 failed/pending. Skipped is not a passing test or merge/deploy permission.

[Candidate artifact on the push run](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39523861037):
`owner-first-candidate-86e5a3dccfc2637f6a97c0f5f7dcd60f646fc433-py312`,
artifact ID12312013507, listed as429.8KB and not expired at inspection. Contains wheel,
sdist and SHA256SUMS only; retention14days. No user state, owner.key, DB, photos,
populated env or private rollout log in artifact paths. This is a source-pinned CI
artifact, not a release, signature, dependency lock or production installer.

All application/native/package and docs/browser execution occurred in Actions.
Local work was static text/AST only. All credentials/images/listings were synthetic,
new temporary CI state was deleted on smoke exit; no network socket/real login/VPS
request, real owner credential issuance, publication, main merge/tag/release occurred.

## Accepted behavior

Separate operator-only `mcp-rooms-test-candidate` entry point, not a new remote MCP
tool. Fresh-only mkdir/O_EXCL bootstrap refuses existing/failed/alias roots; initializes
new namespaces explicitly, creates one listings-only principal and writes its short
one-hour test key only to0600 private delivery file. Ready marker last. On delivery/
marker failure, attempt marker removal, credential revoke and user disable independently;
failed compensation is explicit recovery-required, not silently reported as rollback.

Existing-profile startup validates canonical0700 directories, regular0600/single-link
bounded files, exact resource/profile/schema, exact base2/market2/media3/publication1
versions and sqlite_schema fingerprint/integrity before opening RoomStore in new
initialize=False mode. No startup DDL/chmod/repair/issuance/key delivery read. Deleted
DB is not recreated by operational connections. Existing WAL/SHM aliases rejected
before SQLite open; rollback journal requires explicit review, not automatic recovery.
Private operator metadata is not a signature or defense against hostile same UID/root.

One nonblocking profile flock; one cooperating process, one reused native decoder
and one HTTP upload slot. General worker/upload defaults remain two and default CLI
remains rooms-only. Registration/browser cookie commands absent; bootstrap key cannot
use room methods despite discovery of20 user tools. Resource/scopes/revoke guards and
consent v2/fresh publication/withdrawal remain in force. CLI serves loopback only,
port8766, no access logging or forwarded-header trust, no systemd/Caddy installation.

Installed-wheel smoke runs from /tmp, confirms package import outside checkout,
uses real Pillow child to normalize synthetic PNG, HTTP uploads binary bytes, MCP
attaches/approves/publishes, reads anonymous escaped HTML/JPEG, decodes JPEG/checks
metadata and withdraws to404. It is in-process ASGI, not actual HTTPS, native browser
UI/accessibility, live external client or OS sandbox/load acceptance.

## Failures retained and corrected

Initial source `230c328575fe5a9fffbaae8cc12421d260093bbe` failed pytest; full diagnostic
archives exceeded provider bounds. Follow-up `425a9a2f2dec5aac1376cd060494bbed492a7135`
kept all tests and exit status while shortening traceback/capture and tailing bounded
output:3.12 reported7 failed/674 passed. Test snapshots incorrectly treated creation
of normal WAL/SHM files by SQLite mode=ro as schema/data repair, contradicting the
already documented sidecar boundary. Snapshots now compare modes and hashes of stable
payloads rather than dumping full private DB/key bytes; all bad version/schema/
trigger/index cases still require refusal and unchanged main DB/marker/key payloads.
They do not require impossible zero filesystem activity from normal WAL reads.

`f831da978fe11a500af134aa739d7d1760766a61` passed the matrix and installed smoke.
Final accepted source adds five extra negative cases for WAL/SHM symlink/hardlink
and hot-journal refusal. No real security requirement, error assertion, native test,
application suite or failure exit code was disabled to make the run pass.

## Remaining blockers / next bounded task

Next F3a is OS filesystem/network isolation of the native child, including negative
proof that parent state/key/DB and network are inaccessible. One slot plus RLIMIT_AS
512MiB is **not** an adequate sandbox or proven VPS RAM budget. Then DB+files snapshot/
restore with revoked/disabled security-state reconciliation; dependency-pinned reviewed
fresh-target operator install/health/stop/rollback package and resource/load checks.
Only afterwards separately approved fresh VPS preflight, isolated loopback and HTTPS
external acceptance. Remote execution always needs separate approval AND special
password. Do not reuse old rooms-only rollout or retained live data as a fresh target.

Browser M3b.3 remains paused/mandatory before cookie writes. No feed/search, automatic
marketplace registration, private reply/admin MCP or production acceptance. Pages is
versioned documentation only; its owner-controlled single-publisher gate is unchanged.
