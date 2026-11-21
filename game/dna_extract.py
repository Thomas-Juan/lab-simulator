# -*- coding: utf-8 -*-
"""DNA & RNA extraction (plasmid miniprep): protocol, gentle inversion, balancing the centrifuge, NanoDrop."""
import math
import random
import pygame
try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None
import audio
import gfx
from stage import Stage, register, TOP, BOTTOM
import render as R
import real
from dna_common import cached, cap_sprite, metal_disc, helix
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, TEAL, LAV, VIOLET,
                  NIGHT, WHITE, GREEN, RED, YELLOW, BLUE, clamp, mix, draw_text, draw_wrapped)

STEPS = [
    ("Pellet the overnight culture", SAND, "Spinning the culture collects the bacteria at the bottom of the tube."),
    ("Resuspend in buffer with RNase A", (240, 220, 160), "RNase A in the resuspension buffer will digest the bacterial RNA."),
    ("Lyse with NaOH / SDS", (170, 200, 240), "SDS dissolves the membranes and NaOH denatures proteins and DNA. Mix by inverting: never vortex."),
    ("Neutralise with acidic salt buffer", (210, 230, 210), "Chromosomal DNA and proteins precipitate as white clumps; the small plasmid renatures and stays in solution."),
    ("Spin down the debris", SAND, "A hard spin pellets the white precipitate; the plasmid is in the clear supernatant."),
    ("Load lysate onto silica column", (230, 210, 240), "In high salt, DNA sticks to the silica membrane."),
    ("Wash with ethanol buffer", (210, 230, 240), "The wash removes salts and proteins while the DNA stays bound."),
    ("Dry spin to remove ethanol", SAND, "Leftover ethanol would spoil enzymes and gels downstream."),
    ("Elute in water or low-salt buffer", (200, 236, 220), "At low salt the DNA lets go of the silica: pure plasmid in your tube."),
]


# ------------------------------------------------------------------ gentle inversion
@register("extract_invert")
class InvertStage(Stage):
    title = "Lyse and neutralise"
    instr = ("Hold the mouse button and move up and down to turn the tube over and back. Invert 6 times after adding the lysis buffer (the lysate turns blue), "
             "then press 'Add neutralisation buffer' and invert 6 times more. Keep the speed in the green band: rough mixing shears "
             "the bacterial chromosome. Lysis must not run past 5 minutes.")
    limit = 40
    N = 6

    def setup(self):
        self.angle = 0.0
        self.speed = 0.0
        self.flip = False
        self.count = 0
        self.phase = "lyse"
        self.shear = 0.0
        self.rough = 0
        self.rough_at = self.lv(15, 12, 10)
        self.lysis_s = self.lv(None, 24.0, 18.0)      # real seconds that stand for the 5 minutes of lysis
        self.lysis_t = 0
        self.over = False
        self.lyse_done_t = None
        self.add_btn = gfx.Button((52, BOTTOM - 74, 196, 44), "Add neutralisation buffer", (210, 230, 210), size=13)
        self.hint = "Slow, smooth turns. Lysis must not last longer than 5 minutes."

    def lysis_minutes(self):
        span = self.lysis_s or 22.0
        return self.lysis_t / 60.0 / span * 5.0

    def tick(self, inp):
        self._inp = inp
        if self.phase == "lyse":
            self.lysis_t += 1
            if self.lysis_s and not self.over and self.lysis_minutes() > 5.0:
                self.over = True
                audio.sfx("buzz")
                self.shake = 14
                self.floaters.add(480, TOP + 60, "Lysis over 5 min!", RED, 24)
            if self.count >= self.N and self.add_btn.hit(inp):
                self.phase = "neutral"
                self.count = 0
                self.flip = False
                audio.sfx("pour")
                self.floaters.f.clear()           # the lysis messages would sit on top of this one
                self.floaters.add(480, TOP + 60, "Neutralisation buffer in", TEAL, 22)
                return
        top, bot = TOP + 80, BOTTOM - 60
        target = self.angle
        if inp.down and not self.add_btn.rect.collidepoint(inp.mouse):
            target = clamp((inp.mouse[1] - top) / float(bot - top), 0, 1) * 180
        new = self.angle + (target - self.angle) * 0.5
        self.spin = getattr(self, "spin", 0.0) * 0.8 + (new - self.angle) * 0.2
        self.speed = self.speed * 0.7 + abs(new - self.angle) * 0.3
        self.angle = new
        if self.speed > self.rough_at:
            self.shear = min(1.0, self.shear + (self.speed - self.rough_at) * 0.004)
            self.rough += 1
            if self.rough % 20 == 1:
                audio.sfx("bad")
                if self.rough % 60 == 1:          # one label at a time, beside the speed gauge
                    self.floaters.add(660, TOP + 60, "Too rough!", RED, 24)
                self.shake = 10
        if self.angle > 165:
            self.flip = True
        if self.angle < 15 and self.flip:
            self.flip = False
            if self.count < self.N:
                self.count += 1
                audio.sfx("good")
                self.floaters.add(480, TOP + 90, "%d" % self.count, GREEN, 30)
                if self.phase == "lyse" and self.count == self.N:
                    self.lyse_done_t = self.t
                    self.floaters.add(480, TOP + 134, "Evenly blue: add the neutralisation buffer", TEAL, 18)
                if self.phase == "neutral" and self.count == self.N:
                    self.finish(*self.result())

    def result(self):
        sc = 100 - 70 * self.shear - (30 if self.over else 0)
        fb = []
        if self.shear < 0.1:
            fb.append("12 gentle inversions: lysed and neutralised evenly.")
        else:
            fb.append("Some turns were too rough (shear %d %%): sheared chromosomal DNA ends up in your prep." % int(self.shear * 100))
        if self.lysis_s:
            if self.over:
                fb.append("Lysis ran past 5 minutes: alkali can denature the plasmid irreversibly.")
            else:
                fb.append("Lysis stopped after %.1f minutes." % min(5.0, self.lysis_minutes()))
        fb.append("The white flocs are chromosomal DNA, proteins and SDS; the plasmid stays in the clear liquid.")
        return (sc,) + tuple(fb)

    def partial(self):
        done = self.count + (self.N if self.phase == "neutral" else 0)
        return max(0, done / (2.0 * self.N) * 80 - 70 * self.shear - (30 if self.over else 0))

    def autoplay(self):
        self.finish(92, "(autoplay)")
    BODY = [(26, 40), (114, 40), (114, 236), (70, 318), (26, 236)]
    INNER = [(30, 44), (110, 44), (110, 235), (70, 312), (30, 235)]

    def tube_layers(self):
        """The tube, close up: milky polypropylene with graduations, a frosted writing patch and a
        natural-coloured lid (drawn over the liquid, so it must stay translucent)."""
        if getattr(self, "_layers", None) is None:
            S = 2
            n = (140 * S, 330 * S)
            out = pygame.Surface(n, pygame.SRCALPHA)
            sc = lambda pts: [(x * S, y * S) for x, y in pts]
            mask = pygame.Surface(n, pygame.SRCALPHA)
            pygame.draw.polygon(mask, (255, 255, 255, 255), sc(self.BODY))
            prof = real.cyl_profile(n[0], 0.3, 0.05, 0.55, 0.6)
            out.blit(real.shaded_mask(mask, (214, 220, 222), prof, 70), (0, 0))
            out.blit(real.soft_edge(mask, (110, 120, 126), 4), (0, 0))
            pygame.draw.line(out, (255, 255, 255, 170), (42 * S, 56 * S), (42 * S, 222 * S), 8)
            pygame.draw.line(out, (255, 255, 255, 90), (99 * S, 60 * S), (99 * S, 190 * S), 3)
            for k in range(5):
                y = (80 + k * 32) * S
                pygame.draw.line(out, (110, 118, 126, 200), (90 * S, y), (110 * S, y), 3)
            pygame.draw.rect(out, (255, 255, 255, 60), (34 * S, 70 * S, 46 * S, 80 * S), border_radius=4 * S)
            lid = pygame.Rect(14 * S, 12 * S, 112 * S, 32 * S)
            lm = pygame.Surface(lid.size, pygame.SRCALPHA)
            pygame.draw.rect(lm, (255, 255, 255, 255), lm.get_rect(), border_radius=8 * S)
            vert = np.linspace(1.12, 0.84, lid.h).astype(np.float32) if np is not None else None
            out.blit(real.shaded_mask(lm, (226, 228, 222), real.cyl_profile(lid.w, 0.3, 0.08, 0.35, 0.72), 245, vert), lid.topleft)
            out.blit(real.soft_edge(lm, (130, 134, 132), 3), lid.topleft)
            outline = pygame.transform.smoothscale(out, (140, 330))
            mask = pygame.Surface((140, 330), pygame.SRCALPHA)
            R.aa_poly(mask, (255, 255, 255), self.INNER, 0, None)
            self._layers = (outline, mask)
        return self._layers

    def compose_tube(self, tilt):
        outline, mask = self.tube_layers()
        ang = -self.angle
        ro = pygame.transform.rotate(outline, ang)
        rm = pygame.transform.rotate(mask, ang)
        mixed = self.count / float(self.N)
        liq = pygame.Surface(rm.get_size(), pygame.SRCALPHA)
        if self.phase == "lyse":
            # the blue lysis buffer streaks through the cloudy suspension until it is evenly blue
            liq.fill(mix((236, 240, 248), (96, 136, 224), 0.25 + 0.75 * mixed) + (255,))
            if mixed < 1:
                for k in range(6):
                    yy = 40 + k * rm.get_height() / 6.0
                    pts = [(x, yy + math.sin(x / 26.0 + k * 1.7 + self.angle / 30.0) * 14) for x in range(0, rm.get_width() + 10, 10)]
                    pygame.draw.lines(liq, (50, 90, 200), False, pts, max(1, int(9 * (1 - mixed))))
        else:
            # neutralisation: the blue clears and white flocs of chromosomal DNA and SDS form
            liq.fill(mix((110, 146, 226), (236, 238, 232), 0.3 + 0.7 * mixed) + (255,))
            rnd = random.Random(7)
            for k in range(int(70 * mixed)):
                fx, fy = rnd.uniform(10, rm.get_width() - 10), rnd.uniform(20, rm.get_height() - 10)
                r_ = rnd.uniform(3, 8)
                pygame.draw.circle(liq, (252, 252, 248), (int(fx), int(fy)), int(r_))
                pygame.draw.circle(liq, (214, 216, 212), (int(fx + 1), int(fy + 1)), int(r_), 1)
        if np is not None:
            a = pygame.surfarray.pixels_alpha(rm)
            col = a.sum(axis=0).astype(np.float64)
            cum = np.cumsum(col[::-1])
            idx = int(np.searchsorted(cum, col.sum() * 0.55))
            wl = rm.get_height() - idx
            ww, hh = a.shape
            la = pygame.surfarray.pixels_alpha(liq)
            line = wl + tilt * (np.arange(ww)[:, None] - ww / 2.0)
            la[:] = np.where(np.arange(hh)[None, :] >= line, a, 0).astype(np.uint8)
            del la, a
        liq.blit(ro, (0, 0))
        return liq

    def render(self, s):
        gfx.bench(s, LAV)
        gfx.card(s, (40, TOP + 20, 220, BOTTOM - TOP - 40), CARD)
        draw_text(s, "1  Lysis" if self.phase == "lyse" else "2  Neutralisation", (150, TOP + 32), 17, INK, center=True, bold=True)
        col = (90, 130, 220) if self.phase == "lyse" else (236, 236, 228)
        for k in range(self.N):
            x, y = 76 + (k % 3) * 52, TOP + 60 + (k // 3) * 66
            gfx.tube(s, x, y, 22, 48, col if k < self.count else (236, 236, 240), 0.55, CORAL)
        # lysis clock: 5 minutes, compressed
        clock = pygame.Rect(62, TOP + 196, 176, 30)
        gfx.screen_rect(s, clock, (30, 40, 36))
        mins = self.lysis_minutes() if self.phase == "lyse" else min(5.0, self.lysis_minutes())
        hot = self.lysis_s and mins > 4.0
        draw_text(s, "lysis %d:%02d / 5:00" % (int(mins), int(mins * 60) % 60), clock.center, 14,
                  (255, 120, 110) if hot or self.over else (140, 255, 170), center=True, bold=True, mono=True, vcenter=True)
        draw_text(s, "Chromosomal DNA", (150, TOP + 236), 14, INK, center=True, bold=True)
        breaks = int(self.shear * 9)
        seg = 160.0 / (breaks + 1)
        for k in range(breaks + 1):
            x0 = 70 + k * seg + (3 if k else 0)
            helix(s, x0, TOP + 268 + (k % 2) * 6 * (breaks > 0), max(6, seg - 8), 5, 24)
        draw_text(s, "intact" if breaks == 0 else "sheared into %d pieces" % (breaks + 1), (150, TOP + 290), 13, GREEN if breaks == 0 else RED, center=True, bold=True)
        if self.phase == "lyse" and self.count >= self.N:
            self.add_btn.draw(s, getattr(self, "_inp", None))
            if (self.t // 20) % 2 == 0:
                gfx.rrect(s, self.add_btn.rect.inflate(8, 8), None, CORAL, 3, 12)
        else:
            msg = ("Evenly blue means fully lysed." if self.phase == "lyse" else "White flocs form as you invert.")
            draw_wrapped(s, msg, (60, TOP + 318), 14, 180, INK_SOFT)
        # the tube, with the liquid kept level by gravity
        dx = int(math.sin(self.shake * 1.7) * 6) if self.shake else 0
        cx, cy = 520 + dx, (TOP + BOTTOM) // 2
        tilt = clamp(getattr(self, "spin", 0.0) * 0.06, -0.35, 0.35)
        key = (round(self.angle, 1), round(tilt, 2), self.count, self.phase)
        if getattr(self, "_tube_key", None) != key:
            self._tube_key = key
            self._tube_img = self.compose_tube(tilt)
        img = self._tube_img
        s.blit(img, img.get_rect(center=(cx, cy)))
        # speed gauge
        gfx.card(s, (780, TOP + 20, 140, BOTTOM - TOP - 40), CARD)
        draw_text(s, "Speed", (850, TOP + 34), 18, INK, center=True, bold=True)
        g = pygame.Rect(814, TOP + 70, 72, 340)     # wide enough for its "too rough" label
        gfx.rrect(s, g, (250, 214, 204), INK, 2, 10, 0.0, False)
        ra = self.rough_at
        green = pygame.Rect(g.x + 2, g.bottom - int(g.h * ra / 20.0), g.w - 4, int(g.h * (ra - 2) / 20.0))
        gfx.rrect(s, green, (180, 226, 184), None, 0, 6, 0.1, False)
        draw_text(s, "gentle", (g.centerx, green.centery), 12, (60, 120, 70), center=True, bold=True, vcenter=True)
        y = g.bottom - g.h * clamp(self.speed / 20.0, 0, 1)
        gfx.poly(s, CORAL if self.speed > self.rough_at else INK, [(g.x - 18, y - 9), (g.x - 2, y), (g.x - 18, y + 9)])
        draw_text(s, "too rough", (850, g.y + 8), 13, RED, center=True, bold=True)

# ------------------------------------------------------------------ balance the centrifuge
@register("extract_balance")
class BalanceStage(Stage):
    title = "Balance the centrifuge"
    instr = ("Place all the tubes in the rotor so that it is balanced (the centre of mass must stay in the middle), then press Spin. "
             "Click a slot to add or remove a tube.")
    limit = 90
    WEIGHT = {"full": 1.0, "half": 0.7}     # a 1.5 mL tube with 0.75 mL weighs ~1.75 g against ~2.5 g full
    CAPCOL = {"full": (214, 58, 48), "half": (52, 112, 206)}

    def setup(self):
        rng = self.rng
        if self.level == 0:
            self.rounds = [(12, {"full": 4}), (12, {"full": 6}), (24, {"full": 6})]
            self.instr += " Hover over a slot to see the one opposite it."
        elif self.level == 1:
            self.rounds = [(12, {"full": rng.choice([3, 4])}), (12, {"full": rng.choice([5, 7])}), (24, {"full": rng.choice([5, 7, 9])})]
        else:
            self.rounds = [(12, {"full": 3, "half": 2}), (12, {"full": 2, "half": 3}), (24, {"full": 3, "half": 4})]
            self.instr += " Some tubes hold only half the volume: balance by mass, not by number. Pick a tube type on the right first."
        self.r = 0
        self.scores = []
        self.first_try = 0
        self.spin_btn = gfx.Button((770, BOTTOM - 70, 160, 46), "Spin", SAND)
        self.kind_btns = {"full": pygame.Rect(706, TOP + 132, 104, 92), "half": pygame.Rect(820, TOP + 132, 104, 92)}
        self.mouse = (0, 0)
        self.new_round()

    def new_round(self):
        self.slots, counts = self.rounds[self.r]
        self.avail = dict(counts)
        self.n = sum(counts.values())
        self.sel = "full"
        self.filled = {}
        self.tries = 0
        self.anim = 0
        self.balanced = None
        self.rot = 0.0

    def slot_pos(self, i):
        rad = 150 if self.slots == 12 else 160
        a = i * math.tau / self.slots - math.pi / 2
        return 440 + math.cos(a) * rad, (TOP + BOTTOM) // 2 + math.sin(a) * rad

    def imbalance(self):
        x = sum(self.WEIGHT[k] * math.cos(i * math.tau / self.slots) for i, k in self.filled.items())
        y = sum(self.WEIGHT[k] * math.sin(i * math.tau / self.slots) for i, k in self.filled.items())
        return math.hypot(x, y)

    def slot_at(self, pos):
        r = 18 if self.slots == 12 else 13
        for i in range(self.slots):
            x, y = self.slot_pos(i)
            if math.hypot(pos[0] - x, pos[1] - y) <= r + 3:
                return i
        return None

    def tick(self, inp):
        self.mouse = inp.mouse
        if self.anim:
            self.anim -= 1
            self.rot += 0.05 + (120 - self.anim) * 0.004
            if self.anim == 0:
                if self.balanced:
                    sc = [100, 60, 25][min(self.tries - 1, 2)]
                    if self.tries == 1:
                        self.first_try += 1
                    self.scores.append(sc)
                    self.next_round()
                elif self.tries >= 3:
                    self.scores.append(0)
                    self.floaters.add(440, TOP + 60, "Moving on...", CORAL_D, 20)
                    self.next_round()
            return
        if inp.click:
            for kind, rect in self.kind_btns.items():
                if kind in self.avail and rect.collidepoint(inp.mouse):
                    self.sel = kind
                    audio.sfx("blip")
                    return
            i = self.slot_at(inp.mouse)
            if i is not None:
                if i in self.filled:
                    self.avail[self.filled.pop(i)] += 1
                    audio.sfx("blip")
                else:
                    kind = self.sel if self.avail.get(self.sel, 0) > 0 else next((k for k, v in self.avail.items() if v > 0), None)
                    if kind:
                        self.filled[i] = kind
                        self.avail[kind] -= 1
                        audio.sfx("click")
        self.spin_btn.enabled = len(self.filled) == self.n
        if self.spin_btn.hit(inp):
            self.tries += 1
            self.balanced = self.imbalance() < 0.05
            self.anim = 120
            audio.sfx("whoosh" if self.balanced else "buzz")
            if self.balanced:
                self.floaters.add(440, TOP + 60, "Balanced!", GREEN, 26)
                self.particles.burst(440, (TOP + BOTTOM) // 2, 20)
            else:
                self.shake = 24
                self.floaters.add(440, TOP + 60, "Unbalanced: it shakes!", RED, 24)

    def next_round(self):
        self.r += 1
        if self.r >= len(self.rounds):
            fb = ["Rotor balanced on the first try in %d of 3 runs." % self.first_try]
            if self.level == 2:
                fb.append("Tubes of different mass do not balance each other: put a tube of the same mass opposite each one, or space three equal tubes 120 degrees apart.")
            fb.append("Opposite tubes cancel out; three equal tubes spaced 120 degrees apart also balance.")
            self.finish(sum(self.scores) / 3.0, *fb)
            self.r = len(self.rounds) - 1
        else:
            self.new_round()

    def partial(self):
        return sum(self.scores) / 3.0

    def autoplay(self):
        self.finish(90, "(autoplay)")
    def housing(self, cx, cy):
        """A benchtop microcentrifuge seen from above with the lid open: white moulded housing
        around a dark chamber."""
        def make():
            sf = pygame.Surface((450, 450), pygame.SRCALPHA)
            o = pygame.Rect(10, 6, 430, 430)
            sf.blit(R.soft_shadow(o.w, o.h, 40, (10, 10, 24), 120, 12), (o.x - 24 + 5, o.y - 24 + 10))
            sf.blit(real.plastic(o.w, o.h, (236, 236, 232), 40, 0.35), o.topleft)
            c = (o.centerx, o.centery - 6)
            S = 2
            n = 440 * S
            big = pygame.Surface((n, n), pygame.SRCALPHA)
            if np is not None:
                yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
                d = np.sqrt((xx - n / 2) ** 2 + (yy - n / 2) ** 2) / S
                v = np.where(d < 199, 26 + 40 * (d / 199.0) ** 2, np.where(d < 210, 150 + 60 * (1 - np.abs(d - 204.5) / 5.5), 0))
                a = np.clip((210 - d) * 2, 0, 1) * 255
                rgb = np.clip(np.stack([v, v + 2, v + 8], axis=2), 0, 255).astype(np.uint8)
                pygame.surfarray.pixels3d(big)[:] = rgb.transpose(1, 0, 2)
                pygame.surfarray.pixels_alpha(big)[:] = a.astype(np.uint8).T
            sf.blit(pygame.transform.smoothscale(big, (440, 440)), (c[0] - 220, c[1] - 220))
            return sf
        s_ = cached(("cf_house2",), make)
        return s_, (cx - 225, cy - 215)

    def render(self, s):
        gfx.bench(s, SKY)
        cx, cy = 440, (TOP + BOTTOM) // 2
        shake = 0
        if self.anim and not self.balanced:
            shake = math.sin(self.anim * 1.3) * min(12, 3 + self.imbalance() * 4)
        hs, pos = self.housing(cx, cy)
        s.blit(hs, (pos[0] + shake * 0.3, pos[1]))
        cx += shake
        disc = metal_disc(188)
        s.blit(disc, (int(cx - disc.get_width() / 2), int(cy - disc.get_height() / 2)))
        r = 18 if self.slots == 12 else 13
        spinning = self.anim > 0
        speed = 0.05 + (120 - self.anim) * 0.004 if spinning else 0
        for i in range(self.slots):
            x, y = self.slot_pos(i)
            a = self.rot
            dx, dy = x - 440, y - ((TOP + BOTTOM) // 2)
            x, y = cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)
            gfx.circle(s, (22, 24, 30), (x, y), r + 1, 2, (120, 124, 132), False)
            gfx.alpha_circle(s, (90, 96, 108), (x + r * 0.2, y + r * 0.25), r * 0.7, 60)
            if i in self.filled:
                kind = self.filled[i]
                col = self.CAPCOL[kind]
                if spinning and speed > 0.15:
                    for k in range(1, 4):
                        b = a - speed * k * 0.5
                        tx, ty = cx + dx * math.cos(b) - dy * math.sin(b), cy + dx * math.sin(b) + dy * math.cos(b)
                        gfx.alpha_circle(s, col, (tx, ty), r - 3, 90 - k * 25)
                lab = ("1.5" if kind == "full" else ".75") if self.level == 2 else ""
                sp = cap_sprite(r - 2, col, lab, size=7 if r < 15 else 9)
                s.blit(sp, (int(x - sp.get_width() / 2), int(y - sp.get_height() / 2)))
            elif self.level == 0 and not spinning:
                hov = self.slot_at(self.mouse)
                if hov is not None and (hov + self.slots // 2) % self.slots == i:
                    gfx.circle(s, None, (x, y), r + 4, 3, GREEN, False)
                    if hov in self.filled:
                        gfx.alpha_circle(s, GREEN, (x, y), r - 2, 70)
        hub = metal_disc(30)
        s.blit(hub, (int(cx - 30), int(cy - 30)))
        gfx.circle(s, (70, 74, 88), (cx, cy), 10, 2, (40, 42, 50))
        gfx.card(s, (690, TOP + 20, 250, 300), CARD)
        draw_text(s, "Run %d of 3" % (self.r + 1), (815, TOP + 32), 16, MUTED, center=True, bold=True)
        draw_text(s, "%d tubes" % self.n, (815, TOP + 60), 30, INK, center=True, bold=True)
        draw_text(s, "%d-slot rotor" % self.slots, (815, TOP + 102), 16, INK_SOFT, center=True)
        if self.level == 2:
            for kind, rect in self.kind_btns.items():
                sel = kind == self.sel
                gfx.rrect(s, rect, (255, 246, 214) if sel else (246, 246, 242), CORAL if sel else (170, 170, 166), 3 if sel else 1, 10, 0.05)
                n = self.avail.get(kind, 0)
                for k in range(n):
                    gfx.tube(s, rect.x + 10 + k * 22, rect.y + 10, 15, 40, (240, 200, 160), 0.8 if kind == "full" else 0.4, self.CAPCOL[kind])
                draw_text(s, "1.5 mL x%d" % n if kind == "full" else "0.75 mL x%d" % n, (rect.centerx, rect.bottom - 22), 13, INK, center=True, bold=True)
            draw_wrapped(s, "Pick a type, then click slots.", (712, TOP + 274), 14, 220, INK_SOFT)
        else:
            left = self.n - len(self.filled)
            for k in range(left):
                gfx.tube(s, 712 + (k % 9) * 24, TOP + 140 + (k // 9) * 60, 16, 44, (240, 200, 160), 0.6, CORAL)
            draw_wrapped(s, "All tubes hold the same volume.", (712, TOP + 274), 14, 220, INK_SOFT)
        scr = pygame.Rect(712, TOP + 236, 116, 26)
        gfx.screen_rect(s, scr, (30, 40, 36))
        rpm = int(min(1.0, (120 - self.anim) / 80.0) * 13000) if spinning else 0
        draw_text(s, "%s rpm" % "{:,}".format(rpm), scr.center, 14, (140, 255, 170), center=True, bold=True, mono=True, vcenter=True)
        if self.anim and not self.balanced:
            gfx.led(s, (842, TOP + 249), RED, (self.anim // 6) % 2 == 0, 6)
            draw_text(s, "IMBALANCE", (854, TOP + 242), 12, RED, bold=True)
        self.spin_btn.draw(s)

# ------------------------------------------------------------------ NanoDrop
def spline(points, steps=12):
    out = []
    pts = [points[0]] + points + [points[-1]]
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for k in range(steps):
            t = k / float(steps)
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t +
                                    (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in range(2)))
    out.append(points[-1])
    return out


def spectrum_pic(a260, r280, r230):
    def pic(s, r):
        body = pygame.Rect(r.x, r.y, r.w, r.h)
        gfx.metal_rect(s, body, (226, 228, 234), 10)
        draw_text(s, "Spectrophotometer  ·  nucleic acid", (body.x + 16, body.y + 10), 12, INK_SOFT, bold=True)
        scr = pygame.Rect(body.x + 14, body.y + 30, body.w - 28, body.h - 116)
        gfx.screen_rect(s, scr, (24, 30, 42))
        g = pygame.Rect(scr.x + 40, scr.y + 16, scr.w - 56, scr.h - 50)
        for k in range(1, 4):
            y = g.y + g.h * k / 4.0
            pygame.draw.line(s, (44, 54, 72), (g.x, y), (g.right, y), 1)
        top = max(1.4, a260 / r230 * 1.5, a260 * 1.15)
        pts_nm = [(220, a260 / r230 * 1.45), (230, a260 / r230), (240, a260 * 0.6), (260, a260), (280, a260 / r280), (300, a260 * 0.06), (340, 0.0)]

        def xy(nm, a):
            return g.x + (nm - 220) / 120.0 * g.w, g.bottom - a / top * g.h
        for nm in (230, 260, 280):
            x = xy(nm, 0)[0]
            pygame.draw.line(s, (70, 84, 110), (x, g.y), (x, g.bottom), 1)
            draw_text(s, "%d" % nm, (x, g.bottom + 4), 12, (180, 196, 220), center=True, bold=True)
        pts = spline([xy(nm, a) for nm, a in pts_nm])
        pygame.draw.lines(s, (40, 120, 150), False, pts, 5)
        pygame.draw.lines(s, (110, 230, 250), False, pts, 2)
        pygame.draw.aalines(s, (190, 250, 255), False, pts)
        pygame.draw.line(s, (150, 170, 200), g.bottomleft, g.bottomright, 1)
        pygame.draw.line(s, (150, 170, 200), g.bottomleft, g.topleft, 1)
        draw_text(s, "nm", (g.right - 4, g.bottom + 4), 12, (150, 170, 200), right=True)
        draw_text(s, "A", (g.x - 22, g.y - 4), 13, (150, 170, 200), bold=True)
        y = body.bottom - 74
        for k, (lab, val) in enumerate((("A260/A280", "%.2f" % r280), ("A260/A230", "%.2f" % r230))):
            box = pygame.Rect(body.x + 16 + k * (body.w // 2 - 8), y, body.w // 2 - 32, 56)
            gfx.screen_rect(s, box, (30, 40, 36))
            draw_text(s, lab, (box.centerx, box.y + 6), 12, (170, 200, 180), center=True, bold=True)
            draw_text(s, val, (box.centerx, box.y + 24), 22, (140, 255, 170), center=True, bold=True, mono=True)
    return pic


DIAG = [
    ("clean", 1.86, 2.15, "Clean DNA, ready to use", "Both ratios are in range: about 1.8 for 260/280 and 2.0-2.2 for 260/230."),
    ("protein", 1.48, 1.9, "Protein contamination", "A low 260/280 ratio means something absorbs at 280 nm: protein or phenol. The ratio is relatively insensitive to protein, so a value this low means a lot of contamination."),
    ("salt", 1.82, 0.95, "Guanidine salt or phenol carried over", "A low 260/230 ratio and a strong 230 nm peak point to guanidine salts or phenol from the extraction."),
]


def diag_question(rng):
    key, r280, r230, ans, why = rng.choice(DIAG)
    opts = ["Clean DNA, ready to use", "Protein contamination", "Guanidine salt or phenol carried over", "No nucleic acid in the sample"]
    return dict(q="Your NanoDrop reading for a plasmid prep. What does it tell you?", options=opts, answer=opts.index(ans), why=why,
                pic=spectrum_pic(1.0, r280, r230))


def conc_question(rng):
    a = rng.choice([0.4, 0.6, 0.8, 1.2, 1.5, 2.0])
    rna = rng.random() < 0.4
    f = 40 if rna else 50
    kind = "An RNA" if rna else "A double-stranded DNA"
    vals = [a * f, a * (90 - f), a * 33, a * f * 10]
    opts = ["%g ng/µL" % v for v in vals]
    return dict(q="%s sample reads A260 = %.1f (10 mm path). What is its concentration?" % (kind, a), options=opts, answer=0,
                why="An A260 of 1.0 equals about 50 ng/µL of dsDNA and 40 ng/µL of RNA (33 for single-stranded DNA).",
                pic=spectrum_pic(a, 2.0 if rna else 1.85, 2.1))


ABS_Q = dict(q="Why does DNA absorb light at 260 nm?", options=["Its bases have aromatic rings that absorb UV", "Its sugars are coloured", "The phosphates glow", "It does not; the buffer does"],
             answer=0, why="The ring structures of the four bases absorb ultraviolet light most strongly around 260 nm.")


TECH = dict(
    key="extract", name="DNA & RNA extraction", full="Nucleic acid extraction (plasmid miniprep)", wing="DNA", icon="extract",
    blurb="Breaks open cells and purifies their DNA or RNA away from proteins, lipids and salts, ready for enzymes and sequencing.",
    facts=[
        "Friedrich Miescher first isolated DNA in 1869, from white blood cells in pus on surgical bandages. He called it 'nuclein'.",
        "The alkaline lysis miniprep was published by Birnboim and Doly in 1979, and most plasmid kits still follow it.",
        "Silica binds DNA in the presence of chaotropic salts such as guanidine, and lets it go again in water.",
        "RNase A is so stable that it can refold and work again after boiling, which is why RNA labs are strict about keeping it away.",
        "Pure DNA gives an A260/A280 ratio of about 1.8 and pure RNA about 2.0.",
        "An absorbance of 1 at 260 nm corresponds to about 50 µg/mL of double-stranded DNA and 40 µg/mL of RNA.",
        "TRIzol, a mix of phenol and guanidinium thiocyanate, is based on the single-step RNA method of Chomczynski and Sacchi from 1987.",
    ],
    quiz=[
        dict(q="Why must you not vortex after adding the lysis buffer?", options=["It shears chromosomal DNA, which then contaminates the plasmid", "It heats the sample", "It destroys the RNase", "It makes the column clog with ethanol"],
             answer=0, why="Long chromosomal DNA breaks into fragments that no longer precipitate with the debris and end up in your prep."),
        dict(q="What does a low A260/A230 ratio usually mean?", options=["Salt (guanidine) or phenol carry-over", "Too much DNA", "RNA contamination", "The DNA is supercoiled"],
             answer=0, why="Guanidine and phenol absorb strongly near 230 nm."),
        dict(q="Why do you balance a centrifuge?", options=["An unbalanced rotor vibrates and can damage the machine", "To make the spin faster", "To keep the tubes cold", "To separate DNA from RNA"],
             answer=0, why="At thousands of g, a small imbalance becomes a large force on the drive shaft."),
    ],
    music=dict(name="Spin Column Shuffle", bpm=116, beats=4, root=52, mode="blues", prog=[0, 0, 2, 0, 3, 2, 0, 3], lead="organ", comp="walk",
               drums="shuffle", swing=0.3, motif=[(0, 2), (1, 1), (2, 1), (3, 2), (4, 2), (3, 1), (2, 1), (0, 6)]),
    stages=[
        ("order", dict(title="Miniprep protocol", steps=STEPS, heading="Plasmid miniprep", limit=75,
                       instr="Put the miniprep steps in order. Each step explains what it does once placed.")),
        ("extract_invert", {}),
        ("extract_balance", {}),
        ("quiz", dict(title="Read the NanoDrop", questions=[diag_question, conc_question, ABS_Q], n=3,
                      instr="Judge the purity and concentration of your prep from the spectrophotometer readings.")),
    ],
)
TECHS = [TECH]
