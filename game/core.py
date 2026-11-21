# -*- coding: utf-8 -*-
"""Shared constants, palette, input (mouse + keys), text and save helpers."""
import json
import math
import re
import os
import sys
import pygame

WEB = sys.platform == "emscripten"      # running in a browser (pygbag build)
WEB_KEY = "juanlab-lab-simulator-save"

W, H = 960, 540
FPS = 60
TITLE = "Lab Simulator"

# Juan Lab palette (ligne claire: sand, coral, turquoise, lavender, ink outlines)
PAPER = (248, 243, 234)
PAPER2 = (241, 232, 217)
CARD = (255, 253, 248)
INK = (31, 27, 51)
INK_SOFT = (63, 58, 85)
MUTED = (106, 100, 121)
SAND = (242, 204, 146)
PEACH = (247, 199, 159)
CORAL = (224, 97, 63)
CORAL_D = (194, 78, 47)
SKY = (142, 207, 201)
TURQ = (42, 157, 153)
TEAL = (28, 111, 115)
LAV = (185, 165, 214)
VIOLET = (110, 90, 158)
NIGHT = (34, 29, 59)
WHITE = (255, 255, 255)
GREEN = (86, 170, 92)
RED = (210, 64, 58)
YELLOW = (246, 206, 84)
BLUE = (70, 120, 200)
GEL = (196, 214, 226)
DYE = (92, 70, 170)

# Base colours (Sanger and Illumina conventions)
BASE_COL = {"A": (46, 160, 67), "C": (40, 100, 210), "G": (30, 30, 30), "T": (214, 52, 52), "N": (150, 150, 150)}

KEYMAP = {
    "left": (pygame.K_LEFT, pygame.K_a), "right": (pygame.K_RIGHT, pygame.K_d),
    "up": (pygame.K_UP, pygame.K_w), "down": (pygame.K_DOWN, pygame.K_s),
    "ok": (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER),
    "space": (pygame.K_SPACE,),
    "back": (pygame.K_ESCAPE,),
    "tab": (pygame.K_TAB,),
}


class Input:
    """Keyboard and mouse state for one frame.

    held/pressed: action names from KEYMAP.  keys: raw key codes pressed this frame.
    text: characters typed this frame.  mouse: position in game pixels.
    click / release: left button went down / up this frame.  down: left button held.
    wheel: wheel steps this frame (positive = up)."""
    def __init__(self):
        self.held = set()
        self.pressed = set()
        self.keys = set()
        self.text = ""
        self.mouse = (0, 0)
        self.down = False
        self.click = False
        self.release = False
        self.rclick = False
        self.wheel = 0
        self.moved = 0.0
        self.bot = None  # test hook: callable(inp) that fills the fields itself

    def update(self, events):
        prev_mouse = self.mouse
        self.pressed = set()
        self.keys = set()
        self.text = ""
        self.click = self.release = self.rclick = False
        self.wheel = 0
        if self.bot is not None:
            self.bot(self)
            self.moved = math.dist(prev_mouse, self.mouse)
            return
        kp = pygame.key.get_pressed()
        self.held = {a for a, ks in KEYMAP.items() if any(kp[k] for k in ks)}
        for e in events:
            if e.type == pygame.KEYDOWN:
                self.keys.add(e.key)
                for a, ks in KEYMAP.items():
                    if e.key in ks:
                        self.pressed.add(a)
            elif e.type == pygame.TEXTINPUT:
                self.text += e.text
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1:
                    self.click = True
                    self.down = True
                elif e.button == 3:
                    self.rclick = True
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self.release = True
                self.down = False
            elif e.type == pygame.MOUSEWHEEL:
                self.wheel += e.y
        if not pygame.mouse.get_pressed()[0] and self.down and not self.click:
            self.down = False
            self.release = True
        self.mouse = pygame.mouse.get_pos()
        self.moved = math.dist(prev_mouse, self.mouse)

    def axis(self):
        x = ("right" in self.held) - ("left" in self.held)
        y = ("down" in self.held) - ("up" in self.held)
        return x, y

    def ok(self):
        return "ok" in self.pressed


# ------------------------------------------------------------------ text
_fonts = {}
_NAMES = ["segoeui", "verdana", "helveticaneue", "helvetica", "tahoma", "arial", "dejavusans"]
_MONO = ["consolas", "couriernew", "menlo", "dejavusansmono", "courier"]


def font(size, bold=False, mono=False):
    k = (size, bold, mono)
    if k not in _fonts:
        f = None
        try:
            path = pygame.font.match_font(_MONO if mono else _NAMES, bold=bold)
            if path:
                f = pygame.font.Font(path, size)
        except Exception:
            f = None
        if f is None:
            f = pygame.font.Font(None, int(size * 1.25))
        _fonts[k] = f
    return _fonts[k]


_PRETTY = [(" deg C", " °C"), (" - ", " – "), ("->", "→"), ("x10^4", "×10⁴"), ("x10^6", "×10⁶")]
_UNITS = re.compile(r"(?<=[\d\s(])(uL|ul|ug|uM|um)\b")
_MICRO = {"uL": "µL", "ul": "µL", "ug": "µg", "uM": "µM", "um": "µm"}


def pretty(t):
    for a, b in _PRETTY:
        t = t.replace(a, b)
    if "u" in t:
        t = _UNITS.sub(lambda m: _MICRO[m.group(1)], t)
    return t


_tcache = {}


def text_surf(t, size, color, bold=False, mono=False):
    k = (t, size, color, bold, mono)
    s = _tcache.get(k)
    if s is None:
        if len(_tcache) > 900:
            _tcache.clear()
        s = font(size, bold, mono).render(t, True, color)
        _tcache[k] = s
    return s


def draw_text(surf, t, pos, size=18, color=INK, center=False, bold=False, right=False, mono=False,
              shadow=None, vcenter=False):
    t = pretty(str(t))
    s = text_surf(t, size, color, bold, mono)
    x, y = pos
    if center:
        x -= s.get_width() // 2
    elif right:
        x -= s.get_width()
    if vcenter:
        y -= s.get_height() // 2
    if shadow:
        surf.blit(text_surf(t, size, shadow, bold, mono), (x + 1, y + 2))
    surf.blit(s, (x, y))
    return s.get_width()


def text_w(t, size, bold=False, mono=False):
    return font(size, bold, mono).size(pretty(str(t)))[0]


def wrap(t, size, width, bold=False):
    f = font(size, bold)
    out = []
    for para in pretty(t).split("\n"):
        line = ""
        for word in para.split(" "):
            test = (line + " " + word) if line else word
            if f.size(test)[0] <= width:
                line = test
            else:
                if line:
                    out.append(line)
                line = word
        out.append(line)
    return out


def draw_wrapped(surf, t, pos, size, width, color=INK, bold=False, lh=None, center=False, shadow=None):
    lh = lh or int(size * 1.38)
    x, y = pos
    for ln in wrap(t, size, width, bold):
        draw_text(surf, ln, (x + (width // 2 if center else 0), y), size, color, bold=bold, center=center, shadow=shadow)
        y += lh
    return y


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    t = clamp(t, 0, 1)
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


# ------------------------------------------------------------------ saving
def save_dir():
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = os.environ.get("APPDATA") or os.environ.get("XDG_DATA_HOME") or home
    d = os.path.join(base, "LabSimulator")
    os.makedirs(d, exist_ok=True)
    return d


SAVE_FILE = None


def _path():
    return SAVE_FILE or os.path.join(save_dir(), "save.json")


def new_slot():
    return {"pos": 0, "best": {}, "plays": {}, "facts": [], "coffee": 2, "laps": 0, "rolls": 0,
            "time": 0.0, "done": False, "name": ""}


def default_data():
    return {"slots": [None, None, None], "opt": {"music": 6, "sfx": 7, "full": False, "last": None}}


def _read_save():
    if WEB:
        import platform
        raw = platform.window.localStorage.getItem(WEB_KEY)
        if not raw:
            raise IOError("no save yet")
        return str(raw)
    with open(_path(), "r", encoding="utf-8") as f:
        return f.read()


def load_all():
    data = default_data()
    try:
        d = json.loads(_read_save())
        if isinstance(d.get("slots"), list) and len(d["slots"]) == 3:
            for i, s in enumerate(d["slots"]):
                if s:
                    base = new_slot()
                    base.update(s)
                    data["slots"][i] = base
        data["opt"].update(d.get("opt", {}))
    except Exception:
        pass
    return data


def save_all(data):
    if WEB:
        try:
            import platform
            platform.window.localStorage.setItem(WEB_KEY, json.dumps(data))
            return True
        except Exception:
            return False
    try:
        p = _path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, p)
        return True
    except Exception:
        return False
