# Blog Extractor - Complete User Guide

**Version:** 2.0
**Last Updated:** January 2025
**Audience:** Web designers, marketers, and non-technical users

---

## Executive Summary

Blog Extractor is a user-friendly tool that automatically copies blog posts from any website and converts them into a format that WordPress can import. No coding knowledge required - just provide the blog URLs, and the tool handles everything else.

**What it does:**

- Extracts blog posts from any platform (Wix, WordPress, Squarespace, DealerOn, Medium, etc.)
- Preserves content, images, formatting, dates, authors, and categories
- Generates a WordPress XML file ready for one-click import
- Handles JavaScript-heavy sites automatically
- Prevents duplicate content
- Processes multiple posts simultaneously for speed

**Time savings:** Extract 40 blog posts in 15-20 seconds instead of hours of manual copying.

---

## Table of Contents

1. [What This Tool Does](#what-this-tool-does)
2. [Who Should Use This](#who-should-use-this)
3. [System Requirements](#system-requirements)
4. [Getting Started - Installation](#getting-started---installation)
5. [Project File Structure](#project-file-structure)
6. [How to Use - Three Methods](#how-to-use---three-methods)
7. [Understanding Your Results](#understanding-your-results)
8. [Importing to WordPress](#importing-to-wordpress)
9. [Troubleshooting Common Issues](#troubleshooting-common-issues)
10. [Frequently Asked Questions](#frequently-asked-questions)
11. [Supported Platforms](#supported-platforms)
12. [Advanced Options](#advanced-options)
13. [Appendix: Technical Details](#appendix-technical-details)

---

## What This Tool Does

The Blog Extractor automates the process of migrating blog content from one platform to WordPress. Instead of manually copying and pasting each blog post, the tool:

1. **Visits each blog URL** you provide
2. **Automatically detects** the blog platform (Wix, Squarespace, etc.)
3. **Extracts** title, content, author, date, categories, tags, and images
4. **Converts** the content to WordPress format
5. **Generates** a WordPress XML file ready for import
6. **Handles** all technical details automatically

### Key Features

✅ **Universal Platform Support** - Works with any HTML-based blog (tested on 8+ major platforms)
✅ **Automatic Image Handling** - Images are automatically included and imported to WordPress
✅ **Smart Duplicate Detection** - Prevents duplicate posts if the same content appears at multiple URLs
✅ **Fast Processing** - Processes multiple URLs simultaneously (3-5x faster than sequential)
✅ **Two Interfaces** - Easy web interface OR command-line for automation
✅ **No Coding Required** - Just follow simple step-by-step instructions

---

## Who Should Use This

### Perfect for

- **Web Designers** migrating client websites to WordPress
- **Marketing Teams** consolidating blog content from multiple sources
- **Agencies** managing multiple client migrations
- **Website Owners** moving from Wix, Squarespace, or custom platforms to WordPress
- **Anyone** who needs to migrate 10+ blog posts efficiently

### Use Cases

1. **Client Website Migration** - Moving a client's 50 blog posts from Wix to WordPress
2. **Platform Consolidation** - Combining blogs from multiple platforms into one WordPress site
3. **Content Backup** - Creating a WordPress-compatible backup of existing blog content
4. **Domain Migration** - Moving blog content to a new domain while preserving all links
5. **Multi-Site Management** - Extracting content from multiple dealer/franchise sites

---

## System Requirements

### Operating System

- **Windows** 10 or later
- **macOS** 10.15 (Catalina) or later
- **Linux** (Ubuntu 20.04+, Debian 11+, or equivalent)

### Software Requirements

- **Python 3.8 or later** (Python 3.13+ recommended)
- **Internet connection** (for downloading dependencies and accessing blog URLs)
- **Web browser** (Chrome, Firefox, Safari, or Edge)

### Disk Space

- **500 MB** for software and dependencies
- **Additional space** for extracted content (varies by blog size)

### Don't worry

The automated setup script checks for Python and installs everything else automatically. If Python isn't installed, the script will tell you where to download it.

---

## Getting Started - Installation

Installation is **completely automated**. Just run the setup script for your operating system and it handles everything.

### Windows Installation

1. **Download or navigate to** the `blog-tool` folder
2. **Double-click** `setup.bat`
3. **Wait** for the automated installation (2-5 minutes)
4. **Done!** The tool is ready to use

**What the setup script does:**

- ✅ Checks if Python is installed
- ✅ Creates a virtual environment (isolated installation)
- ✅ Installs all required Python libraries
- ✅ Downloads Chromium browser for JavaScript-heavy sites (~300MB)
- ✅ Creates `output/` folders for extracted content
- ✅ Creates a sample `urls.txt` file

### Mac/Linux Installation

1. **Open Terminal**
2. **Navigate** to the `blog-tool` folder:

   ```bash
   cd /path/to/blog-tool
   ```

3. **Run the setup script:**

   ```bash
   bash setup.sh
   ```

4. **Wait** for the automated installation (2-5 minutes)
5. **Done!** The tool is ready to use

### Verification

After setup completes, you should see:

```bash
========================================
Setup Complete!
========================================

Next steps:
1. Edit urls.txt and add your blog URLs (one per line)
2. Run the web UI: blog-extractor-env\Scripts\streamlit.exe run streamlit_app.py
3. OR run the CLI: blog-extractor-env\Scripts\python.exe extract.py
```

If you see this message, installation was successful!

### Troubleshooting Installation

#### Problem: "Python is not installed or not in PATH"

**Solution:**

1. Download Python from <https://www.python.org/downloads/>
2. During installation, **CHECK** the box that says "Add Python to PATH"
3. Restart your computer
4. Run setup.bat again

#### Problem: "Failed to install dependencies"

**Solution:**

1. Check your internet connection
2. Try again - sometimes download servers are temporarily slow
3. If it still fails, try the manual installation (see README.md)

#### Problem: "Playwright browser installation failed"

**Solution:**

- Don't worry! The tool will still work with basic functionality
- For best results with JavaScript-heavy sites (like Wix), run:

  ```bash
  blog-extractor-env\Scripts\python.exe -m playwright install --with-deps
  ```

---

## Project File Structure

After installation, your folder will contain:

```bash
blog-tool/
├── setup.bat                    # Windows setup script (double-click to install)
├── setup.sh                     # Mac/Linux setup script
├── run_extractor.bat            # Windows quick launcher (double-click to extract)
├── urls.txt                     # Your list of blog URLs (EDIT THIS FILE)
├── blog_extractor.py            # Core extraction engine (don't edit)
├── extract.py                   # Command-line interface (don't edit)
├── streamlit_app.py             # Web interface (don't edit)
├── blog-extractor-env/          # Virtual environment (created by setup)
├── output/                      # Extracted content appears here
│   ├── blog_posts.xml           # WordPress import file (main output)
│   ├── extracted_links.txt      # All hyperlinks found
│   ├── blog_posts.json          # JSON backup (optional)
│   └── images/                  # Downloaded images (optional, CLI only)
├── README.md                    # Technical documentation
├── ARCHITECTURE.md              # Technical deep dive
└── CLAUDE.md                    # AI assistant instructions
```

### Files You'll Use

- **`urls.txt`** - Add your blog URLs here (one per line)
- **`output/blog_posts.xml`** - This is what you import to WordPress
- **`output/extracted_links.txt`** - Lists all hyperlinks found (useful for checking internal links)

### Files You Won't Need to Touch

- **`blog_extractor.py`**, **`extract.py`**, **`streamlit_app.py`** - Tool source code
- **`blog-extractor-env/`** - Contains all installed libraries (auto-managed)

---

## How to Use - Three Methods

Choose the method that works best for you. All three methods produce the same WordPress XML file.

### Method A: Web Interface (Recommended for Beginners)

**Best for:** Visual interface, real-time progress, URL paste-in

**Steps:**

1. **Start the web interface:**
   - **Windows:** Open Command Prompt in the `blog-tool` folder and run:

     ```bash
     blog-extractor-env\Scripts\streamlit.exe run streamlit_app.py
     ```

   - **Mac/Linux:** Open Terminal in the `blog-tool` folder and run:

     ```bash
     blog-extractor-env/bin/streamlit run streamlit_app.py
     ```

2. **Your web browser opens automatically** to <http://localhost:8501>
   - If it doesn't open, manually visit <http://localhost:8501>

3. **Add your blog URLs:**
   - **Option 1:** Paste URLs directly into the text box (one per line)
   - **Option 2:** Upload a text file with URLs

4. **Configure settings** (optional):
   - **Concurrent Requests:** How many URLs to process simultaneously (default: 5)
   - **Delay Between Requests:** Pause between URLs to avoid rate limiting (default: 2 seconds)
   - **Max Retries:** How many times to retry failed URLs (default: 3)

5. **Click "Start Extraction"**

6. **Watch real-time progress:**
   - ✅ Green checkmarks for successful extractions
   - ❌ Red X marks for failures (with error messages)
   - Progress bar shows overall completion

7. **Download your files:**
   - Click **"Download WordPress XML"** - This is the file you import to WordPress
   - Click **"Download Extracted Links"** - Lists all hyperlinks found

8. **Done!** Close the browser tab and press Ctrl+C in the terminal to stop the server

**Success indicators:**

- Status shows "✅ Success" for each URL
- Progress bar reaches 100%
- "Download WordPress XML" button appears
- Activity log shows "Extraction completed successfully"

---

### Method B: Command Line (For Tech-Savvy Users)

**Best for:** Automation, scripting, advanced options

**Steps:**

1. **Create/edit `urls.txt`** in the `blog-tool` folder:

   ```text
   https://example.com/blog/post-1
   https://example.com/blog/post-2
   https://example.com/blog/post-3
   ```

2. **Open Command Prompt (Windows) or Terminal (Mac/Linux)** in the `blog-tool` folder

3. **Run the extractor:**

   ```bash
   # Windows
   blog-extractor-env\Scripts\python.exe extract.py

   # Mac/Linux
   blog-extractor-env/bin/python extract.py
   ```

4. **Watch the progress bar:**

   ```bash
   Processing URLs: 100%|████████████████| 10/10 [00:15<00:00, 1.53s/URL]
   ```

5. **Check the output:**

   ```bash
   ✅ Successfully processed 10 URLs
   📁 Output saved to:
      - output/blog_posts.xml
      - output/extracted_links.txt
   ```

6. **Done!** Import `output/blog_posts.xml` to WordPress

**Advanced options:**

```bash
# Process 5 URLs simultaneously (3-5x faster)
python extract.py --concurrent 5

# Add 3-second delay between requests (avoid rate limiting)
python extract.py --delay 3

# Retry failed URLs 5 times instead of 3
python extract.py --retries 5

# Generate all output formats (XML, JSON, CSV)
python extract.py --format all

# Download images to local folder (optional backup)
python extract.py --download-images

# Verbose output (show detailed logs)
python extract.py --verbose

# Combine options
python extract.py --concurrent 5 --delay 2 --retries 5 --verbose
```

---

### Method C: Windows Batch File (One-Click Extraction)

**Best for:** Windows users who want the simplest possible workflow

**Steps:**

1. **Create/edit `urls.txt`** in the `blog-tool` folder:

   ```text
   https://example.com/blog/post-1
   https://example.com/blog/post-2
   ```

2. **Double-click `run_extractor.bat`**

3. **Wait for extraction to complete:**

   ```bash
   ========================================
      Blog Extractor - Playwright Powered
   ========================================

   Starting blog extraction...
   Processing URLs: 100%|████████████████| 10/10 [00:15<00:00]

   ========================================
   Extraction complete!

   Output files:
   - output\blog_posts.xml (WordPress XML)
   - output\extracted_links.txt (All hyperlinks)
   ========================================
   ```

4. **Press any key** to close the window

5. **Done!** Import `output\blog_posts.xml` to WordPress

---

## Understanding Your Results

After extraction completes, you'll find these files in the `output/` folder:

### Primary Output: blog_posts.xml

**What it is:** WordPress WXR 1.2 format XML file containing all extracted blog posts

**What's inside:**

- Post titles
- Post content (HTML formatted)
- Authors
- Publication dates
- Categories
- Tags
- Images (as HTTPS URLs that WordPress will download during import)
- Internal links (preserved)

**What to do with it:** Import this file to WordPress (see next section)

**File size:** Varies by content amount (typically 100KB - 10MB)

### Secondary Output: extracted_links.txt

**What it is:** Plain text file listing all hyperlinks found in all blog posts

**Format:**

```bash
=== https://example.com/blog/post-1 ===
- https://example.com/products
- https://example.com/about
- https://external-site.com

=== https://example.com/blog/post-2 ===
- https://example.com/contact
- https://another-site.com
```

**What to do with it:**

- Check for broken links before importing
- Identify internal vs external links
- Plan link redirection strategy for domain migrations

### Optional Output: blog_posts.json (CLI only)

**What it is:** JSON-formatted version of the extracted data

**When it's created:** Only if you use `--format json` or `--format all` flags in CLI

**What to do with it:** Use for custom processing, backups, or integration with other tools

### Optional Output: images/ folder (CLI only)

**What it is:** Local copies of all images from blog posts

**When it's created:** Only if you use `--download-images` flag in CLI

**Note:** The WordPress XML always uses HTTPS URLs for images (not local file paths), so WordPress downloads images from the web during import. This folder is just a backup.

---

## Importing to WordPress

Once you have `blog_posts.xml`, follow these steps to import it to WordPress:

### Step 1: Access WordPress Admin

1. Log in to your WordPress admin dashboard
2. Navigate to **Tools → Import**

### Step 2: Install WordPress Importer (if needed)

1. Find **WordPress** in the list of importers
2. Click **Install Now** if not already installed
3. Click **Run Importer** after installation

### Step 3: Upload XML File

1. Click **Choose File**
2. Select `output/blog_posts.xml` from your computer
3. Click **Upload file and import**

### Step 4: Assign Authors

1. WordPress will ask you to assign authors to the imported posts
2. **Option 1:** Create new author accounts (if you want to preserve original author names)
3. **Option 2:** Assign all posts to an existing user
4. **Check the box** "Download and import file attachments" (this downloads images)

### Step 5: Wait for Import

1. WordPress processes the file (usually 10-60 seconds for 50 posts)
2. You'll see a progress indicator
3. Success message appears when complete

### Step 6: Verify Import

1. Go to **Posts → All Posts** - You should see all imported posts
2. Go to **Media → Library** - Images should be downloading/uploaded
3. Open a few posts to verify content looks correct

### Step 7: Final Touches

1. **Check categories:** Go to **Posts → Categories** - Imported categories appear here
2. **Check tags:** Go to **Posts → Tags** - Imported tags appear here
3. **Review permalinks:** Go to **Settings → Permalinks** - Make sure URL structure matches your old site
4. **Set up redirects:** Use a redirect plugin to redirect old URLs to new WordPress URLs

### Troubleshooting Import

**Problem: "Failed to import media" or images missing**

**Causes:**

- WordPress couldn't access the image URLs
- Images were removed from the source site
- Server firewall blocking downloads

**Solutions:**

1. Re-run the importer (WordPress will retry failed images)
2. Check that image URLs are accessible in a web browser
3. If using CLI, use `--download-images` flag to save local copies, then manually upload to Media Library

**Problem: "XML file is empty" or "Invalid file"**

**Causes:**

- Extraction may have failed
- XML file corrupted

**Solutions:**

1. Open `blog_posts.xml` in a text editor - should contain XML data starting with `<?xml version="1.0"?>`
2. If empty or corrupted, re-run the extraction
3. Check extraction logs for error messages

**Problem: "Duplicate posts after import"**

**Causes:**

- Importing the same XML file twice
- Same content at different URLs

**Solutions:**

1. Delete duplicate posts manually or use a duplicate post cleaner plugin
2. The extractor already prevents duplicate content in a single extraction using MD5 hashing

---

## Troubleshooting Common Issues

### Issue 1: Tool Crashes with "UnicodeEncodeError"

**Symptoms:**

```bash
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'
```

**Cause:** Windows console can't display certain Unicode characters

**Solution:** This is **fixed in the latest version**. If you're still seeing this:

1. Update to the latest version
2. Or run the web interface instead of CLI (web interface doesn't have this issue)

---

### Issue 2: No Content Extracted (Empty XML)

**Symptoms:**

- Extraction completes but XML file is empty or has no posts
- Status shows "Success" but no content

**Causes:**

- URL is not a blog post (might be a homepage or category page)
- Website blocks automated tools
- Content is behind a login/paywall

**Solutions:**

1. **Verify URLs are blog posts** - Open each URL in a browser and confirm it's a blog post
2. **Try a single post first** - Test with just one URL to isolate the issue
3. **Check website structure** - Some platforms require you to be logged in to see full content
4. **Use verbose mode** - Run with `--verbose` flag to see detailed logs:

   ```bash
   python extract.py --verbose
   ```

---

### Issue 3: Tool Hangs or Freezes

**Symptoms:**

- Progress bar stops moving
- No output for several minutes
- CPU usage stays high

**Causes:**

- Website taking too long to respond
- JavaScript-heavy page loading slowly
- Server rate-limiting or blocking requests

**Solutions:**

1. **Wait longer** - Some pages take 30-60 seconds to load (especially with Playwright)
2. **Reduce concurrent requests** - Lower from 5 to 3 or 2:

   ```bash
   python extract.py --concurrent 2
   ```

3. **Add delay between requests** - Avoid overwhelming the server:

   ```bash
   python extract.py --delay 5
   ```

4. **Kill and restart** - Press Ctrl+C to stop, then run again with different settings

---

### Issue 4: Images Not Appearing in WordPress

**Symptoms:**

- Posts imported successfully but images are missing
- Placeholder images or broken image icons

**Causes:**

- WordPress server can't access image URLs
- Images were removed from source site
- Dynamic image URLs expired

**Solutions:**

1. **Re-run WordPress import** - Go to Tools → Import → WordPress and upload XML again (WordPress retries failed images)
2. **Check image URLs** - Open `blog_posts.xml` in a text editor and find an `<img src="...">` tag - Copy the URL and try opening it in a browser
3. **Use CLI with --download-images** - Downloads images locally as backup:

   ```bash
   python extract.py --download-images
   ```

4. **Check WordPress Media Library** - Images may still be downloading (can take 5-10 minutes for large imports)

---

### Issue 5: "Playwright not installed" Warning

**Symptoms:**

```bash
WARNING: Playwright not installed. Falling back to basic HTTP requests.
```

**Impact:**

- Tool still works but may miss JavaScript-rendered content on sites like Wix or Webflow

**Solution:**

1. **Install Playwright browsers:**

   ```bash
   # Windows
   blog-extractor-env\Scripts\python.exe -m playwright install --with-deps

   # Mac/Linux
   blog-extractor-env/bin/python -m playwright install --with-deps
   ```

2. **If installation fails** - The tool still works! Just may not capture 100% of content on JavaScript-heavy sites

---

### Issue 6: "Rate Limited" or "Access Denied" Errors

**Symptoms:**

```bash
ERROR: HTTP 429 Too Many Requests
ERROR: HTTP 403 Forbidden
```

**Causes:**

- Website blocking automated requests
- Too many requests too quickly

**Solutions:**

1. **Reduce concurrent requests:**

   ```bash
   python extract.py --concurrent 1 --delay 5
   ```

2. **Add longer delays:**

   ```bash
   python extract.py --delay 10
   ```

3. **Process in smaller batches** - Extract 10 URLs at a time instead of 100

---

## Frequently Asked Questions

### General Questions

**Q: Do I need to know coding or programming?**

A: No! The tool is designed for non-technical users. Just run the setup script and follow the step-by-step instructions.

---

**Q: How long does extraction take?**

A:

- **Single post:** 2-5 seconds (basic sites) or 10-20 seconds (JavaScript-heavy sites)
- **10 posts (concurrent):** 15-25 seconds
- **50 posts (concurrent):** 60-90 seconds
- **100 posts (concurrent):** 2-4 minutes

---

**Q: What platforms are supported?**

A: The tool works with any HTML-based blog. Fully tested and optimized for:

- Wix
- Webflow
- WordPress
- Squarespace
- Medium
- Blogger
- DealerOn (automotive dealer platforms)
- DealerInspire (automotive dealer platforms)

Even if your platform isn't listed, it will likely work using generic HTML parsing.

---

**Q: Will images be included?**

A: **Yes!** Images are automatically handled in two ways:

1. **Resolved HTTPS URLs** included in WordPress XML - WordPress downloads images during import
2. **(Optional)** Local backup copies if you use `--download-images` flag in CLI

---

**Q: Will it create duplicate posts?**

A: **No.** The tool uses MD5 content hashing to detect duplicates. If the same content appears at multiple URLs, only one copy is extracted.

---

**Q: Can I run this on a schedule?**

A: **Yes!** CLI method can be automated:

- **Windows:** Use Task Scheduler to run `run_extractor.bat` daily/weekly
- **Mac/Linux:** Use cron jobs to run `extract.py` on a schedule
- **Cloud:** Deploy to Streamlit Cloud or AWS and run on demand

---

**Q: Does it work with password-protected blogs?**

A: **No.** The tool can only access publicly available content. If your blog requires login, you'll need to make posts public temporarily or manually copy content.

---

**Q: Can I use it for non-blog content (pages, products, etc.)?**

A: Currently optimized for blog posts only. Pages and products may extract but formatting might not be perfect. Future versions may add support.

---

**Q: What if my platform isn't supported?**

A: The tool uses generic fallback parsing for unknown platforms. It may still extract content successfully. Try it with 1-2 test URLs first.

---

### Technical Questions

**Q: What is a "virtual environment"?**

A: A virtual environment (`blog-extractor-env/`) is an isolated installation of Python libraries. It keeps this tool's dependencies separate from other Python projects on your computer. The setup script creates this automatically - you don't need to manage it.

---

**Q: Why does setup download 300MB of Chromium browser?**

A: Playwright uses a real Chromium browser to render JavaScript-heavy websites (like Wix). This ensures all content is loaded before extraction. Without it, the tool falls back to basic HTTP requests which may miss dynamically-loaded content.

---

**Q: Can I delete the virtual environment folder?**

A: Yes, you can delete `blog-extractor-env/` to free up space (~500MB). To use the tool again, just run `setup.bat` or `setup.sh` to reinstall.

---

**Q: Does it use my web browser or a separate browser?**

A: Playwright uses its own headless (invisible) Chromium browser. It doesn't touch your personal Chrome/Firefox browser or settings.

---

**Q: What does "concurrent processing" mean?**

A: Instead of extracting URLs one-by-one (sequential), concurrent processing extracts multiple URLs at the same time (parallel). This makes extraction 3-5x faster.

**Example:**

- **Sequential (1 at a time):** 50 posts × 2 seconds = 100 seconds
- **Concurrent (5 at a time):** 50 posts ÷ 5 × 2 seconds = 20 seconds

---

**Q: Is my data sent to external servers?**

A: **No.** Everything runs locally on your computer. The tool only accesses the blog URLs you provide to extract content. No data is sent to third parties.

---

**Q: Can I run this on a server without a display (headless)?**

A: **Yes!** Playwright runs in headless mode by default. You can deploy to:

- AWS EC2 instances
- Docker containers
- Streamlit Cloud
- GitHub Actions

---

## Supported Platforms

The tool has been **tested and optimized** for these platforms:

| Platform | Status | Notes |
|----------|--------|-------|
| **Wix** | ✅ Fully Supported | Lazy-loaded content, JavaScript rendering |
| **Webflow** | ✅ Fully Supported | Rich text content extraction |
| **WordPress** | ✅ Fully Supported | Direct content extraction |
| **Squarespace** | ✅ Fully Supported | Blog content |
| **Medium** | ✅ Fully Supported | Article extraction |
| **Blogger** | ✅ Fully Supported | Google's blog platform |
| **DealerOn** | ✅ Fully Supported | Automotive dealer blogs |
| **DealerInspire** | ✅ Fully Supported | Automotive dealer blogs |
| **Custom/Unknown** | ⚠️ Generic Fallback | May work - test first |

### How Platform Detection Works

The tool automatically detects your blog platform by analyzing:

1. **Meta tags** - `<meta name="generator" content="Wix.com">`
2. **CSS classes** - Platform-specific class names
3. **URL patterns** - Domain and path structure
4. **HTML structure** - Unique element patterns

Once detected, it uses **platform-specific extraction rules** for best results. If the platform isn't recognized, it falls back to **generic HTML parsing** which works with most sites.

### Testing Your Platform

Not sure if your platform is supported? Test with 1-2 URLs first:

1. Add 2 blog post URLs to `urls.txt`
2. Run the extraction
3. Check `blog_posts.xml` - if content looks good, you're all set!
4. If content is missing or malformed, contact support with your platform details

---

## Advanced Options

### CLI Flags Reference

For power users who want more control:

```bash
python extract.py [OPTIONS]
```

**Input Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--input FILE` | Path to input file with URLs | `urls.txt` |

**Processing Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--concurrent N` | Process N URLs simultaneously | `1` (sequential) |
| `--delay N` | Wait N seconds between requests | `2` |
| `--retries N` | Retry failed URLs N times | `3` |

**Output Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--format FORMAT` | Output format: `xml`, `json`, `csv`, `all` | `xml` |
| `--output DIR` | Output directory path | `output` |

**Image Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--download-images` | Download images to local folder | `False` |
| `--relative-links` | Keep links relative (for domain migration) | `False` (absolute) |

**Logging Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--verbose` | Show detailed logs | `False` |

**Examples:**

```bash
# Fast concurrent extraction
python extract.py --concurrent 5 --delay 1

# Safe extraction for rate-limited sites
python extract.py --concurrent 2 --delay 10 --retries 5

# All output formats with local image backup
python extract.py --format all --download-images

# Domain migration (keep relative links)
python extract.py --relative-links --format xml

# Custom input/output paths
python extract.py --input my_urls.txt --output my_output/

# Full verbose logging for debugging
python extract.py --verbose --retries 5
```

---

### Web UI Advanced Settings

The Streamlit web interface includes an **Advanced Settings** panel:

#### Concurrent Requests (1-10)

- How many URLs to process simultaneously
- **Recommended:** 3-5 (balance of speed and safety)
- **Higher (8-10):** Faster but may trigger rate limiting
- **Lower (1-2):** Slower but safest for sensitive sites

#### Delay Between Requests (0-30 seconds)

- Pause between each request
- **Recommended:** 2-3 seconds
- **Higher (10+):** For rate-limited sites
- **Lower (0-1):** For fast sites without rate limits

#### Max Retries (1-10)

- How many times to retry failed URLs
- **Recommended:** 3 retries
- **Higher (5-10):** For unreliable sites
- **Lower (1-2):** For stable sites

#### Download Images (Yes/No)

- Save images to local folder as backup
- **Default:** No (images imported via XML)
- **Yes:** Creates local backup in `output/images/`

---

## Appendix: Technical Details

For developers and advanced users who want to understand how the tool works under the hood.

### Architecture Overview

**Three-Layer Design:**

1. **Core Engine** (`blog_extractor.py`) - Standalone extraction engine
   - Platform detection
   - Content extraction
   - Image resolution
   - WordPress XML generation

2. **CLI Interface** (`extract.py`) - Command-line wrapper
   - Argument parsing
   - Progress bars
   - Multiple output formats

3. **Web UI** (`streamlit_app.py`) - Browser-based interface
   - Real-time progress tracking
   - URL input and file upload
   - Download buttons for results

### Content Extraction Pipeline

**Step 1: Fetch Content**

- Try async Playwright (best for JavaScript-heavy sites)
- Fall back to sync Playwright
- Fall back to requests library (works everywhere)

**Step 2: Detect Platform**

- Analyze meta tags, CSS classes, URL patterns
- Select platform-specific extraction rules

**Step 3: Extract Content**

- Title, author, date, categories, tags
- Main content area (excluding navigation/footer)
- All hyperlinks and images

**Step 4: Process Content**

- Convert relative URLs to absolute
- Resolve dynamic image URLs (WebDAM → S3)
- Normalize Unicode characters
- Detect duplicates using MD5 hashing

**Step 5: Generate Output**

- WordPress WXR 1.2 XML format
- Gutenberg block conversion
- Preserve all formatting and attributes

### Image Handling Strategy

**Problem:** Many sites use dynamic image URLs that expire or redirect.

**Solution:**

1. Detect dynamic URLs (WebDAM, `display.php`, etc.)
2. Follow redirects to get permanent S3 URLs
3. Strip signed parameters (`?signature=...`, `?expires=...`)
4. Cache resolved URLs to avoid duplicate requests
5. Include HTTPS URLs in WordPress XML (not `file://` paths)
6. (Optional) Download local backup if `--download-images` enabled

**Result:** WordPress downloads images from HTTPS URLs during import, ensuring they persist even if removed from source site.

### Duplicate Detection

**Method:** MD5 content hashing

**Process:**

1. Extract content text (strip HTML tags)
2. Normalize (lowercase, trim whitespace)
3. Generate MD5 hash
4. Compare to previous hashes
5. Skip if duplicate detected

**Why MD5?** Fast and sufficient collision resistance for blog posts (not for security).

**Future:** May migrate to `blake2s` or SHA-256 for FIPS compliance.

### Concurrency Model

**Pattern:** Semaphore-based async processing

**How it works:**

1. Create semaphore with max limit (e.g., 5 concurrent)
2. Launch async tasks for all URLs
3. Semaphore blocks when limit reached
4. Tasks complete and release semaphore slots
5. New tasks acquire slots and proceed

**Benefits:**

- 3-5x speedup over sequential processing
- Controlled load on servers
- Error isolation (one failure doesn't stop others)

**Trade-offs:**

- Higher memory usage (~50-250MB for 5 concurrent)
- Risk of rate limiting if too many concurrent requests

### WordPress XML Format

**Standard:** WXR 1.2 (WordPress eXtended RSS)

**Structure:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:wp="http://wordpress.org/export/1.2/">
  <channel>
    <title>Imported Blog</title>
    <item>
      <title><![CDATA[Post Title]]></title>
      <content:encoded><![CDATA[
        <!-- wp:html -->
        <p>Post content here...</p>
        <!-- /wp:html -->
      ]]></content:encoded>
      <wp:post_type>post</wp:post_type>
      <wp:status>publish</wp:status>
      <category domain="category"><![CDATA[Category Name]]></category>
    </item>
  </channel>
</rss>
```

**Critical Implementation:**

- Must use `formatter="minimal"` with BeautifulSoup to prevent URL line breaks
- WordPress truncates URLs split across lines, breaking all links
- HTTPS URLs for images (not `file://` paths) so WordPress server can access them

### Performance Characteristics

**Single URL:**

- Playwright: 10-20 seconds
- Requests: 2-5 seconds

**Concurrent Processing (5 URLs):**

- Sequential: 50-100 seconds
- Concurrent: 15-25 seconds (3-5x speedup)

**Memory Usage:**

- Per URL: ~10-50 MB
- Concurrent (5): ~50-250 MB

---

## Support & Resources

### Getting Help

**For issues, questions, or feature requests:**

1. Check this guide's [Troubleshooting](#troubleshooting-common-issues) section
2. Check the [FAQ](#frequently-asked-questions)
3. Open an issue on the project repository (if available)
4. Contact the developer or your IT support team

### Additional Documentation

- **README.md** - Quick start guide and technical overview
- **ARCHITECTURE.md** - Deep dive into code structure and design patterns
- **CLAUDE.md** - AI assistant instructions and critical constraints
- **CONTRIBUTING.md** - Guide for developers adding new features

### Version History

- **v2.0** (January 2025) - Fixed Unicode encoding issues, improved documentation
- **v1.5** - Added Streamlit Cloud support with Playwright auto-install
- **v1.0** - Initial release with 8+ platform support

---

## License

See LICENSE file for details.

---

**Questions? Feedback? Found a bug?**
Open an issue or contact your project administrator.

---

*End of User Guide*
