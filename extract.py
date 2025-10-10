#!/usr/bin/env python3
"""
Blog Extractor CLI - Enhanced with argparse
Extract blog posts from URLs and convert to multiple formats.
"""

import argparse
import asyncio
import sys
import time

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    tqdm = None  # type: ignore

from blog_extractor import BlogExtractor, URLS_FILE, OUTPUT_DIR, REQUEST_DELAY


def main():
    """Main extraction function with CLI arguments"""
    parser = argparse.ArgumentParser(
        description='Extract blog posts and convert to WordPress XML, JSON, or CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use defaults (urls.txt, output/, XML)
  %(prog)s --urls myblog.txt --output results/  # Custom files
  %(prog)s --format json                     # Export as JSON
  %(prog)s --concurrent 5                    # Process 5 URLs simultaneously (3-5x faster!)
  %(prog)s --delay 5 --retries 5             # More retries, longer delay (sequential)
  %(prog)s --concurrent 3 --format all       # Concurrent + all formats
  %(prog)s --verbose                         # Show detailed logs
  %(prog)s --quiet                           # Minimal output
        """
    )

    parser.add_argument(
        '--urls',
        default=URLS_FILE,
        help=f'Path to file containing URLs (default: {URLS_FILE})'
    )
    parser.add_argument(
        '--output',
        default=OUTPUT_DIR,
        help=f'Output directory for results (default: {OUTPUT_DIR})'
    )
    parser.add_argument(
        '--format',
        choices=['xml', 'json', 'csv', 'all'],
        default='xml',
        help='Output format (default: xml)'
    )
    parser.add_argument(
        '--delay',
        type=int,
        default=REQUEST_DELAY,
        help=f'Delay between requests in seconds (default: {REQUEST_DELAY})'
    )
    parser.add_argument(
        '--retries',
        type=int,
        default=3,
        help='Max retries per URL (default: 3)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed logs'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimal output (errors only)'
    )
    parser.add_argument(
        '--concurrent',
        type=int,
        default=1,
        help='Max concurrent requests (1=sequential, 5=recommended max, default: 1)'
    )
    parser.add_argument(
        '--relative-links',
        action='store_true',
        help='Keep internal links relative in XML output (useful for domain migration)'
    )
    parser.add_argument(
        '--include-images',
        action='store_true',
        default=True,
        help='Include images in exported content (WordPress will auto-download during import, default: True)'
    )
    parser.add_argument(
        '--no-images',
        action='store_true',
        help='Exclude images from exported content'
    )

    args = parser.parse_args()

    # Handle verbose/quiet modes
    verbose = args.verbose if not args.quiet else False

    # Handle include_images: --no-images takes precedence
    include_images = not args.no_images if args.no_images else args.include_images

    # Create extractor
    extractor = BlogExtractor(
        urls_file=args.urls,
        output_dir=args.output,
        verbose=verbose,
        relative_links=args.relative_links,
        include_images=include_images
    )

    # Load URLs
    urls = extractor.load_urls()

    if not urls:
        extractor._log("warning", "No URLs to process")
        return 1

    extractor._log("info", f"=== Blog Post Extractor ===")
    extractor._log("info", f"Processing {len(urls)} URLs with Playwright...")
    extractor._log("info", f"Output format: {args.format}")
    extractor._log("info", f"Max retries per URL: {args.retries}")

    if args.concurrent > 1:
        extractor._log("info", f"Concurrent mode: {args.concurrent} simultaneous requests")
    else:
        extractor._log("info", f"Sequential mode with {args.delay}s delay between requests")

    success_count = 0
    duplicate_count = 0

    # Use async concurrent processing if --concurrent > 1
    if args.concurrent > 1:
        # Async concurrent processing
        extractor._log("info", f"Starting concurrent processing...")
        start_time = time.time()

        results = asyncio.run(extractor.process_urls_concurrently(urls, args.concurrent))

        # Count results
        for result in results:
            if result.get('status') == 'success':
                success_count += 1
                if not args.quiet:
                    extractor._log("info", f"✓ {result.get('title', 'Unknown')}")
            elif result.get('status') == 'duplicate':
                duplicate_count += 1
                if not args.quiet:
                    extractor._log("warning", f"⊘ Duplicate: {result.get('title', 'Unknown')}")

        elapsed = time.time() - start_time
        extractor._log("info", f"\nCompleted in {elapsed:.1f} seconds")

    # Process URLs with optional progress bar (sequential)
    elif HAS_TQDM and tqdm is not None and not args.quiet:
        progress_bar = tqdm(total=len(urls), desc="Extracting", unit="post")
        for i, url in enumerate(urls, 1):
            data = extractor.extract_blog_data(url)

            if data['status'] == 'success':
                # Update tqdm description
                progress_bar.set_postfix({
                    'platform': data.get('platform', 'unknown'),
                    'last': data['title'][:30]
                })
                success_count += 1
            elif data['status'] == 'duplicate':
                duplicate_count += 1

            # Update progress bar
            progress_bar.update(1)

            # Delay between requests
            if i < len(urls):
                time.sleep(args.delay)

        progress_bar.close()
    else:
        # No tqdm - verbose output
        for i, url in enumerate(urls, 1):
            extractor._log("info", f"\n[{i}/{len(urls)}] Processing...")
            data = extractor.extract_blog_data(url)

            if data['status'] == 'success':
                extractor._log("info", f"✓ Success: {data['title']}")
                extractor._log("info", f"  Platform: {data.get('platform', 'unknown')}")
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
                extractor._log("warning", f"⊘ Duplicate: {data['title']}")
                duplicate_count += 1
            else:
                extractor._log("error", f"✗ Failed - {data.get('error', 'Unknown error')}")

            # Delay between requests
            if i < len(urls):
                time.sleep(args.delay)

    # Save results
    if extractor.extracted_data:
        if args.format in ['xml', 'all']:
            extractor.save_to_xml("blog_posts.xml")
        if args.format in ['json', 'all']:
            try:
                extractor.save_to_json("blog_posts.json")
            except AttributeError:
                extractor._log("warning", "JSON export not yet implemented")
        if args.format in ['csv', 'all']:
            try:
                extractor.save_to_csv("blog_posts.csv")
            except AttributeError:
                extractor._log("warning", "CSV export not yet implemented")

        extractor.save_links_to_txt("extracted_links.txt")

    # Summary
    extractor._log("info", f"\n=== Summary ===")
    extractor._log("info", f"Total URLs: {len(urls)}")
    extractor._log("info", f"Successful: {success_count}")
    extractor._log("info", f"Duplicates: {duplicate_count}")
    extractor._log("info", f"Failed: {len(urls) - success_count - duplicate_count}")
    if len(urls) > 0:
        extractor._log("info", f"Success rate: {success_count/len(urls)*100:.1f}%")

    return 0 if success_count == len(urls) else 1


if __name__ == "__main__":
    sys.exit(main())