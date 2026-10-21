# Архитектура и граф связей MCP Rooms

Главный принцип проекта: **пользователь работает с площадкой в чате со своим ИИ-агентом
через MCP; web ближайшего этапа является витриной только для чтения.**

## Общая схема

```mermaid
flowchart TD
  User[Пользователь] --> Chat[Чат с ИИ агентом]
  Chat --> Client[MCP клиент]
  Client --> MCP[User MCP]
  MCP --> Auth[Identity scopes revoke expiry]
  Auth --> Market[Marketplace services]
  Auth --> Rooms[Rooms services]
  Market --> Drafts[Drafts and categories]
  Market --> Photos[Photo pipeline]
  Market --> Publish[Preview consent publish withdraw]
  Drafts --> SQLite[(SQLite)]
  Rooms --> SQLite
  Publish --> SQLite
  Photos --> SQLite
  Photos --> Files[Private photo files]
  Publish --> Public[Public projection]
  Files --> Public
  Visitor[Посетитель без агента] --> Web[Read only web storefront]
  Web --> Public
```

ИИ действует только по явному поручению пользователя. Actor берётся из проверенного
credential, а не из JSON команды. Сообщения и объявления — данные, не инструкции.

## Кто что может

| Участник | Может | Не может |
| --- | --- | --- |
| Пользователь через агента | Управлять своими черновиками, фото и публикациями в пределах scopes | Задавать owner, читать чужие private данные, выполнять admin или OS команды |
| Посетитель web | Читать активную публичную карточку и опубликованные фото | Создавать и редактировать, видеть ключи и private drafts |
| Оператор | Выполнять фиксированные install, control и recovery действия после разрешения | Получать shell или SQL через MCP, принимать partial install |
| Будущий администратор | Typed moderation через отдельную audience | Использовать обычный пользовательский ключ или общий shell |

## Жизненный цикл объявления

```mermaid
flowchart LR
  Draft[Private draft] --> Preview[Exact preview]
  Preview --> Consent[Explicit consent]
  Consent --> Published[Published card]
  Published --> Storefront[Read only web]
  Published --> Withdrawn[Withdrawn]
  Withdrawn --> Gone[Public GET returns 404]
  Draft --> Changed[Changed revision]
  Changed --> Preview
```

Изменение текста или фото создаёт новую revision и требует нового preview и consent.
Старое согласие не разрешает публикацию изменённой версии.

## Границы доверия

```mermaid
flowchart TD
  Request[Untrusted request] --> Token[Bearer digest lookup]
  Token --> Authority[Fresh persisted authority]
  Authority --> Command[Typed application command]
  Command --> Tx[SQLite transaction CAS idempotency]
  Upload[Untrusted image bytes] --> Admission[Byte and pixel limits]
  Admission --> Sandbox[Landlock seccomp child]
  Sandbox --> JPEG[Reencoded JPEG]
  JPEG --> Storage[Private files]
```

Нет `eval`, arbitrary URL fetch, shell, Python или SQL через пользовательский MCP.
Public web читает только allowlisted projection и не получает дополнительных прав от
cookie или Authorization header.

## Связи готовых компонентов

```mermaid
flowchart TD
  Identity --> RoomsMCP[Rooms MCP]
  Identity --> DraftStore[Draft store]
  Worker[Media worker and sandbox] --> Media[Media storage]
  DraftStore --> PhotoDrafts[Photo drafts]
  Media --> PhotoDrafts
  PhotoDrafts --> Publication
  Publication --> MarketMCP[Marketplace MCP]
  Publication --> PublicWeb[Read only web]
  MarketMCP --> Candidate[Test candidate]
  PublicWeb --> Candidate
  Candidate --> Bundle[Offline bundle]
  Bundle --> Install[Fresh install]
  Install --> Control[Guarded lifecycle]
  Candidate --> Recovery[Recovery quarantine]
```

## Отложенные связи

- Browser session core → transaction-time authority → browser write commands.
- Published listing → отдельная participant ACL модель → private responses.
- Separate admin identity → typed moderation → audit.
- Recovery quarantine → отдельная cutover policy → promoted service.

Browser login/logout уже существует, но cookie пока не даёт права записывать market/media.
Shared Rooms не являются приватными переговорами.

## Путь к внешнему TEST

```mermaid
flowchart LR
  Source[Accepted source SHA] --> Actions[GitHub Actions]
  Actions --> Package[Offline package]
  Package --> Preflight[Approved VPS preflight]
  Preflight --> Loopback[Isolated loopback TEST]
  Loopback --> HTTPS[Temporary HTTPS]
  HTTPS --> RealFlow[Real MCP publish read withdraw]
  RealFlow --> Review[Evidence and decision]
```

Ни один переход не выполняется автоматически. Preflight, loopback install и HTTPS —
три отдельных разрешения. Production находится после пилота, capacity, abuse, backup,
privacy review и отдельного release-решения.

## Данные

Реализованы USER, CREDENTIAL, ROOM, MEMBERSHIP, MESSAGE, DRAFT, CATEGORY,
MEDIA_MANIFEST, PHOTO_ATTACHMENT и PUBLICATION. WEB_SESSION реализована, но не связана
с market writes. RESPONSE и ADMIN сущности пока только запланированы.

Удаление Room не удаляет Listing. Публичная карточка не раскрывает credential, UUID
владельца, private заметки, внутренние пути или точный адрес.
