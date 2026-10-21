# F3c.2c.2 evidence — actual installed candidate under exact unit

Accepted source [`8c5ac1462fdfecc82ec264b4c93c70c8751e0071`](https://github.com/LeonidYasin/mcp-rooms/commit/8c5ac1462fdfecc82ec264b4c93c70c8751e0071).
[Contract and limits](candidate-unit-ci.md). This accepts a CI integration harness,
not a production installer, VPS capacity certification or live public deployment.

## Exact-source results

- [Push CI attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39615199575), [same-source PR](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39615211146): Python3.10–3.13 success. Python3.12 **911 passed,2 warnings**; Python3.10 **850 passed,42 skipped,2 warnings**.8 new pure fixture-helper/guard cases. Warnings not claimed fixed.
- [Push locked-wheelhouse/native candidate/unit job attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39615199647), [same-source PR](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39615210503): success. The exact rendered candidate unit was installed on a disposable hosted runner, not a fake executable or substitute DynamicUser service. Pip/bootstrap/application ran as a new non-root fixed candidate identity; root-owned copied CPython/release and private candidate-owned state were distinct. No install scripts/application/Pillow imports as root.
- `CANDIDATE UNIT PASS` binds full source SHA: real authenticated TCP MCP/20tools; native photo; admission429; body timeout408; disconnect slot release; native fault timeout504 with reap/slot reuse; publication/card/JPEG/withdraw; wrong public Host421; restart preserving key, listing and withdrawn state. production_installer=false and vps_capacity_accepted=false.
- Real4000×3000 (12MP) synthetic PNG becomes1600×1200 JPEG without synthetic input metadata/EXIF. Consent is explicit for synthetic data only, public reads are loopback with canonical Host, withdrawal makes both HTML and photo404. No real listing, Caddy or external client acceptance.
- Exact native photo child command/UID/cgroup was pinned by pidfd before root CI injected SIGSTOP. Real worker wall timeout returned typed504 and reaped the child after **8.011s**; next valid upload succeeded. This is a controlled fault, not every native compromise/crash scenario.
- Kernel cgroup **memory.peak181010432 bytes (172.625MiB)** includes startup and descendants in that unit invocation. Post-readiness scenario group CPU usage **762931 microseconds** (0.762931CPU seconds, not elapsed wall time). Sampled task peak **3**, sampled native parallel peak **1**, no observed OOM kill. Task/native sampling can miss short peaks; memory.peak is kernel charged-memory accounting, not a cold-cache total-host or sum-of-RSS bound. Installation/bootstrap may already warm shared library pages outside the service cgroup.
- Synthetic state at the pre-stop sample: logical274526 bytes, allocated286720 bytes. Sample bounds<64MiB are fixture assertions, NOT accepted retention/exhaustion/disk capacity policy. Interpreter/release/bundle disk is outside this state-only sample.
- [Separate cgroup fixture](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39615199565) remains green; TERM-resistant descendant cleanup proof from [F3c.2c.1](ci-f3c2c1.md) is not replaced by graceful application stop alone.
- [Docs QA/build](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39615199729):16 diagrams, links/assets, mobile overflow/search/screenshots passed. Pages is documentation only; owner single-publisher gate remains.
- Aggregate18 success,1 skipped,0 failed/pending, complete19-check enumeration. No merge or deployment permission follows.

## Failures retained for handoff, not reclassified as success

- Initial `7fcb256ccc8be51b0f4857465d23aac31f61b619` [integration failed](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39613292295). Teardown `reset-failed` could fail after a successful inactive unit had been garbage-collected, hiding the earlier test error. Diagnostic-only `262d2d38f1de71cbf1f1451b1a050c1eb02ab3d4` classified this without dumping raw command output. Cleanup now calls reset only for an actually failed unit and emits bounded failure locations/milestones.
- `fd29c80a1226798c92a47ee67e43032b1b5819c0` [showed real native/body/timeout stages passing](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39614501055) but failed the public-card assertion. The test used automatic127.0.0.1 Host; public_web deliberately requires the configured canonical authority. Accepted fix sets canonical Host in the CI client AND asserts incorrect public Host421. No production Host/TLS/auth/sandbox policy was weakened. These earlier sources are not accepted checkpoints.

## What remains

The CI harness deliberately creates and destroys synthetic fixtures. **Never run it
as the VPS installer**. It does not implement hardened installation receipts,
crash recovery, hostile concurrent mutation protection or general rollback.
F3c.2c.3 must implement reviewed fresh-only operator installation and pre-effect
account/ancestor/path/release/unit/drop-in/process identities; validate base Python
trust; interruption and unrelated-service protection; adopt defensible capacity/
disk/retention/safety-margin criteria. Reuse this exact-unit evidence instead of
rebuilding the same harness. Separate real-key authorization and state-preserving
stop-only rollback remain mandatory. Then owner-approved fresh VPS preflight →
loopback → HTTPS/external acceptance, with approval AND special password per remote
execution. No main/release/VPS/Caddy/live DB/real keys/recovery promotion here.
