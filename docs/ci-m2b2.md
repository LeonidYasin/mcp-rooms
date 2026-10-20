# M2b.2 CI evidence — private derivative files

Accepted source SHA: [`4eebfce413b80621dfe9e4a2d715df6e55bf0c75`](https://github.com/LeonidYasin/mcp-rooms/commit/4eebfce413b80621dfe9e4a2d715df6e55bf0c75).
This evidence is recorded in a later documentation-only commit. It does not change
the source SHA under test or imply that later changes were already checked.

## Results

- [Application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39483797699), attempt1: success; matrix Python3.10/3.11/3.12/3.13, package build and outside-source imports.
- Python3.12: **330 passed, 2 warnings** (previous worker slice294; 36 file-layer fixtures added).
- Core/file primitives on Python3.10:282 passed/29 skipped/2 warnings observed at predecessor `d172654f252ea6b41773658a6237a202dc11c58c`; runtime source unchanged since that run. Optional codec integration requires>=3.11, so this is not media acceptance on3.10.
- [Documentation build/QA/deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39483789867), attempt1: success. QA:11 diagrams, local links/assets, mobile overflow, local search and screenshots.
- Accepted-SHA aggregate:14 success,1 skipped,0 failures/pending. These include documentation/deploy jobs, not14 application tests or permission to merge.

## Added fixtures

- Durable write, private file modes, reopen/digest read and distinct random keys for identical bytes.
- Invalid root paths/modes, moved/replaced directories, symlink/hardlink/unknown inventory and FIFO rejection.
- Invalid internal derivative/receipt, traversal-like keys, same-size corruption, truncation and unsafe file permissions.
- Persistent count/byte quotas and cooperating-instance concurrent admission.
- Injected disk-write and fsync failures, rollback and short-write handling.
- Real synthetic PNG → installed decode worker → private JPEG file → integrity read, with actual JPEG decode verification in CI.

These establish filesystem primitives only. They do not establish owner authorization,
SQLite reservations/manifests, idempotent attachment, public reads, storage lifecycle,
full OS sandbox or a load/capacity result on the VPS.

## CI failures retained, not hidden

Initial source `b2ef4391` passed application CI but failed the documentation registry:
new node used a hyphen where the schema permits underscores. Fixed in `d172654f`.

The browser search smoke subsequently timed out. Saved screenshots/worker diagnostics
showed a READY worker, no page/network error, an entered query but no subsequent
query message. Static inspection of the pinned Material source map showed that its
query observer listens to `keyup`, while Playwright's text insertion for Cyrillic
does not necessarily generate that event. Waiting longer/typing sequentially alone
did not fix it. The accepted test waits for worker READY, fills the query and presses
End to generate a real keyup without navigation. Result assertions remain mandatory;
search was not disabled or mocked to return success. The final source passes both
push/PR application checks and documentation checks.

No local project execution, VPS access, live data migration, public application route,
credential issuance or main/release change was performed. The earlier Pages
[single-publisher settings gate](ci-pages.md#remaining-single-publisher-configuration-gate)
remains separate; an Actions deploy is not proof the competing publisher was disabled.
