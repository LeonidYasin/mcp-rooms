# F3c.2c.2 — installed candidate under exact reviewed unit

**SOURCE pending Actions. CI-only harness, NOT a production/root installer.**
[Reviewed unit](operator-supervision.md) · [Prior lifecycle](operator-lifecycle.md).

## Scope

The locked-wheelhouse workflow builds a disposable fixed user/group, root-owned
copied CPython3.12 runtime and immutable release, private fresh synthetic profile,
and exact rendered `/run/systemd/system/mcp-rooms-candidate.service`. Pip and
application/bootstrap execute as the non-root candidate user, never as root.
The CI controller imports no application/Pillow code and prints no raw credentials,
request bodies, pip/bootstrap output or subprocess errors. No artifacts contain
state, keys or photos. No enable-at-boot, Caddy, public HTTPS or real publication.
Fixture setup/teardown intentionally require root ONLY on a GitHub-hosted runner.
The harness is not safe general-purpose installation tooling and must not run on VPS.

## Real application acceptance scenario

- Exact unit with NoNewPrivileges/empty capabilities/ProtectSystem/Home; native
  Landlock/seccomp preflight must succeed before readiness. Root-owned code is
  separate from candidate-owned state; no substitution of a fake executable/unit.
- Real TCP authenticated MCP initialize and20 tools; synthetic private listing.
- A partial binary HTTP body holds the single upload admission; concurrent upload
  returns429, the real10s body timeout returns408 and disconnect releases the slot.
- Real12-megapixel synthetic PNG with synthetic metadata normalizes in the native
  isolated child, attaches to exact listing revision, publishes by explicit test
  preview/consent, renders public loopback HTML/JPEG with the canonical Host, rejects an incorrect
  public Host with421, and withdraws to404.
- Root CI injects SIGSTOP only through a pidfd for the exact known child command,
  UID and candidate cgroup. The real8s worker wall timeout must return typed504,
  reap the child and allow a subsequent successful native upload. No code mocking,
  arbitrary PID or signal injection exists in public MCP/HTTP methods.
- Real systemd stop/restart preserves the key/listing and withdrawn state; stop-only
  result preserves private state. Later synthetic fixture deletion is teardown,
  **not** the operator rollback policy.
- Cgroup memory.peak, CPU use and sampled task/native counts include the candidate
  and native descendants, not the external load generator. State logical/allocated
  disk bytes are sampled. No OOM kill, one native child and bounded fixture disk.

## What this does NOT accept

One bounded CI scenario is not saturation/concurrency capacity, disk-retention
exhaustion policy, adversarial load certification or measured minimum VPS RAM.
1GiB/64tasks/100%CPU remain provisional candidate ceilings. Sampling may miss very
short peaks; cgroup memory.peak is kernel-accounted, sampled tasks/native counts
are observations only. Synthetic credentials expire and never become live accounts.

Fresh-only operator installation still needs reviewed immutable source/runtime
trust, ready-last release receipt, crash/interruption recovery, loaded unit/drop-in/
path/account checks immediately before effects, unrelated-service preservation,
credential bootstrap authorization and a complete disk/capacity runbook. Existing
units/accounts/state must never be adopted by copying this CI harness. Disaster
restore promotion and browser writes remain separate gates. Every VPS execution
requires explicit owner approval AND the special password. No main merge implied.
