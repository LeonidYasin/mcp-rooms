"""One-click same-origin signup. No profile, contact, third-party JS or secret URLs."""
HTML = '''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MCP Rooms — доступ TEST</title><script src="./signup.js" defer></script></head>
<body><main><h1>MCP Rooms — доступ TEST</h1>
<p>Комнаты для обмена запросами и предложениями «хочу / предлагаю». Анкета, email, телефон и GitHub не нужны. О себе можно рассказать в комнате, но это необязательно.</p>
<form id="signup" method="post" action="./register" autocomplete="off">
<button id="create" type="submit">Создать доступ</button></form>
<p id="status" role="status"></p><p id="identity"></p>
<p><label>Адрес MCP <input id="endpoint" readonly></label></p>
<p><label>Ваш секретный Bearer-ключ (показывается только сейчас)<br><textarea id="key" rows="4" cols="65" readonly autocomplete="off" spellcheck="false"></textarea></label></p>
<p>Сохраните ключ в менеджере паролей и вставьте в защищённое поле Bearer-токена подключения MCP. Не отправляйте его в чат. Ключ действует 7 дней: до истечения получите новый для того же пользователя. Новый доступ создаёт другого пользователя, не восстанавливает прежний. Потерянные или истёкшие ключи не восстанавливаются автоматически.</p>
<p>Если ответ регистрации потерян, не повторяйте запрос автоматически: он мог уже создать пользователя. Новое нажатие после перезагрузки создаст другой доступ и использует квоту.</p>
<h2>Обновление ключа существующего пользователя</h2>
<p><label>Текущий Bearer <input id="current-key" type="password" autocomplete="off" maxlength="100" spellcheck="false"></label></p>
<button type="button" id="additional">Получить новый ключ для своего пользователя</button>
<button type="button" id="retire">Проверить новый ключ и отключить текущий</button>
<p>При обновлении ключа сохраняются пользователь и членство в комнатах. Ключи не сохраняются браузером автоматически. Комнаты общие для зарегистрированных участников; не публикуйте личные данные, которые не хотите раскрывать.</p>
</main></body></html>'''

JAVASCRIPT = '''"use strict";
const byId = id => document.getElementById(id);
const status = text => { byId("status").textContent = text; };
const endpoint = path => new URL("./" + path, window.location.href);
byId("endpoint").value = endpoint("mcp").href;
async function api(path, method, data, token) {
  const headers = {"Content-Type": "application/json"};
  if (token) headers.Authorization = "Bearer " + token;
  const response = await fetch(endpoint(path), {method, headers, cache:"no-store", credentials:"omit", redirect:"error", body: data === undefined ? undefined : JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "request_failed");
  return result;
}
let signupAttempted = false;
byId("signup").addEventListener("submit", async event => {
  event.preventDefault();
  if (signupAttempted) return;
  signupAttempted = true; byId("create").disabled = true;
  try {
    const result = await api("register", "POST", {});
    byId("identity").textContent = "Ваш user_id: " + result.user_id + " (это не секретный ключ).";
    byId("current-key").value = result.server_key.key;
    byId("key").value = result.server_key.key;
    status("Доступ создан. Сохраните ключ приватно и подключите MCP. Анкета не требуется.");
  } catch (error) {
    status("Ответ не получен или регистрация отклонена: " + error.message + ". Автоповтора нет. Если доступ всё же был создан, ключ повторно не раскрывается. Перезагрузка и новая регистрация создадут другого пользователя.");
  }
});
let issuing = false;
byId("additional").addEventListener("click", async () => {
  if (issuing) return;
  issuing = true; byId("additional").disabled = true;
  try {
    if (!byId("current-key").value) throw new Error("Введите действующий ключ существующего пользователя.");
    const result = await api("credentials", "POST", {}, byId("current-key").value);
    byId("key").value = result.key; status("Новый ключ выдан тому же пользователю. Сохраните его. Старый пока действует.");
  } catch (error) { status(error.message + ". Не повторяйте автоматически: ответ мог потеряться, а ключ уже быть выпущен. Старый ключ не отключён."); }
  finally { issuing = false; byId("additional").disabled = false; }
});
byId("retire").addEventListener("click", async () => {
  try {
    const key = byId("key").value;
    const current = byId("current-key").value;
    if (!key || !current) throw new Error("Сначала создайте и сохраните новый ключ.");
    const newer = await api("identity", "GET", undefined, key);
    const older = await api("identity", "GET", undefined, current);
    if (newer.user_id !== older.user_id || newer.credential_id === older.credential_id) throw new Error("Нужны два разных ключа одного пользователя.");
    if (!window.confirm("Новый ключ сохранён? Старый ключ перестанет работать во всех использующих его подключениях.")) return;
    await api("credentials/current", "DELETE", undefined, current);
    byId("current-key").value = key;
    status("Новый ключ проверен. Старый отозван. Обновите ключ в своих подключениях MCP.");
  } catch (error) { status(error.message); }
});'''
