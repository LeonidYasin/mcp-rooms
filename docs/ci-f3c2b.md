# F3c.2b CI evidence — real unprivileged offline lifecycle

Accepted source [`a51d306e3ca5ca0b664a17494dfe606b379b9558`](https://github.com/LeonidYasin/mcp-rooms/commit/a51d306e3ca5ca0b664a17494dfe606b379b9558).
[Contract and boundaries](operator-lifecycle.md). This is CI acceptance of an
unprivileged rehearsal, NOT root/systemd supervision, VPS deployment or production.

## Exact-source observations

- [Push CI attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39607635794): Python3.10–3.13 matrix success. Python3.12 **864 passed,2 warnings**; Python3.10 **803 passed,42 skipped,2 warnings**.38 more passing cases than F3c.2a; warnings not claimed fixed.
- [Push offline wheelhouse attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39607635812): success. Real new venv installation from the verified complete hash-pinned wheelhouse with no-index/no-deps/only-binary/require-hashes, pip check, installed native/recovery smoke and real TCP lifecycle rehearsal.
- `LIFECYCLE SMOKE PASS` bound to the full accepted source: offline_install=true, occupied_port_preserved=true, interrupted_start_reaped=true, real_loopback_start_stop_restart=true, authenticated_synthetic_mcp=true, listing_and_key_preserved=true, rollback=stop-only, root_or_systemd=false, resource_budget_accepted=false.
- Occupied-port fixture kept an existing listener alive; no process readiness receipt was committed. A separate injected failure after real server startup but before process receipt caused exact-child termination/reaping; port became reusable and private state remained. These are two specific real faults, not proof against every crash window or hostile same-UID process.
- Real synthetic authenticated initialize/tools/list/create/get used the installed package over loopback;20 tools, private listing and disposable credential preserved across stop/restart. Bootstrap is explicit; controller never reads/returns the key. Only the CI client reads its disposable key for authentication. No real-user key or state uploaded.
- Observed idle parent RSS **60068 KiB** and maximum RSS of one reaped child **72544 KiB**, from this run only. Neither is combined parent/native peak, concurrency stress, cgroup accounting, memory budget or VPS capacity acceptance.
- [Documentation QA attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39607635733):16 diagrams, local links/assets, mobile overflow, search and screenshots passed. GitHub Pages remains documentation only; the separate single-publisher owner configuration gate remains.
- Exact-source aggregate:16 success,1 skipped,0 failed/pending, complete check-source enumeration. The skipped job is not a passing runtime test. No merge/deployment approval follows from aggregate success.

## Accepted behavior

Fresh-only private install with exclusive lock and ready-last receipt; bounded,
strict owner/path/receipt/interpreter/source checks; clean environment and fixed
argv; separate bootstrap. Actual child identity includes boot ID/start ticks/UID/
command hash and pidfd pinning. Readiness checks the child's loopback listener plus
unauthenticated401; authenticated acceptance is a distinct CI client check.
Stop signals only the pinned process. Restart preserves prior receipts and state;
rollback only stops the candidate, never rewinds DB, revocations or publication.

Pure unit negatives cover partial install/receipt commit, existing paths and links,
metadata tampering, conflicting locks, malformed/reused identities and stop timeout.
Runtime probes/tests/builds ran in Actions; local preparation was text/AST only.

## Next gate: F3c.2c

Root-owned immutable release paths and fixed systemd unit/drop-in verification,
cgroup descendant cleanup, measured aggregate CPU/RSS/Tasks/timeout/admission/disk
budgets and reviewed operator runbook remain. This process-only rehearsal cannot
replace those controls. Then separately authorized fresh VPS preflight, loopback
TEST and HTTPS/external acceptance. Each remote execution requires owner approval
AND special password. No such operation, main merge, release, real credential
issuance, live DB change or public listing was performed by this slice.
Browser writes and recovery promotion remain separate paused gates.
