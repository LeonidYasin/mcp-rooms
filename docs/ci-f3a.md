# F3a CI evidence — Landlock/seccomp native photo child

Accepted application source:
[`948b4b7ae9b8a0af4e2beb1a180781adf0c3842e`](https://github.com/LeonidYasin/mcp-rooms/commit/948b4b7ae9b8a0af4e2beb1a180781adf0c3842e).
Subsequent docs checkpoints do not change accepted runtime SHA.
[Policy, prerequisites and limitations](media-sandbox.md). [F2 baseline](ci-f2.md).

## Exact-source verification

- [Push CI, attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39526902717): success, Python3.10–3.13 matrix, wheel/sdist, installed-package checks.
- [Same-source PR CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39526909407): matrix success.
- Python3.12: **709 passed, 2 warnings**,23 more than accepted F2.
- Python3.10: **648 passed, 42 skipped, 2 warnings**. Eight additional native-only skips; core remains supported, candidate/native requires Linux Python≥3.11. Missing kernel support on a native CI runner does not turn into a skip.
- Installed-wheel synthetic native PNG → HTTP upload → MCP attach/preview/consent/publish → anonymous HTML/JPEG → withdraw404 passed on3.11/3.12/3.13. Retrieved3.12 log: `CANDIDATE SMOKE PASS: installed wheel; real native synthetic photo; MCP consent/public/withdraw; no sockets or VPS`. Candidate startup and every decode now require the OS policy, so this also exercises real codecs after lockdown.
- [Docs build/QA/deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39526902764): `DOCS QA PASS: 15 diagrams; local links/assets; mobile overflow; search; screenshots`.
- Aggregate inspected:14 successful checks,1 skipped,0 failed/pending. Skipped is not a passed test or merge permission.

[Push-run artifact](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39526902717):
`owner-first-candidate-948b4b7ae9b8a0af4e2beb1a180781adf0c3842e-py312`, ID12313383175,447.2KB,
not expired at inspection. Contains wheel/sdist/SHA256SUMS only, retention14days.
Not a signed release, dependency lock, VPS installer or packaged state.

## Accepted protections and proofs

Fixed child-only Linux x86_64 policy: unprivileged equal real/effective/saved UID,
zero effective/permitted/inheritable/ambient capabilities; no_new_privs; Landlock
ABI≥3 read-only runtime allowlist; seccomp architecture/x32 guards and reviewed
denylist, including socket/io_uring, process/exec/ptrace/signals/resource mutations,
filesystem metadata mutations and all syscall numbers≥450 pending review.
Installed libraries may be read, but state/DB/marker/key and outside secrets may not.

Landlock ABI3 alone does not mediate chmod/chown/xattr/utime/ioctl/fcntl/flock.
These were explicitly denied with seccomp, not incorrectly claimed to be covered
by read-only Landlock. Synthetic negative child attempts file reads/writes, metadata
changes, sockets/socketpair, fork/signals and fixed forbidden syscalls. Parent checks
content/mode/uid/gid/mtime/ctime unchanged and remains unrestricted.

Candidate probes isolation before constructing the app; every decode reapplies it
before Pillow/input. Unsupported kernel/architecture/privilege, malformed/duplicate
health protocol and timeout fail closed. Tests cover typed unavailable response,
no bare-child fallback, child reaping, admission-slot release and profile-lock
release after startup refusal. Real PNG and JPEG normalization succeed under policy.
No test was weakened or skipped because a required sandbox was unavailable.

All app/native/build/browser work ran in Actions, with synthetic data only. Local
work was text/AST preparation. No VPS command/probe/install, real user/photo/key,
main merge, release/tag or production change occurred. No credential/state enters
the distribution artifact.

## Not accepted by this checkpoint

Not a VM, full syscall allowlist or proof against kernel exploits/compromised
parent/host or hostile same-UID processes. Landlock does not hide stat/chdir/access
metadata; allowed library trees are readable, pre-opened FDs need close_fds discipline.
Parent service remains outside child policy. Bare internal PhotoWorker remains for
legacy internal tests; the TEST candidate never falls back to it.

No claim about actual VPS Landlock ABI or capacity. F3b DB+photos consistent restore
and current revoke/disable reconciliation, F3c dependency/resource/operator package,
then separately approved preflight/install/HTTPS remain. Full browser onboarding,
private replies, search/admin are not silently included in this shorter TEST.
