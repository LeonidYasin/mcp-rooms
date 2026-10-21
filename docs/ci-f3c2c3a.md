# F3c.2c.3a — fresh-only offline install/inspect accepted in CI

Accepted source [`e63134e077902d59a455f183de00e59760d3f453`](https://github.com/LeonidYasin/mcp-rooms/commit/e63134e077902d59a455f183de00e59760d3f453).
[Installer contract](operator-install.md). This is acceptance of install/inspect,
not a complete production lifecycle, VPS deployment or authority to start a real service.

## Exact-source evidence, attempt1

- [Push matrix](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39621273077) and [same-source PR matrix](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39621278464): Python3.10–3.13 green. Python3.12 **939 passed,2 warnings**, up28 from911. Warnings remain.
- [Push offline package/real unit](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39621272966) and [same-source PR](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39621278552): success. The actual installer runs from a root-owned trusted copy on disposable Actions, with OS `/usr/bin/python3.12`, private verified wheelhouse and umask077. App/Pillow/pip/bootstrap are not imported/run as root. Offline venv/pip/check run as the fresh service identity in bounded transient build units. The whole build cgroup is collected before sealing root-owned code.
- Ready-last root inventory/receipt, inactive exact `/etc/systemd/system` unit, no profile/key/bootstrap/start/enable. Inspect succeeds, a repeated install refuses existing targets without altering its receipt. Presence of this unit is not start authorization. Interruption, partial markers, code/receipt/unit/account drift, unsafe links and restrictive-umask modes are covered by pure tests; these mocks are not crash/power-loss proof on every host.
- CI then explicitly bootstraps **synthetic** data and starts the real candidate separately. Accepted regressions: authenticated TCP MCP/20tools; native12MP PNG→JPEG; admission429/body timeout408/disconnect slot release; exact native child SIGSTOP→504/reap/slot reuse; explicit synthetic consent/card/photo/withdraw; wrong public Host421; restart preserves key/listing/withdrawal. No Caddy/external client/real listing or credential issuance.
- This run: kernel cgroup memory.peak178024448 bytes (169.77734375MiB), scenario CPU637891 microseconds, sampled tasks3/native parallel1; native fault timeout8.011s. State logical274526/allocated286720 bytes. These are bounded fixture samples, **not runtime capacity, full install disk, retention or host-wide cold-cache bounds**. Earlier [F3c.2c.2 measurements](ci-f3c2c2.md) remain separate evidence.
- [Separate descendant/cgroup fixture](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39621272963) and [docs QA/build](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39621272997) success. Docs publication is not VPS deployment; single-publisher owner configuration gate remains.
- Complete19-check enumeration:18 success,1 skipped,0 failed/pending. No merge/release/deploy permission follows.

## Failures retained, not silently reclassified

- Initial source `ca2f1f6a98208f717235fb64e7b13b0d8612933a` was superseded before acceptance. Static review found mkdir modes masked by077; `510abd0ee517c1efd45c3ee8f278e3beca86d2d1` adds explicit directory modes and actual installer umask077 in CI. Files likewise get explicit fd-based modes; exclusive create never adopts an existing path.
- [Rejected runner](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39618797269), diagnostic `667178170f8480440c66be213ba53af6af0dcc4b` [run](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39619653648): hosted runner `/opt` is root-owned0777. Installer correctly refused an untrusted ancestor. `ead4385f6a561bc52e6c26bf81a9a89ef1d3fd81` hardens `/opt` **only in the guarded disposable CI fixture**, restores the original mode on safe teardown; production installer never auto-chmods unsafe existing ancestors.
- [Next rejection](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39620252044), diagnostic `46795fbc07e1558447798650325c6874ce033833` [run](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39620747295): release inventory rejected legitimate zero-byte package files. Fix allows/hashes empty **inventory entries only**; empty trust helpers/wheels/receipts remain rejected. New regression proves this distinction. No ownership/link/write checks were removed.
- Diagnostics print fixed OS path metadata, function names and file uid/mode/link count/size only, not file contents, keys, DBs or message bodies. Failed installs preserve partial targets for review; the production tool has no destructive compensation. CI is disposable, not a production cleanup recipe.

## Next bounded task — F3c.2c.3b

Reuse this installer and accepted actual-unit harness; do not rebuild them. Implement
separately reviewed explicit bootstrap/start/stop with installed-receipt and just-before-
effect account/path/unit/drop-in/process identity checks. A start failure must clean up
only its owned process/cgroup; stop-only rollback preserves all private data and unrelated
services. Keep real-key issuance a separate authorization, with no key in logs/artifacts.
Adopt runtime margins plus full release/bundle/state disk and exhaustion/retention criteria;
current BUILD floors are not service admission. Prove identity drift/interruption and
unrelated-service protection in Actions. Then fresh owner-approved VPS preflight →
loopback → HTTPS/external acceptance, with approval AND special password per execution.
No main, existing MCP services, Caddy, live DB, real keys or recovery promotion here.
