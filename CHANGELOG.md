# Changelog

All notable changes to the Blog Post Extractor & WordPress Migration Tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Elementor Support**: Extract from Elementor-built WordPress sites, including featured images
- **Table Preservation**: HTML tables survive extraction and export as proper Gutenberg table blocks
- **Structured Block Preservation**: Buttons, FAQs, cards, and pull quotes export as structured blocks instead of flattened paragraphs
- **Content Review Flags**: CLI and Streamlit UI surface posts that may need manual review after extraction
- **Content-Transform Test Suite**: pytest coverage for tables, Gutenberg blocks, and WordPress XML validity
- **Faster WordPress Fast Path**: Quicker extraction for standard WordPress sites via the requests library

### Fixed

- Duplicate `wp:post_id` values in exported XML (IDs are now guaranteed unique)
- `<p>` tags no longer injected inside table cells (malformation guard)
- Content fidelity issues in WordPress export

### Changed

- Dependency floors bumped to current releases
- Documentation updated: README notes the developer docs (CLAUDE.md, ARCHITECTURE.md, CONTRIBUTING.md) and the project creation date (September 26, 2025)

### Developer

- ruff lint config (`ruff.toml`) and a Claude Code PostToolUse formatter hook

## [1.0.0] - 2025-11-19

### Added

- **8+ Platform Support**: Wix, Webflow, WordPress, DealerOn, DealerInspire, Medium, Squarespace, Blogger
- **Smart Content Extraction**: Automatic platform detection with platform-specific selectors
- **Image Protection**: WebDAM/dynamic URL resolution to permanent S3 URLs for WordPress import
- **Duplicate Detection**: MD5 content hashing prevents duplicate posts automatically
- **Concurrent Processing**: Process 3-5 URLs simultaneously for 3-5x speed improvement
- **Multiple Interfaces**:
  - CLI interface with argparse (`extract.py`)
  - Streamlit web UI (`streamlit_app.py`)
- **WordPress WXR 1.2 Export**: Standard WordPress export format for easy import
- **Multiple Output Formats**: XML, JSON, CSV (CLI only)
- **Link Extraction**: Comprehensive hyperlink extraction from blog posts
- **Link Analysis**: Internal vs external link categorization
- **Find/Replace**: Domain migration support for changing URLs during migration
- **Image Handling**:
  - Automatic image resolution for dynamic URLs
  - Optional local backup download (CLI only with --download-images flag)
  - HTTPS URLs in XML for WordPress automatic import
- **Automated Setup Scripts**:
  - `setup.bat` for Windows (one-click installation)
  - `setup.sh` for Mac/Linux (automated bash script)
- **Quick Launcher**: `run_extractor.bat` for Windows users
- **Streamlit Cloud Support**: Full Playwright browser installation on cloud deployment
- **Comprehensive Documentation**:
  - README.md - User guide
  - ARCHITECTURE.md - Technical deep dive
  - CONTRIBUTING.md - Developer onboarding
  - USER_GUIDE.md - Detailed usage instructions
  - QUICKSTART.md - Fast start guide
  - CLAUDE.md - AI-focused critical constraints
- **Development Tools**:
  - ruff for linting
  - mypy for type checking
  - pytest for testing
  - Multiple requirements files for different use cases
- **Python 3.14+ Support**: Modern asyncio patterns without deprecated APIs
- **Windows Asyncio Fix**: Automatic ProactorEventLoop setup for Playwright subprocess support
- **Callback-based Logging**: Allows UI integration without tight coupling
- **Platform-specific Selectors**: Optimized extraction for each supported platform
- **Content Validation**: Minimum character count validation to ensure quality extraction
- **Category/Tag Filtering**: Excludes SEO/navigation terms from blog categories
- **Graceful Degradation**: Async Playwright → Sync Playwright → requests library fallback
- **License**: MIT License for maximum permissiveness

### Technical Implementation

- BeautifulSoup with `formatter="minimal"` to prevent WordPress URL truncation
- HTTPS URLs in WordPress XML (not file:// paths) for server-side image download
- MD5 content hashing for duplicate detection
- Semaphore-based concurrent processing with asyncio
- Three-layer architecture: core extractor, CLI, web UI
- Virtual environment setup (`blog-extractor-env/`)

### Security

- Input validation for URLs
- Safe HTML parsing with BeautifulSoup
- No code execution from scraped content

### Compatibility

- Python 3.8+
- Windows, Mac, Linux support
- Streamlit Cloud deployment ready

### Known Limitations

- Default 5 concurrent requests (higher may trigger rate limiting)
- MD5 hashing (consider blake2s for FIPS compliance in future)
- Playwright browser download ~300MB

---

## Release Notes

This is the initial production release of the Blog Post Extractor & WordPress Migration Tool. The tool has been extensively tested across multiple blog platforms and is ready for production use.

**Recommended for:**

- Blog migrations to WordPress
- Content archival
- Bulk blog post extraction
- Agency/freelancer workflow automation

**Installation:**
Simply run `setup.bat` (Windows) or `bash setup.sh` (Mac/Linux) to install everything automatically!

**Next Steps:**
See README.md for usage instructions or run `python extract.py --help` for CLI options.
