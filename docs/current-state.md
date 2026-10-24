# Текущее состояние MCP Rooms

Проверено для принятого исходного SHA `db32c6ddf8f3b57874180dce81908e0d43aaa2f0`;
`main` после owner merge — `06031dbcb1dcb37d7b0b6a700b0924a9ca09f19a` (PR #6, docs).
Это состояние
кода, CI и изолированного loopback TEST, **не production**.

## Проект в одном абзаце

MCP Rooms — MCP-first площадка «Хочу / Предлагаю». Основной способ работы пользователя
с площадкой — чат со своим ИИ-агентом. Агент получает ограниченные MCP-инструменты и по
явному поручению пользователя создаёт черновик, добавляет фото, показывает точный
предпросмотр, публикует и снимает объявление. Web на текущем этапе — публичная
**витрина только для просмотра** уже опубликованных карточек и фотографий. Web-форма,
кабинет, каталог с записью и cookie-authorized редактирование пока не являются частью
ближайшего результата.

## Что реализовано

### Основа доступа и общения

- локальные UUID-пользователи без обязательного GitHub/email/телефона;
- digest-only Bearer-ключи, scopes, срок действия, отзыв и блокировка пользователя;
- 8 MCP-инструментов общих Rooms;
- 12 opt-in MCP-инструментов объявлений;
- официальный MCP Python SDK и Streamable HTTP;
- SQLite как единое локальное хранилище.

### Объявления и фото

- приватный черновик, категории, revision CAS и идемпотентные команды;
- безопасная загрузка JPEG/PNG и перекодирование без метаданных;
- приватное файловое хранилище, квоты, staging, cleanup и проверка владельца;
- точный preview конкретной версии;
- отдельное согласие на публикацию;
- публикация, публичная allowlist-проекция и снятие объявления;
- анонимная read-only HTML-карточка и публичные производные фото.

### Эксплуатационная подготовка

- Linux sandbox декодера: Landlock/seccomp, rlimits и bounded worker;
- offline DB+photos recovery в новую закрытую карантинную копию;
- hash-pinned offline wheelhouse;
- fresh-only root-trusted установка без неявного bootstrap/start;
- фиксированный systemd unit и cgroup harness;
- отдельный guarded controller для capacity check, bootstrap, start и stop;
- отказы при занятом порте, unit/drop-in/path/process drift и прерванном старте;
- stop сохраняет БД, фото, ключи и receipts.

## Что подтверждено

На SHA `db32c6ddf8f3b57874180dce81908e0d43aaa2f0` успешно завершены:

- CI на Python 3.10, 3.11, 3.12 и 3.13;
- build wheel/sdist и import установленного wheel вне checkout;
- installed owner-first candidate smoke на поддерживаемых версиях;
- operator systemd supervision proof с реальным disposable systemd/cgroup fixture;
- тесты нового read-only preflight-инструмента;
- повторный read-only preflight после апгрейда до 4 GiB — PASS; на тот момент установка не выполнялась;
- GitHub Pages/documentation workflows;
- fresh isolated owner-first TEST на 4 GiB VPS: install/bootstrap/start, synthetic
  MCP draft → upload → preview → consent → publish → public GET → withdraw,
  stop-only rollback и повторный start/synthetic flow — PASS
  ([evidence](owner-first-vps-test-2026-10-23.md)).

Это подтверждает код, Actions и loopback-сценарий на конкретном VPS. Это **не**
подтверждает внешний HTTPS/Caddy, реальную карточку с реальными фото, production
или публичную регистрацию. Synthetic key был одноразовым и имел TTL 1 час.

## Что пока не сделано

- production MCP Rooms и постоянно работающий endpoint;
- внешний HTTPS/Caddy route и external MCP acceptance;
- открытая регистрация и безопасное восстановление потерянного доступа;
- запись через браузер: формы, кабинет и cookie-authorized market/media commands;
- общий публичный feed/search;
- приватные отклики и переговоры;
- отдельный admin MCP и модерация;
- полный независимый disaster-recovery cutover без исходной current authority;
- VPS capacity acceptance и measured production RSS/peak под нагрузкой (cgroup
  memory.peak/CPU/tasks измерены в Actions через `tools/ci_candidate_unit.py`,
  но не являются доказательством достаточности конкретного VPS);
- off-host backup, шифрование backup, retention и алертинг.

## Текущая граница

Принятый application source — `db32c6d…`; `main` — `06031db…` после merge
[PR #6](https://github.com/LeonidYasin/mcp-rooms/pull/6) (docs/loopback TEST). Pre-release
`operator-wheelhouse-db32c6d` содержит проверенный offline bundle; тег и артефакт
не являются production deploy.

Fresh isolated owner-first TEST на VPS выполнен 2026-10-23: bundle скачан и
проверен, installer/inspect отработали без bootstrap/start, контроллер отдельно
создал disposable профиль и запустил кандидат, synthetic MCP flow прошёл, stop
сохранил state, повторный start и synthetic flow также прошли. Caddy/HTTPS не
менялись; внешний MCP и реальная карточка не принимались. Подробности и границы —
в [loopback evidence](owner-first-vps-test-2026-10-23.md).

Synthetic owner key имел TTL 3600 секунд. После его истечения authenticated
external testing требует отдельного одобрения нового listing-scoped test credential
или fresh profile/key gate; нельзя молча выпускать или переиспользовать ключ.

### Запись мержа (2026-10-22/23)

Владелец отдельно одобрил объединение базовой alpha: [PR #1](https://github.com/LeonidYasin/mcp-rooms/pull/1)
мержится, после чего история `main` по одобрению владельца восстановлена в линейном
виде на `7c1bd3b9b8dbbe45e4197b2cacce5a2a7a74bf08` (промежуточный squash-коммит
удалён, чтобы evidence-документы ссылались на достижимые из `main` точные SHA).
Затем владелец смержил [PR #2](https://github.com/LeonidYasin/mcp-rooms/pull/2)
(docs baseline, `bd0643f`), [PR #3](https://github.com/LeonidYasin/mcp-rooms/pull/3)
(F3c.2d read-only preflight, merge commit `4f08f0ab5fd9efd1363a8639e4031a0420ac1f27`),
[PR #4](https://github.com/LeonidYasin/mcp-rooms/pull/4) (seccomp-исправление и
первый VPS-отчёт, merge commit `fd2f61650bd3977947ea3679cd677dbc77bc8692`) и
[PR #5](https://github.com/LeonidYasin/mcp-rooms/pull/5) (x-ui protected default и
4 GiB preflight PASS, merge commit `258684311d2f4bb009e339f007978634211da8eb`), а
2026-10-24 — [PR #6](https://github.com/LeonidYasin/mcp-rooms/pull/6) (loopback TEST
evidence и handoff-состояние, merge commit `06031dbcb1dcb37d7b0b6a700b0924a9ca09f19a`;
application source не менялся).
Текущий `main` — `06031db…`. Создан pre-release `operator-wheelhouse-db32c6d`
для offline install; production deploy, тег production и real card не созданы.
Принятый application source SHA — `db32c6d…`; новые изменения идут через особые
owner-approved PR в `main`.

## Следующий шаг

Проверено в CI: **F3c.2c.3c real systemd proof персистентного unit** (PR #12) и **F3c.2c.3c aggregate capacity measurement** (PR #13/work-state, docs/ci-f3c2c3c.md): no OOM kill, peak ~172 MiB < 1 GiB, tasks <= 64, cpu > 0; `fixture_capacity_bounds_only=true`, `vps_capacity_accepted=false`.

Далее — только отдельным owner-разрешением: persistent install/enable персистентного unit на VPS и **HTTPS/external acceptance** (G3). Каждая серверная операция требует отдельного согласия владельца и специального пароля. Агент не выполняет remote/SSH/VPS.

Loopback-часть fresh owner-first TEST завершена. HTTPS/external acceptance — только после нового отдельного разрешения:

1. узкий временный Caddy route с сохранением Host и снятием только `/rooms`;
2. проверка external MCP без токена (`401`) и с одобренным test credential;
3. отдельное решение по новому listing-scoped credential или fresh profile/key,
   потому что synthetic key имел TTL 1 час;
4. одна реальная карточка с реальными фото и явным согласием владельца;
5. внешняя проверка read-only web с устройства без агента;
6. снятие карточки, удаление route, остановка TEST и сохранение evidence.

Каждое удалённое действие требует отдельного разрешения владельца и специального
пароля. Merge, release и production — отдельные решения.
