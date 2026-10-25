"""Opt-in, anonymous GET-only card + read-only market index; no credentials, mutation or startup DDL."""
from functools import partial
from html import escape
from hashlib import sha256
from base64 import b64encode
import re
import threading
import time
from urllib.parse import urlsplit
import anyio
from starlette.responses import Response
from .domain import DomainError
from .media_http import Admission, HTTPFailure, UUID

ROUTE = re.compile(r'/market/(' + UUID + r')(?:/photos/([1-9][0-9]{0,18})/(' + UUID + r')\.jpg)?')
CSS = """*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:#172330;font:17px/1.6 system-ui,sans-serif}header,main,footer{max-width:1080px;margin:auto;padding:24px}header{font-weight:750}header span{color:#49657f}article{background:white;border:1px solid #dce3eb;border-radius:22px;padding:clamp(20px,4vw,48px)}h1{font-size:clamp(28px,5vw,48px);line-height:1.15;overflow-wrap:anywhere}h2{font-size:22px}.badge{display:inline-block;color:#096145;background:#e1f4ec;border-radius:8px;padding:4px 12px}.price{font-size:32px;font-weight:750}.location,.category,.author,footer{color:#526477}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:16px}.gallery img{display:block;width:100%;height:auto;max-height:600px;object-fit:contain;background:#f5f7fa;border-radius:12px}.description{white-space:pre-wrap;overflow-wrap:anywhere}.notice{background:#eef4fb;border-radius:12px;padding:18px;margin-top:28px}footer{font-size:14px}a{color:#165ca5}.sections{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px}.sections a{background:#eef4fb;border-radius:999px;padding:6px 14px;color:#165ca5;text-decoration:none;font-size:14px}.index{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));gap:16px}.index li{background:white;border:1px solid #dce3eb;border-radius:16px;padding:18px}.index a.cardlink{font-size:20px;color:#165ca5;text-decoration:none}.index .meta{color:#526477;margin-top:8px}@media(prefers-color-scheme:dark){body{background:#111923;color:#eef5fc}article{background:#1b2735;border-color:#34465a}.location,.category,.author,footer{color:#bbc9d8}.notice{background:#253b51}.gallery img{background:#14202e}.index li{background:#1b2735;border-color:#34465a}.index a.cardlink{color:#9ec7f5}.index .meta,.sections a{color:#bbc9d8}.sections a{background:#253b51}}}"""
STYLE_HASH = b64encode(sha256(CSS.encode()).digest()).decode('ascii')
HEADERS = {'Cache-Control':'no-store','Pragma':'no-cache',
    'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
    'X-Robots-Tag':'noindex, nofollow, noarchive',
    'Cross-Origin-Resource-Policy':'same-origin',
    'Content-Security-Policy':"default-src 'none'; img-src 'self'; style-src 'sha256-"+STYLE_HASH+"'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"}


def render_card(card, prefix):
    """Escape untrusted plain text; never turn participant text into HTML or links."""
    e=lambda v: escape(str(v),quote=True)
    title=e(card['title'])
    amount=card['price_minor']
    price=('Цена по договорённости' if amount is None else
           f"{amount//100:,}".replace(',', ' ')+(f",{amount%100:02d}" if amount%100 else '')+' '+e(card['currency']))
    location=' · '.join(e(card[k]) for k in ('locality','region','country') if card[k])
    gallery=''.join('<img loading="lazy" decoding="async" src="'+prefix+'/market/'+e(card['id'])+
        '/photos/'+str(card['publication_revision'])+'/'+e(p['media_id'])+'.jpg" alt="Фото '+str(i)+' объявления">'
        for i,p in enumerate(card['photos'],1))
    categories=' → '.join(e(p['title']) for p in card['category_path'])
    modes=' · '.join({'pickup':'Самовывоз','shipping':'Доставка','online':'Онлайн'}[m] for m in card['modes'])
    kind='Предлагаю' if card['kind']=='offer' else 'Ищу'
    return ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+
        ' — Хочу · Предлагаю</title><style>'+CSS+'</style></head><body>'
        '<header>Хочу <span>·</span> Предлагаю <span> / TEST</span></header><main><article>'
        '<div class="category">Раздел: '+categories+'</div><p class="badge">'+kind+'</p><h1>'+title+
        '</h1><p class="author">Автор: '+e(card['author'])+'</p><p class="location">'+location+'</p><p class="price">'+price+'</p><p>'+modes+'</p><div class="gallery">'+
        (gallery or '<p>Фотографии не добавлены.</p>')+'</div><h2>Описание и условия</h2>'
        '<div class="description">'+e(card['description'])+'</div><aside class="notice">'
        'Тестовая площадка. Встроенная переписка, оплата и гарантии сделки пока недоступны. '
        'Связь возможна только способом, который автор явно указал в описании. '
        'Не передавайте ключи доступа и не переводите предоплату незнакомцам.</aside></article></main>'
        '<footer>MCP Rooms · MIT. Данные объявления предоставлены автором. '
        'Публикация не означает проверку товара или продавца.</footer></body></html>')


def _price(item):
    amount = item.get('price_minor')
    if amount is None:
        return 'Цена по договорённости'
    currency = item.get('currency') or ''
    return f"{amount//100:,}".replace(',', ' ') + (f",{amount%100:02d}" if amount % 100 else '') + ' ' + currency


def render_index(index, prefix):
    """Read-only market navigation: sections and published cards, fully escaped."""
    e = lambda v: escape(str(v), quote=True)
    seen = {}
    for item in index['items']:
        top = (item.get('category_path') or [{}])[0]
        key = top.get('id') if isinstance(top, dict) else None
        seen.setdefault(key, [top.get('title') if isinstance(top, dict) else 'Разное', 0])
        seen[key][1] += 1
    sections = ''.join(
        '<a class="section" href="' + e(prefix + '/market') + '">' + e(title) + ' (' + str(n) + ')</a>'
        for title, n in [v for v in seen.values()] if v[1])
    cards = ''
    for item in index['items']:
        cats = ' → '.join(e(p.get('title', '')) for p in (item.get('category_path') or []) if isinstance(p, dict))
        modes = ' · '.join({'pickup': 'Самовывоз', 'shipping': 'Доставка', 'online': 'Онлайн'}[m] for m in item.get('modes', []) if m in {'pickup', 'shipping', 'online'})
        cards += ('<li><a class="cardlink" href="' + e(prefix + '/market/' + item['id']) + '">'
                  '<strong>' + e(item.get('title', '')) + '</strong></a>'
                  '<div class="meta">' + e(item.get('author', '')) + ' · ' + e(cats) +
                  ' · ' + e(_price(item)) + '</div>'
                  '<div class="meta">' + e(modes) + '</div></li>')
    body = ('' if cards else '<p>Пока опубликованных объявлений нет.</p>')
    return ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>'
            'Рынок — Хочу · Предлагаю</title><style>' + CSS + '</style></head><body>'
            '<header>Хочу <span>·</span> Предлагаю <span> / TEST</span></header><main>'
            '<h1>Что предлагают и ищут</h1><p class="sections">' + sections + '</p>'
            '<ul class="index">' + cards + '</ul><aside class="notice">'
            'Тестовая площадка. Встроенная переписка, оплата и гарантии сделки пока недоступны. '
            'Не передавайте ключи доступа и не переводите предоплату незнакомцам.</aside></main>'
            '<footer>MCP Rooms · MIT. Показаны только явно опубликованные объявления.</footer></body></html>')


class PublicMarket:
    def __init__(self,publisher,resource):
        self.publisher=publisher
        url=urlsplit(resource)
        self.authority,self.prefix=url.netloc,url.path[:-4]
        self.admission=Admission(2,2)
        self.lock=threading.Lock()
        self.window,self.count=0,0

    @staticmethod
    def match(path):
        return path=='/market' or path.startswith('/market/')

    def budget(self):
        # Fixed global process window; no attacker-controlled IP/owner map.
        with self.lock:
            window=int(time.monotonic()//60)
            if window!=self.window:self.window,self.count=window,0
            if self.count>=120:raise HTTPFailure('public_busy',429)
            self.count+=1

    async def handle(self,scope,receive,send):
        async def reply(data,status=200,media='text/plain',extra=None):
            await Response(data,status_code=status,media_type=media,
                           headers={**HEADERS,**(extra or {})})(scope,receive,send)
        hosts=[v.decode('latin1') for k,v in scope.get('headers',[]) if k.lower()==b'host']
        if hosts!=[self.authority]:return await reply('Invalid host',421)
        if scope['method']!='GET':return await reply('Method not allowed',405,extra={'Allow':'GET'})
        path=scope['path']
        is_index=path=='/market' or path=='/market/'
        route=None if is_index else ROUTE.fullmatch(path)
        if not is_index and route is None:return await reply('Объявление недоступно',404)
        started=False
        async def tracked(message):
            nonlocal started
            if message['type']=='http.response.start':started=True
            await send(message)
        try:
            self.budget()
            with self.admission.slot('public'):
                if is_index:
                    index=await anyio.to_thread.run_sync(self.publisher.public_index)
                    data,media=render_index(index,self.prefix),'text/html'
                else:
                    lid,epoch,mid=route.groups()
                    if mid is None:
                        card=await anyio.to_thread.run_sync(self.publisher.public_get,lid)
                        data,media=render_card(card,self.prefix),'text/html'
                    else:
                        data=await anyio.to_thread.run_sync(partial(self.publisher.public_photo,lid,int(epoch),mid))
                        media='image/jpeg'
                # Hold admission through bounded sending; no second response after start.
                with anyio.fail_after(10):
                    await Response(data,media_type=media,headers=HEADERS)(scope,receive,tracked)
        except Exception as exc:
            if started:raise
            if isinstance(exc,DomainError):return await reply('Объявление недоступно',404)
            if isinstance(exc,HTTPFailure):return await reply('Попробуйте позже',429,extra={'Retry-After':'60'})
            return await reply('Временно недоступно',503)
