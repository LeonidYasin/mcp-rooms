# Архитектура и граф связей MCP Rooms

Эта схема отделяет уже проверенный CI-код от будущих функций. Главный принцип:
**действия выполняются через чат пользователя с его ИИ-агентом и MCP; web пока является
витриной только для чтения.**

## Общий поток

```mermaid
flowchart TB
  U[Пользователь] --> CHAT[Личный чат с ИИ-агентом]
  CHAT --> CLIENT[MCP-клиент: Notion, Qwen или другой]
  CLIENT -->|Bearer| MCP[User MCP /mcp]
  MCP --> GATE[Identity + resource + scopes + revoke/expiry]
  GATE --> MARKET[Marketplace application services]
  GATE --> ROOMS[Shared Rooms services]

  VISITOR[Посетитель без агента] --> WEB[Read-only web-витрина]
  WEB --> PUBLIC[Allowlisted public projection]
  MARKET --> PUBLIC

  MARKET --> DRAFTS[Draft/category/CAS]
  MARKET --> MEDIA[Photo staging/attachment]
  MARKET --> PUBLISH[Preview/consent/publish/withdraw]
  DRAFTS --> DB[(Standalone SQLite)]
  PUBLISH --> DB
  ROOMS --> DB
  GATE --> DB
  MEDIA --> DB
  MEDIA --> FILES[Private derivative files]
  FILES --> PUBLIC

  OP[Оператор] --> TOOLS[Fixed operator CLI]
  TOOLS --> INSTALL[Offline install/inspect]
  TOOLS --> CONTROL[Capacity/bootstrap/start/stop]
  TOOLS --> RECOVERY[Offline DB+files quarantine]

  CI[GitHub Actions] --> ART[Exact-SHA wheelhouse/evidence]
  ART --> INSTALL
```

## Что может делать каждый участник

| Участник | Может | Не может |
| --- | --- | --- |
| Пользователь через агента | Управлять собственными черновиками, фото и публикациями в пределах scopes | Задавать owner в JSON, читать чужие private данные, выполнять admin/OS команды |
| Посетитель web | Читать active публичную карточку и её опубликованные фото | Создавать/редактировать, видеть ключи, private drafts или внутренние пути |
| Оператор | Выполнить фиксированные install/control/recovery действия после разрешения | Получить произвольный shell/SQL через MCP, автоматически принять partial install |
| Администратор будущего | Typed moderation через отдельную audience | Использовать обычный пользовательский ключ или общий shell |

## Текущий путь объявления

```mermaid
stateDiagram-v2
  [*] --> PrivateDraft
  PrivateDraft --> PrivateDraft: update with expected revision
  PrivateDraft --> Preview: exact content and photo set
  Preview --> Consent: explicit owner command
  Consent --> Published: transactional recheck and consume
  Published --> Published: anonymous read-only web GET
  Published --> Withdrawn: owner MCP command
  Withdrawn --> [*]: public GET becomes 404
```

Изменение текста или фото меняет revision и требует нового preview/consent. Старое
согласие не разрешает публиковать новую версию.

## Trust boundaries

```mermaid
flowchart LR
  subgraph Untrusted
    TEXT[Messages and listing text]
    IMG[Uploaded bytes]
    HTTP[HTTP request fields]
  end

  subgraph AuthBoundary[Authentication boundary]
    TOKEN[Bearer digest lookup]
    AUTH[Fresh persisted authority check]
  end

  subgraph App[Application boundary]
    CMD[Typed command]
    TX[SQLite transaction + CAS + idempotency]
  end

  subgraph Media[Native media boundary]
    ADMIT[Byte/pixel admission]
    CHILD[Landlock/seccomp child]
    DERIV[Re-encoded JPEG]
  end

  TEXT --> CMD
  HTTP --> TOKEN --> AUTH --> CMD --> TX
  IMG --> ADMIT --> CHILD --> DERIV
  TX --> DB[(SQLite)]
  DERIV --> FS[Private files]
```

Сообщения и объявления являются данными, а не инструкциями для агента. Нет `eval`,
произвольных URL fetch, shell, Python или SQL через пользовательский MCP.

## Реализованные связи

```mermaid
flowchart TD
  ID[Identity] --> R[Rooms MCP]
  ID --> D[Private drafts]
  D --> PD[Photo drafts]
  MW[Media worker+sandbox] --> MS[Media staging/files]
  MS --> PD
  PD --> P[Publication]
  P --> MT[Marketplace MCP]
  P --> PW[Read-only public web]
  MT --> C[Test candidate]
  PW --> C
  C --> B[Offline bundle]
  B --> I[Fresh install]
  I --> CTRL[Guarded lifecycle controller]
  C --> REC[Recovery quarantine]
```

## Отложенные связи

```mermaid
flowchart LR
  BS[Browser session core] -. M3b.3 transaction binding .-> BW[Browser write commands]
  BW -. later .-> FORM[Draft/photo web form]
  PUB[Published listing] -. separate ACL model .-> RESP[Private responses]
  ADM[Separate admin identity] -. typed capabilities .-> MOD[Moderation/audit]
  REC[Quarantine restore] -. explicit cutover policy .-> LIVE[Promoted service]
```

Browser session уже умеет login/logout, но cookie не является authority для записи
market/media. До M3b.3 web остаётся read-only. Shared Rooms не являются приватными
переговорами; responses требуют отдельной модели участников.

## Развёртывание

```mermaid
flowchart LR
  CODE[Accepted source SHA] --> CI[Actions matrix]
  CI --> PKG[Hash-pinned offline package]
  PKG --> PRE[Owner-approved read-only VPS preflight]
  PRE --> LOOP[Fresh isolated loopback TEST]
  LOOP --> HTTPS[Separately approved temporary HTTPS]
  HTTPS --> REAL[Real owner MCP publish/read/withdraw]
  REAL --> REVIEW[Evidence and next decision]
```

Ни один переход вправо не происходит автоматически. Для каждой удалённой операции
нужны отдельное разрешение владельца и специальный пароль. Production находится после
пилота, capacity/abuse/backup/privacy review и отдельного release-решения.

## Целевая модель данных

```mermaid
erDiagram
  USER ||--o{ CREDENTIAL : owns
  USER ||--o{ DRAFT : owns
  CATEGORY ||--o{ DRAFT : classifies
  DRAFT ||--o{ PHOTO_ATTACHMENT : contains
  MEDIA_MANIFEST ||--o{ PHOTO_ATTACHMENT : supplies
  DRAFT ||--o{ PUBLICATION : snapshots
  PUBLICATION ||--o{ PUBLIC_PHOTO : exposes
  USER ||--o{ ROOM_MEMBERSHIP : joins
  ROOM ||--o{ ROOM_MEMBERSHIP : has
  ROOM ||--o{ MESSAGE : contains
  USER ||--o{ MESSAGE : authors
  USER ||--o{ WEB_SESSION : authenticates
  PUBLICATION ||--o{ RESPONSE : receives_future
  USER ||--o{ RESPONSE : writes_future
  ADMIN_PRINCIPAL ||--o{ ADMIN_AUDIT : creates_future
```

`RESPONSE` и `ADMIN_*` пока целевые сущности, а не принятый runtime. Удаление Room не
удаляет Listing; публичная карточка не раскрывает credential, UUID владельца, private
заметки или точный адрес.
