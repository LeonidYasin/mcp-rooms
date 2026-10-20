# Граф связей и границ доверия

Текущее направление: [ADR-001 — минимальный собственный Python/SQLite domain](decisions/001-marketplace-foundation.md).
[Общий контракт приёмки](marketplace-conformance.md) описан, но не выполнен.

Проектная схема следующего этапа, не схема уже работающего production.
Связи описаны для запланированных компонентов; только room core/identity/operator CLI
и Qwen adapter реализованы в базовом alpha. Web preview и listing_contract — первый
изолированный шаг, НЕ зарегистрированные публичные API.

## Компоненты и потоки

```mermaid
flowchart TB
  H[Человек в браузере] --> W[Web витрина / формы / кабинет · план]
  A[Агент: Notion / Qwen / иной] --> U[Пользовательский /mcp]
  Q[Qwen без HTTP headers] --> P[Локальный proxy на ПК]
  P --> U
  W --> WS[Защищённая web session · план]
  WS --> ID[Локальная identity / отзыв / сроки]
  U --> ID
  ID --> AUTH[Проверка scopes / ownership / membership]
  W --> PUB[Только явно публичная проекция]
  AUTH --> L[Listing service · план]
  AUTH --> R[Room service · существует]
  AUTH --> O[Order / quote service · позже]
  L --> C[Category catalogue · план]
  L --> M[Media service · план]
  L --> R
  O --> L
  O --> PRIVATE[Приватные переговоры · план]
  PRIVATE --> RESPONSEDB[Изолированные response / participant ACL · план]
  RESPONSEDB --> DB
  L --> DB[(Одна standalone SQLite)]
  R --> DB
  O --> DB
  ID --> DB
  C --> DB
  M --> F[Частное хранилище оригиналов вне webroot]
  F --> TH[Проверенные перекодированные публичные миниатюры]
  TH --> PUB
  L --> PUB
  PUB --> W
  ADMIN[Администратор] --> AM[Отдельный admin MCP · отдельный origin / audience]
  AM --> AID[Отдельные admin credentials / roles / expiry]
  AID --> POLICY[Allowlist операций + dry-run + CAS + подтверждение]
  POLICY --> MOD[Модерация / категории / квоты]
  MOD --> L
  MOD --> C
  POLICY --> AUD[Санитизированный admin audit]
  MOD --> AUD
  POLICY --> OPS[Guarded operator jobs · отдельное разрешение]
  OPS --> BACK[Снимок / проверка новой копии]
  BACK --> DB
  OPS -. без автоматического root .-> ROOT[Оператор VPS / пароль / подтверждение]
  CI[GitHub PR / Actions] --> ART[Проверенный артефакт + SHA]
  ART --> ROOT
  ROOT --> DEP[Явный TEST / rollout / rollback]
  DEP --> U
  DEP --> W
```

Публичный web GET не требует секретного ключа и читает только allowlisted public поля.
Права web/MCP проверяются в общем сервисном слое, не только в UI. Admin вход закрыт
по умолчанию, отдельно от публичной регистрации и от старого mcp-server.

## Модель данных — целевая

```mermaid
erDiagram
  USER ||--o{ CREDENTIAL : delegates
  USER ||--o{ WEB_SESSION : authenticates
  USER ||--o{ LISTING : owns
  CATEGORY o|--o{ CATEGORY : parent
  CATEGORY ||--o{ LISTING : classifies
  LISTING ||--o{ MEDIA : has
  LISTING o|--o{ DISCUSSION_LINK : discusses
  ROOM o|--o{ DISCUSSION_LINK : references
  USER ||--o{ MEMBERSHIP : joins
  ROOM ||--o{ MEMBERSHIP : permits
  ROOM ||--o{ MESSAGE : contains
  USER ||--o{ MESSAGE : authors
  LISTING ||--o{ RESPONSE : receives
  USER ||--o{ RESPONSE : proposes
  LISTING o|--o{ ORDER : originates
  ORDER ||--o{ QUOTE : receives
  USER ||--o{ QUOTE : offers
  USER ||--o{ ORDER : requests
  ORDER ||--o| ASSIGNMENT : selects
  QUOTE ||--o| ASSIGNMENT : accepted
  ADMIN_PRINCIPAL ||--o{ ADMIN_CREDENTIAL : authenticates
  ADMIN_PRINCIPAL ||--o{ ADMIN_AUDIT : initiates
  ADMIN_AUDIT ||--o| CONFIRMATION : binds
```

ER-схема концептуальная: constraints/индексы/транзакции ещё предстоит реализовать.
Приватные данные адресов/контактов в отдельной защищённой проекции заказа, не в public listing.
Связь listing-room НЕ каскад удаления объявления при rooms_close; nullable/unlink.
У admin отдельный principal namespace: пользователь не повышает себя до admin.
ASSIGNMENT: уникальный order_id и CAS версии заказа в одной транзакции; один исполнитель.

## Инвентарь взаимосвязей

| Источник → цель | Контракт и граница |
| --- | --- |
| Браузер → public GET | Нет Bearer; только active/public/not-expired/not-blocked |
| Web session → сервис | Secure/HttpOnly/SameSite; CSRF, отзыв и scopes каждый запрос |
| Агент → /mcp | Индивидуальный Bearer; не токен в arguments/URL |
| /mcp → domain | Проверенный principal; owner не задаётся клиентом |
| Domain → SQLite | Параметры SQL, транзакции, revision CAS, квоты |
| Listing → public view | Allowlist полей; без credentials, точных адресов и внутренних заметок |
| Listing → room | Обсуждение отдельно, права не наследуются по одной ссылке |
| Media → файл | UUID reference, проверка формата/размера, перекодирование; не внешний URL-fetch |
| Admin → admin MCP | Отдельная audience/роль, не обычный пользовательский ключ |
| Admin command → mutation | Capability, reason, target revision, одноразовое подтверждение, audit |
| Operator → VPS | Только ручное согласованное выполнение; никакого remote shell tool |
| Backup → restore | Новая закрытая копия + проверка; revocation rewind reconciliation перед expose |
| Agents → external LLM | Опционально; приватный текст не отправляется без согласия |

## Карта исходников

- Реализовано: src/mcp_rooms/{store,service,identity,enrollment,server,admin,maintenance}.py.
- Начато отдельно: src/mcp_rooms/listing_contract.py — чистые типы/валидация/проекция,
  без SQL, transport, registration и новых scopes у существующих credentials.
- web/prototype/index.html — автономный дизайн-прототип с демо, не live витрина.
- Следующие модули: listing_store/service, web_app/templates, media, admin_server/auth/audit.
- Сейчас НЕ расширять IdentityStore.SCOPES до admin: отдельная модель и issuer/resource.

[Mindmap и этапы](product-mindmap.md) · [Admin boundary](admin-mcp-design.md)
· [Первый тест продажи](first-sale-acceptance.md).
