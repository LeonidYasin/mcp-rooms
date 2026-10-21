# AI handoff — продолжить работу, прочитав только репозиторий

Это точка входа, не ещё одна история переписки. Начните с [AGENTS.md](../AGENTS.md)
и [машинного состояния](work-state.json). SHA в состоянии — **принятый код приложения**,
не SHA последнего docs-коммита. Последний remote HEAD необходимо проверить отдельно.
CI проверяет ссылки/структуру handoff; он не удостоверяет актуальное состояние VPS.

## Продукт и ближайший результат

MCP Rooms / «Хочу — Предлагаю»: рынок возможностей из личного общения человека с
любым агентом. Человек работает через web, агент через MCP/HTTP; объекты и правила
одни. Долгая перспектива — вещи, услуги, работа/сотрудники, проекты/стартапы,
инвесторы/партнёры. **Не реализовывать все вертикали одновременно.** География —
фильтр, не ограничение регистрации одним городом; GitHub/email/телефон не обязательны.

Ближайшая приёмка: одна настоящая вещь → приватный черновик и реальные фото →
точный preview/отдельное согласие → публичная карточка → независимый приватный
отклик. Продажа не гарантируется и не подделывается. Снятый/помытый б/у унитаз —
допустимый технический тест, не обязательный PR-образ проекта. Фото, цену,
местоположение, комплект и дефекты должен подтвердить сам владелец.

## Текущий приоритет: короткий owner-first TEST

[Сокращённый маршрут F1–F2](owner-first-test.md): MCP/Bearer HTTP управляет объявлением;
публичный web только читает явно опубликованную карточку/фото по ссылке. ≈3 крупных
ворот до разрешённого VPS TEST вместо ожидания всего полного6-этапного сценария.
Нет browser editing/onboarding/search/replies/admin MCP; это меньший результат.
M3b.3 session binding **не отменён**: paused до возвращения browser writes.
[F1 принят в exact-SHA CI](ci-f1.md):645 tests на Python3.12.
[F2 принят в exact-SHA CI](ci-f2.md):686 tests на3.12 плюс installed-wheel native smoke.
[Контракт TEST-кандидата](test-candidate.md) описывает fresh-only bootstrap, startup без
DDL и один worker/upload. F3a [Landlock/seccomp](media-sandbox.md) [принят в exact-SHA CI](ci-f3a.md):709 tests на3.12.
Candidate обязан отказать до app startup без рабочей политики. F3b [offline recovery quarantine](recovery-candidate.md) [принят в CI](ci-f3b.md):761 tests на3.12.
Original current authority обязателен; output не compose-ready, все publications withdrawn.
F3c.1 [offline wheelhouse](operator-package.md) [принят в CI](ci-f3c1.md):789 tests;
30 runtime hash pins, offline clean venv/native+recovery smoke. F3c.2a [read-only proposal](operator-plan.md) [принят в CI](ci-f3c2a.md):826 tests;
unattested observations, fixed isolated targets, no host probe/effects.
Current F3c.2b [unprivileged lifecycle rehearsal](operator-lifecycle.md) — [принят в CI](ci-f3c2b.md):864 tests3.12; real offline install/loopback MCP/stop/restart, occupied-port preservation и interrupted-start cleanup. Не root/systemd supervisor.
Current F3c.2c.1 [unit/cgroup proof](operator-supervision.md) — [accepted in CI](ci-f3c2c1.md):903 tests3.12; real synthetic descendant cleanup/accounting, not actual candidate-in-unit or capacity acceptance.
Current F3c.2c.2 [actual candidate under exact unit](candidate-unit-ci.md) — SOURCE pending Actions; CI-only privileged fixture, not production installer.
F3c.2c.3 fresh root installer/capacity/disk acceptance — next_task; recovery promotion/missing-current disaster policy сохранены в
paused_tasks (RECOVERY-CUTOVER). Ни один из них не означает самовольный deploy.

## Архитектура уже выбрана

[ADR-001](decisions/001-marketplace-foundation.md): минимальный собственный Python/SQLite
предметный слой, поддерживаемые инфраструктурные библиотеки. Не микросервисы,
PostgreSQL, Telegram-storage, обязательные embeddings или новый готовый marketplace
framework без измеренного blocker. Исследование кандидатов завершено; результаты
сохранены в [итогах](marketplace-research-final.md).

- `store.py`, `identity.py`: SQLite, UUID users, digest-only Bearer, resource/scopes/revoke/disable.
- `draft_store.py`, `listing_contract.py`: private drafts/category/CAS/idempotency, market schema2.
- `media_image.py`, `media_worker*.py`: normalize JPEG/PNG → metadata-free JPEG; bounded isolated
  child; candidate дополнительно требует `media_sandbox.py` Landlock/seccomp.
  Legacy bare worker не является OS sandbox. Native >=3.11, core >=3.10.
- `media_files.py`, `media_stage.py`, `media_cleanup.py`: private pinned root, media schema3,
  owner-bound staging, reviewed plan/apply cleanup. Crashes/orphans fail closed; не auto-delete.
- `photo_drafts.py`, `publication_store.py`: ordered0–8 photos; publication schema1;
  exact live consent consume/snapshot/audit, withdrawal, public allowlist primitives.
- `market_adapter.py`, `market_tools.py`, `server.py`: explicit market composition,
  8 rooms +12 scoped listing tools. Default CLI по-прежнему8 rooms.
- `media_http.py`: explicit opt-in bounded binary upload/private JPEG read; не public photo route.
- `test_candidate.py`: отдельный fresh-only операторский профиль и process lock; не VPS installer.
- `recovery.py`: offline snapshot/restore/verify, оригинальная current authority обязательна,
  output quarantine без profile marker; не autonomous DR/promotion и не MCP endpoint.
- `tools/operator_bundle.py`: versioned runtime hash-lock, source/hash verifier, public-only offline wheelhouse; не VPS installer.
- `public_web.py`: explicit opt-in anonymous read-only card/photo; нет feed, формы или cookie writes.
- `browser_sessions.py`: отдельный bounded session core, browser schema1.
- `browser_http.py`: opt-in session login/bootstrap/logout bridge; статус в work-state.
  Cookie ещё не является authority для listing/media writes: сначала transaction-time
  session binding (M3b.3), затем browser commands. Default CLI не изменён.

Сервисный слой повторно проверяет persisted authority, не доверяет Principal из JSON.
Адаптер должен строить Principal только из проверенного credential/session. Ранее
выданный ключ/снимок scopes не заменяет свежую проверку. Старый private intent не
превращается в live publication consent. Replay receipt — исторический результат,
поэтому после повторной publish/withdraw команды отдельно читать текущий статус.

## Фото человеком и агентом

[HTTP контракт](media-http.md): raw binary upload, owner/write/revision/idempotency,
не arbitrary URL, путь, multipart или base64 в MCP. Оригинал не сохраняется. Загрузка
не прикрепляет и не публикует. Агенту нужен реальный доступ к файлу и binary HTTP;
MCP сам не открывает диск пользователя. Будущая web-форма вызывает тот же service,
используя отдельную браузерную session/CSRF, а не Bearer в frontend/localStorage/URL.

## Что ещё НЕ сделано

Cookie-authorized market commands, автоматический onboarding/recovery и форма, публичный каталог/search, web-редактирование, приватный отклик, отдельный admin MCP; VPS OS-policy/load/RAM
приёмка, DB+files disaster restore/security-state reconciliation, безопасная очистка
долгоживущих auth receipts/сессий. Не считать стадией production наличие public_get
внутри Python, green unit tests или GitHub Pages. [План до TEST](deployment-readiness.md)
содержит полный6-этапный и сокращённый3-воротный маршрут; ни один не означает готовый deploy.

## Состояние инфраструктуры — только последнее известное

- Разработка `feat/standalone-identity`, PR #1. Main по последней сохранённой проверке —
  scaffold, не текущий marketplace. Не мерджить без решения владельца.
- Standalone Rooms TEST был проверен Qwen ↔ Notion, затем остановлен/HTTPS route удалён.
  Старый production `mcp-server` — другой проект/сервис. Rooms production не принимался.
- GitHub Pages — документация, не marketplace. Каждая страница привязана к source SHA.
  Возможен конкурирующий Jekyll publisher: [owner-controlled gate](ci-pages.md#remaining-single-publisher-configuration-gate).
- Не выводить текущую доступность VPS из старого отчёта. Для новых проверок соблюдать
  разрешения AGENTS.md; вместо самовольного probe сначала согласовать действие.

## Процедура продолжения нового чата

1. Прочитать AGENTS, work-state, реестр; проверить remote branch HEAD, PR и CI. Если
   HEAD отличается от ожидаемого — перечитать изменённые файлы, не затирать работу.
2. Сопоставить accepted source SHA с evidence и открытыми blockers. SOURCE не считать CI.
3. Взять **одну** next task из work-state; прочитать её контракт и source/tests. Не начинать
   с переписывания стека/маркетинговых обещаний или расширения всех категорий.
4. Подготовить код/негативные тесты/документацию. Локально только static/AST, без импорта
   приложения/pytest/build/browser. Commit через expected-head CAS; проверки только Actions.
5. Разобрать failures по attempt-pinned bounded logs, исправить причину, не ослаблять тест.
6. После green source SHA записать evidence, обновить README/ROADMAP/реестр/work-state.
   Docs-коммит проверяется отдельно и не подменяет source acceptance SHA.
7. Завершить понятной сводкой: что принято, что не работает извне, следующий bounded
   шаг, нужны ли разрешения владельца. Не просить пользователя заново пересказывать чат.


## Исходный mcp-server — отдельный durable handoff

Для GitHub/research/binary и embedded rooms не восстанавливать старую переписку:
[документационный PR118](https://github.com/LeonidYasin/mcp-server/pull/118),
[pinned entry](https://github.com/LeonidYasin/mcp-server/blob/8f07bafce89f350badaf48b59abea30b495c4aab/AGENTS.md).
Там индексированы исходники/проверки/незавершённые gates и исторический extraction.
Это отдельный незамерженный docs PR, не runtime dependency Rooms и не общий deploy.
