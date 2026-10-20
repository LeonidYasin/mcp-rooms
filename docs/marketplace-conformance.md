# Marketplace conformance: общий контракт приёмки

Статус: спецификация будущих интеграционных/негативных тестов, **не исполняемый тестовый
набор и не PASS-отчёт**. Применима к собственному ядру или adapter внешнего движка.
Связь: [ADR-001](decisions/001-marketplace-foundation.md).

## Фикстуры и наблюдаемость

Изолированная временная БД и media root, управляемые clock/IDs, два обычных actor A/B,
два credentials A1/A2 одного actor, credential B1 другого actor, expired/revoked key,
admin observer/moderator с отдельной audience. Никаких реальных ключей/контактов/VPS.
Browser write требует session+CSRF; MCP write — scoped Bearer. Формат transport ошибок
может отличаться, но эффект/доступ к данным и запрет утечек должны совпадать.

Не задавать actor/owner из пользовательских аргументов. Сравнивать результаты через
наблюдаемый API/read model, а не зависеть от WP post IDs/имён таблиц. Для atomicity
допустим отдельный storage adapter test с barrier/fault injection.

| ID | Действие / граница | Ожидаемый проверяемый результат |
| --- | --- | --- |
| ID-01 | Signup без email/phone/GitHub | Новый stable actor и отдельный секрет, нет обязательных контактов; signup явно включён и ограничен |
| ID-02 | A1 и A2 действуют от одного actor | Одинаковое ownership; отзыв A1 не отнимает ресурсы/доступ A2 |
| ID-03 | Revoked/expired/disabled credential пишет | Отказ до мутации; остальные пользователи не затронуты |
| L-01 | A создаёт draft, anonymous/B ищут/читают | Draft не выдаётся, не утекли title/media/существование; A читает свой |
| L-02 | B изменяет/снимает объект A, подставляет owner A | Отказ; content/revision/state A неизменны |
| L-03 | Два update с одной expected_revision | Ровно один commit, другой conflict; нет lost update |
| L-04 | Retry той же команды/actor/client key и payload | Тот же результат без дубля/второй мутации; changed payload с тем же key — conflict |
| L-05 | Idempotency в конкурентных запросах | Ровно одна effect transaction; проверены scope actor/op и атомарность retry record |
| P-01 | Publish без consent или для другой revision | Отказ; скрытый draft не попадает в public index/media |
| P-02 | Preview→изменение→publish со старым consent | Conflict/new preview; подтверждение связывается с содержимым/версией, а не глобальным bool |
| P-03 | Явный publish текущей версии | Stable URL, одна public projection, только разрешённые поля |
| P-04 | Pause/expire/fulfilled/blocked | Нет в активном search; прежняя ссылка не раскрывает закрытые данные; поведение страницы статуса определено |
| M-01 | A использует private media B / arbitrary path/URL | Отказ; нет fetch чужой сети/файлов, никаких credentials в URL |
| M-02 | Файл с ложным MIME, повреждённый, oversized bytes/pixels/count | Отказ до публикации; лимиты CPU/memory/файлов и cleanup проверены |
| M-03 | EXIF/GPS, SVG/script, polyglot/image metadata | Только выбранные decoded/re-encoded форматы, EXIF отсутствует, active content не исполняется |
| M-04 | Crash/rollback между upload и listing commit | Нет публичного private объекта, orphan cleanup не удаляет referenced media |
| W-01 | Один listing меняют web и MCP | Одна revision/history/ownership policy, обе стороны читают committed результат |
| W-02 | CSRF, session fixation/revoke/expiry, XSS в тексте | Нет несанкционированного write; escaped output; Secure/HttpOnly/SameSite; ключи не в frontend storage |
| S-01 | Anonymous search/category/pagination/locality | Только active public, bounded stable paging; география не условие account admission |
| R-01 | B отвечает A; третий actor/anonymous читает | Только участники response видят содержание; public room не используется как private response |
| R-02 | Включён web; старые shared rooms существуют | Их история не индексируется/не публикуется; schema/TTL/API совместимы |
| A-01 | User key→admin; admin key→user; observer mutation | Audience/role denial; admin tools отсутствуют в user tools/list |
| A-02 | Ошибка permission checker/storage | Fail closed, без частичного write и повышения полномочий |
| A-03 | Hide/restore/report resolution | Reason/actor/revision/audit связаны атомарно; модератор не переписывает текст автора |
| A-04 | Confirmation replay/expired/changed target/actor/args | Нет effect; только точный одноразовый план проходит при актуальных правах |
| O-01 | Backup→новый isolated restore→integrity/counts | Live DB не перезаписана, credentials не раскрыты; восстановление не считается безопасным без revoke reconciliation |
| O-02 | SQL busy/full, media quota, restart, logs | Bounded errors/retry, нет частичной публикации и секретов; disk/memory/time budgets измерены |
| E-01 | Реальный товар/фото/цена/условия от владельца | Не demo, нет выдуманных дефектов/исправности/спроса; preview и consent получены |
| E-02 | Другой человек находит ссылку и отправляет ответ | Реальный read/response через согласованный TEST; факт продажи отдельно подтверждает продавец |

## Правило отчёта

Для каждого ID фиксировать version SHA, transport, fixture, observed result и evidence.
Допустимые статусы: NOT IMPLEMENTED / NOT RUN / PASS / FAIL / BLOCKED, не «готово по README».
Первая публикация в публичный TEST допускается только после обязательных auth/ACL,
consent/media/session/admin isolation gates; наличие пилотных room PASS не переносится
на новые ресурсы. Имена будущих методов и публичных URL определяются реализацией;
этот документ не выдаёт несуществующие API за рабочие команды.
