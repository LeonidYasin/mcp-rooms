# M3a.2 — приватная бинарная загрузка для человека и агента

**CI: [точный принятый SHA и проверки](ci-m3a2.md). Не внешний endpoint и не production.**
Над [staging](media-staging.md) добавлен отдельный opt-in HTTP transport.
Обычный CLI остаётся rooms-only. Даже `market=adapter` не включает загрузку:
нужен явный `create_app(..., market=adapter, media_http=True)` с подготовленными
сервисами/schema. Никаких миграций на запросе или скрытой выдачи marketplace scopes.

## Кто загружает

- **Человек:** будущая браузерная форма выбора файла, использующая этот HTTP API.
  Самой формы, cookie-session/CSRF/onboarding в этом срезе ещё нет.
- **Агент:** тот же HTTP API с принадлежащим пользователю ограниченным Bearer.
  Файл должен реально быть доступен его окружению; подключение MCP не даёт агенту
  доступ к диску человека. Агент без binary HTTP/file capability сможет предложить
  человеку загрузить фото в будущей форме, а затем использовать полученный ID.
- MCP передаёт ID, порядок фотографий и команды черновика, **не base64 изображения**.
  Загрузка по URL, multipart, произвольные пути/имена, прокси чужих сайтов не включены.

## Контракт

`POST /listings/{listing_id}/photos` — только свой редактируемый непубличный черновик.

| Header | Значение |
| --- | --- |
| Authorization | Bearer пользователя с `listings:write` |
| Content-Type | строго `image/jpeg` или `image/png` |
| X-Expected-Revision | текущая положительная revision |
| Idempotency-Key | новый canonical lowercase UUID команды |
| Content-Length | необязателен, но при наличии один и точно соответствует телу |

Body — исходные байты, максимум 8 MiB. Тип подтверждается декодером, не расширением.
Поддержан bounded chunked stream без Content-Length; конфликт CL/TE, дубли и encoding
отклоняются. Реальная защита wire framing/reverse-proxy также требует отдельной
проверки сервера HTTP, это не доказательство отсутствия request smuggling во всей цепи.
Проверка auth/ownership/revision выполняется **до чтения body**, затем повторяется
ядром после чтения и после worker. Таймаут чтения тела 10 секунд.

Новый результат `201`, точный повтор той же команды/байтов `200`, одно и то же
`media_id`, без повторного decode и продления TTL. ID связан с владельцем,
черновиком, revision, resource и policy. Другие байты под тем же UUID — `409`.
Ответ содержит размеры, digest и ID **обработанного JPEG**, но не оригинал,
filesystem path/blob key или ключ доступа. Изображение приватно, не прикреплено
и не опубликовано. Для прикрепления — `listings_set_photos`, затем новый preview
и отдельное согласие на точную публикацию. Окно staging по умолчанию 10 минут.

`GET /listings/{listing_id}/photos/{media_id}` — только свой JPEG с `listings:read`.
Проверяется связь route listing ID с media ID, права и срок до/после filesystem I/O.
Чужой/неизвестный/истёкший/повреждённый объект получает одинаковый `404` без байтов.
Ответ `image/jpeg`, `no-store`, `nosniff`, same-origin resource policy, no-referrer,
CSP sandbox. Секрет не передавать в URL. Public photo route **не** реализован.

## Ограничения и отказы

В одном app/process: максимум 2 upload, 1 на пользователя; 4 preview reads,
2 на пользователя. Без очереди; admission держится от начала чтения до отправки
ответа. Только `media_http_busy` даёт Retry-After: 1. Квоты manifest/files/receipts
нельзя исправить слепым повтором/новым UUID: нужен анализ/проверенная очистка.
Worker failure может оставить terminal reservation, это предусмотрено ядром.

`401` — нет действующей identity; `403` — недостаточный scope/origin; `404` —
объект недоступен; `409` — revision/idempotency/publication conflict; `413` —
размер; `415` — неподдержанный transport MIME/encoding; `408` — медленное тело;
`429` — admission/quota; `503/504` — недоступный/просроченный worker/storage.
Детали ошибок/пути/ключи не копируются в ответ. Query string запрещён общим gate.

Admission **не распределён между процессами**. Максимум 2×8 MiB входов плюс копии,
ASGI buffers, выходы и decoder memory — не жёсткая оценка RAM. Native worker
имеет собственные лимиты и не является полной OS sandbox. Для VPS необходимы
изоляция, профиль CPU/RAM, concurrency/load/reverse-proxy limits, private roots,
DB+files restore и отдельное разрешение владельца. Этот срез их не заменяет.
Не открывать несколько workers/внешний upload до приёмки общей модели лимитов.

## Проверки

[Тесты HTTP](../tests/test_media_http.py) используют синтетические credentials,
ASGI и изображения. План: default-off, auth-before-body, cross-user/route binding,
strict headers, chunk boundaries/length/disconnect/timeout, replay/CAS, revocation
во время body/filesystem I/O, admission release, реальный child worker в CI >=3.11,
MCP attachment/preview. Никаких реальных ключей, фото, DB или VPS в CI.

Следующие слои: browser auth/onboarding, форма/preview, публичная карточка и media
projection с согласованием lifecycle/cache/privacy; приватные отклики и admin MCP.
[Оценка до TEST](deployment-readiness.md) остаётся **6 крупных этапов**: первый
закрывается частями, не уменьшаем число за каждый внутренний адаптер.
