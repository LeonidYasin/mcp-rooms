# Текущее состояние MCP Rooms

Проверено для исходного SHA `88eabfb35aa7cc763d85352e3e67a48e9d5fb97f` в ветке
`feat/standalone-identity`. Это состояние кода и CI, **не работающий production**.

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
- повторный read-only preflight после апгрейда до 4 GiB — PASS; установка не выполнялась;
- GitHub Pages/documentation workflows.

Это подтверждает код и синтетический Actions-сценарий. Это **не** подтверждает ёмкость
конкретного VPS, внешний HTTPS, реальный ключ, публичную регистрацию или production.

## Что пока не сделано

- production MCP Rooms и постоянно работающий endpoint;
- открытая регистрация и безопасное восстановление потерянного доступа;
- запись через браузер: формы, кабинет и cookie-authorized market/media commands;
- общий публичный feed/search;
- приватные отклики и переговоры;
- отдельный admin MCP и модерация;
- полный независимый disaster-recovery cutover без исходной current authority;
- измеренная ёмкость конкретного VPS, off-host backup и production runbook.

## Текущая граница

Код F3c.2d.2 — read-only preflight (root-only, без записи, установки и запуска
сервисов) с исправленной seccomp-пробой и `x-ui.service` в дефолтном
protected-наборе — присутствует в HEAD и прошёл Actions:
Python3.12 **992 passed**. Принятый source SHA — `db32c6d…`; docs-коммит сверху не
меняет принятый source SHA. Первый прогон на реальном VPS 2026-10-22 завершился
STOP по памяти ([отчёт](preflight-vps-2026-10-22.md)); после апгрейда до 4 GiB
повторный прогон — PASS, MemAvailable ≈3.07 GiB
([отчёт](preflight-vps-2026-10-22-4gb.md)); `x-ui.service` (3x-ui/VPN) добавлен
в дефолтный protected-набор. PR #4 смержен (`main` = `fd2f616`). Установка не
выполнялась и требует отдельного разрешения владельца со спецпаролем; PASS
preflight не разрешает install, loopback или HTTPS.

### Запись мержа (2026-10-22)

Владелец отдельно одобрил объединение базовой alpha: [PR #1](https://github.com/LeonidYasin/mcp-rooms/pull/1)
мержится, после чего история `main` по одобрению владельца восстановлена в линейном
виде на `7c1bd3b9b8dbbe45e4197b2cacce5a2a7a74bf08` (промежуточный squash-коммит
удалён, чтобы evidence-документы ссылались на достижимые из `main` точные SHA).
Затем владелец смержил [PR #2](https://github.com/LeonidYasin/mcp-rooms/pull/2)
(docs baseline, `bd0643f`) и [PR #3](https://github.com/LeonidYasin/mcp-rooms/pull/3)
(F3c.2d read-only preflight, merge commit `4f08f0ab5fd9efd1363a8639e4031a0420ac1f27`)
и [PR #4](https://github.com/LeonidYasin/mcp-rooms/pull/4) (seccomp-исправление и
первый VPS-отчёт, merge commit `fd2f61650bd3977947ea3679cd677dbc77bc8692`);
текущий `main` — `fd2f616…`. Тег, релиз и production-деплой не созданы. Принятый
application source SHA — `db32c6d…`; новые изменения идут через особые
owner-approved PR в `main`.

## Следующий шаг

Следующая крупная точка — **fresh isolated owner-first TEST**:

1. отдельно разрешённый read-only preflight конкретного VPS;
2. новая отдельная установка без использования старой Rooms TEST DB;
3. loopback synthetic acceptance;
4. только после отдельного разрешения — временный HTTPS и внешний MCP-клиент;
5. публикация одной реальной карточки с реальными фото и явным согласием владельца;
6. снятие карточки, остановка TEST и сохранение evidence.

Каждое удалённое действие требует отдельного разрешения владельца и специального
пароля. Merge, release и production — отдельные решения.
