---
paths:
  - "streamlit_app.py"
  - "packages.txt"
---

# Streamlit Cloud

## Deployment Considerations

### Streamlit Cloud

The app automatically installs browsers on first startup.

**Required files:**

- `packages.txt` - System dependencies for browser execution (already included)
- `streamlit_app.py` - Auto-installs browsers on first run (already configured)

**How it works:**

1. App detects Linux environment (Streamlit Cloud)
2. Runs Playwright's own installer, `python -m playwright install chromium`, once per server process
   (`install_playwright_browsers()` is wrapped in `st.cache_resource`, so script reruns skip it)
3. The installer downloads only when the Chromium build the installed playwright package needs is
   missing - no browser revision is hard-coded, so a Playwright upgrade needs no edit here
4. Falls back to requests library if installation fails

**packages.txt contents:** read `packages.txt` itself (one apt package per line).
