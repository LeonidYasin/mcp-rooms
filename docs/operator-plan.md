# F3c.2a — read-only предложение операторской установки

**SOURCE, ожидает exact-SHA Actions. Не installer, не выполненный dry-run VPS.**
[Предшествующий offline bundle](operator-package.md) · [Общий контракт](test-candidate.md).

`tools/operator_plan.py` не импортирует приложение, не создаёт каталогов/ключей,
не запускает processes/sockets/systemctl/useradd/pip/SSH. Доверенный verifier из
репозитория повторно проверяет весь распакованный wheelhouse: source SHA, внешний
ожидаемый runtime-lock hash, bytes/files/metadata/target. Не исполнять verifier
из неизвестного архива для доказательства доверия этому же архиву. SHA256 самого
tar.gz сверять независимо ДО extraction; планировщик не принимает произвольный tar.

## Фиксированная изоляция будущего TEST

- User/group `mcp-rooms-candidate`, unit `mcp-rooms-candidate.service`.
- Read-only application release `/opt/mcp-rooms-candidate/releases/<full-source-SHA>`;
  новый venv внутри. Это не `/home/mcp` и не предыдущий rooms-test checkout.
- Private state parent `/var/lib/mcp-rooms-candidate`0700, новый `owner-first`0700.
- Только127.0.0.1:8766, один worker/upload; no proxy headers/no HTTPS creation/
  no autostart. Resource — отдельный canonical HTTPS audience, не listener URL.
- Fresh-only offline/hash-required install; default rooms-only CLI не меняется.
  Никакой import чужой/live DB, fallback download или promotion recovery outputs.

Ни один из путей/пользователь/unit/порт **не проверен на текущем VPS**. Наличие
плана не означает, что они свободны или что разрешено их создать.

## Observations — входные данные, а не аттестация

Точная bounded JSON shape: platform, absent user/group/четыре fixed paths,
port_free/systemd/python312+venv, Landlock ABI, disk/available RAM. Unknown fields,
truthy non-bool, existing targets, wrong platform, ABI<3, disk<2GiB отказывают.
Это sanity floor диска, НЕ принятая capacity оценка. Low/unknown RAM не становится
успешной resource acceptance: `runtime_resources_accepted=false` всегда.

Любой может написать JSON «порт свободен». Поэтому output ВСЕГДА
`host_probe_performed=false`, `install_authorized=false`,
`observation_authority=caller-supplied-unattested; recheck before every effect`.
Observation digest/plan hash связывают reviewed bytes, но НЕ удостоверяют хост,
время, подпись оператора или его согласие. Installer обязан повторно проверить
identity/absence/port непосредственно перед каждым эффектом; нельзя применять
сохранённый план спустя время как полномочие или объявлять защищённость от TOCTOU.

## Семь описанных стадий, не команды

Preflight → offline_install → bootstrap → loopback_start → health → stop → rollback.
Нет произвольных argv/shell, только typed stage IDs и требования для будущей реализации.
Bootstrap означает отдельное разрешение на настоящий key и приватную выдачу.
Health без ключа не заменяет authenticated MCP/photo/consent/card/withdraw acceptance.
Stop/rollback должны проверять unit/process/path identity и сохранять данные; для
fresh-only установки rollback означает остановить только новый candidate, НЕ
откатить БД/снять публикации/восстановить старый state или удалить неизвестные файлы.

## Actions и незавершённое

Unit tests проверяют deterministic plan/digest, неизменность input, явные false
flags, names/layout/stage order, conflicts/types/fields/resources/trust anchors и
передачу verifier refusal без downgrade. Integration workflow вызывает настоящий
wheelhouse verifier с synthetic-unattested observations; не создаёт accounts/unit.
No real observations/key/state/log uploaded; только прежний public wheelhouse artifact.

Следующий F3c.2b — реализовать lifecycle с fresh/interrupted/stale identity/health/
stop/rollback negative tests, измерить ресурсы/timeout/admission/disk и проверить
на изолированном Actions контуре. Затем новые owner approvals на read-only VPS
preflight, loopback и HTTPS. На каждую remote execution — согласие+спецпароль.
