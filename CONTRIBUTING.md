# Contributing Guide

Thank you for contributing to the blog extraction tool! This guide covers development setup, adding platform support, testing, and contribution guidelines.

## Development Setup

### Prerequisites

- Python 3.10+ (recommended: 3.13)
- Git
- Virtual environment tool (venv or uv)

### Quick Setup

#### Automated (Recommended for First-Time Contributors)

```bash
# Clone repository
git clone <repository-url>
cd blog-tool

# Run setup script
# Windows: double-click setup.bat
# Mac/Linux: bash setup.sh

# Install dev dependencies
blog-extractor-env\Scripts\activate      # Windows
source blog-extractor-env/bin/activate   # Mac/Linux
pip install -r requirements-dev.txt
```

#### Manual Setup (Advanced)

```bash
# Clone repository
git clone <repository-url>
cd blog-tool

# Create virtual environment
python -m venv blog-extractor-env

# Activate virtual environment
blog-extractor-env\Scripts\activate          # Windows
source blog-extractor-env/bin/activate       # Mac/Linux

# Install production dependencies
pip install -r requirements.txt          # Full (CLI + Streamlit)
# Or for CLI only: pip install -r requirements-cli.txt

# Install dev dependencies
pip install -r requirements-dev.txt

# Install Playwright browsers
python -m playwright install --with-deps
```

### Dev Dependencies

The project uses modern Python tooling:

- **ruff** (0.14.1) - Fast linting and formatting
- **mypy** (1.18.2) - Static type checking
- **pytest** (8.4.2) - Testing framework
- **pytest-asyncio** (1.2.0) - Async test support
- **types-requests** - Type stubs for requests library

## Adding Platform Support

### Step 1: Platform Detection

Edit `blog_extractor.py`, find the `detect_platform()` method (around line 400):

```python
def detect_platform(self, soup) -> str:
    # ... existing platforms ...

    # Add your platform
    if soup.find('meta', {'name': 'generator', 'content': lambda x: x and 'NewPlatform' in x}):
        return 'NewPlatform'

    # Or check for specific CSS classes
    if soup.select_one('div.new-platform-blog-content'):
        return 'NewPlatform'

    return 'Unknown'
```

**Detection strategies:**

- Meta tags: `<meta name="generator" content="PlatformName">`
- CSS classes: Platform-specific class names
- URL patterns: Domain or path patterns
- Script tags: Platform-specific JavaScript includes

### Step 2: Content Extraction

In the `extract_content()` method (around line 500):

```python
def extract_content(self, soup, platform: str):
    content = None

    # ... existing platforms ...

    elif platform == 'NewPlatform':
        # Try platform-specific selector first
        content = soup.select_one('div.new-platform-article-content')

        if not content:
            # Fallback to generic selector
            content = soup.select_one('article.post-content')

    # ... rest of method ...
```

**Best practices:**

- Use specific selectors (classes/IDs unique to platform)
- Always provide a fallback to generic selectors
- Test with multiple URLs from the platform
- Ensure content area excludes navigation/footer/sidebar

### Step 3: Category Extraction (Optional)

If the platform has blog-specific categories, add extraction logic in `extract_categories()` (around line 600):

```python
def extract_categories(self, soup, platform: str) -> List[str]:
    categories = []

    # ... existing platforms ...

    if platform == 'NewPlatform':
        cat_elements = soup.select('div.new-platform-categories a.category')
        categories = [cat.get_text(strip=True) for cat in cat_elements]

    # Filter out common non-category terms
    return [cat for cat in categories if cat.lower() not in self.excluded_terms]
```

### Step 4: Tag Extraction (Optional)

Similar to categories, in `extract_tags()` (around line 700):

```python
def extract_tags(self, soup, platform: str) -> List[str]:
    tags = []

    # ... existing platforms ...

    if platform == 'NewPlatform':
        tag_elements = soup.select('ul.new-platform-tags li')
        tags = [tag.get_text(strip=True) for tag in tag_elements]

    return [tag for tag in tags if tag.lower() not in self.excluded_terms]
```

### Step 5: Testing

Test your new platform support thoroughly:

```bash
# Create a test file with URLs from the new platform
echo "https://newplatform-example.com/blog/post-1" > test_urls.txt
echo "https://newplatform-example.com/blog/post-2" >> test_urls.txt

# Run extraction
python extract.py --verbose

# Verify output
cat output/blog_posts.xml  # Check XML is valid
```

**Test checklist:**

- [ ] Platform is correctly detected
- [ ] Content extraction is clean (no nav/footer/ads)
- [ ] Images are extracted and resolved
- [ ] Categories/tags are correct (not site-wide terms)
- [ ] Links within content are preserved
- [ ] Author and date are extracted
- [ ] WordPress XML imports successfully

### Step 6: Update Documentation

Update the supported platforms list in:

- `README.md` - Under "Supported Platforms"
- `CLAUDE.md` - Platform detection section
- `ARCHITECTURE.md` - Platform detection examples

## Code Quality

### Linting

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check . --fix

# Check specific files
ruff check blog_extractor.py
```

**Key rules:**

- Sort imports (isort-compatible)
- Remove unused imports (F401)
- No bare `except` clauses (E722)
- Remove unused variables (F841)
- No f-strings without placeholders (F541)

### Type Checking

```bash
# Check all main files
mypy blog_extractor.py extract.py streamlit_app.py

# Check specific file
mypy blog_extractor.py
```

**Current status:**

- Some methods lack type hints
- Goal: Full type coverage for all public methods

### Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_extractor.py

# Run with coverage
pytest --cov=blog_extractor
```

**Test areas:**

- Platform detection
- Content extraction
- Image URL resolution
- Duplicate detection
- XML generation

## Pull Request Guidelines

### Before Submitting

1. **Lint your code:** `ruff check . --fix`
2. **Type check:** `mypy blog_extractor.py extract.py streamlit_app.py`
3. **Run tests:** `pytest`
4. **Test manually:** Extract real blog posts from the platform
5. **Update docs:** Add platform to README.md if applicable

### PR Description Template

```markdown
## Description

Brief description of changes (e.g., "Add support for NewPlatform blog posts")

## Type of Change

- [ ] Bug fix
- [ ] New feature (platform support)
- [ ] Performance improvement
- [ ] Documentation update
- [ ] Code refactoring

## Testing

- [ ] Tested with Playwright
- [ ] Tested with requests fallback
- [ ] Verified WordPress XML import
- [ ] Linting passes (ruff)
- [ ] Type checking passes (mypy)
- [ ] Tests pass (pytest)

## Platform Details (if applicable)

- **Platform name:** NewPlatform
- **Test URLs:** (provide 2-3 example blog post URLs)
- **Special considerations:** (any platform-specific quirks)
```

### Commit Messages

Use clear, descriptive commit messages:

```bash
# Good
git commit -m "Add support for NewPlatform blog extraction"
git commit -m "Fix image URL resolution for WebDAM redirects"
git commit -m "Improve error handling in async processing"

# Not recommended
git commit -m "fix bug"
git commit -m "update code"
```

## Code Style

### Imports

Group imports in this order:

```python
# 1. Standard library
import sys
import asyncio
from typing import Optional, List

# 2. Third-party
import requests
from bs4 import BeautifulSoup

# 3. Local
from blog_extractor import BlogExtractor
```

### Docstrings

Use descriptive docstrings for public methods:

```python
def extract_blog_data(self, url: str) -> Dict[str, Any]:
    """
    Extract blog post data from a URL.

    Args:
        url: Full URL to the blog post (must start with http/https)

    Returns:
        Dict containing:
            - status: 'success', 'failed', or 'duplicate'
            - title: Post title
            - content: HTML content
            - categories: List of categories
            - tags: List of tags
            - author: Author name
            - date: Publication date (ISO format)
            - url: Original URL

    Raises:
        ValueError: If URL is invalid
        requests.RequestException: If fetch fails after retries
    """
```

### Error Handling

Always use specific exception types:

```python
# Good
try:
    response = requests.get(url)
    response.raise_for_status()
except requests.Timeout:
    self._log("error", f"Timeout fetching {url}")
except requests.RequestException as e:
    self._log("error", f"Request failed: {e}")

# Avoid bare except
try:
    # ...
except:  # Don't do this
    pass
```

## Common Issues

### Playwright Subprocess Error (Windows)

**Symptom:** `RuntimeError: Event loop is closed`

**Solution:** No longer an issue in Python 3.8+ on Windows. ProactorEventLoop is the default, and the code uses modern `asyncio.run()` pattern which handles event loop creation automatically.

Note: The deprecated `WindowsProactorEventLoopPolicy` code was removed in Python 3.14+ to use modern asyncio patterns.

### Import Errors

**Symptom:** `ModuleNotFoundError: No module named 'bs4'`

**Solution:** Activate virtual environment and install dependencies:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

### Type Checking Errors

**Symptom:** mypy reports missing types

**Solution:** Add type hints or use `# type: ignore` for third-party libraries:

```python
from typing import Optional, List, Dict, Any

def my_function(url: str) -> Dict[str, Any]:
    # ...
```

## Project Structure Best Practices

### File Organization

- **blog_extractor.py** - Core logic only, no CLI/UI code
- **extract.py** - CLI wrapper, imports from blog_extractor
- **streamlit_app.py** - UI wrapper, imports from blog_extractor

### Separation of Concerns

- Keep extraction logic in BlogExtractor class
- Keep UI logic in streamlit_app.py
- Keep CLI logic in extract.py
- Avoid mixing concerns

### Configuration

Use class initialization for configuration:

```python
extractor = BlogExtractor(
    callback=my_callback,
    download_images=True,
    skip_duplicates=True,
    request_delay=2,
    max_retries=3
)
```

Don't use global variables or environment variables for configuration.

## Getting Help

- **Questions:** Open a GitHub issue with the "question" label
- **Bugs:** Open a GitHub issue with reproduction steps
- **Feature requests:** Open a GitHub issue describing the use case
- **Documentation:** Improve docs via PR

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
