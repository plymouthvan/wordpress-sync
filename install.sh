#!/bin/bash
# WordPress Sync Installation Script

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "Installing WordPress Sync..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    echo "Please install Python 3 and try again."
    exit 1
fi

# Check if WordPress CLI is installed
if ! command -v wp &> /dev/null; then
    echo "Warning: WordPress CLI (wp) is not installed or not in PATH."
    echo "WordPress Sync requires WordPress CLI to function properly."
    echo "Please install WordPress CLI: https://wp-cli.org/#installing"
fi

# Check if rsync is installed
if ! command -v rsync &> /dev/null; then
    echo "Warning: rsync is not installed or not in PATH."
    echo "WordPress Sync requires rsync to function properly."
    echo "Please install rsync using your package manager."
fi

# Create virtual environment using the built-in venv module
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment and install dependencies
echo "Installing Python dependencies in virtual environment..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Make scripts executable
echo "Making scripts executable..."
chmod +x wordpress_sync.py
chmod +x resources/*.py

# Create wrapper script
echo "Creating wrapper script..."
cat > wordpress-sync << 'EOF'
#!/bin/bash
# WordPress Sync Wrapper Script

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Run the wordpress_sync.py script with all arguments passed to this script
python "$SCRIPT_DIR/wordpress_sync.py" "$@"

# Deactivate virtual environment
deactivate
EOF

# Make wrapper script executable
chmod +x wordpress-sync

# Deactivate virtual environment
deactivate

echo "Installation complete!"
echo ""
echo "To use WordPress Sync, edit the config/config.yaml file with your settings,"
echo "then run: ./wordpress-sync --direction push (or pull)"
echo ""
echo "For more information, see the README.md file."
