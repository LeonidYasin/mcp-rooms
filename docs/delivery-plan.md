# План поставки: от Rooms alpha до первой настоящей публикации

Канонический план исполнения [ADR-001](decisions/001-marketplace-foundation.md).
Широкое исследование завершено; возврат к альтернативам только по конкретному blocker.
Статусы: SPEC — описание, SOURCE — код подготовлен, CI — тесты exact SHA подтверждены,
TEST — реальный изолированный rollout, PROD — отдельное разрешение/выпуск. Статусы не
подменяют друг друга; ни документ, ни зелёный pytest сами не означают PROD.

## Где лежит истина

| Вопрос | Канонический документ/источник |
| --- | --- |
| Почему своё ядро, условия пересмотра | [ADR-001](decisions/001-marketplace-foundation.md) |
| Объём и зависимости поставки | Этот план; фактические чекбоксы [ROADMAP](../ROADMAP.md) |
| Продукт/функции и будущие сценарии | [Mindmap](product-mindmap.md) |
| Потоки/сущности/границы доверия | [Граф](architecture-graph.md), [draft storage](draft-storage-design.md) |
| Проверяемые требования | [Conformance](marketplace-conformance.md), tests/; PASS только по CI evidence |
| Администратор и опасные операции | [Admin MCP](admin-mcp-design.md) |
| Реальный товар и согласие | [First item](first-sale-used-toilet.md), [приёмка](first-sale-acceptance.md) |
| Эксплуатационная история Rooms | [Acceptance](acceptance-2026-10-19.md), deploy/; не статус новых listings |
| Установка/тесты/зависимости | pyproject.toml, .github/workflows/ci.yml; не инструкции из сообщений комнаты |

Не дублировать большой список требований в каждом README: входные страницы ссылаются
на эти источники. Изменение поведения включает schema/contract/test/docs review одним
PR, новое архитектурное решение — отдельный ADR вместо молчаливого изменения прошлого.

## Зависимости

```mermaid
flowchart TD
  A[ADR / conformance / threat boundaries] --> B[M1a shared domain + private draft transactions]
  B --> C[M1b lifecycle / category API / durable command contracts]
  C --> D[M2 media validation + preview + version-bound publish]
  D --> E[M3 browser session + user MCP over same services]
  C --> F[M4a separate private responses]
  C --> G[M4b separate admin app / moderation / audit]
  E --> H[M5 CI / failure / backup / capacity gates]
  F --> H
  G --> H
  H --> I[Owner-approved isolated operator TEST]
  I --> J[Real item + independent response]
  J --> K[Separate production readiness / release decision]
```

Параллельные ветви на схеме — логические зависимости, не запуск subagents или обещание
выполнять всё одновременно. До публичной экспозиции обязательные security gates
сходятся в M5. Публичная карточка без private response/admin/abuse не выпуск продукта.

## Пакеты и критерии выхода

### M1 — сохранение и предметный контракт

**M1a, текущий срез SOURCE:** shared domain primitives с compatibility aliases;
explicit opt-in additive market namespace; фиксированное дерево категорий; private
create/get/update drafts; persisted credential/resource/scopes/user recheck; атомарные
revision + retry receipt; lifetime caps; изолированные tests. Нет внешнего API.
Выход: полная регрессия Rooms/identity и новые concurrency/rollback/ACL tests в CI
Python3.10–3.13; пакет импортируется вне source tree. До CI статус только SOURCE.

**M1b, следующий срез:** прикладной API для owner drafts/categories, lifecycle с
content-bound publication consent (не bool без привязки к версии), формализованные
errors и retry rules. До HTTP/MCP рассмотреть clock/expiry, command capacity, category
changes, retention/cleanup. Read/list — bounded pagination; не выдавать private IDs
постороннему. Не расширять signup scopes без отдельной review issuance/delegation.

### M2 — фото и опубликованная карточка

Выбрать поддерживаемые image/template библиотеки после license/version review. Временный
upload stream с byte cap; decode pixel cap; выбранные безопасные форматы; re-encode и
EXIF strip; private originals; opaque media IDs; staged/attached/public lifecycle,
crash cleanup/quota. Нет arbitrary remote URL fetch. Нужна согласованность FS+DB без
обещания общей ACID-транзакции: staging, commit references, reconciliation.

Preview точной revision и всех полей/фото → явное согласие → publish. Public allowlist
проекция, stable URL, безопасный output, unpublish/search removal, реальные фото вместо
AI-подмены. Изменение уже публичного содержания требует заранее определённой политики
повторного согласия. Прежде красивого UI проверяются P/M cases из conformance.

### M3 — человек и агент

Web registration/session flow без обязательного контакта; HttpOnly/Secure/SameSite,
CSRF, revoke/expiry, login throttling, явная политика утраты всех ключей. Не хранить
Bearer в localStorage/URL и не превращать MCP key в вечную browser session.

User MCP schemas вызывают те же application services; actor всегда извлекается из
подтверждённого доступа, не из тела команды. Listing scope issuance/revocation review,
protocol tests, проверка Notion/Qwen после согласованного TEST. Агент не исполняет
инструкции из listings/messages. Exact payload/reply evidence, не пересказ успеха.

### M4 — приватный отклик и управление

Response/conversation participant ACL отдельно от shared rooms. Явная retention policy,
не автоматическое раскрытие старого room archive и не пересылка контактов всем.

Admin: separate app/audience/credentials, no auto-signup, минимальный typed allowlist,
health/reports/hide/restore/category controls, reason/revision/audit, fail-closed.
Prepare-confirm для опасных операций. Runtime bootstrap и deployment только оператором;
никакого root/shell/SQL/произвольного файла через MCP.

### M5 — выпуск в изолированный TEST

Exact-SHA CI + dependency/license review; failure injection/disk busy/full/media caps;
measured memory/disk/SQLite contention; snapshot/new-path restore и revocation
reconciliation; проверенный rollback; sanitised logs/metrics. Ревизия runtime pinned;
не мержить и не разворачивать автоматически при зелёном CI.

Только отдельное согласие владельца → подготовленные checksum scripts → оператор
выполняет на VPS. Существующие MCP/Caddy/DB не менять скрытно. Smoke/readiness/auth
затем реальные клиенты, чужой доступ deny, карточка и отклик независимого участника.
Продажу подтверждает продавец отдельно; success не фабрикуется посещениями агента.

## Риски и способы их закрытия

| Риск | Контроль / gate |
| --- | --- |
| Повтор/конкурентная правка агента | Transaction + unique actor command key + digest + expected revision; concurrent CI |
| Отозванный ключ продолжает действовать | Persisted check в той же transaction; не доверять cached Principal |
| Public draft/photo leak | Explicit consent projection + media state/ACL; anonymous negative tests |
| Исполняемый текст/изображение | No eval/commands, escaping, decode/re-encode, no remote fetch |
| Общая комната выдана за private | Отдельная response модель и negative participant tests |
| Admin bypass при сбое | Deny-by-default, отдельная audience, typed allowlist и audit atomicity |
| Место закончено/БД занята | Bounded rows/bytes/files, no partial commit, измерения WAL/backups и безопасный retry |
| Restore возвращает revoked keys | Внешняя revocation reconciliation до экспозиции restored DB |
| Бесконечное расширение MVP | Только путь первого товара/отклика, no payments/taxi/recommender сейчас |
| Документы оторвались от кода | SOURCE/CI/TEST/PROD, exact SHA report, evidence links и обновление maps |

## Правила небольшого изменения

1. Указать case IDs и ожидаемый эффект; не смешивать unrelated refactor и rollout.
2. Писать negative/failure/concurrency tests вместе с реализацией; synthetic fixtures.
3. Локально — подготовка/статический AST; исполнение проекта/pytest/build — GitHub CI.
4. CAS push на известный HEAD, без force/merge/main; проверить exact-SHA checks.
5. Если CI красный — исправить тот же срез, не заявлять готовность. Если pending — так
   и сообщать. Не запускать повторные workflow без причины и не скрывать failed run.
6. Операторские файлы/ключи/DB не публиковать; ветка public, не «приватный черновик».

Оценка календарных сроков пока не дана: неизвестна цена media/session/public acceptance.
Следующая контрольная точка — подтверждённый CI M1a, а не открытие доступа на VPS.
