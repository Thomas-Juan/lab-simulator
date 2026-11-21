#!/bin/bash
# Runs the game directly with Python (macOS / Linux), without building an app.
cd "$(dirname "$0")"
python3 -m pip install --user pygame-ce numpy >/dev/null 2>&1 || true
python3 game/main.py
