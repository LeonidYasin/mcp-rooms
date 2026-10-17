"""Minimal same-origin enrollment UI. No third-party scripts, trackers, or secrets in URLs."""
HTML = '''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MCP Rooms — регистрация TEST</title><script src="./signup.js" defer></script></head>
<body><main><h1>MCP Rooms — регистрация TEST</h1>
<p>Закрытый тест. Email/телефон не подтверждаются и не сохраняются. Секретом доступа является UUID, а не контакт. Это не восстановление по email и не подтверждение личности.</p>
<form id="signup" method="post" action="./register" autocomplete="off">
<p><label>Email или телефон в международном формате <input id="contact" name="contact" maxlength="254" required autocomplete="off"></label></p>
<p><label>Ваш секретный случайный UUIDv4 <input id="uuid" name="bootstrap_uuid" type="password" required autocomplete="new-password" maxlength="36" spellcheck="false"></label> <button type="button" id="generate">Сгенерировать UUID на этом устройстве</button></p>
<p>Не используйте пример из документации, ID комнаты или предсказуемый UUID. Не отправляйте UUID в чат.</p>
<p><label><input type="checkbox" id="server-key" checked>Получить также новый 256-битный серверный ключ</label></p>
<button type="submit">Создать пользователя</button></form>
<p id="status" role="status"></p><p id="identity"></p>
<p>Вы можете использовать свой UUID как Bearer или серверный ключ ниже. Оба действуют 7 дней; старый ключ не отключается автоматически. Создайте и сохраните новый ключ до истечения срока. Email не восстановит утраченный доступ.</p>
<p><label>Серверный Bearer-ключ (показывается только сейчас)<br><textarea id="key" rows="4" cols="65" readonly autocomplete="off" spellcheck="false"></textarea></label></p>
<p><label>Текущий Bearer для управления ключами <input id="current-key" type="password" autocomplete="off" maxlength="100" spellcheck="false"></label></p>
<button type="button" id="additional">Получить новый ключ для своего пользователя</button>
<button type="button" id="retire">Проверить новый ключ и отключить текущий</button>
<p>Ключ копируется только в защищённое поле подключения MCP. Переписки общие для зарегистрированных участников; личные данные в них не публикуйте.</p>
</main></body></html>'''

JAVASCRIPT = '''"use strict";
const byId = id => document.getElementById(id);
const status = text => { byId("status").textContent = text; };
const endpoint = path => new URL("./" + path, window.location.href);
async function api(path, method, data, token) {
  const headers = {"Content-Type": "application/json"};
  if (token) headers.Authorization = "Bearer " + token;
  const response = await fetch(endpoint(path), {method, headers, cache:"no-store", credentials:"omit", redirect:"error", body: data === undefined ? undefined : JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "request_failed");
  return result;
}
byId("generate").addEventListener("click", () => {
  if (!window.crypto || !window.crypto.randomUUID) { status("Нужен HTTPS и браузер с crypto.randomUUID()."); return; }
  byId("uuid").value = window.crypto.randomUUID(); status("UUID создан на вашем устройстве. Сохраните его приватно.");
});
byId("signup").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const result = await api("register", "POST", {contact:byId("contact").value, bootstrap_uuid:byId("uuid").value, issue_server_key:byId("server-key").checked});
    byId("identity").textContent = "Ваш user_id: " + result.user_id + ". Контакт НЕ подтверждён и НЕ сохранён.";
    byId("current-key").value = byId("uuid").value;
    if (result.server_key) byId("key").value = result.server_key.key;
    status(result.already_registered ? "UUID уже зарегистрирован. Ранее выданный серверный ключ повторно не раскрывается; можно выпустить новый." : "Пользователь создан. Сохраните ключи приватно, не в чате.");
  } catch (error) { status(error.message); }
});
byId("additional").addEventListener("click", async () => {
  try {
    const result = await api("credentials", "POST", {}, byId("current-key").value || byId("uuid").value);
    byId("key").value = result.key; status("Новый ключ выдан. Исходный UUID пока действует.");
  } catch (error) { status(error.message); }
});
byId("retire").addEventListener("click", async () => {
  try {
    const key = byId("key").value;
    const current = byId("current-key").value || byId("uuid").value;
    if (!key || !current) throw new Error("Сначала создайте, скопируйте и сохраните новый серверный ключ.");
    const newer = await api("identity", "GET", undefined, key);
    const older = await api("identity", "GET", undefined, current);
    if (newer.user_id !== older.user_id || newer.credential_id === older.credential_id) throw new Error("Нужны два разных ключа одного пользователя.");
    await api("credentials/current", "DELETE", undefined, current);
    byId("current-key").value = key;
    byId("uuid").value = "";
    status("Серверный ключ проверен. Исходный UUID отозван. Сохраните серверный ключ — email не восстанавливает доступ.");
  } catch (error) { status(error.message); }
});'''
