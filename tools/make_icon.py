# -*- coding: utf-8 -*-
"""Makes the game's icon and title logo from the logo artwork (needs Pillow).

    logo/emblem.svg, logo/logo.svg   the masters (edit these)
    logo/emblem.png, logo/logo.png   renders of the masters (headless Edge, transparent background)
    game/icon.png, icon.ico, icon.icns, game/logo.png   written by this script

To re-render the PNGs after editing an SVG (Windows):
    msedge --headless=new --disable-gpu --hide-scrollbars --default-background-color=00000000
           --window-size=512,512 --screenshot=logo\\emblem.png logo\\emblem.svg
    (and --window-size=1580,512 for logo.svg)"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the game folder, one level up
LOGO = os.path.join(HERE, "logo")
GAME = os.path.join(HERE, "game")

emblem = Image.open(os.path.join(LOGO, "emblem.png")).convert("RGBA")
emblem.resize((256, 256), Image.LANCZOS).save(os.path.join(GAME, "icon.png"))
emblem.save(os.path.join(GAME, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
emblem.save(os.path.join(GAME, "icon.icns"))
logo = Image.open(os.path.join(LOGO, "logo.png")).convert("RGBA")
w = 600
logo.resize((w, round(logo.height * w / logo.width)), Image.LANCZOS).save(os.path.join(GAME, "logo.png"))
print("wrote game/icon.png, icon.ico, icon.icns and logo.png")
