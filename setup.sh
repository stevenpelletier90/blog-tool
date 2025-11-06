#!/bin/bash

set -e  # Exit on error

echo "========================================"
echo "   Blog Extractor - Complete Setup"
echo "========================================"
echo ""

# Check if Python is installed
echo "[1/6] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo ""
    echo "Please install Python 3.8+ using:"
    echo "  macOS: brew install python3"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "  Fedora: sudo dnf install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "Found: $PYTHON_VERSION"
echo ""

# Remove old virtual environment if it exists
if [ -d "blog-extractor-env" ]; then
    echo "Found existing virtual environment. Cleaning up..."
    rm -rf blog-extractor-env
fi

# Create virtual environment
echo "[2/6] Creating virtual environment..."
python3 -m venv blog-extractor-env
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment!"
    echo ""
    echo "Try running: python3 -m pip install --upgrade pip"
    exit 1
fi
echo "Virtual environment created successfully."
echo ""

# Upgrade pip in virtual environment
echo "[3/6] Upgrading pip..."
blog-extractor-env/bin/python -m pip install --upgrade pip --quiet
echo "Pip upgraded successfully."
echo ""

# Install Python dependencies
echo "[4/6] Installing Python dependencies..."
echo "This may take a few minutes..."
blog-extractor-env/bin/python -m pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies!"
    echo ""
    echo "Check your internet connection and try again."
    exit 1
fi
echo "Dependencies installed successfully."
echo ""

# Install Playwright browsers
echo "[5/6] Installing Playwright browsers..."
echo "This may take several minutes (downloading ~300MB)..."
blog-extractor-env/bin/python -m playwright install chromium

if [ $? -ne 0 ]; then
    echo "WARNING: Playwright browser installation failed."
    echo "The tool will fall back to basic HTTP requests."
    echo "For best results with JavaScript-heavy sites, run:"
    echo "blog-extractor-env/bin/python -m playwright install --with-deps"
    echo ""
else
    echo "Playwright browsers installed successfully."
fi
echo ""

# Create necessary directories
echo "[6/6] Creating output directories..."
mkdir -p output/images
echo "Directories created."
echo ""

# Create sample urls.txt if it doesn't exist
if [ ! -f "urls.txt" ]; then
    echo "Creating sample urls.txt file..."
    cat > urls.txt << 'EOF'
# Add your blog post URLs here, one per line
# Example:
# https://example.com/blog/post-1
# https://example.com/blog/post-2
EOF
    echo "Sample urls.txt created."
    echo ""
fi

# Make the script executable
chmod +x setup.sh 2>/dev/null || true

# Display completion message
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit urls.txt and add your blog URLs (one per line)"
echo ""
echo "2. Run the web UI:"
echo "   blog-extractor-env/bin/streamlit run streamlit_app.py"
echo ""
echo "3. OR run the CLI:"
echo "   blog-extractor-env/bin/python extract.py"
echo ""
echo "========================================"
echo ""
