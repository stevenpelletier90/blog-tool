# CLAUDE.md

This file provides guidance to Claude Code when working with this repository. For user documentation, see [README.md](README.md). For technical details, see [ARCHITECTURE.md](ARCHITECTURE.md).

Path-specific rules live in `.claude/rules/` (extraction code, setup scripts, Streamlit Cloud) and load when Claude reads or edits a matching file.

## Project Overview

A blog post extraction and migration tool that converts blog content from any platform (Wix, WordPress, Medium, DealerOn, DealerInspire, etc.) into WordPress-compatible XML format. Uses Playwright for JavaScript-heavy sites with fallback to requests library.

## Core Architecture

**Three-layer design:**

1. **blog_extractor.py** - Core extraction engine with async/sync scraping, platform detection, image resolution
2. **extract.py** - CLI interface with argparse, concurrent processing, multiple formats
3. **streamlit_app.py** - Web UI with real-time progress tracking

**Key patterns:**

- Callback-based logging for UI integration without tight coupling
- Graceful degradation: async Playwright → sync Playwright → requests
- Content hashing (blake2s) prevents duplicate processing
- Semaphore-based concurrent processing with asyncio

## Deployment

- **CI/Docker:** Cache virtual environment + run `python -m playwright install --with-deps` during build
- **Virtual environment:** Uses `blog-extractor-env/` by default (created by setup scripts)

## Files Overview

- **blog_extractor.py** - Core `BlogExtractor` class
- **extract.py** - CLI wrapper with argparse
- **streamlit_app.py** - Web UI with progress tracking
- **setup.bat** - Automated Windows setup script (installs everything)
- **setup.sh** - Automated Mac/Linux setup script (installs everything)
- **run_extractor.bat** - Quick launcher for Windows (runs CLI extractor)
- **create_distribution.py** - Build script: packages a distribution zip (excludes dev/internal files)
- **packages.txt** - System dependencies for Streamlit Cloud Playwright support
- **requirements.txt** - Full dependencies (CLI + Streamlit)
- **requirements-cli.txt** - CLI only (no Streamlit; same `pillow>=12.3.0` floor as requirements.txt)
- **requirements-dev.txt** - Dev tooling (ruff, mypy, pytest)

For detailed architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Testing & Quality

```bash
# Linting (the gate — ruff config lives in ruff.toml)
ruff check .

# Type checking
mypy blog_extractor.py extract.py streamlit_app.py create_distribution.py

# Tests (content-transform suite: tables, Gutenberg blocks, WP validity)
pytest tests/
```

Install dev tools: `pip install -r requirements-dev.txt`

There are no git hooks — nothing gates a commit. Run the checks above yourself.

**Don't run `ruff format` here.** This repo has never adopted the
formatter: `ruff check .` passes clean while `ruff format` would rewrite most of
blog_extractor.py, burying every one-line edit under a mass reformat and applying a
standard the gate never checks. If you want ruff's formatter, adopt it as its own
deliberate `ruff format .` commit first.

**Adding a dev-only file? Add it to `EXCLUDE_PATTERNS` in `create_distribution.py`.**
That script uses a blocklist, so anything not listed ships to end users in the zip.
`ruff.toml` is excluded there for exactly this reason.

See [CONTRIBUTING.md](CONTRIBUTING.md) for full developer setup.
