#!/usr/bin/env python3
"""
Create distribution-ready zip file for Blog Extractor Tool
Excludes development files, caches, and virtual environments
"""

import zipfile
from pathlib import Path
import sys

# Files and directories to exclude
EXCLUDE_PATTERNS = [
    'blog-extractor-env/',
    '__pycache__/',
    'output/',
    '.git/',
    '.vscode/',
    '.idea/',
    '.claude/',
    '.mypy_cache/',
    '.pytest_cache/',
    '.ruff_cache/',
    '.streamlit/',
    'test-results/',
    'playwright-report/',
    'screenshots/',
    'downloads/',
    '*.pyc',
    '*.pyo',
    '*.pyd',
    '.DS_Store',
    'Thumbs.db',
    '*.log',
    'nul',
    'create_distribution.py',  # Don't include this script
    'blog-extractor-v*.zip',   # Don't include previous zip files
    # Exclude internal/developer documentation (not for end users)
    'CLAUDE.md',           # Internal AI assistant documentation
    'ARCHITECTURE.md',     # Developer documentation
    'CONTRIBUTING.md',     # Developer contribution guide
    'QUICKSTART.md',       # Redundant with simplified README
    'USER_GUIDE.md',       # Will consolidate into README
    'mypy.ini',            # Developer tool config
    'requirements-dev.txt',  # Developer dependencies
]

def should_exclude(file_path: Path) -> bool:
    """Check if file should be excluded from distribution"""
    path_str = file_path.as_posix()

    for pattern in EXCLUDE_PATTERNS:
        if pattern.endswith('/'):
            # Directory exclusion
            if pattern.rstrip('/') in path_str.split('/'):
                return True
        elif pattern.startswith('*'):
            # Extension exclusion
            if file_path.suffix == pattern[1:]:
                return True
        else:
            # Exact match
            if pattern in path_str:
                return True

    return False

def create_distribution_zip():
    """Create the distribution zip file"""
    version = "1.0.0"
    zip_filename = f"blog-extractor-v{version}.zip"
    project_root = Path(__file__).parent
    zip_path = project_root / zip_filename

    print(f"Creating distribution: {zip_filename}")
    print(f"Project root: {project_root}")
    print()

    files_included = []
    files_excluded = []

    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add all files from current directory
        for file_path in project_root.rglob('*'):
            if file_path.is_file():
                # Get relative path
                rel_path = file_path.relative_to(project_root)

                # Skip the zip file itself
                if file_path == zip_path:
                    files_excluded.append(str(rel_path))
                    continue

                if should_exclude(rel_path):
                    files_excluded.append(str(rel_path))
                else:
                    # Add to zip with folder structure
                    arcname = f"blog-extractor-v{version}/{rel_path}"
                    zipf.write(file_path, arcname)
                    files_included.append(str(rel_path))

    print(f"[OK] Distribution created: {zip_filename}")
    print(f"\n[INFO] Files included: {len(files_included)}")
    print(f"[INFO] Files excluded: {len(files_excluded)}")
    print(f"\nZip file size: {Path(zip_filename).stat().st_size / 1024 / 1024:.2f} MB")
    print("\nKey files included:")
    for file in sorted(files_included)[:20]:
        print(f"  - {file}")
    if len(files_included) > 20:
        print(f"  ... and {len(files_included) - 20} more files")

    return zip_filename

if __name__ == "__main__":
    try:
        zip_file = create_distribution_zip()
        print(f"\n[SUCCESS] Distribution ready for sharing: {zip_file}")
        print("\nTo distribute:")
        print("  1. Share this zip file with users")
        print("  2. Users extract the zip")
        print("  3. Users run setup.bat (Windows) or bash setup.sh (Mac/Linux)")
        print("  4. Everything installs automatically!")
    except Exception as e:
        print(f"[ERROR] Error creating distribution: {e}", file=sys.stderr)
        sys.exit(1)
