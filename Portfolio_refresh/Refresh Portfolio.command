#!/bin/bash
# ── Portfolio Live Refresh ────────────────────────────────────────────────────
# Double-click this file on Mac to refresh your portfolio prices.
# If it doesn't open as a script: right-click → Open With → Terminal

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "================================================"
echo "================================================"
echo ""

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo " ERROR: Python 3 not found."
    echo ""
    echo " Install via: brew install python"
    echo " Or download from https://www.python.org/downloads/"
    echo ""
    read -p " Press Enter to close..."
    exit 1
fi

# Install required packages if missing
echo " Checking required packages..."
python3 -c "import requests" 2>/dev/null || pip3 install requests --quiet
python3 -c "import openpyxl" 2>/dev/null || pip3 install openpyxl --quiet
echo " Packages OK."
echo ""

# Run the refresh script
cd "$SCRIPT_DIR"
python3 refresh_portfolio.py

read -p " Press Enter to close..."
