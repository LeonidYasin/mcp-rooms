# F3c.2c.3c — aggregate capacity measurement accepted in CI

## Итог

Срез принят как **CI**, не как VPS TEST и не как production.

- Accepted application source SHA: `db32c6ddf8f3b57874180dce81908e0d43aaa2f0` (application source не менялся с момента принятия; CI прогонял docs-коммит ветки `feat/standalone-identity`).
- CI workflow: `Operator offline package` (`.github/workflows/operator-package.yml`), шаг **Real installed candidate under exact systemd unit (disposable CI only)**.
- CI run: https://github.com/LeonidYasin/mcp-rooms/actions/runs/40132542321 (conclusion: success).
- Harness: `tools/ci_candidate_unit.py` — запускается только при `GITHUB_ACTIONS=true`, root euid, cgroup v2, Python 3.12, исключительно на disposable GitHub runner. Не установщик, не VPS, не production acceptance.

## Что проверено

Harness устанавливает реального nonroot кандидата под точный rendering systemd-юнита, выполняет сценарий (MCP initialize + 20 инструментов, синтетическое приватное объявление, нативное фото 12 МП, admission 429, таймаут тела 408, освобождение слота при разрыве, инъекция SIGSTOP → типизированный 504/reap, повторная загрузка, публикация по явному consent, карта/фото/withdraw, неверный public Host 421, перезапуск с сохранением ключа/списка/снятия) и собирает измерения cgroup v2 для группы юнита и его нативных потомков.

Измерения (наблюдения одного Actions прогона, не гарантия ёмкости конкретного VPS):

| Показатель | Значение | Порог/проверка |
|---|---|---|
| cgroup `memory.peak` | 180473856 bytes (~172.1 MiB) | `< 1 GiB` |
| cgroup CPU usage | 725968 microseconds | `> 0` |
| sampled tasks peak | 3 | `<= 64` |
| sampled native parallel peak | 1 | — |
| OOM kill | 0 | `== 0` |
| state logical bytes | 274526 | `< 64 MiB` |
| state allocated bytes | 286720 | `< 64 MiB` |
| native worker wall timeout | 8.01 s | `7 <= t < 16` |

Вывод harness: `fixture_capacity_bounds_only=true`, `vps_capacity_accepted=false`.

## Что это не доказывает

- Измерения на disposable Actions runner не доказывают достаточную ёмкость конкретного VPS; пороги `MemoryMax=1 GiB`/`TasksMax=64` остаются **предварительными review ceiling**, а не принятым VPS budget.
- Нет разрешения на запуск на VPS; persistent install/enable и HTTPS/external acceptance требуют отдельного одобрения владельца **и** специального пароля.
- Не проверены внешний HTTPS/Caddy, реальный MCP-клиент, пользовательская публикация, реальные ключи.
- Sampling может пропустить очень короткие пики; `memory.peak` — kernel-учёт памяти группы юнита, не сумма RSS по всему хосту и не cold-cache bound.

## Следующий gate

Persistent install/enable персистентного unit на VPS и HTTPS/external acceptance (G3) требуют отдельного owner-одобрения и специального пароля. Агент готовит только статические docs/чеклисты и не выполняет серверные операции.
