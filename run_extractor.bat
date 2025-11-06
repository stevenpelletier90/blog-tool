@echo off
echo ========================================
echo    Blog Extractor - Playwright Powered
echo ========================================
echo.
echo Starting blog extraction...
echo.

REM Check if virtual environment exists
if not exist "blog-extractor-env\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Please run setup first or contact support.
    pause
    exit /b 1
)

REM Check if urls.txt exists
if not exist "urls.txt" (
    echo ERROR: urls.txt file not found!
    echo Please create urls.txt with blog URLs (one per line).
    pause
    exit /b 1
)

REM Run the extractor
echo Running extraction...
blog-extractor-env\Scripts\python.exe extract.py

echo.
echo ========================================
echo Extraction complete!
echo.
echo Output files:
echo - output\blog_posts.xml (WordPress XML)
echo - output\extracted_links.txt (All hyperlinks)
echo ========================================
echo.
pause