# F3c.2d.1 — seccomp probe correction: exact-SHA CI evidence

## Итог

Срез принят как **CI**, не как VPS TEST и не как production. На реальном VPS
исправленная проверка ещё не запускалась.

- Source SHA: `e6116aeff40d0128de90e36ab1b4045d2f8082e1`
- Branch: `feat/standalone-identity`
- CI workflow run: `39823990594`
- Python3.12: **991 passed, 2 warnings**; 3.10–3.13 jobs success.

## Причина исправления

Первый read-only preflight на VPS (`docs/preflight-vps-2026-10-22.md`) дал
`preflight_seccomp_unavailable`, хотя ядро 6.8 KVM поддерживает seccomp.
Проверка ошибочно требовала строку `filter` в
`/proc/sys/kernel/seccomp/actions_avail`. Этот файл перечисляет *действия*
(`kill_process`, `kill_thread`, `trap`, `errno`, `user_notif`, `trace`, `log`,
`allow`); `filter` — это режим seccomp, а не action, поэтому проверка не могла
пройти ни на одном современном ядре.

## Что изменено

- `actions_avail` проверяется на реальные действия `kill_process` и `errno`.
- Добавлена живая проба: в forked child выставляется `PR_SET_NO_NEW_PRIVS` и
  устанавливается allow-all BPF-фильтр через `SECCOMP_SET_MODE_FILTER`. Успех
  доказывает поддержку filter-режима; родительский процесс и хост не меняются.
- Тесты используют реальный список действий (регрессия на отсутствие `filter`),
  проверяют отсутствие обязательных действий, сбой пробы и реальную установку
  фильтра на Linux x86_64.

## Сохранённый красный прогон

На `defc9d7` CI упал: проба запускалась без root и без `no_new_privs`, ядро
вернуло EPERM. Исправление `e6116ae` добавляет `PR_SET_NO_NEW_PRIVS` только в
дочернем процессе. Проверка не ослаблена: seccomp-фильтр по-прежнему реально
устанавливается.

## Что это не доказывает

- На момент CI-приёмки исправленная проба на VPS не запускалась; последующий
  прогон после апгрейда RAM — PASS
  ([отчёт](preflight-vps-2026-10-22-4gb.md)).
- Реальная runtime capacity, native-нагрузка и HTTPS этим не подтверждены.
- Нет разрешения на install/bootstrap/loopback/HTTPS, merge/release/production.

## Следующий gate

`OWNER-FIRST-VPS-PREFLIGHT` завершён (STOP на 2 GiB, затем PASS на 4 GiB).
Далее — отдельно разрешённая fresh install/bootstrap/start и loopback acceptance.
PASS preflight не разрешает установку.
