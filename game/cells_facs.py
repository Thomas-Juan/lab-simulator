# -*- coding: utf-8 -*-
"""Flow cytometry and fluorescence-activated cell sorting (FACS)."""
import math
import random
import pygame
import audio
import gfx
import render as R
from stage import Stage, register, TOP, BOTTOM
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, LAV, VIOLET, NIGHT, WHITE,
                  GREEN, RED, YELLOW, clamp, mix, draw_text, draw_wrapped, text_surf)

FG = (80, 220, 100)     # GFP
FR = (240, 70, 90)      # mCherry
FY = (240, 210, 70)     # both
TYPES = {"g": [FG], "r": [FR], "y": [FG, FR], "n": [], "2": [FG, FR]}
WANT = {"g": "L", "r": "R", "y": None, "n": None, "2": None}
LASER_Y, PLATE_Y, TUBE_Y = TOP + 120, TOP + 250, 448
NOZ = (480, TOP + 34)


@register("facs_sort")
class FacsSort(Stage):
    title = "Sort the stream"
    instr = ("Cells fall one by one through the lasers. Press LEFT for GFP-only (green) cells and RIGHT for mCherry-only (red) "
             "cells, before they reach the plates. Do nothing for cells that are both or neither: they go to waste. "
             "Dim cells still count. A droplet holding two cells must go to waste too.")

    def setup(self):
        self.total = self.p.get("cells", self.lv(18, 24, 30))
        k = self.total
        types = ["g"] * (k * 7 // 24) + ["r"] * (k * 7 // 24) + ["y"] * (k * 5 // 24) + ["n"] * (k * 5 // 24)
        if self.level == 2:
            types += ["2"] * 4               # coincident events: two cells in one droplet
        while len(types) < self.total:
            types.append(self.rng.choice("grny"))
        types = types[:self.total]
        self.rng.shuffle(types)
        self.queue = types
        self.dim_p = self.lv(0.0, 0.25, 0.35)        # share of single-colour cells that express only weakly
        self.base_v = self.lv(1.35, 1.6, 1.9)
        self.mistakes = {}
        self.drops = []
        self.spawned = 0
        self.next = 30
        self.correct = 0
        self.resolved = 0
        self.wrong = 0
        self.tubes = {"L": [], "W": [], "R": []}
        self.flash = {"g": 0, "r": 0}
        self.hint = "LEFT = green only    RIGHT = red only    nothing = both or neither"

    def speed(self):
        return self.base_v + 1.7 * self.spawned / self.total

    def tick(self, inp):
        self.next -= 1
        if self.next <= 0:
            if self.queue and self.rng.random() < 0.55:
                t = self.queue.pop()
                dim = t in "gr" and self.rng.random() < self.dim_p
                self.drops.append({"y": NOZ[1] + 10, "x": NOZ[0], "vx": 0.0, "t": t, "dec": None, "seen": False, "dim": dim})
                self.spawned += 1
            else:
                self.drops.append({"y": NOZ[1] + 10, "x": NOZ[0], "vx": 0.0, "t": None, "dec": None, "seen": False})
            self.next = int(max(14, 34 - 18 * self.spawned / self.total))
        dec = None
        if "left" in inp.pressed or (inp.click and inp.mouse[0] < 380):
            dec = "L"
        if "right" in inp.pressed or (inp.click and inp.mouse[0] > 580):
            dec = "R"
        if dec:
            cand = [d for d in self.drops if d["t"] and d["seen"] and d["dec"] is None and d["y"] < PLATE_Y]
            if cand:
                d = min(cand, key=lambda d: -d["y"])
                d["dec"] = dec
                audio.sfx("click")
            else:
                self.floaters.add(480 + (-120 if dec == "L" else 120), PLATE_Y - 30, "no cell to sort", MUTED, 15)
        sp = self.speed()
        for d in self.drops:
            d["y"] += sp
            if d["t"] and not d["seen"] and d["y"] >= LASER_Y:
                d["seen"] = True
                for k in ("g", "r"):
                    if (k == "g" and d["t"] in "gy2") or (k == "r" and d["t"] in "ry2"):
                        self.flash[k] = 12 if d.get("dim") else 30
                audio.sfx("tick")
            if d["y"] >= PLATE_Y:
                d["vx"] += {"L": -0.12, "R": 0.12, None: 0}[d["dec"]] * sp / 2
                d["x"] += d["vx"]
            if d["y"] >= TUBE_Y - 20:
                d["dead"] = True
                if d["t"]:
                    self.resolve(d)
        self.drops = [d for d in self.drops if not d.get("dead")]
        for k in self.flash:
            self.flash[k] = max(0, self.flash[k] - 1)
        if self.resolved >= self.total:
            fb = ["%d of %d cells ended up in the right tube." % (self.correct, self.total)]
            worst = sorted(self.mistakes.items(), key=lambda kv: -kv[1])
            tips = {"g": "Dim green cells are still GFP-positive: sort them LEFT.", "r": "Dim red cells are still mCherry-positive: sort them RIGHT.",
                    "y": "Double-positive cells (green and red together) belong in waste.", "n": "Unlabelled cells belong in waste.",
                    "2": "A droplet with two cells must be aborted: sorting it would carry the unwanted cell into the tube."}
            if worst:
                fb.append(tips[worst[0][0]])
            fb.append("A real sorter charges each droplet that holds a wanted cell; charged plates bend it into the tube.")
            self.finish(100.0 * self.correct / self.total, *fb)

    def resolve(self, d):
        self.resolved += 1
        tube = d["dec"] or "W"
        self.tubes[tube].append(d["t"])
        ok = (WANT[d["t"]] or "W") == tube
        x = {"L": 300, "W": 480, "R": 660}[tube]
        if ok:
            self.correct += 1
            self.floaters.add(x, TUBE_Y - 40, "+1", GREEN, 18)
        else:
            self.wrong += 1
            self.mistakes[d["t"]] = self.mistakes.get(d["t"], 0) + 1
            self.shake = 6
            audio.sfx("bad")
            name = {"g": "a GFP cell", "r": "an mCherry cell", "y": "a double-positive cell", "n": "an unlabelled cell",
                    "2": "two cells in one drop"}[d["t"]]
            self.floaters.add(x, TUBE_Y - 40, name + " here!", RED, 16)

    def partial(self):
        return 100.0 * self.correct / self.total

    def autoplay(self):
        self.finish(92, "22 of 24 cells ended up in the right tube.")

    def draw_drop(self, s, d):
        x, y = d["x"], d["y"]
        r = 8 if d["t"] else 5
        R.gd.filled_circle(s, int(x), int(y), r, (120, 170, 210))
        R.gd.aacircle(s, int(x), int(y), r, (190, 226, 250))
        R.gd.filled_circle(s, int(x - r * 0.35), int(y - r * 0.35), max(1, r // 3), (235, 248, 255))
        if d["t"] == "2":                 # two cells sharing one droplet
            for k, col in ((-1, FG), (1, FR)):
                cx = int(x + k * 3)
                if d["seen"]:
                    R.glow(s, (cx, y), 12, tuple(int(c * 0.45) for c in col))
                R.gd.filled_circle(s, cx, int(y), 3, col if d["seen"] else (150, 156, 170))
        elif d["t"]:
            cols = TYPES[d["t"]] if d["seen"] else []
            if cols:
                col = cols[0] if len(cols) == 1 else FY
                near = abs(y - LASER_Y) < 16
                k = 0.45 if d.get("dim") else 1.0
                R.glow(s, (x, y), 26 if near else 14, tuple(int(c * (0.9 if near else 0.45) * k) for c in col))
                R.gd.filled_circle(s, int(x), int(y), 4, mix(col, (150, 156, 170), 0.45) if d.get("dim") else col)
            else:
                R.gd.filled_circle(s, int(x), int(y), 4, (150, 156, 170))
            if d["dec"]:
                sign = "+" if d["dec"] == "L" else "−"
                ring = (255, 150, 120) if d["dec"] == "L" else (140, 180, 255)
                R.gd.aacircle(s, int(x), int(y), r + 4, ring)
                R.gd.aacircle(s, int(x), int(y), r + 5, ring)
                draw_text(s, sign, (x + 14, y - 10), 14, ring, bold=True)

    def render(self, s):
        s.blit(_sorter_bg(), (0, 0))
        # fluorescence flashes at the laser intercept
        for k, col in (("g", FG), ("r", FR)):
            f = self.flash[k] / 30.0
            if f:
                R.glow(s, (NOZ[0], LASER_Y), int(30 + 30 * f), tuple(int(c * f) for c in col))
        # detector read-outs
        for k, col, yy, lab in (("g", FG, LASER_Y - 76, "GFP  530/30"), ("r", FR, LASER_Y + 24, "mCherry  610/20")):
            box = pygame.Rect(600, yy, 146, 50)
            draw_text(s, lab, (box.x + 10, box.y + 6), 12, (210, 216, 230), bold=True)
            gfx.bar(s, (box.x + 10, box.y + 28, box.w - 20, 12), self.flash[k] / 30.0, col, (20, 22, 30), (90, 96, 110))
            gfx.led(s, (box.right - 12, box.y + 12), col, self.flash[k] > 0, 4)
        # collection tubes
        from cells_common import label as _label
        for key, x, lab, col in (("L", 300, "GFP only", FG), ("W", 480, "waste", (150, 150, 160)), ("R", 660, "mCherry only", FR)):
            _facs_tube(s, x, TUBE_Y - 22, min(0.9, 0.1 + 0.05 * len(self.tubes[key])), col)
            _label(s, (x - 46, TUBE_Y + 48, 92, 18), lab, 11)
        for d in self.drops:
            self.draw_drop(s, d)
        # legend
        rows = [([FG], "LEFT"), ([FR], "RIGHT"), ([FG, FR], "waste"), ([], "waste")]
        if self.level == 2:
            rows.append(("2", "waste (2 cells)"))
        p = pygame.Rect(776, TOP + 6, 170, 108 + len(rows) * 40 + 30)
        gfx.card(s, p, CARD)
        draw_text(s, "Sort rule", (p.x + 12, p.y + 10), 16, INK, bold=True)
        for i, (cols, lab) in enumerate(rows):
            y = p.y + 48 + i * 40
            gfx.circle(s, (34, 38, 50), (p.x + 26, y), 13, 2)
            if cols == "2":
                for k, col in ((-1, FG), (1, FR)):
                    R.gd.filled_circle(s, p.x + 26 + k * 4, y, 3, col)
            else:
                col = cols[0] if len(cols) == 1 else FY if cols else (150, 156, 170)
                if cols:
                    R.glow(s, (p.x + 26, y), 14, tuple(int(c * 0.6) for c in col))
                R.gd.filled_circle(s, p.x + 26, y, 5, col)
            draw_text(s, lab, (p.x + 50, y - 10), 15 if len(lab) < 8 else 13, INK, bold=True)
        yy = p.y + 30 + len(rows) * 40
        draw_text(s, "Sorted %d / %d" % (self.resolved, self.total), (p.x + 12, yy), 14, INK_SOFT, bold=True)
        draw_wrapped(s, "Dim cells still count. Most droplets are empty.", (p.x + 12, yy + 24), 12, p.w - 24, INK_SOFT)


_SORTER = {}


def _facs_tube(s, x, y, level, cap):
    """A 5 mL round-bottom polystyrene FACS tube with a snap cap, in the holder."""
    key = ("tube", round(level, 2), cap)
    sp = _SORTER.get(key)
    if sp is None:
        import real
        w, h = 30, 78
        S = 3
        big = pygame.Surface(((w + 8) * S, (h + 14) * S), pygame.SRCALPHA)
        m = pygame.Surface((w * S, h * S), pygame.SRCALPHA)
        pygame.draw.rect(m, (255, 255, 255, 255), (0, 0, w * S, (h - w // 2) * S))
        pygame.draw.ellipse(m, (255, 255, 255, 255), (0, (h - w) * S, w * S, w * S))
        big.blit(real.shaded_mask(m, (216, 224, 228), real.cyl_profile(w * S, spec_k=0.5), 130), (4 * S, 10 * S))
        if level > 0:
            lm = m.copy()
            pygame.draw.rect(lm, (0, 0, 0, 0), (0, 0, w * S, int((h - (h - 6) * level) * S)))
            big.blit(real.shaded_mask(lm, mix(cap, (236, 236, 240), 0.6), real.cyl_profile(w * S, spec_k=0.3) * 0.9 + 0.1, 200), (4 * S, 10 * S))
        big.blit(real.soft_edge(m, (120, 128, 134), 2), (4 * S, 10 * S))
        cm = pygame.Surface(((w + 6) * S, 12 * S), pygame.SRCALPHA)
        pygame.draw.rect(cm, (255, 255, 255, 255), cm.get_rect(), border_radius=3 * S)
        big.blit(real.shaded_mask(cm, cap, real.cyl_profile(cm.get_width(), 0.3, 0.1, 0.35, 0.7), 245), (S, 0))
        sp = _SORTER[key] = pygame.transform.smoothscale(big, (w + 8, h + 14))
    s.blit(sp, (x - sp.get_width() // 2, y))


def _sorter_bg():
    """The sort chamber: steel housing with a dark window, nozzle, two lasers, detectors and charged plates."""
    if "bg" in _SORTER:
        return _SORTER["bg"]
    b = pygame.Surface((W, H))
    gfx.bench(b, SKY)
    body = pygame.Rect(196, TOP + 4, 568, 428)
    gfx.shadow(b, body, 14)
    gfx.metal_rect(b, body, (196, 202, 212), 14)
    win = pygame.Rect(body.x + 14, body.y + 14, body.w - 28, TUBE_Y - 34 - body.y)
    gfx.rrect(b, win, (22, 26, 36), (70, 74, 84), 2, 10, 0.12, False)
    # nozzle
    gfx.metal_rect(b, (NOZ[0] - 40, TOP + 4, 80, 18), (160, 166, 176), 4)
    R.aa_poly(b, (186, 192, 204), [(NOZ[0] - 22, TOP + 20), (NOZ[0] + 22, TOP + 20), (NOZ[0] + 5, NOZ[1]), (NOZ[0] - 5, NOZ[1])], 1, (110, 116, 126))
    gfx.line(b, (236, 240, 248), (NOZ[0] - 12, TOP + 22), (NOZ[0] - 3, NOZ[1] - 2), 2)
    draw_text(b, "vibrating nozzle", (NOZ[0] + 30, TOP + 26), 12, (190, 200, 216), bold=True)
    # the jet down to the break-off point
    gfx.line(b, (130, 190, 230), NOZ, (NOZ[0], LASER_Y + 34), 3)
    R.glow(b, (NOZ[0], (NOZ[1] + LASER_Y) // 2), 18, (10, 30, 50))
    # two lasers: blue 488 nm excites GFP, yellow-green 561 nm excites mCherry
    for (lab, beam, dy) in (("488 nm", (70, 150, 255), -6), ("561 nm", (190, 240, 60), 6)):
        y = LASER_Y + dy
        hb = pygame.Rect(win.x + 6, y - 11 + (dy > 0) * 2 - (dy < 0) * 10, 72, 20)
        gfx.rrect(b, hb, (64, 66, 82), (36, 38, 46), 1, 4, 0.2)
        draw_text(b, lab, hb.center, 12, beam, center=True, bold=True, vcenter=True)
        for k in range(6):
            pygame.draw.line(b, tuple(int(c * 0.12) for c in beam), (hb.right, y), (win.right - 6, y), 7 - k)
        pygame.draw.line(b, beam, (hb.right, y), (NOZ[0] + 110, y), 2)
        R.glow(b, (NOZ[0], y), 16, tuple(int(c * 0.5) for c in beam))
    # detectors (dark boxes on the right)
    for yy in (LASER_Y - 76, LASER_Y + 24):
        gfx.rrect(b, (600, yy, 146, 50), (40, 44, 58), (110, 118, 134), 2, 6, 0.1)
    # charged deflection plates
    for x, col, lab in ((410, (90, 130, 230), "−"), (550, (230, 100, 90), "+")):
        gfx.metal_rect(b, (x - 8, PLATE_Y, 16, 100), (176, 182, 194), 4)
        pygame.draw.line(b, col, (x - 3, PLATE_Y + 6), (x - 3, PLATE_Y + 94), 2)
        R.glow(b, (x, PLATE_Y + 50), 34, tuple(int(c * 0.22) for c in col))
        draw_text(b, lab, (x, PLATE_Y + 104), 20, col, center=True, bold=True)
    draw_text(b, "charged plates", (NOZ[0], PLATE_Y + 104), 12, (190, 200, 216), center=True, bold=True)
    # tube holder on the instrument's shelf
    gfx.metal_rect(b, (232, TUBE_Y + 28, 496, 16), (150, 156, 168), 4)
    gl = pygame.Rect(win.x + 4, win.y + 4, win.w - 8, 26)
    gfx.alpha_rect(b, gl, (255, 255, 255), 14, 8)
    _SORTER["bg"] = b
    return b


# ------------------------------------------------------------------ gating
PLOT = pygame.Rect(96, TOP + 44, 390, 360)


def heat(f):
    """Pseudocolour map used by flow cytometry software: blue, cyan, green, yellow, red."""
    stops = [(0.0, (40, 70, 220)), (0.25, (40, 190, 230)), (0.5, (60, 220, 90)), (0.75, (245, 220, 60)), (1.0, (240, 60, 50))]
    f = clamp(f ** 0.6, 0, 1)
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if f <= b:
            return mix(ca, cb, (f - a) / (b - a))
    return stops[-1][1]


SAMPLES = [("Jurkat T cells", 0.46, 0.26), ("HEK293 cells", 0.55, 0.36), ("HeLa cells", 0.58, 0.40), ("primary splenocytes", 0.40, 0.22)]


def _gen_events(rng, level=1, sample=None):
    """A scatter plot of one sample: single cells, debris, dead cells and clumps. Harder levels bring the
    dead cells and clumps closer to the main population and add more of them."""
    name, cx, cy = sample or rng.choice(SAMPLES)
    sp = (0.06, 0.07, 0.085)[level]
    ev = []
    for _ in range(1260):
        ev.append((rng.gauss(cx, sp), rng.gauss(cy, sp * 0.85), "cell"))
    for _ in range(510):
        ev.append((abs(rng.gauss(0.06, 0.04)), abs(rng.gauss(0.12, 0.09)), "debris"))
    gap = (0.26, 0.23, 0.18)[level]
    for _ in range((180, 210, 300)[level]):
        ev.append((rng.gauss(cx - gap, 0.05), rng.gauss(cy + gap, 0.08), "dead"))
    for _ in range((150, 180, 260)[level]):
        ev.append((rng.gauss(cx + gap * 1.35, 0.06), rng.gauss(cy + gap * 1.2, 0.1), "clump"))
    return [(clamp(x, 0.005, 0.995), clamp(y, 0.005, 0.995), k) for x, y, k in ev]


@register("facs_gate")
class FacsGate(Stage):
    title = "Draw the gate"
    instr = ("Drag a box around the main population of intact cells on the forward (FSC) versus side scatter (SSC) plot. "
             "Leave out the debris, dead cells and clumps. Then press Confirm.")
    limit = 45

    def setup(self):
        self.sample = self.rng.choice(SAMPLES)
        self.ev = _gen_events(self.rng, self.level, self.sample)
        self.gate = None
        self.drag = None
        self.confirm = gfx.Button((560, 410, 180, 44), "Confirm gate", SAND)
        self.revealed = False

    def to_px(self, x, y):
        return PLOT.x + x * PLOT.w, PLOT.bottom - y * PLOT.h

    def to_n(self, px, py):
        return clamp((px - PLOT.x) / PLOT.w, 0, 1), clamp((PLOT.bottom - py) / PLOT.h, 0, 1)

    def stats(self):
        if not self.gate:
            return 0, 0, 0
        x0, y0, x1, y1 = self.gate
        inside = [k for x, y, k in self.ev if x0 <= x <= x1 and y0 <= y <= y1]
        cells = sum(1 for k in inside if k == "cell")
        total = sum(1 for _, _, k in self.ev if k == "cell")
        return len(inside), cells / total, (cells / len(inside) if inside else 0)

    def grade(self):
        n, recall, purity = self.stats()
        sc = self.score_of(recall, purity)
        fb = ["Your gate holds %d %% of the %s and is %d %% pure." % (round(recall * 100), self.sample[0], round(purity * 100))]
        if purity < 0.9:
            fb.append("Low FSC is debris, high SSC with low FSC is dead cells, very high FSC is clumps: keep them out.")
        elif recall < 0.8:
            fb.append("The gate is clean but cuts off part of the population; make it a little larger.")
        audio.sfx("good" if sc >= 70 else "bad")
        self.revealed = True
        self.finish(sc, *fb)

    def tick(self, inp):
        if self.gate and self.confirm.hit(inp):
            self.grade()
            return
        if inp.click and PLOT.collidepoint(inp.mouse):
            self.drag = self.to_n(*inp.mouse)
        if self.drag and inp.down:
            a = self.drag
            b = self.to_n(*inp.mouse)
            self.gate = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
        if inp.release:
            self.drag = None
            if self.gate and (self.gate[2] - self.gate[0] < 0.02 or self.gate[3] - self.gate[1] < 0.02):
                self.gate = None

    def score_of(self, recall, purity):
        r0, p0 = self.lv(0.35, 0.4, 0.45), self.lv(0.5, 0.55, 0.6)
        return 100 * clamp((recall - r0) / (0.85 - r0), 0, 1) * clamp((purity - p0) / (0.93 - p0), 0, 1)

    def partial(self):
        if not self.gate:
            return 0
        n, recall, purity = self.stats()
        return self.score_of(recall, purity)

    def autoplay(self):
        _, cx, cy = self.sample
        w = (0.13, 0.135, 0.14)[self.level]
        self.gate = (cx - w, cy - w * 0.95, cx + w, cy + w * 0.95)
        self.grade()

    def plot_layer(self):
        """Pseudocolour density plot on the instrument screen (cached; recoloured by class after grading)."""
        key = self.revealed
        if getattr(self, "_plot_key", None) == key:
            return self._plot
        sf = pygame.Surface(PLOT.size, pygame.SRCALPHA)
        g = 60
        dens = {}
        for x, y, k in self.ev:
            c = (int(x * g), int(y * g))
            dens[c] = dens.get(c, 0) + 1
        mx = max(dens.values())
        cols = {"cell": (90, 160, 255), "debris": (230, 170, 90), "dead": (240, 110, 200), "clump": (130, 230, 110)}
        for x, y, k in self.ev:
            px, py = x * PLOT.w, PLOT.h - y * PLOT.h
            if self.revealed:
                col = cols[k]
            else:
                col = heat(dens[(int(x * g), int(y * g))] / float(mx))
            sf.fill(col + (255,), (int(px), int(py), 2, 2))
        self._plot, self._plot_key = sf, key
        return sf

    def render(self, s):
        gfx.bench(s, SKY)
        _monitor(s, PLOT.inflate(80, 70).move(-12, 4), "%s.fcs  -  FSC-A / SSC-A" % self.sample[0].split()[0])
        _axes(s, PLOT, "FSC-A", "SSC-A", lin=True)
        s.blit(self.plot_layer(), PLOT.topleft)
        if self.gate:
            x0, y0, x1, y1 = self.gate
            ax, ay = self.to_px(x0, y1)
            bx, by = self.to_px(x1, y0)
            gr = pygame.Rect(int(ax), int(ay), max(1, int(bx - ax)), max(1, int(by - ay)))
            pygame.draw.rect(s, (20, 20, 24), gr, 1)
            n_in = self.stats()[0]
            draw_text(s, "Cells  %.1f" % (100.0 * n_in / len(self.ev)), (gr.x + 2, gr.y - 16), 12, (20, 20, 24), bold=True)
        p = pygame.Rect(530, TOP + 30, 400, 440)
        gfx.card(s, p, CARD)
        draw_text(s, "Reading a scatter plot", (p.x + 16, p.y + 14), 17, INK, bold=True)
        y = draw_wrapped(s, "Forward scatter (FSC) grows with cell size. Side scatter (SSC) grows with granularity "
                            "and internal complexity. Each dot is one event that passed the lasers.", (p.x + 16, p.y + 44), 15, p.w - 32, INK_SOFT)
        n, recall, purity = self.stats()
        draw_text(s, "Events in gate: %d of %d" % (n, len(self.ev)), (p.x + 16, y + 16), 17, INK, bold=True)
        if self.revealed:
            yy = y + 50
            for k, lab2 in (("cell", "single cells"), ("debris", "debris"), ("dead", "dead cells"), ("clump", "clumps")):
                gfx.rrect(s, (p.x + 18, yy + 4, 12, 12), {"cell": (90, 160, 255), "debris": (230, 170, 90), "dead": (240, 110, 200), "clump": (130, 230, 110)}[k], INK, 1, 3, 0)
                draw_text(s, lab2, (p.x + 38, yy), 15, INK)
                yy += 24
        elif self.gate:
            self.confirm.draw(s)
        else:
            draw_text(s, "Drag on the plot to draw a gate.", (p.x + 16, y + 52), 15, CORAL_D, bold=True)


def _monitor(s, rect, title):
    """A monitor showing the cytometry software: dark bezel, light window with a title bar."""
    rect = pygame.Rect(rect)
    gfx.shadow(s, rect, 12)
    gfx.plastic_rect(s, rect.inflate(18, 18), (44, 46, 52), 12, 0.1)
    win = rect
    gfx.rrect(s, win, (236, 238, 242), None, 0, 3, 0, False)
    gfx.rrect(s, (win.x, win.y, win.w, 22), (210, 214, 222), None, 0, 3, 0.1, False)
    draw_text(s, title, (win.x + 10, win.y + 4), 12, (40, 44, 52), bold=True)
    for i, c in enumerate(((236, 90, 80), (240, 190, 60), (90, 190, 90))):
        R.gd.filled_circle(s, win.right - 14 - i * 16, win.y + 11, 4, c)


def _axes(s, pr, xl, yl, lin=True):
    """White plot area with black axes and tick labels (linear 0-250K, or log decades)."""
    gfx.rrect(s, pr, (255, 255, 255), None, 0, 0, 0, False)
    ink = (20, 20, 24)
    pygame.draw.line(s, ink, pr.bottomleft, pr.bottomright, 1)
    pygame.draw.line(s, ink, pr.bottomleft, pr.topleft, 1)
    if lin:
        ticks = [(i / 5.0, "%dK" % (i * 50) if i else "0") for i in range(6)]
    else:
        ticks = [(0.0, "0"), (0.25, "10³"), (0.5, "10⁴"), (0.75, "10⁵")]
    for f, t in ticks:
        x = pr.x + f * pr.w
        y = pr.bottom - f * pr.h
        pygame.draw.line(s, ink, (x, pr.bottom), (x, pr.bottom + 4), 1)
        pygame.draw.line(s, ink, (pr.x - 4, y), (pr.x, y), 1)
        draw_text(s, t, (x, pr.bottom + 6), 10, ink, center=True)
        draw_text(s, t, (pr.x - 6, y - 6), 10, ink, right=True)
        if not lin:
            for k in range(2, 10):
                fx = f + math.log10(k) * 0.25
                if fx < 1:
                    pygame.draw.line(s, ink, (pr.x + fx * pr.w, pr.bottom), (pr.x + fx * pr.w, pr.bottom + 2), 1)
                    pygame.draw.line(s, ink, (pr.x - 2, pr.bottom - fx * pr.h), (pr.x, pr.bottom - fx * pr.h), 1)
    draw_text(s, xl, (pr.centerx, pr.bottom + 20), 12, ink, center=True, bold=True)
    lab = pygame.transform.rotate(text_surf(yl, 12, ink, True), 90)
    s.blit(lab, (pr.x - 42, pr.centery - lab.get_height() // 2))


# ------------------------------------------------------------------ quadrants
QNAMES = ["GFP− mCherry−", "GFP+ mCherry−", "GFP− mCherry+", "GFP+ mCherry+ (double positive)"]
QCENT = [(0.2, 0.2), (0.72, 0.2), (0.2, 0.72), (0.72, 0.72)]


def _quad_plot(seed, fr, hi=None):
    def pic(s, rect):
        r = random.Random(seed)
        pr = pygame.Rect(rect.x + 54, rect.y + 10, rect.w - 70, rect.h - 56)
        _axes(s, pr, "GFP", "mCherry", lin=False)
        top = max(fr)
        for q, f in enumerate(fr):
            cx, cy = QCENT[q]
            for _ in range(int(f * 18)):
                x, y = clamp(r.gauss(cx, 0.08), 0.01, 0.99), clamp(r.gauss(cy, 0.08), 0.01, 0.99)
                d2 = ((x - cx) ** 2 + (y - cy) ** 2) / (2 * 0.08 ** 2)
                col = heat(math.exp(-d2) * (0.35 + 0.65 * f / float(top)))
                s.fill(col, (int(pr.x + x * pr.w), int(pr.bottom - y * pr.h), 2, 2))
        qx, qy = pr.x + 0.44 * pr.w, pr.bottom - 0.44 * pr.h
        pygame.draw.line(s, (20, 20, 24), (qx, pr.y), (qx, pr.bottom), 1)
        pygame.draw.line(s, (20, 20, 24), (pr.x, qy), (pr.right, qy), 1)
        if hi is not None:
            x0 = pr.x if hi in (0, 2) else qx
            y0 = qy if hi in (0, 1) else pr.y
            w = (qx - pr.x) if hi in (0, 2) else (pr.right - qx)
            h = (pr.bottom - qy) if hi in (0, 1) else (qy - pr.y)
            gfx.alpha_rect(s, (x0, y0, w, h), YELLOW, 90)
        else:
            for q, f in enumerate(fr):
                x = pr.x + 6 if q in (0, 2) else pr.right - 6
                y = pr.y + 6 if q in (2, 3) else pr.bottom - 24
                draw_text(s, "%d %%" % f, (x, y), 15, (20, 20, 24), bold=True, right=q in (1, 3))
    return pic


def _fracs(rng):
    while True:
        a = [rng.randint(5, 45) for _ in range(3)]
        if sum(a) < 92:
            fr = a + [100 - sum(a)]
            rng.shuffle(fr)
            sums = {fr[1] + fr[3], fr[1], fr[3], fr[2] + fr[3]}
            if len(sums) == 4:
                return fr


def _quad_q(rng):
    fr = _fracs(rng)
    seed = rng.randrange(10 ** 6)
    if rng.random() < 0.5:
        hi = rng.randrange(4)
        return dict(q="Which cells sit in the highlighted quadrant?", options=QNAMES, answer=hi, keep_order=True,
                    pic=_quad_plot(seed, fr, hi), why="Right of the vertical line is GFP+, above the horizontal line is mCherry+.")
    vals = [fr[1] + fr[3], fr[1], fr[3], fr[2] + fr[3]]
    return dict(q="What percentage of all cells express GFP, with or without mCherry?",
                options=["%d %%" % v for v in vals], answer=0, pic=_quad_plot(seed, fr),
                why="GFP+ cells are both right-hand quadrants: %d %% + %d %% = %d %%." % (fr[1], fr[3], vals[0]))


QUIZ = [
    dict(q="What does forward scatter (FSC) mainly tell you about a cell?", options=["Its size", "Its DNA content",
         "Whether it expresses GFP", "Its granularity"], answer=0,
         why="Forward scatter grows with size; side scatter grows with granularity and internal complexity."),
    dict(q="What is compensation in flow cytometry?", options=["Correcting for one dye's light spilling into another dye's detector",
         "Adjusting the stream speed", "Adding more cells to reach a count", "Cooling the laser"], answer=0,
         why="Emission spectra overlap, e.g. GFP light partly reaches the PE detector; compensation subtracts that spillover."),
    dict(q="How does a sorter move a wanted cell into the collection tube?",
         options=["It charges the droplet holding the cell; charged plates deflect it", "A tiny robot arm picks it",
                  "A magnet pulls GFP towards it", "Air jets blow every droplet sideways"], answer=0,
         why="The vibrating stream breaks into droplets; the droplet with the wanted cell gets a charge just as it breaks off."),
    dict(q="Why gate out events with very high forward scatter?", options=["They are mostly clumps and doublets, not single cells",
         "They are debris", "They are bacteria", "They are the brightest GFP cells"], answer=0,
         why="Two cells stuck together scatter more light; height-versus-area plots separate doublets from singlets."),
]

TECH = dict(
    key="facs", name="FACS", full="Flow cytometry and fluorescence-activated cell sorting", wing="Cells & embryos", icon="facs",
    blurb="Measuring the light scatter and fluorescence of thousands of single cells per second, and sorting the ones you want.",
    facts=[
        "Mack Fulwyler built an electrostatic cell sorter at Los Alamos in 1965, borrowing the droplet idea from ink-jet printing.",
        "Leonard Herzenberg's group at Stanford built the first fluorescence-activated cell sorter around 1970; FACS later became a Becton Dickinson trademark.",
        "A sorter breaks the stream into droplets by vibrating the nozzle; the droplet holding a wanted cell is charged and deflected by charged plates.",
        "Forward scatter roughly reflects cell size and side scatter reflects granularity.",
        "Modern sorters analyse tens of thousands of cells per second.",
        "Compensation corrects for the light of one fluorophore spilling into another fluorophore's detector.",
        "Doublets, two cells stuck together, are removed by comparing the height and area of the scatter signal.",
    ],
    quiz=QUIZ,
    music=dict(name="Droplet Drum and Bass", bpm=168, beats=4, root=45, mode="min", prog=[0, 0, 5, 6, 0, 0, 3, 4],
               lead="square", comp="drive", drums="dnb", swing=0.0,
               motif=[(7, 1), (7, 1), (4, 2), (7, 1), (8, 1), (7, 2), (4, 1), (3, 1), (2, 1), (0, 3), (2, 2)]),
    stages=[
        ("facs_sort", {}),
        ("facs_gate", {}),
        ("quiz", dict(title="Read the dot plot", questions=[_quad_q, _quad_q, _quad_q, QUIZ[1]], n=3, tint=SKY,
                      instr="Read the GFP versus mCherry plots.")),
    ],
)
TECHS = [TECH]
