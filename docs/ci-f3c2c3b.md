# F3c.2c.3b — guarded lifecycle controller: exact-SHA CI evidence

## Итог

Срез принят как **CI**, не как VPS TEST и не как production.

- Source SHA: `88eabfb35aa7cc763d85352e3e67a48e9d5fb97f`
- Branch: `feat/standalone-identity`
- PR: `#1` (draft)
- CI workflow run: `39625696177`
- Operator supervision run: `39625696463`

## Что проверено

- Python 3.10–3.13 jobs завершились успешно.
- Build wheel/sdist и installed-wheel import завершились успешно.
- Installed owner-first candidate smoke завершился успешно на Python >=3.11.
- Реальный disposable systemd/cgroup fixture завершился успешно.
- `tools/operator_control.py` требует отдельную authorization phrase для bootstrap/start.
- Controller не читает и не возвращает `owner.key`.
- Bootstrap работает только с валидной fresh install и блокирует повтор/partial state.
- Start перепроверяет install, account, paths, unit/drop-ins и inactive process identity
  непосредственно перед эффектом.
- Занятый порт не освобождается насильно и чужой listener сохраняется.
- Прерванный start останавливает только подтверждённую собственную cgroup; при
  невозможности безопасной очистки требуется ручной разбор.
- Stop отказывается при unit/drop-in/process drift и сохраняет private state.
- Приняты явные минимальные runtime/disk/inode/retention критерии; их нарушение
  возвращает typed failure.
- Existing candidate-in-unit native photo/publication/withdraw/restart scenario повторно
  проходит через новый controller.

## Что это не доказывает

- Порог `MemoryMax=1 GiB` и измерения Actions не доказывают достаточность конкретного VPS.
- Нет разрешения на запуск controller на VPS.
- Не создан реальный профиль и не выдан реальный ключ.
- Не проверены внешний HTTPS, реальный MCP-клиент или пользовательская публикация.
- Не разрешены merge/main/release/production.

## Следующий gate

Отдельно разрешённый fresh read-only VPS preflight, затем isolated loopback TEST и
только после его приёмки — отдельно разрешённый HTTPS/external-client TEST.
