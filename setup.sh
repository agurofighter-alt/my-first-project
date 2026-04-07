#!/bin/bash
# setup.sh — Mac mini initial setup for kindle_capture
# Creates venv, installs dependencies, and compiles ocr_helper.swift

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Kindle Capture Setup ==="

# 1. Python venv
if [ ! -d "venv" ]; then
    echo "[1/3] Creating Python virtual environment..."
    python3 -m venv venv
else
    echo "[1/3] venv already exists, skipping."
fi

echo "[2/3] Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  Installed: $(pip show Pillow 2>/dev/null | grep Version)"

# 2. Compile ocr_helper.swift
echo "[3/3] Compiling ocr_helper.swift..."
swiftc ocr_helper.swift \
    -o ocr_helper \
    -framework Vision \
    -framework AppKit \
    -framework PDFKit \
    -O
echo "  Built: $(file ocr_helper)"

echo ""
echo "=== Setup complete ==="
echo "Run with:"
echo "  source venv/bin/activate"
echo "  python3 kindle_capture.py"
