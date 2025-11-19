#!/usr/bin/env python3
"""
Blog Extractor CLI - Enhanced with argparse
Extract blog posts from URLs and convert to multiple formats.
"""

__version__ = "1.0.0"

# Setup Windows environment before any other imports
import sys
if sys.platform.startswith('win'):
    import warnings
    # Suppress Playwright subprocess cleanup warnings on Windows
    # Note: ProactorEventLoop is the default on Windows since Python 3.8
    warnings.filterwarnings("ignore", category=ResourceWarning)

# Standard library imports
import argparse
import asyncio
import logging
import time

# Third-party imports
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

# Local imports
from blog_extractor import OUTPUT_DIR, REQUEST_DELAY, URLS_FILE, BlogExtractor

# Configure logging (after imports)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Initialize rich console
console = Console()


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
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
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
        help='Include images in exported content (default: True)'
    )
    parser.add_argument(
        '--no-images',
        action='store_true',
        help='Exclude images from exported content'
    )
    parser.add_argument(
        '--download-images',
        action='store_true',
        default=False,
        help='Download images locally to output/images/ (protects against source images being removed)'
    )
    parser.add_argument(
        '--no-download-images',
        action='store_true',
        help='Explicitly disable image downloads (same as default behavior)'
    )

    args = parser.parse_args()

    # Handle verbose/quiet modes
    verbose = args.verbose if not args.quiet else False

    # Handle include_images: --no-images takes precedence
    include_images = not args.no_images if args.no_images else args.include_images

    # Handle download_images: --no-download-images takes precedence
    download_images = not args.no_download_images if args.no_download_images else args.download_images

    # Create extractor
    extractor = BlogExtractor(
        urls_file=args.urls,
        output_dir=args.output,
        verbose=verbose,
        relative_links=args.relative_links,
        include_images=include_images,
        download_images=download_images
    )

    # Load URLs
    urls = extractor.load_urls()

    if not urls:
        extractor._log("warning", "No URLs to process")
        return 1

    extractor._log("info", "=== Blog Post Extractor ===")
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
        if not args.quiet:
            # Rich progress for concurrent mode
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("({task.completed}/{task.total})"),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"[cyan]Processing {args.concurrent} URLs concurrently...", total=len(urls))

                # Create progress callback to update the bar in real-time
                def update_progress(result: dict):
                    nonlocal success_count, duplicate_count

                    if result.get('status') == 'success':
                        success_count += 1
                        title = result.get('title', 'Unknown')[:40]
                        progress.update(task, description=f"[green]✓ {title}...")
                    elif result.get('status') == 'duplicate':
                        duplicate_count += 1
                        progress.update(task, description="[yellow]↺ Duplicate skipped")
                    else:
                        progress.update(task, description=f"[red]✗ Failed")

                    # Advance the progress bar
                    progress.advance(task)

                # Run concurrent extraction with progress callback
                results = asyncio.run(extractor.process_urls_concurrently(urls, args.concurrent, progress_callback=update_progress))

                # Update as complete
                progress.update(task, description=f"[green]✓ Completed! {success_count} successful, {duplicate_count} duplicates")
        else:
            # Quiet mode - no progress bar
            results = asyncio.run(extractor.process_urls_concurrently(urls, args.concurrent))
            for result in results:
                if result.get('status') == 'success':
                    success_count += 1
                elif result.get('status') == 'duplicate':
                    duplicate_count += 1

    # Process URLs with rich progress bar (sequential)
    elif not args.quiet:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Extracting blog posts...", total=len(urls))

            for i, url in enumerate(urls, 1):
                data = extractor.extract_blog_data(url)

                if data['status'] == 'success':
                    platform = data.get('platform', 'unknown')
                    title = data['title'][:40] + "..." if len(data['title']) > 40 else data['title']
                    progress.update(task, description=f"[cyan][OK] {platform}: {title}")
                    success_count += 1
                elif data['status'] == 'duplicate':
                    duplicate_count += 1
                    progress.update(task, description="[yellow][SKIP] Duplicate skipped")

                # Update progress
                progress.advance(task)

                # Delay between requests
                if i < len(urls):
                    time.sleep(args.delay)
    else:
        # No tqdm - verbose output
        for i, url in enumerate(urls, 1):
            extractor._log("info", f"\n[{i}/{len(urls)}] Processing...")
            data = extractor.extract_blog_data(url)

            if data['status'] == 'success':
                extractor._log("info", f"[OK] Success: {data['title']}")
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
                extractor._log("warning", f"[SKIP] Duplicate: {data['title']}")
                duplicate_count += 1
            else:
                extractor._log("error", f"[FAIL] Failed - {data.get('error', 'Unknown error')}")

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

    # Summary with rich table
    if not args.quiet:
        failed_count = len(urls) - success_count - duplicate_count
        success_rate = (success_count / len(urls) * 100) if len(urls) > 0 else 0

        table = Table(title="Extraction Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Count", justify="right", style="green")

        table.add_row("Total URLs", str(len(urls)))
        table.add_row("[OK] Successful", f"[green]{success_count}[/green]")
        table.add_row("[SKIP] Duplicates", f"[yellow]{duplicate_count}[/yellow]")
        table.add_row("[FAIL] Failed", f"[red]{failed_count}[/red]")
        table.add_row("Success Rate", f"[bold]{success_rate:.1f}%[/bold]")

        if download_images and extractor.downloaded_images:
            table.add_row("Images Downloaded", f"[blue]{len(extractor.downloaded_images)}[/blue]")

        console.print("\n")
        console.print(table)
    else:
        # Quiet mode - simple text summary
        extractor._log("info", "\n=== Summary ===")
        extractor._log("info", f"Total URLs: {len(urls)}")
        extractor._log("info", f"Successful: {success_count}")
        extractor._log("info", f"Duplicates: {duplicate_count}")
        extractor._log("info", f"Failed: {len(urls) - success_count - duplicate_count}")
        if len(urls) > 0:
            extractor._log("info", f"Success rate: {success_count/len(urls)*100:.1f}%")

        if download_images and extractor.downloaded_images:
            extractor._log("info", f"Images downloaded: {len(extractor.downloaded_images)} to {extractor.images_dir}")

    return 0 if success_count == len(urls) else 1


if __name__ == "__main__":
    sys.exit(main())
