#!/usr/bin/env python3
"""
Simple Blog Extractor CLI
Extract blog posts from URLs and convert to WordPress XML.
"""

import os
import time
from pathlib import Path

from blog_extractor import BlogExtractor, URLS_FILE, REQUEST_DELAY


def main():
    """Main extraction function"""
    print("=== Blog Post Extractor ===")

    # Just run the main function from the extractor
    from blog_extractor import main as extractor_main
    extractor_main()


if __name__ == "__main__":
    main()