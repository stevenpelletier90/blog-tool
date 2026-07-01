# Table Preservation & Content-Fidelity Cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the blog tool flattening HTML tables into paragraphs; preserve tables and several sibling elements as valid, well-formed WordPress Gutenberg blocks, and flag posts containing tables.

**Architecture:** All content passes `extract_content()` → `clean_html()` (whitelist sanitizer) → `html_to_gutenberg()` (top-level block walker) → `element_to_gutenberg_block()` (per-element emitter). We widen the `clean_html` allow-list, teach the walker + emitter about new block types, emit `wp:html` for anything that can't be guaranteed valid, add a structural validity check, and surface a per-post `warnings` list.

**Tech Stack:** Python 3.14, BeautifulSoup4 (`html.parser`), pytest. Dev venv: `blog-extractor-env`.

## Global Constraints

- Output must import into WordPress with **no Gutenberg block-validation errors and no malformed HTML.** When a native block can't be guaranteed valid, emit `<!-- wp:html -->…<!-- /wp:html -->` (raw HTML always imports).
- Do NOT touch the 5 documented "DO NOT CHANGE" constraints (formatter="minimal", HTTPS URLs in XML, Windows asyncio, MD5 hashing, concurrency=5).
- `html` stdlib module already imported (`blog_extractor.py:13`) — use `html.escape` for code.
- Verified WP save formats (Context7 `/house-of-giants/wp-block-docs`):
  - Table: `<!-- wp:table --><figure class="wp-block-table"><table>…</table></figure><!-- /wp:table -->`
  - Separator: `<!-- wp:separator --><hr class="wp-block-separator"/><!-- /wp:separator -->`
  - Image+caption: `<figure class="wp-block-image"><img …/><figcaption class="wp-element-caption">…</figcaption></figure>`
  - List: `<ul class="wp-block-list">…</ul>`; Quote inner content is `<p>`-wrapped; Heading carries `class="wp-block-heading"`.
  - Inline `<mark> <del> <ins> <sub> <sup> <abbr> <cite> <s>` are valid inside a paragraph — allow-list only, no block needed.
- Run all pytest via the venv: `& ".\blog-extractor-env\Scripts\python.exe" -m pytest tests/ -v`

---

### Task 1: Test harness + preserve simple tables as native `wp:table`

**Files:**
- Create: `tests/__init__.py` (empty), `tests/test_content_transform.py`
- Modify: `blog_extractor.py` — `clean_html` allow-list (~957) & allowed_attrs (~968); `html_to_gutenberg` block list (~1141); `element_to_gutenberg_block` (~1178, add table case + `_table_to_block` helper)

**Interfaces:**
- Produces: `BlogExtractor.clean_html(html:str)->str`, `.html_to_gutenberg(html:str)->str`, new `._table_to_block(el:Tag)->str`.
- Test helper `to_blocks(extractor, raw_html)` = `extractor.html_to_gutenberg(extractor.clean_html(raw_html))`.

- [ ] **Step 1: Write failing test**
```python
# tests/test_content_transform.py
import pytest
from blog_extractor import BlogExtractor

@pytest.fixture
def ex(tmp_path):
    return BlogExtractor(output_dir=str(tmp_path), callback=None,
                         download_images=False, skip_playwright=True, verbose=False)

def to_blocks(ex, raw):
    return ex.html_to_gutenberg(ex.clean_html(raw))

SIMPLE_TABLE = ("<table><thead><tr><th>Model</th><th>MPG</th></tr></thead>"
                "<tbody><tr><td>Traverse</td><td>27</td></tr></tbody></table>")

def test_simple_table_becomes_native_table_block(ex):
    out = to_blocks(ex, SIMPLE_TABLE)
    assert "<!-- wp:table -->" in out
    assert '<figure class="wp-block-table">' in out
    assert "<th>Model</th>" in out
    assert "<td>Traverse</td>" in out
    assert "<!-- /wp:table -->" in out
    # must NOT be flattened to a paragraph
    assert "<!-- wp:paragraph -->\n<p>Model" not in out
```

- [ ] **Step 2: Run — expect FAIL** (table currently flattened)
`& ".\blog-extractor-env\Scripts\python.exe" -m pytest tests/test_content_transform.py::test_simple_table_becomes_native_table_block -v`

- [ ] **Step 3: Implement**
  - `clean_html` allow-list — replace the set at ~957 with:
```python
allowed_tags = {
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'em', 'u', 'ul', 'ol', 'li',
    'blockquote', 'pre', 'code', 'a',
    # Tables
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'caption', 'colgroup', 'col',
    # Block-level siblings
    'hr', 'figure', 'figcaption', 'dl', 'dt', 'dd',
    # Inline semantic tags (valid inside paragraphs/cells)
    'sub', 'sup', 'mark', 'del', 'ins', 'abbr', 'cite', 's',
}
```
  - `allowed_attrs` (~968) — add cell/list/abbr attrs:
```python
allowed_attrs = {
    'a': ['href', 'class', 'data-is-button'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'class'],
    'th': ['colspan', 'rowspan', 'scope'],
    'td': ['colspan', 'rowspan'],
    'ol': ['start', 'type', 'reversed'],
    'col': ['span'], 'colgroup': ['span'],
    'abbr': ['title'],
}
```
  - `html_to_gutenberg` block list (~1141) — add table/hr/figure/dl:
```python
if element.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol',
                    'blockquote', 'pre', 'img', 'table', 'hr', 'figure', 'dl']:
```
  - `element_to_gutenberg_block` — add before the final `else` fallback:
```python
elif tag_name == 'table' and isinstance(element, Tag):
    return self._table_to_block(element)
```
  - New helper method (place after `element_to_gutenberg_block`):
```python
def _table_to_block(self, element: 'Tag') -> str:
    """Simple tables -> native wp:table; merged-cell or nested tables -> wp:html (always valid)."""
    has_merged = bool(element.find(['td', 'th'], attrs={'colspan': True})
                      or element.find(['td', 'th'], attrs={'rowspan': True}))
    has_nested = element.find('table') is not None
    table_html = str(element)
    if has_merged or has_nested:
        return f'<!-- wp:html -->\n{table_html}\n<!-- /wp:html -->'
    return (f'<!-- wp:table -->\n<figure class="wp-block-table">{table_html}</figure>\n'
            f'<!-- /wp:table -->')
```

- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Commit** — `git add tests/ blog_extractor.py && git commit -m "feat: preserve simple tables as native wp:table block"`

---

### Task 2: Complex tables (merged/nested) → `wp:html` fallback

- [ ] **Step 1: Test**
```python
MERGED_TABLE = ('<table><tbody><tr><td colspan="2">Spans two</td></tr>'
                '<tr><td>A</td><td>B</td></tr></tbody></table>')

def test_merged_cell_table_falls_back_to_html_block(ex):
    out = to_blocks(ex, MERGED_TABLE)
    assert "<!-- wp:html -->" in out
    assert 'colspan="2"' in out            # merged structure preserved exactly
    assert "<!-- wp:table -->" not in out  # not the native block
```
- [ ] **Step 2: Run — expect PASS** (already handled by Task 1's `_table_to_block`; this locks the behavior). If it fails, fix `_table_to_block`.
- [ ] **Step 3: Commit** — `git commit -am "test: lock wp:html fallback for merged/nested tables"`

---

### Task 3: Table cell inline formatting + special-char safety

- [ ] **Step 1: Test**
```python
def test_table_cells_keep_links_and_escape_safely(ex):
    raw = ('<table><tbody><tr><td><a href="https://x.com">Deal</a></td>'
           '<td>A &amp; B</td></tr></tbody></table>')
    out = to_blocks(ex, raw)
    assert '<a href="https://x.com">Deal</a>' in out
    assert 'A &amp; B' in out   # ampersand stays a valid entity, not raw &
```
- [ ] **Step 2: Run — expect PASS** (BeautifulSoup `str()` re-encodes entities). If `&amp;` is lost, investigate clean_html character replacements.
- [ ] **Step 3: Commit** — `git commit -am "test: table cells preserve inline formatting and entities"`

---

### Task 4: `hr` → `wp:separator`

- [ ] **Step 1: Test**
```python
def test_hr_becomes_separator(ex):
    out = to_blocks(ex, "<p>Before</p><hr/><p>After</p>")
    assert "<!-- wp:separator -->" in out
    assert 'class="wp-block-separator"' in out
    assert "<!-- /wp:separator -->" in out
```
- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** — add to `element_to_gutenberg_block`:
```python
elif tag_name == 'hr':
    return '<!-- wp:separator -->\n<hr class="wp-block-separator"/>\n<!-- /wp:separator -->'
```
- [ ] **Step 4: Run — PASS**  •  **Step 5: Commit** `git commit -am "feat: convert <hr> to wp:separator"`

---

### Task 5: `figure`/`figcaption` caption preserved

- [ ] **Step 1: Test**
```python
def test_figure_caption_preserved(ex):
    raw = ('<figure><img src="https://x.com/a.jpg" alt="Car"/>'
           '<figcaption>2026 Model</figcaption></figure>')
    out = to_blocks(ex, raw)
    assert "<!-- wp:image -->" in out
    assert '<figcaption class="wp-element-caption">2026 Model</figcaption>' in out
```
- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** — add case (uses `unquote`, already imported inside img branch; import at top of method or reuse `from urllib.parse import unquote`):
```python
elif tag_name == 'figure' and isinstance(element, Tag):
    img = element.find('img')
    figcaption = element.find('figcaption')
    if img is not None and isinstance(img, Tag) and self.include_images:
        from urllib.parse import unquote
        src = img.get('src', '')
        alt = unquote(str(img.get('alt', ''))) if img.get('alt') else ''
        img_tag = f'<img src="{src}" alt="{alt}"/>' if alt else f'<img src="{src}"/>'
        cap = figcaption.decode_contents().strip() if isinstance(figcaption, Tag) else ''
        cap_html = f'<figcaption class="wp-element-caption">{cap}</figcaption>' if cap else ''
        return (f'<!-- wp:image -->\n<figure class="wp-block-image">{img_tag}{cap_html}'
                f'</figure>\n<!-- /wp:image -->')
    return f'<!-- wp:html -->\n{str(element)}\n<!-- /wp:html -->'
```
- [ ] **Step 4: Run — PASS**  •  **Step 5: Commit** `git commit -am "feat: preserve figure/figcaption as wp:image with caption"`

---

### Task 6: Inline semantics (`sub`,`sup`,`mark`,`del`,`ins`,`abbr`,`cite`,`s`) survive

- [ ] **Step 1: Test**
```python
def test_inline_semantics_survive(ex):
    out = to_blocks(ex, "<p>H<sub>2</sub>O and 1<sup>st</sup> and <mark>hot</mark></p>")
    assert "<sub>2</sub>" in out and "<sup>st</sup>" in out and "<mark>hot</mark>" in out
```
- [ ] **Step 2: Run — PASS** (allow-list from Task 1 already permits these; they ride inside the paragraph). If FAIL, confirm tags are in `allowed_tags`.
- [ ] **Step 3: Commit** `git commit -am "test: inline semantic tags preserved in paragraphs"`

---

### Task 7: `dl`/`dt`/`dd` → `wp:html`

- [ ] **Step 1: Test**
```python
def test_definition_list_preserved_as_html(ex):
    out = to_blocks(ex, "<dl><dt>MPG</dt><dd>27 city</dd></dl>")
    assert "<!-- wp:html -->" in out
    assert "<dt>MPG</dt>" in out and "<dd>27 city</dd>" in out
```
- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement**:
```python
elif tag_name == 'dl':
    return f'<!-- wp:html -->\n{str(element)}\n<!-- /wp:html -->'
```
- [ ] **Step 4: Run — PASS**  •  **Step 5: Commit** `git commit -am "feat: preserve definition lists as wp:html"`

---

### Task 8: Escape code blocks (malformation fix)

- [ ] **Step 1: Test**
```python
def test_code_block_escapes_specials(ex):
    out = to_blocks(ex, "<pre><code>if a < b && c</code></pre>")
    assert "if a &lt; b &amp;&amp; c" in out
    assert "a < b" not in out   # raw < must not survive inside code
```
- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** — change the `pre`/`code` branch (~1210):
```python
elif tag_name == 'pre':
    if element.find('code'):
        content = html.escape(element.get_text())
        return f'<!-- wp:code -->\n<pre class="wp-block-code"><code>{content}</code></pre>\n<!-- /wp:code -->'
    else:
        content = str(element)
        return f'<!-- wp:preformatted -->\n{content}\n<!-- /wp:preformatted -->'
```
- [ ] **Step 4: Run — PASS**  •  **Step 5: Commit** `git commit -am "fix: HTML-escape code block content to prevent malformed markup"`

---

### Task 9: WP-native classes — list, heading, quote validity

- [ ] **Step 1: Tests**
```python
def test_list_has_wp_block_class(ex):
    out = to_blocks(ex, "<ul><li>one</li><li>two</li></ul>")
    assert '<ul class="wp-block-list">' in out

def test_heading_has_wp_block_class(ex):
    out = to_blocks(ex, "<h2>Section</h2>")
    assert 'class="wp-block-heading"' in out

def test_quote_inner_is_p_wrapped(ex):
    out = to_blocks(ex, "<blockquote>Bare quote text</blockquote>")
    assert "<blockquote class=\"wp-block-quote\"><p>Bare quote text</p>" in out
```
- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** — update three branches:
```python
elif tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
    level = int(tag_name[1])
    if isinstance(element, Tag):
        element['class'] = 'wp-block-heading'
    content = str(element)
    return f'<!-- wp:heading {{"level":{level}}} -->\n{content}\n<!-- /wp:heading -->'

elif tag_name in ['ul', 'ol']:
    if isinstance(element, Tag):
        element['class'] = 'wp-block-list'
    content = str(element)
    return f'<!-- wp:list -->\n{content}\n<!-- /wp:list -->'

elif tag_name == 'blockquote':
    inner = element.decode_contents().strip()
    if not re.search(r'<(p|h[1-6]|ul|ol|blockquote|figure|table)\b', inner, re.I):
        inner = f'<p>{inner}</p>'
    return f'<!-- wp:quote -->\n<blockquote class="wp-block-quote">{inner}</blockquote>\n<!-- /wp:quote -->'
```
- [ ] **Step 4: Run — PASS**  •  **Step 5: Commit** `git commit -am "fix: emit WP-native classes for list/heading and p-wrap quotes"`

---

### Task 10: Gutenberg validity safeguard

**Files:** Modify `blog_extractor.py` — add `_validate_gutenberg`.

- [ ] **Step 1: Test**
```python
def test_validate_gutenberg_detects_imbalance(ex):
    assert ex._validate_gutenberg("<!-- wp:table -->\n<figure></figure>") != []
    assert ex._validate_gutenberg(to_blocks(ex, SIMPLE_TABLE)) == []
```
- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement**:
```python
def _validate_gutenberg(self, content: str) -> List[str]:
    """Return structural issues; empty list means every wp:block comment is balanced."""
    if not content:
        return []
    opens = re.findall(r'<!--\s*wp:([a-z0-9/-]+)(?:\s|-->)', content)
    closes = re.findall(r'<!--\s*/wp:([a-z0-9/-]+)\s*-->', content)
    from collections import Counter
    oc, cc = Counter(opens), Counter(closes)
    issues: List[str] = []
    for name in sorted(set(oc) | set(cc)):
        if oc[name] != cc[name]:
            issues.append(f"unbalanced wp:{name} ({oc[name]} open / {cc[name]} close)")
    return issues
```
- [ ] **Step 4: Run — PASS**  •  **Step 5: Commit** `git commit -am "feat: add Gutenberg block-balance validity safeguard"`

---

### Task 11: Table flag plumbing (`warnings` on result dicts + logging)

**Files:** Modify `blog_extractor.py` — add `detect_content_warnings`; wire into both result dicts (`:1538` sync, `:1615` async) and log.

- [ ] **Step 1: Test**
```python
def test_detect_warnings_counts_tables(ex):
    content = to_blocks(ex, SIMPLE_TABLE)
    warns = ex.detect_content_warnings(content)
    assert any("table" in w.lower() for w in warns)
    assert ex.detect_content_warnings(to_blocks(ex, "<p>no tables</p>")) == []
```
- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** — add method:
```python
def detect_content_warnings(self, content: str) -> List[str]:
    """Human-readable review flags for a post's converted content (tables, malformed blocks)."""
    warnings_list: List[str] = []
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        tables = [t for t in soup.find_all('table') if not t.find_parent('table')]
        if tables:
            n = len(tables)
            warnings_list.append(f"{n} table{'s' if n != 1 else ''} preserved — review formatting")
    for issue in self._validate_gutenberg(content):
        warnings_list.append(f"malformed block: {issue}")
    return warnings_list
```
  - In `extract_blog_data` (before `data = {` at ~1537) and `extract_blog_data_async` (~1614):
```python
content_warnings = self.detect_content_warnings(content)
for _w in content_warnings:
    self._log('warning', f"  ⚠ {_w}")
```
  - Add `'warnings': content_warnings,` as the last key in both `data = {...}` dicts.
- [ ] **Step 4: Run — PASS** + full suite green.  •  **Step 5: Commit** `git commit -am "feat: flag posts containing tables via result warnings + log"`

---

### Task 12: Surface `warnings` in CLI output (`extract.py`)

**Files:** Modify `extract.py` — read the JSON/CSV/summary writer; add `warnings` to JSON objects and a `Warnings` column to CSV (join list with "; "); print a per-post warning line in the rich output.

- [ ] **Step 1:** Locate where per-post results are serialized (grep `csv`/`json.dump`/`writerow` in `extract.py`).
- [ ] **Step 2:** Add `warnings` to JSON output and CSV rows using `"; ".join(post.get('warnings', []))`.
- [ ] **Step 3:** In the rich summary loop, if `post.get('warnings')`, print `console.print(f"[yellow]⚠ {url}: {'; '.join(warnings)}[/yellow]")`.
- [ ] **Step 4:** Run `ruff check .` + `mypy` (docs command). Commit `git commit -am "feat: surface content warnings in CLI CSV/JSON/summary"`

---

### Task 13: Surface `warnings` in Streamlit UI (`streamlit_app.py`)

**Files:** Modify `streamlit_app.py` — where extraction results are displayed, render `result.get('warnings')`.

- [ ] **Step 1:** Locate results rendering (grep `extraction_results`, `st.success`, results table).
- [ ] **Step 2:** For each successful result with warnings, show `st.warning("⚠ " + "; ".join(result['warnings']))` (or add a "Notes" column if results are shown as a table).
- [ ] **Step 3:** Commit `git commit -am "feat: surface table/content warnings in Streamlit results"`

---

### Task 14: Final gate + docs

- [ ] **Step 1:** Full suite: `& ".\blog-extractor-env\Scripts\python.exe" -m pytest tests/ -v` → all green.
- [ ] **Step 2:** `& ".\blog-extractor-env\Scripts\ruff.exe" check .` and `mypy blog_extractor.py extract.py streamlit_app.py create_distribution.py` → clean.
- [ ] **Step 3:** Note the real test suite in `CONTRIBUTING.md`/`CLAUDE.md` testing sections (replace "no tests" implication with `pytest tests/`).
- [ ] **Step 4:** Commit `git commit -am "docs: document content-transform test suite"`.
- [ ] **Step 5 (manual, optional):** Live-validate against the two reported DealerOn URLs (requires `playwright install chromium`); confirm tables appear as blocks and warnings fire.

## Self-review

- **Spec coverage:** P1 tables → Tasks 1–3, 11; flag → 11–13. P2 siblings → 4–7 (hr, figure, inline, dl). P3 validity → 8 (code), 9 (list/quote/heading). Safeguard → 10. Tests → all. Docs/rollout → 14. ✓
- **Placeholder scan:** Tasks 12–13 describe locate-then-edit rather than exact line code because those files aren't yet read; steps name the exact grep anchors and transformation. Acceptable (discovery tasks), resolved at execution.
- **Type consistency:** `_table_to_block`, `_validate_gutenberg`, `detect_content_warnings` names used consistently; `warnings` key name consistent across result dicts, CLI, and UI. ✓
