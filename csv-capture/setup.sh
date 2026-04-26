#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "=== Setting up Emotiv EEG project ==="

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating Python venv..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install hidapi pycryptodome

echo ""
echo "=== Setup complete ==="
echo ""
echo "To activate: source .venv/bin/activate"
echo ""
echo "Usage:"
echo "  python read_raw_eeg.py --list-devices          # Check if dongle is detected"
echo "  python read_raw_eeg.py --serial YOUR_SERIAL     # Stream to stdout"
echo "  python read_raw_eeg.py --serial YOUR_SERIAL -o recording.csv -d 60"
echo ""
echo "The serial number is 16 chars printed on the headset arm."
