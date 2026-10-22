# Read-only VPS preflight — 4 GiB rerun (PASS), 2026-10-22

## Что запускалось

- Инструмент: `tools/operator_preflight.py` из source SHA
  `e6116aeff40d0128de90e36ab1b4045d2f8082e1` (исправленная seccomp-проба), sha256
  `8b204ddedf73baf10e41f1c56d06a67e5e868709a68d75e41f5f77434ddf5f7c`.
- Где: тот же реальный VPS после апгрейда RAM до 4 GiB; root console, вручную владельцем.
- Режим: read-only; установка/запись/перезапуск сервисов не выполнялись.
- Команда: `/usr/bin/python3.12 tools/operator_preflight.py` (защищённые
  `caddy.service`, `mcp-server.service`, `mcp-test.service` были active).

## Sanitized JSON (verbatim output)

```json
{"blockers": [], "checks": {"ancestors": {"install_parent": true, "run_parent": true, "state_parent": true, "unit_parent": true}, "candidate_identity": {"exists": false}, "candidate_paths": {"candidate_build": {"files": false, "loaded": false}, "candidate_service": {"files": false, "loaded": false}, "paths_absent": true}, "candidate_port": {"free": true, "port": 8766}, "capacity": {"inode_free_floor": 65536, "install_free_bytes": 16199569408, "memory_available_bytes": 3290501120, "state_free_bytes": 16199569408}, "host": {"cgroup_v2": true, "linux_x86_64": true, "root_console": true}, "landlock": {"abi": 4, "floor": 3}, "protected_services": {"caddy.service": {"active": true, "loaded": true, "main_pid": "1005", "sub_state": "running"}, "mcp-server.service": {"active": true, "loaded": true, "main_pid": "1013", "sub_state": "running"}, "mcp-test.service": {"active": true, "loaded": true, "main_pid": "1014", "sub_state": "running"}}, "python": {"trusted": true, "version": "3.12"}, "seccomp": {"filter_supported": true, "required_actions": ["errno", "kill_process"]}}, "config_changed": false, "credentials_read": false, "database_opened": false, "installation_authorized": false, "ok": true, "packages_installed": false, "ready_for_separately_approved_install": true, "result": "PREFLIGHT", "services_restarted": false}
```

Exit code: `0` (PASS).

## Наблюдения хоста (owner-provided, read-only)

- `MemTotal: 4009856 kB`, `MemAvailable: 3215188 kB`; `free -m`: total 3915,
  available 3136; swap 511 MiB.
- Install/state FS free ≈15.1 GiB; inode floor 65536.
- Kernel `6.8.0-142-generic`, KVM; cgroup v2; Landlock ABI 4.
- Работают, среди прочего: `x-ui.service` (VPN-панель), `agora-mcp.service`,
  `glacier-*.service`, `postgresql@16-main.service`, `caddy.service`,
  `mcp-server.service`, `mcp-test.service`.
- `x-ui`/VPN не входили в дефолтный PROTECTED-набор на момент этого прогона; после
  него `x-ui.service` добавлен в defaults. Если `mcp-server` будет погашен, в
  следующем прогоне добавляйте остальные реально критичные юниты через
  `--protected-unit` (флаг заменяет список defaults, поэтому перечислите все).

## Разбор

- `memory_floor` пройден: ≈3.07 GiB available > 2 GiB floor.
- Seccomp-фикс подтверждён на реальном хосте: `filter_supported=true`.
- Кандидатные account/group/unit/path отсутствуют; порт 8766 свободен; предки
  безопасны; защищённые сервисы active.
- PASS не подтверждает реальную capacity, native-нагрузку, HTTPS и не разрешает
  install/bootstrap/start.

## Решение

- Preflight PASS. Установка **не выполнялась** и требует отдельного разрешения
  владельца и специального пароля; loopback и HTTPS — дальнейшие отдельные gates.
- Никаких изменений на хосте не вносилось.
