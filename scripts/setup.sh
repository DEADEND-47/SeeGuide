#!/usr/bin/env bash
# SeeGuide Environment Setup Script for Linux/macOS
set -euo pipefail

echo "===================================================================="
echo "Setting up SeeGuide Environment..."
echo "===================================================================="

PYTHON_CMD="python3"
if ! command -v "$PYTHON_CMD" &> /dev/null; then
    PYTHON_CMD="python"
fi

echo "[*] Creating virtual environment (.venv)..."
"$PYTHON_CMD" -m venv .venv

echo "[*] Activating virtual environment..."
source .venv/bin/activate

echo "[*] Upgrading pip..."
pip install --upgrade pip

echo "[*] Installing pinned requirements from requirements.txt..."
pip install -r requirements.txt

echo "[*] Running environment verification..."
python scripts/check_environment.py

echo "[*] Running contract validation..."
python scripts/validate_contracts.py

echo "===================================================================="
echo "SeeGuide setup complete! Activate with: source .venv/bin/activate"
echo "===================================================================="
