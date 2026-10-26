# MCP Rooms — понятный roadmap

## Направление продукта

MCP Rooms — MCP-first площадка «Хочу / Предлагаю».

- Основная работа пользователя: чат со своим ИИ-агентом → MCP-инструменты площадки.
- Web ближайшего этапа: витрина только для чтения опубликованных карточек и фото.
- Web-редактирование, каталог, приватные отклики и модерация появятся позже и не
  блокируют первый owner-first TEST.

Текущее состояние: [понятная сводка](docs/current-state.md),
[карта проекта](docs/project-map.md), [граф](docs/architecture-graph.md),
[machine-readable state](docs/work-state.json).

## Уже завершено

### 1. Rooms и identity — TEST/CI

- UUID users без обязательного GitHub/email/телефона.
- Digest-only Bearer credentials, scopes, revoke/disable/expiry.
- 8 Rooms MCP tools.
- Исторический Notion ↔ Qwen TEST принят и затем остановлен.

### 2. Marketplace core — CI

- Private drafts, categories, revision CAS и idempotency.
- Photo normalize, sandbox, files, staging, attachment и cleanup.
- Exact preview и version-bound consent.
- Publish/withdraw/public projection.
- 12 opt-in listing MCP tools поверх общих application services.

### 3. Read-only web-витрина — CI

- Анонимная HTML-карточка и опубликованные JPEG.
- Allowlist public fields, escaping, CSP/no-store и withdrawal recheck.
- Нет форм, feed/search, cookie writes или скрытых полномочий.

### 4. Owner-first operator candidate — CI

- Fresh candidate, recovery quarantine и hash-pinned wheelhouse.
- Root-trusted fresh-only install/inspect без запуска.
- Fixed systemd unit/cgroup и реальный candidate/native fixture в Actions.
- Guarded capacity/bootstrap/start/stop controller.
- Read-only fresh VPS preflight tool (`tools/operator_preflight.py`; один read-only прогон на VPS, без установки).
- Accepted source SHA: `db32c6ddf8f3b57874180dce81908e0d43aaa2f0`.
- Evidence: [F3c.2d.2](docs/ci-f3c2d2.md).
- 2026-10-22: первый read-only preflight на VPS — STOP по памяти
  ([отчёт](docs/preflight-vps-2026-10-22.md)); seccomp-проверка исправлена в CI.
- 2026-10-22: после апгрейда до 4 GiB повторный preflight — PASS
  ([отчёт](docs/preflight-vps-2026-10-22-4gb.md)); на тот момент установка не выполнялась.
- 2026-10-22: `x-ui.service` (3x-ui-панель и managed Xray VPN) добавлен в
  дефолтный protected-набор preflight; на тот момент установка не выполнялась.
- 2026-10-22: базовая alpha принята владельцем и объединена в `main` (линейная история,
  SHA `7c1bd3b9…`); тег/релиз/production не созданы.
- 2026-10-22: F3c.2d принят владельцем и смержен в `main`
  ([PR #3](https://github.com/LeonidYasin/mcp-rooms/pull/3), merge commit `4f08f0ab…`);
  тег/релиз/production не созданы.
- 2026-10-22: seccomp-исправление и первый VPS preflight смержены
  ([PR #4](https://github.com/LeonidYasin/mcp-rooms/pull/4), merge commit `fd2f616…`);
  тег/релиз/production не созданы.
- 2026-10-23: `x-ui` protected default и 4 GiB preflight PASS смержены
  ([PR #5](https://github.com/LeonidYasin/mcp-rooms/pull/5), `main` = `2586843…`);
  опубликован offline pre-release `operator-wheelhouse-db32c6d`.
- 2026-10-23: fresh isolated loopback TEST на VPS — install/bootstrap/start,
  synthetic MCP publish/read/withdraw, stop-only rollback и restart + повторный
  flow PASS ([evidence](docs/owner-first-vps-test-2026-10-23.md)). Caddy/HTTPS,
  реальная карточка и production не принимались.
- 2026-10-24: loopback TEST evidence и handoff-состояние смержены
  ([PR #6](https://github.com/LeonidYasin/mcp-rooms/pull/6), merge commit
  `06031dbc…`); application source не менялся, тег/релиз/production не созданы.

## Сейчас: первый fresh owner-first TEST

### Gate A — документация и exact-SHA closure

- [x] Сверить remote branches и HEAD.
- [x] Зафиксировать F3c.2c.3b как принятый CI source SHA.
- [x] Обновить состояние, карту, граф и roadmap.
- [ ] Дождаться успешных Actions на docs-коммите и записать docs HEAD отдельно.

### Gate B — read-only VPS preflight

Требует отдельного разрешения и специального пароля.

- [x] Read-only инструмент `tools/operator_preflight.py` принят в CI ([F3c.2d.1](docs/ci-f3c2d1.md), [F3c.2d.2](docs/ci-f3c2d2.md)); `x-ui.service` входит в defaults.
- [x] Первый прогон на VPS выполнен ([отчёт](docs/preflight-vps-2026-10-22.md)): STOP по памяти (1.18 GiB < 2 GiB floor); на тот момент установка не выполнялась.
- [x] Повторный прогон после апгрейда до 4 GiB — PASS ([отчёт](docs/preflight-vps-2026-10-22-4gb.md)); на тот момент установка не выполнялась.
- [x] Проверить trusted `/usr/bin/python3.12`, Linux x86_64, cgroup v2 и Landlock/seccomp — подтверждено PASS-прогоном.
- [x] Проверить свободные новые user/group/unit/paths/port без изменения хоста — подтверждено PASS-прогоном.
- [x] Проверить RAM, disk, inode и filesystem ancestor safety — подтверждено PASS-прогоном.
- [x] Проверить отсутствие конфликта с существующими MCP/Caddy/services — подтверждено PASS-прогоном.
- [x] Сохранить только sanitized result; никаких ключей/config snapshots в Git — `docs/preflight-vps-2026-10-22-4gb.md`.

### Gate C — isolated loopback TEST

Выполнено 2026-10-23; evidence:
[owner-first-vps-test-2026-10-23.md](docs/owner-first-vps-test-2026-10-23.md).

- [x] Установить exact accepted artifact в новые fixed paths.
- [x] Отдельно авторизовать bootstrap disposable owner key.
- [x] Запустить только loopback.
- [x] Выполнить synthetic MCP draft → upload → preview → consent → publish → GET → withdraw.
- [x] Проверить restart/state preservation и stop-only rollback.
- [x] Снять runtime resource measurements (RSS/peak cgroup) — отдельный ops/HTTPS gate.
      Сделано в Actions через `tools/ci_candidate_unit.py` (no OOM kill, peak<1GiB,
      tasks<=64, cpu>0); это не VPS capacity acceptance.
- [x] Не использовать старую Rooms TEST DB и не менять Caddy.

### Gate D — temporary HTTPS/external MCP acceptance

Требует нового отдельного разрешения. Loopback synthetic key имел TTL 1 час;
после истечения нужен отдельно одобренный listing-scoped test credential или
fresh profile/key gate. Caddy всё ещё не менялся.

- [ ] Добавить узкий временный route с cleanup/manual fallback.
- [ ] Проверить реальный внешний MCP-клиент.
- [ ] Опубликовать одну настоящую карточку с реальными фото и явным согласием владельца.
- [ ] Проверить read-only web с устройства без агента.
- [ ] Снять публикацию, закрыть route/service и записать evidence.

**Оценка до owner-first внешнего TEST:** 1–2 недели при быстрых разрешениях;
до 3 недель при проблемах совместимости VPS/HTTPS. Это не production.

## После owner-first TEST

### E. Надёжное агентное использование — 1–2 недели

- [ ] Уточнить MCP UX: компактные typed ответы, понятные ошибки и recovery hints.
- [ ] Проверить реальные Notion/Qwen/другие клиенты на одинаковом listing flow.
- [ ] Least-privilege delegation/renewal без расширения signup scopes.
- [ ] Добавить документацию для владельца и безопасную передачу ключа.

### F. Browser write path — 2–3 недели

- [ ] M3b.3: проверять session authority внутри той же transaction, что market/media write.
- [ ] Доказать logout/revoke/expiry во время upload/native IO.
- [ ] Typed browser commands, CSRF, rate limits и bounded retention.
- [ ] Только после gate — форма черновика/фото. MCP остаётся основным интерфейсом.

### G. Каталог и поиск — 2–3 недели

- [ ] Read-only feed, категории, фильтры и поиск.
- [ ] Pagination, expiry/withdraw/moderation filtering.
- [ ] Mobile/accessibility/browser QA.
- [ ] Без фиктивных продавцов, рейтингов, спроса или продаж.

### H. Приватные отклики — 2–3 недели

- [ ] Отдельные response/conversation сущности.
- [ ] Participant ACL, retention и negative tests.
- [ ] p1 уведомление участника об обновлённом приватном ответе/сообщении: контент-безопасный
      `unread_messages` + read-метки тред-диалога (namespace v3, mark-on-read); CI pending.
- [ ] Никакого переименования shared Rooms в «приватный чат».

### O. Открытые/приватные комнаты + read-only веб-каталог (2026-10-25)

- [x] **Срез A (реализовано)**: комнаты получают `topic_id` + приватность (`private|open`),
      фикс при создании; базовый каталог тем в `RoomStore` (`topics` + `room_topics`,
      `rooms`/`user_version` не меняются); `rooms_create`/`rooms_list` расширены,
      `rooms_topics` — просмотр дерева (9-й rooms tool). Дизайн: docs/open-rooms-web.md.
- [x] **Единый каталог, Фаза 1 (реализовано)**: `topics` становится единым каталогом — добавлены
      `root` (явный в seed, бэкфилл) и `active` (default 1); market listing-поддерево
      (`things`→`home-repair`→`plumbing`→`toilets`, `services`) досеяно под `market`
      идемпотентной миграцией; общий валидатор `RoomStore._topic` (active/root-ancestry)
      задействован в `rooms_create` и броузинге. `market_categories` продолжает работать —
      поведение не меняется. PR #29, green на 979b759 (3.10: 1031+42; 3.11–3.13: 1092).
- [x] **Единый каталог, Фаза 2 (реализовано)**: все чтения marketplace-категорий переведены с
      `market_categories` на единый `topics` — `DraftStore._category`/`categories()`/`_preview`,
      `PhotoDraftStore._document`, `recovery` (источник из `topics`). Поведение сохранено:
      category_path останавливается на семантическом корне (`id==root`, путь карточки
      `['things','home-repair','plumbing','toilets']` и веб-секции прежние), top-level броуз =
      семантические listing-корни (`parent_id IS NOT NULL AND id=root AND active=1` → `['services','things']`).
      `market_categories` остаётся созданным/сидимым как legacy-FK до Фазы 3. PR #30, green на cf28f5e.
- [x] **Единый каталог, Фаза 3 (реализовано)**: `market_categories` удалена — `SCHEMA_VERSION` 3,
      `TABLES` без legacy-таблицы, `initialize()` не создаёт/сеет её и отвергает старые БД
      (`unsupported_market_schema`), FK `market_drafts.category_id` → `topics(id)`. Вариант 2:
      миграция v1→v2 и её 3 теста удалены осознанно (переносить нечего). candidate `REQUIRED`
      без `market_categories`, ожидаемая версия `market_schema` 3. PR #31, green на 5c1968e
      (3.10: 1028+42; 3.11–3.13: 1089; build/supervision/wheelhouse pass, deploy owner-gated);
      смержен в main `2652409`. Отказ legacy-БД (таблица `market_categories` ещё на диске)
      закреплён тестом `test_legacy_market_categories_database_refused_without_mutation`
      (PR #32, green на 0d329ea: 3.10 1029+42; 3.11–3.13 1090).
- [x] **Срез B (реализовано)**: read-only веб-витрина открытых комнат по дереву тем (`/rooms`, `/rooms/topic/<id>`); только `open`, приватные/legacy не раскрываются, весь текст escaped.
- [x] **Срез C (реализовано)**: read-only лента сообщений открытой комнаты (`/rooms/room/<id>` + `?cursor=`), bounded/kурсор, escaping, 404 на приватные/несуществующие.
- [x] **Срез D (реализовано статически)**: production-prep комнат в docs/rooms-web-production.md (композиция `public_rooms=True`, app-пути, коллизия префикса и рекомендация). Деплой — отдельный owner-gate + пароль.

### I. Отдельный admin MCP — 2–3 недели

- [ ] Отдельные principal/audience/credentials.
- [ ] Typed complaints/hide/restore/categories/disable и audit.
- [ ] Prepare/confirm для опасных действий.
- [ ] Никакого shell, Python, SQL, произвольных файлов или root.

### J. Полный pilot readiness — 3–5 недель

- [ ] Abuse/load/SQLite contention и измеренные VPS budgets.
- [ ] DB+files backup/restore и current revocation reconciliation.
- [ ] Off-host backup, monitoring, retention/exhaustion runbook.
- [ ] Privacy/prohibited-goods/moderation policy.
- [ ] Изолированный пилот с независимым участником.

### K. Минимальный production на VPS — подготовка (только owner-шаги)

- [ ] Пакет готовности: [docs/production-readiness.md](docs/production-readiness.md) (G1–G6, 증거, открытые блокеры).
- [ ] Fresh read-only VPS preflight — `tools/operator_preflight.py` (owner approval + пароль).
- [ ] Persistent install `operator_install.py install --persistent` из pinned pre-release `db32c6d…` (owner approval + пароль).
- [ ] `inspect`, `bootstrap` (CREATE-FRESH-OWNER-PROFILE), `start` (START-OWNER-FIRST-CANDIDATE).
- [ ] `enable` (ENABLE-OWNER-FIRST-CANDIDATE) — boot symlink, без старта; требует `persistent: true`.
- [ ] HTTPS/external acceptance G3 — узкий `/rooms` route `tools/operator_route.py`, отдельное одобрение + пароль.
- [ ] Санитизированный отчёт; решение о release/теге/rollout — отдельное решение владельца.

Ориентир до полноценного внешнего marketplace TEST: **10–16 недель** одного основного
разработчика с AI-поддержкой. До production после пилота: ещё **3–6 недель**, точнее —
только по фактическим результатам TEST.

## Отложено сознательно

- Полноценный disaster cutover без исходной current authority.
- Payments/escrow, доставка/такси, вакансии, команды, стартапы и инвесторы.
- Embeddings/LLM matching, PostgreSQL/Redis/microservices.
- Автономные действия агентов без явного поручения пользователя.

## Правила каждого этапа

1. Один bounded slice за раз.
2. Negative/failure/concurrency tests вместе с кодом.
3. Application execution и pytest — в GitHub Actions.
4. Exact source SHA, evidence и обновлённый handoff после green CI.
5. CI ≠ VPS TEST ≠ production.
6. Никаких secrets, реальных DB/фото/config snapshots в Git.
7. Merge/main/release/VPS/Caddy/real credentials — только по отдельному разрешению.
