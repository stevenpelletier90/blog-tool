#!/usr/bin/env python3
"""
Blog Content Extractor - Simplified with Playwright Only
Extracts blog posts and converts to WordPress XML using only the best tool.
"""

# Configuration
URLS_FILE = "urls.txt"
OUTPUT_DIR = "output"
REQUEST_DELAY = 2  # seconds between requests

# Standard library imports
import csv
import html
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
from urllib.parse import urljoin, urlparse

# Third-party imports
import requests
from bs4 import BeautifulSoup, Tag

# Playwright import
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("ERROR: Playwright is required. Install with: pip install playwright && playwright install chromium")
    exit(1)


class BlogExtractor:
    """Simplified blog extractor using only Playwright for all JavaScript-heavy sites"""

    def __init__(self, urls_file: str = URLS_FILE, output_dir: str = OUTPUT_DIR):
        self.urls_file = urls_file
        self.output_dir = output_dir
        self.extracted_data: List[Dict[str, Any]] = []

        # Create output directory if it doesn't exist
        Path(self.output_dir).mkdir(exist_ok=True)

        # User agents for variety
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]

    def fetch_content(self, url: str) -> Optional[str]:
        """Fetch URL content using Playwright - handles all dynamic content"""
        if not HAS_PLAYWRIGHT:
            return None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=random.choice(self.user_agents),
                    viewport={'width': 1920, 'height': 1080}
                )
                page = context.new_page()

                # Navigate and wait for content to load
                print("  Fetching with Playwright...")
                page.goto(url, wait_until='networkidle', timeout=30000)

                # Wait extra time for any dynamic content
                page.wait_for_timeout(3000)

                # Get page content
                html_content = page.content()
                browser.close()
                return html_content

        except Exception as e:
            print(f"  Playwright failed: {e}")
            return None

    def extract_categories(self, soup: BeautifulSoup) -> List[str]:
        """Extract categories using Wix-specific selectors"""
        selectors = [
            # Wix-specific selectors based on your HTML
            'ul[aria-label="Post categories"] a',
            'section ul.pRGtWE li a',
            '.pRGtWE a',
            # Generic fallbacks
            '.category a',
            '.categories a',
            'meta[name="article:section"]',
        ]

        categories = set()
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                if isinstance(element, Tag):
                    if element.name == 'meta':
                        content = element.get('content')
                        if content:
                            cat = str(content).strip()
                        else:
                            cat = ''
                    else:
                        cat = element.get_text().strip()

                    if cat and cat.lower() not in ['uncategorized', 'blog', 'all posts']:
                        categories.add(cat)

        return list(categories)

    def extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """Extract tags using Wix-specific selectors"""
        selectors = [
            # Wix-specific selectors based on your HTML
            'nav[aria-label="Tags"] ul li a',
            '.zmug2R li a',
            '._u2fqx',
            # Generic fallbacks
            '.tag a',
            '.tags a',
            'meta[name="keywords"]',
        ]

        tags = set()
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                if isinstance(element, Tag):
                    if element.name == 'meta':
                        content = element.get('content')
                        if content:
                            tag_content = str(content)
                            tag_parts = tag_content.split(',')
                            new_tags = [t.strip() for t in tag_parts]
                            for tag in new_tags:
                                if tag:
                                    tags.add(tag)
                    else:
                        tag = element.get_text().strip()
                        if tag:
                            tags.add(tag)

        return list(tags)

    def extract_title(self, soup: BeautifulSoup) -> str:
        """Extract post title"""
        selectors = [
            'h1[data-hook="post-title"]',
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
        """Extract main post content"""
        selectors = [
            'section[data-hook="post-description"]',
            'article .entry-content',
            'article',
            '.post-content',
            '.content',
            'main',
        ]

        for selector in selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Clean up the content
                for script in content_elem.find_all(['script', 'style']):
                    script.decompose()

                content = content_elem.get_text().strip()
                if content and len(content) > 100:  # Must have substantial content
                    return content

        return ""

    def extract_author(self, soup: BeautifulSoup) -> str:
        """Extract author information"""
        selectors = [
            '[data-hook="user-name"]',
            'meta[name="author"]',
            '.author',
            '.byline',
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

    def extract_date(self, soup: BeautifulSoup) -> str:
        """Extract publication date"""
        selectors = [
            '[data-hook="time-ago"]',
            'meta[property="article:published_time"]',
            '.date',
            '.published',
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element and isinstance(element, Tag):
                if element.name == 'meta':
                    content = element.get('content')
                    date_str = str(content) if content else ''
                else:
                    title_attr = element.get('title')
                    if title_attr:
                        date_str = str(title_attr)
                    else:
                        date_str = element.get_text().strip()

                if date_str:
                    return date_str

        return datetime.now().strftime('%Y-%m-%d')

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract hyperlinks from blog post content only (not navigation/menus)"""
        # First find the content area using same selectors as extract_content()
        content_selectors = [
            'section[data-hook="post-description"]',
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

        # Extract links only from within the content area
        links = []
        for link in content_element.find_all('a', href=True):
            if isinstance(link, Tag):
                href_attr = link.get('href', '')
                text = link.get_text().strip()

                if href_attr:  # Only process if href exists
                    href = str(href_attr)  # Convert to string
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
        print(f"Processing: {url}")

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

        # Extract data
        title = self.extract_title(soup)
        content = self.extract_content(soup)
        author = self.extract_author(soup)
        date = self.extract_date(soup)
        categories = self.extract_categories(soup)
        tags = self.extract_tags(soup)
        links = self.extract_links(soup, url)

        data = {
            'status': 'success',
            'url': url,
            'title': title,
            'content': content,
            'content_length': len(content),
            'author': author,
            'date': date,
            'categories': categories,
            'tags': tags,
            'links': links,
        }

        self.extracted_data.append(data)
        return data

    def load_urls(self) -> List[str]:
        """Load URLs from the input file"""
        urls = []
        if not os.path.exists(self.urls_file):
            print(f"Error: {self.urls_file} not found")
            return urls

        with open(self.urls_file, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url and url.startswith('http'):
                    urls.append(url)

        print(f"Loaded {len(urls)} URLs to process")
        return urls

    def save_to_xml(self, filename: str):
        """Save extracted data to WordPress XML format"""
        output_path = os.path.join(self.output_dir, filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8" ?>\n')
            f.write('<rss version="2.0" xmlns:wp="http://wordpress.org/export/1.2/">\n')
            f.write('<channel>\n')
            f.write('<title>Blog Export</title>\n')
            f.write('<description>Exported blog posts</description>\n')

            for post in self.extracted_data:
                if post['status'] == 'success':
                    f.write('<item>\n')
                    f.write(f'<title><![CDATA[{html.escape(post["title"])}]]></title>\n')
                    f.write(f'<link>{html.escape(post["url"])}</link>\n')
                    f.write(f'<wp:post_date>{post["date"]}</wp:post_date>\n')
                    f.write(f'<dc:creator>{html.escape(post["author"])}</dc:creator>\n')
                    f.write('<content:encoded><![CDATA[')
                    f.write(html.escape(post["content"]))
                    f.write(']]></content:encoded>\n')

                    # Add categories
                    for cat in post["categories"]:
                        f.write(f'<category><![CDATA[{html.escape(cat)}]]></category>\n')

                    # Add tags
                    for tag in post["tags"]:
                        f.write(f'<wp:tag><![CDATA[{html.escape(tag)}]]></wp:tag>\n')

                    f.write('</item>\n')

            f.write('</channel>\n')
            f.write('</rss>\n')

        print(f"WordPress XML saved to: {output_path}")

    def save_links_to_txt(self, filename: str):
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

        print(f"Links saved to: {output_path}")


def main():
    """Main function for CLI usage"""
    extractor = BlogExtractor()
    urls = extractor.load_urls()

    if not urls:
        print("No URLs to process")
        return

    print(f"Processing {len(urls)} URLs with Playwright...")
    success_count = 0

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}]", end=" ")
        data = extractor.extract_blog_data(url)

        if data['status'] == 'success':
            print(f"✓ Success - {data['title']}")
            print(f"  Content: {data['content_length']} characters")
            print(f"  Links: {len(data.get('links', []))} found")
            if data['categories']:
                print(f"  Categories: {', '.join(data['categories'])}")
            if data['tags']:
                print(f"  Tags: {', '.join(data['tags'])}")
            success_count += 1
        else:
            print(f"✗ Failed - {data.get('error', 'Unknown error')}")

        # Delay between requests
        if i < len(urls):
            time.sleep(REQUEST_DELAY)

    # Save results
    if extractor.extracted_data:
        extractor.save_to_xml("blog_posts.xml")
        extractor.save_links_to_txt("extracted_links.txt")

    print(f"\n=== Summary ===")
    print(f"Total URLs: {len(urls)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(urls) - success_count}")
    print(f"Success rate: {success_count/len(urls)*100:.1f}%")


if __name__ == "__main__":
    main()