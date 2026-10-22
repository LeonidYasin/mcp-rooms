# F3c.2d — fresh read-only VPS preflight tool: exact-SHA CI evidence

## Итог

Срез принят как **CI**, не как VPS TEST и не как production. Инструмент ни разу
не запускался на реальном VPS.

- Source SHA: `01d2a93821639efa1a4ad3ab0ca14a2483e4821c`
- Branch: `feat/standalone-identity`
- CI workflow run: `39793266701`
- Operator supervision run: `39793266538`
- Operator offline package run: `39793266579`
- Documentation Pages run: `39793266751`

## Что проверено

- Python 3.10–3.13 jobs успешны; в Python3.12 логе **990 passed, 2 warnings**
  (известные dependency warnings, не подавлены).
- `tools/operator_preflight.py` — root-only operator console, read-only: не пишет,
  не устанавливает, не стартует, не перезапускает сервисы, не читает Caddy
  config, БД, ключи или private logs.
- Проверки: trusted canonical `/usr/bin/python3.12` (плюс probe версии 3.12),
  Linux x86_64, cgroup v2, Landlock ABI≥3 через version syscall, требуемые
  seccomp filter actions, отсутствие кандидатных account/group, candidate и build
  units, release/state путей и control-lock каталога, свободный порт8766
  (только LISTEN-записи `/proc/net/tcp{,6}`), безопасные canonical ancestors,
  floors MemAvailable2GiB / install FS2GiB / state FS4GiB /65536 inodes,
  LoadState/ActiveState/SubState/MainPID выбранных защищённых units без чтения
  их конфигурации.
- Sanitized JSON и typed STOP-коды; неожиданные ошибки дают
  `preflight_review_required` без деталей исключения.
- Tests покрывают каждый отказ/порог, парсинг listeners, Landlock/seccomp,
  root-отказ до наблюдений и коды выхода без раскрытия приватных деталей.

## Найденный и исправленный дефект

На `73114d6` новый тест `test_capacity_observation_failure_is_typed` падал:
fixture подменяла `_available_memory`, поэтому ветка с отсутствующим
`/proc/meminfo` не исполнялась. Исправление `01d2a93` — только тестовое:
разделены проверки `_available_memory` (нет MEMINFO) и `_capacity` (сбой
statvfs). Production-код не менялся, проверки не ослаблены; первый красный
прогон сохранён в истории Actions.

## Что это не доказывает

- Фактические VPS-значения (python, cgroup, Landlock, seccomp, память, диск,
  порт) этим срезом не измерены: на VPS инструмент не запускался.
- PASS preflight не разрешает install/bootstrap/loopback/HTTPS и не подтверждает
  ёмкость или устойчивость конкретного хоста.
- Нет реальных ключей, БД, Caddy config, профиля или пользовательской публикации.
- Нет разрешения на merge/release/production.

## Следующий gate

`OWNER-FIRST-VPS-PREFLIGHT`: отдельное разрешение владельца и специальный пароль,
затем pinned вызов инструмента, sanitized report и STOP. Install — отдельное
следующее разрешение; loopback и HTTPS — ещё отдельные gates.
