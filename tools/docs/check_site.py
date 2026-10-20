"""CI-only built-site QA; serves static docs, never starts/imports the app."""
from pathlib import Path
from urllib.parse import urlsplit, unquote
from html.parser import HTMLParser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / '.pages-site'
SHOTS = ROOT / '.pages-qa'; SHOTS.mkdir(exist_ok=True)
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag in {'a','script','link','img'}:
            for k in ('href','src'):
                if k in d:self.links.append(d[k])
for f in SITE.rglob('*.html'):
    parser=Links();parser.feed(f.read_text())
    for link in parser.links:
        u=urlsplit(link)
        if u.scheme or u.netloc or link.startswith('#'):continue
        # The only root-relative external base is this project's Pages path.
        path=unquote(u.path)
        if path.startswith('/mcp-rooms/'): target=SITE/path[len('/mcp-rooms/'):]
        elif path.startswith('/'):continue
        else:target=f.parent/path
        if target.is_dir():target=target/'index.html'
        assert target.exists(), ('Broken built link',f,link)
manifest=json.loads((SITE/'version.json').read_text())
assert len(manifest['source_sha']) == 40 and manifest['production'] is False
assert not list(SITE.rglob('*.py')) and not list(SITE.rglob('.env*'))
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(SITE)))
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
    page.emulate_media(reduced_motion='reduce')
    external=[]; errors=[]
    page.on('request',lambda req:external.append(req.url) if not req.url.startswith(base) and not req.url.startswith('data:') else None)
    page.on('pageerror',lambda err:errors.append(str(err)))
    # Exercise every generated page containing authored Mermaid source.
    diagrams=0
    for f in SITE.rglob('*.html'):
        if 'diagram-src' not in f.read_text():continue
        rel=f.relative_to(SITE).as_posix()
        page.goto(base+'/'+rel)
        page.wait_for_function('window.docsDiagrams && window.docsDiagrams.ready',timeout=60000)
        result=page.evaluate('window.docsDiagrams')
        assert not result['errors'],('Diagram render failure',rel,result)
        diagrams+=page.locator('.diagram-frame svg').count()
    assert diagrams>=5,diagrams
    for width,height,label in [(1440,1050,'desktop'),(390,950,'mobile')]:
        page.set_viewport_size({'width':width,'height':height})
        for route,name in [('/','home'),('/map/','map'),('/docs/product-mindmap/','mindmap')]:
            page.goto(base+route)
            page.wait_for_function('window.docsDiagrams && window.docsDiagrams.ready',timeout=60000)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'),(route,width,'page overflow')
            page.screenshot(path=str(SHOTS/f'{name}-{label}.png'),full_page=False)
            if name=='mindmap':
                page.locator('button[data-diagram-scale="actual"]').first.click()
                page.locator('.diagram-frame').first.screenshot(path=str(SHOTS/f'mindmap-zoom-{label}.png'))
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        if label=='mobile':
            page.goto(base+'/')
            page.locator('.md-header label[for="__drawer"]').click()
            page.wait_for_function('document.querySelector(".md-sidebar--primary").getBoundingClientRect().left >= -1')
            page.screenshot(path=str(SHOTS/'menu-mobile.png'),full_page=False)
    page.emulate_media(color_scheme='dark')
    page.goto(base+'/')
    page.wait_for_function('document.body.dataset.mdColorScheme === "slate"')
    page.screenshot(path=str(SHOTS/'home-dark.png'),full_page=False)
    # Built-in local search must return a known document.
    page.set_viewport_size({'width':1440,'height':1050})
    # Fresh page + settled local JS/index, then real keyboard input. A single fill
    # immediately after navigation can precede Material's async subscriptions.
    page.goto(base+'/')
    page.wait_for_load_state('networkidle')
    query = page.locator('input[data-md-component="search-query"]')
    query.focus()
    page.wait_for_load_state('networkidle')
    query.press_sequentially('фотографий', delay=80)
    try:
        page.wait_for_function('document.querySelectorAll(".md-search-result__link").length > 0',timeout=30000)
    except Exception:
        page.screenshot(path=str(SHOTS/'search-failure.png'),full_page=False)
        (SHOTS/'search-failure.txt').write_text(page.locator('.md-search').inner_text())
        raise
    page.screenshot(path=str(SHOTS/'search.png'),full_page=False)
    browser.close()
server.shutdown()
assert not external,('Unexpected external browser requests',external[:8])
assert not errors,errors[:8]
print('DOCS QA PASS:',diagrams,'diagrams; local links/assets; mobile overflow; search; screenshots')
