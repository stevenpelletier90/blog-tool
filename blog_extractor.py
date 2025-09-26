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
        """Extract main post content with HTML structure preserved"""
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
                # Clean up unwanted elements
                for unwanted in content_elem.find_all(['script', 'style', 'noscript']):
                    unwanted.decompose()

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
        # Parse the HTML content
        soup = BeautifulSoup(html_content, 'html.parser')

        # Define allowed tags (semantic HTML only, NO images or br tags)
        allowed_tags = {
            'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li',
            'blockquote', 'pre', 'code', 'a'
        }

        # Define which attributes to keep for specific tags
        allowed_attrs = {
            'a': ['href']
        }

        # Remove unwanted elements but keep their content
        unwrap_tags = ['div', 'span', 'section', 'article', 'header', 'footer', 'nav']
        for tag_name in unwrap_tags:
            for tag in soup.find_all(tag_name):
                if isinstance(tag, Tag):
                    tag.unwrap()

        # Clean attributes from all elements
        for element in soup.find_all():
            if isinstance(element, Tag):
                if element.name in allowed_tags:
                    # Keep only allowed attributes for this tag
                    allowed = allowed_attrs.get(element.name, [])
                    attrs_to_remove = [attr for attr in element.attrs.keys() if attr not in allowed]
                    for attr in attrs_to_remove:
                        del element.attrs[attr]
                else:
                    # Remove disallowed tags but keep their content
                    element.unwrap()

        # Remove empty paragraphs and those containing only br tags
        for p in soup.find_all('p'):
            if isinstance(p, Tag):
                text_content = p.get_text().strip()
                # Remove if empty or contains only whitespace/breaks
                if not text_content or text_content == '':
                    p.decompose()
                # Also remove paragraphs that only contain br tags
                elif p.find_all('br') and not p.get_text().strip():
                    p.decompose()

        # Remove all br tags completely
        for br in soup.find_all('br'):
            if isinstance(br, Tag):
                br.decompose()

        # Return cleaned HTML
        return str(soup).strip()

    def html_to_gutenberg(self, html_content: str) -> str:
        """Convert clean HTML to Gutenberg blocks format"""
        if not html_content.strip():
            return ""

        # Parse the cleaned HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        gutenberg_blocks = []

        # Process each top-level element
        for element in soup.children:
            if isinstance(element, Tag) and element.name:
                block_html = self.element_to_gutenberg_block(element)
                if block_html:
                    gutenberg_blocks.append(block_html)
            elif not isinstance(element, Tag) and str(element).strip():  # Text node with content
                # Wrap loose text in paragraph block
                text = str(element).strip()
                if text:
                    gutenberg_blocks.append(f'<!-- wp:paragraph -->\n<p>{text}</p>\n<!-- /wp:paragraph -->')

        return '\n\n'.join(gutenberg_blocks)

    def element_to_gutenberg_block(self, element) -> str:
        """Convert a single HTML element to Gutenberg block"""
        tag_name = element.name.lower()

        if tag_name == 'p':
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
            # Wrap blockquote in proper wp-block-quote class
            inner_content = element.decode_contents()
            return f'<!-- wp:quote -->\n<blockquote class="wp-block-quote">{inner_content}</blockquote>\n<!-- /wp:quote -->'

        elif tag_name == 'pre':
            # Check if it contains code
            if element.find('code'):
                content = element.get_text()
                return f'<!-- wp:code -->\n<pre class="wp-block-code"><code>{content}</code></pre>\n<!-- /wp:code -->'
            else:
                content = str(element)
                return f'<!-- wp:preformatted -->\n{content}\n<!-- /wp:preformatted -->'

        elif tag_name == 'img':
            # Skip images completely
            return ""

        else:
            # For other elements, wrap in paragraph or return as-is
            content = str(element)
            if tag_name in ['strong', 'b', 'em', 'i', 'u', 'a', 'code']:
                # Inline elements - wrap in paragraph
                return f'<!-- wp:paragraph -->\n<p>{content}</p>\n<!-- /wp:paragraph -->'
            elif tag_name == 'br':
                # Skip br tags completely
                return ""
            else:
                # Block elements - return as-is or wrap in paragraph
                return f'<!-- wp:paragraph -->\n<p>{content}</p>\n<!-- /wp:paragraph -->'

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

        # Calculate text length for display (strip HTML tags for counting)
        text_for_counting = BeautifulSoup(content, 'html.parser').get_text() if content else ""

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
                    # Handle ']]>' in content to prevent CDATA breaking (like WordPress wxr_cdata)
                    content = post["content"].replace(']]>', ']]]]><![CDATA[>')
                    f.write(content)
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
            print(f"✓ Success: {data['title']}")
            print(f"  URL: {data['url']}")
            print(f"  Date: {data['date']}")
            print(f"  Author: {data['author']}")
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