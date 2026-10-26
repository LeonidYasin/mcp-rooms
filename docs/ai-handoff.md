# AI handoff — как продолжить MCP Rooms

## Сначала прочитать

1. `AGENTS.md` — обязательные ограничения и permission gates.
2. `docs/current-state.md` — понятное состояние продукта и кода.
3. `docs/work-state.json` — exact accepted source SHA и следующий gate.
4. `docs/project-map.md` и `docs/architecture-graph.md`.
5. `ROADMAP.md` и документ текущего контракта/evidence.

Прошлый чат не является источником истины. Всегда сначала проверить remote branch HEAD,
PR и Actions. Docs-коммит может быть новее принятого application source SHA.

## Продукт

MCP Rooms — MCP-first площадка «Хочу / Предлагаю». Основной интерфейс пользователя —
чат со своим ИИ-агентом. Агент по явному поручению использует MCP tools над общими
application services. Web ближайшего этапа — анонимная витрина только для просмотра
явно опубликованных карточек и фото.

Не превращать web в основной write path до отдельного решения. Не добавлять формы,
cookie-authorized writes или broad signup в короткий owner-first TEST. Cookie session
core существует, но M3b.3 transaction-time authority остаётся paused до browser writes.

## Принятое состояние

- Branch: `feat/standalone-identity`; PRs #1–#6 merged into `main` by separate owner
  approvals (2026-10-22/24), then #12–#15 (operator/capacity/production-readiness docs)
  and #17 (web card author context). `main` is at
  `b4034f1ee9f3da9abbc75eee28540e1cbe3da915`; pre-release
  `operator-wheelhouse-db32c6d` exists, but there is no production deploy.
- Accepted application source SHA: `db32c6ddf8f3b57874180dce81908e0d43aaa2f0`.
- Evidence: `docs/ci-f3c2d2.md` and
  `docs/owner-first-vps-test-2026-10-23.md`.
- Python 3.10–3.13 CI, build/install smoke, operator systemd supervision and
  installed-wheel native smoke successful.
- Fresh isolated owner-first VPS TEST 2026-10-23: public pre-release bundle verified;
  install/inspect, separate bootstrap, loopback start, synthetic MCP
  publish/read/withdraw, stop-only rollback and restart + second synthetic flow all
  PASS. MCP without token `401`, web root `404`; only `127.0.0.1:8766`.
- No Caddy/HTTPS change, no real listing/photo, no real credential, no production.
  The synthetic owner key had a 3600s TTL and is not reusable.
- Новые изменения идут через `feat/standalone-identity` и отдельные owner-approved
  PR в `main`; merge требует отдельного решения владельца.
- Старый Rooms TEST остановлен; production MCP Rooms отсутствует.
- **Единый каталог, Фаза 1 (PR #29, смержен в main `6eb1004`)**: `topics` — единый каталог
  (`root`/`active` + market listing-поддерево под `market`, валидатор `RoomStore._topic`),
  аддитивно; `market_categories` не менялся. CI green на 979b759 (3.10: 1031 passed, 42 skipped;
  3.11–3.13: 1092 passed).
- **Единый каталог, Фаза 2 (PR #30 open, owner merge pending)**: все чтения marketplace-категорий
  переведены с `market_categories` на единый `topics` (`DraftStore._category`/`categories()`/`_preview`,
  `PhotoDraftStore._document`, `recovery`). Поведение сохранено: category_path останавливается на
  семантическом корне (`id==root`) — пути карточек и веб-секции прежние; top-level броуз =
  listing-корни (`['services','things']`). `market_categories` остаётся созданным/сидимым как legacy-FK.
  CI green на cf28f5e (test 3.10–3.13, build, supervision, wheelhouse pass; deploy owner-gated).
  Фаза 3 (удаление `market_categories`/candidate `REQUIRED`, депрекейт, перенос FK
  `market_drafts.category_id` на `topics`) — последующий срез.

## Следующий gate

Проверено в CI: **F3c.2c.3c real systemd proof персистентного unit** (PR #12) и **F3c.2c.3c aggregate capacity measurement** (docs/ci-f3c2c3c.md): no OOM kill, peak < 1 GiB, tasks <= 64, cpu > 0; `fixture_capacity_bounds_only=true`, `vps_capacity_accepted=false`.

Далее — только отдельным owner-разрешением: persistent install/enable персистентного unit на VPS и HTTPS/external acceptance. Точный пакет owner-шагов и открытые блокеры — в [docs/production-readiness.md](production-readiness.md).

HTTPS/external acceptance — только после нового отдельного разрешения:

1. узкий временный Caddy route: preserve Host, strip only `/rooms`, no broad auth bypass;
2. external MCP without token must return candidate `401`;
3. authenticated external flow requires a separately approved listing-scoped test
   credential or fresh profile/key gate. The loopback synthetic key had a one-hour
   TTL and must not be silently reused or reissued;
4. one real card with real photos and explicit owner consent for exact content;
5. external read-only web check without an agent; withdraw, route cleanup, stop and
   sanitized evidence.

До разрешения можно только проверить документацию/скрипты статически и подготовить
точный checklist. Нельзя самостоятельно выполнять remote probe.

## Нельзя без отдельного разрешения

- merge в main, release/tag или production rollout;
- VPS/SSH/Caddy/systemd execution, restart или reconfiguration;
- real credentials, live DB migration или TEST reopening;
- recovery promotion;
- secret/password в Git, chat или logs.

Каждая remote operation требует отдельного согласия владельца **и специального пароля**.

## Как выполнять следующий кодовый slice

1. Сверить remote HEAD и expected SHA; не force-push.
2. Выбрать один bounded task из `work-state.json`.
3. Прочитать contract/source/tests/evidence зависимостей.
4. Подготовить code + negative/failure/concurrency tests + docs.
5. Локально только static/AST; application/pytest/build — Actions.
6. Исправлять причину CI failure, не ослаблять тест.
7. После green exact source SHA обновить evidence, roadmap, registry и work-state.
8. Ясно отделить SOURCE, CI, TEST и PROD.

## Архитектурные ограничения

- Python/SQLite modular monolith; official MCP SDK.
- Default CLI остаётся rooms-only; marketplace — explicit opt-in composition.
- Actor всегда из проверенного credential/session, никогда из client JSON.
- Web public GET читает только allowlisted projection.
- Shared Rooms не являются private responses.
- Admin MCP — отдельная audience и typed operations, никогда shell/SQL/root.
- Media: no remote URL fetch, bounded decode, re-encode, private files.
- Recovery output остаётся quarantine без автоматического promotion.

## Paused, но обязательные задачи

- M3b.3 transaction-time browser session authority до browser writes.
- Independent disaster recovery/cutover при потере current authority.
- Private responses, admin MCP и full pilot readiness после owner-first TEST.
