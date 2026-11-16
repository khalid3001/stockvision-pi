#!/usr/bin/env bash
# One-time setup on a Raspberry Pi (Raspberry Pi OS Bookworm or newer, 64-bit).
# Run from the project folder:  bash scripts/pi_setup.sh
set -e
cd "$(dirname "$0")/.."

# picamera2 comes from the operating system, not from pip.
sudo apt update
sudo apt install -y python3-picamera2 python3-venv libgl1 libglib2.0-0

# --system-site-packages lets the virtual environment see the system's picamera2.
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/init_db.py

echo
echo "Done. Test the camera:   .venv/bin/python scripts/capture.py --photo-only"
echo "Start the dashboard:     make pi-dashboard"
