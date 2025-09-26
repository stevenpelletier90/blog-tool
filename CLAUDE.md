# Blog Extractor - Playwright-Powered Tool

Simplified, modern tool to extract blog posts from Wix and other platforms, converting them to WordPress XML format with comprehensive link extraction.

## Quick Start

1. Add URLs to `urls.txt` (one per line)
2. Run: `blog-extractor-env/Scripts/python.exe extract.py`
3. Find output in:
   - `output/blog_posts.xml` - WordPress XML for import
   - `output/extracted_links.txt` - All hyperlinks from blog content

## Key Features

### ✅ Modern Extraction

- **Playwright-only approach** - Handles JavaScript-heavy sites (especially Wix) perfectly
- **Wix-specific selectors** - Extracts categories and tags using aria-label attributes
- **Content-focused link extraction** - Only gets links from blog content (not navigation/menus)

### ✅ Rich Data Extraction

- **Complete blog data** - Title, content, author, date, categories, tags
- **Character count** - Shows content length for each post
- **Hyperlink extraction** - All links within blog content with text and URLs
- **Clean output** - No duplicate debug messages

### ✅ WordPress-Ready Output

- **WordPress XML (WXR) format** - Direct import to WordPress
- **Organized link export** - Separate txt file with all hyperlinks by post
- **Proper encoding** - Handles special characters and HTML correctly

## File Structure

- `blog_extractor.py` - Core extraction engine (Playwright-powered)
- `extract.py` - Simple CLI wrapper
- `urls.txt` - Input URLs (ready with 40 Chevrolet blog URLs)
- `output/` - Generated files (XML + links)
- `requirements.txt` - Minimal dependencies (requests, beautifulsoup4, lxml, playwright)

## Configuration

Settings in `blog_extractor.py`:

```python
URLS_FILE = "urls.txt"
OUTPUT_DIR = "output"
REQUEST_DELAY = 2  # Seconds between requests
```

## Dependencies

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

## Sample Output

```bash
[1/40] Processing: https://example.com/blog/post
✓ Success - Amazing Blog Post Title
  Content: 2,547 characters
  Links: 3 found
  Categories: Technology, Tips
  Tags: JavaScript, Web Development

=== Summary ===
Total URLs: 40
Successful: 38
Failed: 2
Success rate: 95.0%

WordPress XML saved to: output/blog_posts.xml
Links saved to: output/extracted_links.txt
```

## Current Status

- **Production-ready** - Zero type errors, clean code
- **40 Chevrolet URLs** from kirkbrotherschevroletofvicksburg.com loaded
- **Modern tooling** - Using latest Playwright for reliability
- **Comprehensive extraction** - Gets everything: content, metadata, links

## Run Command

```bash
blog-extractor-env/Scripts/python.exe extract.py
```

## Technical Notes

- Uses Playwright for JavaScript rendering (3x faster than Selenium)
- Content-area detection prevents extraction of navigation/menu links
- Handles Wix's dynamic loading and aria-label category/tag structure
- Clean, type-safe code with proper error handling
