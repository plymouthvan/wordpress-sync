#!/bin/bash
# WordPress Sync Uninstall Script

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "WordPress Sync Uninstaller"
echo "=========================="
echo "This script will remove WordPress Sync components installed by the install.sh script."
echo "Source code files will remain intact."
echo ""

# Confirmation prompt
read -p "Are you sure you want to uninstall WordPress Sync? (y/n): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

# Check if we're in the correct directory
if [ ! -f "wordpress_sync.py" ] || [ ! -d "resources" ]; then
    echo "Error: This script must be run from the WordPress Sync installation directory."
    echo "Current directory: $(pwd)"
    exit 1
fi

# Option to preserve config
read -p "Would you like to keep your configuration files? (y/n): " keep_config
echo ""

# Remove virtual environment
if [ -d "venv" ]; then
    echo "Removing virtual environment..."
    rm -rf venv
fi

# Remove wrapper script
if [ -f "wordpress-sync" ]; then
    echo "Removing wrapper script..."
    rm wordpress-sync
fi

# Remove configuration files if not preserved
if [[ "$keep_config" != "y" && "$keep_config" != "Y" ]]; then
    echo "Removing configuration files..."
    # Remove any generated config files but keep the sample
    find config -type f -not -name "*.sample" -delete
else
    echo "Keeping configuration files..."
fi

# Remove any potential cache or temporary files
echo "Cleaning up any temporary files..."
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -delete
find . -name "*.pyo" -delete
find . -name "*.pyd" -delete
find . -name ".DS_Store" -delete

echo ""
echo "Uninstallation complete!"
echo ""
echo "The following components have been removed:"
echo "- Virtual environment (venv/)"
echo "- Wrapper script (wordpress-sync)"
if [[ "$keep_config" != "y" && "$keep_config" != "Y" ]]; then
    echo "- Configuration files"
fi
echo "- Temporary and cache files"
echo ""
echo "Source code files have been preserved. To completely remove WordPress Sync,"
echo "you can delete this directory."
echo ""
