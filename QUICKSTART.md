# Blog Extractor - Quick Start Guide

## Installation

### Automated (Recommended)

**Windows:** Double-click `setup.bat`

**Mac/Linux:** Run `bash setup.sh`

The script automatically installs everything (Python packages, Playwright browsers, creates folders).

### Manual

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (first time only)
python -m playwright install chromium
```

## Basic Usage

### CLI (Recommended for Production)

```bash
# Simple extraction
python extract.py

# Fast concurrent mode (3-5x faster!)
python extract.py --concurrent 5

# Quiet mode (for scripts)
python extract.py --concurrent 5 --quiet
```

### Web UI (User-Friendly)

```bash
streamlit run streamlit_app.py
# Opens browser at http://localhost:8501
```

## Common Commands

```bash
# Extract with all features
python extract.py --concurrent 5 --download-images --format xml

# Fast extraction without images
python extract.py --concurrent 5 --no-images --no-download-images

# Custom input/output
python extract.py --urls myblog.txt --output results/ --concurrent 5

# Verbose logging for debugging
python extract.py --concurrent 5 --verbose

# Export all formats (XML, JSON, CSV)
python extract.py --concurrent 5 --format all
```

## Output Files

After extraction, find your results in `output/`:

- **blog_posts.xml** - Import this into WordPress (Tools → Import → WordPress)
- **extracted_links.txt** - All links found in blog posts
- **images/** - Downloaded images (backup protection)

## Performance Tips

- **Use --concurrent 5** for 3-5x faster extraction
- **Use --quiet** to reduce console output overhead
- **Use --no-download-images** if you don't need local image backups

## Troubleshooting

### Issue: "Playwright not installed"

```bash
python -m playwright install chromium
```

### Issue: Images not downloading

- Make sure `--download-images` is enabled (it's default)
- Check you have write permissions to `output/images/`

### Issue: Slow extraction

- Use `--concurrent 5` for parallel processing
- Reduce `--delay` (default is 2 seconds between requests)

## WordPress Import

1. Go to WordPress Admin → Tools → Import
2. Install/activate "WordPress" importer
3. Upload `output/blog_posts.xml`
4. Map authors and select "Download and import file attachments"
5. Click "Submit"

Done! Your blog posts are now in WordPress.

## Development

```bash
# Install dev tools
pip install -r requirements-dev.txt

# Run linter
ruff check .

# Run type checker
mypy blog_extractor.py

# Run tests
pytest
```

## Support

- Documentation: See [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md)
- Issues: Check [CLAUDE.md](CLAUDE.md) for known constraints
- Contributing: See [CONTRIBUTING.md](CONTRIBUTING.md)
