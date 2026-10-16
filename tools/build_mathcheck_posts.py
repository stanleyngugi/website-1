#!/usr/bin/env python3
"""Render the committed research articles with Pandoc.

The MathCheck articles are author-revised website editions, and the C article
is a website editorial revision. Preserve technical claims in these sources;
only rewrite links and add website navigation here.
"""

from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BASE = "https://stanleyngugi.netlify.app"
POSTS = (
    {
        "name": "MathCheck RL",
        "slug": "mathcheck-rl",
        "modified": "2026-10-17",
        "description": "Formal verification of bounded mathematical submissions against frozen specifications, producing RL rewards without stored answer keys.",
        "previous_title": "Grading Mathematical Answers Without Answer Keys",
        "repo": "https://github.com/stanleyngugi/mathcheck-rl",
        "source_path": "TECHNICAL_ARTICLE.md",
        "publication": "2026-09-12",
        "topics": "RL, formal methods",
    },
    {
        "name": "MathCheck Engine",
        "slug": "mathcheck-engine",
        "modified": "2026-10-17",
        "description": "A verifier that turns bounded mathematical specifications and candidate answers into Lean programs, checks the complete finite domain, and records the scope and outcome of each verdict.",
        "repo": "https://github.com/stanleyngugi/mathcheck-engine",
        "source_path": "TECHNICAL_ARTICLE.md",
        "publication": "2026-09-12",
        "topics": "formal methods",
    },
    {
        "name": "Formally Verified C",
        "slug": "formally-verified-c",
        "description": "An RL environment where models write C functions and reward comes from proving the code satisfies a fixed specification, rather than from passing a test suite.",
        "repo": "https://github.com/stanleyngugi/formally-verified-code-rl",
        "source_path": "docs/BLOG_POST_DRAFT.md",
        "publication": "2026-09-13",
        "topics": "RL, formal methods",
    },
)


def render(post):
    source = ROOT / "content" / f"{post['slug']}.md"
    original = source.read_text(encoding="utf-8")
    heading, body = original.split("\n", 1)
    if not heading.startswith("# "):
        raise ValueError(f"Expected first-level title in {source}")
    title = heading[2:].strip()
    url = f"{BASE}/posts/{post['slug']}"
    minutes = (len(original.split()) + 219) // 220

    result = subprocess.run(
        ["pandoc", "--from=gfm+tex_math_dollars", "--to=html", "--mathml", "--wrap=none", "--no-highlight"],
        input=body, text=True, capture_output=True, check=True,
    )
    article_body = result.stdout
    # Keep long native MathML formulas inside the article on narrow screens.
    article_body = re.sub(
        r'<p>(<math display="block".*?</math>)</p>',
        r'<div class="math-display" tabindex="0" role="region" '
        r'aria-label="Scrollable mathematical formula">\1</div>',
        article_body, flags=re.S,
    )
    # Mermaid expects graph text directly inside its container, not a nested
    # Pandoc code element. If the module cannot load, this still shows source.
    article_body = re.sub(
        r'<pre class="mermaid"><code>(.*?)</code></pre>',
        r'<pre class="mermaid">\1</pre>', article_body, flags=re.S,
    )

    # Repo-relative links in the copied Markdown must still lead to their
    # authoritative code/evidence files; companion articles use the new pages.
    article_body = re.sub(
        r'href="(?!https?://|/|#|mailto:)([^"#]+)(#[^"]*)?"',
        lambda m: f'href="{post["repo"]}/blob/main/{m[1]}{m[2] or ""}"',
        article_body,
    )
    for other in POSTS:
        original_link = f"{other['repo']}/blob/main/{other['source_path']}"
        article_body = article_body.replace(
            f'href="{original_link}"', f'href="/posts/{other["slug"]}"'
        )

    headings = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', article_body)
    if headings:
        links = "\n".join(
            f'<li><a href="#{anchor}">{label}</a></li>' for anchor, label in headings
        )
        toc = (
            '<details class="article-contents"><summary>In this article</summary>'
            f'<nav aria-label="Article contents"><ul>{links}</ul></nav></details>\n'
        )
        article_body = article_body.replace("<h2 ", toc + "<h2 ", 1)
    article_body = article_body.replace(
        "<table>",
        '<div class="table-wrap" tabindex="0" role="region" '
        'aria-label="Scrollable data table"><table>',
    ).replace("</table>", "</table></div>")

    template = (ROOT / "posts" / "_template.html").read_text(encoding="utf-8")
    prefix = template.split('<article class="prose">', 1)[0]
    suffix = template.split("</article>", 1)[1]
    suffix = suffix.replace(
        "</body>",
        '<script type="module">\n'
        "import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@12/dist/mermaid.esm.min.mjs';\n"
        "mermaid.initialize({startOnLoad: true, securityLevel: 'strict', theme: 'neutral'});\n"
        "</script>\n</body>",
    )
    prefix = re.sub(r'<!--.*?-->\s*', "", prefix, flags=re.S)
    prefix = prefix.replace("[Post Title]", escape(title, quote=True))
    prefix = prefix.replace("[One-sentence summary of the post.]", escape(post["description"], quote=True))
    prefix = prefix.replace("[filename]", post["slug"])
    prefix = prefix.replace("[YYYY-MM-DD]", post["publication"])
    metadata = {
        "@context": "https://schema.org", "@type": "Article", "headline": title,
        "description": post["description"],
        "@id": url + "#article",
        "author": {"@type": "Person", "@id": BASE + "/#person", "name": "Stanley Ngugi",
                   "url": BASE + "/", "sameAs": ["https://github.com/stanleyngugi"]},
        "datePublished": post["publication"], "url": url,
        "mainEntityOfPage": url, "dateModified": post.get("modified", "2026-10-06"),
    }
    prefix = prefix.replace(
        "</head>",
        f'<link rel="canonical" href="{url}">\n'
        f'<script type="application/ld+json">{json.dumps(metadata, ensure_ascii=False)}</script>\n'
        "</head>",
    )
    title_history = (
        f'<p class="entry-date article-title-history">Previously titled '
        f'“{escape(post["previous_title"])}”. The article URL is unchanged.</p>\n'
        if post.get("previous_title") else ""
    )
    bib = (
        f"@misc{{ngugi2026{post['slug'].replace('-', '')},\n"
        f"  title = {{{title}}},\n  author = {{Ngugi, Stanley}},\n"
        f"  year = {{2026}},\n  month = {{sep}},\n  url = {{{url}}},\n"
        f"  note = {{Companion code and evidence: {post['repo']}}}\n}}\n"
    )
    (ROOT / "citations" / f"{post['slug']}.bib").write_text(bib, encoding="utf-8")
    html = (
        '<article class="prose cfg-article mathcheck-article">\n'
        f'<header class="article-header"><h1>{escape(title)}</h1>\n'
        f'<div class="entry-date">By <a href="/" rel="author">Stanley Ngugi</a> · {minutes} min read · {post["topics"]} · '
        f'<a href="{post["repo"]}">code ↗</a></div>\n'
        f'{title_history}</header>\n'
        f'{article_body}\n'
        '<div class="cite-box"><div class="cite-label">Cite this post</div>\n'
        f'<p><a href="/citations/{post["slug"]}.bib" download>Download BibTeX</a></p>\n'
        f'<pre><code>{escape(bib)}</code></pre></div>\n'
        f'<p class="article-artifacts"><a href="{post["repo"]}">Companion code and evidence</a> '
        f'· <a href="/content/{post["slug"]}.md">Markdown source</a></p>\n'
        '</article>'
    )
    (ROOT / "posts" / f"{post['slug']}.html").write_text(
        prefix + html + suffix, encoding="utf-8"
    )
    return {
        "source": f"{post['repo']}/blob/main/{post['source_path']}",
        "source_relation": "website author rewrite" if post['slug'] in ('mathcheck-rl', 'mathcheck-engine') else "website editorial revision",
        "sha256": sha256(original.encode("utf-8")).hexdigest(),
        "output": f"posts/{post['slug']}.html", "title": title,
        "reading_minutes": minutes,
    }


def main():
    manifest = {f"{post['slug']}.md": render(post) for post in POSTS}
    (ROOT / "content" / "research-posts-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    index = (ROOT / "index.html").read_text()
    rss = (ROOT / "rss.xml").read_text()
    sitemap = (ROOT / "sitemap.xml").read_text()
    for post in POSTS:
        record = manifest[f"{post['slug']}.md"]
        canonical = f"{BASE}/posts/{post['slug']}"
        pattern = r'(<a href="/posts/' + re.escape(post['slug']) + r'(?:\.html)?" class="entry">)(.*?)(</a>)'
        def entry(match):
            inner = re.sub(r'(<span class="entry-title">).*?(</span>)', lambda m:m[1]+escape(record['title'])+m[2], match[2], flags=re.S)
            inner = re.sub(r'(<span class="entry-date">).*?(</span>)', lambda m:m[1]+f'{post["topics"]} · {record["reading_minutes"]} min'+m[2], inner, flags=re.S)
            return match[1]+inner+match[3]
        index, count = re.subn(pattern, entry, index, flags=re.S)
        if count != 1:
            raise RuntimeError(f"Expected one homepage entry for {post['slug']}")
        def item(match):
            if f'<link>{canonical}</link>' not in match[0]:
                return match[0]
            value = re.sub(r'<title>.*?</title>', lambda m:'<title>'+escape(record['title'])+'</title>', match[0], flags=re.S)
            return re.sub(r'<description>.*?</description>', lambda m:'<description>'+escape(post['description'])+'</description>', value, flags=re.S)
        rss = re.sub(r'<item>.*?</item>', item, rss, flags=re.S)
        sitemap = re.sub(r'(<url>\s*<loc>'+re.escape(canonical)+r'</loc>\s*<lastmod>).*?(</lastmod>)', lambda m:m[1]+post.get("modified", "2026-10-06")+m[2], sitemap, flags=re.S)
    (ROOT / "index.html").write_text(index)
    (ROOT / "rss.xml").write_text(rss)
    (ROOT / "sitemap.xml").write_text(sitemap)
    print("Rendered three research posts; synchronized homepage, RSS, and sitemap.")


if __name__ == "__main__":
    main()
