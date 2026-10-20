"""Prepare a public docs-only tree. Never import or start the Rooms application."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit
from html import escape
import json
import os
import posixpath
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / '.pages-src'
REPO = 'https://github.com/LeonidYasin/mcp-rooms'
SHA = os.environ.get('GITHUB_SHA', '')
REF = os.environ.get('GITHUB_REF_NAME', '')
assert re.fullmatch('[0-9a-f]{40}', SHA), 'Exact source GITHUB_SHA required'
assert REF and len(REF) < 200
REGISTRY = json.loads((ROOT / 'docs/project-status.json').read_text())
assert REGISTRY['schema'] == 1
NODES = REGISTRY['components']
IDS = {n['id'] for n in NODES}
assert len(IDS) == len(NODES)
for n in NODES:
    assert re.fullmatch('[a-z][a-z0-9_]*', n['id'])
    assert n['stage'] in {'SPEC', 'SOURCE', 'CI', 'TEST'}
    assert len(n['title']) <= 80 and len(n['summary']) <= 500
    assert set(n['depends_on']) <= IDS and n['id'] not in n['depends_on']
    for key in ('doc', 'source', 'evidence'):
        if n[key]:
            f = ROOT / n[key]
            assert f.is_file() and not f.is_symlink() and f.resolve().is_relative_to(ROOT)
    if n['stage'] in {'CI', 'TEST'}:
        assert n['source'] and n['evidence']
visited, active = set(), set()
def visit(i):
    assert i not in active, 'Dependency cycle'
    if i in visited: return
    active.add(i)
    for d in next(n for n in NODES if n['id'] == i)['depends_on']: visit(d)
    active.remove(i); visited.add(i)
for i in IDS: visit(i)

# Only explicitly public Markdown and assets; never recursively publish repository.
paths = [Path('README.md'), Path('ROADMAP.md'), Path('clients/qwen/README.md')]
paths += sorted(Path('docs').rglob('*.md'))
assert not any((ROOT / f).is_symlink() for f in paths)
assert not DEST.is_symlink()
if DEST.exists(): shutil.rmtree(DEST)
DEST.mkdir()
allowed = {str(f) for f in paths}
site_paths = {str(f): (f.parent / 'overview.md').as_posix() if f.name == 'README.md' else f.as_posix() for f in paths}
manifest = []

def provenance(path):
    exact = REPO + '/blob/' + SHA + '/' + quote(path, safe='/')
    history = REPO + '/commits/' + quote(REF, safe='') + '/' + quote(path, safe='/')
    return ('\n\n---\n\n**Версия этой страницы:** `' + SHA[:12] + '` · '
            + '[Исходник этой версии](' + exact + ') · [История изменений](' + history + ')\n')

for f in paths:
    data = (ROOT / f).read_bytes()
    text = data.decode('utf-8')
    # Link targets outside the published set resolve to exact-SHA source, not a
    # mutable branch or a copy of secrets, scripts, env, DB, upstream snapshots.
    def link(match):
        label, target = match.group(1), match.group(2)
        u = urlsplit(target)
        if u.scheme or u.netloc or target.startswith('#'): return match.group(0)
        raw = (ROOT / f.parent / u.path).resolve()
        assert raw.is_relative_to(ROOT), ('Escaping link', f, target)
        rel = raw.relative_to(ROOT).as_posix()
        assert raw.exists(), ('Broken local doc link', f, target)
        if rel in allowed:
            dest = posixpath.relpath(site_paths[rel], posixpath.dirname(site_paths[str(f)]) or '.')
            if u.fragment: dest += '#' + u.fragment
            return '[' + label + '](' + dest + ')'
        assert not raw.is_symlink()
        dest = REPO + ('/tree/' if raw.is_dir() else '/blob/') + SHA + '/' + quote(rel, safe='/')
        if u.fragment: dest += '#' + u.fragment
        return '[' + label + '](' + dest + ')'
    text = re.sub(r'\[([^]\n]+)\]\(([^)\s]+)\)', link, text)
    out = DEST / site_paths[str(f)]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + provenance(str(f)))
    manifest.append({'path':str(f), 'sha256':sha256(data).hexdigest()})

# Static home: honest state, short paths into canonical docs, no app signup/API.
home = """# Рынок возможностей из вашего чата с ИИ

<div class="hero-note">MCP Rooms · «Хочу — Предлагаю» · открытая разработка</div>

Люди через web, агенты через MCP. Вещи и услуги сначала; работа, команды, проекты
и партнёрства — следующие направления. Это **сайт документации**, не работающий
маркетплейс и не регистрация пользователей.

<div class="state-note"><strong>Alpha, не production.</strong> Комнаты проверены в прежнем пилоте;
ядро объявлений, фото и opt-in user MCP — в CI. Default CLI остаётся rooms-only; Rooms TEST остановлен.
Публичная публикация объявлений ещё не работает.</div>

## От идеи — к работающей площадке

<div class="entry-grid">
<a class="entry-card" href="map/"><span>01 / КАРТА</span><strong>Что уже есть и что дальше</strong><p>Компоненты, зависимости, границы и доказательства.</p></a>
<a class="entry-card" href="docs/opportunity-model/"><span>02 / ЗАМЫСЕЛ</span><strong>Не только вещи</strong><p>Услуги, работа, команды, проекты и партнёры — без раздувания MVP.</p></a>
<a class="entry-card" href="docs/delivery-plan/"><span>03 / ПЛАН</span><strong>Путь к первой публикации</strong><p>Фото, согласие, карточка, приватный отклик и отдельное администрирование.</p></a>
</div>

## Быстрый ориентир

| Слой | Честный статус | Подробности |
| --- | --- | --- |
| Rooms / identity / Qwen | Исторический TEST; сейчас остановлен | [Пилот](docs/acceptance-2026-10-19.md) |
| Приватные черновики и intent | SOURCE + CI, не публичный API | [Контракт](docs/publication-intent.md) |
| Нормализация фото | SOURCE + CI, не публичная загрузка | [Лимиты и границы](docs/media-image-safety.md) |
| Публикация и user MCP | CI, явный opt-in; default CLI rooms-only | [Проверки](docs/ci-m3a1.md) |
| Private photo HTTP | CI, opt-in; общий transport для человека и агента, пока без формы | [Проверки](docs/ci-m3a2.md) |
| Web/onboarding, приватный отклик, admin MCP | SPEC / следующий этап | [Карта](map.md) |
| Main / production | Не выпуск этой alpha-ветки | [Состояние репозитория](overview.md) |

## Версия, которую вы читаете

"""
home += ('Снимок исходников **`' + SHA[:12] + '`**, канал **development**, ref **`' + REF + '`**. '
         'Каждая страница связана с точным коммитом и историей Markdown. '
         '«Последняя документация» не означает «последний успешный runtime CI» или работающий сервер.\n\n'
         '[Правила обновления и версий](docs/documentation-site.md) · '
         '[Machine-readable version manifest](version.json) · '
         '[Репозиторий](' + REPO + ') · [PR #1](' + REPO + '/pull/1)\n')
(DEST / 'index.md').write_text(home + provenance('tools/docs/prepare.py'))

text = '# Подробная карта проекта\n\n'
text += 'Карта собрана из [единого реестра](' + REPO + '/blob/' + SHA + '/docs/project-status.json). '
text += 'Зависимость — требование к будущей интеграции, не свидетельство готовности.\n\n'
text += '**SPEC** — спроектировано; **SOURCE** — код без принятого CI; **CI** — тесты конкретного SHA; '
text += '**TEST** — историческая изолированная проверка. Ни один статус не означает PROD.\n\n'
text += '[Продуктовая mindmap](docs/product-mindmap.md) · [Архитектура и ER](docs/architecture-graph.md) · [Roadmap](ROADMAP.md)\n\n'
text += '## Компоненты и доказательства\n\n<div class="component-grid">\n'
for n in NODES:
    docurl = site_paths[n['doc']][:-3] + '/'
    text += '<section class="component-card" id="' + n['id'] + '"><span class="stage stage-' + n['stage'].lower() + '">' + n['stage'] + '</span><h3>' + escape(n['title']) + '</h3><p>' + escape(n['summary']) + '</p>'
    text += '<a href="../' + docurl + '">Контракт и документация</a>'
    if n['source']: text += ' · <a href="' + REPO + '/blob/' + SHA + '/' + quote(n['source']) + '">Код версии</a>'
    if n['evidence']: text += ' · <a href="../' + n['evidence'][:-3] + '/">Evidence</a>'
    if n['depends_on']: text += '<p class="depends">Зависит от: ' + ', '.join('<a href="#' + d + '">' + escape(next(x['title'] for x in NODES if x['id']==d)) + '</a>' for d in n['depends_on']) + '</p>'
    text += '</section>\n'
text += '</div>\n\n## Граф зависимостей\n\n```mermaid\nflowchart TD\n'
for n in NODES:
    text += '  ' + n['id'] + '["' + n['title'] + ' · ' + n['stage'] + '"]\n'
    for d in n['depends_on']: text += '  ' + d + ' --> ' + n['id'] + '\n'
text += '```\n\nГраф показывает порядок интеграции. Подробные data/trust/sequence diagrams — в [архитектуре](docs/architecture-graph.md) и [storage design](docs/draft-storage-design.md).\n'
(DEST / 'map.md').write_text(text + provenance('docs/project-status.json'))
assets = ROOT / 'docs/site-assets'
for f in assets.iterdir():
    assert f.is_file() and not f.is_symlink()
    out = DEST / 'assets' / f.name
    out.parent.mkdir(exist_ok=True);out.write_bytes(f.read_bytes())
(DEST / 'version.json').write_text(json.dumps({'schema':1,'source_sha':SHA,'source_ref':REF,
    'channel':'development','built_at':datetime.now(timezone.utc).isoformat(),
    'production':False,'documents':manifest},ensure_ascii=False,indent=2))
(DEST / '.nojekyll').touch()
print('Prepared public docs:', len(paths), 'Markdown sources;', len(NODES), 'components; SHA', SHA)
