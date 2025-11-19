#!/usr/bin/env python3
"""
Blog Content Extractor - Simplified with Playwright Only
Extracts blog posts and converts to WordPress XML using only the best tool.
"""

# Standard library imports
import asyncio
import csv
import hashlib
import html
import io
import json
import logging
import os
import random
import re
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Union, cast
from urllib.parse import urljoin, urlparse

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Playwright

# Third-party imports
import aiofiles
import aiohttp
import filetype
import requests
import validators
from dateutil import parser as dateutil_parser

try:
    from bs4 import BeautifulSoup, Tag
    from bs4.element import NavigableString, PageElement
except ImportError:
    print("ERROR: BeautifulSoup4 is required. Install with: pip install beautifulsoup4")
    raise

# Check if Playwright is available (both sync and async)
async_playwright: Optional[Any] = None
sync_playwright: Optional[Any] = None

try:
    from playwright.async_api import async_playwright as _async_pw
    async_playwright = _async_pw
    HAS_ASYNC_PLAYWRIGHT = True
except ImportError:
    HAS_ASYNC_PLAYWRIGHT = False

try:
    from playwright.sync_api import sync_playwright as _sync_pw
    sync_playwright = _sync_pw
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("WARNING: Playwright not available. Some features may not work.")

# Configuration constants
URLS_FILE = "urls.txt"
OUTPUT_DIR = "output"
REQUEST_DELAY = 2  # seconds between requests
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB - prevent disk fill attacks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def setup_windows_environment() -> None:
    """
    Configure Windows-specific environment settings for asyncio and Playwright.

    This function MUST be called before importing blog_extractor in Windows environments
    to prevent subprocess handling errors and resource warnings.

    Per CLAUDE.md: This setup was moved from module-level to avoid side effects when
    blog_extractor.py is imported as a library.
    """
    if sys.platform.startswith('win'):
        # Windows uses ProactorEventLoop by default (since Python 3.8) for subprocess support
        # Suppress Playwright subprocess cleanup warnings on Windows
        warnings.filterwarnings("ignore", category=ResourceWarning)


class BlogExtractor:
    """Simplified blog extractor using only Playwright for all JavaScript-heavy sites"""

    def __init__(
        self,
        urls_file: str = URLS_FILE,
        output_dir: str = OUTPUT_DIR,
        callback: Optional[Callable[[str, str], None]] = None,
        verbose: bool = True,
        relative_links: bool = False,
        include_images: bool = True,
        skip_duplicates: bool = True,
        download_images: bool = True,
        skip_playwright: bool = False
    ):
        self.urls_file = urls_file
        self.output_dir = output_dir
        self.extracted_data: List[Dict[str, Any]] = []
        self.callback = callback  # Optional callback for UI updates (level, message)
        self.verbose = verbose
        self.relative_links = relative_links  # Keep internal links relative in XML output
        self.include_images = include_images  # Include images in exported content
        self.skip_duplicates = skip_duplicates  # Skip duplicate content (default True)
        self.download_images = download_images  # Download images locally instead of using external URLs
        self.skip_playwright = skip_playwright  # Fast mode - skip Playwright for WordPress/static sites
        self.seen_hashes: Set[str] = set()  # For duplicate detection
        self.resolved_image_cache: Dict[str, str] = {}  # Cache for resolved image URLs
        self.downloaded_images: Dict[str, str] = {}  # Map original URL -> local file path
        # Shared Playwright browser for async concurrent mode (reduces overhead)
        self._playwright: Optional['Playwright'] = None
        self._browser: Optional['Browser'] = None
        self._context: Optional['BrowserContext'] = None

        # Create output directory if it doesn't exist
        Path(self.output_dir).mkdir(exist_ok=True)

        # Create images directory for downloaded images
        self.images_dir = os.path.join(self.output_dir, "images")
        if self.download_images:
            Path(self.images_dir).mkdir(exist_ok=True)

        # User agents for variety
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]

    def _log(self, level: str, message: str) -> None:
        """Log message to logger and optionally call callback for UI updates"""
        # Log to standard logger
        log_level = getattr(logging, level.upper(), logging.INFO)
        logger.log(log_level, message)

        # Call callback if provided (for Streamlit or other UIs)
        if self.callback:
            self.callback(level, message)

        # Print to stdout if verbose (for CLI compatibility)
        elif self.verbose:
            # Handle Unicode encoding issues on Windows console (cp1252)
            try:
                print(message)
            except UnicodeEncodeError:
                # Fallback: encode with error replacement for console display
                print(message.encode('ascii', errors='replace').decode('ascii'))

    async def _get_or_create_browser(self) -> Any:
        """Lazily initialize shared async browser instance for concurrent mode"""
        if self._browser is None and HAS_ASYNC_PLAYWRIGHT and async_playwright is not None:
            self._playwright = await async_playwright().start()
            if self._playwright is not None:
                self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    async def _get_or_create_context(self) -> Any:
        """Get or create browser context with random user agent"""
        if self._context is None:
            browser = await self._get_or_create_browser()
            if browser:
                self._context = await browser.new_context(
                    user_agent=random.choice(self.user_agents),
                    viewport={'width': 1920, 'height': 1080}
                )
        return self._context

    async def close_browser(self) -> None:
        """Close shared browser instance - call this at end of concurrent processing"""
        try:
            if self._context:
                await self._context.close()
                self._context = None
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            # Give asyncio time to cleanup pipes on Windows
            await asyncio.sleep(0.1)
        except Exception:
            # Suppress Windows asyncio cleanup warnings (harmless)
            pass


    def get_content_hash(self, content: str) -> str:
        """Generate blake2s hash of content for duplicate detection (FIPS-compliant)"""
        return hashlib.blake2s(content.encode('utf-8')).hexdigest()

    def _quick_platform_check(self, url: str) -> Optional[str]:
        """Quick platform detection using basic requests (no Playwright) - FAST!

        Returns platform name or None if detection fails.
        This is used to determine if Playwright is needed before wasting time on heavy rendering.
        """
        try:
            # Quick HEAD request first to check accessibility
            head_response = requests.head(url, timeout=5, allow_redirects=True)

            # If HEAD fails, try GET but with minimal timeout
            if head_response.status_code >= 400:
                response = requests.get(url, timeout=10)
            else:
                response = requests.get(url, timeout=10)

            response.raise_for_status()
            html = response.text

            # Quick platform detection from HTML markers
            html_lower = html.lower()

            # JavaScript-heavy platforms (NEED Playwright)
            if 'wix.com' in html_lower or 'data-hook=' in html or '_wix' in html_lower:
                return 'wix'
            if 'webflow.com' in html_lower or 'data-wf-domain' in html or 'data-wf-page' in html:
                return 'webflow'
            if 'blog__article__content__text' in html or 'dealer-content' in html_lower:
                # DealerOn/DealerInspire - Angular/JavaScript heavy
                return 'dealeron'

            # Static platforms (DON'T need Playwright)
            if 'wp-content' in html_lower or 'wordpress' in html_lower or 'wp-includes' in html_lower:
                return 'wordpress'
            if 'blogger.com' in html_lower or 'blogspot.com' in html_lower:
                return 'blogger'
            if 'medium.com' in html_lower:
                return 'medium'
            if 'squarespace' in html_lower:
                return 'squarespace'

            # Generic/unknown - assume static (most sites are)
            return 'generic'

        except Exception as e:
            self._log("debug", f"  Quick platform check failed: {e}")
            return None

    def _needs_javascript_rendering(self, platform: Optional[str]) -> bool:
        """Determine if a platform needs JavaScript rendering (Playwright)

        Returns:
            True if Playwright needed (JS-heavy site)
            False if requests library is sufficient (static site)
        """
        if platform is None:
            # Unknown platform - be safe and use Playwright
            return True

        # Platforms that REQUIRE Playwright (JavaScript-heavy)
        js_heavy_platforms = {'wix', 'webflow', 'dealeron', 'dealerinspire'}

        # Platforms that DON'T need Playwright (static HTML)
        static_platforms = {'wordpress', 'blogger', 'medium', 'squarespace', 'generic'}

        return platform.lower() in js_heavy_platforms

    def detect_platform(self, soup: BeautifulSoup) -> str:
        """Detect the blog platform from HTML structure"""
        # Check meta generator tag
        generator = soup.find('meta', attrs={'name': 'generator'})
        if generator and isinstance(generator, Tag):
            content_attr = generator.get('content')
            if content_attr:
                content = str(content_attr).lower()
                if 'wix' in content:
                    self._log("info", "  Detected platform: Wix")
                    return 'wix'
                if 'wordpress' in content:
                    self._log("info", "  Detected platform: WordPress")
                    return 'wordpress'
                if 'medium' in content:
                    self._log("info", "  Detected platform: Medium")
                    return 'medium'
                if 'squarespace' in content:
                    self._log("info", "  Detected platform: Squarespace")
                    return 'squarespace'
                if 'blogger' in content:
                    self._log("info", "  Detected platform: Blogger")
                    return 'blogger'

        # Check for platform-specific attributes/classes
        if soup.find(attrs={'data-hook': True}):  # Wix signature
            self._log("info", "  Detected platform: Wix (via data-hook)")
            return 'wix'

        # Webflow - check for data-wf-domain or data-wf-page attributes
        if soup.find(attrs={'data-wf-domain': True}) or soup.find(attrs={'data-wf-page': True}):
            self._log("info", "  Detected platform: Webflow")
            return 'webflow'

        # WordPress classes - check for any element with wp- prefix in class
        wp_elements = soup.find_all(class_=True)
        for elem in wp_elements:
            if isinstance(elem, Tag):
                classes = elem.get('class')
                if classes and isinstance(classes, list):
                    for cls in classes:
                        if isinstance(cls, str) and cls.startswith('wp-'):
                            self._log("info", "  Detected platform: WordPress (via wp- classes)")
                            return 'wordpress'

        if soup.find('article', attrs={'data-post-id': True}):  # Medium
            self._log("info", "  Detected platform: Medium (via data-post-id)")
            return 'medium'

        # Default to generic
        self._log("info", "  Platform: Generic (no specific platform detected)")
        return 'generic'

    def fetch_content(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Fetch URL content with SMART platform detection - skips Playwright for static sites!

        Performance optimization: Quickly detects platform type first, then:
        - Static sites (WordPress, Blogger, etc.) → requests library (5-10x faster!)
        - JavaScript-heavy sites (Wix, Webflow, DealerOn) → Playwright
        """
        # STEP 1: Quick platform detection (5-10 seconds) to determine method
        self._log("info", "  Detecting platform type...")
        platform = self._quick_platform_check(url)
        needs_js = self._needs_javascript_rendering(platform)

        if platform:
            if needs_js:
                self._log("info", f"  Platform: {platform} (JavaScript-heavy → using Playwright)")
            else:
                self._log("info", f"  Platform: {platform} (static HTML → using requests for speed)")

        # STEP 2: If static site, skip Playwright entirely and use requests
        if not needs_js:
            self._log("info", "  Fetching with requests library (fast path)...")
            for attempt in range(max_retries):
                try:
                    response = requests.get(
                        url,
                        headers={'User-Agent': random.choice(self.user_agents)},
                        timeout=30
                    )
                    response.raise_for_status()
                    return response.text
                except Exception as e:
                    self._log("warning", f"  Requests attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        delay = 2 ** attempt
                        self._log("info", f"  Retrying in {delay} seconds...")
                        time.sleep(delay)

            # If requests failed, fall through to try Playwright anyway
            self._log("warning", "  Requests failed, falling back to Playwright...")

        # STEP 3: Try Playwright for JavaScript-heavy sites (or if requests failed)
        if HAS_PLAYWRIGHT and sync_playwright is not None:
            for attempt in range(max_retries):
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        try:
                            context = browser.new_context(
                                user_agent=random.choice(self.user_agents),
                                viewport={'width': 1920, 'height': 1080}
                            )
                            page = context.new_page()

                            # Navigate and wait for page load (optimized timeout)
                            self._log("info", f"  Fetching with Playwright (attempt {attempt + 1}/{max_retries})...")
                            # wait_until='load' ensures page is fully loaded
                            page.goto(url, wait_until='load', timeout=45000)  # 45s (was 120s) - faster!

                            # Wait for blog content to render (Angular SPA)
                            try:
                                page.wait_for_selector('div.blog__article__content__text, article, .blog-post', timeout=15000)  # 15s (was 30s)
                            except Exception as e:
                                # Continue anyway, content might use different selector
                                self._log("debug", f"  Selector wait failed (expected): {e}")
                            page.wait_for_timeout(500)  # Brief wait for dynamic content

                            # OPTIMIZED SCROLLING: Faster but still loads all images
                            self._log("info", "  Scrolling to load all images (15-20 seconds)...")

                            # Scroll to 25% of page
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.25)")
                            page.wait_for_load_state('networkidle', timeout=8000)  # 8s (was 20s)

                            # Scroll to 50% of page
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
                            page.wait_for_load_state('networkidle', timeout=8000)

                            # Scroll to 75% of page
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.75)")
                            page.wait_for_load_state('networkidle', timeout=8000)

                            # Scroll to bottom
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            page.wait_for_load_state('networkidle', timeout=8000)
                            page.wait_for_timeout(500)  # Brief wait for final images

                            # Scroll back to top
                            page.evaluate("window.scrollTo(0, 0)")
                            page.wait_for_timeout(500)

                            # Get page content
                            html_content = cast(str, page.content())
                            return html_content
                        finally:
                            # Always cleanup browser resources, even on error
                            browser.close()

                except Exception as e:
                    self._log("warning", f"  Playwright attempt {attempt + 1} failed: {e}")

                    if attempt < max_retries - 1:
                        # Exponential backoff: 2^attempt seconds (1s, 2s, 4s)
                        delay = 2 ** attempt
                        self._log("info", f"  Retrying in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        self._log("info", "  All Playwright attempts failed, falling back to requests...")

        # Fallback to requests (for Streamlit Cloud compatibility)
        for attempt in range(max_retries):
            try:
                headers = {
                    'User-Agent': random.choice(self.user_agents),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                }

                self._log("info", f"  Fetching with requests (attempt {attempt + 1}/{max_retries})...")
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response.text

            except Exception as e:
                self._log("warning", f"  Requests attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    # Exponential backoff
                    delay = 2 ** attempt
                    self._log("info", f"  Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    self._log("error", f"  All attempts failed for {url}")

        return None

    async def fetch_content_async(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Async version: Fetch URL content with optional Playwright skip (fast mode)"""
        if not HAS_ASYNC_PLAYWRIGHT or async_playwright is None:
            # Fall back to synchronous version if async not available
            return self.fetch_content(url, max_retries)

        # FAST MODE: If skip_playwright is True, try requests first (10x faster!)
        # But fall back to Playwright if site blocks requests (403, etc.)
        if self.skip_playwright:
            self._log("info", "  Fast mode: Trying requests library first...")
            for attempt in range(max_retries):
                try:
                    # Use sync requests in async context (it's fast enough)
                    response = requests.get(
                        url,
                        headers={'User-Agent': random.choice(self.user_agents)},
                        timeout=30
                    )
                    response.raise_for_status()
                    self._log("info", "  Fast mode succeeded with requests!")
                    return response.text
                except Exception as e:
                    self._log("warning", f"  Requests attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        delay = 2 ** attempt
                        self._log("info", f"  Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)

            # Requests failed - fall back to Playwright (site probably has bot protection)
            self._log("warning", "  Fast mode blocked by site - falling back to Playwright...")
            # Continue to Playwright below instead of returning None

        # NORMAL MODE: Smart platform detection (if not in fast mode)
        # STEP 1: Quick platform detection to determine method
        self._log("info", "  Detecting platform type...")
        platform = self._quick_platform_check(url)  # Still uses sync requests (fast)
        needs_js = self._needs_javascript_rendering(platform)

        if platform:
            if needs_js:
                self._log("info", f"  Platform: {platform} (JavaScript-heavy → using Playwright)")
            else:
                self._log("info", f"  Platform: {platform} (static HTML → using requests for speed)")

        # STEP 2: If static site, skip Playwright and use requests
        if not needs_js:
            self._log("info", "  Fetching with requests library (fast path)...")
            for attempt in range(max_retries):
                try:
                    # Use sync requests in async context (it's fast enough)
                    response = requests.get(
                        url,
                        headers={'User-Agent': random.choice(self.user_agents)},
                        timeout=30
                    )
                    response.raise_for_status()
                    return response.text
                except Exception as e:
                    self._log("warning", f"  Requests attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        delay = 2 ** attempt
                        self._log("info", f"  Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)

            # If requests failed, fall through to Playwright
            self._log("warning", "  Requests failed, falling back to Playwright...")

        # STEP 3: Try async Playwright for JavaScript-heavy sites (or if requests failed)
        for attempt in range(max_retries):
            page = None
            try:
                # Create fresh browser for each request (more stable)
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(
                        user_agent=random.choice(self.user_agents),
                        viewport={'width': 1920, 'height': 1080}
                    )
                    try:
                        page = await context.new_page()

                        # Navigate and wait for page load (optimized timeout)
                        self._log("info", f"  Fetching with Playwright async (attempt {attempt + 1}/{max_retries})...")
                        # wait_until='load' ensures page is fully loaded
                        await page.goto(url, wait_until='load', timeout=45000)  # 45s (was 120s) - faster!

                        # Wait for blog content to render (Angular SPA)
                        try:
                            await page.wait_for_selector('div.blog__article__content__text, article, .blog-post', timeout=15000)  # 15s (was 30s)
                        except Exception as e:
                            # Continue anyway, content might use different selector
                            self._log("debug", f"  Selector wait failed (expected): {e}")
                        await page.wait_for_timeout(500)  # Brief wait for dynamic content

                        # OPTIMIZED SCROLLING: Faster but still loads all images
                        self._log("info", "  Scrolling to load all images (15-20 seconds)...")

                        # Scroll to 25% of page
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.25)")
                        await page.wait_for_load_state('networkidle', timeout=8000)  # 8s (was 20s)

                        # Scroll to 50% of page
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
                        await page.wait_for_load_state('networkidle', timeout=8000)

                        # Scroll to 75% of page
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.75)")
                        await page.wait_for_load_state('networkidle', timeout=8000)

                        # Scroll to bottom
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await page.wait_for_load_state('networkidle', timeout=8000)
                        await page.wait_for_timeout(500)  # Brief wait for final images

                        # Scroll back to top
                        await page.evaluate("window.scrollTo(0, 0)")
                        await page.wait_for_timeout(500)

                        # Get page content
                        html_content = cast(str, await page.content())
                        return html_content
                    finally:
                        # Clean up browser resources
                        if page:
                            await page.close()
                        await browser.close()

            except Exception as e:
                self._log("warning", f"  Async Playwright attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt seconds (1s, 2s, 4s)
                    delay = 2 ** attempt
                    self._log("info", f"  Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    self._log("error", f"  All async attempts failed for {url}")

        return None

    def extract_categories(self, soup: BeautifulSoup) -> List[str]:
        """Extract categories - only from blog-specific areas, not navigation"""
        # DealerInspire - div.meta-below-content with rel="category tag" links (Speck Buick GMC)
        meta_below = soup.select_one('div.meta-below-content')
        if meta_below:
            category_links = meta_below.find_all('a', rel='category tag')
            if category_links:
                categories = set()
                for elem in category_links:
                    if isinstance(elem, Tag):
                        cat = elem.get_text().strip()
                        if cat:
                            categories.add(cat)
                return list(categories)

        # Priority Honda/DealerOn: Look for categories ONLY within blog entry area
        blog_entry = soup.select_one('div.blog__entry')
        if blog_entry:
            # Only look for categories within the blog entry container
            category_elements = blog_entry.select('div.blog__entry__content__categories a')
            if category_elements:
                categories = set()
                for elem in category_elements:
                    if isinstance(elem, Tag):
                        cat = elem.get_text().strip()
                        if cat:
                            categories.add(cat)
                return list(categories)

        # Great Lakes Subaru / DealerOn v2 - div.categories structure
        categories_div = soup.select_one('div.categories')
        if categories_div:
            category_links = categories_div.find_all('a')
            if category_links:
                categories = set()
                for elem in category_links:
                    if isinstance(elem, Tag):
                        cat = elem.get_text().strip()
                        if cat:
                            categories.add(cat)
                return list(categories)

        # WordPress - category links with rel="category tag" (Earnhardt Hyundai, etc.)
        category_tag_links = soup.find_all('a', rel='category tag')
        if category_tag_links:
            categories = set()
            for elem in category_tag_links:
                if isinstance(elem, Tag):
                    cat = elem.get_text().strip()
                    if cat:
                        categories.add(cat)
            if categories:
                return list(categories)

        # Wix-specific selectors (very targeted)
        wix_selectors = [
            'ul[aria-label="Post categories"] a',
            'section ul.pRGtWE li a',
        ]

        categories = set()
        for selector in wix_selectors:
            elements = soup.select(selector)
            for element in elements:
                if isinstance(element, Tag):
                    cat = element.get_text().strip()
                    if cat:
                        categories.add(cat)

        # Meta tag fallback - ONLY use article-specific meta tags
        # IMPORTANT: We explicitly DO NOT use meta[name="keywords"] because it contains
        # site-wide SEO keywords (e.g., "Honda Dealer") that are NOT blog categories
        meta = soup.select_one('meta[name="article:section"]')
        if meta and isinstance(meta, Tag):
            content = meta.get('content')
            if content:
                cat = str(content).strip()
                if cat:
                    categories.add(cat)

        # Filter out navigation/dealer terms
        exclude_terms = [
            'uncategorized', 'blog', 'all posts', 'home', 'about', 'contact',
            'dealer', 'dealership', 'inventory', 'service', 'parts', 'hours',
            'location', 'directions', 'finance', 'specials', 'reviews',
            'privacy', 'sitemap', 'careers', 'testimonials', 'team',
            'new inventory', 'used inventory', 'schedule service', 'financing',
            'honda', 'roanoke', 'priority'  # Brand/location terms
        ]

        filtered_categories = []
        for cat in categories:
            cat_lower = cat.lower()
            # Exclude if any exclude term is in the category
            is_excluded = any(term in cat_lower for term in exclude_terms)
            # Also exclude if it looks like a URL or link text
            if not is_excluded and len(cat.split()) <= 3 and 'http' not in cat_lower:
                filtered_categories.append(cat)

        return filtered_categories

    def extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """Extract tags from blog-specific areas only"""
        selectors = [
            # Priority Honda/DealerOn-specific selectors
            'ul.blog__entry__content__tags li a',
            'ul.blog__entry__content__tags li a strong',
            # Wix-specific selectors based on your HTML
            'nav[aria-label="Tags"] ul li a',
            '.zmug2R li a',
            '._u2fqx',
            # Generic fallbacks
            '.tag a',
            '.tags a',
            # NOTE: We do NOT use meta[name="keywords"] as it contains site-wide SEO terms
            # (e.g., "Honda Dealer") that are NOT blog post tags
        ]

        tags = set()
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                if isinstance(element, Tag):
                    tag = element.get_text().strip()
                    if tag:
                        tags.add(tag)

        # Filter out obvious non-tags (dealer/navigation terms)
        exclude_terms = ['dealer', 'dealership', 'inventory', 'home', 'about', 'contact']
        filtered_tags = []
        for tag in tags:
            tag_lower = tag.lower()
            is_excluded = any(term in tag_lower for term in exclude_terms)
            if not is_excluded and len(tag.split()) <= 5:  # Tags are usually short
                filtered_tags.append(tag)

        return filtered_tags

    def extract_title(self, soup: BeautifulSoup) -> str:
        """Extract post title"""
        selectors = [
            'h1[data-hook="post-title"]',
            'h1.slider-heading',  # Webflow
            'h1.H3vOVf',
            'h1',
            'title',
            'meta[property="og:title"]',
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element and isinstance(element, Tag):
                if element.name == 'meta':
                    content = element.get('content')
                    if content:
                        title = str(content).strip()
                    else:
                        title = ''
                else:
                    title = element.get_text().strip()
                if title:
                    return title
        return "Untitled Post"

    def extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main post content with HTML structure preserved"""
        selectors = [
            # Priority Honda/DealerOn - actual blog content area
            'div.blog__article__content__text',  # THIS is the actual content!
            'div.blog__entry__content > div',  # Fallback
            'div.blog__entry__content',
            # Borgman Ford / DealerOn variant
            # Ruges Ford and similar sites
            'div.editor',
            'div.entry-content.text-content-container',
            # Webflow-specific (rich text editor content)
            'div.rich-text-block',
            'div.post-body-container',
            # Wix-specific
            'section[data-hook="post-description"]',
            # DealerInspire - actual blog content only (excludes author/social/category metadata)
            'div.entry',
            # WordPress dealer blogs (Earnhardt, etc.) - actual blog content
            'div.blogContent',
            # WordPress and generic
            'article .entry-content',
            'article',
            '.post-content',
            '.content',
            'main',
        ]

        for selector in selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Clean up unwanted elements (breadcrumbs, navigation, title duplication)
                for unwanted in content_elem.find_all(['script', 'style', 'noscript']):
                    unwanted.decompose()

                # Remove breadcrumbs (common in custom HTML sites)
                for breadcrumb in content_elem.find_all(class_='breadcrumbs'):
                    breadcrumb.decompose()
                for breadcrumb in content_elem.find_all('nav', attrs={'aria-label': 'Breadcrumb'}):
                    breadcrumb.decompose()

                # Remove duplicate title (if content_title div exists)
                for title_div in content_elem.find_all(class_='content_title'):
                    title_div.decompose()

                # Remove post navigation (prev/next links) - WordPress/dealer blogs
                for nav in content_elem.find_all(class_='post-navigation'):
                    nav.decompose()

                # Remove duplicate title and date divs - dealer blog pattern
                for title_div in content_elem.find_all(class_='titleDiv'):
                    title_div.decompose()
                for date_div in content_elem.find_all(class_='dateDiv'):
                    date_div.decompose()

                # Remove social sharing icons
                for sharing in content_elem.find_all(class_='sharingIcons'):
                    sharing.decompose()

                # Remove post metadata (categories, "Posted in" footer)
                for meta in content_elem.find_all(class_='postmetadata'):
                    meta.decompose()

                # Remove any paragraphs containing "Posted in" (category footer)
                for p in content_elem.find_all('p'):
                    p_text = p.get_text().strip()
                    if p_text.startswith('Posted in') or 'Comments Off' in p_text:
                        p.decompose()

                # Remove "Connect with us" sections - common footer element
                for elem in content_elem.find_all(['h2', 'h3', 'h4']):
                    if 'Connect with us' in elem.get_text():
                        elem.decompose()

                # Get HTML content instead of just text
                html_content = content_elem.decode_contents()

                # Check if there's substantial text content
                text_content = content_elem.get_text().strip()
                if text_content and len(text_content) > 100:
                    # Clean and convert to Gutenberg blocks
                    cleaned_html = self.clean_html(html_content)
                    gutenberg_content = self.html_to_gutenberg(cleaned_html)
                    return gutenberg_content

        return ""

    def clean_html(self, html_content: str) -> str:
        """Clean HTML by removing unwanted attributes and elements while preserving structure"""
        # STEP 1: Fix character encoding issues
        html_content = html_content.replace('\u2019', "'")  # Right single quote
        html_content = html_content.replace('\u2018', "'")  # Left single quote
        html_content = html_content.replace('\u201c', '"')  # Left double quote
        html_content = html_content.replace('\u201d', '"')  # Right double quote
        html_content = html_content.replace('\u2013', '-')  # En dash
        html_content = html_content.replace('\u2014', '-')  # Em dash
        html_content = html_content.replace('\u00a0', ' ')  # Non-breaking space

        # STEP 1.5: Convert Wix-style paragraph breaks to double <br> tags
        # Wix uses consecutive empty spans with whitespace/newlines as paragraph separators
        # Pattern: <span>\n</span><span>\n</span> or <span> </span><span> </span>
        # Convert to: <br/><br/> so next step converts to paragraph breaks
        html_content = re.sub(
            r'<span[^>]*>\s*</span>\s*<span[^>]*>\s*</span>',
            '<br/><br/>',
            html_content,
            flags=re.IGNORECASE
        )

        # STEP 2: Convert double <br> tags to paragraph breaks
        # This handles the pattern: text<br/><br/>more text
        # Replace with: </p><p>
        html_content = re.sub(
            r'<br\s*/?>\s*<br\s*/?>',
            '</p><p>',
            html_content,
            flags=re.IGNORECASE
        )

        # Parse the HTML content
        # NOTE: We do NOT wrap content in <p> tags here because that destroys
        # the structure of content that already has proper block elements (h1-h6, ul, ol, etc.)
        # The html_to_gutenberg function handles unwrapped content properly
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove all HTML comments
        from bs4 import Comment
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Mark button links with a special attribute before processing
        for link in soup.find_all('a', class_=True):
            if isinstance(link, Tag):
                classes = link.get('class')
                if classes and isinstance(classes, list):
                    # Check if it's a button link (has 'btn' or 'button' in classes)
                    if any('btn' in cls.lower() or 'button' in cls.lower() for cls in classes):
                        link['data-is-button'] = 'true'

                        # Standardize button class to "btn btn-cta"
                        link['class'] = 'btn btn-cta'

                        # Add required data-dotagging attributes if not present
                        href_attr = link.get('href')
                        href = str(href_attr) if href_attr else ''
                        if 'data-dotagging-link-url' not in link.attrs:
                            link['data-dotagging-link-url'] = href
                        if 'data-dotagging-event' not in link.attrs:
                            link['data-dotagging-event'] = 'cta_interaction'
                        if 'data-dotagging-product-name' not in link.attrs:
                            link['data-dotagging-product-name'] = 'Website|Custom Content'
                        if 'data-dotagging-event-action-result' not in link.attrs:
                            link['data-dotagging-event-action-result'] = 'open'
                        if 'data-dotagging-element-type' not in link.attrs:
                            link['data-dotagging-element-type'] = 'body'
                        if 'data-dotagging-element-order' not in link.attrs:
                            link['data-dotagging-element-order'] = '0'
                        if 'data-dotagging-element-subtype' not in link.attrs:
                            link['data-dotagging-element-subtype'] = 'cta_button'

        # Replace <br> tags with spaces to prevent text from running together
        # This is critical - br tags separate text but shouldn't create new paragraphs
        for br in soup.find_all('br'):
            if isinstance(br, Tag):
                br.replace_with(' ')

        # Fix lazy-loaded images (Wix uses data-pin-media for full-quality images)
        if self.include_images:
            for img in soup.find_all('img'):
                if isinstance(img, Tag):
                    # Wix lazy loading: data-pin-media contains full quality image
                    # while src contains low-quality placeholder
                    data_pin_media = img.get('data-pin-media')
                    if data_pin_media:
                        img['src'] = data_pin_media
                        # Remove lazy-loading attributes
                        for attr in ['data-pin-media', 'data-load-done', 'data-ssr-src-done', 'data-pin-url']:
                            if attr in img.attrs:
                                del img[attr]

        # Remove img tags if include_images is False
        if not self.include_images:
            # Remove all img tags completely (we don't want images)
            # Add space before removing to prevent text concatenation
            for img in soup.find_all('img'):
                if isinstance(img, Tag):
                    img.insert_before(NavigableString(' '))
                    img.insert_after(NavigableString(' '))
                    img.decompose()

        # Define allowed tags (semantic HTML only)
        # Note: b/i tags are normalized to strong/em before this check
        allowed_tags = {
            'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'strong', 'em', 'u', 'ul', 'ol', 'li',
            'blockquote', 'pre', 'code', 'a'
        }

        # Add img to allowed tags if we're including images
        if self.include_images:
            allowed_tags.add('img')

        # Define which attributes to keep for specific tags
        allowed_attrs = {
            'a': ['href', 'class', 'data-is-button'],  # Allow class and button marker for links
            'img': ['src', 'alt', 'title', 'width', 'height', 'class']  # Image attributes
        }

        # Remove unwanted elements but keep their content
        # Add spaces when unwrapping to prevent text concatenation
        unwrap_tags = ['div', 'span', 'section', 'article', 'header', 'footer', 'nav']
        for tag_name in unwrap_tags:
            for tag in soup.find_all(tag_name):
                if isinstance(tag, Tag):
                    # Add space after the tag before unwrapping to prevent text merging
                    # Only if the tag has content and isn't just whitespace
                    if tag.get_text(strip=True):
                        tag.insert_after(NavigableString(' '))
                    tag.unwrap()

        # Normalize tags - convert presentational HTML to semantic HTML
        # WordPress Gutenberg prefers semantic tags
        for b_tag in soup.find_all('b'):
            if isinstance(b_tag, Tag):
                b_tag.name = 'strong'

        for i_tag in soup.find_all('i'):
            if isinstance(i_tag, Tag):
                i_tag.name = 'em'

        # Convert H1 to H2 - WordPress post title is already H1, so content H1s create duplicate H1s
        # This fixes SEO and accessibility issues
        for h1_tag in soup.find_all('h1'):
            if isinstance(h1_tag, Tag):
                h1_tag.name = 'h2'

        # Clean attributes from all elements
        for element in soup.find_all():
            if isinstance(element, Tag):
                if element.name in allowed_tags:
                    # For button links, preserve class and data-* attributes
                    if element.name == 'a' and element.get('data-is-button') == 'true':
                        # Keep all data-* attributes and class for buttons
                        allowed = ['href', 'class'] + [attr for attr in element.attrs.keys() if attr.startswith('data-')]
                    else:
                        # Keep only allowed attributes for this tag
                        allowed = allowed_attrs.get(element.name, [])

                    attrs_to_remove = [attr for attr in element.attrs.keys() if attr not in allowed]
                    for attr in attrs_to_remove:
                        del element.attrs[attr]
                else:
                    # Remove disallowed tags but keep their content
                    # Add space to prevent text concatenation
                    if element.get_text(strip=True):
                        element.insert_after(NavigableString(' '))
                    element.unwrap()

        # Extract block-level elements (like headings) from paragraphs
        # Headings should not be nested inside paragraphs
        for p in soup.find_all('p'):
            if isinstance(p, Tag):
                # Find any headings or other block elements inside this paragraph
                block_elements = p.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                for block_elem in block_elements:
                    if isinstance(block_elem, Tag):
                        # Extract the block element and insert it before the paragraph
                        block_elem.extract()
                        p.insert_before(block_elem)

        # Extract images from paragraphs and headings to make them block-level (if including images)
        # Images work better as separate Gutenberg blocks, not inline
        if self.include_images:
            # Extract from paragraphs
            for p in soup.find_all('p'):
                if isinstance(p, Tag):
                    # Find any images inside this paragraph
                    images = p.find_all('img')
                    for img in images:
                        if isinstance(img, Tag):
                            # Extract the image and insert it before the paragraph
                            img.extract()
                            p.insert_before(img)

            # Extract from headings (h1-h6)
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                if isinstance(heading, Tag):
                    # Find any images inside this heading
                    images = heading.find_all('img')
                    for img in images:
                        if isinstance(img, Tag):
                            # Extract the image and insert it before the heading
                            img.extract()
                            heading.insert_before(img)

        # Extract block-level elements from lists
        # Lists (ul/ol) can ONLY contain <li> as direct children
        for list_elem in soup.find_all(['ul', 'ol']):
            if isinstance(list_elem, Tag):
                # Find any block elements that are direct children (not nested in <li>)
                invalid_children = []
                for child in list_elem.children:
                    if isinstance(child, Tag) and child.name not in ['li']:
                        invalid_children.append(child)

                # Extract invalid block elements and insert them after the list
                for invalid_elem in invalid_children:
                    if isinstance(invalid_elem, Tag):
                        invalid_elem.extract()
                        list_elem.insert_after(invalid_elem)

        # Normalize whitespace in paragraphs and remove empty ones
        for p in soup.find_all('p'):
            if isinstance(p, Tag):
                # Normalize whitespace in text nodes only, leave tags intact
                for item in p.descendants:
                    if isinstance(item, NavigableString) and not isinstance(item, Comment):
                        # Replace multiple whitespace chars with single space
                        normalized_text = re.sub(r'\s+', ' ', str(item))
                        item.replace_with(normalized_text)

                # Strip leading/trailing whitespace from the paragraph's text content
                if p.contents:
                    # Strip whitespace from first text node
                    first = p.contents[0]
                    if isinstance(first, NavigableString):
                        first.replace_with(str(first).lstrip())
                    # Strip whitespace from last text node
                    last = p.contents[-1]
                    if isinstance(last, NavigableString):
                        last.replace_with(str(last).rstrip())

                # Check if paragraph is empty after normalization
                text_content = p.get_text().strip()
                if not text_content or len(text_content) < 2:
                    p.decompose()

        # Final cleanup: remove leading/trailing whitespace after paragraph tags
        html_output = str(soup).strip()
        # Remove whitespace right after <p> tags
        html_output = re.sub(r'<p>\s+', '<p>', html_output)
        # Remove whitespace right before </p> tags
        html_output = re.sub(r'\s+</p>', '</p>', html_output)

        return html_output

    def html_to_gutenberg(self, html_content: str) -> str:
        """Convert clean HTML to Gutenberg blocks format (with block comments)"""
        if not html_content.strip():
            return ""

        # Parse the cleaned HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract button links from paragraphs and make them separate elements
        for p in soup.find_all('p'):
            if isinstance(p, Tag):
                button_links = p.find_all('a', attrs={'data-is-button': 'true'})
                if button_links:
                    # Extract buttons from paragraph and insert them after the paragraph
                    for button in button_links:
                        if isinstance(button, Tag):
                            # Remove button from paragraph
                            button.extract()
                            # Insert button as sibling after the paragraph
                            p.insert_after(button)

        gutenberg_blocks = []

        # Group consecutive inline/text elements into paragraphs
        current_paragraph_parts: List[PageElement] = []

        # Process each top-level element
        for element in soup.children:
            if isinstance(element, Tag) and element.name:
                # Check if it's a block-level element
                if element.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'blockquote', 'pre', 'img']:
                    # Flush any accumulated inline content first
                    if current_paragraph_parts:
                        para_content = ''.join(str(p) for p in current_paragraph_parts)
                        gutenberg_blocks.append(f'<!-- wp:paragraph -->\n<p>{para_content}</p>\n<!-- /wp:paragraph -->')
                        current_paragraph_parts = []

                    # Process the block element
                    block_html = self.element_to_gutenberg_block(element)
                    if block_html:
                        gutenberg_blocks.append(block_html)
                elif element.get('data-is-button') == 'true':
                    # Button links are separate blocks
                    if current_paragraph_parts:
                        para_content = ''.join(str(p) for p in current_paragraph_parts)
                        gutenberg_blocks.append(f'<!-- wp:paragraph -->\n<p>{para_content}</p>\n<!-- /wp:paragraph -->')
                        current_paragraph_parts = []

                    block_html = self.element_to_gutenberg_block(element)
                    if block_html:
                        gutenberg_blocks.append(block_html)
                else:
                    # Inline element - accumulate it
                    current_paragraph_parts.append(element)
            elif not isinstance(element, Tag):
                # Text node - accumulate if not empty
                text = str(element).strip()
                if text:
                    current_paragraph_parts.append(element)

        # Flush any remaining inline content
        if current_paragraph_parts:
            para_content = ''.join(str(p) for p in current_paragraph_parts)
            gutenberg_blocks.append(f'<!-- wp:paragraph -->\n<p>{para_content}</p>\n<!-- /wp:paragraph -->')

        return '\n\n'.join(gutenberg_blocks)

    def element_to_gutenberg_block(self, element) -> str:
        """Convert a single HTML element to Gutenberg block with proper comments"""
        tag_name = element.name.lower()

        if tag_name == 'a' and isinstance(element, Tag) and element.get('data-is-button') == 'true':
            # Handle button links as HTML blocks
            element_copy = BeautifulSoup(str(element), 'html.parser').find('a')
            if element_copy and isinstance(element_copy, Tag):
                if 'data-is-button' in element_copy.attrs:
                    del element_copy['data-is-button']
                button_html = str(element_copy)
            else:
                button_html = str(element)
            return f'<!-- wp:html -->\n{button_html}\n<!-- /wp:html -->'

        elif tag_name == 'p':
            content = str(element)
            return f'<!-- wp:paragraph -->\n{content}\n<!-- /wp:paragraph -->'

        elif tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(tag_name[1])
            content = str(element)
            return f'<!-- wp:heading {{"level":{level}}} -->\n{content}\n<!-- /wp:heading -->'

        elif tag_name in ['ul', 'ol']:
            content = str(element)
            return f'<!-- wp:list -->\n{content}\n<!-- /wp:list -->'

        elif tag_name == 'blockquote':
            inner_content = element.decode_contents()
            return f'<!-- wp:quote -->\n<blockquote class="wp-block-quote">{inner_content}</blockquote>\n<!-- /wp:quote -->'

        elif tag_name == 'pre':
            if element.find('code'):
                content = element.get_text()
                return f'<!-- wp:code -->\n<pre class="wp-block-code"><code>{content}</code></pre>\n<!-- /wp:code -->'
            else:
                content = str(element)
                return f'<!-- wp:preformatted -->\n{content}\n<!-- /wp:preformatted -->'

        elif tag_name == 'img':
            # Create WordPress-native image block format (matches what WordPress generates)
            if isinstance(element, Tag):
                from urllib.parse import unquote

                src = element.get('src', '')
                alt = element.get('alt', '')

                # URL-decode alt text (e.g., "2025%20Nissan" -> "2025 Nissan")
                # This prevents Gutenberg validation errors
                if alt:
                    alt = unquote(str(alt))

                # Build minimal img tag - only src and alt (matches WordPress native format)
                # No width/height attributes or inline styles - WordPress handles sizing
                if alt:
                    img_html = f'<img src="{src}" alt="{alt}"/>'
                else:
                    img_html = f'<img src="{src}"/>'

                # Simple Gutenberg image block without JSON attributes
                return f'<!-- wp:image -->\n<figure class="wp-block-image">{img_html}</figure>\n<!-- /wp:image -->'
            return ""

        else:
            # For other elements, wrap in paragraph or return as-is
            content = str(element)
            if tag_name in ['strong', 'em', 'u', 'a', 'code']:
                # Inline elements - wrap in paragraph
                return f'<!-- wp:paragraph -->\n<p>{content}</p>\n<!-- /wp:paragraph -->'
            elif tag_name == 'br':
                # Skip br tags completely
                return ""
            else:
                # Block elements - wrap in paragraph
                return f'<!-- wp:paragraph -->\n<p>{content}</p>\n<!-- /wp:paragraph -->'

    def extract_author(self, soup: BeautifulSoup) -> str:
        """Extract author information"""
        # Priority Honda/DealerOn-specific: look for author link in span.blog__entry__content__author
        author_container = soup.select_one('span.blog__entry__content__author')
        if author_container and isinstance(author_container, Tag):
            # Find the author link (contains "See the ... blog entries")
            author_link = author_container.select_one('a[href*="?author="]')
            if author_link and isinstance(author_link, Tag):
                author_text = author_link.get_text().strip()
                if author_text:
                    return author_text

        # Standard selectors
        selectors = [
            '[data-hook="user-name"]',
            'meta[name="author"]',
            'div.text-blog',  # Webflow (sidebar author area)
            '.author',
            '.byline',
            '.post-author',
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element and isinstance(element, Tag):
                if element.name == 'meta':
                    content = element.get('content')
                    if content:
                        author = str(content).strip()
                    else:
                        author = ''
                else:
                    author = element.get_text().strip()
                if author:
                    return author
        return "Unknown Author"

    def extract_date(self, soup: BeautifulSoup, url: str = '') -> str:
        """Extract publication date"""
        # DealerInspire - div.meta-below-title > span.updated (Speck Chevrolet Prosser, Speck Buick GMC)
        meta_below_title = soup.select_one('div.meta-below-title span.updated')
        if meta_below_title and isinstance(meta_below_title, Tag):
            date_text = meta_below_title.get_text().strip()
            if date_text:
                return date_text

        # Priority Honda/DealerOn-specific: look for date in span.blog__entry__content__author
        author_container = soup.select_one('span.blog__entry__content__author')
        if author_container and isinstance(author_container, Tag):
            # Find all spans - the date is usually in the last one after the " / " separator
            date_spans = author_container.find_all('span', class_='blog__entry__content__author')
            for span in date_spans:
                if isinstance(span, Tag):
                    text = span.get_text().strip()
                    # Check if it looks like a date (contains month name or numbers)
                    if re.search(r'\d{1,2}', text) and not text.startswith('by'):
                        # Likely a date
                        if text and text != '/' and 'blog entries' not in text.lower():
                            return text

        # Webflow-specific: Handle multiple div.text-date-blog-post elements (first is often empty)
        webflow_dates = soup.select('div.text-date-blog-post')
        for date_elem in webflow_dates:
            if isinstance(date_elem, Tag):
                date_text = date_elem.get_text().strip()
                # Skip empty elements (w-dyn-bind-empty)
                if date_text and len(date_text) > 3:
                    return date_text

        # Standard selectors
        selectors = [
            '[data-hook="time-ago"]',
            'meta[property="article:published_time"]',
            '.date',
            '.published',
            'time[datetime]',
            'time',
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element and isinstance(element, Tag):
                if element.name == 'meta':
                    content = element.get('content')
                    date_str = str(content) if content else ''
                else:
                    # For <time> elements, prioritize datetime attribute (already ISO-formatted)
                    datetime_attr = element.get('datetime')
                    if datetime_attr:
                        date_str = str(datetime_attr)
                    else:
                        title_attr = element.get('title')
                        if title_attr:
                            date_str = str(title_attr)
                        else:
                            date_str = element.get_text().strip()

                if date_str:
                    return date_str

        # Fallback: Try to extract date from URL pattern (e.g., /2019/july/17/ or /2019/07/17/)
        if url:
            # Match patterns like /YYYY/MM/DD/ or /YYYY/month/DD/
            url_date_pattern = r'/(\d{4})/([a-zA-Z]+|\d{1,2})/(\d{1,2})/'
            match = re.search(url_date_pattern, url)
            if match:
                year, month, day = match.groups()
                # Convert month name to number if needed
                month_map = {
                    'january': '01', 'february': '02', 'march': '03', 'april': '04',
                    'may': '05', 'june': '06', 'july': '07', 'august': '08',
                    'september': '09', 'october': '10', 'november': '11', 'december': '12'
                }
                if month.lower() in month_map:
                    month = month_map[month.lower()]
                # Format as YYYY-MM-DD
                try:
                    date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    # Validate it's a real date
                    datetime.strptime(date_str, '%Y-%m-%d')
                    return date_str
                except ValueError:
                    pass

        return datetime.now().strftime('%Y-%m-%d')

    def extract_images_from_content(self, content: str) -> List[Dict[str, str]]:
        """Extract image URLs and attributes from Gutenberg content

        Note: Image URLs are NOT resolved here because this runs before
        _convert_relative_urls_to_absolute() which handles URL resolution
        during XML generation.
        """
        if not content:
            return []

        soup = BeautifulSoup(content, 'html.parser')
        images = []

        for img in soup.find_all('img'):
            if isinstance(img, Tag):
                src = img.get('src', '')
                if src:
                    # Only include images with valid sources
                    images.append({
                        'src': str(src),
                        'alt': str(img.get('alt', '')),
                        'width': str(img.get('width', '')),
                        'height': str(img.get('height', ''))
                    })

        return images

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract hyperlinks from blog post content only (not navigation/menus/tags)"""
        # First find the content area using same selectors as extract_content()
        content_selectors = [
            # Priority Honda/DealerOn - actual blog content area
            'div.blog__article__content__text',  # THIS is the actual content!
            'div.blog__entry__content > div:first-child',
            # Webflow-specific (rich text editor content)
            'div.rich-text-block',
            'div.post-body-container',
            # Wix-specific
            'section[data-hook="post-description"]',
            # DealerInspire - actual blog content only (excludes author/social/category links)
            'div.entry',
            # WordPress and generic
            'article .entry-content',
            'article',
            '.post-content',
            '.content',
            'main',
        ]

        content_element = None
        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                break

        # If no content area found, return empty list
        if not content_element:
            return []

        # Extract links only from the content area
        links = []
        for link in content_element.find_all('a', href=True):
            if isinstance(link, Tag):
                # Check if link is inside excluded sections (tags, categories, author, nav)
                parent_classes: List[str] = []
                for parent in link.parents:
                    if isinstance(parent, Tag):
                        class_attr = parent.get('class')
                        if class_attr and isinstance(class_attr, list):
                            parent_classes.extend(class_attr)

                # Skip if link is inside metadata sections or breadcrumbs
                excluded_classes = ['blog__entry__content__tags', 'blog__entry__content__categories',
                                   'blog__entry__content__author', 'tags', 'categories', 'author-info',
                                   'breadcrumbs', 'breadcrumb']
                if any(exc in parent_classes for exc in excluded_classes):
                    continue

                href_attr = link.get('href', '')
                text = link.get_text().strip()

                if href_attr:  # Only process if href exists
                    href = str(href_attr)  # Convert to string

                    # Skip metadata links by URL pattern
                    if any(pattern in href.lower() for pattern in ['?tag=', '?author=', '?category=']):
                        continue

                    # Convert relative URLs to absolute
                    if href.startswith('http'):
                        full_url = href
                    else:
                        full_url = urljoin(base_url, href)

                    if text and full_url != base_url:  # Skip empty text and self-links
                        links.append({
                            'text': text,
                            'url': full_url
                        })

        return links

    def extract_blog_data(self, url: str) -> Dict[str, Any]:
        """Extract all blog data from a URL"""
        self._log("info", f"Processing: {url}")

        # Fetch content
        html_content = self.fetch_content(url)
        if not html_content:
            return {
                'status': 'failed',
                'url': url,
                'error': 'Could not fetch content'
            }

        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # Detect platform
        platform = self.detect_platform(soup)

        # Extract data
        # IMPORTANT: Extract categories/tags BEFORE extract_content,
        # because extract_content removes postmetadata elements
        title = self.extract_title(soup)
        author = self.extract_author(soup)
        date = self.extract_date(soup, url)
        categories = self.extract_categories(soup)
        tags = self.extract_tags(soup)

        # Extract content AFTER categories/tags (modifies soup)
        content = self.extract_content(soup)
        links = self.extract_links(soup, url)

        # Check for duplicate content
        if content:
            content_hash = self.get_content_hash(content)
            if content_hash in self.seen_hashes:
                if self.skip_duplicates:
                    self._log("warning", "  [WARNING] Duplicate content detected - skipping")
                    return {
                        'status': 'duplicate',
                        'url': url,
                        'title': title,
                        'error': 'Duplicate content'
                    }
                else:
                    self._log("warning", "  [WARNING] Duplicate content detected - including anyway")
            self.seen_hashes.add(content_hash)

        # Calculate text length for display (strip HTML tags for counting)
        text_for_counting = BeautifulSoup(content, 'html.parser').get_text() if content else ""

        # Extract image URLs from content for WordPress attachments
        images = self.extract_images_from_content(content) if self.include_images else []

        data = {
            'status': 'success',
            'url': url,
            'title': title,
            'content': content,
            'content_length': len(text_for_counting.strip()),
            'author': author,
            'date': date,
            'categories': categories,
            'tags': tags,
            'links': links,
            'platform': platform,
            'images': images,  # Add images for WordPress attachment items
        }

        self.extracted_data.append(data)
        return data

    async def extract_blog_data_async(self, url: str) -> Dict[str, Any]:
        """Async version: Extract all blog data from a URL"""
        self._log("info", f"Processing: {url}")

        # Fetch content asynchronously
        html_content = await self.fetch_content_async(url)
        if not html_content:
            return {
                'status': 'failed',
                'url': url,
                'error': 'Could not fetch content'
            }

        # Parse HTML (synchronous, but fast)
        soup = BeautifulSoup(html_content, 'html.parser')

        # Detect platform
        platform = self.detect_platform(soup)

        # Extract data (all synchronous, but fast)
        # IMPORTANT: Extract categories/tags BEFORE extract_content,
        # because extract_content removes postmetadata elements
        title = self.extract_title(soup)
        author = self.extract_author(soup)
        date = self.extract_date(soup, url)
        categories = self.extract_categories(soup)
        tags = self.extract_tags(soup)

        # Extract content AFTER categories/tags (modifies soup)
        content = self.extract_content(soup)
        links = self.extract_links(soup, url)

        # Check for duplicate content
        if content:
            content_hash = self.get_content_hash(content)
            if content_hash in self.seen_hashes:
                if self.skip_duplicates:
                    self._log("warning", "  [WARNING] Duplicate content detected - skipping")
                    return {
                        'status': 'duplicate',
                        'url': url,
                        'title': title,
                        'error': 'Duplicate content'
                    }
                else:
                    self._log("warning", "  [WARNING] Duplicate content detected - including anyway")
            self.seen_hashes.add(content_hash)

        # Calculate text length for display (strip HTML tags for counting)
        text_for_counting = BeautifulSoup(content, 'html.parser').get_text() if content else ""

        # Extract image URLs from content for WordPress attachments
        images = self.extract_images_from_content(content) if self.include_images else []

        # Download images asynchronously if enabled
        if self.download_images and images:
            image_urls = [img['src'] for img in images]
            await self._batch_download_images_async(image_urls)

        data = {
            'status': 'success',
            'url': url,
            'title': title,
            'content': content,
            'content_length': len(text_for_counting.strip()),
            'author': author,
            'date': date,
            'categories': categories,
            'tags': tags,
            'links': links,
            'platform': platform,
            'images': images,  # Add images for WordPress attachment items
        }

        self.extracted_data.append(data)
        return data

    async def _extract_with_semaphore(self, url: str, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
        """Extract blog data with semaphore to limit concurrent requests"""
        async with semaphore:
            return await self.extract_blog_data_async(url)

    async def _batch_download_images_async(self, image_urls: List[str]) -> None:
        """Batch download multiple images asynchronously for faster performance

        Args:
            image_urls: List of image URLs to download in parallel
        """
        if not self.download_images or not image_urls:
            return

        self._log("info", f"  Downloading {len(image_urls)} images in parallel...")

        # Create aiohttp session for reusing connections
        async with aiohttp.ClientSession() as session:
            # Download all images concurrently
            download_tasks = [
                self._download_image_async(url, session)
                for url in image_urls
                if url not in self.downloaded_images  # Skip already downloaded
            ]

            if download_tasks:
                await asyncio.gather(*download_tasks, return_exceptions=True)

    async def process_urls_concurrently(self, urls: List[str], max_concurrent: int = 5) -> List[Dict[str, Any]]:
        """Process multiple URLs concurrently with rate limiting

        Now includes async image downloads for significantly faster performance.
        """
        if not HAS_ASYNC_PLAYWRIGHT:
            self._log("warning", "Async Playwright not available, falling back to sequential processing")
            results = []
            for url in urls:
                result = self.extract_blog_data(url)
                results.append(result)
            return results

        self._log("info", f"Processing {len(urls)} URLs with max {max_concurrent} concurrent requests...")

        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)

        # Create tasks for all URLs
        tasks = [self._extract_with_semaphore(url, semaphore) for url in urls]

        # Run all tasks concurrently
        raw_results: List[Union[Dict[str, Any], BaseException]] = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        processed_results: List[Dict[str, Any]] = []
        for i, raw_result in enumerate(raw_results):
            if isinstance(raw_result, Exception):
                self._log("error", f"Exception processing {urls[i]}: {raw_result}")
                processed_results.append({
                    'status': 'failed',
                    'url': urls[i],
                    'error': str(raw_result)
                })
            else:
                # Type narrowing: raw_result is Dict[str, Any] here
                result = cast(Dict[str, Any], raw_result)
                processed_results.append(result)


        # Cleanup shared browser resources
        await self.close_browser()

        return processed_results

    def load_urls(self) -> List[str]:
        """Load URLs from the input file with validation

        Uses validators library to ensure URLs are properly formed before processing.
        Invalid URLs are logged and skipped to avoid wasted processing.
        """
        urls: List[str] = []
        invalid_urls = []

        if not os.path.exists(self.urls_file):
            self._log("error", f"Error: {self.urls_file} not found")
            return urls

        with open(self.urls_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                url = line.strip()
                if not url or url.startswith('#'):  # Skip empty lines and comments
                    continue

                # Validate URL format
                if validators.url(url):
                    urls.append(url)
                else:
                    invalid_urls.append((line_num, url))
                    self._log("warning", f"  Line {line_num}: Invalid URL skipped: {url[:60]}...")

        if invalid_urls:
            self._log("warning", f"Skipped {len(invalid_urls)} invalid URLs")

        self._log("info", f"Loaded {len(urls)} valid URLs to process")
        return urls

    def normalize_unicode(self, text: str) -> str:
        """Normalize unicode characters to ASCII-compatible equivalents"""
        import unicodedata

        if not text:
            return text

        # First, apply general unicode normalization
        text = unicodedata.normalize('NFKD', text)

        # Manual replacements for common problematic characters
        replacements = {
            # Smart quotes
            '\u2018': "'",  # Left single quotation mark
            '\u2019': "'",  # Right single quotation mark
            '\u201C': '"',  # Left double quotation mark
            '\u201D': '"',  # Right double quotation mark

            # Dashes
            '\u2014': '--',  # Em dash
            '\u2013': '-',   # En dash

            # Other common characters
            '\u2026': '...',  # Horizontal ellipsis
            '\u00A0': ' ',    # Non-breaking space
            '\u2022': '*',    # Bullet
            '\u00B7': '*',    # Middle dot

            # Accented characters (examples)
            '\u00E9': 'e',   # é
            '\u00E1': 'a',   # á
            '\u00ED': 'i',   # í
            '\u00F3': 'o',   # ó
            '\u00FA': 'u',   # ú
        }

        for unicode_char, ascii_char in replacements.items():
            text = text.replace(unicode_char, ascii_char)

        return text

    def parse_and_format_date(self, date_string: str) -> dict:
        """Parse extracted date and format for WordPress WXR

        Uses python-dateutil for intelligent date parsing - handles almost any format automatically.
        Falls back to current date if parsing fails.
        """
        if not date_string:
            # Default to current date
            date_obj = datetime.now()
        else:
            try:
                # Remove ordinal suffixes (1st, 2nd, 3rd, 4th, etc.) for better parsing
                date_string_cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_string)

                # Use python-dateutil for intelligent parsing - handles most formats automatically
                # dayfirst=False assumes US format (MM/DD/YYYY) for ambiguous dates
                date_obj = dateutil_parser.parse(date_string_cleaned.strip(), fuzzy=True, dayfirst=False)
                self._log("debug", f"  Parsed date: '{date_string}' → {date_obj.strftime('%Y-%m-%d')}")

            except (ValueError, TypeError, dateutil_parser.ParserError) as e:
                # If parsing fails, use current date
                self._log("warning", f"  Could not parse date '{date_string}': {e}, using current date")
                date_obj = datetime.now()

        # Format for WordPress WXR
        return {
            'rfc2822': date_obj.strftime('%a, %d %b %Y %H:%M:%S +0000'),  # Mon, 27 Nov 2023 00:00:00 +0000
            'mysql': date_obj.strftime('%Y-%m-%d %H:%M:%S'),              # 2023-11-27 00:00:00
            'mysql_gmt': date_obj.strftime('%Y-%m-%d %H:%M:%S')          # Same for GMT (simplified)
        }

    def _download_image(self, img_url: str) -> Optional[str]:
        """Download image to local directory and return local file path

        Args:
            img_url: Image URL to download

        Returns:
            Local file path if successful, None if download failed
        """
        if not self.download_images:
            return None

        # Check if already downloaded
        if img_url in self.downloaded_images:
            return self.downloaded_images[img_url]

        try:
            # First resolve the URL if it's a dynamic endpoint
            resolved_url = self._resolve_image_url(img_url)

            # Generate local filename from URL (with path traversal protection)
            parsed = urlparse(resolved_url)
            filename = Path(parsed.path).name  # Only filename, strips any path components

            # Security: Validate filename to prevent path traversal
            if not filename or '..' in filename or filename.startswith(('/', '\\')):
                filename = hashlib.blake2s(resolved_url.encode()).hexdigest() + '.jpg'

            # If no valid filename, generate from hash
            if not filename or '.' not in filename:
                filename = hashlib.blake2s(resolved_url.encode()).hexdigest() + '.jpg'

            # Ensure unique filename
            local_path = os.path.join(self.images_dir, filename)
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(local_path):
                filename = f"{base_name}_{counter}{ext}"
                local_path = os.path.join(self.images_dir, filename)
                counter += 1

            # Download the image
            self._log("info", f"  Downloading image: {filename}")
            response = requests.get(resolved_url, timeout=30, stream=True)
            response.raise_for_status()

            # Save to file and track size (with limit to prevent disk fill)
            bytes_downloaded = 0
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    bytes_downloaded += len(chunk)

                    # Check size limit to prevent disk fill attacks
                    if bytes_downloaded > MAX_IMAGE_SIZE:
                        raise ValueError(f"Image exceeds size limit: {bytes_downloaded / 1024 / 1024:.1f}MB > {MAX_IMAGE_SIZE / 1024 / 1024}MB")

                    f.write(chunk)

            # Validate image file type
            kind = filetype.guess(local_path)
            if kind is None:
                self._log("warning", f"  Could not determine file type for {filename}, keeping anyway")
            elif kind.mime.startswith('image/'):
                self._log("debug", f"  Validated image: {filename} ({kind.mime})")
            else:
                self._log("warning", f"  Downloaded file is not an image: {filename} ({kind.mime})")
                # Keep file anyway - might be SVG or other format

            # Cache the result
            self.downloaded_images[img_url] = local_path
            self._log("info", f"  Saved: {filename} ({bytes_downloaded:,} bytes)")

            return local_path

        except Exception as e:
            self._log("warning", f"  Failed to download image {img_url[:60]}...: {e}")
            return None

    async def _download_image_async(self, img_url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """Async version: Download image to local directory and return local file path

        Significantly faster in concurrent mode as multiple images can download in parallel.

        Args:
            img_url: Image URL to download
            session: aiohttp ClientSession for reusing connections

        Returns:
            Local file path if successful, None if download failed
        """
        if not self.download_images:
            return None

        # Check if already downloaded
        if img_url in self.downloaded_images:
            return self.downloaded_images[img_url]

        try:
            # First resolve the URL if it's a dynamic endpoint (still sync for now)
            resolved_url = self._resolve_image_url(img_url)

            # Generate local filename from URL (with path traversal protection)
            parsed = urlparse(resolved_url)
            filename = Path(parsed.path).name  # Only filename, strips any path components

            # Security: Validate filename to prevent path traversal
            if not filename or '..' in filename or filename.startswith(('/', '\\')):
                filename = hashlib.blake2s(resolved_url.encode()).hexdigest() + '.jpg'

            # If no valid filename, generate from hash
            if not filename or '.' not in filename:
                filename = hashlib.blake2s(resolved_url.encode()).hexdigest() + '.jpg'

            # Ensure unique filename
            local_path = os.path.join(self.images_dir, filename)
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(local_path):
                filename = f"{base_name}_{counter}{ext}"
                local_path = os.path.join(self.images_dir, filename)
                counter += 1

            # Download the image asynchronously
            self._log("debug", f"  Downloading image: {filename}")
            async with session.get(resolved_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()

                # Save to file asynchronously and track size (with limit to prevent disk fill)
                bytes_downloaded = 0
                async with aiofiles.open(local_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        bytes_downloaded += len(chunk)

                        # Check size limit to prevent disk fill attacks
                        if bytes_downloaded > MAX_IMAGE_SIZE:
                            raise ValueError(f"Image exceeds size limit: {bytes_downloaded / 1024 / 1024:.1f}MB > {MAX_IMAGE_SIZE / 1024 / 1024}MB")

                        await f.write(chunk)

            # Validate image file type
            kind = filetype.guess(local_path)
            if kind is None:
                self._log("warning", f"  Could not determine file type for {filename}, keeping anyway")
            elif kind.mime.startswith('image/'):
                self._log("debug", f"  Validated image: {filename} ({kind.mime})")
            else:
                self._log("warning", f"  Downloaded file is not an image: {filename} ({kind.mime})")

            # Cache the result
            self.downloaded_images[img_url] = local_path
            self._log("debug", f"  Saved: {filename} ({bytes_downloaded:,} bytes)")

            return local_path

        except Exception as e:
            self._log("warning", f"  Failed to download image {img_url[:60]}...: {e}")
            return None

    def _resolve_image_url(self, img_url: str) -> str:
        """Resolve image URL by following redirects to get actual downloadable URL

        This is critical for WebDAM URLs and other dynamic image serving endpoints
        that redirect to actual S3/CDN URLs. WordPress importer doesn't follow redirects,
        so we need to resolve them before writing to XML.

        Also strips signed parameters from S3 URLs to provide clean, permanent URLs
        that WordPress can reliably download.

        Args:
            img_url: Original image URL (may be a redirect endpoint)

        Returns:
            Final clean image URL after following redirects and stripping signed params
        """
        # Check cache first
        if img_url in self.resolved_image_cache:
            return self.resolved_image_cache[img_url]

        # Only resolve URLs that look like they might redirect
        # WebDAM URLs, dealer.com dynamic endpoints, etc.
        should_resolve = any([
            'webdamdb.com' in img_url.lower(),
            'display.php' in img_url.lower(),
            ('dealer.com' in img_url.lower() and '?' in img_url),
        ])

        if not should_resolve:
            # Not a known dynamic endpoint, return as-is
            self.resolved_image_cache[img_url] = img_url
            return img_url

        # Try to follow redirects to get actual image URL
        try:
            response = requests.head(img_url, allow_redirects=True, timeout=10)

            # Check if we got redirected
            if response.url != img_url:
                # We were redirected - use the final URL
                final_url = response.url

                # If it's an S3 URL, strip signed parameters to get clean, permanent URL
                # S3 buckets often allow public access without signed params
                # This gives WordPress a reliable URL that won't expire
                if 's3.us-west-2.amazonaws.com' in final_url or 's3.' in final_url:
                    parsed = urlparse(final_url)
                    # Keep only scheme, netloc, and path - remove query params
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    self._log("info", f"  Resolved & cleaned: {img_url[:50]}... -> {clean_url[:70]}...")
                    self.resolved_image_cache[img_url] = clean_url
                    return clean_url
                else:
                    self._log("info", f"  Resolved image: {img_url[:60]}... -> {final_url[:60]}...")
                    self.resolved_image_cache[img_url] = final_url
                    return final_url
            else:
                # No redirect, return original
                self.resolved_image_cache[img_url] = img_url
                return img_url

        except Exception as e:
            # If resolution fails, log warning and return original URL
            self._log("warning", f"  Could not resolve image URL {img_url[:60]}...: {e}")
            self.resolved_image_cache[img_url] = img_url
            return img_url

    def _get_base_domain(self) -> str:
        """Extract base domain from extracted blog posts"""
        if not self.extracted_data:
            return 'https://example.com'

        # Get first successful post URL and extract domain
        for post in self.extracted_data:
            if post.get('status') == 'success' and post.get('url'):
                url = post['url']
                # Extract scheme and domain (e.g., https://www.devenerelaw.com)
                parsed = urlparse(url)
                base_domain = f"{parsed.scheme}://{parsed.netloc}"
                return base_domain

        return 'https://example.com'

    def _write_xml_header(self, f: Any) -> None:
        """Write WordPress XML header with actual source domain"""
        base_domain = self._get_base_domain()

        f.write('<?xml version="1.0" encoding="UTF-8" ?>\n')
        f.write('<rss version="2.0"\n')
        f.write('    xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"\n')
        f.write('    xmlns:content="http://purl.org/rss/1.0/modules/content/"\n')
        f.write('    xmlns:wfw="http://wellformedweb.org/CommentAPI/"\n')
        f.write('    xmlns:dc="http://purl.org/dc/elements/1.1/"\n')
        f.write('    xmlns:wp="http://wordpress.org/export/1.2/">\n')
        f.write('<channel>\n')
        f.write('<title>Blog Export</title>\n')
        f.write(f'<link>{base_domain}</link>\n')
        f.write('<description>Exported blog posts</description>\n')
        f.write('<pubDate>Wed, 01 Jan 2025 00:00:00 +0000</pubDate>\n')
        f.write('<language>en-US</language>\n')
        f.write('<wp:wxr_version>1.2</wp:wxr_version>\n')
        f.write(f'<wp:base_site_url>{base_domain}</wp:base_site_url>\n')
        f.write(f'<wp:base_blog_url>{base_domain}</wp:base_blog_url>\n')

    def _write_xml_footer(self, f: Any) -> None:
        """Write WordPress XML footer"""
        f.write('</channel>\n')
        f.write('</rss>\n')

    def _convert_relative_urls_to_absolute(self, html_content: str, base_url: str) -> str:
        """Convert URLs based on relative_links setting

        If relative_links=True:
            - Keep internal links relative (for WordPress migration)
            - Convert external relative links to absolute
            - Convert internal absolute links to relative
        If relative_links=False:
            - Convert all relative links to absolute (for preservation)
        """
        if not html_content:
            return html_content

        soup = BeautifulSoup(html_content, 'html.parser')
        base_domain = urlparse(base_url).netloc

        # Process all URLs in <a> tags
        for link in soup.find_all('a', href=True):
            if isinstance(link, Tag):
                href = link.get('href', '')
                href_str = str(href)

                # Skip anchors, mailto, tel
                if href_str.startswith(('#', 'mailto:', 'tel:')):
                    continue

                # If it's already absolute
                if href_str.startswith(('http://', 'https://')):
                    parsed_href = urlparse(href_str)

                    if self.relative_links and parsed_href.netloc == base_domain:
                        # Convert internal absolute URLs to relative paths
                        relative_path = parsed_href.path
                        if parsed_href.query:
                            relative_path += '?' + parsed_href.query
                        if parsed_href.fragment:
                            relative_path += '#' + parsed_href.fragment
                        link['href'] = relative_path
                    # External absolute URLs: keep as-is
                    continue
                else:
                    # It's relative - handle based on relative_links setting
                    if not self.relative_links:
                        # Convert all relative links to absolute
                        absolute_url = urljoin(base_url, href_str)
                        link['href'] = absolute_url
                    else:
                        # Keep relative links as-is (they're already relative)
                        # Just ensure they're properly formatted
                        continue

        # Convert all relative URLs in <img> tags to absolute AND resolve/download images
        for img in soup.find_all('img', src=True):
            if isinstance(img, Tag):
                src = img.get('src', '')
                src_str = str(src)

                # Convert relative URLs to absolute
                if src and not src_str.startswith(('http://', 'https://', 'data:')):
                    src_str = urljoin(base_url, src_str)

                # Handle image downloads or URL resolution
                if src_str.startswith(('http://', 'https://')):
                    # Always resolve dynamic URLs (WebDAM, dealer.com, etc.) to get clean HTTPS URLs
                    src_str = self._resolve_image_url(src_str)

                    # Download image locally as backup (if enabled)
                    # But ALWAYS use the HTTPS URL in XML so WordPress can import it
                    if self.download_images:
                        self._download_image(src_str)
                        # Note: We download but still use src_str (HTTPS URL) in XML
                        # This gives us backup + WordPress compatibility

                img['src'] = src_str

        # Use decode() with formatter="minimal" to prevent BeautifulSoup from adding
        # line breaks in long href attributes, which can cause WordPress to truncate URLs
        return soup.decode(formatter="minimal")

    def _write_xml_post(self, f: Any, post: Dict[str, Any]) -> None:
        """Write single post to WordPress XML"""
        # Normalize unicode characters in all text fields
        title = self.normalize_unicode(post["title"])
        author = self.normalize_unicode(post["author"])
        content = self.normalize_unicode(post["content"])

        # Convert relative URLs to absolute so WordPress can detect and replace them
        content = self._convert_relative_urls_to_absolute(content, post["url"])

        # Parse and format the date properly
        date_formats = self.parse_and_format_date(post["date"])

        # Generate unique positive post ID
        post_id = abs(hash(post["url"]) % 1000000) + 1

        f.write('<item>\n')
        f.write(f'<title><![CDATA[{title}]]></title>\n')
        f.write(f'<link>{html.escape(post["url"])}</link>\n')
        f.write(f'<pubDate>{date_formats["rfc2822"]}</pubDate>\n')
        f.write(f'<dc:creator><![CDATA[{author}]]></dc:creator>\n')
        f.write('<guid isPermaLink="false">{}</guid>\n'.format(html.escape(post["url"])))
        f.write('<description></description>\n')
        f.write('<content:encoded><![CDATA[')
        # Handle ']]>' in content to prevent CDATA breaking (like WordPress wxr_cdata)
        content = content.replace(']]>', ']]]]><![CDATA[>')
        f.write(content)
        f.write(']]></content:encoded>\n')
        f.write('<excerpt:encoded><![CDATA[]]></excerpt:encoded>\n')
        f.write(f'<wp:post_id>{post_id}</wp:post_id>\n')
        f.write(f'<wp:post_date><![CDATA[{date_formats["mysql"]}]]></wp:post_date>\n')
        f.write(f'<wp:post_date_gmt><![CDATA[{date_formats["mysql_gmt"]}]]></wp:post_date_gmt>\n')
        f.write('<wp:comment_status><![CDATA[open]]></wp:comment_status>\n')
        f.write('<wp:ping_status><![CDATA[open]]></wp:ping_status>\n')
        # Extract slug from source URL (last part of path, minus parent folders)
        from urllib.parse import urlparse
        parsed_url = urlparse(post["url"])
        # Get the last segment of the path (e.g., /blog/2024/post-slug/ -> post-slug)
        path_segments = [s for s in parsed_url.path.split('/') if s]
        slug = path_segments[-1] if path_segments else title.lower().replace(' ', '-')
        # Remove .htm, .html, .php extensions from slug
        slug = re.sub(r'\.(htm|html|php)$', '', slug, flags=re.IGNORECASE)
        f.write('<wp:post_name><![CDATA[{}]]></wp:post_name>\n'.format(slug))
        f.write('<wp:status><![CDATA[publish]]></wp:status>\n')
        f.write('<wp:post_parent>0</wp:post_parent>\n')
        f.write('<wp:menu_order>0</wp:menu_order>\n')
        f.write('<wp:post_type><![CDATA[post]]></wp:post_type>\n')
        f.write('<wp:post_password><![CDATA[]]></wp:post_password>\n')
        f.write('<wp:is_sticky>0</wp:is_sticky>\n')

        # Add categories
        for cat in post["categories"]:
            normalized_cat = self.normalize_unicode(cat)
            f.write('<category domain="category" nicename="{}"><![CDATA[{}]]></category>\n'.format(
                normalized_cat.lower().replace(' ', '-'), normalized_cat))

        # Add tags
        for tag in post["tags"]:
            normalized_tag = self.normalize_unicode(tag)
            f.write('<category domain="post_tag" nicename="{}"><![CDATA[{}]]></category>\n'.format(
                normalized_tag.lower().replace(' ', '-'), normalized_tag))

        f.write('</item>\n')

        # Write attachment items for each image in the post
        if 'images' in post and post['images']:
            for idx, image in enumerate(post['images']):
                self._write_xml_attachment(f, image, idx, post_id, date_formats, author)

    def _write_xml_attachment(self, f: Any, image: Dict[str, str], post_id: int, parent_post_id: int, date_formats: dict, author: str) -> None:
        """Write single attachment item to WordPress XML"""
        # Get image source - resolve to clean HTTPS URL for WordPress import
        image_src = image['src']
        if image_src.startswith(('http://', 'https://')):
            # Always resolve dynamic URLs to get clean HTTPS URLs
            image_src = self._resolve_image_url(image_src)

            # Download locally as backup (if enabled)
            # But use HTTPS URL in XML so WordPress can import it
            if self.download_images:
                self._download_image(image_src)
                # Note: We download but still use image_src (HTTPS URL) in XML

        # Generate unique attachment ID
        attachment_id = abs(hash(image_src) % 1000000) + 1000000  # Offset to avoid collision with posts

        # Extract filename from URL for title
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(image_src)
        base_filename = os.path.basename(parsed_url.path) or 'image'

        # Make filename unique by including query parameters or hash
        # This prevents WordPress from treating all "GetLibraryImage" URLs as the same file
        if parsed_url.query:
            # Parse query string to extract unique identifiers
            query_params = parse_qs(parsed_url.query)
            unique_id = None

            # Look for common ID parameters
            for param_name in ['fileNameOrId', 'id', 'file', 'image', 'imageId']:
                if param_name in query_params:
                    unique_id = query_params[param_name][0]
                    break

            if unique_id:
                # Append unique ID to filename: GetLibraryImage_208132
                name_part, ext_part = os.path.splitext(base_filename)
                filename = f"{name_part}_{unique_id}{ext_part if ext_part else ''}"
            else:
                # No recognizable ID param, use hash of full URL for uniqueness
                url_hash = hashlib.md5(image_src.encode()).hexdigest()[:8]
                name_part, ext_part = os.path.splitext(base_filename)
                filename = f"{name_part}_{url_hash}{ext_part if ext_part else ''}"
        else:
            filename = base_filename

        title = os.path.splitext(filename)[0].replace('-', ' ').replace('_', ' ').title()

        f.write('<item>\n')
        f.write(f'<title><![CDATA[{title}]]></title>\n')
        f.write(f'<link>{html.escape(image_src)}</link>\n')
        f.write(f'<pubDate>{date_formats["rfc2822"]}</pubDate>\n')
        f.write(f'<dc:creator><![CDATA[{author}]]></dc:creator>\n')
        f.write('<guid isPermaLink="false">{}</guid>\n'.format(html.escape(image_src)))
        f.write('<description></description>\n')
        f.write('<content:encoded><![CDATA[]]></content:encoded>\n')
        f.write('<excerpt:encoded><![CDATA[]]></excerpt:encoded>\n')
        f.write(f'<wp:post_id>{attachment_id}</wp:post_id>\n')
        f.write(f'<wp:post_date><![CDATA[{date_formats["mysql"]}]]></wp:post_date>\n')
        f.write(f'<wp:post_date_gmt><![CDATA[{date_formats["mysql_gmt"]}]]></wp:post_date_gmt>\n')
        f.write('<wp:comment_status><![CDATA[closed]]></wp:comment_status>\n')
        f.write('<wp:ping_status><![CDATA[closed]]></wp:ping_status>\n')
        f.write('<wp:post_name><![CDATA[{}]]></wp:post_name>\n'.format(filename.lower().replace(' ', '-')))
        f.write('<wp:status><![CDATA[inherit]]></wp:status>\n')
        f.write(f'<wp:post_parent>{parent_post_id}</wp:post_parent>\n')
        f.write('<wp:menu_order>0</wp:menu_order>\n')
        f.write('<wp:post_type><![CDATA[attachment]]></wp:post_type>\n')
        f.write('<wp:post_password><![CDATA[]]></wp:post_password>\n')
        f.write('<wp:is_sticky>0</wp:is_sticky>\n')
        f.write('<wp:attachment_url><![CDATA[{}]]></wp:attachment_url>\n'.format(html.escape(image_src)))
        f.write('</item>\n')

    def save_to_xml(self, filename: str) -> None:
        """Save extracted data to WordPress XML format"""
        output_path = os.path.join(self.output_dir, filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            self._write_xml_header(f)

            for post in self.extracted_data:
                if post['status'] == 'success':
                    self._write_xml_post(f, post)

            self._write_xml_footer(f)

        self._log("info", f"WordPress XML saved to: {output_path}")

    def save_links_to_txt(self, filename: str) -> None:
        """Save all extracted links to a txt file"""
        output_path = os.path.join(self.output_dir, filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Extracted Hyperlinks from Blog Posts\n")
            f.write("# Format: [Post Title] Link Text -> URL\n\n")

            for post in self.extracted_data:
                if post['status'] == 'success' and post.get('links'):
                    f.write(f"## {post['title']}\n")
                    f.write(f"Source: {post['url']}\n\n")

                    for link in post['links']:
                        f.write(f"{link['text']} -> {link['url']}\n")

                    f.write("\n" + "="*80 + "\n\n")

        self._log("info", f"Links saved to: {output_path}")

    def save_to_json(self, filename: str) -> None:
        """Save extracted data to JSON format"""
        output_path = os.path.join(self.output_dir, filename)

        # Prepare data for JSON export
        json_data: Dict[str, Any] = {
            'export_date': datetime.now().isoformat(),
            'total_posts': len([p for p in self.extracted_data if p['status'] == 'success']),
            'posts': []
        }

        for post in self.extracted_data:
            if post['status'] == 'success':
                json_post = {
                    'url': post['url'],
                    'title': post['title'],
                    'author': post['author'],
                    'date': post['date'],
                    'platform': post.get('platform', 'unknown'),
                    'content': post['content'],
                    'content_length': post['content_length'],
                    'categories': post['categories'],
                    'tags': post['tags'],
                    'links': post.get('links', [])
                }
                json_data['posts'].append(json_post)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        self._log("info", f"JSON saved to: {output_path}")

    def save_to_csv(self, filename: str) -> None:
        """Save extracted data to CSV format"""
        output_path = os.path.join(self.output_dir, filename)

        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['url', 'title', 'author', 'date', 'platform', 'content_length',
                         'categories', 'tags', 'links_count', 'content']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for post in self.extracted_data:
                if post['status'] == 'success':
                    csv_row = {
                        'url': post['url'],
                        'title': post['title'],
                        'author': post['author'],
                        'date': post['date'],
                        'platform': post.get('platform', 'unknown'),
                        'content_length': post['content_length'],
                        'categories': ', '.join(post['categories']),
                        'tags': ', '.join(post['tags']),
                        'links_count': len(post.get('links', [])),
                        'content': post['content']
                    }
                    writer.writerow(csv_row)

        self._log("info", f"CSV saved to: {output_path}")

    def get_xml_content(self) -> str:
        """Generate and return WordPress XML content as string"""
        output = io.StringIO()
        self._write_xml_header(output)

        for post in self.extracted_data:
            if post['status'] == 'success':
                self._write_xml_post(output, post)

        self._write_xml_footer(output)
        return output.getvalue()

    def get_json_content(self) -> str:
        """Generate and return JSON content as string"""
        json_data: Dict[str, Any] = {
            'export_date': datetime.now().isoformat(),
            'total_posts': len([p for p in self.extracted_data if p['status'] == 'success']),
            'posts': []
        }

        for post in self.extracted_data:
            if post['status'] == 'success':
                json_post = {
                    'url': post['url'],
                    'title': post['title'],
                    'author': post['author'],
                    'date': post['date'],
                    'platform': post.get('platform', 'unknown'),
                    'content': post['content'],
                    'content_length': post['content_length'],
                    'categories': post['categories'],
                    'tags': post['tags'],
                    'links': post.get('links', [])
                }
                json_data['posts'].append(json_post)

        return json.dumps(json_data, ensure_ascii=False, indent=2)

    def get_csv_content(self) -> str:
        """Generate and return CSV content as string"""
        output = io.StringIO()
        fieldnames = ['url', 'title', 'author', 'date', 'platform', 'content_length',
                     'categories', 'tags', 'links_count', 'content']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for post in self.extracted_data:
            if post['status'] == 'success':
                csv_row = {
                    'url': post['url'],
                    'title': post['title'],
                    'author': post['author'],
                    'date': post['date'],
                    'platform': post.get('platform', 'unknown'),
                    'content_length': post['content_length'],
                    'categories': ', '.join(post['categories']),
                    'tags': ', '.join(post['tags']),
                    'links_count': len(post.get('links', [])),
                    'content': post['content']
                }
                writer.writerow(csv_row)

        return output.getvalue()

    def get_links_content(self) -> str:
        """Generate and return links content as string"""
        output = io.StringIO()
        output.write("# Extracted Hyperlinks from Blog Posts\n")
        output.write("# Format: [Post Title] Link Text -> URL\n\n")

        for post in self.extracted_data:
            if post['status'] == 'success' and post.get('links'):
                output.write(f"## {post['title']}\n")
                output.write(f"Source: {post['url']}\n\n")

                for link in post['links']:
                    output.write(f"{link['text']} -> {link['url']}\n")

                output.write("\n" + "="*80 + "\n\n")

        return output.getvalue()


def main():
    """Main function for CLI usage"""
    extractor = BlogExtractor()
    urls = extractor.load_urls()

    if not urls:
        extractor._log("warning", "No URLs to process")
        return

    extractor._log("info", f"Processing {len(urls)} URLs with Playwright...")
    success_count = 0
    duplicate_count = 0

    for i, url in enumerate(urls, 1):
        extractor._log("info", f"\n[{i}/{len(urls)}] Processing...")
        data = extractor.extract_blog_data(url)

        if data['status'] == 'success':
            extractor._log("info", f"[OK] Success: {data['title']}")
            extractor._log("info", f"  URL: {data['url']}")
            extractor._log("info", f"  Date: {data['date']}")
            extractor._log("info", f"  Author: {data['author']}")
            extractor._log("info", f"  Content: {data['content_length']} characters")
            extractor._log("info", f"  Links: {len(data.get('links', []))} found")
            if data['categories']:
                extractor._log("info", f"  Categories: {', '.join(data['categories'])}")
            if data['tags']:
                extractor._log("info", f"  Tags: {', '.join(data['tags'])}")
            success_count += 1
        elif data['status'] == 'duplicate':
            extractor._log("warning", f"[SKIP] Duplicate: {data['title']}")
            duplicate_count += 1
        else:
            extractor._log("error", f"[FAIL] Failed - {data.get('error', 'Unknown error')}")

        # Delay between requests
        if i < len(urls):
            time.sleep(REQUEST_DELAY)

    # Save results
    if extractor.extracted_data:
        extractor.save_to_xml("blog_posts.xml")
        extractor.save_links_to_txt("extracted_links.txt")

    extractor._log("info", "\n=== Summary ===")
    extractor._log("info", f"Total URLs: {len(urls)}")
    extractor._log("info", f"Successful: {success_count}")
    extractor._log("info", f"Duplicates: {duplicate_count}")
    extractor._log("info", f"Failed: {len(urls) - success_count - duplicate_count}")
    if len(urls) > 0:
        extractor._log("info", f"Success rate: {success_count/len(urls)*100:.1f}%")


if __name__ == "__main__":
    main()
