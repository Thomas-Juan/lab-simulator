#!/bin/bash
# Builds "Lab Simulator.app" on macOS. Double-click this file in Finder,
# or run:  bash build_mac.command      (needs Python 3.10+: https://www.python.org/downloads/)
set -e
cd "$(dirname "$0")"
python3 -m venv .venv-mac
source .venv-mac/bin/activate
pip install --upgrade pip pygame-ce numpy pyinstaller
pyinstaller --noconfirm --clean --windowed --name "Lab Simulator" \
  --icon "$PWD/game/icon.icns" --add-data "$PWD/game/icon.png:." --add-data "$PWD/game/logo.png:." --add-data "$PWD/game/juanlab.png:." --paths "$PWD/game" --distpath dist-mac --workpath build-mac --specpath build-mac game/main.py
echo
echo "Done: dist-mac/Lab Simulator.app  (drag it to Applications)."
echo "First launch: right-click the app > Open (it is not signed by Apple)."
