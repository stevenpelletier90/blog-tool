# Blog Post Extractor & WordPress Migration Tool

Extract blog posts from any website and convert them to WordPress XML format in 3 easy steps.

**Supports:** Wix, WordPress, Medium, Squarespace, Blogger, DealerOn, DealerInspire, Webflow, and more!

---

## Installation (One-Time Setup)

### Windows

1. **Extract this folder** to your computer
2. **Double-click `setup.bat`**
3. Wait for installation to complete (2-5 minutes)

That's it! Everything is installed automatically.

### Mac/Linux

1. **Extract this folder** to your computer
2. **Open Terminal** in this folder
3. **Run:** `bash setup.sh`
4. Wait for installation to complete (2-5 minutes)

That's it! Everything is installed automatically.

**What the setup does:**

- Checks if Python is installed (requires Python 3.8+)
- Creates a virtual environment
- Installs all required libraries
- Downloads browser components
- Creates sample files

---

## How to Use

You have **2 options**: Web Interface (easier) or Command Line (faster for bulk jobs)

### Option 1: Web Interface (Recommended for Beginners)

**Windows:**

```bash
blog-extractor-env\Scripts\streamlit.exe run streamlit_app.py
```

**Mac/Linux:**

```bash
blog-extractor-env/bin/streamlit run streamlit_app.py
```

Then:

1. Your browser will open automatically at `http://localhost:8501`
2. Paste your blog URLs (one per line)
3. Click "Extract Blog Posts Now"
4. Download the XML file when complete
5. Import to WordPress (see below)

### Option 2: Command Line (For Bulk Extraction)

**Step 1:** Create a file called `urls.txt` with your blog URLs (one per line):

```bash
https://example.com/blog/post-1
https://example.com/blog/post-2
https://example.com/blog/post-3
```

**Step 2:** Run the extractor:

**Windows:**

```bash
blog-extractor-env\Scripts\python.exe extract.py
```

**Mac/Linux:**

```bash
blog-extractor-env/bin/python extract.py
```

**Step 3:** Find your WordPress XML file in the `output/` folder

#### Common Options

**Process 5 URLs at once (3-5x faster):**

```bash
# Windows
blog-extractor-env\Scripts\python.exe extract.py --concurrent 5

# Mac/Linux
blog-extractor-env/bin/python extract.py --concurrent 5
```

**See all options:**

```bash
# Windows
blog-extractor-env\Scripts\python.exe extract.py --help

# Mac/Linux
blog-extractor-env/bin/python extract.py --help
```

---

## Importing to WordPress

Once you have the XML file (`blog_posts.xml`):

1. Log into your WordPress admin panel
2. Go to **Tools → Import**
3. Click **WordPress** (install the WordPress Importer if prompted)
4. Click **Choose File** and select `blog_posts.xml`
5. Click **Upload file and import**
6. Assign authors (or create new ones)
7. Check **"Download and import file attachments"** to import images
8. Click **Submit**
9. Done! Your blog posts are now in WordPress

---

## What Gets Extracted

✅ Blog post titles
✅ Full content (text, images, formatting)
✅ Author names
✅ Publication dates
✅ Categories and tags
✅ All links (internal and external)
✅ Images (WordPress downloads them automatically)

---

## Troubleshooting

### "Python is not installed"

Download and install Python 3.8 or newer from [python.org/downloads](https://www.python.org/downloads/)
**Important:** Check "Add Python to PATH" during installation

### "Command not found" or "File not found"

Make sure you're running commands from the extracted folder where the files are located

### Images not appearing in WordPress

- Make sure you checked "Download and import file attachments" during import
- Images may take a few minutes to download after import
- Check your WordPress Media Library to see import progress

### Extraction is slow

Use the `--concurrent 5` option to process 5 URLs simultaneously:

```bash
blog-extractor-env\Scripts\python.exe extract.py --concurrent 5
```

### Website blocking the tool

Some sites have anti-scraping protection. Try adding a delay:

```bash
blog-extractor-env\Scripts\python.exe extract.py --delay 5
```

---

## Output Files

All files are saved to the `output/` folder:

- **blog_posts.xml** - WordPress import file (this is what you need!)
- **extracted_links.txt** - All links found in your blog posts
- **blog_posts.json** - JSON format (optional, for developers)
- **blog_posts.csv** - CSV format (optional, for spreadsheets)

---

## Need Help?

**Common Questions:**

**Q: Do I need to keep the virtual environment folder?**
A: Yes! The `blog-extractor-env` folder contains all the installed libraries. Don't delete it.

**Q: Can I move this folder?**
A: Yes! Just move the entire folder. Everything will still work.

**Q: How do I extract more blog posts later?**
A: Just add new URLs to `urls.txt` and run the extractor again. Or use the web interface.

**Q: What if I have 1000+ blog posts?**
A: Use the command line with `--concurrent 5` option. It can handle thousands of URLs.

**Q: Can I extract from password-protected blogs?**
A: No, the blog posts must be publicly accessible.

---

## Version

Current version: **1.0.0**

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.

---

## License

This software is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

You are free to use, modify, and distribute this software for any purpose, including commercial use.

---

## Quick Reference Card

```bash
INSTALLATION (one time):
  Windows:    Double-click setup.bat
  Mac/Linux:  bash setup.sh

WEB INTERFACE:
  Windows:    blog-extractor-env\Scripts\streamlit.exe run streamlit_app.py
  Mac/Linux:  blog-extractor-env/bin/streamlit run streamlit_app.py

COMMAND LINE:
  Windows:    blog-extractor-env\Scripts\python.exe extract.py
  Mac/Linux:  blog-extractor-env/bin/python extract.py

FASTER EXTRACTION (5x speed):
  Add --concurrent 5 to the command

OUTPUT:
  Look in the output/ folder for blog_posts.xml

IMPORT TO WORDPRESS:
  Tools → Import → WordPress → Upload blog_posts.xml
```
