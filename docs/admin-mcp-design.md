# Отдельный admin MCP: проект безопасности

Статус: спецификация, НЕ включённый endpoint. Старый операторский CLI остаётся CLI.
Цель — управлять проектом через отдельный MCP без превращения публичного сервера в root-shell.

## Отдельный вход

- Отдельный ASGI/MCP app и resource/audience, рекомендуется отдельный hostname.
  URL выбирается перед операторским TEST, адреса в этом документе не действующие.
- Отдельное хранилище credential digests/ролей и namespace admin principal. Нет auto-signup.
- Bootstrap первого администратора только оператором, секрет в private delivery,
  не в чате/tool arguments/URL/логах/публичной регистрации. Выдача admin ключа не MCP tool.
- Пользовательский rm1/rooms credential не допускается в admin, даже при одинаковом UUID.
- Минимальные роли: observer, moderator, operator. grant/revoke roles отдельно от moderation.
- Короткие сессии, expiry/revocation/disable на каждом вызове; MFA/step-up — отдельный
  поддерживаемый механизм перед широким использованием, не имитация второго фактора.
- Сеть: allowlist/VPN или иной ограниченный ingress, rate limits и выключатель;
  endpoint не открывается вместе с пользовательской витриной.

## Предлагаемые capabilities (названия будущие)

| Группа | Примеры | Ограничения |
| --- | --- | --- |
| Read-only | admin_health, admin_metrics, admin_jobs, admin_audit_list | Без секретов/raw logs/DB download, bounded pagination |
| Категории | admin_category_create/update/archive | reason, revision CAS; не удалить используемую рубрику |
| Модерация | admin_listing_hide/restore, admin_report_resolve | Public hidden state, reason, appeal; не переписать автора |
| Доступ | admin_user_disable, admin_credential_revoke | Target ID, human approval при массовом/критичном изменении |
| Квоты | admin_limits_propose/apply | Validated allowlist, bounds, preview, отдельное подтверждение |
| Данные | admin_snapshot_prepare/status/verify | Guarded job; новый private path, не произвольный путь клиента |
| Выпуск | admin_release_inspect/plan | Только SHA-pinned report/план, не авто-merge/root/deploy |

«Любое администрирование» означает покрытие типизированными проверяемыми операциями,
а НЕ run_python/run_command/SQL/shell/произвольный доступ к файлам. Нет универсального
admin_execute, template interpolation, передачи scripts и root credentials инструменту.
Новые возможности добавляются только после review и тестов negative ACL.

## Опасные операции

Двухшаговый prepare → confirm → execute: план фиксирует actor, capability, target IDs,
revision, digest аргументов, срок и одноразовый nonce. Подтверждение привязано к точному
плану, не глобальный флажок "да". Повтор не исполняет действие второй раз. При смене
прав/ревизии/истечении — отказ, re-plan. Audit одной транзакцией с изменением или отказ.

Для root/VPS изменения **дополнительно** требуется явное подтверждение владельца и
специальный пароль в согласованном безопасном канале. Agent не выполняет эти операции
ни прямо, ни через подставной job. На первом этапе выдаёт проверенный скрипт оператору.
Пароль не принимается как MCP argument. Реализация механизма step-up ещё не готова.

## Аудит и восстановление

- Actor/credential ID, operation, target IDs, reason, plan digest, before/after revision,
  timestamp, outcome/correlation ID. Не raw токены, cookies, адреса, тела личных сообщений.
- Нет скрытой массовой выгрузки пользователей и чтения личной переписки «для удобства».
- Причины модерации видимы автору; меры обратимы там, где возможно; hard-delete отдельно.
- Restore может воскресить отозванные ключи: внешний revocation journal/reconciliation
  обязателен перед возвратом восстановленной копии в доступ. SQLite backup не решает это сам.
- Tamper-evidence/off-host audit, алерты и budgets — отдельные production gates.

## Обязательные тесты до включения

1. Обычный пользователь → admin 401/403; admin key → user endpoint не проходит audience.
2. Observer не мутирует; moderator не меняет роли/выпуски/ключи; disabled/revoked отсекаются.
3. Нет admin tools в user tools/list; нет утечки секретов в errors/logs/metrics.
4. Stale revision/expired plan/replayed confirmation/замена actor или аргументов → отказ.
5. Результат мутации и audit атомарны; storage failure не оставляет частичное действие.
6. Нет возможности выполнить shell/SQL, выбрать путь/hostname по содержимому комнаты.
7. Операторский TEST не затрагивает существующие mcp-server/Caddy/другие БД.
