# Blog Extractor - Playwright-Powered Tool

Simplified, modern tool to extract blog posts from Wix and other platforms, converting them to WordPress XML format with comprehensive link extraction.

## Quick Start

### Option 1: Easy Batch File (Recommended)

1. Add URLs to `urls.txt` (one per line)
2. Double-click `run_extractor.bat`
3. Find output in:
   - `output/blog_posts.xml` - WordPress XML for import
   - `output/extracted_links.txt` - All hyperlinks from blog content

### Option 2: Command Line

1. Add URLs to `urls.txt` (one per line)
2. Run: `blog-extractor-env/Scripts/python.exe extract.py`
3. Check the `output/` folder for results

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

## Run Commands

### Windows (Easy)

```cmd
Double-click: run_extractor.bat
```

### Windows (Command Line)

```cmd
blog-extractor-env\Scripts\python.exe extract.py
```

### Mac/Linux

```bash
blog-extractor-env/bin/python extract.py
```

## Prerequisites

1. **Virtual environment** with dependencies installed
2. **urls.txt file** with blog URLs (one per line)
3. **Playwright browser** installed (`playwright install chromium`)

## Troubleshooting

**"Virtual environment not found"**: Make sure `blog-extractor-env/` folder exists with Python installed

**"urls.txt not found"**: Create a text file named `urls.txt` with your blog URLs

**"No URLs to process"**: Check that URLs in `urls.txt` start with `http` or `https`

**Import fails in WordPress**: Ensure WordPress allows file uploads and try importing smaller batches

## Technical Notes

- Uses Playwright for JavaScript rendering (3x faster than Selenium)
- Content-area detection prevents extraction of navigation/menu links
- Handles Wix's dynamic loading and aria-label category/tag structure
- Clean, type-safe code with proper error handling
- Generates proper WordPress WXR format with Gutenberg blocks
