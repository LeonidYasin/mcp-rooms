# Минимальный production на VPS — пакет готовности (только статика, без выполнения)

Статус: **подготовлен к ревью владельца**. Документ не является разрешением и не содержит выполненных на VPS операций. Каждый серверный шаг требует отдельного одобрения владельца **и** специального пароля; агент не выполняет SSH/VPS/Caddy/systemd.

Принятый application source SHA: `db32c6ddf8f3b57874180dce81908e0d43aaa2f0` (не менялся с момента принятия). Pre-release `operator-wheelhouse-db32c6d` — не production.

## Готовность по воротам (честная картина)

| Gate | Содержание | Статус |
|---|---|---|
| G1 | Код + CI (принятый source `db32c6d…`) | Принято |
| G2 | Изолированный loopback TEST на VPS | Принято 2026-10-23 |
| G3 | HTTPS/external acceptance (узкий `/rooms` route) | Подготовлен чеклист; не разрешён |
| G4 | Персистентный unit + boot-enable | Код+CI proof приняты (PR #12); install/enable на VPS — owner-шаг |
| G5 | Backup/restore, ключи, мониторинг, runbook | Runbook подготовлен; off-host backup/шифрование/retention/алертинг открыты |
| G6 | Release/production rollout | Решение владельца; не начато |

## Точная последовательность owner-шагов на VPS (без агента)

Каждый пункт — отдельное одобрение владельца и специальный пароль; агент готовит только docs/скрипты, не выполняет.

1. **Fresh read-only VPS preflight** — `tools/operator_preflight.py` (доверенный python3.12, Linux x86_64, cgroup v2, Landlock ABI≥3, seccomp, отсутствие candidate account/unit/path/port, безопасность предков, свободное место на диске, защищённые units). Только санитизированный JSON в отчёт.
2. **Persistent install** — pinned pre-release bundle, `operator_install.py install --persistent --source-sha db32c6d… --lock-sha256 <lock> --resource https://leonid-mcp.duckdns.org/rooms/mcp`. Рендерит персистентный unit (`Restart=on-failure`, `RestartSec=5s`, без `RuntimeMaxSec`, `[Install] WantedBy=multi-user.target`), записывает `"persistent": true` в ready-last receipt, не создаёт профиль, не запускает, не включает в boot.
3. **Inspect** — `operator_install.py inspect` (сверка release/unit/receipt/state, без изменений).
4. **Bootstrap** — `operator_control.py bootstrap --authorization CREATE-FRESH-OWNER-PROFILE` (создаёт fresh owner-профиль, синтетический ключ с ограниченным TTL, ключ не печатается).
5. **Start** — `operator_control.py start --authorization START-OWNER-FIRST-CANDIDATE` (capacity check + systemd start + готовность; не включает в boot).
6. **Boot-enable** — `operator_control.py enable --authorization ENABLE-OWNER-FIRST-CANDIDATE` (только `systemctl enable`, unit остаётся inactive; требует `persistent: true` в receipt).
7. **HTTPS/external acceptance (G3)** — узкий временный Caddy route `/rooms` → `127.0.0.1:8766` через `tools/operator_route.py --plan/--open/--remove`, external MCP без токена `401`, авторизованный flow с отдельно одобренным test credential (bootstrap-ключ TTL 1ч не переиспользуется), одна реальная карточка только с явным consent владельца, затем удаление route, остановка, санитизированный отчёт.
8. **Production decision** — отдельное решение владельца о release/теге/rollout с rollback; нет автоматического переключения.

## Что остаётся открытым (блокирует «минимальный production»)

- Off-host backup и проверенный disaster-recovery cutover (реcovery output в карантине, без авто-promotion).
- Шифрование/защита backup, правила retention, хранение вне хоста.
- Алертинг и сбор метрик (в runbook только ручные проверки).
- Правила выпуска реальных ключей, отзыв, ротация, онбординг.
- Внешний HTTPS/Caddy route и real card с реальными фото (требует отдельного consent).
- Неизмеренная на конкретном VPS ёмкость: Actions-измерения (peak ~172 MiB < 1 GiB, tasks ≤ 64, OOM 0) — fixture bounds, не VPS acceptance.

## Evidence (точные SHA)

- `docs/ci-f3c2c3c.md` — aggregate capacity в Actions (run 121 Operator offline package).
- `docs/operator-supervision.md` — real systemd proof персистентного policy (PR #12).
- `docs/production-runbook.md` (PR #11) — инвентарь, предусловия, backup/restore, ротация ключей, мониторинг минимум, инцидент/откат.
- `docs/https-external-checklist.md` — G3 чеклист.
- `docs/owner-first-vps-test-2026-10-23.md` — loopback TEST evidence.

## Grenzen (что не входит в минимальный production пока)

Web-запись, форма, кабинет, cookie-authorized market/media, общий feed/search, приватные отклики, отдельный admin MCP, полный публичный пилот, реальная продажа. Default CLI остаётся rooms-only.
