"""Tests for the HTML -> WordPress Gutenberg content transform.

These run the transform directly (clean_html + html_to_gutenberg) with no
network access, and assert the output is faithful AND well-formed / valid
WordPress block markup. See docs/superpowers/specs/2026-07-01-table-preservation-content-fidelity-design.md
"""
import pytest

from blog_extractor import BlogExtractor


@pytest.fixture
def ex(tmp_path):
    """A BlogExtractor wired for offline unit testing (no Playwright, no downloads)."""
    return BlogExtractor(
        output_dir=str(tmp_path),
        callback=None,
        download_images=False,
        skip_playwright=True,
        verbose=False,
    )


def to_blocks(ex, raw):
    """Full transform: sanitize then convert to Gutenberg blocks."""
    return ex.html_to_gutenberg(ex.clean_html(raw))


SIMPLE_TABLE = (
    "<table><thead><tr><th>Model</th><th>MPG</th></tr></thead>"
    "<tbody><tr><td>Traverse</td><td>27</td></tr></tbody></table>"
)
MERGED_TABLE = (
    '<table><tbody><tr><td colspan="2">Spans two</td></tr>'
    "<tr><td>A</td><td>B</td></tr></tbody></table>"
)


# --- Task 1/2/3: tables --------------------------------------------------

def test_simple_table_becomes_native_table_block(ex):
    out = to_blocks(ex, SIMPLE_TABLE)
    assert "<!-- wp:table -->" in out
    assert '<figure class="wp-block-table">' in out
    assert "<th>Model</th>" in out
    assert "<td>Traverse</td>" in out
    assert "<!-- /wp:table -->" in out
    assert "<!-- wp:paragraph -->\n<p>Model" not in out


def test_merged_cell_table_falls_back_to_html_block(ex):
    out = to_blocks(ex, MERGED_TABLE)
    assert "<!-- wp:html -->" in out
    assert 'colspan="2"' in out
    assert "<!-- wp:table -->" not in out


def test_br_in_cell_does_not_inject_paragraph(ex):
    # The upstream <br><br> -> paragraph pass must not put a <p> inside a table cell
    from bs4 import BeautifulSoup
    out = to_blocks(ex, "<table><tbody><tr><td>a<br><br>b</td></tr></tbody></table>")
    soup = BeautifulSoup(out, "html.parser")
    assert all(cell.find("p") is None for cell in soup.find_all(["td", "th"]))
    assert ex._validate_gutenberg(out) == []


def test_table_with_block_cell_falls_back_to_html(ex):
    # A cell containing a block element (list) can't be a valid native table block
    raw = "<table><tbody><tr><td><ul><li>x</li></ul></td></tr></tbody></table>"
    out = to_blocks(ex, raw)
    assert "<!-- wp:html -->" in out
    assert "<!-- wp:table -->" not in out
    assert ex._validate_gutenberg(out) == []


def test_table_cells_keep_links_and_escape_safely(ex):
    raw = (
        '<table><tbody><tr><td><a href="https://x.com">Deal</a></td>'
        "<td>A &amp; B</td></tr></tbody></table>"
    )
    out = to_blocks(ex, raw)
    assert '<a href="https://x.com">Deal</a>' in out
    assert "A &amp; B" in out


# --- Task 4/5/6/7: sibling elements -------------------------------------

def test_hr_becomes_separator(ex):
    out = to_blocks(ex, "<p>Before</p><hr/><p>After</p>")
    assert "<!-- wp:separator -->" in out
    assert 'class="wp-block-separator"' in out
    assert "<!-- /wp:separator -->" in out


def test_figure_caption_preserved(ex):
    raw = (
        '<figure><img src="https://x.com/a.jpg" alt="Car"/>'
        "<figcaption>2026 Model</figcaption></figure>"
    )
    out = to_blocks(ex, raw)
    assert "<!-- wp:image -->" in out
    assert '<figcaption class="wp-element-caption">2026 Model</figcaption>' in out


def test_inline_semantics_survive(ex):
    out = to_blocks(ex, "<p>H<sub>2</sub>O and 1<sup>st</sup> and <mark>hot</mark></p>")
    assert "<sub>2</sub>" in out
    assert "<sup>st</sup>" in out
    assert "<mark>hot</mark>" in out


def test_definition_list_preserved_as_html(ex):
    out = to_blocks(ex, "<dl><dt>MPG</dt><dd>27 city</dd></dl>")
    assert "<!-- wp:html -->" in out
    assert "<dt>MPG</dt>" in out
    assert "<dd>27 city</dd>" in out


# --- Task 8/9: WordPress validity ---------------------------------------

def test_code_block_escapes_specials(ex):
    out = to_blocks(ex, "<pre><code>if a < b && c</code></pre>")
    assert "if a &lt; b &amp;&amp; c" in out
    assert "a < b" not in out


def test_list_has_wp_block_class(ex):
    out = to_blocks(ex, "<ul><li>one</li><li>two</li></ul>")
    assert '<ul class="wp-block-list">' in out


def test_heading_has_wp_block_class(ex):
    out = to_blocks(ex, "<h2>Section</h2>")
    assert 'class="wp-block-heading"' in out


def test_quote_inner_is_p_wrapped(ex):
    out = to_blocks(ex, "<blockquote>Bare quote text</blockquote>")
    assert '<blockquote class="wp-block-quote"><p>Bare quote text</p>' in out


# --- Task 10/11: safeguard + flags --------------------------------------

def test_validate_gutenberg_detects_imbalance(ex):
    assert ex._validate_gutenberg("<!-- wp:table -->\n<figure></figure>") != []
    assert ex._validate_gutenberg(to_blocks(ex, SIMPLE_TABLE)) == []


def test_detect_warnings_counts_tables(ex):
    content = to_blocks(ex, SIMPLE_TABLE)
    warns = ex.detect_content_warnings(content)
    assert any("table" in w.lower() for w in warns)
    assert ex.detect_content_warnings(to_blocks(ex, "<p>no tables</p>")) == []


# --- Cross-cutting: output is always well-formed & balanced -------------

@pytest.mark.parametrize(
    "raw",
    [SIMPLE_TABLE, MERGED_TABLE, "<p>x</p><hr/><p>y</p>",
     "<dl><dt>a</dt><dd>b</dd></dl>", "<h2>H</h2><ul><li>i</li></ul>"],
)
def test_output_blocks_are_balanced(ex, raw):
    out = to_blocks(ex, raw)
    assert ex._validate_gutenberg(out) == []
