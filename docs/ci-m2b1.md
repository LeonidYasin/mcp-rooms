# M2b.1 CI evidence — bounded decoder subprocess

Exact tested source: [`583df1b96374a8a9d7e3c46f9e56c32ba39d9fa6`](https://github.com/LeonidYasin/mcp-rooms/commit/583df1b96374a8a9d7e3c46f9e56c32ba39d9fa6).
Evidence documentation is a later commit; it does not change that tested runtime SHA.

- [Push CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39479931742), attempt 1: success.
- [PR CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39479940698).
- Matrix: Python 3.10, 3.11, 3.12, 3.13; wheel and sdist built, installed package checked outside source tree.
- Python3.12: **294 passed, 2 warnings**. Previous M2a: 267 passed; 27 worker tests added.
- Python3.10: **247 passed, 28 skipped, 2 warnings**. Worker tests require Linux/Python>=3.11; the optional Pillow normalizer module is also skipped. These skips are not media acceptance on3.10.
- Commit aggregate at inspection: 14 successful checks, 1 skipped, zero failures/pending. This includes documentation/deploy jobs, not 14 application test jobs or approval to merge.

## What the new fixtures establish

Real installed-module child processes normalize synthetic JPEG/PNG and propagate
safe validation errors. Fault fixtures cover nonzero exits, malformed and excessive
stdout, wall timeout/kill/reap, slot reuse after failure, no waiting queue, clean
launch environment/argv, strict response keys/types/digest/dimensions and no Pillow
import in the supervisor. A structural test checks rlimits precede decoder imports.

This does **not** prove a network/filesystem sandbox, production resource capacity,
OS-level hostile-child isolation, aggregate multi-process admission, durable media
storage, authenticated upload, publication or VPS rollout. No project execution was
performed locally: only file preparation/static parsing; runtime tests ran in CI.

## Deployment/documentation boundary

No VPS service, Caddy route, database, credential or main branch was changed.
The prior [Pages single-publisher settings gate](ci-pages.md#remaining-single-publisher-configuration-gate)
is not resolved by a green CI result and remains owner-controlled. Public loading
of untrusted photos stays blocked pending OS sandbox and staged-storage gates.
