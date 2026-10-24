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

## Opt-in persistent unit shape (wired, not activated)

`tools/operator_unit.py` accepts `persistent=True` (CLI `--persistent`). The default
output is byte-identical to the accepted TEST unit (`Restart=no`, `RuntimeMaxSec=2h`,
no `[Install]`), so existing receipts and evidence stay valid. The persistent variant
adds `Restart=on-failure`, `RestartSec=5s`, removes `RuntimeMaxSec`, and appends
`[Install] WantedBy=multi-user.target` while keeping every sandbox/resource directive.

The mode is now carried end to end for fresh installs:
`operator_install.py install --persistent` renders the persistent unit and records
`"persistent": true` in the ready-last receipt; `inspect` and the guarded controller
re-render with the recorded mode and refuse any receipt/unit mismatch. Receipts written
before this field exist remain valid and mean `false` (transient), so an already
installed TEST candidate can still be inspected, started and stopped.

Still not granted: boot enable is a separate explicit action below, restart-policy
acceptance under real systemd, runtime capacity, backup/monitoring, and any production
approval. The persistent shape must be proven by a fresh install under the real unit,
not by rendering alone.

## Boot enable — explicit, authorized, never started

`operator_control.py` has two more actions, each with its own confirmation phrase:

- `enable` (`ENABLE-OWNER-FIRST-CANDIDATE`): requires a receipt recorded with
  `"persistent": true` (otherwise `control_enable_requires_persistent_mode`), the exact
  inactive validated unit, then runs only `systemctl enable`. It confirms the unit file
  state became `enabled` and that the unit is still `inactive` with `MainPID=0`
  (`control_enable_started_the_unit` otherwise). Re-running is idempotent.
- `disable` (`DISABLE-OWNER-FIRST-CANDIDATE`): requires the same validated inactive
  unit, runs only `systemctl disable`, confirms the state left `enabled`, and is
  idempotent when already disabled.

Neither action starts, restarts, stops, edits or reloads the unit, and neither touches
Caddy or another service. Enabling does not by itself make the candidate production:
backup/restore, monitoring, real credentials, capacity measurement and the owner's
release decision remain open, and every host action still needs separate approval and
the special password.

## Next implementation and acceptance

1. Root-owned fresh-only reviewed installation wrapper; atomic ready-last release
   commit and fail-closed pre-effect identity checks, no adoption of existing state.
2. Real installed candidate under exact unit/sandbox, including native photo child,
   timeout/disconnect behavior, measured aggregate CPU/RSS/Tasks and disk budgets.
3. Separate bootstrap authorization and stop-only rollback preserving state; no
   recovery promotion, DB rewind, Caddy, other service changes or enabling at boot.
4. Fresh separately approved VPS read-only preflight → loopback → HTTPS acceptance.
   Every remote execution requires explicit approval AND the special password.
