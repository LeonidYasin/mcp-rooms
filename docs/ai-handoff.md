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

- Branch: `feat/standalone-identity`, PR #1 draft.
- Accepted application source SHA: `88eabfb35aa7cc763d85352e3e67a48e9d5fb97f`.
- Evidence: `docs/ci-f3c2c3b.md`.
- Python 3.10–3.13 CI, build/install smoke и operator systemd supervision successful.
- Guarded lifecycle controller реализован; это CI, не VPS TEST.
- `main` остаётся scaffold до отдельного merge-решения.
- Старый Rooms TEST остановлен; production MCP Rooms отсутствует.

## Следующий gate

Fresh isolated owner-first TEST:

1. отдельно разрешённый read-only VPS preflight;
2. отдельно разрешённая fresh loopback install/bootstrap/start/synthetic acceptance;
3. отдельно разрешённый временный HTTPS и external MCP acceptance;
4. одна реальная карточка с реальными фото и явным согласием;
5. withdraw, cleanup и evidence.

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
