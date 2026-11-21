# -*- coding: utf-8 -*-
"""Procedural music and sound effects (numpy synthesis, no asset files).

Every technique has its own tune, described by a small spec in its technique dict, plus
tunes for the title screen and the board. A tune is 16 bars: a chord progression, a
melody built from motifs that land on chord tones (optionally opened by a hand-written
hook), an accompaniment pattern, a bass line and a drum groove, with a stereo echo."""
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
    name  = "Thermocycler Funk",   # title shown at the station
    bpm   = 112, beats = 4,        # beats per bar: 3 or 4
    root  = 50,                    # MIDI note of the key centre (45-60)
    mode  = "dor",                 # maj min dor mix phr lyd harm pent blues
    prog  = [0, 3, 4, 0, 5, 3, 4, 4],   # 8 chord roots as scale degrees (0 = tonic), repeated twice
    lead  = "epiano",              # flute bell marimba epiano organ synth square pluck harpsi sitar brass vibes whistle
    comp  = "stab",                # arp waltz drone pad drive stab walk bossa alberti
    drums = "funk",                # none soft rock funk disco dnb latin march shuffle tick tabla techno
    swing = 0.0,                   # 0 (straight) to 0.33 (triplet swing)
    motif = [(0, 2), (2, 1), (4, 1), (7, 4)],   # optional hook: (scale degree, length in eighths), 1-2 bars
)"""

RATE = 44100
ok = False
_sfx = {}
_tunes = {}
_specs = {}
_lock = threading.Lock()
_cur = None
_ch = []
_chi = 0
vol_music, vol_sfx = 0.6, 0.7


def init():
    global ok, _ch, RATE
    if np is None:
        return
    try:
        pygame.mixer.quit()
        pygame.mixer.init(44100, -16, 2, 1024)
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


# ------------------------------------------------------------------ synthesis
def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


SAW = [(k, 1.0 / k ** 1.5) for k in range(1, 9)]
SQR = [(k, 1.0 / k ** 1.25) for k in range(1, 10, 2)]
INSTR = {
    # name: (partials, attack, decay, sustain, release, vibrato, bend, detune, octave offset of lead)
    "sitar": ([(k, 1.0 / k ** 1.2) for k in range(1, 10)], 0.003, 0.32, 0.04, 0.05, 0.0, 0.035, 0.004, 1),
    "bell": ([(1, 1), (2, 0.35), (4, 0.2), (6, 0.07)], 0.002, 0.42, 0.0, 0.05, 0.0, 0.0, 0.0, 2),
    "flute": ([(1, 1), (2, 0.22), (3, 0.07)], 0.05, 1.0, 0.8, 0.07, 0.004, 0.0, 0.0, 2),
    "harpsi": ([(k, 1.0 / k) for k in range(1, 11)], 0.002, 0.2, 0.0, 0.03, 0.0, 0.0, 0.0, 1),
    "synth": (SAW, 0.012, 0.3, 0.6, 0.06, 0.003, 0.0, 0.006, 1),
    "square": (SQR, 0.006, 0.2, 0.55, 0.04, 0.003, 0.0, 0.0, 2),
    "pluck": ([(1, 1), (2, 0.4), (3, 0.2), (4, 0.1)], 0.003, 0.24, 0.0, 0.03, 0.0, 0.0, 0.0, 2),
    "pad": (SAW, 0.3, 1.0, 0.8, 0.3, 0.002, 0.0, 0.005, 1),
    "bass": ([(1, 1), (2, 0.35), (3, 0.12)], 0.005, 0.4, 0.35, 0.03, 0.0, 0.0, 0.0, 0),
    "marimba": ([(1, 1), (3.93, 0.25), (9.2, 0.05)], 0.002, 0.18, 0.0, 0.03, 0.0, 0.0, 0.0, 2),
    "epiano": ([(1, 1), (2, 0.25), (3, 0.08), (7.1, 0.06)], 0.004, 0.55, 0.12, 0.06, 0.0, 0.0, 0.002, 1),
    "organ": ([(0.5, 0.5), (1, 1), (2, 0.6), (3, 0.3), (4, 0.25), (6, 0.1)], 0.01, 1.0, 0.9, 0.04, 0.0, 0.0, 0.0, 1),
    "brass": (SAW, 0.045, 0.4, 0.7, 0.06, 0.005, 0.02, 0.004, 1),
    "vibes": ([(1, 1), (4, 0.3), (10, 0.05)], 0.003, 0.7, 0.0, 0.1, 0.0, 0.0, 0.0, 2),
    "whistle": ([(1, 1), (2, 0.05)], 0.03, 1.0, 0.85, 0.06, 0.008, 0.0, 0.0, 2),
}
_ncache = {}


def _voice(f, n, harm, vib, bend, trem=False):
    t = np.arange(n, dtype=np.float32) / RATE
    ph = 2 * np.pi * f * t
    if vib:
        ph = ph + (f * vib / 5.5) * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1.0, t * 4)
    if bend:
        ph = ph + 2 * np.pi * f * bend * 0.05 * (np.exp(-t / 0.05) - 1)
    out = np.zeros(n, dtype=np.float32)
    for k, a in harm:
        if k * f < RATE * 0.42:
            out += a * np.sin(k * ph)
    if trem:
        out *= 0.8 + 0.2 * np.sin(2 * np.pi * 5.0 * t)
    return out


def note(inst, midi, n):
    key = (inst, midi, n)
    w = _ncache.get(key)
    if w is None:
        harm, att, dec, sus, rel, vib, bend, det, _ = INSTR[inst]
        f = hz(midi)
        w = _voice(f, n, harm, vib, bend, inst == "vibes")
        if det:
            w = 0.5 * (w + _voice(f * (1 + det), n, harm, vib, bend))
        t = np.arange(n, dtype=np.float32) / RATE
        env = np.minimum(t / att, 1.0) * (sus + (1 - sus) * np.exp(-t / dec))
        r = min(n, max(1, int(rel * RATE)))
        env[-r:] *= np.linspace(1, 0, r, dtype=np.float32)
        w = w * env / max(1.0, sum(a for _, a in harm) * 0.6)
        _ncache[key] = w
    return w


def _drums():
    rng = np.random.default_rng(5)

    def t(n):
        return np.arange(n, dtype=np.float32) / RATE

    def noise(n):
        return rng.standard_normal(n).astype(np.float32)
    d = {}
    n = int(0.22 * RATE)
    d["kick"] = np.sin(2 * np.pi * (45 * t(n) + (110 - 45) * 0.03 * (1 - np.exp(-t(n) / 0.03)))) * np.exp(-t(n) / 0.08)
    n = int(0.18 * RATE)
    d["snare"] = (np.diff(noise(n), prepend=0) * 0.5 * np.exp(-t(n) / 0.055) + 0.5 * np.sin(2 * np.pi * 190 * t(n)) * np.exp(-t(n) / 0.035))
    n = int(0.05 * RATE)
    d["hat"] = np.diff(noise(n), prepend=0) * 0.35 * np.exp(-t(n) / 0.012)
    n = int(0.25 * RATE)
    d["ohat"] = np.diff(noise(n), prepend=0) * 0.3 * np.exp(-t(n) / 0.09)
    n = int(0.2 * RATE)
    cl = np.diff(noise(n), prepend=0) * (np.exp(-t(n) / 0.05))
    for k in (0.008, 0.017):
        s = int(k * RATE)
        cl[s:] += np.diff(noise(n - s), prepend=0) * 0.7 * np.exp(-t(n - s) / 0.012)
    d["clap"] = cl * 0.45
    n = int(0.3 * RATE)
    d["tlo"] = np.sin(2 * np.pi * (88 * t(n) + 70 * 0.06 * (1 - np.exp(-t(n) / 0.06)))) * np.exp(-t(n) / 0.13)
    n = int(0.12 * RATE)
    d["thi"] = np.sin(2 * np.pi * 400 * t(n)) * np.exp(-t(n) / 0.045) + 0.1 * noise(n) * np.exp(-t(n) / 0.004)
    n = int(0.06 * RATE)
    d["rim"] = (np.sin(2 * np.pi * 1700 * t(n)) * 0.6 + np.sin(2 * np.pi * 2500 * t(n)) * 0.3) * np.exp(-t(n) / 0.012)
    n = int(0.08 * RATE)
    d["shaker"] = noise(n) * 0.18 * np.sin(np.pi * np.minimum(1, t(n) / 0.08)) ** 2
    n = int(0.04 * RATE)
    d["tick"] = np.sin(2 * np.pi * 3200 * t(n)) * np.exp(-t(n) / 0.006) * 0.6
    n = int(0.3 * RATE)
    d["conga"] = np.sin(2 * np.pi * (210 * t(n) + 60 * 0.02 * (1 - np.exp(-t(n) / 0.02)))) * np.exp(-t(n) / 0.09)
    return {k: v.astype(np.float32) for k, v in d.items()}


MODES = {
    "maj": [0, 2, 4, 5, 7, 9, 11], "min": [0, 2, 3, 5, 7, 8, 10], "dor": [0, 2, 3, 5, 7, 9, 10],
    "mix": [0, 2, 4, 5, 7, 9, 10], "phr": [0, 1, 3, 5, 7, 8, 10], "lyd": [0, 2, 4, 6, 7, 9, 11],
    "harm": [0, 2, 3, 5, 7, 8, 11], "pent": [0, 2, 4, 7, 9], "blues": [0, 3, 5, 6, 7, 10],
}
RHY = {4: [[2, 2, 2, 2], [2, 1, 1, 2, 2], [3, 1, 2, 2], [2, 2, 1, 1, 2], [4, 2, 2], [1, 1, 2, 2, 2], [3, 1, 4], [2, 2, 4], [1, 1, 1, 1, 2, 2]],
       3: [[2, 2, 2], [3, 1, 2], [2, 1, 1, 2], [4, 2], [2, 2, 1, 1], [1, 1, 2, 2]]}

# drum grooves: lists of (sound, position in eighths, gain) for one bar of 4 beats (3-beat bars use the first 6 eighths)
G = {
    "soft": [("kick", 0, .4), ("kick", 4, .35), ("snare", 2, .2), ("snare", 6, .2)] + [("hat", i, .1) for i in range(8)],
    "rock": [("kick", 0, .6), ("kick", 4, .6), ("kick", 5, .4), ("snare", 2, .36), ("snare", 6, .36)] + [("hat", i, .16) for i in range(8)],
    "funk": [("kick", 0, .6), ("kick", 1.5, .4), ("kick", 5, .5), ("snare", 2, .38), ("snare", 6, .38), ("snare", 3.5, .1), ("snare", 7.5, .12)]
            + [("hat", i / 2, .12 if i % 2 else .16) for i in range(16)] + [("ohat", 7, .12)],
    "disco": [("kick", i, .55) for i in (0, 2, 4, 6)] + [("clap", 2, .3), ("clap", 6, .3)] + [("ohat", i + 1, .14) for i in (0, 2, 4, 6)] + [("hat", i, .08) for i in range(0, 8, 2)],
    "dnb": [("kick", 0, .6), ("kick", 2.5, .5), ("snare", 2, .4), ("snare", 6, .4), ("snare", 7.5, .12)] + [("hat", i / 2, .1) for i in range(16)],
    "latin": [("conga", 0, .3), ("conga", 1.5, .25), ("conga", 3, .3), ("tlo", 4, .3), ("conga", 5.5, .25), ("conga", 7, .28)]
             + [("rim", p, .18) for p in (0, 1.5, 3, 5, 6)] + [("shaker", i, .25) for i in range(8)] + [("kick", 0, .4), ("kick", 4, .35)],
    "march": [("kick", 0, .5), ("kick", 4, .45), ("snare", 2, .3), ("snare", 6, .3), ("snare", 6.5, .15), ("snare", 7, .2), ("snare", 7.5, .25)] + [("hat", i, .08) for i in range(8)],
    "shuffle": [("kick", 0, .5), ("kick", 4, .45), ("snare", 2, .3), ("snare", 6, .3)] + [("hat", i, .14 if i % 2 == 0 else .09) for i in range(8)],
    "tick": [("tick", i, .22 if i % 2 == 0 else .12) for i in range(8)] + [("kick", 0, .35), ("rim", 4, .14)],
    "tabla": [("tlo", 0, .5), ("thi", 2, .2), ("thi", 3, .28), ("tlo", 4, .35), ("thi", 5, .2), ("thi", 6, .28), ("thi", 7, .16)],
    "techno": [("kick", i, .65) for i in (0, 2, 4, 6)] + [("ohat", i + 1, .16) for i in (0, 2, 4, 6)] + [("clap", 2, .22), ("clap", 6, .22)] + [("hat", i / 2, .06) for i in range(16)],
}


def _spec(key):
    sp = dict(bpm=100, beats=4, root=55, mode="maj", prog=[0, 4, 5, 3, 0, 4, 3, 4], lead="flute", comp="arp", drums="soft", swing=0.0)
    sp.update(_specs.get(key) or BUILTIN.get(key) or {})
    return sp


BUILTIN = {
    "title": dict(name="Lab Simulator", bpm=104, beats=4, root=53, mode="maj", prog=[0, 5, 3, 4, 0, 5, 1, 4], lead="marimba",
                  comp="arp", drums="soft", motif=[(0, 1), (2, 1), (4, 2), (7, 2), (6, 1), (4, 1), (5, 4), (4, 4)]),
    "board": dict(name="Board", bpm=96, beats=4, root=55, mode="mix", prog=[0, 6, 3, 0, 0, 6, 4, 4], lead="vibes",
                  comp="bossa", drums="latin", swing=0.12),
    "results": dict(name="Results", bpm=120, beats=4, root=57, mode="maj", prog=[0, 3, 4, 0, 5, 3, 4, 0], lead="bell", comp="arp", drums="soft"),
}


def _melody(rnd, beats, mode, prog, motif):
    n, bs = len(mode), beats * 2
    motifs = rnd.sample(RHY[beats], 4)
    form = [0, 1, 0, 2, 0, 1, 3, "end"]
    lo, hi = -2, n + 3
    deg = rnd.choice([0, 2, 4]) % n
    out = []

    def snap(c, tones):
        for off in (0, 1, -1, 2, -2, 3):
            if (c + off) % n in tones:
                return c + off
        return c
    hook = []
    if motif:
        pos = 0
        for d, ln in motif:
            hook.append((pos, ln, d))
            pos += ln
    hook_len = int(math.ceil(sum(ln for _, ln, _ in hook) / bs)) if hook else 0
    for sec in range(2):
        b = 0
        if hook:
            for pos, ln, d in hook:
                out.append((sec * 8 * bs + pos, ln, d))
            b = hook_len
            deg = hook[-1][2]
        while b < 8:
            tones = {(prog[b] + i * (2 if n >= 6 else 1)) % n for i in (0, 1, 2)}
            if form[b] == "end":
                rh = [bs] if sec else ([4, bs - 4] if bs > 4 else [bs])
            else:
                rh = motifs[form[b]]
            dirn = 1 if (b + sec) % 2 == 0 else -1
            pos = 0
            for i, d in enumerate(rh):
                strong = pos % 2 == 0 and (i == 0 or d >= 2)
                c = deg + (dirn * rnd.choice([1, 1, 2]) if rnd.random() < 0.78 else -dirn)
                if strong:
                    c = snap(c, tones)
                if form[b] == "end" and i == len(rh) - 1:
                    c = snap(c, {0} if sec else tones)
                if c > hi:
                    c, dirn = c - 2, -1
                if c < lo:
                    c, dirn = c + 2, 1
                if strong:
                    c = snap(c, tones)
                if c == deg and out and rnd.random() < 0.8:
                    c = snap(c + 2 * dirn, tones) if strong else c + dirn
                rest = (not strong) and d == 1 and rnd.random() < 0.1
                if not rest:
                    out.append((sec * 8 * bs + b * bs + pos, d, c))
                deg = c
                pos += d
            b += 1
    return out


def _compose(key):
    sp = _spec(key)
    bpm, beats, root = sp["bpm"], sp["beats"], sp["root"]
    mode = MODES.get(sp["mode"], MODES["maj"])
    prog = [p % len(mode) for p in sp["prog"]]
    lead, comp, drums, swing = sp["lead"], sp["comp"], sp["drums"], sp.get("swing", 0.0)
    if lead not in INSTR:
        lead = "flute"
    rnd = random.Random("labsim-" + str(key))
    n = len(mode)
    bs = beats * 2
    step = RATE * 60.0 / bpm / 2
    total = int(round(step * bs * 16))
    buf = np.zeros(total + RATE * 2, dtype=np.float32)
    third = 2 if n >= 6 else 1

    def sem(d):
        return mode[d % n] + 12 * (d // n)

    def at(pos):
        """sample index of an eighth-note position, with swing on the off-beats"""
        frac = pos - math.floor(pos)
        whole = math.floor(pos)
        if swing and whole % 2 == 1 and frac == 0:
            pos = pos + swing
        return int(pos * step)

    def add(inst, d, octv, start, dur, gain, sustain=True):
        ln = int(dur * step * (0.96 if sustain else 1.0))
        w = note(inst, root + sem(d) + 12 * octv, max(64, ln))
        s = at(start)
        buf[s:s + len(w)] += w * gain

    loct = INSTR[lead][8]
    for st, d, deg in _melody(rnd, beats, mode, prog, sp.get("motif")):
        add(lead, deg, loct, st, d, 0.42)
    dk = _drums()

    def hit(name, start, gain):
        w = dk[name]
        s = at(start)
        buf[s:s + len(w)] += w * gain

    for bar in range(16):
        c = prog[bar % 8]
        b0 = bar * bs
        tri = [c, c + third, c + 2 * third]
        fifth = c + (4 if n >= 6 else 3)
        if comp == "arp":
            for i, k in enumerate([0, 2, 1, 2, 0, 2, 1, 2][:bs]):
                add("pluck" if lead != "harpsi" else "harpsi", tri[k] + (n if k == 2 and i % 4 == 3 else 0), 1, b0 + i, 1, 0.16)
            add("bass", c, -1, b0, bs // 2, 0.42)
            add("bass", c + (4 if bar % 2 else 0), -1, b0 + bs // 2, bs // 2, 0.36)
        elif comp == "alberti":
            for i, k in enumerate([0, 2, 1, 2] * 4):
                if i / 2.0 < bs:
                    add("harpsi" if lead == "harpsi" else "epiano", tri[k], 0, b0 + i / 2.0, 0.5, 0.12)
            add("bass", c, -1, b0, bs, 0.36)
        elif comp == "waltz":
            add("bass", c, -1, b0, 2, 0.5)
            for beat in range(1, beats):
                for k in tri:
                    add("pluck", k, 1, b0 + beat * 2, 2, 0.11)
        elif comp == "drone":
            for k, g in ((0, 0.11), (4 if n >= 6 else 3, 0.08), (n, 0.05)):
                add("pad", k, 0, b0, bs, g)
            add("bass", c, -1, b0, bs, 0.3)
        elif comp == "pad":
            for k in tri:
                add("pad", k, 1, b0, bs, 0.085)
            add("bass", c, -1, b0, bs, 0.34)
        elif comp == "stab":   # off-beat chord stabs (funk / reggae) over a syncopated bass
            for q in range(1, bs, 2):
                for k in tri:
                    add("epiano" if lead != "epiano" else "organ", k, 1, b0 + q, 0.7, 0.07, False)
            for q, d in ((0, 0), (1.5, 0), (3, n), (4, 0), (5.5, 4 if n >= 6 else 3), (7, 0))[:bs and 6 if bs == 8 else 4]:
                add("bass", c + d, -1, b0 + q, 1, 0.4)
        elif comp == "walk":   # walking bass in quarter notes, swung chord comping on 2 and 4
            line = [c, c + third, fifth, c + third + 1 if bar % 2 else fifth + 1]
            for i in range(beats):
                add("bass", line[i % 4], -1, b0 + i * 2, 2, 0.44)
            for q in ((2, 6) if beats == 4 else (2, 4)):
                for k in tri:
                    add("epiano", k, 1, b0 + q, 1.2, 0.07)
        elif comp == "bossa":
            for q, d in ((0, c), (3, fifth), (4, fifth), (7, c))[:4 if beats == 4 else 2]:
                add("bass", d, -1, b0 + q, 1.5, 0.38)
            for q in ((0, 1.5, 3, 5, 6.5) if beats == 4 else (0, 1.5, 4)):
                for k in tri:
                    add("pluck", k, 1, b0 + q, 1, 0.075)
        else:  # drive
            for i in range(bs):
                add("bass", c + (n if i % 2 else 0), -1 if i % 2 == 0 else -2, b0 + i, 1, 0.36)
            for i in (2, 5):
                if i < bs:
                    for k in tri:
                        add("square", k, 1, b0 + i, 1, 0.055)
        fill = bar % 8 == 7
        groove = G.get(drums, [])
        for nm, q, g in groove:
            if q < bs:
                hit(nm, b0 + q, g)
        if fill and drums not in ("none", "tick", "tabla"):
            for q in (bs - 1.5, bs - 1, bs - 0.5):
                hit("snare" if drums != "latin" else "conga", b0 + q, 0.24)
        elif fill and drums == "tabla":
            for q in (bs - 1.5, bs - 1, bs - 0.5):
                hit("thi", b0 + q, 0.3)
    # fold the tail back to the start so the loop is seamless, then add stereo echo
    buf[:RATE * 2] += buf[total:total + RATE * 2]
    dry = buf[:total]
    d1, d2 = int(step * 3), int(step * 4)
    left = dry + 0.22 * np.roll(dry, d1) + 0.09 * np.roll(dry, d1 * 2)
    right = dry + 0.22 * np.roll(dry, d2) + 0.09 * np.roll(dry, d2 + d1)
    st = np.stack([left, right], axis=1)
    st = np.tanh(st * 0.2 / max(0.02, float(np.sqrt((st ** 2).mean())))) * 0.8
    return (st * 32767).astype(np.int16)


def render_wav(key, path):
    """Write a tune to a WAV file (used to listen to tunes outside the game)."""
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


# ------------------------------------------------------------------ sound effects
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
