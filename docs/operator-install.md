# F3c.2c.3a — fresh-only install, never implicit start

**Accepted in [exact-source Actions](ci-f3c2c3a.md),939 tests3.12. No VPS execution authorized.**
`tools/operator_install.py`: install/inspect only. No bootstrap, key read, enable,
start, upgrade, deletion or recovery. Presence of an installed unit is not start approval.

## Trust and effects

- Linux x86_64/Python3.12/root/cgroupv2; tool directory, fixed helper files and runtime
  lock must be root-owned under non-writable canonical ancestors. Mutable checkout
  or a GitHub toolcache interpreter is not accepted as production operator trust.
- Fixed OS `/usr/bin/python3.12`, root-owned OS stdlib. OS/package administrator is
  trusted; root attackers/concurrent hostile root changes are not a solved threat.
- Already extracted, root-private verified exact-source wheelhouse; no download or
  archive extraction. Caller-supplied expected source/lock hash are required; the
  trusted committed runtime lock must match. Digests are not signatures/CVE clearance.
- Exclusive root-private operator lock, fresh fixed account/group/unit/release/state
  only. Existing/dangling paths, unit files/drop-ins across system directories and
  loaded/transient units fail closed; no adoption or automatic cleanup.
- Venv/hashed offline pip/check run as the fresh non-root identity in bounded transient
  build units, not as root/runuser alone. Private temp, no new privileges/capabilities,
  read-only host FS except venv, protected cgroups, AF_UNIX only/IP deny;120s/512MiB/
  32tasks/100%CPU. Entire build cgroup must be collected before root seals files:
  chown alone cannot revoke retained open write file descriptors.
- Root-owned sealed release with bounded file/link inventory and hashes; no links
  escaping release. Trusted tools/interpreter/account/bundle rechecked before unit
  commit. Fixed root-owned `/etc/systemd/system` unit is verified and daemon-reloaded,
  **not started/enabled**. Loaded fragment must match, with no drop-ins/PID/activity.
- Explicit new directory/file modes survive umask077; no existing path is adopted.
- Root-only inventory and installation receipt committed ready-last with fsync and
  exclusive creation. Failure preserves partial new paths/account for review and
  permanently blocks automatic retry; no compensation deletes data or unrelated units.
- Inspect rechecks trusted code/interpreter/account, release inventory, rendered unit,
  root receipt/base inode, private state directory and inactive loaded unit. It reads
  no owner key/profile DB and grants no startup authority.

## Resource boundaries

Install checks a conservative BUILD MemAvailable floor768MiB, release-FS free2GiB
and state-FS free512MiB before effects/build phases. These are necessary build
floors, **not runtime capacity acceptance** or a guarantee against filesystem races.
Actual candidate policy remains provisional1GiB/64tasks; do not start from this
installer until the separate start/controller+capacity gate is accepted. No quota,
retention/exhaustion or cross-host disaster recovery is silently accepted.

## Validation and continuation

Pure interruption/existing-target/code/receipt/unit/account drift tests plus the
existing real candidate-in-unit CI harness must call the actual installer from a
root-owned trusted copy. CI asserts no profile/start, inspect, repeat-install refusal,
then explicitly bootstraps synthetic data and reuses the accepted native/fault/card/
withdraw/restart scenario. Fixture teardown deletes synthetic state only in CI;
production installer has no deletion operation.

Next: separately reviewed profile bootstrap and start/stop controller, just-before-
effect identity and interrupted-start cleanup, adopted runtime/disk safety margins,
then separately approved fresh VPS preflight → loopback → HTTPS. Every VPS execution
requires explicit approval AND special password. Do not run CI harness on VPS.

CI prerequisite: hosted Actions `/opt` is0777. The disposable fixture temporarily
hardens that ancestor and restores it on safe teardown. This is **not** an installer
feature or permission to change VPS ancestor modes. Installer still refuses unsafe
existing ancestors. Legitimate empty package files are hashed in code inventory;
empty trust inputs/receipts remain rejected. See evidence for failures and fixes.
