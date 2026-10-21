# F3c.2c.1 — fixed unit and cgroup supervision proof

**CI: [exact-source evidence](ci-f3c2c1.md). Not an installer or VPS deployment.**
Part of F3c.2c, not completion of that gate. [Previous lifecycle](operator-lifecycle.md).

## Fixed candidate unit

`tools/operator_unit.py` renders review text only, to stdout. Full lowercase source
SHA and canonical HTTPS resource are validated; user/group, port via candidate CLI,
release/state paths and executable module are fixed. No arbitrary shell/ExecStart,
file writes, service calls, network or credential reads. No Install section or
autostart. Source and resource are not proof of approval or existing profile validity.

Root-owned `/opt/mcp-rooms-candidate/releases/<sha>` is immutable to the service;
only `/var/lib/mcp-rooms-candidate` is writable in the host filesystem namespace
(excluding private tmp/device mounts). ProtectSystem/Home, empty capabilities,
NoNewPrivileges, control-group stop with a bounded TERM grace followed by KILL,
finite runtime and accounting are specified. Null stdout/stderr avoids accidental
credential or body logging; a future operator must provide typed diagnostics.
MemoryMax1GiB, TasksMax64 and CPUQuota100% are **provisional review ceilings**, not
accepted capacity or sufficient free RAM/disk on the VPS. They are not installed.
Root wrapper must prove owner/mode/ancestors/venv/site-package immutability, trusted
base Python, profile binding and loaded unit/drop-in identities before effects.
Renderer alone does none of those checks and grants no root operation capability.

## Real CI experiment, not just mocked systemctl

Dedicated secret-free GitHub-hosted ubuntu24.04 job runs a root-owned ephemeral
fixture under a different fixed `/run` unit. Non-root DynamicUser process spawns a
TERM-resistant child; both allocate bounded synthetic memory. A private systemd
runtime marker signals readiness only after child allocation/TERM handler setup;
readiness is not inferred from an RSS floor. Cgroup v2 accounts
memory.current/peak, pids.current and cpu.stat across the group. Stop must remove
both parent and child despite ignored TERM, respect a bounded stop duration and
leave no runnable fixture process. Existing fixture paths/loaded units are refused.
The candidate unit itself is syntax-checked, **not installed or started**.
No artifacts/private data/credentials or persistent/autostart units are created.
Root exists only on a disposable Actions runner, never via our VPS MCP tools.

These measurements demonstrate accounting/cleanup for this fixture, not real
native photo load, candidate admission, disk retention, concurrency or capacity.
A live candidate-in-unit test and aggregate stress/timeouts/disk measurements remain.

## Next implementation and acceptance

1. Root-owned fresh-only reviewed installation wrapper; atomic ready-last release
   commit and fail-closed pre-effect identity checks, no adoption of existing state.
2. Real installed candidate under exact unit/sandbox, including native photo child,
   timeout/disconnect behavior, measured aggregate CPU/RSS/Tasks and disk budgets.
3. Separate bootstrap authorization and stop-only rollback preserving state; no
   recovery promotion, DB rewind, Caddy, other service changes or enabling at boot.
4. Fresh separately approved VPS read-only preflight → loopback → HTTPS acceptance.
   Every remote execution requires explicit approval AND the special password.
