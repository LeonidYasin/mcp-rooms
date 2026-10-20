# Повторная проверка готовых основ: glacier-mcp и classifieds

Исследовательский срез после уточнения первого товара: **б/у унитаз**.
Это сравнение исходников/документации, не security audit, benchmark, проверка всех
альтернатив или разрешение установить их на VPS. Никакой внешний код не скопирован.

## Наш glacier-mcp — полезен архитектурным принципом

Проверены README, docs/architecture.md, __main__.py, state.py; затем HEAD main:
`f8a53422c1d21728b1671dbabc449f941318f1fd`.

- [Архитектура](https://github.com/LeonidYasin/glacier-mcp/blob/f8a53422c1d21728b1671dbabc449f941318f1fd/docs/architecture.md):
  браузерный UI и MCP работают над одним PolygonState; UI через FastAPI/WebSocket.
- [Состояние](https://github.com/LeonidYasin/glacier-mcp/blob/f8a53422c1d21728b1671dbabc449f941318f1fd/src/glacier_mcp/state.py):
  коллекция полигонов, единая точка мутаций apply, ограниченная общая undo/redo история.
- [Запуск](https://github.com/LeonidYasin/glacier-mcp/blob/f8a53422c1d21728b1671dbabc449f941318f1fd/src/glacier_mcp/__main__.py):
  два сервера в одном процессе; переносить номера портов нельзя — проверять занятость.

Переносимый принцип: **человек правит карточку в web, агент правит ту же запись через
MCP; оба проходят один сервисный слой; web видит зафиксированную сервером версию**.
Не заводить независимые "карточку для агента" и "карточку для человека".

Не переносить буквально: глобальное in-memory состояние, общую для всех undo и GIS
зависимости. Для публичной многопользовательской площадки нужны SQLite transactions,
owner/scopes, revision CAS, idempotency и audit. WebSocket — необязательная оптимизация;
сначала bounded polling/обновление версии. Карта позже полезна для приблизительной
локации/доставки, но не блокирует продажу одной вещи и не публикует домашний адрес.
MIT glacier не снимает необходимость отдельных проверок безопасности Rooms.

## Внешние основы

| Проект | Подтверждено источником | Что полезно | Ограничение решения |
| --- | --- | --- | --- |
| [OpenClassify](https://github.com/openclassify/openclassify) | В текущем README: Listing, Category, Location, Conversation, Offer, Report, Admin; Laravel/Filament, PHP8.4+, PostgreSQL16+, Node20+ | Наиболее предметный кандидат полноценной готовой доски: дерево категорий, custom fields, inbox, предложения и модерация | Это другой backend/БД/операционный стек, не библиотека для Python/SQLite. Лицензия модулей, эксплуатация, API и actor-scoped MCP ещё не проверены. Наличие папки .ai/mcp не доказывает пользовательский marketplace/admin MCP |
| [Osclass](https://github.com/osclass/Osclass) | README: classifieds, plugins/themes, multilingual, dashboard/SEO; Apache2.0 | Образец карточек и расширяемых атрибутов категорий | Проверенный README содержит исторические ссылки; актуальный поддерживаемый вариант, зависимости, исправления безопасности и API требуют проверки. Не объявлять production-ready |
| [Discourse](https://github.com/discourse/discourse) | Темы, chat, plugins, self-hosting, REST backend; Ruby/Rails, PostgreSQL, Redis; GPL2.0-or-later | Обсуждения/сообщества, темы/модерация, идеи для UX | Не готовая модель объявления/заказа. Другой стек и лицензионные условия; не копировать код в MIT core без совместимого оформления |
| [Sharetribe Go](https://github.com/sharetribe/sharetribe) | README явно: no longer actively maintained; Sharetribe Community Public License, source-available | Источник продуктовых сценариев marketplace | Не выбирать как поддерживаемую бесплатную MIT-основу нового сервиса; проверить отдельные условия, не смешивать с новым SaaS |

Источники прочитаны через GitHub MCP и публичный web, а не только по описанию поиска.
Числа stars/репозиториев, модульные списки и заявленные возможности не заменяют испытание.
Ни для одного внешнего проекта здесь не доказана готовность наших требований admin MCP,
изолированных пользователей, backup/revocation и approved VPS rollout.

## Решение и обязательная проверка против "велосипеда"

Пока не переключать стек/БД и не разворачивать второй движок. Взять принцип shared
web/MCP state из glacier, проверить форму объявления на реальном предмете, использовать
готовые поддерживаемые библиотеки auth/templates/media, не писать свой HTTP/crypto.

Если выяснится, что уже в первом релизе необходим полный marketplace cabinet/chat/
moderation suite, до их самостоятельной реализации провести ограниченный spike
**OpenClassify + actor-scoped MCP adapter**: лицензии и ownership API → draft/photo/
publish/update → anonymous public read → private message → admin moderation → rollback.
Сравнить с существующим Python/SQLite направлением по объёму оставшихся функций,
операционным требованиям и тестируемости. Не считать наш код автоматически дешевле:
написать весь движок заново может оказаться хуже готового backend. Но смена на
PostgreSQL/PHP — отдельное решение владельца, не следствие красивого README.

Первый рынок не требует рекомендаций/embeddings, торгов или оплаты внутри платформы.
Gorse/LLM-подбор пока не нужен для объявления одной вещи. Сначала реальная публикация
и отклик; доставка/поездки не смешиваются с недоказанной готовностью classifieds.

## Конкретный первый товар

[Черновик и поля: б/у унитаз](first-sale-used-toilet.md). Предыдущий велосипед был
только визуальной демо-карточкой. У пользователя нет подтверждённых цены, состояния,
комплектности, фотографий и места вывоза в текущем контексте — не заполнять их догадками.
