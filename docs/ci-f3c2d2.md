# CI evidence — F3c.2d.2 x-ui protected by default, 2026-10-22

## Source point

- Source SHA: `db32c6ddf8f3b57874180dce81908e0d43aaa2f0`
- `tools/operator_preflight.py` sha256:
  `5e141f47fdaaca47cc97b948e1ea00c6ad5a3ac73e34a8a1afa2242af846eb57`
- Change: default `PROTECTED` now includes `x-ui.service` (3x-ui panel and its
  managed Xray VPN), plus a regression test for the exact default tuple.
- Same commit records the post-upgrade VPS PASS report
  ([`preflight-vps-2026-10-22-4gb.md`](preflight-vps-2026-10-22-4gb.md)).

## GitHub Actions (all on `db32c6d`)

- CI run [39833038788](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39833038788): success.
  - Python 3.10: `931 passed, 42 skipped`.
  - Python 3.11: `992 passed`.
  - Python 3.12: `992 passed` (was 991; one regression test added).
  - Python 3.13: `992 passed`.
  - Build/install smoke and source-pinned candidate distribution: success.
- Operator systemd supervision proof
  [39833038477](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39833038477): success.
- Operator offline package
  [39833038430](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39833038430): success.
- Documentation Pages
  [39833038701](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39833038701): success.
- Pages build/deployment
  [39833036863](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39833036863): success.

No failing run was produced in this slice.

## What this does not prove

- CI does not run the tool against the real VPS; the PASS report is a separate
  owner-run point-in-time observation.
- `x-ui.service` is the host's panel/VPN unit; a distinct VPN unit would need an
  explicit `--protected-unit`. That flag replaces, not augments, the defaults.
- CI is not live TEST or production and authorizes no install, bootstrap, start,
  loopback, HTTPS, credentials, merge or release.

## Next gate

`OWNER-FIRST-VPS-INSTALL` — separately approved fresh install/bootstrap/start and
loopback acceptance, with the special password. Preflight PASS alone authorizes
none of it.
