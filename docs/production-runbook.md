# Runbook эксплуатации кандидата (подготовлен, не исполнялся)

Статус: **подготовлен**. Документ описывает проверяемые шаги для уже принятого
кандидата `db32c6d…`. Он не является разрешением: каждая серверная операция требует
отдельного одобрения владельца **и** специального пароля, а root-команды выполняет
только владелец на своей консоли.

Что этот runbook **не** даёт: production approval, SLA, гарантию восстановления без
исходной authority, off-host копии, шифрование backup, алертинг, измеренную ёмкость
под нагрузкой и правила выпуска реальных ключей. Ниже эти дыры перечислены явно.

## 1. Инвентарь того, что реально есть

| Возможность | Инструмент | Что делает | Чего не делает |
| --- | --- | --- | --- |
| Read-only проверка хоста | `tools/operator_preflight.py` | смотрит память, диск, cgroup, Landlock/seccomp, занятость порта/путей, protected units | ничего не пишет и не запускает |
| Установка | `tools/operator_install.py install` | fresh-only, pinned hashes, root-owned release, unit + ready-last receipt | не создаёт профиль, не стартует, не включает |
| Инспекция | `tools/operator_install.py inspect` | сверяет release/unit/receipt/state | не меняет состояние |
| Профиль | `operator_control.py bootstrap` | создаёт fresh owner-профиль и синтетический ключ | не печатает ключ, TTL ограничен |
| Запуск | `operator_control.py start` | capacity check + `systemctl start` + готовность | не включает в boot |
| Остановка | `operator_control.py stop` | останавливает только этот unit, state сохраняется | не удаляет данные |
| Boot-enable | `operator_control.py enable/disable` | только `systemctl enable/disable`, unit остаётся inactive | не стартует и не перезапускает |
| Маршрут | `tools/operator_route.py` | один CAS-маршрут `/rooms` → `127.0.0.1:8766` или его удаление | не правит Caddyfile и чужие маршруты |
| Backup/restore | `mcp-rooms-recovery snapshot/restore/verify` | офлайн-снимок DB+derived photos в **новую** директорию | не копирует на другой хост, не шифрует, не подменяет live |
| Ключи | `docs/identity.md` | выпуск/отзыв/ротация Bearer | без авто-восстановления утерянных ключей |

## 2. Предусловия на каждую операцию

1. Отдельное «да» владельца именно на этот шаг и специальный пароль по согласованному
   каналу. Пароль не попадает в Git, чат, shell history или логи.
2. Известен точный принятый source SHA (`db32c6d…`) и pinned lock/bundle hash.
3. Известно текущее состояние: `systemctl is-active`/`is-enabled`, listener на 8766,
   свободное место, MemAvailable.
4. Есть свежий backup (см. §4) **до** любых изменений, кроме первого install.
5. Понятен план отката: остановка, восстановление в новый путь, решение о
   переключении. Автоматического promotion нет.

## 3. Штатный запуск после перезагрузки хоста

`enable` создаёт boot-включение, но unit при загрузке поднимется только если
persistent-режим реально принят и установлен. Проверка после ребута — read-only:

```sh
systemctl is-enabled mcp-rooms-candidate    # PASS: enabled
systemctl is-active mcp-rooms-candidate     # PASS: active
ss -ltn | grep ':8766'                      # PASS: 127.0.0.1:8766 only
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8766/mcp   # PASS: 401
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8766/      # PASS: 404
```

Если unit не поднялся — STOP и разбор причины. Не «чинить» перезапусками и не
переустанавливать поверх существующих путей: installer намеренно отказывается
работать с существующим target.

## 4. Backup (офлайн, только с остановленным сервисом)

```sh
systemctl stop mcp-rooms-candidate          # отдельное разрешение
mcp-rooms-recovery snapshot --source <state-dir> --current <state-dir> \
    --destination /var/backups/mcp-rooms-<date> --resource https://leonid-mcp.duckdns.org/rooms/mcp
mcp-rooms-recovery verify --source /var/backups/mcp-rooms-<date> \
    --resource https://leonid-mcp.duckdns.org/rooms/mcp
```

PASS: `verify` успешен, манифест создан последним, директория owner-only, размеры в
лимитах (DB ≤64 MiB, ≤256 derivatives/32 MiB). STOP: любой отказ, частичный каталог
без ready-маркера, занятый lock, непустой WAL, orphan-ссылки.

Важно: снимок содержит **чувствительные данные и digest'ы credential'ов**. `0600`
не означает «зашифровано». Копию нельзя класть в Git, публичный artifact или
незащищённое облако.

**Дыра:** репозиторий не делает off-host transfer и не расписывает retention.
Пока владелец не решит, где хранится копия вне хоста, disaster recovery после потери
хоста не закрыт.

## 5. Restore (только в новый каталог)

```sh
mcp-rooms-recovery restore --backup /var/backups/mcp-rooms-<date> \
    --current <current-state-dir> --destination <new-state-dir> \
    --resource https://leonid-mcp.duckdns.org/rooms/mcp
```

PASS: восстановление в новую директорию, `verify` проходит, current authority
сужается по правилам recovery. STOP: `--current` недоступен/не совпадает, целевой
путь существует, лимиты нарушены.

Переключение на восстановленную директорию — отдельное решение владельца: live-путь
не подменяется автоматически, quarantined-выход не промоутится сам.

## 6. Ротация и отзыв ключей

Порядок из `docs/identity.md`: выпустить новый ключ тому же пользователю →
подключиться и проверить → явно отозвать старый. Отзыв действует на новые запросы;
уже принятые in-flight запросы не отменяются. Утерянный ключ не восстанавливается —
его нужно идентифицировать по метаданным и отозвать. Ключи не печатать в чат, URL,
логи и не переиспользовать синтетический bootstrap-ключ.

## 7. Мониторинг минимума

| Что | Порог/сигнал | Действие |
| --- | --- | --- |
| `MemoryMax` | 1 GiB, `MemorySwapMax=0` | рост → проверить утечки/нагрузку, не поднимать лимит вслепую |
| `TasksMax` | 64 | приближение → разбор, а не «+100» |
| Диск state | свободно ≥4 GiB (floor preflight) | ниже — STOP, снимок и разбор |
| Unit | `active`, без `failed` | `failed` → stop, сохранить состояние, разбор |
| Внешний MCP без токена | `401` | иначе STOP: маршрут/конфигурация изменились |
| Логи | без Authorization/секретов | утечка → ротация ключей и разбор |

Алертинга в проекте нет: это ручные проверки. Отсутствие алертов — известная дыра.

## 8. Инцидент и откат

1. Остановить только кандидат (`stop`), state сохранить.
2. Не перезапускать «на всякий случай» и не переустанавливать поверх.
3. Снять/не трогать маршрут в зависимости от риска: `operator_route.py --remove`.
4. Собрать sanitized-факты: коды ответов, состояние unit, время, SHA.
5. Восстановление — из проверенного снимка в новый путь (§5), затем решение владельца.
6. Секреты в отчёт не попадают.

## 9. Что остаётся до production

- off-host backup и проверенный disaster recovery cutover;
- шифрование/защита backup и правила retention;
- алертинг и сбор метрик;
- измеренная ёмкость под нагрузкой (RSS/peak, конкурентность, диск);
- правила выпуска реальных ключей и онбординга;
- HTTPS/external acceptance по [чеклисту](https-external-checklist.md);
- решение владельца о release/теге и rollout с rollback.

Пока эти пункты открыты, кандидат остаётся TEST-кандидатом, даже если unit
persistent, включён в boot и доступен по HTTPS.
