# Architecture Documentation

Technical deep dive into the blog extraction tool's architecture, design patterns, and implementation details.

## Table of Contents

- [Three-Layer Architecture](#three-layer-architecture)
- [File Structure](#file-structure)
- [Core Design Patterns](#core-design-patterns)
- [Content Extraction Pipeline](#content-extraction-pipeline)
- [Image Handling System](#image-handling-system)
- [Concurrency Model](#concurrency-model)
- [Deployment Options](#deployment-options)

## Three-Layer Architecture

### 1. Core Engine - blog_extractor.py (~2000 lines)

**Purpose:** Standalone extraction engine that can be embedded in any Python application

**Key Components:**

- `BlogExtractor` class - Main orchestrator
- Platform detection system
- Content extraction with HTML-to-Gutenberg conversion
- Image URL resolution and optional download
- Duplicate detection (MD5 hashing)
- WordPress WXR 1.2 XML generation
- Async/sync dual-mode operation

**Important Methods:**

- `extract_blog_data(url)` - Main entry point (line ~850)
- `extract_blog_data_async(url)` - Async version (line ~1100)
- `detect_platform(soup)` - Platform auto-detection (line ~400)
- `extract_content(soup, platform)` - Content extraction (line ~500)
- `_resolve_image_url(url)` - WebDAM/dynamic URL resolution (line ~1477)
- `_download_image(url, img_dir)` - Optional local image download (line ~1594, skipped if download_images=False)
- `_convert_relative_urls_to_absolute(content, base_url)` - URL normalization (line ~1550)
- `save_to_xml(filename)` - WordPress WXR generation (line ~1753)
- `process_urls_concurrently(urls, max_concurrent)` - Async batch processing (line ~300)

### 2. CLI Interface - extract.py (~250 lines)

**Purpose:** Command-line wrapper with rich argument parsing

**Features:**

- Argparse-based CLI with 15+ options
- Progress bars via tqdm
- Multiple output formats (XML, JSON, CSV)
- Concurrent processing coordination
- Domain migration helpers (relative URLs, find/replace)

**Entry Point:** `main()` function orchestrates the extraction flow

### 3. Web UI - streamlit_app.py (~680 lines)

**Purpose:** User-friendly web interface with real-time feedback

**Features:**

- URL input (paste or upload file)
- Real-time progress tracking with callback logging
- Link analysis (internal vs external)
- Domain find/replace
- Download buttons for XML and links
- Advanced settings panel

**Key Functions:**

- `process_urls()` - Main extraction orchestrator (line ~309)
- `logging_callback(level, message)` - Filters/displays logs in UI (line ~321)
- `get_concurrent_settings()` - User settings retrieval (line ~240)

## File Structure

```bash
blog-tool/
├── blog_extractor.py      # Core extraction engine
├── extract.py             # CLI interface
├── streamlit_app.py       # Web UI
├── requirements.txt           # Full dependencies (CLI + Streamlit)
├── requirements-cli.txt       # CLI only (minimal deps)
├── requirements-streamlit.txt # Streamlit + dependencies
├── requirements-dev.txt       # Dev tools (ruff, mypy, pytest)
├── urls.txt              # Input file (one URL per line)
├── output/               # Generated output
│   ├── blog_posts.xml    # WordPress WXR 1.2
│   ├── extracted_links.txt
│   ├── blog_posts.json
│   ├── blog_posts.csv
│   └── images/           # Downloaded images (optional, CLI --download-images only)
├── CLAUDE.md             # AI-focused constraints
├── README.md             # User documentation
├── ARCHITECTURE.md       # This file
└── CONTRIBUTING.md       # Developer guide
```

## Core Design Patterns

### 1. Callback-Based Logging

**Pattern:** Dependency injection for logging

```python
class BlogExtractor:
    def __init__(self, callback: Optional[Callable[[str, str], None]] = None):
        self.callback = callback

    def _log(self, level: str, message: str):
        if self.callback:
            self.callback(level, message)  # UI can intercept
        logger.log(getattr(logging, level.upper()), message)
```

**Benefits:**

- Decouples UI from extraction logic
- Allows real-time progress updates in Streamlit
- No tight coupling between layers

**Usage:**

```python
def my_callback(level, message):
    if level == 'error':
        st.error(message)
    elif level == 'info':
        st.info(message)

extractor = BlogExtractor(callback=my_callback)
```

### 2. Graceful Degradation

**Pattern:** Fallback chain for web scraping

```bash
1. Try async Playwright (best for JS-heavy sites)
   ↓ fails
2. Try sync Playwright
   ↓ fails
3. Fall back to requests library (works everywhere)
```

**Implementation:**

- Async path: `fetch_with_playwright_async()` → line ~250
- Sync path: `fetch_with_playwright_sync()` → line ~150
- Fallback: `fetch_with_requests()` → line ~400

**Benefits:**

- Works on Streamlit Cloud (no Playwright)
- Best performance when Playwright available
- Always works somewhere

### 3. Content Hashing for Duplicates

**Pattern:** MD5 hashing of normalized content

```python
def get_content_hash(self, content: str) -> str:
    normalized = content.strip().lower()
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()
```

**Storage:** `self.seen_hashes` - Set of MD5 hashes

**Location:** Lines ~850, ~1230 in `extract_blog_data()`

**Why MD5:**

- Fast for content hashing (not security)
- Sufficient collision resistance for blog posts
- Future: Consider blake2s for FIPS compliance

### 4. Retry Logic with Exponential Backoff

**Pattern:** Exponential backoff with configurable retries

```python
for attempt in range(max_retries):
    try:
        # ... attempt operation ...
        return result
    except Exception as exc:
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # 1s, 2s, 4s, 8s
            await asyncio.sleep(wait_time)
        else:
            raise
```

**Locations:**

- Async Playwright: line ~250-320
- Sync Playwright: line ~150-220
- Requests fallback: line ~400-450

### 5. Semaphore-Based Concurrency

**Pattern:** Limit concurrent async operations

```python
async def process_urls_concurrently(self, urls, max_concurrent=5):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_limit(url):
        async with semaphore:
            return await self.extract_blog_data_async(url)

    tasks = [process_with_limit(url) for url in urls]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

**Location:** Line ~300

**Why 5 concurrent:**

- Balance between speed and server load
- Higher values (10+) risk rate limiting/bans
- Safe range: 3-5

## Content Extraction Pipeline

### Step 1: Platform Detection (line ~400)

```python
def detect_platform(self, soup) -> str:
    # Check meta tags
    if soup.find('meta', {'name': 'generator', 'content': lambda x: x and 'wix' in x.lower()}):
        return 'Wix'

    # Check CSS classes
    if soup.select_one('div.dealer-inspire-content'):
        return 'DealerInspire'

    # ... more platform checks ...

    return 'Unknown'
```

**Supported Platforms:**

1. Wix - Meta generator tag
2. Webflow - CSS class patterns
3. WordPress - Meta generator or wp-content
4. DealerOn - Specific div classes
5. DealerInspire - URL patterns and classes
6. Medium - Domain and structure
7. Squarespace - Meta tags
8. Blogger - Domain pattern

### Step 2: Content Extraction (line ~500)

**Strategy:**

1. Use platform-specific selectors (highest priority)
2. Fall back to generic selectors
3. Validate content (>100 chars of text)
4. Extract only from content areas (exclude nav/footer)

**Example - DealerOn:**

```python
if platform == 'DealerOn':
    content = soup.select_one('div.blog__article__content__text')
    if not content:
        content = soup.select_one('article')  # Fallback
```

### Step 3: Metadata Extraction

**Categories (line ~600):**

- Platform-specific selectors (e.g., `div.meta-below-content`)
- Filters out dealer/SEO terms (dealer, inventory, service, etc.)
- Does NOT use `meta[name="keywords"]` (too generic)

**Tags (line ~700):**

- Blog-specific tag areas only
- Excludes navigation items
- Deduplicates with categories

**Author (line ~800):**

- Platform-specific author selectors
- Falls back to meta tags
- Default: "Admin"

**Published Date (line ~850):**

- Tries multiple date formats
- Falls back to current date
- Normalized to WordPress format

### Step 4: URL Normalization (line ~1550)

**Critical Function:** `_convert_relative_urls_to_absolute()`

**Process:**

1. Parse content with BeautifulSoup
2. Find all `<a>` tags → make hrefs absolute
3. Find all `<img>` tags → resolve and download images
4. Preserve button attributes (`data-*`)
5. **Use `formatter="minimal"`** to prevent URL line breaks

### Step 5: Image Resolution (line ~1477-1550)

**Two-phase process:**

## Phase 1: URL Resolution

```python
def _resolve_image_url(self, url: str) -> str:
    # Detect WebDAM/dynamic URLs
    if 'webdamdb.com' in url or 'dealerdotcom' in url:
        # Follow redirect to S3
        response = requests.head(url, allow_redirects=True)
        final_url = response.url
        # Strip signed parameters
        return re.sub(r'[?&](signature|expires|...)=.*', '', final_url)
    return url
```

## Phase 2: Local Download

```python
def _download_image(self, url: str, img_dir: Path) -> Optional[str]:
    resolved_url = self._resolve_image_url(url)
    filename = Path(urlparse(resolved_url).path).name

    response = requests.get(resolved_url, stream=True)
    with open(img_dir / filename, 'wb') as f:
        f.write(response.content)

    return resolved_url  # Return HTTPS URL for XML
```

**Why HTTPS URLs in XML:**

WordPress server can't access `file://` URLs. The tool always puts HTTPS URLs in XML so WordPress can fetch images during import.

- **Default (Streamlit):** No local downloads, images imported via XML only
- **Optional (CLI --download-images):** Local backup saved to output/images/, XML still uses HTTPS URLs
- **WordPress Import:** Fetches images from HTTPS URLs and adds to Media Library

## Image Handling System

### WebDAM URL Resolution

**Problem:** Many dealer sites use WebDAM with temporary signed URLs

```bash
Original URL:
https://dealerdotcom.webdamdb.com/embeddables/display.php?size=550&webid=XYZ123

Redirects to:
https://s3.amazonaws.com/bucket/image.jpg?signature=ABC&expires=1234567890

After stripping:
https://s3.amazonaws.com/bucket/image.jpg
```

**Detection Logic:**

```python
def _is_dynamic_url(self, url: str) -> bool:
    dynamic_patterns = [
        'webdamdb.com',
        'dealerdotcom.com/cdn',
        'display.php',
        'image.php'
    ]
    return any(pattern in url for pattern in dynamic_patterns)
```

**Resolution Cache:**

```python
self.resolved_urls: Dict[str, str] = {}  # Cache to avoid duplicate requests
```

### Image Processing Flow

```bash
1. Find <img> tag in content
   ↓
2. Check if URL is relative → make absolute
   ↓
3. Check if URL is dynamic (WebDAM) → resolve to S3
   ↓
4. Check cache → if resolved before, use cached URL
   ↓
5. (Optional) Download to output/images/ directory if download_images=True
   ↓
6. Update <img src="https://..."> with resolved HTTPS URL in XML
   ↓
7. WordPress import fetches images from HTTPS URLs during import
```

**Note:** Streamlit UI always uses `download_images=False`. CLI users can enable with `--download-images` flag.

## Concurrency Model

### Async Architecture

**Event Loop:** Windows defaults to `ProactorEventLoop` (Python 3.8+), no manual policy setting needed. Code uses modern `asyncio.run()` pattern.

**Semaphore Control:**

```python
semaphore = asyncio.Semaphore(5)  # Max 5 concurrent

async def process_with_limit(url):
    async with semaphore:
        return await self.extract_blog_data_async(url)
```

**Gather Pattern:**

```python
tasks = [process_with_limit(url) for url in urls]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

**Error Handling:**

- Each URL extraction wrapped in try/except
- Exceptions returned as results (not raised)
- Failed URLs logged but don't stop batch

### Thread Safety

**Not thread-safe:** `BlogExtractor` uses instance state (`seen_hashes`, `posts`, etc.)

**Solution:** Create one `BlogExtractor` per thread or use async only

## Deployment Options

### 1. Local Development

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
python -m playwright install --with-deps
streamlit run streamlit_app.py
```

**Best performance:** Full Playwright support for JavaScript-heavy sites

### 2. Streamlit Cloud

```bash
# requirements.txt (Playwright omitted)
beautifulsoup4==4.14.2
requests==2.32.5
lxml==6.0.2
tqdm==4.67.1
streamlit==1.50.0
```

**Fallback mode:** Uses requests library only (no Playwright)

**Trade-off:** May miss JS-rendered content on some platforms

### 3. Docker

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt && \
    python -m playwright install --with-deps

COPY . .
CMD ["streamlit", "run", "streamlit_app.py"]
```

**Benefits:** Consistent environment, Playwright support

### 4. CI/CD (GitHub Actions)

```yaml
- name: Install dependencies
  run: |
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    python -m playwright install --with-deps

- name: Run tests
  run: |
    ruff check .
    mypy blog_extractor.py extract.py streamlit_app.py
    pytest
```

## WordPress XML Generation

### WXR 1.2 Format (line ~1753)

**Structure:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" ...>
  <channel>
    <title>Imported Blog</title>
    <item>
      <title><![CDATA[Post Title]]></title>
      <content:encoded><![CDATA[<!-- wp:html -->...]]></content:encoded>
      <wp:post_type>post</wp:post_type>
      <category domain="category" nicename="..."><![CDATA[Category]]></category>
    </item>
  </channel>
</rss>
```

**Critical Implementation:**

```python
# MUST use formatter="minimal" to prevent URL line breaks
final_xml = soup.decode(formatter="minimal")
```

**Gutenberg Block Conversion:**

- Regular content → `<!-- wp:html -->`
- Images → `<!-- wp:image -->`
- Embeds → `<!-- wp:embed -->`
- Buttons → `<!-- wp:html -->` (preserves data-\* attributes)

## Performance Characteristics

### Single URL Extraction

- **With Playwright:** 10-20 seconds (includes page load + JS execution)
- **With requests:** 2-5 seconds (HTML only)

### Concurrent Processing (5 URLs)

- **Sequential:** 50-100 seconds
- **Concurrent:** 15-25 seconds (3-5x speedup)

### Memory Usage

- **Per URL:** ~10-50 MB (depends on content size)
- **Concurrent (5):** ~50-250 MB
- **Large batches (100+ URLs):** Consider streaming XML generation

## Known Limitations

1. **Line numbers in docs:** Get stale after refactoring (use function names when possible)
2. **No streaming XML:** Large migrations (1000+ posts) may consume significant memory
3. **Single Playwright instance:** Each URL launches new browser (overhead)
4. **MD5 hashing:** Not FIPS-compliant (use blake2s if needed)
5. **No incremental updates:** Re-processes all URLs on each run

## Future Optimizations

1. **Shared Playwright context:** Reuse browser across URLs (~30% faster)
2. **Streaming XML writer:** Constant memory usage for large migrations
3. **Incremental processing:** Skip already-processed URLs
4. **Better type hints:** Full mypy coverage
5. **CI automation:** GitHub Actions for ruff/mypy/pytest
