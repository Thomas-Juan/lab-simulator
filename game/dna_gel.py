# -*- coding: utf-8 -*-
"""Agarose gel electrophoresis: choose the %, melt the agarose, pour without bubbles, read the bands."""
import math
import pygame
import audio
import gfx
from stage import Stage, register, TOP, BOTTOM
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, LAV, NIGHT, WHITE,
                  GREEN, RED, YELLOW, GEL, DYE, clamp, mix, draw_text, draw_wrapped)
import render as R
import real
from dna_common import (gel_picture, fmt_bp, flask_shape, LADDER_1KB, cached, agarose_slab, steam, pipette_tip, helix,
                        marker_text)


# ------------------------------------------------------------------ quiz: which agarose %
PCT_CASES = [
    ("0.7 %", [12000, 8000, 6000], "Large fragments (5-10 kb and more) need big pores: about 0.7 % agarose."),
    ("1 %", [3000, 1500, 800], "1 % agarose is the all-rounder, good for roughly 0.5-8 kb."),
    ("2 %", [400, 250, 150], "Small fragments (100-500 bp) need tighter pores: about 2 % agarose."),
]


def pct_question(rng):
    ans, sizes, why = rng.choice(PCT_CASES)
    opts = ["0.7 %", "1 %", "2 %", "8 %"]

    def pic(s, r):
        draw_text(s, "Fragments to separate", (r.centerx, r.y + 6), 17, INK, center=True, bold=True)
        for k, sz in enumerate(sizes):
            y = r.y + 70 + k * 80
            ln = 40 + 25 * math.log2(sz / 100.0)
            x0 = r.centerx - ln / 2
            helix(s, x0, y, ln, 7, 30)
            draw_text(s, fmt_bp(sz), (r.centerx, y + 16), 16, INK, center=True, bold=True)
    return dict(q="Which agarose percentage separates these fragments best?", options=opts, answer=opts.index(ans), why=why, pic=pic, keep_order=True)


STATIC_GEL_Q = [
    dict(q="Why does DNA move towards the positive (red) electrode?", options=["Its phosphate backbone is negatively charged", "It is attracted to the dye", "Smaller molecules float", "The buffer pushes it"],
         answer=0, why="Each phosphate in the backbone carries a negative charge, so DNA runs to the anode: 'run to red'."),
    dict(q="Which fragments travel furthest in the same time?", options=["The smallest", "The largest", "The most GC-rich", "They all travel the same distance"],
         answer=0, why="Small fragments slip through the pores of the gel more easily, so they move faster."),
]


# ------------------------------------------------------------------ microwave scene
MW_BOX = pygame.Rect(110, TOP + 56, 620, 380)
MW_WIN = pygame.Rect(MW_BOX.x + 26, MW_BOX.y + 26, 410, MW_BOX.h - 52)


def _microwave_body():
    """A countertop microwave: white enamel housing, a black glass door with its silver handle,
    and a dark control panel with a membrane keypad."""
    sf = pygame.Surface((W, H), pygame.SRCALPHA)
    box, win = MW_BOX, MW_WIN
    sf.blit(R.soft_shadow(box.w, box.h, 18, (10, 10, 24), 120, 12), (box.x - 24 + 6, box.y - 24 + 12))
    sf.blit(real.plastic(box.w, box.h, (238, 238, 234), 18, 0.35), box.topleft)
    door = win.inflate(22, 22)
    sf.blit(real.plastic(door.w, door.h, (30, 32, 36), 12, 0.25), door.topleft)
    sf.blit(real.steel(14, door.h - 70, 7), (door.right - 34, door.y + 35))
    panel = pygame.Rect(door.right + 22, box.y + 24, box.right - door.right - 46, box.h - 48)
    sf.blit(real.plastic(panel.w, panel.h, (58, 62, 70), 10, 0.15), panel.topleft)
    for k in range(9):
        c = (panel.centerx - 40 + (k % 3) * 40, panel.y + 104 + (k // 3) * 40)
        sf.blit(real.plastic(30, 26, (196, 200, 206), 6, 0.3), (c[0] - 15, c[1] - 13))
        draw_text(sf, str(k + 1), c, 13, (40, 42, 48), center=True, bold=True, vcenter=True)
    st = pygame.Rect(panel.x + 14, panel.y + 290, panel.w - 28, 34)
    sf.blit(real.plastic(st.w, st.h, (70, 160, 90), 8, 0.3), st.topleft)
    draw_text(sf, "START", st.center, 15, WHITE, center=True, bold=True, vcenter=True)
    for k in range(10):
        pygame.draw.line(sf, (200, 200, 196), (box.right - 160 + k * 12, box.bottom - 14), (box.right - 154 + k * 12, box.bottom - 14), 3)
    return sf, panel


def _mesh(w, h):
    """The perforated metal screen inside a microwave door, plus a faint reflection on the glass."""
    sf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(3, h, 5):
        for x in range(3 + (y // 5 % 2) * 2, w, 5):
            pygame.draw.circle(sf, (16, 14, 18, 46), (x, y), 1)
    pygame.draw.polygon(sf, (255, 255, 255, 14), [(0, 0), (w * 0.45, 0), (w * 0.2, h), (0, h)])
    return sf


def _flask_sprite(w, h):
    """An empty borosilicate Erlenmeyer flask with white printed graduations (cached)."""
    def make():
        S = 3
        sf = pygame.Surface(((w + 20) * S, (h + 20) * S), pygame.SRCALPHA)
        pts = [((x + w / 2 + 10) * S, (y + 10) * S) for x, y in flask_shape(0, 0, w, h)]
        mask = pygame.Surface(sf.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255), pts)
        prof = real.cyl_profile(sf.get_width(), 0.3, 0.05, 0.6, 0.55)
        glass = real.shaded_mask(mask, (210, 228, 234), prof, 60)
        sf.blit(glass, (0, 0))
        sf.blit(real.soft_edge(mask, (120, 150, 160), 3 * S), (0, 0))
        nx = (w / 2 + 10) * S
        pygame.draw.rect(sf, (230, 236, 238, 200), (nx - w * 0.24 * S, 7 * S, w * 0.48 * S, 6 * S), border_radius=2 * S)
        for k in range(4):
            y = (h * 0.62 + 10 - k * h * 0.11) * S
            pygame.draw.line(sf, (255, 255, 255, 230), (nx + w * 0.08 * S, y), (nx + w * 0.2 * S, y), 2 * S)
        return pygame.transform.smoothscale(sf, (w + 20, h + 20))
    return cached(("flask", w, h), make)


def microwave_scene(st, s, v):
    gfx.bench(s, PEACH)
    body, panel = cached("mw_body", _microwave_body)
    s.blit(body, (0, 0))
    win = MW_WIN
    running = st.state == "run"
    s.blit(R.vgrad(win.size, (255, 236, 170), (232, 196, 120)) if running else R.vgrad(win.size, (206, 198, 184), (168, 160, 146)), win.topleft)
    if running:
        gfx.glow(s, (win.centerx, win.y + 20), 220, (60, 44, 10))
    cx, base = win.centerx, win.bottom - 34
    # glass turntable
    gfx.alpha_rect(s, (cx - 160, base - 10, 320, 30), (220, 230, 236), 90, 15)
    pygame.draw.arc(s, (255, 255, 255), (cx - 150, base - 8, 300, 26), 2.4, 3.0, 2)
    wob = math.sin(st.t * 0.08) * 6 if running else 0
    fx = cx + wob
    top = base - 214
    clear = clamp(v / 0.62, 0, 1)
    liquid_top = base - 78 - (v - 0.8) / 0.2 * 30 * (v > 0.8)
    pts = flask_shape(fx, top, 168, 212)
    s.blit(R.soft_shadow(150, 16, 8, (0, 0, 0), 90, 6), (fx - 75 - 12, base - 8))
    liq = pygame.Surface(win.size, pygame.SRCALPHA)
    lp = [(x - win.x, y - win.y) for x, y in pts]
    cloudy = mix((240, 238, 228), (206, 226, 236), clear)
    R.aa_poly(liq, cloudy + (int(235 - 110 * clear),), lp, 0, None)
    pygame.draw.rect(liq, (0, 0, 0, 0), (0, 0, win.w, int(liquid_top - win.y)))
    s.blit(liq, win.topleft)
    pygame.draw.line(s, mix(cloudy, WHITE, 0.6), (fx - 60, liquid_top + 1), (fx + 60, liquid_top + 1), 2)
    for k in range(int(46 * (1 - clear))):          # undissolved agarose grains
        gx = fx - 62 + (k * 37) % 124
        gy = liquid_top + 12 + (k * 23) % 58
        gfx.alpha_circle(s, (250, 250, 244), (gx, gy), 2, 220)
    if v > 0.5:                                     # boiling bubbles
        for k in range(int((v - 0.5) * 70)):
            bx = fx - 58 + (k * 41 + st.t * 3) % 116
            by = liquid_top + 62 - ((k * 17 + st.t * 2.5) % 62)
            gfx.alpha_circle(s, (255, 255, 255), (bx, by), 3, 130)
            gfx.alpha_circle(s, (255, 255, 255), (bx - 1, by - 1), 1, 240)
    if v > 0.8:                                     # foam rising up the neck
        foam = (v - 0.8) / 0.2 * 150
        for k in range(22):
            yy = liquid_top - foam * (k / 21.0)
            half = 72 - 50 * clamp((liquid_top - yy) / 70.0, 0, 1)
            gfx.alpha_circle(s, (250, 250, 246), (fx - half * 0.6 + (k * 19) % (half * 1.2 + 1), yy), 9 + (k % 3), 235)
    if v >= 1 or st.state == "over":
        for k in range(12):
            gfx.alpha_circle(s, (250, 250, 246), (fx - 34 + k * 7, top - 6 + (k % 3) * 5), 8, 240)
        for k in range(6):
            gfx.alpha_circle(s, (240, 238, 228), (fx + 80 - k * 34, base + 6), 10, 230)
    fl = _flask_sprite(168, 212)
    s.blit(fl, (int(fx - 84 - 10), int(top - 10)))
    tape = pygame.Rect(int(fx - 46), int(top + 120), 92, 22)
    gfx.alpha_rect(s, tape, (244, 238, 214), 235, 1)
    lab = marker_text("1 % agarose TAE", 13, (24, 34, 110), 0)
    s.blit(lab, (tape.centerx - lab.get_width() // 2, tape.centery - lab.get_height() // 2))
    s.blit(cached("mw_mesh", lambda: _mesh(win.w, win.h)), win.topleft)
    # the dark door glass in front of the cavity
    gfx.alpha_rect(s, win, (20, 16, 10), 60 if running else 110, 8)
    if v >= 1 or st.state == "over":
        draw_text(s, "Boiled over!", (win.centerx, win.y + 20), 22, RED, center=True, bold=True, shadow=WHITE)
    scr = pygame.Rect(panel.x + 14, panel.y + 18, panel.w - 28, 46)
    gfx.screen_rect(s, scr, (30, 40, 36))
    left = max(0, int(90 * (1 - v)))
    draw_text(s, "%d:%02d" % (left // 60, left % 60) if running else "--:--", scr.center, 22, (140, 255, 170), center=True, bold=True, mono=True, vcenter=True)
    stop = pygame.Rect(panel.x + 14, panel.y + 240, panel.w - 28, 40)
    s.blit(real.plastic(stop.w, stop.h, (210, 66, 52) if running else (150, 66, 60), 8, 0.3), stop.topleft)
    draw_text(s, "STOP", stop.center, 18, WHITE, center=True, bold=True, vcenter=True)


MICRO = dict(title="Melt the agarose", scene=microwave_scene, dur=7, ideal=0.78, window=(0.70, 0.88), rounds=2, speed_up=0.8, jitter=0.12,
             instr="Agarose only dissolves near boiling. Stop the microwave when the solution turns clear, before it foams up and boils over. Two flasks.",
             readout=lambda v: "%d deg C" % int(20 + 78 * clamp(v / 0.75, 0, 1)),
             early_msg="Still cloudy: undissolved agarose gives a lumpy gel with uneven lanes.",
             late_msg="It was starting to foam: superheated agarose can erupt out of the flask. Heat in short bursts and swirl.",
             over_msg="It boiled over: you lost gel solution, and the water that boiled off raised the agarose percentage. Use short bursts and swirl between them.",
             good_msg="Clear and fully dissolved, without boiling over.")


# ------------------------------------------------------------------ pour and pop bubbles
@register("gel_pour")
class PourStage(Stage):
    title = "Pour the gel"
    instr = "Click the comb to drop it into the tray, then pop every air bubble with a tip before the gel sets. Bubbles near the wells distort the lanes."
    limit = 20

    def setup(self):
        self.tray = pygame.Rect(170, TOP + 90, 560, 330)
        self.comb_in = False
        self.comb_y = TOP + 26
        self.bubbles = []
        self.spawn = [self.rng.uniform(0.2, self.limit * 0.45) for _ in range(self.lv(10, 14, 18))]
        self.popped = 0
        self.total = len(self.spawn)
        self.mouse = (0, 0)
        self.pokes = []                     # holes stabbed into the gel where there was no bubble
        self.free_pokes = self.lv(4, 2, 1)
        self.instr += " Stabbing the gel where there is no bubble leaves a hole."

    def comb_rect(self):
        return pygame.Rect(self.tray.x + 30, self.comb_y, self.tray.w - 60, 40)

    def tick(self, inp):
        self.mouse = inp.mouse
        sec = self.t / 60.0
        for t0 in list(self.spawn):
            if sec >= t0:
                self.spawn.remove(t0)
                self.bubbles.append([self.rng.uniform(self.tray.x + 20, self.tray.right - 20), self.rng.uniform(self.tray.y + 20, self.tray.bottom - 20),
                                     self.rng.uniform(5, 11), self.rng.uniform(0, 6.28)])
        for b in self.bubbles:
            b[3] += 0.03
            b[0] += math.cos(b[3]) * 0.15
            b[1] += math.sin(b[3] * 0.7) * 0.1
        if self.comb_in:
            self.comb_y += (self.tray.y + 12 - self.comb_y) * 0.2
        if inp.click:
            if not self.comb_in and self.comb_rect().inflate(10, 10).collidepoint(inp.mouse):
                self.comb_in = True
                audio.sfx("click")
                return
            hit = False
            for b in self.bubbles:
                if math.hypot(inp.mouse[0] - b[0], inp.mouse[1] - b[1]) < b[2] + 7:
                    self.bubbles.remove(b)
                    self.popped += 1
                    audio.sfx("pop")
                    self.particles.burst(b[0], b[1], 8, cols=(WHITE, SKY), speed=2.5, size=2)
                    hit = True
                    break
            if not hit and self.tray.inflate(-10, -10).collidepoint(inp.mouse):
                self.pokes.append(inp.mouse)
                if len(self.pokes) > self.free_pokes:
                    audio.sfx("bad")
                    self.shake = 6
                    if self.t - getattr(self, "_hole_t", -99) >= 30:     # one label at a time, or they pile up
                        self._hole_t = self.t
                        self.floaters.add(inp.mouse[0], inp.mouse[1] - 18, "hole in the gel", RED, 15)
                else:
                    audio.sfx("tick")
        if not self.spawn and not self.bubbles and self.comb_in:
            self.finish(100 - self.poke_penalty(), *self.summary())

    def poke_penalty(self):
        return 5 * max(0, len(self.pokes) - self.free_pokes)

    def summary(self):
        left = len(self.bubbles) + len(self.spawn)
        near = sum(1 for b in self.bubbles if b[1] < self.tray.y + 70)
        fb = ["%d of %d bubbles popped." % (self.popped, self.total)]
        if left:
            fb.append("%d left in the gel%s." % (left, (", %d of them right by the wells" % near) if near else ""))
        else:
            fb.append("No bubbles and the comb is in: clean, straight wells.")
        bad = max(0, len(self.pokes) - self.free_pokes)
        if bad:
            fb.append("%d extra hole%s stabbed in the gel: aim at the bubbles." % (bad, "" if bad == 1 else "s"))
        return fb

    def partial(self):
        sc = 100 * self.popped / self.total
        if not self.comb_in:
            sc -= 40
        return sc - self.poke_penalty()

    def update(self, inp):
        was = self.done
        Stage.update(self, inp)
        if self.done and not was and self.feedback == ["Time ran out."]:
            self.feedback = ["The gel set before you were done."] + self.summary()[:2]
            if not self.comb_in:
                self.feedback = ["No comb: the gel has no wells to load!"] + self.feedback[1:]

    def autoplay(self):
        self.finish(92, "(autoplay)")

    @staticmethod
    def _floor(w, h):
        sf = pygame.Surface((w, h), pygame.SRCALPHA)
        sf.fill((214, 226, 232, 255))
        for x in range(0, w, 20):
            pygame.draw.line(sf, (176, 190, 200, 255), (x, 0), (x, h), 1 if x % 100 else 2)
        for y in range(0, h, 20):
            pygame.draw.line(sf, (190, 202, 210, 255), (0, y), (w, y), 1)
        return sf

    @staticmethod
    def _sheen(h):
        sf = pygame.Surface((120, h), pygame.SRCALPHA)
        for x in range(120):
            a = int(70 * math.exp(-((x - 60) / 26.0) ** 2))
            pygame.draw.line(sf, (255, 255, 255, a), (x + h * 0.25, 0), (x - h * 0.25 + 60, h), 1)
        return sf

    def render(self, s):
        gfx.bench(s, SKY)
        setf = clamp(self.t / 60.0 / self.limit, 0, 1)
        tr = self.tray
        base = tr.inflate(60, 50)
        # casting stand (grey moulded plastic), UV-transparent acrylic tray, black rubber end gates
        s.blit(R.soft_shadow(base.w, base.h, 14, (10, 10, 24), 110, 10), (base.x - 20 + 5, base.y - 20 + 9))
        s.blit(real.plastic(base.w, base.h, (150, 156, 166), 14, 0.3), base.topleft)
        for x in (base.x + 8, base.right - 28):
            s.blit(real.plastic(20, tr.h + 12, (28, 28, 32), 6, 0.25), (x, tr.y - 6))
        hot = mix((244, 238, 222), (226, 236, 240), setf)
        # the acrylic tray floor with its ruler lines shows through the clear molten agarose
        floor = cached(("tray_floor", tr.w, tr.h), lambda: self._floor(tr.w, tr.h))
        s.blit(floor, tr.topleft)
        slab = agarose_slab(tr.w, tr.h, hot, 45).copy()
        slab.set_alpha(int(150 + 90 * setf))
        s.blit(slab, tr.topleft)
        gfx.alpha_rect(s, tr, (255, 250, 236), int(60 * (1 - setf)), 4)
        # meniscus: the agarose climbs the tray walls, darker along the edges
        for k in range(6):
            gfx.rrect(s, tr.inflate(-2 * k, -2 * k), None, mix((170, 178, 186), hot, k / 6.0), 1, 4)
        # a slow sheen across the liquid surface (fades as the gel sets)
        sx = tr.x + (self.t * 1.2) % (tr.w + 200) - 100
        sheen = cached(("sheen", tr.h), lambda: self._sheen(tr.h))
        sheen.set_alpha(int(110 * (1 - setf)) + 30)
        s.blit(sheen, (int(sx), tr.y), special_flags=0)
        for px, py in self.pokes:                 # stab holes: a dark dimple with a bright rim
            gfx.alpha_circle(s, (110, 120, 130), (px, py), 4, 120)
            gfx.alpha_circle(s, WHITE, (px - 1, py - 1), 2, 160)
        s.blit(real.glass(tr.w + 10, tr.h + 10, (220, 236, 242), 40, 6), (tr.x - 5, tr.y - 5))
        if setf < 0.75:
            for k in range(4):
                steam(s, tr.x + 90 + k * 130, tr.y + 40, self.t + k * 37, 2, 70, int(60 * (1 - setf / 0.75)), 26)
        for x, y, r, _ in self.bubbles:            # air bubbles: clear, a dark lower rim, a bright glint
            gfx.alpha_circle(s, (70, 80, 96), (x, y + 0.5), r, 70)
            gfx.alpha_circle(s, (246, 250, 252), (x, y - 0.5), r - 1, 170)
            gfx.alpha_circle(s, (226, 232, 238), (x, y), r - 2.5, 200)
            gfx.alpha_circle(s, WHITE, (x - r * 0.35, y - r * 0.38), max(1.5, r * 0.3), 250)
        c = self.comb_rect()
        gap = c.w / 9.0
        comb = (40, 44, 52)
        if self.comb_in:
            for k in range(8):
                s.blit(real.plastic(22, 12, comb, 2, 0.2), (c.x + gap * (k + 1) - 11, c.y + 14))
            s.blit(real.plastic(c.w, 16, comb, 4, 0.35), c.topleft)
        else:
            s.blit(R.soft_shadow(c.w, 16, 6, (0, 0, 0), 90, 6), (c.x - 12 + 8, c.y - 12 + 34))
            s.blit(real.plastic(c.w, 16, comb, 4, 0.35), c.topleft)
            for k in range(8):
                s.blit(real.plastic(20, 26, comb, 3, 0.3), (c.x + gap * (k + 1) - 10, c.y + 13))
            if (self.t // 20) % 2 == 0:
                gfx.rrect(s, c.inflate(14, 14), None, CORAL, 3, 8)
                draw_text(s, "click the comb", (c.centerx, c.y - 24), 14, CORAL_D, center=True, bold=True)
        gfx.card(s, (790, TOP + 90, 150, 210), CARD)
        draw_text(s, "Setting", (865, TOP + 102), 15, INK, center=True, bold=True)
        gfx.bar(s, (806, TOP + 130, 118, 18), setf, TURQ)
        draw_text(s, "hot" if setf < 0.5 else "setting" if setf < 1 else "set", (865, TOP + 152), 13, MUTED, center=True)
        draw_text(s, "Bubbles", (865, TOP + 184), 15, INK, center=True, bold=True)
        draw_text(s, "%d popped" % self.popped, (865, TOP + 208), 18, GREEN, center=True, bold=True)
        draw_text(s, "%d left" % len(self.bubbles), (865, TOP + 236), 18, CORAL_D, center=True, bold=True)
        pipette_tip(s, self.mouse)

# ------------------------------------------------------------------ quiz: read band sizes
SAMPLE_SIZES = [750, 1200, 1800, 2500, 3500, 4500, 7000, 600]


def band_question(rng):
    size = rng.choice(SAMPLE_SIZES)
    others = [x for x in SAMPLE_SIZES if abs(math.log(x / size)) > 0.25]
    rng.shuffle(others)
    opts = [fmt_bp(size)] + [fmt_bp(x) for x in others[:3]]

    def pic(s, r):
        draw_text(s, "1 kb ladder (lane L) and your sample (lane S)", (r.centerx, r.y), 14, INK_SOFT, center=True, bold=True)
        gel_picture(s, pygame.Rect(r.x + 40, r.y + 24, r.w - 120, r.h - 30), [LADDER_1KB, [size]], lane_names=["L", "S"], span=(14000, 350))
    return dict(q="How big is the band in lane S?", options=opts, answer=0, why="Compare the band with the ladder bands just above and below it: their sizes bracket it.", pic=pic)


TECH = dict(
    key="gel", name="Agarose gel", full="Agarose gel electrophoresis", wing="DNA", icon="gel",
    blurb="Sorts DNA fragments by size in an electric field, so you can see whether a PCR or digest gave the band you expected.",
    facts=[
        "Agarose is the main polysaccharide of agar, which is extracted from red seaweeds.",
        "DNA runs towards the positive electrode because every phosphate in its backbone carries a negative charge. Lab shorthand: 'run to red'.",
        "Ethidium bromide slips between the base pairs of DNA and glows orange under UV. Many labs now use less hazardous dyes such as SYBR Safe or GelRed.",
        "In a 1 % gel the blue loading dye bromophenol blue runs roughly with fragments of about 300 bp, so it tells you how far your small bands have gone.",
        "Pulsed-field gel electrophoresis keeps switching the direction of the field and can separate DNA molecules millions of base pairs long, such as whole yeast chromosomes.",
        "The same plasmid can give several bands: supercoiled, nicked and linear forms run at different speeds even though they have the same length.",
        "The distance a fragment travels falls roughly in a straight line with the logarithm of its size, which is why ladders are read on a log scale.",
    ],
    quiz=[
        STATIC_GEL_Q[0],
        dict(q="Which agarose percentage suits fragments of 100-500 bp?", options=["About 2 %", "About 0.5 %", "About 0.7 %", "Agarose percentage does not matter"],
             answer=0, why="A higher percentage gives smaller pores that separate small fragments."),
        dict(q="What is the DNA ladder for?", options=["To estimate the sizes of your bands", "To stain the DNA", "To make the DNA sink into the well", "To carry the current"],
             answer=0, why="A ladder is a mix of fragments of known sizes run beside your samples."),
    ],
    music=dict(name="Agarose Waltz", bpm=138, beats=3, root=53, mode="maj", prog=[0, 3, 4, 0, 5, 1, 4, 4], lead="bell", comp="waltz", drums="none",
               motif=[(4, 2), (5, 1), (4, 1), (2, 2), (0, 4), (2, 2)]),
    stages=[
        ("quiz", dict(title="Choose the gel", questions=[pct_question, pct_question] + STATIC_GEL_Q, n=3,
                      instr="Pick the agarose percentage for the fragments shown and answer questions on how DNA runs in a gel.")),
        ("stop", MICRO),
        ("gel_pour", {}),
        ("quiz", dict(title="Read the gel", questions=[band_question, band_question, band_question], n=3,
                      instr="Estimate each band size by comparing it with the ladder.")),
    ],
)
TECHS = [TECH]
