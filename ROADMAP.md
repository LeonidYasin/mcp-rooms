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
- Accepted source SHA: `e6116aeff40d0128de90e36ab1b4045d2f8082e1`.
- Evidence: [F3c.2d.1](docs/ci-f3c2d1.md).
- 2026-10-22: первый read-only preflight на VPS — STOP по памяти
  ([отчёт](docs/preflight-vps-2026-10-22.md)); seccomp-проверка исправлена в CI.
- 2026-10-22: после апгрейда до 4 GiB повторный preflight — PASS
  ([отчёт](docs/preflight-vps-2026-10-22-4gb.md)); установка не выполнялась.
- 2026-10-22: `x-ui.service` (3x-ui-панель и managed Xray VPN) добавлен в
  дефолтный protected-набор preflight; установка не выполнялась.
- 2026-10-22: базовая alpha принята владельцем и объединена в `main` (линейная история,
  SHA `7c1bd3b9…`); тег/релиз/production не созданы.
- 2026-10-22: F3c.2d принят владельцем и смержен в `main`
  ([PR #3](https://github.com/LeonidYasin/mcp-rooms/pull/3), merge commit `4f08f0ab…`);
  тег/релиз/production не созданы.

## Сейчас: первый fresh owner-first TEST

### Gate A — документация и exact-SHA closure

- [x] Сверить remote branches и HEAD.
- [x] Зафиксировать F3c.2c.3b как принятый CI source SHA.
- [x] Обновить состояние, карту, граф и roadmap.
- [ ] Дождаться успешных Actions на docs-коммите и записать docs HEAD отдельно.

### Gate B — read-only VPS preflight

Требует отдельного разрешения и специального пароля.

- [x] Read-only инструмент `tools/operator_preflight.py` принят в CI ([F3c.2d.1](docs/ci-f3c2d1.md)); на VPS не запускался.
- [x] Первый прогон на VPS выполнен ([отчёт](docs/preflight-vps-2026-10-22.md)): STOP по памяти (1.18 GiB < 2 GiB floor); установка не выполнялась.
- [x] Повторный прогон после апгрейда до 4 GiB — PASS ([отчёт](docs/preflight-vps-2026-10-22-4gb.md)); установка не выполнялась.
- [ ] Проверить trusted `/usr/bin/python3.12`, Linux x86_64, cgroup v2 и Landlock/seccomp.
- [ ] Проверить свободные новые user/group/unit/paths/port без изменения хоста.
- [ ] Проверить RAM, disk, inode и filesystem ancestor safety.
- [ ] Проверить отсутствие конфликта с существующими MCP/Caddy/services.
- [ ] Сохранить только sanitized result; никаких ключей/config snapshots в Git.

### Gate C — isolated loopback TEST

Требует отдельного разрешения.

- [ ] Установить exact accepted artifact в новые fixed paths.
- [ ] Отдельно авторизовать bootstrap disposable owner key.
- [ ] Запустить только loopback.
- [ ] Выполнить synthetic MCP draft → upload → preview → consent → publish → GET → withdraw.
- [ ] Проверить restart/state preservation, resource measurements и stop-only rollback.
- [ ] Не использовать старую Rooms TEST DB и не менять Caddy.

### Gate D — temporary HTTPS/external MCP acceptance

Требует нового отдельного разрешения.

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
- [ ] Никакого переименования shared Rooms в «приватный чат».

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
