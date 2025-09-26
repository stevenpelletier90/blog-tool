#!/usr/bin/env python3
"""
Streamlit Web Interface for Blog Extractor Tool
Provides a user-friendly web interface for extracting blog posts and converting to WordPress XML.
"""

import streamlit as st
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any
import io
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

    with st.expander("📋 How to Use This Tool", expanded=False):
        st.markdown("""
        ### Instructions:
        1. **Paste URLs**: Copy and paste your blog URLs into the text box (one per line)
        2. **Extract**: Click the "Extract Blog Posts" button
        3. **Download**: Get your WordPress XML file and extracted links

        ### What This Tool Does:
        - ✅ Extracts blog content from any website (especially Wix)
        - ✅ Gets titles, content, authors, dates, categories, and tags
        - ✅ Finds all links within blog posts
        - ✅ Creates WordPress XML file for easy import
        - ✅ Works with JavaScript-heavy sites
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

def process_urls(urls: List[str], request_delay: int):
    """Process URLs with progress tracking"""
    if not urls:
        st.error("❌ No valid URLs to process")
        return

    # Initialize progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.empty()

    # Initialize extractor
    extractor = BlogExtractor()

    # Reset session state
    st.session_state.extraction_results = []
    st.session_state.error_log = []

    start_time = time.time()

    for i, url in enumerate(urls):
        # Update progress
        progress = (i + 1) / len(urls)
        progress_bar.progress(progress)
        status_text.text(f"🔄 Processing {i + 1}/{len(urls)}: {url}")

        try:
            # Extract blog data
            result = extractor.extract_blog_data(url)

            if result and result.get('title'):
                st.session_state.extraction_results.append(result)
                status = "✅ Success"
            else:
                st.session_state.error_log.append({
                    'url': url,
                    'error': 'No content extracted'
                })
                status = "❌ Failed - No content"

        except Exception as e:
            st.session_state.error_log.append({
                'url': url,
                'error': str(e)
            })
            status = f"❌ Failed - {str(e)}"

        # Show live results
        with results_container.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"{i + 1}. {url}")
            with col2:
                st.write(status)

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
    """Generate XML and links files"""
    try:
        # Set extracted data in extractor
        extractor.extracted_data = st.session_state.extraction_results

        # Generate XML content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as tmp_xml:
            extractor.save_to_xml(tmp_xml.name)
            with open(tmp_xml.name, 'r', encoding='utf-8') as f:
                st.session_state.xml_content = f.read()

        # Generate links content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp_links:
            extractor.save_links_to_txt(tmp_links.name)
            with open(tmp_links.name, 'r', encoding='utf-8') as f:
                st.session_state.links_content = f.read()

    except Exception as e:
        st.error(f"❌ Error generating output files: {e}")

def display_results():
    """Display extraction results and statistics"""
    if not st.session_state.extraction_complete:
        return

    st.header("📊 Extraction Results")

    # Statistics
    total_urls = len(st.session_state.extraction_results) + len(st.session_state.error_log)
    success_count = len(st.session_state.extraction_results)
    failed_count = len(st.session_state.error_log)
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

    # Error log
    if st.session_state.error_log:
        st.subheader("❌ Failed URLs")
        with st.expander(f"View {len(st.session_state.error_log)} failed URLs"):
            for error in st.session_state.error_log:
                st.write(f"**URL:** {error['url']}")
                st.write(f"**Error:** {error['error']}")
                st.write("---")

def provide_downloads():
    """Provide download buttons for generated files"""
    if not st.session_state.extraction_complete:
        return

    st.header("💾 Download Results")

    col1, col2 = st.columns(2)

    with col1:
        if st.session_state.xml_content:
            # Apply replacements before download
            final_xml = apply_replacements(st.session_state.xml_content)

            # Show indicator if modified
            label = "📄 Download WordPress XML"
            if st.session_state.get('replacements'):
                label += " (modified)"

            st.download_button(
                label=label,
                data=final_xml,
                file_name=f"blog_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml",
                mime="application/xml",
                help="WordPress XML file ready for import"
            )

    with col2:
        if st.session_state.links_content:
            st.download_button(
                label="🔗 Download Extracted Links",
                data=st.session_state.links_content,
                file_name=f"extracted_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                help="All hyperlinks found in blog content"
            )

    # Preview options
    if st.session_state.xml_content:
        with st.expander("👀 Preview WordPress XML"):
            st.code(st.session_state.xml_content[:2000] + "..." if len(st.session_state.xml_content) > 2000 else st.session_state.xml_content, language="xml")

    if st.session_state.links_content:
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

    # Main processing
    if urls and not st.session_state.is_processing:
        if st.button("🚀 Extract Blog Posts", type="primary"):
            st.session_state.is_processing = True
            st.session_state.extraction_complete = False

            with st.spinner("Starting extraction..."):
                process_urls(urls, 2)  # Fixed 2-second delay

    # Display results
    display_results()

    # Display link analysis and find/replace interface
    display_link_analysis()
    display_find_replace()

    # Provide downloads
    provide_downloads()

if __name__ == "__main__":
    main()