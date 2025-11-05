#!/usr/bin/env python3
"""
Streamlit Web Interface for Blog Extractor Tool
Provides a user-friendly web interface for extracting blog posts and converting to WordPress XML.
"""

# Setup Windows environment before any other imports
import sys
if sys.platform.startswith('win'):
    import asyncio
    import warnings
    # Python 3.14+: Explicitly create ProactorEventLoop (supports subprocesses) before Streamlit imports
    # This is the modern approach - direct class instantiation instead of deprecated Policy API
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)
    # Suppress Playwright subprocess cleanup warnings on Windows
    warnings.filterwarnings("ignore", category=ResourceWarning)

# Standard library imports
import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse

# Third-party imports
import streamlit as st

# Local imports
from blog_extractor import BlogExtractor

# Install Playwright browsers on Streamlit Cloud (runs once on first startup)
# This is required because Streamlit Cloud doesn't have browsers pre-installed
import os
import subprocess
from pathlib import Path

def install_playwright_browsers():
    """Install Playwright browsers if not already installed (for Streamlit Cloud deployment)."""
    # Check if running on Streamlit Cloud (Linux environment)
    if sys.platform.startswith('linux'):
        # Check if chromium browser is already installed
        playwright_cache = Path.home() / '.cache' / 'ms-playwright'
        chromium_path = playwright_cache / 'chromium-1187' / 'chrome-linux' / 'chrome'

        if not chromium_path.exists():
            try:
                print("Installing Playwright browsers for Streamlit Cloud...")
                subprocess.run(['playwright', 'install', 'chromium'], check=True, capture_output=True)
                print("Playwright browsers installed successfully!")
            except subprocess.CalledProcessError as e:
                print(f"Warning: Failed to install Playwright browsers: {e}")
                print("App will fall back to requests library for extraction.")
            except FileNotFoundError:
                print("Warning: playwright command not found. Falling back to requests library.")

# Run browser installation check on app startup
install_playwright_browsers()

# Configure logging (after imports)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Page configuration
st.set_page_config(
    page_title="Blog Extractor Tool",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide anchor links from headers
st.markdown("""
<style>
    /* Hide anchor links from headers */
    .stMarkdown h1 a,
    .stMarkdown h2 a,
    .stMarkdown h3 a,
    .stMarkdown h4 a {
        display: none !important;
    }

    /* Better spacing for the app */
    .block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

def setup_session_state():
    """Initialize session state variables"""
    if 'extraction_results' not in st.session_state:
        st.session_state.extraction_results = []
    if 'is_processing' not in st.session_state:
        st.session_state.is_processing = False
    if 'extraction_complete' not in st.session_state:
        st.session_state.extraction_complete = False
    if 'error_log' not in st.session_state:
        st.session_state.error_log = []
    if 'duplicate_log' not in st.session_state:
        st.session_state.duplicate_log = []
    if 'xml_content' not in st.session_state:
        st.session_state.xml_content = None
    if 'links_content' not in st.session_state:
        st.session_state.links_content = None
    if 'link_analysis' not in st.session_state:
        st.session_state.link_analysis = None
    if 'replacements' not in st.session_state:
        st.session_state.replacements = []

def display_header():
    """Display the main header and instructions"""
    st.title("📰 Blog Extractor Tool")
    st.markdown("**Convert blog posts to WordPress XML format with comprehensive link extraction**")

    st.info("💡 **Quick Start:** 1) Paste URLs → 2) Click Extract → 3) Download XML | ⚡ Concurrent processing enabled by default!")

    with st.expander("📋 How to Use This Tool", expanded=False):
        st.markdown("""
        ### Instructions:
        1. **Paste URLs**: Copy and paste your blog URLs into Step 1 (one per line)
        2. **Click Extract**: Hit the big blue "EXTRACT BLOG POSTS NOW" button
        3. **Download**: Scroll down to get your WordPress XML file

        ### Optional:
        - Expand Step 2 to adjust concurrent processing (default: 5 workers)

        ### What This Tool Does:
        - ✅ Extracts blog content from any website (Wix, WordPress, Medium, etc.)
        - ✅ Gets titles, content, authors, dates, categories, and tags
        - ✅ Finds all links within blog posts
        - ✅ Creates WordPress XML file for easy import
        - ✅ Works with JavaScript-heavy sites
        - ✅ Concurrent processing enabled by default (3-5x faster!)
        """)

def validate_urls(urls: List[str]) -> List[str]:
    """Validate and clean URL list"""
    valid_urls = []
    for url in urls:
        url = url.strip()
        if url and (url.startswith('http://') or url.startswith('https://')):
            valid_urls.append(url)
    return valid_urls

def analyze_links(extraction_results: List[Dict]) -> Dict[str, Any]:
    """Analyze all extracted links and categorize them with anchor text"""
    source_domains = set()
    internal_links: Dict[str, Dict[str, Any]] = {}  # {url: {'count': N, 'texts': [anchor texts], 'sources': [blog post URLs]}}
    external_links: Dict[str, Dict[str, Any]] = {}

    # Collect source domains
    for result in extraction_results:
        if 'url' in result:
            source_domains.add(urlparse(result['url']).netloc)

    # Analyze each link
    for result in extraction_results:
        post_url = result.get('url', 'Unknown')
        for link in result.get('links', []):
            url = link['url']
            text = link.get('text', 'No text')

            # Skip anchor-only links (#section)
            if url.startswith('#'):
                continue

            # Categorize as internal or external
            link_domain = urlparse(url).netloc
            is_internal = link_domain in source_domains

            target_dict = internal_links if is_internal else external_links

            if url not in target_dict:
                target_dict[url] = {
                    'count': 0,
                    'texts': set(),
                    'sources': set()
                }

            target_dict[url]['count'] += 1
            target_dict[url]['texts'].add(text)
            target_dict[url]['sources'].add(post_url)

    # Convert sets to lists for serialization
    for link_dict in [internal_links, external_links]:
        for url in link_dict:
            link_dict[url]['texts'] = list(link_dict[url]['texts'])
            link_dict[url]['sources'] = list(link_dict[url]['sources'])

    return {
        'internal': internal_links,
        'external': external_links,
        'source_domains': list(source_domains)
    }

def get_url_inputs():
    """Simple URL input without extract button"""
    st.markdown("### 📝 Step 1: Enter Your Blog URLs")
    st.caption("Paste your blog URLs below (one per line)")

    # Text area for URL input
    url_text = st.text_area(
        "Blog URLs:",
        height=250,
        placeholder="https://example.com/blog/post1\nhttps://example.com/blog/post2\nhttps://example.com/blog/post3",
        label_visibility="collapsed"
    )

    # Parse and validate URLs
    urls = []
    if url_text:
        urls = [url.strip() for url in url_text.strip().split('\n') if url.strip()]

    valid_urls = validate_urls(urls)

    # Show URL count
    if valid_urls:
        st.success(f"✅ {len(valid_urls)} valid URL{'s' if len(valid_urls) != 1 else ''} ready to extract")
    else:
        st.info("👆 Paste your blog URLs above to get started")

    return valid_urls


def get_concurrent_settings() -> tuple[int, bool, bool, bool, bool]:
    """Get concurrent processing settings - concurrent is default for best performance"""
    st.markdown("### ⚙️ Step 2: Configuration Options")
    st.caption("Configure how your blog posts will be extracted and processed")

    with st.expander("⚡ Performance Settings", expanded=False):
        max_concurrent = st.slider(
            "Concurrent requests:",
            min_value=1,
            max_value=10,
            value=5,
            help="1 = Sequential (slower), 5 = Recommended (3-5x faster), 10 = Maximum (may overwhelm server)"
        )

        if max_concurrent == 1:
            st.info("🐢 Sequential processing (one URL at a time)")
        else:
            st.info(f"💨 Processing {max_concurrent} URLs simultaneously (3-5x faster!)")

    with st.expander("🔧 Content Options", expanded=True):
        # Link handling option
        relative_links = st.checkbox(
            "Use relative links in XML output",
            value=False,
            help="Keep internal links relative for easier domain migration (useful when moving to a new domain)"
        )

        if relative_links:
            st.info("🔗 Internal links will be relative (e.g., /page instead of https://example.com/page)")
        else:
            st.info("🔗 All links will be absolute URLs (preserves exact source URLs)")

        st.markdown("---")

        # Image extraction option
        include_images = st.checkbox(
            "Include images in exported content",
            value=True,
            help="Extracts images from blog posts and includes them in the WordPress XML."
        )

        if include_images:
            st.info("🖼️ Images will be included in the export")
        else:
            st.info("🚫 Images will be excluded from exported content")

        # Image download option (only show if images are included)
        download_images = False
        if include_images:
            download_images = st.checkbox(
                "Download images locally (RECOMMENDED)",
                value=True,
                help="Downloads images to output/images/ folder. This protects you if source images are removed and gives you full control over hosting."
            )

            if download_images:
                st.success("💾 Images will be downloaded locally to output/images/ - you're protected if source images go offline!")
            else:
                st.warning("⚠️ Using external image URLs (not recommended) - images may break if source site removes them")

        st.markdown("---")

        # Duplicate handling option
        skip_duplicates = st.checkbox(
            "Skip duplicate content (recommended)",
            value=True,
            help="Automatically skip blog posts with identical content. Uncheck this if you need duplicates in the XML for find/replace operations."
        )

        if skip_duplicates:
            st.info("✅ Duplicate posts will be detected and skipped")
        else:
            st.warning("⚠️ Duplicates will be included - useful for find/replace but may create duplicate posts in WordPress")

    return max_concurrent, relative_links, include_images, skip_duplicates, download_images

def display_find_replace():
    """General-purpose find/replace interface for XML modification"""
    # Only show if extraction is complete
    if not st.session_state.extraction_complete:
        return

    st.markdown("### 🔄 Find & Replace in XML")
    st.write("Search and replace any text in the XML before downloading (works on entire file: URLs, domains, text, etc.)")

    # Initialize replacements in session state
    if 'replacements' not in st.session_state:
        st.session_state.replacements = []

    # Simple two-field form
    col1, col2 = st.columns(2)
    with col1:
        find_text = st.text_input("Find:", placeholder="blog.oldsite.com")
    with col2:
        replace_text = st.text_input("Replace with:", placeholder="newsite.com/blog")

    if find_text and replace_text:
        if st.button("Add Replacement"):
            st.session_state.replacements.append((find_text, replace_text))
            st.success(f"✅ Will replace '{find_text}' with '{replace_text}'")
            st.rerun()

    # Show active replacements
    if st.session_state.replacements:
        st.write("**Active replacements:**")
        for i, (find, replace) in enumerate(st.session_state.replacements):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"• {find} → {replace}")
            with col2:
                if st.button("❌", key=f"remove_{i}"):
                    st.session_state.replacements.pop(i)
                    st.rerun()

        if st.button("Clear All Replacements"):
            st.session_state.replacements = []
            st.rerun()

def apply_replacements(xml_content: str) -> str:
    """Apply all replacements to XML content"""
    if not st.session_state.get('replacements'):
        return xml_content

    modified_content = xml_content
    for find_text, replace_text in st.session_state.replacements:
        modified_content = modified_content.replace(find_text, replace_text)

    return modified_content

def process_urls(urls: List[str], max_concurrent: int = 1, relative_links: bool = False, include_images: bool = True, skip_duplicates: bool = True, download_images: bool = True):
    """Process URLs with progress tracking (supports async concurrent mode)"""
    if not urls:
        st.error("❌ No valid URLs to process")
        return

    # Initialize clean progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Simple progress counter with time tracking
    counters = {
        'total': len(urls),
        'completed': 0,
        'start_time': time.time()
    }

    def update_progress():
        """Update progress bar and status message with estimated time remaining"""
        if counters['completed'] == 0:
            status_text.info(f"⏳ **Starting...** Processing {counters['total']} URLs")
            return

        progress = counters['completed'] / counters['total']
        progress_bar.progress(progress)
        percent = int(progress * 100)

        # Calculate estimated time remaining
        elapsed = time.time() - counters['start_time']
        avg_time_per_url = elapsed / counters['completed']
        remaining_urls = counters['total'] - counters['completed']
        estimated_remaining = avg_time_per_url * remaining_urls

        # Format time remaining
        if estimated_remaining < 60:
            time_str = f"~{int(estimated_remaining)}s remaining"
        else:
            mins = int(estimated_remaining / 60)
            time_str = f"~{mins}m remaining"

        status_text.info(f"⏳ **Processing:** {counters['completed']} of {counters['total']} ({percent}%) • {time_str}")


    log_container = st.empty()
    current_url_text = st.empty()

    # Create callback for logging
    def logging_callback(level: str, message: str):
        """Clean callback - hides technical details, shows only essential user-friendly messages"""

        # Update progress on completion events
        if 'Success:' in message or '[OK]' in message or 'Duplicate content' in message or '[SKIP]' in message or '[FAIL]' in message:
            counters['completed'] += 1
            update_progress()

        # Show current URL being processed
        if 'Processing:' in message:
            url = message.replace('Processing:', '').strip()
            current_url_text.info(f"🔄 Currently processing: {url}")
            return  # Don't show "Processing" in log

        # Hide technical errors and verbose details
        hide_messages = [
            "Fetching with", "attempt", "Retrying", "Scrolling to load",
            "Detected platform", "Platform:", "URL:", "Date:", "Author:",
            "Content:", "Links:", "Categories:", "Tags:", "All",
            "Selector wait failed", "Timeout", "Page.wait_for", "Call log",
            "waiting for locator", "locator(", "to be visible"
        ]

        if any(phrase in message for phrase in hide_messages):
            return  # Hide technical details from users

        # Show only essential user-friendly messages
        with log_container.container():
            if 'Success:' in message or '[OK]' in message:
                # Show successful extraction
                title = message.replace('✓ Success: ', '').replace('[OK]', '').strip()
                st.success(f"✅ {title}")
            elif '[FAIL]' in message:
                # Show user-friendly failure message
                st.error(f"❌ {message.replace('[FAIL]', '').strip()}")
            elif 'Duplicate content' in message or '[SKIP]' in message:
                st.info(f"⏭️ {message}")
            elif 'Parsed date:' in message:
                st.info(f"ℹ️ {message}")
            # Hide all other technical messages

    # Initialize extractor with callback
    extractor = BlogExtractor(
        callback=logging_callback,
        verbose=False,
        relative_links=relative_links,
        include_images=include_images,
        skip_duplicates=skip_duplicates,
        download_images=download_images
    )

    # Reset session state
    st.session_state.extraction_results = []
    st.session_state.error_log = []
    st.session_state.duplicate_log = []

    # Show initial status
    update_progress()

    if max_concurrent > 1:

        # Run async processing
        results = asyncio.run(extractor.process_urls_concurrently(urls, max_concurrent))

        # Process results
        for i, result in enumerate(results):
            progress = (i + 1) / len(results)
            progress_bar.progress(progress)

            if result and result.get('status') == 'success':
                st.session_state.extraction_results.append(result)

            elif result and result.get('status') == 'duplicate':
                st.session_state.duplicate_log.append({
                    'url': result.get('url', ''),
                    'title': result.get('title', 'Unknown')
                })

            else:
                st.session_state.error_log.append({
                    'url': result.get('url', ''),
                    'error': result.get('error', 'Unknown error')
                })

        elapsed = time.time() - counters['start_time']
        # Calculate actual results from session state
        successful = len(st.session_state.extraction_results)
        duplicates = len(st.session_state.duplicate_log)
        failed = len(st.session_state.error_log)
        success_rate = (successful / counters['total'] * 100) if counters['total'] > 0 else 0

        status_text.success(f"✅ **Complete!** {successful} extracted, {duplicates} duplicates, {failed} failed ({elapsed:.1f}s)")
        progress_bar.progress(1.0)
        current_url_text.empty()  # Clear current URL display

    # Sequential processing (original behavior)
    else:
        for i, url in enumerate(urls):
            # Update progress
            progress = (i + 1) / len(urls)
            progress_bar.progress(progress, text=f"Processing {i + 1}/{len(urls)} URLs")
            status_text.text(f"🔄 Processing: {url}")

            try:
                # Extract blog data
                result = extractor.extract_blog_data(url)

                if result and result.get('status') == 'success':
                    st.session_state.extraction_results.append(result)

                elif result and result.get('status') == 'duplicate':
                    st.session_state.duplicate_log.append({
                        'url': url,
                        'title': result.get('title', 'Unknown')
                    })

                else:
                    st.session_state.error_log.append({
                        'url': url,
                        'error': result.get('error', 'No content extracted')
                    })

            except Exception as e:
                st.session_state.error_log.append({
                    'url': url,
                    'error': str(e)
                })

            # Add small delay to make progress visible
            time.sleep(0.5)

        # Processing complete
        elapsed_time = time.time() - counters['start_time']
        successful = len(st.session_state.extraction_results)
        duplicates = len(st.session_state.duplicate_log)
        failed = len(st.session_state.error_log)

        progress_bar.progress(1.0)
        status_text.success(f"✅ **Complete!** {successful} extracted, {duplicates} duplicates, {failed} failed ({elapsed_time:.1f}s)")
        current_url_text.empty()  # Clear current URL display

    # Update session state
    st.session_state.is_processing = False
    st.session_state.extraction_complete = True

    # Analyze links for internal/external categorization
    if st.session_state.extraction_results:
        link_analysis = analyze_links(st.session_state.extraction_results)
        st.session_state.link_analysis = link_analysis

    # Generate output files
    generate_output_files(extractor)

def generate_output_files(extractor: BlogExtractor):
    """Generate WordPress XML and links content - no files created"""
    try:
        # Set extracted data in extractor
        extractor.extracted_data = st.session_state.extraction_results

        # Generate XML content
        st.session_state.xml_content = extractor.get_xml_content()

        # Generate links content
        st.session_state.links_content = extractor.get_links_content()

    except Exception as e:
        st.error(f"❌ Error generating output content: {e}")

def display_results():
    """Display extraction results and statistics"""
    if not st.session_state.extraction_complete:
        return

    st.markdown("### 📊 Extraction Results")

    # Statistics (simplified to 4 metrics)
    success_count = len(st.session_state.extraction_results)
    duplicate_count = len(st.session_state.duplicate_log)
    failed_count = len(st.session_state.error_log)
    total_urls = success_count + duplicate_count + failed_count
    success_rate = (success_count / total_urls * 100) if total_urls > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total URLs", total_urls)
    with col2:
        st.metric("Successful", success_count)
    with col3:
        st.metric("Failed", failed_count)
    with col4:
        st.metric("Success Rate", f"{success_rate:.1f}%")

    # Compact expandable post cards
    if st.session_state.extraction_results:
        st.subheader("✅ Successfully Extracted Posts")

        for idx, result in enumerate(st.session_state.extraction_results, 1):
            title = result.get('title', 'N/A')
            url = result.get('url', '')

            # Compact summary line for collapsed view
            summary_parts = []

            # Categories
            if result.get('categories'):
                cats = result['categories'][:2]
                summary_parts.append(f"📁 {', '.join(cats)}" + (f" +{len(result['categories'])-2}" if len(result['categories']) > 2 else ""))
            else:
                summary_parts.append("📁 No categories")

            # Tags
            if result.get('tags'):
                tags = result['tags'][:2]
                summary_parts.append(f"🏷️ {', '.join(tags)}" + (f" +{len(result['tags'])-2}" if len(result['tags']) > 2 else ""))

            # Links
            link_count = len(result.get('links', []))
            if link_count > 0:
                summary_parts.append(f"🔗 {link_count} link{'s' if link_count != 1 else ''}")
            else:
                summary_parts.append("🔗 No links")

            summary_text = " • ".join(summary_parts)

            # Expandable card for each post
            with st.expander(f"**[{title}]({url})** • {summary_text}", expanded=False):
                # Full details when expanded
                col1, col2 = st.columns([3, 1])

                with col1:
                    # Metadata
                    metadata = []
                    if result.get('author'):
                        metadata.append(f"👤 {result['author']}")
                    if result.get('date'):
                        metadata.append(f"📅 {result['date']}")
                    if result.get('platform'):
                        metadata.append(f"🌐 {result['platform'].title()}")
                    if result.get('content_length'):
                        metadata.append(f"📝 {result['content_length']:,} chars")

                    if metadata:
                        st.caption(" • ".join(metadata))

                    # Categories (full list)
                    if result.get('categories'):
                        st.markdown(f"**📁 Categories:** {', '.join(result['categories'])}")
                    else:
                        st.markdown("**📁 Categories:** *No categories*")

                    # Tags (full list)
                    if result.get('tags'):
                        st.markdown(f"**🏷️ Tags:** {', '.join(result['tags'])}")
                    else:
                        st.markdown("**🏷️ Tags:** *No tags*")

                with col2:
                    st.metric("Content", f"{result.get('content_length', 0):,}")
                    st.metric("Links", link_count)

                # Show all links in this post with anchor text
                if result.get('links'):
                    st.markdown(f"**🔗 Links in this post ({link_count}):**")
                    for link in result['links'][:20]:  # Show first 20 links
                        link_text = link.get('text', 'No text')
                        link_url = link.get('url', '')
                        st.caption(f"• {link_text} → {link_url}")

                    if len(result['links']) > 20:
                        st.caption(f"... and {len(result['links']) - 20} more links")

    # Duplicate log
    if st.session_state.duplicate_log:
        st.subheader("⊘ Duplicate Content")
        with st.expander(f"View {len(st.session_state.duplicate_log)} duplicates"):
            for dup in st.session_state.duplicate_log:
                st.markdown(f"**[{dup['title']}]({dup['url']})**")
                st.caption("Skipped as duplicate content")
                st.markdown("---")

    # Error log
    if st.session_state.error_log:
        st.subheader("❌ Failed URLs")
        with st.expander(f"View {len(st.session_state.error_log)} failed URLs"):
            for error in st.session_state.error_log:
                st.markdown(f"**[{error['url']}]({error['url']})**")
                st.error(f"Error: {error['error']}")
                st.markdown("---")

def provide_downloads():
    """Provide download buttons for WordPress XML and links"""
    if not st.session_state.extraction_complete:
        return

    st.markdown("### 💾 Download Results")

    # Check if we have content
    if not st.session_state.get('xml_content'):
        st.info("No content generated yet. Please run the extraction first.")
        return

    # Single centered download button for WordPress XML
    final_xml = apply_replacements(st.session_state.xml_content)
    label = "📄 Download WordPress XML"
    if st.session_state.get('replacements'):
        label += " (with modifications)"

    st.download_button(
        label=label,
        data=final_xml,
        file_name=f"blog_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml",
        mime="application/xml",
        help="WordPress XML file ready for import - contains all posts, categories, tags, and links",
        use_container_width=True
    )

    st.caption("💡 All links are included in the XML file and visible in the Extraction Results section above")


def main():
    """Main application function"""
    # Initialize session state
    setup_session_state()

    # Display header
    display_header()

    # Get URLs
    urls = get_url_inputs()

    # Get concurrent settings
    max_concurrent, relative_links, include_images, skip_duplicates, download_images = get_concurrent_settings()

    # Step 3: Extract button (after configuration)
    st.markdown("### 🚀 Step 3: Start Extraction")
    st.caption("Click the button below to begin extracting your blog posts")

    start_extraction = st.button(
        "🚀 EXTRACT BLOG POSTS NOW",
        type="primary",
        use_container_width=True,
        disabled=len(urls) == 0 or st.session_state.is_processing,
        help="Start extracting all blog posts with your configured settings"
    )

    if len(urls) == 0:
        st.info("👆 Enter some URLs in Step 1 to enable extraction")

    # Start extraction if button was clicked
    if start_extraction and urls and not st.session_state.is_processing:
        st.session_state.is_processing = True
        st.session_state.extraction_complete = False

        st.markdown("---")
        st.markdown("### 🔄 Extracting Blog Posts...")

        with st.spinner("Processing your blog posts..."):
            process_urls(urls, max_concurrent, relative_links, include_images, skip_duplicates, download_images)
    elif st.session_state.is_processing:
        st.warning("⏳ Extraction in progress...")

    # Display results
    display_results()

    # Display find/replace interface (for modifying links before export)
    display_find_replace()

    # Provide downloads
    provide_downloads()

if __name__ == "__main__":
    main()
