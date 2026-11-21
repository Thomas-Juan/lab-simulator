# -*- coding: utf-8 -*-
"""Bacterial transformation: heat shock, spreading the plate, blue/white screening."""
import math
import pygame
import audio
import gfx
import real
from stage import Stage, register, TOP, BOTTOM
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, TEAL, LAV, VIOLET,
                  WHITE, GREEN, RED, YELLOW, BLUE, clamp, mix, draw_text, draw_wrapped)

import render as R
from dna_common import water_bath, ice_bucket, stopwatch, steam, colony, spreader, toothpick, magnifier, marker_text

AGAR = (242, 220, 160)


# ------------------------------------------------------------------ heat shock (scene for the stop stage)
def heat_scene(st, s, v):
    gfx.bench(s, SKY)
    bath = pygame.Rect(140, TOP + 176, 450, 270)
    for k in range(3):
        steam(s, bath.x + 110 + k * 120, bath.y + 30, st.t + k * 50, 2, 70, 70, 30, (190, 206, 222))
    water = water_bath(s, bath, st.t)
    ice = pygame.Rect(650, TOP + 306, 240, 140)
    if st.state == "run":
        tx, ty = water.centerx - 13, water.y - 40
        gfx.tube(s, tx, ty, 26, 70, (230, 220, 200), 0.4, CORAL)
        gfx.alpha_rect(s, (tx - 2, water.y + 2, 30, 34), (90, 160, 210), 110, 4)
        s.blit(real.plastic(78, 12, (246, 246, 240), 5, 0.3), (tx - 26, water.y - 6))      # foam float
        for k in range(3):
            pygame.draw.arc(s, (230, 246, 252), (tx - 30 - k * 10, water.y - 6 - k * 4, 86 + k * 20, 16 + k * 8), 3.4, 6.0, 1)
        ice_bucket(s, ice)
    else:
        tx, ty = ice.centerx - 13, ice.y - 66
        gfx.tube(s, tx, ty, 26, 70, (230, 220, 200), 0.4, CORAL)
        ice_bucket(s, ice)
    lo, hi = getattr(st, "window", (0.66, 0.84))
    stopwatch(s, (296, TOP + 96), 62, v * 60, (lo * 60, hi * 60))
    gfx.card(s, (606, TOP + 86, 330, 140), CARD)
    draw_text(s, "Heat shock at 42 deg C", (624, TOP + 100), 20, INK, bold=True)
    draw_wrapped(s, "The sudden heat makes the cell membrane leaky for a moment, and the plasmid slips in. Then straight back on ice.",
                 (624, TOP + 132), 15, 296, INK_SOFT)

HEAT = dict(title="Heat shock", scene=heat_scene, dur=7, ideal=0.75, window=(0.62, 0.86), rounds=2, speed_up=0.8,
            instr="The clock runs fast. Lift the tube out of the 42 deg C bath at 45 seconds (the green zone): click or press Space.",
            readout=lambda v: "00:%02d" % min(59, int(v * 60)),
            early_msg="Too short: fewer cells take up the plasmid.",
            late_msg="Too long for this protocol: efficiency drops when the shock runs over.",
            over_msg="A minute or more at 42 deg C is longer than most kits ask for, and efficiency drops.",
            good_msg="About 45 s: a standard heat shock for chemically competent E. coli.")


# ------------------------------------------------------------------ spread the plate
@register("transform_spread")
class SpreadStage(Stage):
    title = "Spread the plate"
    instr = "Hold the mouse button and sweep the glass spreader across the agar until the whole plate is covered. Fast jabs tear the agar."
    limit = 18

    def setup(self):
        self.c = (400, (TOP + BOTTOM) // 2)
        self.r = 185
        self.cell = 14
        self.cells = {}
        for gx in range(-14, 15):
            for gy in range(-14, 15):
                x, y = self.c[0] + gx * self.cell, self.c[1] + gy * self.cell
                if math.hypot(x - self.c[0], y - self.c[1]) < self.r - 8:
                    self.cells[(gx, gy)] = math.hypot(gx, gy) < 2.2
        self.tears = []
        self.mouse = self.c
        self.prev = None
        self.tear_at = self.lv(60, 45, 34)
        self.target = self.lv(0.93, 0.97, 0.98)
        self.half = self.lv(48, 40, 32)          # half the width of the spreader's working edge
        self.wet = pygame.Surface((self.r, self.r), pygame.SRCALPHA)   # half-resolution map of the spread film
        self.wet_dirty = True

    def coverage(self):
        return sum(self.cells.values()) / float(len(self.cells))

    def tick(self, inp):
        self.mouse = inp.mouse
        mx, my = inp.mouse
        inside = math.hypot(mx - self.c[0], my - self.c[1]) < self.r
        if inp.down and inside:
            if self.prev is not None and math.dist(self.prev, inp.mouse) > self.tear_at and self.t - getattr(self, "last_tear", -99) > 15 and len(self.tears) < 12:
                self.last_tear = self.t
                self.tears.append((mx, my, self.rng.uniform(0, 3)))
                audio.sfx("bad")
                self.floaters.add(mx, my - 20, "torn!", RED, 18)
                self.shake = 8
            ox, oy = self.c[0] - self.r, self.c[1] - self.r
            a = ((self.prev or inp.mouse)[0] - ox) / 2.0, ((self.prev or inp.mouse)[1] - oy) / 2.0
            b = (mx - ox) / 2.0, (my - oy) / 2.0
            pygame.draw.line(self.wet, (255, 255, 255, 255), a, b, self.half)
            pygame.draw.circle(self.wet, (255, 255, 255, 255), (int(b[0]), int(b[1])), self.half // 2)
            self.wet_dirty = True
            for (gx, gy) in self.cells:
                x, y = self.c[0] + gx * self.cell, self.c[1] + gy * self.cell
                if abs(x - mx) < self.half and abs(y - my) < 12:
                    if not self.cells[(gx, gy)]:
                        self.cells[(gx, gy)] = True
            if self.t % 45 == 0:
                audio.sfx("pour")
            self.prev = inp.mouse
        else:
            self.prev = None
        if self.coverage() >= self.target:
            self.finish(100 - 8 * len(self.tears), "The whole plate is covered evenly in %.1f s." % (self.t / 60.0),
                        "%d tear%s in the agar: slow, smooth sweeps." % (len(self.tears), "" if len(self.tears) == 1 else "s") if self.tears else "No tears in the agar.",
                        "Even spreading gives single colonies across the plate instead of a lawn in the middle.")

    def partial(self):
        return clamp(self.coverage() / self.target * 100 - 15, 0, 100) - 8 * len(self.tears)

    def update(self, inp):
        was = self.done
        Stage.update(self, inp)
        if self.done and not was and self.feedback == ["Time ran out."]:
            self.feedback = ["You covered %d %% of the plate. Bare patches give no colonies, the puddle gives a lawn." % int(self.coverage() * 100)]
            if self.tears:
                self.feedback.append("%d tear%s in the agar: sweep smoothly instead of jabbing." % (len(self.tears), "" if len(self.tears) == 1 else "s"))

    def autoplay(self):
        self.finish(92, "(autoplay)")

    def render(self, s):
        gfx.bench(s, PEACH)
        gfx.shadow(s, (self.c[0] - self.r - 8, self.c[1] - self.r - 8, 2 * self.r + 16, 2 * self.r + 16), self.r + 8, (4, 8), 60, 8)
        gfx.petri(s, self.c, self.r, AGAR)
        if self.wet_dirty and (self.t % 3 == 0 or getattr(self, "_wet_img", None) is None):
            self.wet_dirty = False
            n = self.r
            soft = pygame.transform.smoothscale(pygame.transform.smoothscale(self.wet, (max(1, n // 4), max(1, n // 4))), (n, n))
            big = pygame.transform.smoothscale(soft, (2 * self.r, 2 * self.r))
            film = pygame.Surface((2 * self.r, 2 * self.r), pygame.SRCALPHA)
            film.fill((255, 250, 230, 255))
            film.blit(big, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            film.fill((255, 255, 255, 80), special_flags=pygame.BLEND_RGBA_MULT)
            mask = pygame.Surface((2 * self.r, 2 * self.r), pygame.SRCALPHA)
            pygame.draw.circle(mask, (255, 255, 255, 255), (self.r, self.r), self.r - 2)
            film.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self._wet_img = film
        s.blit(self._wet_img, (self.c[0] - self.r, self.c[1] - self.r))
        label = marker_text("LB Amp  X-gal IPTG", 15, (30, 40, 110), 8)
        s.blit(label, (self.c[0] - label.get_width() // 2, self.c[1] + self.r - 44))
        pud = int(42 * (1 - self.coverage()))
        if pud > 4:            # the drop of cell suspension: a glossy puddle
            gfx.alpha_circle(s, (200, 168, 100), self.c, pud + 1, 70)
            gfx.alpha_circle(s, (246, 236, 200), self.c, pud - 1, 150)
            gfx.alpha_circle(s, WHITE, (self.c[0] - pud * 0.35, self.c[1] - pud * 0.4), pud * 0.28, 210)
        for x, y, a in self.tears:
            gfx.line(s, mix(AGAR, (60, 40, 20), 0.55), (x - 9 * math.cos(a), y - 9 * math.sin(a)), (x + 9 * math.cos(a), y + 9 * math.sin(a)), 3)
            gfx.line(s, (255, 250, 230), (x - 8 * math.cos(a), y - 8 * math.sin(a) - 2), (x + 8 * math.cos(a), y + 8 * math.sin(a) - 2), 1)
        spreader(s, self.mouse)
        gfx.card(s, (650, TOP + 30, 280, 220), CARD)
        draw_text(s, "Coverage", (790, TOP + 44), 18, INK, center=True, bold=True)
        gfx.bar(s, (680, TOP + 78, 220, 24), self.coverage(), TURQ)
        draw_text(s, "%d %%" % int(self.coverage() * 100), (790, TOP + 110), 26, INK, center=True, bold=True)
        draw_wrapped(s, "Spread until the liquid is absorbed, so each cell grows into its own colony.", (670, TOP + 150), 14, 240, INK_SOFT)

# ------------------------------------------------------------------ blue / white screening
@register("transform_screen")
class ScreenStage(Stage):
    title = "Blue / white screening"
    instr = ("Pick every white colony with a toothpick: they most likely carry a plasmid with your insert. "
             "Blue colonies have an empty vector. Tiny satellite colonies around a big one have no plasmid at all.")
    limit = 35

    def setup(self):
        self.c = (360, (TOP + BOTTOM) // 2)
        self.r = 190
        self.col = []
        rng = self.rng

        def free(x, y, rr):
            if math.hypot(x - self.c[0], y - self.c[1]) > self.r - rr - 8:
                return False
            if abs(x - self.c[0]) < 100 and y > self.c[1] + self.r - 62:     # keep the marker label readable
                return False
            return all(math.hypot(x - a, y - b) > rr + r2 + 4 for a, b, r2, _ in self.col)

        def place(kind, rr, near=None):
            for _ in range(300):
                if near:
                    ang, d = rng.uniform(0, math.tau), rng.uniform(near[2] + 8, near[2] + 26)
                    x, y = near[0] + math.cos(ang) * d, near[1] + math.sin(ang) * d
                else:
                    x, y = rng.uniform(self.c[0] - self.r, self.c[0] + self.r), rng.uniform(self.c[1] - self.r, self.c[1] + self.r)
                if free(x, y, rr):
                    self.col.append([x, y, rr, kind])
                    return self.col[-1]
            return None
        bigs = [place("blue", 14)] + ([place("blue", 13)] if self.level else [])
        for b in bigs:
            if b:
                for _ in range(rng.randint(4, 6)):
                    place("sat", rng.uniform(2.5, 3.5), b)
        for _ in range(self.lv(6, 7, 6)):
            place("white", rng.uniform(7, 10))
        if self.level == 2:
            # white colonies growing into a blue one are not isolated: they could be a mixture
            for _ in range(2):
                w = place("white", rng.uniform(7, 9))
                if w:
                    for _try in range(60):
                        ang = rng.uniform(0, math.tau)
                        rr = rng.uniform(7, 9)
                        x, y = w[0] + math.cos(ang) * (w[2] + rr - 2), w[1] + math.sin(ang) * (w[2] + rr - 2)
                        if math.hypot(x - self.c[0], y - self.c[1]) < self.r - rr - 8 and all(
                                math.hypot(x - a_, y - b_) > rr + r2 + 2 for a_, b_, r2, _k in self.col if (a_, b_) != (w[0], w[1])):
                            w[3] = "mixed"
                            self.col.append([x, y, rr, "blue"])
                            break
            for _ in range(3):
                place("pale", rng.uniform(7, 9))
        for _ in range(self.lv(16, 22, 20)):
            place("blue", rng.uniform(7, 10))
        self.total = sum(1 for c in self.col if c[3] == "white")
        self.penalty = self.lv(10, 15, 20)
        self.wrong_kinds = []
        if self.level == 2:
            self.instr = ("Pick every white colony that stands on its own. Blue colonies have an empty vector, tiny satellites have no plasmid, "
                          "pale blue ones are doubtful, and a white colony touching a blue one may be a mixture of both.")
        self.picked = 0
        self.wrong = 0
        self.mouse = self.c
        self.lens = None

    def tick(self, inp):
        self.mouse = inp.mouse
        if not inp.click:
            return
        best, bd = None, 1e9
        for c in self.col:
            d = math.hypot(inp.mouse[0] - c[0], inp.mouse[1] - c[1])
            if d < c[2] + 5 and d < bd:
                best, bd = c, d
        if best is None:
            return
        x, y, rr, kind = best
        if kind == "white":
            self.col.remove(best)
            self.picked += 1
            audio.sfx("good")
            self.particles.burst(x, y, 10, cols=(WHITE, YELLOW))
            self.floaters.add(x, y - 18, "insert!", GREEN, 18)
            if self.picked == self.total:
                self.finish(100 - self.penalty * self.wrong, *self.summary())
        else:
            self.wrong += 1
            self.wrong_kinds.append(kind)
            self.shake = 10
            audio.sfx("bad")
            msg = {"blue": "empty vector", "sat": "satellite!", "pale": "pale blue: doubtful", "mixed": "touching a blue one"}[kind]
            self.floaters.add(x, y - 18, msg, RED, 16)

    def summary(self):
        fb = ["All %d isolated white colonies picked." % self.total if self.picked == self.total else "%d of %d white colonies picked." % (self.picked, self.total)]
        if self.wrong:
            names = {"blue": "blue", "sat": "satellite", "pale": "pale blue", "mixed": "not isolated"}
            kinds = sorted(set(self.wrong_kinds))
            fb.append("%d wrong pick%s (%s)." % (self.wrong, "" if self.wrong == 1 else "s", ", ".join(names[k] for k in kinds)))
        else:
            fb.append("No wrong picks.")
        fb.append("Next: grow each pick overnight and check the insert by colony PCR or a digest.")
        return fb

    def partial(self):
        return max(0, 100 * self.picked / max(1, self.total) - self.penalty * self.wrong)

    def autoplay(self):
        self.finish(85, "(autoplay)")

    def draw_plate(self, s):
        gfx.shadow(s, (self.c[0] - self.r - 8, self.c[1] - self.r - 8, 2 * self.r + 16, 2 * self.r + 16), self.r + 8, (4, 8), 60, 8)
        gfx.petri(s, self.c, self.r, AGAR)
        for k, (x, y, rr, kind) in enumerate(self.col):
            colony(s, x, y, rr, "blue" if kind == "blue" else "white", k % 5)
            if kind == "pale":
                gfx.alpha_circle(s, (96, 146, 236), (x, y), rr - 1, 150)

    def render(self, s):
        gfx.bench(s, LAV)
        self.draw_plate(s)
        label = marker_text("LB Amp  X-gal IPTG", 15, (30, 40, 110), 8)
        s.blit(label, (self.c[0] - label.get_width() // 2, self.c[1] + self.r - 40))
        mx, my = self.mouse
        magnifier(s, s, (mx, my), (770, TOP + 124), 96)
        gfx.card(s, (616, TOP + 244, 324, 180), CARD)
        y = TOP + 258
        rows = [("white", "White: the insert breaks lacZ, no blue", 9), ("blue", "Blue: empty vector, lacZ works", 9),
                ("white", "Tiny: satellite, no plasmid", 3)]
        if self.level == 2:
            rows = rows[:2] + [("pale", "Pale blue: doubtful", 8)]
        for kind, txt, r in rows:
            colony(s, 640, y + 10, r, "blue" if kind == "blue" else "white", 1)
            if kind == "pale":
                gfx.alpha_circle(s, (96, 146, 236), (640, y + 10), r - 1, 150)
            draw_text(s, txt, (658, y), 14, INK)
            y += 32
        draw_text(s, "Picked %d of %d" % (self.picked, self.total), (780, y + 14), 20, GREEN, center=True, bold=True)
        toothpick(s, (mx, my))

TECH = dict(
    key="transform", name="Transformation", full="Bacterial transformation", wing="DNA", icon="transform",
    blurb="Puts a plasmid into bacteria, which then copy it every time they divide. The antibiotic on the plate keeps only the cells that took it up.",
    facts=[
        "In 1928 Frederick Griffith saw a 'transforming principle' pass from dead to living pneumococci. In 1944 Avery, MacLeod and McCarty showed it was DNA.",
        "In 1970 Mandel and Higa found that E. coli treated with calcium chloride takes up DNA, the basis of chemically competent cells.",
        "X-gal is cut by beta-galactosidase into a blue product. An insert inside the lacZ fragment breaks the enzyme, so those colonies stay white.",
        "Satellite colonies grow because resistant colonies secrete beta-lactamase, which destroys the ampicillin around them.",
        "Electroporation, which opens pores with a short electric pulse, can give billions of transformants per microgram of plasmid.",
        "In rich medium at 37 deg C, E. coli can divide about every 20 minutes.",
        "A single colony grown overnight holds hundreds of millions of cells, all descended from one bacterium.",
    ],
    quiz=[
        dict(q="Why are white colonies the ones you want in blue/white screening?", options=["The insert disrupts lacZ, so X-gal is not turned blue", "White cells grow faster", "They lack the antibiotic resistance gene", "They contain no plasmid"],
             answer=0, why="The insert sits inside the lacZ fragment. No working beta-galactosidase means no blue product."),
        dict(q="What does the ampicillin in the plate do?", options=["Kills cells that did not take up the plasmid", "Turns colonies blue", "Makes cells competent", "Feeds the bacteria"],
             answer=0, why="The plasmid carries an ampicillin resistance gene, so only transformed cells survive."),
        dict(q="Why put the cells back on ice right after the heat shock?", options=["The sudden temperature changes help DNA enter and the cold lets membranes recover", "To kill the bacteria", "To freeze the plasmid", "To stop the antibiotic"],
             answer=0, why="The heat shock depends on a sharp temperature jump; the cells then recover on ice before the outgrowth at 37 deg C."),
    ],
    music=dict(name="Heat Shock Polka", bpm=144, beats=4, root=57, mode="maj", prog=[0, 4, 4, 0, 0, 4, 4, 0], lead="whistle", comp="arp",
               drums="march", motif=[(4, 1), (4, 1), (5, 1), (4, 1), (2, 2), (0, 2), (1, 1), (2, 1), (3, 1), (1, 1), (4, 4)]),
    stages=[
        ("stop", HEAT),
        ("transform_spread", {}),
        ("transform_screen", {}),
    ],
)
TECHS = [TECH]
