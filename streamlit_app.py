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
    internal_links = {}  # {url: {'count': N, 'texts': [anchor texts], 'sources': [blog post URLs]}}
    external_links = {}

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
    """Simple URL input with immediate extract button"""
    # Use markdown without anchor links
    st.markdown("### 📝 Step 1: Enter Your Blog URLs")
    st.caption("Paste your blog URLs below (one per line)")

    # Two column layout: text area + button
    col1, col2 = st.columns([3, 1])

    with col1:
        # Text area
        url_text = st.text_area(
            "Blog URLs:",
            height=250,
            placeholder="https://example.com/blog/post1\nhttps://example.com/blog/post2\nhttps://example.com/blog/post3",
            label_visibility="collapsed"
        )

    with col2:
        # Add some vertical spacing to align with text area
        st.write("")
        st.write("")

        # Always show button, but disable if no valid URLs
        urls = []
        if url_text:
            urls = [url.strip() for url in url_text.strip().split('\n') if url.strip()]

        valid_urls = validate_urls(urls)

        # Show button always, disable if no URLs
        button_clicked = st.button(
            "🚀 **EXTRACT POSTS**",
            type="primary",
            use_container_width=True,
            disabled=len(valid_urls) == 0,
            key="extract_button_top",
            help="Click to start extracting blog posts"
        )

        if valid_urls:
            st.success(f"✅ {len(valid_urls)} ready")
        else:
            st.info("👆 Paste URLs first")

        st.caption("*or configure options below*")

    return valid_urls, button_clicked


def get_concurrent_settings() -> tuple[int, bool]:
    """Get concurrent processing settings - concurrent is default for best performance"""
    st.markdown("### ⚡ Step 2 (Optional): Performance Settings")
    st.caption("Concurrent processing is enabled by default for maximum speed (3-5x faster)")

    with st.expander("⚙️ Advanced Performance Options"):
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

        st.markdown("---")

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
            help="Extracts images from blog posts. WordPress will download and import them when you check 'Download and import file attachments' during XML import."
        )

        if include_images:
            st.info("🖼️ Images will be included - WordPress will auto-download them during import")
        else:
            st.info("🚫 Images will be excluded from exported content")

        return max_concurrent, relative_links, include_images

    return 5, False, True  # Default to concurrent with 5 workers, absolute links, include images

def display_find_replace():
    """Simple find/replace interface for link modification"""
    if not st.session_state.get('link_analysis'):
        return

    internal = st.session_state.link_analysis.get('internal', {})
    if not internal:
        return

    st.markdown("### 🔄 Fix Internal Links")
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

def process_urls(urls: List[str], max_concurrent: int = 1, relative_links: bool = False, include_images: bool = True):
    """Process URLs with progress tracking (supports async concurrent mode)"""
    if not urls:
        st.error("❌ No valid URLs to process")
        return

    # Initialize progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_container = st.empty()

    # Create callback for logging
    def logging_callback(level: str, message: str):
        """Callback to display logs in Streamlit - filters verbose messages"""
        # Filter out verbose details - only show essential progress info
        skip_phrases = [
            "Fetching with",
            "attempt",
            "Retrying in",
            "Detected platform",
            "Platform:",
            "URL:",
            "Date:",
            "Author:",
            "Content:",
            "Links:",
            "Categories:",
            "Tags:",
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
            elif 'Success:' in message:
                # Simplify success messages to just show title
                st.success(f"✅ {message.replace('✓ Success: ', '')}")
            else:
                st.info(f"ℹ️ {message}")

    # Initialize extractor with callback
    extractor = BlogExtractor(callback=logging_callback, verbose=False, relative_links=relative_links, include_images=include_images)

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
                st.caption(f"Skipped as duplicate content")
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

    # Get URLs and check if extract button was clicked
    urls, start_extraction = get_url_inputs()

    # Get concurrent settings (optional, collapsed by default)
    max_concurrent, relative_links, include_images = get_concurrent_settings()

    # Start extraction if button was clicked
    if start_extraction and urls and not st.session_state.is_processing:
        st.session_state.is_processing = True
        st.session_state.extraction_complete = False

        st.markdown("---")
        st.markdown("### 🔄 Extracting Blog Posts...")

        with st.spinner("Processing your blog posts..."):
            process_urls(urls, max_concurrent, relative_links, include_images)
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