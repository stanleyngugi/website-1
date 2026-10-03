#!/usr/bin/env python3
"""Render verbatim copies of the current research articles with Pandoc.

Sync each content file from its corresponding GitHub article before publishing
a revision. Keep the author's technical claims in those sources unchanged;
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
        "description": "Formal verification of bounded mathematical submissions against frozen specifications, producing RL rewards without precomputed answer keys.",
        "repo": "https://github.com/stanleyngugi/mathcheck-rl",
        "source_path": "TECHNICAL_ARTICLE.md",
        "publication": "2026-09-12",
        "topics": "RL, formal methods",
    },
    {
        "name": "MathCheck Engine",
        "slug": "mathcheck-engine",
        "description": "A verifier that turns bounded mathematical specifications and candidate answers into Lean programs, checks the complete finite domain in isolation, and records what each verdict means.",
        "repo": "https://github.com/stanleyngugi/mathcheck-engine",
        "source_path": "TECHNICAL_ARTICLE.md",
        "publication": "2026-09-12",
        "topics": "formal methods",
    },

)


def render(post):
    source = ROOT / "content" / f"{post['slug']}.md"
    original = source.read_text(encoding="utf-8")
    heading, body = original.split("\n", 1)
    if not heading.startswith("# "):
        raise ValueError(f"Expected first-level title in {source}")
    title = heading[2:].strip()
    url = f"{BASE}/posts/{post['slug']}.html"
    minutes = (len(original.split()) + 219) // 220

    result = subprocess.run(
        ["pandoc", "--from=gfm", "--to=html", "--wrap=none", "--no-highlight"],
        input=body, text=True, capture_output=True, check=True,
    )
    article_body = result.stdout
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
            f'href="{original_link}"', f'href="/posts/{other["slug"]}.html"'
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
        "author": {"@type": "Person", "name": "Stanley Ngugi"},
        "datePublished": post["publication"], "url": url,
        "mainEntityOfPage": url, "dateModified": "2026-10-03",
    }
    prefix = prefix.replace(
        "</head>",
        f'<link rel="canonical" href="{url}">\n'
        f'<script type="application/ld+json">{json.dumps(metadata, ensure_ascii=False)}</script>\n'
        "</head>",
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
        f'<div class="entry-date">{minutes} min read · {post["topics"]} · '
        f'<a href="{post["repo"]}">code ↗</a></div></header>\n'
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
        "sha256": sha256(original.encode("utf-8")).hexdigest(),
        "output": f"posts/{post['slug']}.html", "title": title,
        "reading_minutes": minutes,
    }


def main():
    path = ROOT / "content" / "research-posts-manifest.json"
    manifest = json.loads(path.read_text()) if path.exists() else {}
    manifest.update({f"{post['slug']}.md": render(post) for post in POSTS})
    (ROOT / "content" / "research-posts-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("Rendered both MathCheck posts from their authoritative Markdown sources.")


if __name__ == "__main__":
    main()
