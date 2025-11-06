@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo    Blog Extractor - Complete Setup
echo ========================================
echo.

:: Check if Python is installed
echo [1/6] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.8+ from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Display Python version
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found: !PYTHON_VERSION!
echo.

:: Remove old virtual environment if it exists
if exist "blog-extractor-env\" (
    echo Found existing virtual environment. Cleaning up...
    rmdir /s /q "blog-extractor-env" 2>nul
)

:: Create virtual environment
echo [2/6] Creating virtual environment...
python -m venv blog-extractor-env
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment!
    echo.
    echo Try running: python -m pip install --upgrade pip
    pause
    exit /b 1
)
echo Virtual environment created successfully.
echo.

:: Upgrade pip in virtual environment
echo [3/6] Upgrading pip...
blog-extractor-env\Scripts\python.exe -m pip install --upgrade pip --quiet
echo Pip upgraded successfully.
echo.

:: Install Python dependencies
echo [4/6] Installing Python dependencies...
echo This may take a few minutes...
blog-extractor-env\Scripts\python.exe -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies!
    echo.
    echo Check your internet connection and try again.
    pause
    exit /b 1
)
echo Dependencies installed successfully.
echo.

:: Install Playwright browsers
echo [5/6] Installing Playwright browsers...
echo This may take several minutes (downloading ~300MB)...
blog-extractor-env\Scripts\python.exe -m playwright install chromium
if errorlevel 1 (
    echo WARNING: Playwright browser installation failed.
    echo The tool will fall back to basic HTTP requests.
    echo For best results with JavaScript-heavy sites, run:
    echo blog-extractor-env\Scripts\python.exe -m playwright install --with-deps
    echo.
) else (
    echo Playwright browsers installed successfully.
)
echo.

:: Create necessary directories
echo [6/6] Creating output directories...
if not exist "output\" mkdir output
if not exist "output\images\" mkdir output\images
echo Directories created.
echo.

:: Create sample urls.txt if it doesn't exist
if not exist "urls.txt" (
    echo Creating sample urls.txt file...
    echo # Add your blog post URLs here, one per line > urls.txt
    echo # Example: >> urls.txt
    echo # https://example.com/blog/post-1 >> urls.txt
    echo # https://example.com/blog/post-2 >> urls.txt
    echo Sample urls.txt created.
    echo.
)

:: Display completion message
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo.
echo 1. Edit urls.txt and add your blog URLs (one per line)
echo.
echo 2. Run the web UI:
echo    blog-extractor-env\Scripts\streamlit.exe run streamlit_app.py
echo.
echo 3. OR run the CLI:
echo    blog-extractor-env\Scripts\python.exe extract.py
echo.
echo 4. OR use the quick launcher:
echo    run_extractor.bat
echo.
echo ========================================
echo.
pause
