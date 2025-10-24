# CLAUDE.md

This file provides critical guidance to Claude Code when working with this repository. For user documentation, see [README.md](README.md). For technical details, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Project Overview

A production-ready blog post extraction and migration tool that converts blog content from any platform (Wix, WordPress, Medium, DealerOn, DealerInspire, etc.) into WordPress-compatible XML format. Uses Playwright for JavaScript-heavy sites with intelligent fallback to requests library.

## Core Architecture

**Three-layer design:**

1. **blog_extractor.py** - Core extraction engine with async/sync scraping, platform detection, image resolution
2. **extract.py** - CLI interface with argparse, concurrent processing, multiple formats
3. **streamlit_app.py** - Web UI with real-time progress tracking

**Key patterns:**

- Callback-based logging for UI integration without tight coupling
- Graceful degradation: async Playwright → sync Playwright → requests
- Content hashing (MD5) prevents duplicate processing
- Semaphore-based concurrent processing with asyncio

## Critical Constraints - DO NOT CHANGE

### 1. BeautifulSoup Formatter

**Location:** `_convert_relative_urls_to_absolute()` around line 1550-1600

```python
# MUST use formatter="minimal"
soup.decode(formatter="minimal")
```

**Why:** BeautifulSoup adds line breaks in long `href` attributes without this
**Impact:** WordPress truncates URLs split across lines during import, breaking all links
**Never use:** `formatter="html"` or `formatter="html5"`

### 2. HTTPS URLs in WordPress XML

**Location:** `save_to_xml()` around line 1750-1800

**Why:** WordPress server cannot access `file://` URLs (they're local to your machine)
**Impact:** Images won't import to WordPress media library
**Solution:** Use resolved HTTPS URLs in XML; download locally as backup only

### 3. Windows Asyncio Event Loop Policy

**Location:** Top of blog_extractor.py (lines 8-12)

```python
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
```

**Why:** Prevents subprocess errors on Windows with Playwright
**Impact:** Tool crashes on Windows without this
**Required:** Must execute before any async operations; in future refactors prefer setting this in CLI entry points to avoid surprising host apps

### 4. MD5 Content Hashing

**Location:** `extract_blog_data()` around line 850 and 1230

**Why:** Prevents duplicate posts when same content appears at different URLs
**Impact:** Faster extraction, cleaner WordPress import
**Note:** Uses content only, not title (titles may differ for same content)
**Future:** For FIPS-compliant environments, migrate to `hashlib.blake2s` or SHA-256

### 5. Concurrent Request Limits

**Default:** 5 concurrent requests (semaphore limit)

**Why:** Too many concurrent requests overwhelm servers or trigger rate-limiting
**Impact:** 10+ concurrent may cause failures or IP bans
**Safe range:** 3-5 concurrent requests

## Image Handling - Critical Feature

### WebDAM/Dynamic URL Resolution

Many dealer sites use WebDAM (Digital Asset Management) serving images through dynamic PHP endpoints that redirect to temporary S3 signed URLs:

```bash
https://dealerdotcom.webdamdb.com/embeddables/display.php?size=550&webid=XYZ123
  ↓ redirects to ↓
https://s3.amazonaws.com/bucket/image.jpg?signature=...&expires=...
```

**The tool MUST:**

1. Detect dynamic endpoints (WebDAM, dealer.com URLs with parameters)
2. Follow redirects to get actual S3 URL using `requests.head()`
3. Strip signed parameters (expiration/signature) for permanent URLs
4. Cache resolution results to avoid duplicate requests

**Why:** Protects against images being removed from source sites

**Location:** `_resolve_image_url()` and `_download_image()` around line 1477-1550

### Local Image Downloads

**Default:** `download_images=True`

Downloads all images to `output/images/` directory as backup. XML contains HTTPS URLs (not file://) so WordPress can fetch during import.

**Dual protection strategy:**

- Local backup in `output/images/` for permanence
- HTTPS S3 URLs in XML for WordPress import compatibility

## Platform Detection Strategy

**Location:** `detect_platform()` around line 400

Uses meta tags and CSS classes to auto-detect blog platforms. Platform-specific selectors take priority over generic fallbacks.

**Supported:** Wix, Webflow, WordPress, DealerOn, DealerInspire, Medium, Squarespace, Blogger (8+ platforms)

**Adding new platforms:** See [CONTRIBUTING.md](CONTRIBUTING.md#adding-platform-support)

## Content Extraction Rules

**Location:** `extract_content()` around line 500

1. Platform-specific selectors take priority (e.g., `div.blog__article__content__text` for DealerOn)
2. Generic fallbacks if platform selectors fail
3. Content validation - must have >100 characters of text
4. Link extraction - only from content areas, excludes navigation/metadata

### Categories/Tags Filtering

Explicitly excludes site-wide SEO terms and navigation items:

- Does NOT use `meta[name="keywords"]` (contains dealer/SEO terms)
- Filters out: dealer, dealership, inventory, service, parts, finance, etc.
- Only extracts from blog-specific areas (e.g., `div.meta-below-content`)

## Callback-Based Logging Pattern

```python
def _log(self, level: str, message: str):
    if self.callback:
        self.callback(level, message)  # UI can display this
    logger.log(getattr(logging, level.upper()), message)
```

**Why:** Allows UI integration (Streamlit) without tight coupling
**Note:** The extractor calls `logging.basicConfig`; override in CLI/UI entry points if host app needs custom handlers

## Deployment Considerations

- **Streamlit Cloud:** Works without Playwright (falls back to requests)
- **Local:** Install Playwright for best results (`python -m playwright install --with-deps`)
- **CI/Docker:** Cache virtual environment + run `python -m playwright install --with-deps` during build
- **Virtual environment:** Required - default `.venv/` or managed via `uv`

## Files Overview

- **blog_extractor.py** - Core `BlogExtractor` class (~2000 lines)
- **extract.py** - CLI wrapper with argparse (~250 lines)
- **streamlit_app.py** - Web UI with progress tracking (~680 lines)
- **requirements.txt** - Full dependencies (CLI + Streamlit)
- **requirements-cli.txt** - CLI only (no Streamlit, allows newer Pillow)
- **requirements-streamlit.txt** - Streamlit + CLI dependencies
- **requirements-dev.txt** - Dev tooling (ruff, mypy, pytest)

For detailed architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Testing & Quality

```bash
# Linting
ruff check .

# Type checking
mypy blog_extractor.py extract.py streamlit_app.py

# Tests
pytest
```

Install dev tools: `pip install -r requirements-dev.txt`

See [CONTRIBUTING.md](CONTRIBUTING.md) for full developer setup.

## Future Improvements

- Share single Playwright browser/context across URL fetches to reduce launch overhead
- Replace MD5 with `hashlib.blake2s` for FIPS compliance
- Move `logging.basicConfig` to CLI/UI entry points
- Add CI automation (GitHub Actions) for ruff/mypy/pytest
- Generate WordPress XML via streaming writer for memory efficiency on large migrations
