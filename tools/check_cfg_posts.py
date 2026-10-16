#!/usr/bin/env python3
"""Check source integrity, active pages, local links, and publication metadata."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.links, self.images, self.headings, self.canonicals = [], [], [], [], []
        self.og_urls, self.jsonld, self._jsonld = [], [], None
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        if tag == 'a' and 'href' in a: self.links.append(a['href'])
        if tag == 'img': self.images.append(a)
        if tag == 'script' and 'src' in a: self.links.append(a['src'])
        if tag == 'link' and a.get('rel') == 'stylesheet': self.links.append(a['href'])
        if tag == 'h1': self.headings.append(tag)
        if tag == 'link' and a.get('rel') == 'canonical': self.canonicals.append(a['href'])
        if tag == 'meta' and a.get('property') == 'og:url': self.og_urls.append(a['content'])
        if tag == 'script' and a.get('type') == 'application/ld+json': self._jsonld = ''
    def handle_data(self, data):
        if self._jsonld is not None: self._jsonld += data
    def handle_endtag(self, tag):
        if tag == 'script' and self._jsonld is not None:
            self.jsonld.append(json.loads(self._jsonld))
            self._jsonld = None

manifest = json.loads((ROOT/'content/manifest.json').read_text())
manifest.update(json.loads((ROOT/'content/research-posts-manifest.json').read_text()))
for name, record in manifest.items():
    assert hashlib.sha256((ROOT/'content'/name).read_bytes()).hexdigest() == record['sha256'], name
paths = [ROOT/'index.html', ROOT/'cv.html'] + sorted(p for p in (ROOT/'posts').glob('*.html') if p.name != '_template.html')
canonical_urls = []
for path in paths:
    page = Page(path.read_text())
    assert len(page.headings) == 1 and len(page.canonicals) == 1, path
    canonical_urls.extend(page.canonicals)
    assert page.og_urls == page.canonicals, f'Open Graph/canonical mismatch: {path}'
    if path.parent.name == 'posts':
        articles = [data for data in page.jsonld if data.get('@type') == 'Article']
        assert len(articles) == 1, f'Article structured data: {path}'
        assert articles[0]['url'] == page.canonicals[0], path
        assert articles[0]['author']['@id'] == 'https://stanleyngugi.netlify.app/#person', path
        assert 'rel="author"' in path.read_text(), f'Missing byline: {path}'
    assert len(page.ids) == len(set(page.ids)), f'Duplicate IDs: {path}'
    assert '[TOC]' not in path.read_text(), path
    for img in page.images:
        assert img.get('alt'), f'Missing image description: {path}'
    for ref in page.links + [x['src'] for x in page.images]:
        url = urlsplit(ref)
        if url.scheme or url.netloc: continue
        target = ROOT/unquote(url.path.lstrip('/')) if url.path.startswith('/') else path.parent/unquote(url.path)
        if not url.path: target = path
        if target.is_dir(): target = target/'index.html'
        if not target.is_file() and not target.suffix:
            target = target.with_suffix('.html')
        assert target.is_file(), f'{path.name}: missing {ref}'
        if url.fragment and target.suffix == '.html':
            assert unquote(url.fragment) in Page(target.read_text()).ids, f'{path.name}: missing anchor {ref}'
for name in ('rss.xml', 'sitemap.xml'):
    ET.parse(ROOT/name)
assert len(set(canonical_urls)) == len(canonical_urls), 'Duplicate canonical URLs'
sitemap = {node.text for node in ET.parse(ROOT/'sitemap.xml').iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')}
assert set(canonical_urls) == sitemap, 'Active pages and sitemap disagree'
rss = ET.parse(ROOT/'rss.xml')
items = rss.findall('./channel/item')
assert len(items) == 6, 'Expected six feed entries'
assert len({item.findtext('guid') for item in items}) == 6, 'Duplicate RSS GUIDs'
assert {item.findtext('link') for item in items} == {url for url in canonical_urls if '/posts/' in url}, 'RSS links and active articles disagree'
print('Five source hashes and eight active pages: headings, canonical URLs, author metadata, links, anchors, image descriptions, RSS, and sitemap pass.')
