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


# --- Elementor (WordPress theme-builder) content extraction -------------

ELEMENTOR_POST_BODY = (
    "<p>In this topic, we will focus on how window tinting provides varying "
    "degrees of privacy for vehicle occupants and contents inside.</p>"
    "<h2>Understanding Privacy Levels</h2>"
    '<p>Learn more in <a href="https://example.com/related-post/">our guide</a>.</p>'
    '<img src="https://i0.wp.com/example.com/wp-content/uploads/2025/09/tint.jpeg" alt="Tinted car"/>'
)

ELEMENTOR_SINGLE_POST_PAGE = (
    "<html><body>"
    '<div data-elementor-type="single-post" class="elementor">'
    '<h1 class="elementor-heading-title">Window Tint for Privacy</h1>'
    '<div class="elementor-widget elementor-widget-theme-post-content">'
    + ELEMENTOR_POST_BODY +
    "</div></div>"
    '<footer><div class="elementor-widget elementor-widget-text-editor">'
    "<p>Automotive Elegance Address: 22R Dale St. Andover, Massachusetts 01810 "
    "Hours: Monday through Friday nine to five, Saturday by appointment only.</p>"
    "</div></footer>"
    "</body></html>"
)

ELEMENTOR_WP_POST_PAGE = (
    "<html><body>"
    '<div data-elementor-type="wp-post" class="elementor">'
    '<div class="elementor-widget elementor-widget-text-editor">'
    + ELEMENTOR_POST_BODY +
    "</div></div>"
    "</body></html>"
)


def test_elementor_theme_post_content_extracted(ex):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(ELEMENTOR_SINGLE_POST_PAGE, "html.parser")
    content = ex.extract_content(soup)
    assert "window tinting provides varying degrees of privacy" in content
    assert 'class="wp-block-heading"' in content
    # Post title and footer widgets live outside the post-content widget
    assert "Window Tint for Privacy" not in content
    assert "22R Dale St" not in content
    assert ex._validate_gutenberg(content) == []


def test_elementor_content_yields_images_and_links(ex):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(ELEMENTOR_SINGLE_POST_PAGE, "html.parser")
    content = ex.extract_content(soup)
    images = ex.extract_images_from_content(content)
    assert len(images) == 1
    assert images[0]["src"].startswith("https://i0.wp.com/")
    links = ex.extract_links(soup, "https://example.com/window-tint-for-privacy/")
    assert any(link["url"] == "https://example.com/related-post/" for link in links)


def test_elementor_built_post_body_extracted(ex):
    # Classic theme where the post body itself is built with Elementor
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(ELEMENTOR_WP_POST_PAGE, "html.parser")
    content = ex.extract_content(soup)
    assert "window tinting provides varying degrees of privacy" in content
    assert ex._validate_gutenberg(content) == []


LAZY_PLACEHOLDER = (
    "data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'"
    "%20viewBox='0%200%20800%20534'%3E%3C/svg%3E"
)


def test_lazy_load_placeholder_swapped_for_real_image(ex):
    # WordPress lazy-load (Jetpack/Smush): src is an SVG placeholder, real
    # URL lives in data-lazy-src. Static fetches must recover the real URL.
    from bs4 import BeautifulSoup
    page = (
        '<html><body><div data-elementor-type="single-post">'
        '<div class="elementor-widget-theme-post-content">'
        "<p>Padding text so the content passes the one hundred character "
        "minimum length check used by extract_content in the extractor.</p>"
        f'<img src="{LAZY_PLACEHOLDER}" '
        'data-lazy-src="https://i0.wp.com/example.com/wp-content/uploads/real.jpg?resize=800%2C534" '
        'alt="Car"/>'
        "</div></div></body></html>"
    )
    soup = BeautifulSoup(page, "html.parser")
    content = ex.extract_content(soup)
    assert "data:image/svg+xml" not in content
    images = ex.extract_images_from_content(content)
    assert len(images) == 1
    assert images[0]["src"].startswith("https://i0.wp.com/example.com/")


def test_lazy_load_srcset_only_uses_largest_candidate(ex):
    from bs4 import BeautifulSoup
    page = (
        '<html><body><div data-elementor-type="single-post">'
        '<div class="elementor-widget-theme-post-content">'
        "<p>Padding text so the content passes the one hundred character "
        "minimum length check used by extract_content in the extractor.</p>"
        f'<img src="{LAZY_PLACEHOLDER}" '
        'data-lazy-srcset="https://example.com/img-300.jpg 300w, '
        'https://example.com/img-2560.jpg 2560w, '
        'https://example.com/img-1024.jpg 1024w" alt="Car"/>'
        "</div></div></body></html>"
    )
    soup = BeautifulSoup(page, "html.parser")
    content = ex.extract_content(soup)
    images = ex.extract_images_from_content(content)
    assert len(images) == 1
    assert images[0]["src"] == "https://example.com/img-2560.jpg"


def test_elementor_full_page_post_extracted(ex):
    # Service/landing posts built as full Elementor page designs
    from bs4 import BeautifulSoup
    page = (
        '<html><body><div data-elementor-type="wp-page" class="elementor">'
        '<div class="elementor-widget elementor-widget-text-editor">'
        + ELEMENTOR_POST_BODY +
        "</div></div></body></html>"
    )
    soup = BeautifulSoup(page, "html.parser")
    content = ex.extract_content(soup)
    assert "window tinting provides varying degrees of privacy" in content
    assert ex._validate_gutenberg(content) == []


# --- Featured image -> _thumbnail_id attachment --------------------------

XML_NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "wp": "http://wordpress.org/export/1.2/",
}


def _make_post(**overrides):
    post = {
        "status": "success",
        "url": "https://example.com/my-post/",
        "title": "My Post",
        "content": "<!-- wp:paragraph -->\n<p>Body</p>\n<!-- /wp:paragraph -->",
        "content_length": 4,
        "author": "admin",
        "date": "2025-09-10T12:28:34+00:00",
        "categories": [],
        "tags": [],
        "links": [],
        "platform": "wordpress",
        "images": [],
        "warnings": [],
    }
    post.update(overrides)
    return post


def test_featured_image_extracted_from_og_meta(ex):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(
        '<html><head><meta property="og:image" '
        'content="https://i0.wp.com/example.com/wp-content/uploads/hero.jpg?fit=1000%2C667"/>'
        "</head><body></body></html>",
        "html.parser",
    )
    assert ex.extract_featured_image(soup).startswith("https://i0.wp.com/")


def test_featured_image_written_as_thumbnail_attachment(ex, tmp_path):
    import xml.etree.ElementTree as ET
    hero = "https://i0.wp.com/example.com/wp-content/uploads/hero.jpg?fit=1000%2C667"
    ex.extracted_data.append(_make_post(featured_image=hero))
    ex.save_to_xml("out.xml")
    items = ET.parse(tmp_path / "out.xml").getroot().findall(".//item")
    posts = [i for i in items if i.findtext("wp:post_type", "", XML_NS) == "post"]
    atts = [i for i in items if i.findtext("wp:post_type", "", XML_NS) == "attachment"]
    assert len(posts) == 1 and len(atts) == 1
    thumb_id = None
    for meta in posts[0].findall("wp:postmeta", XML_NS):
        if meta.findtext("wp:meta_key", "", XML_NS) == "_thumbnail_id":
            thumb_id = meta.findtext("wp:meta_value", "", XML_NS)
    assert thumb_id, "post should carry a _thumbnail_id postmeta"
    assert atts[0].findtext("wp:post_id", "", XML_NS) == thumb_id
    assert atts[0].findtext("wp:attachment_url", "", XML_NS) == hero


def test_featured_image_not_duplicated_when_also_in_content(ex, tmp_path):
    import xml.etree.ElementTree as ET
    hero = "https://example.com/wp-content/uploads/hero.jpg"
    ex.extracted_data.append(_make_post(
        featured_image=hero,
        images=[{"src": hero, "alt": "", "width": "", "height": ""}],
    ))
    ex.save_to_xml("out.xml")
    items = ET.parse(tmp_path / "out.xml").getroot().findall(".//item")
    atts = [i for i in items if i.findtext("wp:post_type", "", XML_NS) == "attachment"]
    assert len(atts) == 1


def test_shared_image_across_posts_has_no_duplicate_post_ids(ex, tmp_path):
    # An image reused by several posts (common on Elementor sites) must not
    # emit attachment items sharing one wp:post_id — importers that key items
    # by ID reject the file ("An item with the same key has already been added")
    import xml.etree.ElementTree as ET
    shared = "https://example.com/wp-content/uploads/shared.jpg"
    for slug in ("post-one", "post-two", "post-three"):
        ex.extracted_data.append(_make_post(
            url=f"https://example.com/{slug}/",
            featured_image=shared,
            images=[{"src": shared, "alt": "", "width": "", "height": ""}],
        ))
    ex.save_to_xml("out.xml")
    items = ET.parse(tmp_path / "out.xml").getroot().findall(".//item")
    ids = [i.findtext("wp:post_id", "", XML_NS) for i in items]
    assert len(ids) == len(set(ids)), f"duplicate wp:post_id values: {sorted(ids)}"
    atts = [i for i in items if i.findtext("wp:post_type", "", XML_NS) == "attachment"]
    assert len(atts) == 1
    att_id = atts[0].findtext("wp:post_id", "", XML_NS)
    posts = [i for i in items if i.findtext("wp:post_type", "", XML_NS) == "post"]
    assert len(posts) == 3
    for p in posts:
        thumbs = [m.findtext("wp:meta_value", "", XML_NS)
                  for m in p.findall("wp:postmeta", XML_NS)
                  if m.findtext("wp:meta_key", "", XML_NS) == "_thumbnail_id"]
        assert thumbs == [att_id]


# --- Widget markup: buttons, FAQs, cards, pull quotes must keep structure ---

def test_button_element_with_onclick_becomes_button_block(ex):
    out = to_blocks(ex, '<p>Ready?</p><button onclick="location.href=\'/contact\'">Get a Quote</button>')
    assert "<!-- wp:html -->" in out
    assert 'class="btn btn-cta"' in out
    assert 'href="/contact"' in out
    assert "<p>Get a Quote</p>" not in out


def test_details_summary_faq_becomes_heading_and_paragraph(ex):
    raw = ('<details class="e-n-accordion-item"><summary>Does PPF damage paint?</summary>'
           "<p>No, it protects it.</p></details>"
           "<details><summary>How long does it last?</summary><p>5-10 years.</p></details>")
    out = to_blocks(ex, raw)
    assert out.count("<!-- wp:heading") == 2
    assert "Does PPF damage paint?" in out and "How long does it last?" in out
    assert "<p>No, it protects it.</p>" in out and "<p>5-10 years.</p>" in out
    assert "<details" not in out and "<summary" not in out


def test_elementor_accordion_becomes_headings_and_paragraphs(ex):
    raw = ('<div class="elementor-accordion">'
           '<div class="elementor-accordion-item"><div class="elementor-tab-title">Q1?</div>'
           '<div class="elementor-tab-content">Answer one.</div></div>'
           '<div class="elementor-accordion-item"><div class="elementor-tab-title">Q2?</div>'
           '<div class="elementor-tab-content">Answer two.</div></div></div>')
    out = to_blocks(ex, raw)
    assert out.count("<!-- wp:heading") == 2
    assert "<p>Answer one.</p>" in out and "<p>Answer two.</p>" in out
    assert "Q1? Answer one." not in out


def test_card_grid_divs_do_not_merge_into_one_paragraph(ex):
    raw = ('<div class="row"><div class="card"><div class="card-title">Gold Package</div>'
           '<div class="card-body">Full front coverage</div></div>'
           '<div class="card"><div class="card-title">Silver Package</div>'
           '<div class="card-body">Partial coverage</div></div></div>')
    out = to_blocks(ex, raw)
    assert "Gold Package Full front coverage" not in out
    assert out.count("<!-- wp:heading") == 2  # card titles become headings
    assert "<p>Full front coverage</p>" in out and "<p>Partial coverage</p>" in out


def test_sibling_text_divs_become_separate_paragraphs(ex):
    out = to_blocks(ex, "<div>First block of text.</div><div>Second block of text.</div>")
    assert out.count("<!-- wp:paragraph -->") == 2
    assert "First block of text. Second block of text." not in out


def test_pull_quote_div_becomes_quote_block(ex):
    raw = ('<div class="quote-wrapper"><div class="pull-quote">Best shop in town!</div>'
           '<div class="quote-author">John D.</div></div>')
    out = to_blocks(ex, raw)
    assert "<!-- wp:quote -->" in out
    assert "Best shop in town!" in out
    assert "Best shop in town! John D." not in out


def test_div_inside_table_cell_keeps_native_table(ex):
    out = to_blocks(ex, "<table><tbody><tr><td><div>cell text</div></td><td>plain</td></tr></tbody></table>")
    assert "<!-- wp:table -->" in out
    assert "<td>cell text </td>" in out or "<td>cell text</td>" in out


def test_button_wrapper_div_leaves_no_empty_paragraph(ex):
    raw = ('<div class="elementor-button-wrapper">'
           '<a class="elementor-button" href="/quote"><span class="elementor-button-text">Go</span></a></div>')
    out = to_blocks(ex, raw)
    assert "<!-- wp:html -->" in out and 'href="/quote"' in out
    assert "<p></p>" not in out and "<p> </p>" not in out


# --- Cross-cutting: output is always well-formed & balanced -------------

@pytest.mark.parametrize(
    "raw",
    [SIMPLE_TABLE, MERGED_TABLE, "<p>x</p><hr/><p>y</p>",
     "<dl><dt>a</dt><dd>b</dd></dl>", "<h2>H</h2><ul><li>i</li></ul>"],
)
def test_output_blocks_are_balanced(ex, raw):
    out = to_blocks(ex, raw)
    assert ex._validate_gutenberg(out) == []
