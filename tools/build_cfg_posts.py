#!/usr/bin/env python3
"""Render the two CFG articles; optionally sync canonical sources from their code repo."""
from pathlib import Path
import argparse
import hashlib
from html import escape
import json
import math
import re
import shutil
import markdown

ROOT = Path(__file__).resolve().parents[1]
POSTS = [
    {'source': '01-tactic-cfg.md', 'slug': '2026-08-22-lean-tactic-language-cfg',
     'description': "A practical study of Lean's tactic language: extracting tactic forms from real proofs, designing a grammar around them, and stress-testing what the grammar accepts and rejects."},
    {'source': '02-constrained-decoding.md', 'slug': '2026-08-22-grammar-constrained-decoding-lean',
     'description': 'A study of how grammar masking keeps language-model generations inside the shape of Lean tactics, preventing malformed proof steps without confusing valid syntax with proof correctness.'},
]
CODE = 'https://github.com/stanleyngugi/ai-proof-grammars'
BASE = 'https://stanleyngugi.netlify.app'
MODIFIED = '2026-10-06'
REVISION = 'October 6, 2026'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, help='Companion repository; sync its articles and assets first')
    args = ap.parse_args()
    (ROOT/'content').mkdir(exist_ok=True)
    (ROOT/'assets/cfg').mkdir(parents=True, exist_ok=True)
    if args.source:
        for post in POSTS:
            shutil.copyfile(args.source/'articles'/post['source'], ROOT/'content'/post['source'])
        for asset in (args.source/'articles/assets').glob('*.svg'):
            shutil.copyfile(asset, ROOT/'assets/cfg'/asset.name)
    manifests = {}
    index = (ROOT/'index.html').read_text()
    rss = (ROOT/'rss.xml').read_text()
    for post in POSTS:
        source = ROOT/'content'/post['source']
        text = source.read_text()
        title, body = text.split('\n', 1)
        title = title.removeprefix('# ')
        minutes = math.ceil(len(text.split())/220)
        # Insert a keyboard-accessible collapsible contents list after the introduction.
        body = body.replace('\n## ', '\n[TOC]\n\n## ', 1)
        renderer = markdown.Markdown(extensions=['fenced_code', 'tables', 'toc', 'codehilite'],
                                     extension_configs={'codehilite': {'guess_lang': False}})
        rendered = renderer.convert(body)
        rendered = re.sub(r'<div class="toc">(.*?)</div>',
                          r'<details class="article-contents"><summary>In this article</summary><nav aria-label="Article contents">\1</nav></details>', rendered, flags=re.S)
        rendered = rendered.replace('<table>', '<div class="table-wrap" tabindex="0" role="region" aria-label="Scrollable data table"><table>').replace('</table>', '</table></div>')
        archived = ROOT/'archive/revisions'/f"{post['slug']}-original.html"
        old = archived.read_text()
        prefix = old.split('<article class="prose">')[0]
        prefix = re.sub(r'<meta name="robots"[^>]*>\s*', "", prefix)
        suffix = old.split('</article>', 1)[1]
        prefix = re.sub(r'<title>.*?</title>', f'<title>{escape(title)} - Stanley Ngugi</title>', prefix)
        for key, value in [('description', post['description']), ('og:title', title),
                           ('og:description', post['description']), ('citation_title', title)]:
            prefix = re.sub(r'(<meta (?:name|property)="'+re.escape(key)+r'" content=")[^"]*(">)',
                            lambda m:m[1]+escape(value, quote=True)+m[2], prefix)
        canonical = f"{BASE}/posts/{post['slug']}"
        data = {'@context':'https://schema.org', '@type':'Article', 'headline':title,
                'description':post['description'], '@id':canonical+'#article', 'author':{'@type':'Person','@id':BASE+'/#person','name':'Stanley Ngugi','url':BASE+'/','sameAs':['https://github.com/stanleyngugi']},
                'datePublished':'2026-08-22', 'dateModified':MODIFIED, 'url':canonical,
                'mainEntityOfPage':canonical}
        meta = f'<link rel="canonical" href="{canonical}">\n<meta property="article:modified_time" content="{MODIFIED}T00:00:00Z">\n<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>\n'
        prefix = prefix.replace('</head>', meta+'</head>')
        prefix = prefix.replace(f'{BASE}/posts/{post["slug"]}.html', canonical)
        prefix = prefix.replace('https://github.com/stanleyngugi/lean-tactic-research', CODE)
        suffix = suffix.replace('https://github.com/stanleyngugi/lean-tactic-research', CODE)
        bibkey = 'ngugi2026lean' if post == POSTS[0] else 'ngugi2026quarter'
        bib = ('@misc{' + bibkey + ',\n  title = {' + title + '},\n'
               '  author = {Ngugi, Stanley},\n  year = {2026},\n'
               '  month = {aug},\n  url = {' + canonical + '},\n'
               '  howpublished = {Stanley Ngugi},\n'
               '  note = {Revised ' + REVISION + '. Companion code: ' + CODE + '}\n}\n')
        (ROOT/'citations').mkdir(exist_ok=True)
        (ROOT/'citations'/f"{post['slug']}.bib").write_text(bib)
        article = f'''<article class="prose cfg-article">
<header class="article-header"><h1>{escape(title)}</h1>
<div class="entry-date">By <a href="/" rel="author">Stanley Ngugi</a> · {minutes} min read · formal methods · <a href="{CODE}">code ↗</a></div></header>
{rendered}
<div class="cite-box"><div class="cite-label">Cite this post</div>
<p class="citation-text">Ngugi, Stanley. “{escape(title)}.” August 22, 2026. Revised {REVISION}.</p>
<p><a href="/citations/{post['slug']}.bib" download>Download BibTeX</a></p>
<pre><code>{escape(bib)}</code></pre></div>
<p class="article-artifacts"><a href="{CODE}">Companion code and evidence</a> · <a href="/content/{post['source']}">Markdown source</a></p>
</article>'''
        (ROOT/'posts'/f"{post['slug']}.html").write_text(prefix+article+suffix)
        # Update only the corresponding homepage entry.
        pattern = r'(<a href="/posts/'+re.escape(post['slug'])+r'(?:\.html)?" class="entry">)(.*?)(</a>)'
        def entry(m):
            inner = re.sub(r'(<span class="entry-title">).*?(</span>)', lambda x:x[1]+escape(title)+x[2],m[2],flags=re.S)
            inner = re.sub(r'(<div class="entry-desc">).*?(</div>)', lambda x:x[1]+'\n'+escape(post['description'])+'\n'+x[2],inner,flags=re.S)
            inner = re.sub(r'(<span class="entry-date">).*?(</span>)',
                           lambda x:x[1]+f'formal methods · {minutes} min'+x[2],inner,flags=re.S)
            return m[1]+inner+m[3]
        index, n = re.subn(pattern,entry,index,flags=re.S)
        if n != 1:raise RuntimeError(f"Expected one homepage entry for {post['slug']}")
        def item(m):
            value = m[0]
            if canonical not in value:return value
            value = re.sub(r'<title>.*?</title>', '<title>'+escape(title)+'</title>',value,flags=re.S)
            return re.sub(r'<description>.*?</description>', '<description>'+escape(post['description'])+'</description>',value,flags=re.S)
        rss = re.sub(r'<item>.*?</item>',item,rss,flags=re.S)
        manifests[post['source']] = {'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                                     'output':f"posts/{post['slug']}.html", 'title':title,'reading_minutes':minutes}
    (ROOT/'index.html').write_text(index)
    (ROOT/'rss.xml').write_text(rss)
    sitemap = (ROOT/'sitemap.xml').read_text()
    for post in POSTS:
        sitemap = re.sub(r'(<url>\s*<loc>'+re.escape(BASE+'/posts/'+post['slug'])+r'</loc>\s*<lastmod>).*?(</lastmod>)',
                         lambda m:m[1]+MODIFIED+m[2],sitemap,flags=re.S)
    (ROOT/'sitemap.xml').write_text(sitemap)
    (ROOT/'content/manifest.json').write_text(json.dumps(manifests,indent=2,ensure_ascii=False)+'\n')
    print('Rendered two articles; synchronized homepage, RSS, sitemap, and metadata.')


if __name__ == '__main__':
    main()
