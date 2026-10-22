# Read-only VPS preflight — 2026-10-22

## Что запускалось

- Инструмент: `tools/operator_preflight.py` из принятого source SHA
  `01d2a93821639efa1a4ad3ab0ca14a2483e4821c`, sha256
  `bea79dfe5bdfd093a904e527490675f8c3335f07495b1191ba36fd79113a7c33`.
- Где: реальный VPS, root console, вручную владельцем.
- Режим: read-only; установка/запись/перезапуск сервисов не выполнялись.
- Команда: `/usr/bin/python3.12 tools/operator_preflight.py` (все три защищённых
  юнита были active, поэтому без `--protected-unit`).

## Sanitized JSON (verbatim output)

```json
{"blockers": ["preflight_memory_floor", "preflight_seccomp_unavailable"], "checks": {"ancestors": {"install_parent": true, "run_parent": true, "state_parent": true, "unit_parent": true}, "candidate_identity": {"exists": false}, "candidate_paths": {"candidate_build": {"files": false, "loaded": false}, "candidate_service": {"files": false, "loaded": false}, "paths_absent": true}, "candidate_port": {"free": true, "port": 8766}, "host": {"cgroup_v2": true, "linux_x86_64": true, "root_console": true}, "landlock": {"abi": 4, "floor": 3}, "protected_services": {"caddy.service": {"active": true, "loaded": true, "main_pid": "10197", "sub_state": "running"}, "mcp-server.service": {"active": true, "loaded": true, "main_pid": "401887", "sub_state": "running"}, "mcp-test.service": {"active": true, "loaded": true, "main_pid": "401875", "sub_state": "running"}}, "python": {"trusted": true, "version": "3.12"}}, "config_changed": false, "credentials_read": false, "database_opened": false, "installation_authorized": false, "ok": false, "packages_installed": false, "ready_for_separately_approved_install": false, "result": "PREFLIGHT", "services_restarted": false}
```

Exit code: `2` (blockers).

## Наблюдения хоста (owner-provided, read-only)

- `MemTotal: 2015212 kB`, `MemAvailable: 1233140 kB`, swap 524284 kB.
- `systemd-detect-virt`: `kvm`; kernel `6.8.0-142-generic`.
- `Seccomp: 0` для текущего shell (фильтры не установлены).
- `/proc/sys/kernel/seccomp/actions_avail`:
  `kill_process kill_thread trap errno user_notif trace log allow`.

## Разбор блокеров

- `preflight_memory_floor` — **реальный**. MemAvailable ≈ 1.18 GiB ниже принятого
  floor 2 GiB. Хост ~1.92 GiB RAM уже обслуживает mcp-server, mcp-test и caddy;
  установка кандидата и native-декодирование фото на нём небезопасны.
- `preflight_seccomp_unavailable` — **ложное срабатывание инструмента**. Проверка
  ошибочно искала `filter` среди действий; исправлено в
  [`docs/ci-f3c2d1.md`](ci-f3c2d1.md) (source SHA `e6116ae…`), но на этом хосте
  исправленная проба ещё не запускалась.

## Решение

- STOP. Install/bootstrap/start не выполнялись и не разрешены.
- Этот VPS не подходил для fresh-кандидата по памяти; после апгрейда до 4 GiB
  повторный прогон дал PASS — см.
  [`docs/preflight-vps-2026-10-22-4gb.md`](preflight-vps-2026-10-22-4gb.md).
- Никаких изменений на хосте не вносилось.
