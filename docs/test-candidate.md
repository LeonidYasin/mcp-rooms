# F2 — fresh owner-first TEST candidate, не VPS installer

Срез продолжает [сокращённый маршрут](owner-first-test.md): один владелец управляет
объявлением через MCP/Bearer HTTP, посетитель читает только опубликованную карточку.
**Код и CI-кандидат, не разрешение на серверную операцию.** Сейчас никакие реальные
пользователи/ключи не создаются, VPS/Caddy/unit/main не меняются.

[Exact-SHA F2 CI acceptance](ci-f2.md):686 tests на3.12 плюс installed-wheel native smoke.
Это исторический F2 baseline, не серверная установка. Текущий candidate дополнен
обязательной [F3a OS policy](media-sandbox.md), SOURCE до exact-SHA CI.

## Отдельный профиль вместо старого installer

Entrypoint `mcp-rooms-test-candidate`; исходник `src/mcp_rooms/test_candidate.py`.
Это отдельный opt-in CLI. `mcp-rooms` по-прежнему rooms-only. Не использовать прежние
rooms-only rollout scripts, сохранившуюся БД или unit `mcp-rooms-test.service` как
marketplace install target. Будущий профиль требует другого пользователя/root/unit
и свободного порта после отдельно разрешённого свежего preflight.

Три операторских действия, не MCP tools:

| Действие | Поведение |
| --- | --- |
| `bootstrap --state ABSOLUTE_NEW_ROOT --resource CANONICAL_HTTPS_MCP` | Только новый каталог в существующем owner-only0700 parent. Явно создаёт новую БД/схемы и одного synthetic/test owner; один listings-only ключ в `owner.key`0600. Не stdout. |
| `check --state ROOT --resource SAME_RESOURCE` | Проверяет private paths, marker/schema/fingerprint/DB integrity read-only, без credentials read/выдачи/repair и без native decoder. |
| `serve --state ROOT --resource SAME_RESOURCE` | Linux Python>=3.11 + Pillow13.0.0; фиксированный loopback127.0.0.1:8766, один процесс/decoder/upload, access logging off, proxy headers off. Требует готового профиля. Не ставит systemd, Caddy, HTTPS или таймер. |

**Это спецификация интерфейса для CI/будущего reviewed operator package, не просьба
выполнить команды на VPS сейчас.** Для каждой удалённой операции нужны отдельные
подтверждение и специальный пароль владельца. Новое24h окно не открывается этим кодом.

## Состояние и граница доверия

- Root и непосредственный parent/photos directory: абсолютные canonical пути,
  owner UID, mode0700, без symlink/alias. `market.sqlite3`, `profile.json` и
  `profile.lock`: regular, owner UID,0600,single-link, bounded size.
- Marker `mcp-rooms/owner-first-test/v1`, schema1: только profile/schema/resource/
  schema_hash. Exact resource binding, strict duplicate/unknown/future fields.
- SQLite application_id MCRR, base user_version2, page4096/WAL, market2/media3/
  publication1; ровно ожидаемые таблицы плюс sqlite_sequence; fingerprint всего
  sqlite_schema (tables/indexes/triggers/views), quick_check и foreign_key_check.
  Несовпадение/partial/legacy namespace — отказ, **не миграция**.
- Marker — локальный operator-controlled metadata, не подпись поставщика. Attacker
  с тем же UID/root может переписать и БД, и marker; от него эта проверка не защищает.
  Это не проверка provenance пакета и не замена SHA/checksum artifact.
- `RoomStore(..., initialize=False)` открывает только существующую корректную base2
  БД без create/chmod/DDL/v1 migration. Операционные соединения используют mode=rw,
  а не mode=create; удалённый файл не создаётся заново. Default old initializer
  совместим и используется только в явном fresh bootstrap. Marketplace startup
  сначала проверяет профиль read-only, затем открывает этот existing-only store.
- Существующие WAL/SHM до SQLite open проверяются как owner-only0600 regular
  single-link bounded files; aliases/shared files отвергаются. Наличие rollback
  journal требует явного разбора, не скрытого startup recovery.
- Read-only validation может открыть обычные SQLite WAL/SHM sidecars; отсутствие
  DDL/изменения данных не означает гарантированно ноль файловой активности/atime.
  Root закрыт от чужих UID; hostile same-UID replacement остаётся вне модели.
- `profile.lock` nonblocking flock удерживается до закрытия Candidate; второй
  cooperating process для этого же root получает отказ. Копии root/другие hosts
  не образуют общий fleet lock. Unit ещё нужно ограничить отдельно.

## Явный bootstrap / не скрытая регистрация

Fresh mkdir/O_EXCL отказывается от любого существующего root, включая failed
попытку или symlink. Нет delete-tree, автоматического retry/reuse/repair.
Схемы создаются только здесь, затем один owner и ключ с тремя минимально нужными
scopes: listings:read/write/publish, **без rooms/admin**. TTL в этом техническом
кандидате фиксирован3600s. Delegation не продлевает родителя. Порядок TTL/renewal/
безопасной доставки реального ключа нужно согласовать до более длинного пилота;
сейчас проверки используют только synthetic credentials в Actions.

Raw key возвращается только в приватный `owner.key`0600, не в JSON/stdout/marker/
артефакт GitHub. После безопасного получения оператором delivery file нужно убрать
из runtime root отдельно; compose/check его вообще не читают и не требуют.
ОС-изоляция decoder должна запретить доступ к state/key и сети перед VPS TEST.

Ready marker записывается последним после fsync файла ключа/БД и lock file. При
ошибке доставки/final marker sync: убрать marker, независимо попытаться revoke
ключ и disable нового owner. Ошибка одной компенсации не пропускает другую;
`candidate_bootstrap_recovery_required` означает ручной разбор, не успешный rollback.
Остатки остаются закрытыми для осмотра; нет автоматического удаления БД. При отказе
storage компенсации не гарантируются, остаются fallback TTL и запрет запуска без
valid marker. Storage не должен становиться публичным даже на время recovery.

## Фиксированная runtime composition

Trusted same-store/resource DraftStore → PrivatePhotoFiles → MediaStageStore →
PhotoDraftStore → PublicationStore → MarketAdapter. Никакого initialize() при serve,
реальной выдачи ключа или автоматического browser namespace. MediaHTTP upload slots1;
один reused PhotoWorker(max_parallel=1), default общего класса остаётся2. Только
эти два значения допускаются trusted code; пользователь не задаёт parallelism.

Registration выключена; нет browser session bridge/cookie writes. Discovery всё
ещё20 user tools (8rooms+12listings), но bootstrap ключу rooms-вызовы запрещены.
Отдельные admin tools/shell/SQL не добавляются. Все existing persisted authority,
resource/scopes/revoke/disable, photo bounds, consent v2, publication/withdraw guards
сохраняются. Public routes включены только в этой explicit композиции.

Loopback HTTP за будущим TLS proxy не интерпретируется как trusted browser HTTPS:
этот профиль не использует browser cookies вообще. Exact external resource/Host
binding и prefix-stripping proxy должны быть проверены отдельно. Нельзя включить
proxy_headers/доверие X-Forwarded-* без review и negative tests.

## CI и артефакты

`tests/test_test_candidate.py`: synthetic fresh profile, отсутствие startup DDL/
key read/issuance, bad schema/version/extra trigger/index/permissions/links/resource,
no repair/recreate, failure compensation, single profile/process/worker/upload,
закрытая signup/cookie policy, scope и live revoke checks.

`tools/ci_candidate_smoke.py` запускается Actions **из /tmp после установки wheel**:
реальный native normalize синтетического PNG → HTTP upload → MCP attach/preview/
consent/publish → anonymous HTML/JPEG decode → withdraw404. Скрипт проверяет, что
импортирован установленный пакет вне checkout. Это in-process ASGI, не сетевой
HTTPS или браузерная проверка. Python3.10 сохраняет core tests, candidate native
smoke требует>=3.11. Локально приложение и тесты не исполняются.

Python3.12 job загружает wheel/sdist/SHA256SUMS в artifact с именем exact GITHUB_SHA,
retention14days. Нет key/DB/photos/state/logs в uploaded paths. Это integrity evidence
сборки, **не подпись**, не release и не воспроизводимый lock всех транзитивных
зависимостей. Установочный dependency lock/offline wheelhouse, provenance проверка
на стороне оператора и reviewed install/stop/rollback script ещё не закрыты.

## Следующий bounded gate F3a и оставшиеся F3b/F3c

Пока **нельзя называть этот кандидат готовым к VPS TEST**. Следующий отдельный
кодовый срез F3a (пункт1 ниже) подготовлен, ожидает Actions. Остальные пункты остаются F3b/F3c, не
должны теряться или запускаться на VPS автоматически. Нужны:

1. [F3a Landlock/seccomp child](media-sandbox.md): отдельно проверить, что он
   не читает parent state/owner.key/БД и не имеет network. RLIMIT/isolated Python —
   не такая sandbox. Root-only systemd ограничения не считаются существующими.
2. Один worker всё ещё имеет RLIMIT_AS512MiB; подобрать общий MemoryMax/CPU/Tasks/
   disk budget по свежим данным VPS и нагрузочным/timeout/kill fixtures. Не копировать
   старый unit MemoryMax256M и не объявлять проблему RAM решённой одним semaphore.
3. Согласованный DB+files snapshot/restore, reconciliation отозванных ключей и disabled
   users, отсутствие public exposure восстановленной копии; reviewed retention.
4. Закреплённый dependency/install manifest и проверяемый operator package с dry-run,
   fresh target refusal, health/stop/rollback, no secrets in stdout/logs; без исполнения
   на VPS. Затем отдельное разрешение на preflight и установку, затем HTTPS-проверки.

Полный browser/search/private-replies/admin проект не отменён. M3b.3 paused и
обязателен до любого cookie-authorized editing. См. [handoff](ai-handoff.md),
[work-state](work-state.json), [общий маршрут](deployment-readiness.md).
