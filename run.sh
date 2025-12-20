#!/bin/bash
# Brother QL Label Printer - GUI Launcher

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if venv exists, create if not
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment with uv..."
    uv venv
fi

# Install/update dependencies with uv
echo "Installing dependencies with uv..."
uv pip install -r requirements.txt

# Run the GUI
exec .venv/bin/python3 app/label_printer_gui.py "$@"
