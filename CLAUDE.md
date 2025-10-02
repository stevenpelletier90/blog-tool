# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready blog post extraction and migration tool that converts blog content from any platform (Wix, WordPress, Medium, DealerOn, DealerInspire, etc.) into WordPress-compatible XML format. The tool uses Playwright for JavaScript-heavy sites with intelligent fallback to requests library for cloud deployment compatibility.

## Core Architecture

### Three-Layer Design

1. **blog_extractor.py** - Core extraction engine (`BlogExtractor` class)

   - Handles async/sync web scraping with Playwright/requests
   - Platform auto-detection (8+ platforms: Wix, Webflow, WordPress, DealerOn, DealerInspire, Medium, Squarespace, Blogger)
   - Content extraction with HTML-to-Gutenberg block conversion
   - Duplicate detection via MD5 content hashing
   - Exponential backoff retry logic (3 attempts)
   - Semaphore-based concurrent processing with asyncio
   - WordPress WXR 1.2 XML generation

2. **extract.py** - CLI interface with argparse

   - Simple wrapper around BlogExtractor
   - Supports concurrent mode (`--concurrent 5`)
   - Multiple output formats (`--format xml|json|csv|all`)
   - Progress bars with tqdm

3. **streamlit_app.py** - Web UI
   - User-friendly interface at <http://localhost:8501>
   - Real-time progress tracking with logging callbacks
   - Link analysis (internal vs external)
   - Find/replace for domain migration
   - Download buttons for XML/links

### Key Design Patterns

- **Callback-based logging** - `BlogExtractor.__init__(callback=...)` allows UI integration without tight coupling
- **Content hashing** - `seen_hashes` set prevents duplicate processing using MD5
- **Platform detection** - `detect_platform()` uses meta tags and CSS classes to auto-detect blog platforms
- **Graceful degradation** - Falls back from async Playwright → sync Playwright → requests
- **BeautifulSoup minimal formatter** - Critical for preserving long URLs without line breaks (`soup.decode(formatter="minimal")`)

## Running the Tool

### Development Setup

```bash
# Activate virtual environment
blog-extractor-env\Scripts\activate  # Windows
blog-extractor-env/bin/activate      # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (optional but recommended)
playwright install chromium
```

### Running Commands

#### Streamlit Web UI (Recommended)

```bash
# Windows
blog-extractor-env\Scripts\streamlit run streamlit_app.py

# Mac/Linux
blog-extractor-env/bin/streamlit run streamlit_app.py
```

#### CLI - Basic Usage

```bash
# Windows
blog-extractor-env\Scripts\python.exe extract.py

# Mac/Linux
blog-extractor-env/bin/python extract.py
```

#### CLI - Advanced Options

```bash
# Concurrent mode (3-5x faster)
python extract.py --concurrent 5

# All formats
python extract.py --format all

# Custom settings
python extract.py --delay 3 --retries 5 --verbose

# Help
python extract.py --help
```

### Input/Output

- **Input**: `urls.txt` (one URL per line, must start with http/https)
- **Output**: `output/` directory
  - `blog_posts.xml` - WordPress WXR 1.2 format
  - `extracted_links.txt` - All hyperlinks by post
  - `blog_posts.json` - JSON format (CLI only)
  - `blog_posts.csv` - CSV format (CLI only)

## Testing & Validation

### Syntax Checks

```bash
# Compile-check Python files
blog-extractor-env\Scripts\python.exe -m py_compile blog_extractor.py
blog-extractor-env\Scripts\python.exe -m py_compile extract.py
blog-extractor-env\Scripts\python.exe -m py_compile streamlit_app.py
```

### Windows-Specific Fix

The codebase includes a critical Windows asyncio fix at the top of blog_extractor.py:

```python
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
```

This prevents subprocess errors when using Playwright on Windows.

## Critical Implementation Details

### URL Preservation in WordPress XML

The tool uses `soup.decode(formatter="minimal")` when generating XML to prevent BeautifulSoup from adding line breaks in long `href` attributes, which would cause WordPress to truncate URLs during import. This is implemented in `_convert_relative_urls_to_absolute()` at line 1200.

### Content Extraction Strategy

1. **Platform-specific selectors** take priority (e.g., `div.blog__article__content__text` for DealerOn)
2. **Generic fallbacks** if platform selectors fail
3. **Content validation** - must have >100 characters of text
4. **Link extraction** - only from content areas, excludes navigation/metadata

### Categories/Tags Filtering

The tool explicitly excludes site-wide SEO terms and navigation items:

- Does NOT use `meta[name="keywords"]` (contains dealer/SEO terms)
- Filters out: dealer, dealership, inventory, service, parts, finance, etc.
- Only extracts from blog-specific areas (e.g., `div.meta-below-content`, `ul.blog__entry__content__tags`)

### Button Links Preservation

Button/CTA links are preserved with all `data-*` attributes intact:

- Standardizes class to `btn btn-cta`
- Adds required `data-dotagging-*` attributes if missing
- Exported as `<!-- wp:html -->` blocks for exact preservation

## Async Concurrent Processing

The tool supports concurrent processing with semaphore-based rate limiting:

```python
async def process_urls_concurrently(urls, max_concurrent=5):
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [self._extract_with_semaphore(url, semaphore) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

Performance: 40 URLs in ~15-20 seconds concurrent vs ~80 seconds sequential

## Dependencies

- **beautifulsoup4** - HTML parsing
- **requests** - HTTP fallback
- **lxml** - XML generation
- **playwright** - JavaScript-heavy sites (optional but recommended)
- **tqdm** - CLI progress bars
- **streamlit** - Web UI

## Deployment Notes

- **Streamlit Cloud**: Works without Playwright (falls back to requests)
- **Local**: Install Playwright for best results
- **Virtual environment**: Required - uses `blog-extractor-env/`

## Current Status

- ✅ Zero Pylance errors
- ✅ Production-ready
- ✅ Full type hints
- ✅ Windows/Mac/Linux compatible
- ✅ 16+ major features
- ✅ Supports 8+ blog platforms with generic fallback
