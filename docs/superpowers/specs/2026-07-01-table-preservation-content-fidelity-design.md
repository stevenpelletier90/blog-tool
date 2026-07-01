# Design: Table Preservation & Content-Fidelity Cleanup

**Date:** 2026-07-01
**Status:** Approved (pending spec review)
**Component:** `blog_extractor.py` content transform pipeline (+ `extract.py`, `streamlit_app.py` surfacing)

## Problem

Blog posts migrated to WordPress lose their HTML tables — they arrive as loose
paragraph text, forcing the migration team to manually rebuild every table.
Reported against two DealerOn posts:

- `https://www.mccarthyjeepramls.com/jeep-grand-cherokee-vs-toyota-highlander/`
- `https://dealer25532.dealeron.com/blogs/10132/ram-1500-vs-silverado-vs-f-150-full-truck-comparison/`

## Root cause

The content transform is a three-stage pipeline:

`extract_content()` → `clean_html()` → `html_to_gutenberg()` → `element_to_gutenberg_block()`

Tables (and several sibling elements) are lost because:

1. **`clean_html()` allow-list** (`blog_extractor.py:957`) is "semantic HTML only":
   `p, h1–h6, strong, em, u, ul, ol, li, blockquote, pre, code, a` (+`img`).
   Any tag not on the list is `unwrap()`-ed — tag deleted, text kept
   (`blog_extractor.py:1017-1021`). `table/thead/tbody/tfoot/tr/td/th/caption`
   are not listed, so table structure collapses to text.
2. **`html_to_gutenberg()` block list** (`blog_extractor.py:1141`) has no `table`,
   so a surviving table would be treated as inline and wrapped in `<p>`.
3. **`element_to_gutenberg_block()`** (`blog_extractor.py:1178`) has no `table`
   case; its fallback wraps unknown blocks in a paragraph (`:1251-1253`).

The **same allow-list gap** silently deletes: `hr`, `figure`/`figcaption`,
`sub`/`sup`, `del`/`ins`/`mark`/`abbr`/`cite`/`s`, and `dl`/`dt`/`dd`.

## Guiding principle: valid & well-formed, never malformed

Every change is subordinate to one rule: **output must import cleanly into
WordPress with no Gutenberg block-validation errors and no malformed HTML.**
When a faithful native block cannot be guaranteed valid, we degrade to a
`wp:html` block (raw HTML, always imports) rather than emit something broken.

## Scope (in priority order)

### P1 — Tables (preserve + flag)

- **Preserve, hybrid strategy:**
  - *Simple tables* (only `tr/td/th/thead/tbody/tfoot/caption`, no merged cells,
    no nested tables) → native **Table block**:
    `<!-- wp:table --><figure class="wp-block-table"><table>…</table></figure><!-- /wp:table -->`
  - *Complex tables* (any `colspan`/`rowspan`, or a nested `<table>`) → **`wp:html`
    block** preserving the exact table HTML. Always valid; not natively editable.
- **Cell contents:** inline formatting is preserved (`a`, `strong`, `em`, etc.).
  Cell text is HTML-escaped where it is emitted as text.
- **Flag:** posts containing ≥1 table get a `flags`/`warnings` entry
  (e.g. `"2 tables preserved — review formatting"`), added to the per-post result
  dict (both `extract_blog_data` sync `:1538` and async `:1615`), logged via the
  callback, and surfaced in the Streamlit results panel and the CSV/JSON summary.
  Flags are **not** injected into post body content (keeps output clean).

### P2 — Sibling elements (same root cause)

Add to the allow-list and give each a correct block/inline treatment:

- `hr` → `<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->`
- `figure` + `figcaption` → image with caption (native `wp:image` figure/figcaption)
  when it wraps an image; otherwise `wp:html` to keep it valid.
- `sub`, `sup` → allowed inline; preserved inside paragraphs/cells.
- `del`, `ins`, `mark`, `abbr`, `cite`, `s` → allowed inline (semantic fidelity).
- `dl`/`dt`/`dd` → `wp:html` block (no native definition-list block).

### P3 — WordPress-validity fixes

- **Escape code:** `wp:code`/`wp:preformatted` text is run through `html.escape`
  so `<`, `>`, `&` inside code do not produce invalid markup (`:1210-1216`).
- **Nested lists / list block:** verify current `wp:list` output against the
  active WordPress block format; keep flat classic form if still accepted,
  otherwise degrade the whole list to `wp:html`.
- **Quote block:** ensure inner content is `<p>`-wrapped or degrade to `wp:html`.

### Cross-cutting — validity safeguard

A final `_validate_gutenberg(content)` pass runs on every post's content and:

1. re-parses output and confirms it is well-formed,
2. confirms every `<!-- wp:x -->` has a matching `<!-- /wp:x -->` (balanced),
3. reports any imbalance via the callback log.

Block emitters that cannot guarantee validity return a `wp:html` fallback so the
safeguard has nothing to catch in normal operation.

## Non-goals (YAGNI)

- No table styling/theme reproduction (colors, borders) — WordPress themes own that.
- No native editable representation of merged-cell tables (they use `wp:html`).
- No new UI beyond surfacing the table flag in existing results/summary views.
- No changes to platform detection, extraction selectors, or the 5 documented
  "DO NOT CHANGE" constraints (formatter="minimal", HTTPS URLs, asyncio, MD5,
  concurrency).

## Testing (first tests in this repo)

`pytest` fixtures with hand-authored HTML, asserting on the transformed output:

| Fixture | Assertion |
|---|---|
| simple table | one `wp:table` block, `<figure class="wp-block-table">`, all cells present |
| table w/ header + inline link | `<thead>`/`<th>` preserved, `<a>` intact |
| merged-cell table (colspan) | falls back to a single `wp:html` block, colspan intact |
| nested table | `wp:html` fallback |
| `hr` | `wp:separator` block |
| `figure`+`figcaption` | caption text preserved |
| `sub`/`sup` | tags present in output |
| code with `<`,`&` | escaped in `wp:code` |
| every fixture | output parses as well-formed HTML; wp-block comments balanced |

Tests run against `clean_html()` + `html_to_gutenberg()` directly (no network).
Live-URL validation against the two reported posts is a manual final check.

## Files touched

- `blog_extractor.py` — allow-list, block walker, block emitter, flag plumbing,
  validity safeguard.
- `extract.py` — surface table flag in CSV/JSON summary output.
- `streamlit_app.py` — surface table flag in results panel.
- `tests/test_content_transform.py` — new.
- Dev docs (`CLAUDE.md`/`CONTRIBUTING.md`) — note the now-real test suite.

## Rollout

Live app `blog-tool-dealeron.streamlit.app` auto-redeploys from the tracked
GitHub branch, so merging to that branch ships the fix (and re-installs deps).
