#!/usr/bin/env python3
"""
Streamlit Web Interface for Blog Extractor Tool
Provides a user-friendly web interface for extracting blog posts and converting to WordPress XML.
"""

import streamlit as st
import time
import asyncio
from typing import List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse
from collections import Counter

# Import our blog extractor
from blog_extractor import BlogExtractor

# Page configuration
st.set_page_config(
    page_title="Blog Extractor Tool",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

    st.info("💡 **Quick Start:** Paste your blog URLs below → Click 'Extract Blog Posts Now' → Download your WordPress XML")

    with st.expander("📋 How to Use This Tool", expanded=False):
        st.markdown("""
        ### Instructions:
        1. **Paste URLs**: Copy and paste your blog URLs into the text box (one per line)
        2. **Click Extract**: Hit the big blue "Extract Blog Posts Now" button
        3. **Download**: Get your WordPress XML file from the download section that appears

        ### What This Tool Does:
        - ✅ Extracts blog content from any website (Wix, WordPress, Medium, etc.)
        - ✅ Gets titles, content, authors, dates, categories, and tags
        - ✅ Finds all links within blog posts
        - ✅ Creates WordPress XML file for easy import
        - ✅ Works with JavaScript-heavy sites
        - ✅ Supports concurrent processing (3-5x faster!)
        """)

def get_sample_urls() -> List[str]:
    """Return sample URLs for testing"""
    return [
        "https://www.blog.kirkbrotherschevroletofvicksburg.com/2024/09/19/2024-chevy-silverado-hd-trucks/",
        "https://www.blog.kirkbrotherschevroletofvicksburg.com/2024/09/18/2024-chevy-colorado-zr2/",
        "https://www.blog.kirkbrotherschevroletofvicksburg.com/2024/09/17/2024-chevy-trailblazer/",
    ]

def validate_urls(urls: List[str]) -> List[str]:
    """Validate and clean URL list"""
    valid_urls = []
    for url in urls:
        url = url.strip()
        if url and (url.startswith('http://') or url.startswith('https://')):
            valid_urls.append(url)
    return valid_urls

def analyze_links(extraction_results: List[Dict]) -> Dict[str, Any]:
    """Analyze all extracted links and categorize them"""
    all_links = []
    source_domains = set()

    # Collect all links and source domains
    for result in extraction_results:
        if 'url' in result:
            source_domains.add(urlparse(result['url']).netloc)
        for link in result.get('links', []):
            all_links.append(link['url'])

    # Count unique links
    link_counts = Counter(all_links)

    # Categorize as internal or external
    internal_links = {}
    external_links = {}

    for link, count in link_counts.items():
        link_domain = urlparse(link).netloc
        if link_domain in source_domains:
            internal_links[link] = count
        else:
            external_links[link] = count

    return {
        'internal': internal_links,
        'external': external_links,
        'source_domains': list(source_domains)
    }

def get_url_inputs() -> List[str]:
    """Simple URL input"""
    st.header("📝 Enter Your Blog URLs")

    # Simple text area - that's it
    url_text = st.text_area(
        "Paste your blog URLs here (one per line):",
        height=200,
        placeholder="https://example.com/blog/post1\nhttps://example.com/blog/post2\nhttps://example.com/blog/post3"
    )

    urls = []
    if url_text:
        urls = [url.strip() for url in url_text.strip().split('\n') if url.strip()]

    # Validate URLs
    valid_urls = validate_urls(urls)

    if valid_urls:
        st.success(f"✅ {len(valid_urls)} URLs ready to extract")

    return valid_urls


def get_concurrent_settings() -> int:
    """Get concurrent processing settings"""
    st.header("⚡ Performance")

    enable_concurrent = st.checkbox(
        "Enable concurrent processing (3-5x faster!)",
        value=False,
        help="Process multiple URLs simultaneously for major speed boost"
    )

    if enable_concurrent:
        max_concurrent = st.slider(
            "Max concurrent requests:",
            min_value=2,
            max_value=10,
            value=5,
            help="Higher = faster, but may overwhelm the server. 5 is recommended."
        )
        st.info(f"💨 Will process {max_concurrent} URLs simultaneously")
        return max_concurrent
    else:
        st.info("🐢 Sequential processing (one URL at a time)")
        return 1

def display_link_analysis():
    """Display unique internal links with counts"""
    if not st.session_state.get('link_analysis'):
        return

    analysis = st.session_state.link_analysis
    internal = analysis.get('internal', {})

    if internal:
        with st.expander(f"📊 Internal Links Found ({len(internal)} unique)"):
            st.write("These links point to the same domain as your blog posts:")

            # Sort by count descending
            sorted_links = sorted(internal.items(), key=lambda x: x[1], reverse=True)

            # Display as simple table
            for link, count in sorted_links[:20]:  # Show top 20
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.text(link[:80] + ('...' if len(link) > 80 else ''))
                with col2:
                    st.text(f"×{count}")

            if len(sorted_links) > 20:
                st.write(f"... and {len(sorted_links) - 20} more")

def display_find_replace():
    """Simple find/replace interface for link modification"""
    if not st.session_state.get('link_analysis'):
        return

    internal = st.session_state.link_analysis.get('internal', {})
    if not internal:
        return

    st.header("🔄 Fix Internal Links")
    st.write("Change domain names before downloading (useful when migrating blogs)")

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

def process_urls(urls: List[str], max_concurrent: int = 1):
    """Process URLs with progress tracking (supports async concurrent mode)"""
    if not urls:
        st.error("❌ No valid URLs to process")
        return

    # Initialize progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.empty()
    log_container = st.empty()

    # Create callback for logging
    def logging_callback(level: str, message: str):
        """Callback to display logs in Streamlit - filters verbose messages"""
        # Filter out verbose internal messages for cleaner UI
        skip_phrases = [
            "Fetching with",
            "attempt",
            "Retrying in",
            "Detected platform",
            "Platform:",
            "All",
            "failed",
        ]

        # Skip verbose messages unless it's an error
        if level != 'error' and any(phrase in message for phrase in skip_phrases):
            return

        with log_container.container():
            if level == 'error':
                st.error(f"🔴 {message}")
            elif level == 'warning':
                st.warning(f"⚠️ {message}")
            else:
                st.info(f"ℹ️ {message}")

    # Initialize extractor with callback
    extractor = BlogExtractor(callback=logging_callback, verbose=False)

    # Reset session state
    st.session_state.extraction_results = []
    st.session_state.error_log = []
    st.session_state.duplicate_log = []

    start_time = time.time()

    # Use concurrent processing if enabled
    if max_concurrent > 1:
        status_text.text(f"⚡ Processing {len(urls)} URLs with {max_concurrent} concurrent requests...")

        # Run async processing
        results = asyncio.run(extractor.process_urls_concurrently(urls, max_concurrent))

        # Process results
        for i, result in enumerate(results):
            progress = (i + 1) / len(results)
            progress_bar.progress(progress)

            if result and result.get('status') == 'success':
                st.session_state.extraction_results.append(result)
                with results_container.container():
                    title = result.get('title', 'No title')[:60] + ('...' if len(result.get('title', '')) > 60 else '')
                    st.success(f"✅ **{title}**")

            elif result and result.get('status') == 'duplicate':
                st.session_state.duplicate_log.append({
                    'url': result.get('url', ''),
                    'title': result.get('title', 'Unknown')
                })
                with results_container.container():
                    st.warning(f"⊘ Duplicate: {result.get('title', 'Unknown')}")

            else:
                st.session_state.error_log.append({
                    'url': result.get('url', ''),
                    'error': result.get('error', 'Unknown error')
                })
                with results_container.container():
                    st.error(f"❌ Failed: {result.get('error', 'Unknown error')}")

        elapsed = time.time() - start_time
        status_text.text(f"✅ Completed in {elapsed:.1f} seconds!")
        progress_bar.progress(1.0)

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

                    # Display detailed success info
                    title = result.get('title', 'No title')[:60] + ('...' if len(result.get('title', '')) > 60 else '')
                    content_length = len(result.get('content', ''))
                    links_count = len(result.get('links', []))
                    categories = ', '.join(result.get('categories', []))

                    success_msg = f"✅ **{title}**"
                    details = f"Content: {content_length:,} chars | Links: {links_count} | Categories: {categories or 'None'}"

                    with results_container.container():
                        st.success(success_msg)
                        st.text(f"   {details}")
                        st.text(f"   URL: {url}")
                        st.write("---")

                elif result and result.get('status') == 'duplicate':
                    st.session_state.duplicate_log.append({
                        'url': url,
                        'title': result.get('title', 'Unknown')
                    })
                    with results_container.container():
                        st.warning(f"⊘ Duplicate: {result.get('title', 'Unknown')}")
                        st.text(f"   URL: {url}")
                        st.write("---")

                else:
                    st.session_state.error_log.append({
                        'url': url,
                        'error': result.get('error', 'No content extracted')
                    })
                    with results_container.container():
                        st.error(f"❌ Failed - {result.get('error', 'No content extracted')}")
                        st.text(f"   URL: {url}")
                        st.write("---")

            except Exception as e:
                st.session_state.error_log.append({
                    'url': url,
                    'error': str(e)
                })
                with results_container.container():
                    st.error(f"❌ Failed - {str(e)}")
                    st.text(f"   URL: {url}")
                    st.write("---")

            # Add small delay to make progress visible
            time.sleep(0.5)

        # Processing complete
        elapsed_time = time.time() - start_time
        progress_bar.progress(1.0)
        status_text.text(f"✅ Processing complete! ({elapsed_time:.1f} seconds)")

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

    st.header("📊 Extraction Results")

    # Statistics
    success_count = len(st.session_state.extraction_results)
    duplicate_count = len(st.session_state.duplicate_log)
    failed_count = len(st.session_state.error_log)
    total_urls = success_count + duplicate_count + failed_count
    success_rate = (success_count / total_urls * 100) if total_urls > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total URLs", total_urls)
    with col2:
        st.metric("Successful", success_count)
    with col3:
        st.metric("Duplicates", duplicate_count)
    with col4:
        st.metric("Failed", failed_count)
    with col5:
        st.metric("Success Rate", f"{success_rate:.1f}%")

    # Results table
    if st.session_state.extraction_results:
        st.subheader("✅ Successfully Extracted Posts")

        results_data = []
        for result in st.session_state.extraction_results:
            results_data.append({
                'Title': result.get('title', 'N/A')[:60] + ('...' if len(result.get('title', '')) > 60 else ''),
                'Author': result.get('author', 'N/A'),
                'Date': result.get('date', 'N/A'),
                'Categories': ', '.join(result.get('categories', [])),
                'Tags': ', '.join(result.get('tags', [])),
                'Content Length': f"{len(result.get('content', ''))} chars",
                'Links Found': len(result.get('links', []))
            })

        st.dataframe(results_data, use_container_width=True)

    # Duplicate log
    if st.session_state.duplicate_log:
        st.subheader("⊘ Duplicate Content")
        with st.expander(f"View {len(st.session_state.duplicate_log)} duplicates"):
            for dup in st.session_state.duplicate_log:
                st.write(f"**Title:** {dup['title']}")
                st.write(f"**URL:** {dup['url']}")
                st.write("---")

    # Error log
    if st.session_state.error_log:
        st.subheader("❌ Failed URLs")
        with st.expander(f"View {len(st.session_state.error_log)} failed URLs"):
            for error in st.session_state.error_log:
                st.write(f"**URL:** {error['url']}")
                st.write(f"**Error:** {error['error']}")
                st.write("---")

def provide_downloads():
    """Provide download buttons for WordPress XML and links"""
    if not st.session_state.extraction_complete:
        return

    st.header("💾 Download Results")

    # Check if we have content
    if not st.session_state.get('xml_content'):
        st.info("No content generated yet. Please run the extraction first.")
        return

    # Two columns: XML and Links
    col1, col2 = st.columns(2)

    with col1:
        final_xml = apply_replacements(st.session_state.xml_content)
        label = "📄 WordPress XML"
        if st.session_state.get('replacements'):
            label += " (modified)"
        st.download_button(
            label=label,
            data=final_xml,
            file_name=f"blog_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml",
            mime="application/xml",
            help="WordPress XML file ready for import",
            use_container_width=True
        )

    with col2:
        if st.session_state.get('links_content'):
            st.download_button(
                label="🔗 Extracted Links",
                data=st.session_state.links_content,
                file_name=f"extracted_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                help="All hyperlinks found in blog content",
                use_container_width=True
            )

    # Preview options
    with st.expander("👀 Preview WordPress XML"):
        st.code(st.session_state.xml_content[:2000] + "..." if len(st.session_state.xml_content) > 2000 else st.session_state.xml_content, language="xml")

    if st.session_state.get('links_content'):
        with st.expander("👀 Preview Extracted Links"):
            st.text(st.session_state.links_content[:2000] + "..." if len(st.session_state.links_content) > 2000 else st.session_state.links_content)

def main():
    """Main application function"""
    # Initialize session state
    setup_session_state()

    # Display header
    display_header()

    # Get URLs
    urls = get_url_inputs()

    # Get concurrent settings
    max_concurrent = get_concurrent_settings()

    # Main processing
    st.markdown("---")  # Visual separator
    st.header("🚀 Ready to Extract")

    if urls and not st.session_state.is_processing:
        st.success(f"✅ Ready to process {len(urls)} URL{'s' if len(urls) != 1 else ''}")
        if st.button("🚀 **Extract Blog Posts Now**", type="primary", use_container_width=True):
            st.session_state.is_processing = True
            st.session_state.extraction_complete = False

            with st.spinner("Starting extraction..."):
                process_urls(urls, max_concurrent)
    elif not urls:
        st.info("👆 **Add URLs above** to get started")
    else:
        st.warning("⏳ Processing in progress...")

    # Display results
    display_results()

    # Display link analysis and find/replace interface
    display_link_analysis()
    display_find_replace()

    # Provide downloads
    provide_downloads()

if __name__ == "__main__":
    main()