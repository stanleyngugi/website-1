# Website consolidation review

Reviewed October 6, 2026 against `sngugiresearch-cmd/website:main` at
`ae4b486d22977761dc68e0d6a95c14df3332c607`.

## Branch coverage

| Fork branch | Disposition |
| --- | --- |
| `main` (`92ee711`) | Includes the eleven unpublished article rewrite, rendering, title, and MathCheck validation/publication commits. Uses their latest article sources and the polysemanticity rewrite. |
| `improve-search-visibility` (`d74a955`) | Includes the complete search/author metadata and route changes from upstream PR #8. |
| `portfolio-signalling` (`ce9c6d9`) | Includes the approved CV introduction and accessible email-copy behavior. |
| `mathcheck-site-posts` (`4576f84`) | Earlier MathCheck revisions are superseded by the newer October 5 sources on fork `main`. |
| `refresh-research-profile` | Already included in upstream through PR #2. |
| `revise-cfg-articles` | Already included in upstream through PR #1; incorporates the later website voice revisions from fork `main`. |
| `simplify-portfolio-copy` | Already included in upstream through PRs #5–#7. |
| `streamline-cv-and-home` | Already included in upstream through PR #3. |

This branch starts from current upstream rather than replacing it with the
diverged fork tree. The older homepage, date labels, repeated Now section,
and older CV stylesheet on fork `main` do not replace the subsequently merged
upstream presentation. Existing citations, source/build tooling, archived
revisions, and the A4 CV layout are retained.

## Integration fixes

- Rebuild all five Markdown-backed articles while retaining the search branch's
  extensionless canonical URLs, author identities, and bylines.
- Restore the CFG source manifest and update hashes for the committed revisions.
- Keep all three research articles in the Pandoc renderer, including the
  author's Formally Verified C rewrite. Mark its source relationship explicitly;
  it is not an unchanged copy of the companion repository draft.
- Render MathCheck formulas as native MathML with scrollable display containers.
- Align the renamed MathCheck RL title across its page, homepage, CV, RSS, and
  BibTeX. Preserve its route and the previous-title notice.
- Synchronize reading times and revision metadata without changing publication
  dates or RSS GUIDs. Preserve the Google verification file.
- Retain the accessible email button, mailto link, and accurate success/failure
  status. Test rejection and fallback paths as well as successful copying.
- Move MathCheck Engine to the second CV sheet to accommodate the approved
  longer introduction without crowding the first sheet's footer.
- Restore the polysemanticity configuration caveat and remove the claim that
  weight decay is L1 regularization. Frame the headline 17.9% difference as a
  descriptive L1/ReLU versus L2/GELU comparison. Explain the mismatch between
  the reported t-statistics and significance claims rather than reasserting
  those p-values as validated.

## Validation performed

- Both renderers complete with Pandoc 3.1.3, Markdown 3.8.2, and Pygments 2.19.2.
- Re-running both renderers changes no output files.
- `python3 tools/check_cfg_posts.py` validates five source hashes and all eight
  active pages: headings, unique canonical URLs, Open Graph URL agreement,
  author structured data/bylines, local links and fragments, image descriptions,
  RSS membership/GUID uniqueness, and exact sitemap membership.
- Python compilation, `node --check main.js`, and `git diff --check` pass.
- Six email-copy cases pass: Clipboard API resolve/reject/throw and legacy
  command success/failure/throw, including failure announcements and restored
  focus in the legacy path.
- RSS GUIDs and publication dates match upstream, and the Google verification
  file is byte-identical to upstream.
- A local WeasyPrint print render produces two A4 CV pages. Both were inspected;
  content ends above the page footers. This used fallback fonts, so it is not
  a Chromium or web-font visual check.
- The Mermaid 12 module URL returns JavaScript successfully.
- MathCheck Engine and RL Markdown copies match the current companion repository
  blobs retrieved through GitHub. CFG and C website sources intentionally use
  the author's editorial revisions.

## Remaining validation limits

Chromium was unavailable and its browser download did not yield an executable
archive. Desktop/mobile/theme rendering and print output with the live web fonts
have not been independently checked in a browser during this review.

The underlying ML experiments, Lean native consumer gates, and Frama-C releases
were not rerun for this static website consolidation. The articles link to their
published evidence and retain scope limits: grammar acceptance is not proof
correctness; MathCheck is bounded to encoded contracts; the C release records
open hardening concerns; engineering/GPU runs do not establish held-out learning
gains. Polysemanticity significance requires experiment-level reanalysis, with
the seed counts, degrees of freedom, and compared configurations reconciled.

After deployment, verify extensionless routes, legacy redirects, and archive
noindex headers, then submit the sitemap and inspect the updated pages in
Google Search Console. Source changes cannot perform those deployment checks
or guarantee indexing.
