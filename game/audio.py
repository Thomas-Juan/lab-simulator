# -*- coding: utf-8 -*-
"""Procedural music and sound effects (numpy synthesis, no asset files).

Every technique has its own track. A track is 32 bars long and arranged like a real
piece: an intro (drums and bass come in), the main theme, a breakdown that builds back
up with a snare roll and a riser, and a fuller reprise; then it loops seamlessly.
Instruments are synthesised from filtered harmonics (saw leads, plucks, electric piano,
brass, strings, supersaw pads, sub and reese basses), the drum kit is synthesised too,
and the mix has side-chain pumping on the pads and bass, stereo placement and reverb."""
import math
import random
import sys
import threading
import pygame

WEB = sys.platform == "emscripten"

try:
    import numpy as np
except Exception:  # pragma: no cover - audio is simply disabled without numpy
    np = None

TUNE_HELP = """music = dict(
    name  = "Thermal Cycle",     # title shown at the station
    genre = "funk",              # funk house trance dnb breakbeat halftime shuffle jazzfunk cinematic latin minimal downtempo ambient
    bpm   = 116,
    root  = 50,                  # MIDI note of the key centre (45-57)
    mode  = "dor",               # maj min dor mix phr lyd harm blues
    prog  = [0, 3, 4, 0, 5, 3, 4, 4],   # 8 chord roots as scale degrees (0 = tonic)
    lead  = "keys",              # saw lead_soft brass pluck keys organ strings
    swing = 0.0,                 # 0 (straight) to 0.33
    motif = [(0, 2), (2, 1), (4, 1), (7, 4)],   # optional hook: (scale degree, length in eighths)
)"""

RATE = 44100
ok = False
_sfx = {}
_tunes = {}
_specs = {}
_lock = threading.Lock()
_cur = None
DEBUG = False
_ch = []
_chi = 0
vol_music, vol_sfx = 0.6, 0.7


def init():
    global ok, _ch, RATE
    if np is None:
        return
    try:
        pygame.mixer.quit()
        pygame.mixer.init(22050 if WEB else 44100, -16, 2, 1024)
        RATE = pygame.mixer.get_init()[0]
        pygame.mixer.set_num_channels(16)
        _ch = [pygame.mixer.Channel(0), pygame.mixer.Channel(1)]
        pygame.mixer.set_reserved(2)
        ok = True
        _build_sfx()
        if not WEB:
            threading.Thread(target=_precompose, daemon=True).start()
    except Exception:
        ok = False


def register(key, spec):
    """Make a tune spec known under key (techniques register theirs at start-up)."""
    _specs[key] = spec


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


# ================================================================== instruments
# parts: harmonics; law: amplitude falls as 1/k**law; det: detune of the second (third) voice;
# voices; b0 -> b1 over bt seconds: filter brightness (1 = open); att/dec/sus/rel: amplitude envelope;
# vib: vibrato depth (fraction of pitch); sub: level of a sine one octave down (basses)
INSTR = {
    "saw":       dict(parts=16, law=1.0, det=0.006, voices=2, b0=0.95, b1=0.5, bt=0.22, att=0.008, dec=0.35, sus=0.75, rel=0.09, vib=0.0035),
    "lead_soft": dict(parts=9, law=1.5, det=0.004, voices=2, b0=0.75, b1=0.5, bt=0.3, att=0.025, dec=0.5, sus=0.8, rel=0.12, vib=0.005),
    "brass":     dict(parts=14, law=1.05, det=0.005, voices=2, b0=0.25, b1=0.75, bt=0.07, att=0.035, dec=0.4, sus=0.8, rel=0.1, vib=0.003),
    "pluck":     dict(parts=14, law=1.0, det=0.003, voices=2, b0=1.0, b1=0.12, bt=0.13, att=0.002, dec=0.28, sus=0.0, rel=0.05, vib=0.0),
    "strings":   dict(parts=12, law=1.1, det=0.007, voices=2, b0=0.5, b1=0.55, bt=0.5, att=0.28, dec=1.0, sus=0.9, rel=0.45, vib=0.004),
    "pad":       dict(parts=9, law=1.0, det=0.009, voices=2, b0=0.32, b1=0.4, bt=1.2, att=0.45, dec=1.0, sus=0.9, rel=0.6, vib=0.0),
    "bass":      dict(parts=10, law=1.0, det=0.0, voices=1, b0=0.75, b1=0.22, bt=0.09, att=0.004, dec=0.3, sus=0.55, rel=0.05, vib=0.0, sub=0.7),
    "reese":     dict(parts=10, law=1.0, det=0.011, voices=2, b0=0.42, b1=0.42, bt=0.5, att=0.01, dec=1.0, sus=1.0, rel=0.08, vib=0.0, sub=0.6),
    "organ":     dict(parts=0, att=0.008, dec=1.0, sus=0.95, rel=0.05),
    "keys":      dict(parts=0, att=0.003, dec=1.4, sus=0.0, rel=0.12),
}
LEAD_MAP = {"epiano": "keys", "bell": "keys", "vibes": "keys", "flute": "lead_soft", "whistle": "lead_soft",
            "marimba": "pluck", "harpsi": "pluck", "sitar": "pluck", "synth": "saw", "square": "saw"}
_ncache = {}


def _env(n, att, dec, sus, rel):
    t = np.arange(n, dtype=np.float32) / RATE
    env = np.minimum(t / max(att, 1e-4), 1.0) * (sus + (1 - sus) * np.exp(-np.maximum(t - att, 0) / max(dec, 1e-4)))
    r = min(n, max(1, int(rel * RATE)))
    env[-r:] *= np.linspace(1, 0, r, dtype=np.float32)
    return env, t


def note(inst, midi, n, variant=0):
    """One note as a float32 array of n samples (cached)."""
    key = (inst, midi, n, variant)
    w = _ncache.get(key)
    if w is not None:
        return w
    p = INSTR[inst]
    f = hz(midi)
    env, t = _env(n, p["att"], p["dec"], p["sus"], p["rel"])
    if inst == "keys":        # electric piano: sine body, soft 2nd harmonic, quick bright tine, slow tremolo
        ph = 2 * np.pi * f * t
        w = (np.sin(ph) + 0.32 * np.sin(2 * ph) * np.exp(-t / 0.6) + 0.18 * np.sin(3 * ph) * np.exp(-t / 0.25)
             + 0.25 * np.sin(14.0 * ph) * np.exp(-t / 0.03)) * (1 + 0.06 * np.sin(2 * np.pi * 4.5 * t))
        w = w * env / 1.4
    elif inst == "organ":
        ph = 2 * np.pi * f * t
        w = sum(a * np.sin(k * ph) for k, a in ((0.5, 0.45), (1, 1), (2, 0.55), (3, 0.3), (4, 0.22), (6, 0.12), (8, 0.08)))
        w = w * env * (1 + 0.05 * np.sin(2 * np.pi * 6.0 * t)) / 2.2
    else:
        bri = p["b1"] + (p["b0"] - p["b1"]) * np.exp(-t / max(p["bt"], 1e-3))
        damp = (1.0 - np.clip(bri, 0, 1)) * 0.5
        w = np.zeros(n, dtype=np.float32)
        rng = random.Random(variant * 7 + midi)
        voices = p["voices"]
        for v in range(voices):
            dv = 0.0 if voices == 1 else (p["det"] * (1 if v == 0 else -1) * (1 + 0.3 * variant))
            ph = 2 * np.pi * f * (1 + dv) * t + rng.uniform(0, 6.28)
            if p["vib"]:
                ph = ph + (p["vib"] * f / 5.2) * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t * 2.5)
            for k in range(1, p["parts"] + 1):
                if k * f > RATE * 0.42:
                    break
                w += (1.0 / k ** p["law"]) * np.exp(-(k - 1) * damp) * np.sin(k * ph)
        if p.get("sub"):
            w += p["sub"] * 1.6 * np.sin(np.pi * f * t)
        w = w * env / (voices * 2.2)
    w = w.astype(np.float32)
    _ncache[key] = w
    return w


# ================================================================== drum kit
def _kit():
    rng = np.random.default_rng(5)

    def t(n):
        return np.arange(n, dtype=np.float32) / RATE

    def noise(n):
        return rng.standard_normal(n).astype(np.float32)

    def hp(x, k=2):
        """High-passed noise, then softened (3-tap average) so it hisses less; unit-ish level."""
        for _ in range(k):
            x = np.diff(x, prepend=0)
        x = np.convolve(x, np.array([0.15, 0.7, 0.15], dtype=np.float32), mode="same")
        return x / (1.0 + k)
    d = {}
    n = int(0.42 * RATE)
    tt = t(n)
    sweep = 44 * tt + (150 - 44) * 0.045 * (1 - np.exp(-tt / 0.045))
    d["kick"] = np.tanh(1.6 * np.sin(2 * np.pi * sweep) * np.exp(-tt / 0.22)) + 0.35 * hp(noise(n), 1) * np.exp(-tt / 0.004)
    n = int(0.32 * RATE)
    tt = t(n)
    body = 0.55 * np.sin(2 * np.pi * 185 * tt) * np.exp(-tt / 0.05) + 0.3 * np.sin(2 * np.pi * 330 * tt) * np.exp(-tt / 0.03)
    d["snare"] = body + 0.45 * hp(noise(n), 1) * np.exp(-tt / 0.11)
    n = int(0.25 * RATE)
    tt = t(n)
    cl = hp(noise(n), 1) * np.exp(-tt / 0.08)
    for k in (0.009, 0.019, 0.028):
        s = int(k * RATE)
        cl[s:] += hp(noise(n - s), 1) * 0.8 * np.exp(-t(n - s) / 0.01)
    d["clap"] = cl * 0.5
    metal = lambda n: sum(np.sin(2 * np.pi * fq * t(n)) + 0.3 * np.sin(2 * np.pi * 3 * fq * t(n)) for fq in (3140, 4410, 5870, 7020, 8130, 9450)) / 8.0
    n = int(0.07 * RATE)
    d["hat"] = (0.6 * hp(noise(n), 2) + 0.4 * metal(n)) * 0.35 * np.exp(-t(n) / 0.018)
    n = int(0.4 * RATE)
    d["ohat"] = (0.6 * hp(noise(n), 2) + 0.4 * metal(n)) * 0.3 * np.exp(-t(n) / 0.16)
    n = int(1.8 * RATE)
    d["crash"] = (0.7 * hp(noise(n), 2) + 0.3 * metal(n)) * 0.42 * np.exp(-t(n) / 0.6)
    n = int(0.9 * RATE)
    rd = metal(n) * 0.5 + 0.2 * hp(noise(n), 2)
    d["ride"] = rd * 0.22 * np.exp(-t(n) / 0.35) + 0.15 * np.sin(2 * np.pi * 620 * t(n)) * np.exp(-t(n) / 0.2)
    for name, f0 in (("tlo", 92), ("tmid", 132), ("thi", 180)):
        n = int(0.45 * RATE)
        tt = t(n)
        d[name] = np.sin(2 * np.pi * (f0 * tt + f0 * 0.6 * 0.05 * (1 - np.exp(-tt / 0.05)))) * np.exp(-tt / 0.18) * 0.8
    n = int(0.06 * RATE)
    d["rim"] = (np.sin(2 * np.pi * 1750 * t(n)) * 0.6 + np.sin(2 * np.pi * 2600 * t(n)) * 0.3) * np.exp(-t(n) / 0.012) * 0.6
    n = int(0.09 * RATE)
    d["shaker"] = hp(noise(n), 2) * 0.22 * np.sin(np.pi * np.minimum(1, t(n) / 0.09)) ** 2
    n = int(0.04 * RATE)
    d["tick"] = np.sin(2 * np.pi * 3300 * t(n)) * np.exp(-t(n) / 0.006) * 0.5
    n = int(0.32 * RATE)
    tt = t(n)
    d["conga"] = np.sin(2 * np.pi * (230 * tt + 70 * 0.02 * (1 - np.exp(-tt / 0.02)))) * np.exp(-tt / 0.1) * 0.7
    return {k: v.astype(np.float32) for k, v in d.items()}


def _riser(n):
    """Noise that rises in brightness and level over n samples (the build before a drop)."""
    rng = np.random.default_rng(9)
    x = rng.standard_normal(n).astype(np.float32)
    f = np.linspace(0, 1, n, dtype=np.float32)
    lo = np.cumsum(x) / 40.0
    lo -= np.convolve(lo, np.ones(400, dtype=np.float32) / 400, mode="same")
    hi = np.diff(x, prepend=0)
    return ((1 - f) * lo + f * hi) * f ** 2 * 0.35


# ================================================================== grooves, bass lines, genres
# drum patterns on a 16-step bar: X = accent, x = normal, o = ghost, . = rest
GROOVES = {
    "drive":     dict(kick="X...X...X...X...", snare="....X.......X...", hat="x.o.x.o.x.o.x.ox", ohat="..x...x...x...x."),
    "house":     dict(kick="X...X...X...X...", clap="....X.......X...", hat="o.o.o.o.o.o.o.o.", ohat="..X...X...X...X.", shaker="oooooooooooooooo"),
    "funk":      dict(kick="X..x..X...X..x..", snare="....X..o.o..X..o", hat="xoxoxoxoxoxoxoxo", ohat="..............x."),
    "dnb":       dict(kick="X.........X.....", snare="....X.......X...", hat="x.x.x.x.x.x.x.x.", ghost="..o....o..o..o..", ride="x...x...x...x..."),
    "break":     dict(kick="X.....x...X.....", snare="....X.......X..o", hat="x.xox.xox.xox.xo"),
    "halftime":  dict(kick="X.......x.X.....", snare="........X.......", hat="x.x.x.x.x.x.x.x.", rim="......o.......o."),
    "shuffle":   dict(kick="X.....X.X.......", snare="....X.......X...", hat="x.x.x.x.x.x.x.x."),
    "jazz":      dict(ride="X..xX..xX..xX..x", kick="o.......o.......", ghost="......o.......o.", hat="....x.......x..."),
    "cinematic": dict(kick="X.......X.......", snare="....X.......X...", tlo="..o...o...o.o.o.", tmid="..............x."),
    "latin":     dict(kick="X..x..X.X..x..X.", conga="..x.x..x..x.xx.x", rim="X..X..X...X.X...", shaker="oooooooooooooooo", hat="..o...o...o...o."),
    "tick":      dict(tick="x.x.x.x.x.x.x.x.", kick="X.......X.......", rim="....x.......x..."),
    "trip":      dict(kick="X......x..X.....", snare="....X.......X...", hat="o.o.o.o.o.o.o.o.", rim="...o.......o...."),
    "ambient":   dict(kick="X.........x.....", shaker="o.o.o.o.o.o.o.o.", rim="........o......."),
}
DRUM_GAIN = dict(kick=0.5, snare=0.46, clap=0.44, hat=0.8, ohat=0.6, ride=0.7, ghost=0.18, rim=0.3, tlo=0.32, tmid=0.3,
                 thi=0.3, conga=0.32, shaker=0.6, tick=0.35, crash=0.55)
VEL = {"X": 1.0, "x": 0.72, "o": 0.42}

# bass lines: (step, length in steps, interval: 0 root, 7 octave, 4 fifth, 2 third)
BASS = {
    "funk":     [(0, 2, 0), (3, 1, 7), (6, 2, 0), (8, 1, 0), (10, 2, 4), (13, 1, 7), (14, 2, 0)],
    "offbeat":  [(2, 2, 0), (6, 2, 0), (10, 2, 0), (14, 2, 7)],
    "rolling":  [(s, 1, 0 if s % 4 != 3 else 7) for s in range(16) if s % 4 != 0],
    "reese":    [(0, 8, 0), (8, 6, 0), (14, 2, 4)],
    "syncop":   [(0, 3, 0), (3, 3, 0), (6, 2, 7), (10, 2, 0), (12, 4, 4)],
    "long":     [(0, 12, 0), (12, 4, 4)],
    "walk":     [(0, 4, 0), (4, 4, 2), (8, 4, 4), (12, 4, 5)],
    "ostinato": [(s, 2, 0 if s % 4 == 0 else (7 if s % 8 == 2 else 4)) for s in range(0, 16, 2)],
    "tumbao":   [(3, 3, 0), (6, 2, 4), (11, 3, 0), (14, 2, 4)],
    "pulse":    [(s, 2, 0) for s in range(0, 16, 2)],
}
GENRES = {
    #             drums        bass        chords     arp    pad   bass sound
    "funk":      ("funk",      "funk",     "stab",    False, True, "bass"),
    "house":     ("house",     "offbeat",  "stab",    True,  True, "bass"),
    "trance":    ("drive",     "rolling",  "pad",     True,  True, "bass"),
    "dnb":       ("dnb",       "reese",    "pad",     True,  True, "reese"),
    "breakbeat": ("break",     "syncop",   "stab",    True,  True, "bass"),
    "halftime":  ("halftime",  "long",     "pad",     True,  True, "reese"),
    "shuffle":   ("shuffle",   "walk",     "comp",    False, False, "bass"),
    "jazzfunk":  ("jazz",      "walk",     "comp",    False, True, "bass"),
    "cinematic": ("cinematic", "ostinato", "strings", True,  True, "bass"),
    "latin":     ("latin",     "tumbao",   "stab",    True,  True, "bass"),
    "minimal":   ("tick",      "pulse",    "pad",     True,  True, "bass"),
    "downtempo": ("trip",      "long",     "keys",    False, True, "bass"),
    "ambient":   ("ambient",   "long",     "pad",     True,  True, "reese"),
}
OLD_DRUMS = {"funk": "funk", "disco": "house", "techno": "trance", "dnb": "dnb", "latin": "latin", "march": "cinematic",
             "shuffle": "shuffle", "tick": "minimal", "rock": "breakbeat", "soft": "downtempo", "tabla": "halftime", "none": "ambient"}
MODES = {
    "maj": [0, 2, 4, 5, 7, 9, 11], "min": [0, 2, 3, 5, 7, 8, 10], "dor": [0, 2, 3, 5, 7, 9, 10],
    "mix": [0, 2, 4, 5, 7, 9, 10], "phr": [0, 1, 3, 5, 7, 8, 10], "lyd": [0, 2, 4, 6, 7, 9, 11],
    "harm": [0, 2, 3, 5, 7, 8, 11], "pent": [0, 2, 3, 5, 7, 9, 10], "blues": [0, 2, 3, 5, 7, 9, 10],
}
CELLS = [[4, 2, 2, 4, 4], [3, 3, 2, 4, 4], [2, 2, 4, 2, 2, 4], [6, 2, 4, 4], [3, 3, 4, 2, 2, 2],
         [4, 4, 8], [2, 4, 2, 4, 4], [8, 4, 4], [3, 3, 3, 3, 4], [2, 2, 2, 2, 8]]

BUILTIN = {
    "title":   dict(name="Lab Simulator", genre="cinematic", bpm=100, root=50, mode="min", prog=[0, 5, 2, 6, 0, 5, 3, 4], lead="strings",
                    motif=[(0, 2), (4, 2), (7, 4), (6, 2), (4, 2), (5, 4)]),
    "board":   dict(name="Lab floor", genre="downtempo", bpm=92, root=52, mode="dor", prog=[0, 3, 6, 4, 0, 3, 2, 4], lead="keys"),
    "results": dict(name="Results", genre="house", bpm=122, root=53, mode="mix", prog=[0, 6, 3, 4, 0, 6, 3, 4], lead="saw"),
}


def _spec(key):
    sp = dict(bpm=110, root=50, mode="dor", prog=[0, 3, 4, 0, 5, 3, 4, 4], lead="saw", swing=0.0)
    src = dict(_specs.get(key) or BUILTIN.get(key) or {})
    sp.update(src)
    if "genre" not in src:
        sp["genre"] = OLD_DRUMS.get(src.get("drums", ""), "downtempo")
    sp["lead"] = LEAD_MAP.get(sp["lead"], sp["lead"])
    if sp["lead"] not in INSTR:
        sp["lead"] = "saw"
    if sp["mode"] not in MODES:
        sp["mode"] = "dor"
    return sp


# ================================================================== composition
def _melody(rnd, mode, prog, motif, bars, start_bar, octave_bias=0):
    """A lead line for `bars` bars as (step, length, scale degree), in 4-bar phrases (call, answer,
    call varied, cadence), landing on chord tones on strong beats."""
    n = len(mode)
    out = []
    deg = rnd.choice([0, 2, 4])
    cells = rnd.sample(CELLS, 3)
    hook = []
    if motif:
        pos = 0
        for d, ln in motif:
            hook.append((pos, ln * 2, d))
            pos += ln * 2
    for b in range(bars):
        bar = start_bar + b
        chord = prog[bar % 8]
        tones = {(chord + i) % n for i in (0, 2, 4)}
        phrase_pos = b % 4
        if b < 2 and hook:
            for pos, ln, d in hook:
                if b * 16 <= pos < (b + 1) * 16:
                    out.append((bar * 16 + pos - b * 16, min(ln, (b + 1) * 16 - pos), d + octave_bias * n))
                    deg = d
            continue
        if phrase_pos == 3:
            rh = [6, 2, 8] if rnd.random() < 0.5 else [4, 4, 8]
        else:
            rh = cells[0] if phrase_pos in (0, 2) else cells[1 + (b // 4) % 2]
        pos = 0
        for i, ln in enumerate(rh):
            strong = pos % 8 == 0 or (pos % 4 == 0 and ln >= 4)
            step = rnd.choice([1, 1, 1, 2, 2, 3, -1, -1, -2])
            c = deg + step
            if strong or (phrase_pos == 3 and i == len(rh) - 1):
                for off in (0, 1, -1, 2, -2):
                    if (c + off) % n in tones:
                        c += off
                        break
            if c > n + 4:
                c -= n
            if c < -2:
                c += n
            if not (ln <= 2 and not strong and rnd.random() < 0.15):
                out.append((bar * 16 + pos, ln, c + octave_bias * n))
            deg = c
            pos += ln
    return out


def _compose(key):
    sp = _spec(key)
    drums_name, bass_style, chord_style, use_arp, use_pad, bass_inst = GENRES.get(sp["genre"], GENRES["downtempo"])
    groove = GROOVES[drums_name]
    mode = MODES[sp["mode"]]
    prog = [p % len(mode) for p in sp["prog"]]
    prog_b = prog[4:] + prog[:4]                      # the breakdown runs the progression from its middle
    n = len(mode)
    root = sp["root"]
    bpm = sp["bpm"]
    swing = sp.get("swing", 0.0)
    rnd = random.Random("labsim2-" + str(key))
    BARS = 32
    step = RATE * 60.0 / bpm / 4                       # samples per 16th
    total = int(round(step * 16 * BARS))
    pad_len = RATE * 3
    L = {k: np.zeros(total + pad_len, dtype=np.float32) for k in ("lead", "chords", "arp", "pad", "bass", "drums", "send")}
    kicks = []

    def at(s):
        whole = int(math.floor(s))
        frac = s - whole
        if swing and frac == 0:
            if drums_name in ("shuffle", "jazz") and whole % 4 == 2:
                s += swing * 2
            elif drums_name not in ("shuffle", "jazz") and whole % 2 == 1:
                s += swing
        return int(s * step)

    def sem(d):
        return mode[d % n] + 12 * (d // n)

    def put(bus, w, s, gain, send=0.0):
        i = at(s)
        seg = w[:max(0, len(L[bus]) - i)]
        L[bus][i:i + len(seg)] += seg * gain
        if send:
            L["send"][i:i + len(seg)] += seg * gain * send

    def play(bus, inst, d, octv, s, ln, gain, send=0.0, variant=0):
        m = root + sem(d) + 12 * octv
        w = note(inst, m, max(96, int(ln * step * 0.97)), variant)
        put(bus, w, s, gain, send)

    kit = _kit()

    def hit(name, s, gain, send=0.0):
        put("drums", kit[name], s, gain * DRUM_GAIN.get(name, 0.5), send)
        if name == "kick":
            kicks.append(at(s))

    lead = sp["lead"]
    lead_oct = 1 if lead in ("saw", "lead_soft", "brass", "strings") else 1
    # ---- lead melodies: theme in bars 8-15, reprise in 24-31 (doubled an octave down), counter line in the breakdown
    theme = _melody(rnd, mode, prog, sp.get("motif"), 8, 8)
    for s, ln, d in theme:
        play("lead", lead, d, lead_oct, s, ln, 0.6, 0.3)
    for s, ln, d in theme:
        s2 = s + 16 * 16
        play("lead", lead, d, lead_oct, s2, ln, 0.55, 0.3)
        play("lead", lead, d, lead_oct - 1, s2, ln, 0.28, 0.2, variant=1)
    counter = _melody(random.Random("c" + str(key)), mode, prog_b, None, 8, 16, 0)
    for s, ln, d in counter:
        if s >= 20 * 16:
            play("lead", "strings" if lead != "strings" else "keys", d, 0, s, max(ln, 4), 0.3, 0.4)
    # ---- harmony, bass, arpeggio and drums bar by bar
    for bar in range(BARS):
        sec = bar // 8                                  # 0 intro, 1 theme, 2 breakdown, 3 reprise
        P = prog_b if sec == 2 else prog
        c = P[bar % 8]
        b0 = bar * 16
        chord = [c, c + 2, c + 4, c + 6]                # seventh chords
        if use_pad:
            for k, d in enumerate(chord):
                g = 0.11 if sec != 2 else 0.16
                play("pad", "pad", d, 0, b0, 16, g, 0.25, variant=k % 2)
        if sec in (1, 3) or (sec == 2 and bar >= 20):
            if chord_style == "stab":
                for st_ in ((2, 6, 10, 14) if drums_name in ("house", "latin") else (3, 10) if drums_name == "funk" else (0, 6, 10)):
                    for d in chord:
                        play("chords", "keys" if lead != "keys" else "pluck", d, 1, b0 + st_, 2, 0.14, 0.2)
            elif chord_style == "comp":
                for st_ in (4, 12):
                    for d in chord:
                        play("chords", "keys", d, 1, b0 + st_ + (1 if bar % 2 else 0), 3, 0.13, 0.2)
            elif chord_style == "keys":
                for st_ in (0, 8):
                    for d in chord:
                        play("chords", "keys", d, 1, b0 + st_, 8, 0.13, 0.25)
            elif chord_style == "strings":
                for d in chord[:3]:
                    play("chords", "strings", d, 1, b0, 16, 0.12, 0.3)
        if bar >= 4 and not (sec == 2 and bar < 20 and bass_style not in ("long", "reese")):
            for s0, ln, iv in BASS[bass_style]:
                d = c + {0: 0, 7: n, 4: 4, 2: 2, 5: 5}.get(iv, 0)
                play("bass", bass_inst, d, -2 if bass_inst == "reese" else -1, b0 + s0, ln, 0.38)
        if use_arp and (sec in (1, 3) or bar >= 4 and sec == 0 or bar >= 20):
            pat = [0, 1, 2, 3, 2, 1, 0, 1][:8]
            g = 0.09 if sec == 0 else 0.12
            for i in range(16):
                d = chord[pat[i % 8] % 4] + (n if i % 8 >= 4 else 0)
                play("arp", "pluck", d, 1, b0 + i, 1, g, 0.35, variant=i % 2)
        # drums
        light = (sec == 0 and bar < 4) or (sec == 2 and bar < 20)
        for name, pat in groove.items():
            if light and name not in ("hat", "shaker", "rim", "tick", "ride", "kick"):
                continue
            if sec == 2 and bar < 20 and name == "kick":
                pat = "X..............."
            for i, ch in enumerate(pat):
                if ch != ".":
                    nm = "snare" if name == "ghost" else name
                    hit(nm, b0 + i, VEL[ch] * (0.75 if light else 1.0), 0.15 if nm in ("snare", "clap") else 0.0)
        if bar in (8, 24):
            hit("crash", b0, 1.0, 0.2)
        if bar % 8 == 7 and bar != 23:
            for i in (12, 13, 14, 15):
                hit("snare" if drums_name not in ("latin",) else "conga", b0 + i, 0.5 + 0.1 * (i - 12))
        if bar == 23:                                   # the build: an accelerating snare roll and a riser
            for i in range(16):
                hit("snare", b0 + i, 0.25 + 0.04 * i)
            for i in range(0, 16, 2):
                hit("snare", b0 - 16 + i, 0.18 + 0.02 * i)
            r = _riser(int(step * 32)) * 0.6
            i0 = at(b0 - 16)
            L["drums"][i0:i0 + len(r)] += r
    # ---- mix: side-chain pumping, stereo, reverb, glue
    duck = np.ones(total + pad_len, dtype=np.float32)
    rel = int(0.16 * RATE)
    curve = 1 - 0.55 * np.exp(-np.arange(rel, dtype=np.float32) / (0.06 * RATE))
    for k in kicks:
        seg = duck[k:k + rel]
        np.minimum(seg, curve[:len(seg)], out=seg)
    for bus, depth in (("pad", 1.0), ("chords", 0.6), ("bass", 0.45), ("arp", 0.5)):
        L[bus] *= 1 - depth * (1 - duck)
    if DEBUG:
        print("  bus rms:", "  ".join("%s %.3f" % (k, float(np.sqrt((L[k] ** 2).mean()))) for k in L))
    buf = {}
    for k in L:
        x = L[k]
        x[:pad_len] += x[total:total + pad_len]            # fold release tails back to the start: seamless loop
        buf[k] = x[:total]
    d_arp = int(step * 3)
    left = buf["lead"] + buf["chords"] * 0.9 + buf["arp"] + np.roll(buf["arp"], d_arp) * 0.35 + buf["pad"] * 1.05 + buf["bass"] + buf["drums"]
    right = buf["lead"] + buf["chords"] * 1.1 + np.roll(buf["arp"], d_arp // 2) * 0.9 + buf["pad"] * 0.95 + buf["bass"] + buf["drums"] * 0.97
    send = buf["send"]
    k = 64
    send = np.convolve(send, np.ones(k, dtype=np.float32) / k, mode="same")
    revL = np.zeros(total, dtype=np.float32)
    revR = np.zeros(total, dtype=np.float32)
    for i, (dl, dr) in enumerate(((0.029, 0.033), (0.043, 0.049), (0.061, 0.067), (0.083, 0.091), (0.11, 0.123), (0.149, 0.163), (0.21, 0.23), (0.29, 0.31))):
        g = 0.42 * 0.8 ** i
        revL += np.roll(send, int(dl * RATE)) * g
        revR += np.roll(send, int(dr * RATE)) * g
    revL = revL + 0.5 * np.roll(revL, int(0.037 * RATE))
    revR = revR + 0.5 * np.roll(revR, int(0.041 * RATE))
    left = left + revL * 0.5
    right = right + revR * 0.5
    # presence: add back some of the top end (a gentle high shelf, like an exciter on the master)
    box = np.ones(7, dtype=np.float32) / 7
    left = left + 0.9 * (left - np.convolve(left, box, mode="same"))
    right = right + 0.9 * (right - np.convolve(right, box, mode="same"))
    st = np.stack([left, right], axis=1)
    st = st / max(1e-6, float(np.sqrt((st ** 2).mean())) * 5.0)
    st = np.tanh(st * 1.3) * 0.88
    return (st * 32767).astype(np.int16)


def render_wav(key, path):
    """Write a tune to a WAV file (to listen to tunes outside the game)."""
    import wave
    data = _compose(key)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


def _tune(key):
    with _lock:
        if key not in _tunes:
            for old in [k for k in _tunes if k not in ("board", _cur)]:
                del _tunes[old]          # keep memory low: only the board tune and the current one stay loaded
            _tunes[key] = pygame.mixer.Sound(buffer=_compose(key).tobytes())
            _ncache.clear()
        return _tunes[key]


def _precompose():
    try:
        _tune("title")
        _tune("board")
    except Exception:
        pass


def prepare(key):
    """Compose a tune in the background so that starting it later does not stall the game."""
    if ok and not WEB and key not in _tunes:
        threading.Thread(target=lambda: _tune(key), daemon=True).start()


def music(key):
    global _cur, _chi
    if not ok or key == _cur:
        return
    _cur = key
    _ch[_chi].fadeout(500)
    if key is None:
        return
    _chi = 1 - _chi
    c = _ch[_chi]
    c.set_volume(vol_music * 0.75)
    try:
        c.play(_tune(key), loops=-1, fade_ms=500)
    except Exception:
        pass


def set_volumes(m, s):
    global vol_music, vol_sfx
    vol_music, vol_sfx = m / 10.0, s / 10.0
    for c in _ch:
        c.set_volume(vol_music * 0.75)


# ================================================================== sound effects
SQR = [(k, 1.0 / k ** 1.25) for k in range(1, 10, 2)]

def _blip(f0, f1, dur, vol=0.5, harm=((1, 1), (2, 0.3)), noise=0.0, decay=0.25, vib=0.0):
    n = int(RATE * dur)
    t = np.arange(n, dtype=np.float32) / RATE
    f = f0 * (f1 / f0) ** (t / dur)
    ph = 2 * np.pi * np.cumsum(f) / RATE
    if vib:
        ph += vib * np.sin(2 * np.pi * 30 * t)
    w = sum(a * np.sin(k * ph) for k, a in harm)
    if noise:
        rng = np.random.default_rng(int(f0))
        w = w * (1 - noise) + rng.standard_normal(n) * noise * 0.8
    env = np.minimum(t / 0.004, 1) * np.exp(-t / (dur * decay))
    r = max(1, n // 6)
    env[-r:] *= np.linspace(1, 0, r)
    return (w * env * vol).astype(np.float32)


def _snd(*parts):
    w = np.concatenate(parts)
    w = np.tanh(w * 1.2) * 0.9
    st = np.stack([w, w], axis=1)
    return pygame.mixer.Sound(buffer=(st * 32767).astype(np.int16).tobytes())


def _build_sfx():
    S, B = _sfx, _blip
    bell = ((1, 1), (2, 0.4), (3, 0.15))
    S["blip"] = _snd(B(700, 700, 0.05, 0.25, bell, decay=0.6))
    S["click"] = _snd(B(1200, 900, 0.04, 0.3, bell, noise=0.2, decay=0.4))
    S["good"] = _snd(B(659, 659, 0.08, 0.4, bell, decay=0.9), B(988, 988, 0.22, 0.42, bell, decay=0.5))
    S["bad"] = _snd(B(220, 196, 0.12, 0.42, SQR, decay=0.9), B(165, 147, 0.25, 0.42, SQR, decay=0.5))
    S["pour"] = _snd(B(300, 900, 0.35, 0.3, noise=0.7, decay=0.8))
    S["pop"] = _snd(B(620, 160, 0.1, 0.5, noise=0.25, decay=0.4))
    S["tick"] = _snd(B(2400, 2400, 0.03, 0.35, bell, decay=0.3))
    S["buzz"] = _snd(B(110, 100, 0.45, 0.5, SQR, 0.2, 0.7, vib=2.0))
    S["beep"] = _snd(B(1000, 1000, 0.12, 0.35, ((1, 1),), decay=2.0))
    S["ding"] = _snd(B(1319, 1319, 0.5, 0.4, bell, decay=0.35))
    S["whoosh"] = _snd(B(200, 1200, 0.25, 0.35, noise=0.85, decay=0.6))
    S["splash"] = _snd(B(500, 180, 0.24, 0.4, noise=0.85, decay=0.35))
    S["dice"] = _snd(*[B(900 + 200 * (i % 3), 700, 0.03, 0.3, bell, noise=0.5, decay=0.4) for i in range(5)])
    S["step"] = _snd(B(520, 620, 0.06, 0.3, bell, decay=0.5))
    S["coffee"] = _snd(B(400, 800, 0.12, 0.35, bell, decay=0.8), B(800, 1200, 0.2, 0.35, bell, decay=0.5))
    S["page"] = _snd(B(523, 523, 0.08, 0.4, bell, decay=0.9), B(659, 659, 0.08, 0.4, bell, decay=0.9), B(784, 784, 0.08, 0.4, bell, decay=0.9), B(1047, 1047, 0.35, 0.45, bell, decay=0.4))
    win = [B(hz(m), hz(m), 0.11, 0.42, bell, decay=0.9) for m in (72, 76, 79, 84, 79, 84, 88)]
    S["win"] = _snd(*win, B(hz(91), hz(91), 0.7, 0.45, bell, decay=0.35))
    S["lose"] = _snd(B(392, 370, 0.2, 0.4, SQR, decay=0.9), B(330, 311, 0.2, 0.4, SQR, decay=0.9), B(262, 220, 0.5, 0.4, SQR, decay=0.6))


def sfx(name):
    if ok and name in _sfx:
        s = _sfx[name]
        s.set_volume(vol_sfx)
        s.play()
