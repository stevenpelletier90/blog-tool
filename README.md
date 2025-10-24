# Blog Post Extractor & WordPress Migration Tool

A production-ready tool that extracts blog posts from any platform (Wix, WordPress, Medium, DealerOn, DealerInspire, etc.) and converts them into WordPress-compatible XML format for easy migration.

## Features

- **8+ Platform Support**: Wix, Webflow, WordPress, DealerOn, DealerInspire, Medium, Squarespace, Blogger
- **Smart Content Extraction**: Automatically detects platform and extracts clean content
- **Image Protection**: Downloads images locally and resolves WebDAM/dynamic URLs to permanent S3 URLs
- **Duplicate Detection**: MD5 content hashing prevents duplicate posts
- **Concurrent Processing**: Process multiple URLs simultaneously (3-5x faster)
- **Multiple Interfaces**: CLI and web UI (Streamlit)
- **WordPress WXR 1.2**: Generates standard WordPress export format

## Quick Start

### Installation

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac/Linux

# Install dependencies
# For both CLI and web UI:
pip install -r requirements.txt

# Or CLI only (no Streamlit, includes Pillow 12+):
pip install -r requirements-cli.txt

# Optional: Enhanced features (requires code changes to use)
pip install -r requirements-extras.txt

# Install Playwright browsers (recommended for best results)
python -m playwright install --with-deps
```

### Usage

#### Web UI (Recommended)

```bash
streamlit run streamlit_app.py
```

Then open <http://localhost:8501> in your browser.

**Features:**

- Paste URLs directly or upload a file
- Real-time progress tracking
- Link analysis (internal vs external)
- Find/replace for domain migration
- Download XML and extracted links

#### CLI

```bash
# Basic usage - reads from urls.txt
python extract.py

# Concurrent processing (3-5x faster)
python extract.py --concurrent 5

# Multiple output formats
python extract.py --format all

# Custom settings
python extract.py --delay 3 --retries 5 --verbose

# Domain migration helpers
python extract.py --relative-links --no-download-images

# Help
python extract.py --help
```

### Input Format

Create a `urls.txt` file with one URL per line:

```text
https://example.com/blog/post-1
https://example.com/blog/post-2
https://example.com/blog/post-3
```

### Output

All output is saved to the `output/` directory:

- **blog_posts.xml** - WordPress WXR 1.2 format (import to WordPress)
- **extracted_links.txt** - All hyperlinks found by post
- **images/** - Downloaded images (local backup)
- **blog_posts.json** - JSON format (CLI only)
- **blog_posts.csv** - CSV format (CLI only)

## Supported Platforms

- **Wix** - Full support including lazy-loaded content
- **Webflow** - Rich text content extraction
- **WordPress** - Direct content extraction
- **DealerOn** - Automotive dealer platform
- **DealerInspire** - Automotive dealer platform
- **Medium** - Article extraction
- **Squarespace** - Blog content
- **Blogger** - Google's blog platform

## Key Features Explained

### Image Protection

The tool protects against images being removed from source sites:

1. **Resolves Dynamic URLs**: Follows redirects from WebDAM/PHP endpoints to permanent S3 URLs
2. **Local Downloads**: Saves all images to `output/images/` directory
3. **WordPress Compatible**: XML contains HTTPS URLs for WordPress import

### Duplicate Detection

Uses MD5 content hashing to skip duplicate posts automatically. Same content at different URLs? The tool detects it and skips the duplicate.

### Concurrent Processing

Process 5 URLs simultaneously for 3-5x speed improvement:

```bash
python extract.py --concurrent 5
```

Safe range: 3-5 concurrent requests (higher values may trigger rate limiting)

## Importing to WordPress

1. Extract blog posts using this tool
2. In WordPress admin, go to **Tools → Import**
3. Choose **WordPress** importer (install if needed)
4. Upload `output/blog_posts.xml`
5. Assign authors and download images
6. Done! Your posts are now in WordPress

## Troubleshooting

### Windows: Playwright Subprocess Error

If you get asyncio subprocess errors on Windows, the tool automatically fixes this. No action needed.

### Playwright Not Installed

The tool falls back to `requests` library if Playwright isn't installed. For best results (JavaScript-heavy sites), install Playwright:

```bash
python -m playwright install --with-deps
```

### Rate Limiting / IP Bans

Reduce concurrent requests or add delay between requests:

```bash
python extract.py --concurrent 3 --delay 5
```

### Images Not Downloading

Check your internet connection and ensure the source site allows image downloads. The tool will use the original URL if local download fails.

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Linting
ruff check .

# Type checking
mypy blog_extractor.py extract.py streamlit_app.py

# Tests
pytest
```

### Adding Platform Support

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on adding support for new blog platforms.

## Technical Details

For architecture details, design patterns, and code references, see:

- [CLAUDE.md](CLAUDE.md) - AI-focused critical constraints
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical deep dive
- [CONTRIBUTING.md](CONTRIBUTING.md) - Developer guide

## License

See LICENSE file for details.

## Support

For issues, questions, or feature requests, please open an issue on the repository.
