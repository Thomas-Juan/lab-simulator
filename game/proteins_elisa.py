# -*- coding: utf-8 -*-
"""Sandwich ELISA: build the layers, make a serial dilution, read the standard curve, stop the colour."""
import math
import pygame
import audio
import gfx
import render as R
import real
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, TEAL, LAV, VIOLET, WHITE,
                  GREEN, RED, YELLOW, clamp, mix, lerp, draw_text, draw_wrapped)
from stage import Stage, OrderStage, register, TOP, BOTTOM
from proteins_common import cached, mmss, note_card, antibody, ring_ellipse

TMB_BLUE = (30, 70, 200)
TMB_YELLOW = (236, 186, 20)
PLASTIC = (238, 242, 246)
SAMPLE = (200, 60, 120)


# ----------------------------------------------------------------- the molecular sandwich
def draw_sandwich(s, rect, n, t=0):
    """Cross-section of one well with the first n ELISA steps done."""
    r = pygame.Rect(rect)
    liquid = None
    if n >= 6:
        liquid = (110, 140, 230) if n == 6 else (246, 210, 70)
    wall = 14
    outer = [(r.x, r.y), (r.x, r.bottom - 28), (r.x + 28, r.bottom), (r.right - 28, r.bottom), (r.right, r.bottom - 28), (r.right, r.y)]
    inner = [(r.x + wall, r.y), (r.x + wall, r.bottom - 34), (r.x + 34, r.bottom - wall), (r.right - 34, r.bottom - wall),
             (r.right - wall, r.bottom - 34), (r.right - wall, r.y)]
    gfx.poly(s, (226, 232, 238), outer, 2)
    gfx.poly(s, (250, 252, 253), inner, 0, None)
    if liquid:
        lq = [(x, max(y, r.y + 36)) for x, y in inner]
        gfx.poly(s, mix(liquid, WHITE, 0.4), lq, 0, None)
        gfx.line(s, R.lighten(liquid, 0.3), (r.x + wall + 2, r.y + 37), (r.right - wall - 2, r.y + 37), 2)
    gfx.alpha_rect(s, (r.x + 4, r.y + 6, 4, r.h - 44), WHITE, 170, 2)
    draw_text(s, "polystyrene well (side view)", (r.centerx, r.y - 18), 12, INK_SOFT, center=True, bold=True)
    floor = r.bottom - wall - 2
    xs = [r.x + 40 + i * (r.w - 80) / 4 for i in range(5)]
    if n >= 2:      # blocking protein on bare plastic
        for i in range(4):
            gfx.circle(s, (206, 206, 214), ((xs[i] + xs[i + 1]) / 2, floor - 7), 7, 1)
    for x in xs:
        if n >= 1:
            antibody(s, (x, floor), True, TURQ)
        if n >= 3:
            gfx.circle(s, CORAL, (x, floor - 42), 9)                      # antigen
        if n >= 4:
            antibody(s, (x, floor - 86), False, VIOLET)                   # detection antibody, arms down
            gfx.circle(s, (120, 200, 90), (x, floor - 92), 4, 1)           # biotin
        if n >= 5:
            star = [(x + 9 * math.cos(a * math.pi / 3), floor - 104 + 9 * math.sin(a * math.pi / 3)) for a in range(6)]
            gfx.poly(s, YELLOW, star)                                       # streptavidin-HRP
        if n >= 6:
            for k in range(3):
                ang = t * 0.05 + k * 2.1 + x
                c = (x + 18 * math.cos(ang), floor - 118 + 8 * math.sin(ang))
                gfx.circle(s, (60, 90, 220) if n == 6 else (220, 170, 20), c, 4, 1)
    labels = [(1, "capture Ab", TURQ), (2, "blocker", MUTED), (3, "antigen", CORAL_D), (4, "detection Ab", VIOLET),
              (4, "biotin", (80, 150, 60)), (5, "strep-HRP", (170, 130, 0)), (6, "TMB", (60, 90, 220))]
    y = r.y + 4
    for k, txt, col in labels:
        if n >= k:
            draw_text(s, txt, (r.right + 10, y), 12, col, bold=True)
            y += 16


@register("elisa_layers")
class ElisaLayers(OrderStage):
    title = "Build the sandwich"
    instr = ("Click the steps in the order you add them to the well (the washes between steps are left out). "
             "The well on the right shows what you have built.")

    def slot_rect(self, k):
        return pygame.Rect(600, TOP + 44 + k * 27, 320, 24)

    def render(self, s):
        super().render(s)
        draw_sandwich(s, (610, 306, 190, 184), self.next, self.t)


# ----------------------------------------------------------------- a 96-well plate in perspective
PLATE_TL, PLATE_TR, PLATE_BR, PLATE_BL = (92, 116), (612, 116), (640, 470), (60, 470)


def plate_point(u, v):
    """Bilinear position on the plate top: u across (0..1), v down (0..1)."""
    tx = lerp(PLATE_TL[0], PLATE_TR[0], u)
    bx = lerp(PLATE_BL[0], PLATE_BR[0], u)
    y = lerp(PLATE_TL[1], PLATE_BL[1], v)
    return lerp(tx, bx, v), y


def well_uv(row, col):
    return (0.075 + col * 0.0773, 0.085 + row * 0.119)


def _well_sprite(rx, ry):
    """An empty well seen from above at an angle: clear rim, darker inner wall, bright floor."""
    def make():
        S = 3
        w, h = (2 * rx + 4) * S, (2 * ry + 10) * S
        big = pygame.Surface((w, h), pygame.SRCALPHA)
        cx = w // 2
        top = pygame.Rect(2 * S, 2 * S, 2 * rx * S, 2 * ry * S)
        pygame.draw.ellipse(big, (150, 162, 176, 200), top.inflate(2 * S, 2 * S))          # moulded rim edge
        pygame.draw.ellipse(big, (214, 222, 230, 255), top)                                  # inner wall
        floor = top.move(0, int(ry * 0.55 * S)).inflate(-int(rx * 0.28 * S), -int(ry * 0.5 * S))
        pygame.draw.ellipse(big, (238, 242, 246, 255), floor)                                # flat bottom
        pygame.draw.arc(big, (255, 255, 255, 230), top.inflate(-2 * S, -2 * S), 3.4, 5.6, S)    # light on the far wall
        pygame.draw.arc(big, (120, 132, 146, 180), top, 0.2, 2.9, S)                         # shade on the near lip
        return pygame.transform.smoothscale(big, (w // S, h // S))
    return cached(("well96", rx, ry), make)


def _plate_body():
    sf = pygame.Surface((W, H), pygame.SRCALPHA)
    side = [PLATE_BL, PLATE_BR, (PLATE_BR[0], PLATE_BR[1] + 20), (PLATE_BL[0], PLATE_BL[1] + 20)]
    sh = real.contact_shadow(PLATE_BR[0] - PLATE_BL[0] + 30, 26, 120)
    sf.blit(sh, (PLATE_BL[0] - 14, PLATE_BL[1] + 2))
    R.aa_poly(sf, (196, 206, 216, 235), side, 0, None)
    top = [PLATE_TL, PLATE_TR, PLATE_BR, PLATE_BL]
    R.aa_poly(sf, (234, 239, 244, 252), top, 0, None)
    # skirt highlight and darker edges: clear polystyrene catches light on its edges
    pygame.draw.line(sf, (255, 255, 255), PLATE_TL, PLATE_TR, 2)
    pygame.draw.line(sf, (255, 255, 255), PLATE_TL, PLATE_BL, 2)
    pygame.draw.line(sf, (150, 160, 172), PLATE_TR, PLATE_BR, 2)
    pygame.draw.line(sf, (160, 170, 182), PLATE_BL, PLATE_BR, 1)
    pygame.draw.line(sf, (120, 130, 144), side[3], side[2], 2)
    # chamfered corner (A1) and moulded row/column characters
    R.aa_poly(sf, (210, 218, 226), [PLATE_TL, (PLATE_TL[0] + 18, PLATE_TL[1]), (PLATE_TL[0] - 2, PLATE_TL[1] + 18)], 0, None)
    for c in range(12):
        x, y = plate_point(well_uv(0, c)[0], 0.035)
        draw_text(sf, str(c + 1), (x + 1, y - 6), 11, (255, 255, 255), center=True, bold=True)
        draw_text(sf, str(c + 1), (x, y - 7), 11, (140, 150, 164), center=True, bold=True)
    for rr in range(8):
        x, y = plate_point(0.028, well_uv(rr, 0)[1])
        draw_text(sf, "ABCDEFGH"[rr], (x + 1, y - 6), 11, (255, 255, 255), center=True, bold=True)
        draw_text(sf, "ABCDEFGH"[rr], (x, y - 7), 11, (140, 150, 164), center=True, bold=True)
    for rr in range(8):
        for c in range(12):
            x, y = plate_point(*well_uv(rr, c))
            k = 0.86 + 0.14 * well_uv(rr, c)[1]
            sp = _well_sprite(int(16 * k), int(12 * k))
            sf.blit(sp, (int(x - sp.get_width() / 2), int(y - 12 * k - 2)))
    return sf


def draw_well_liquid(s, row, col, colour):
    """Coloured liquid in a well: deeper colour in the middle (longer light path), a bright meniscus rim."""
    x, y = plate_point(*well_uv(row, col))
    k = 0.86 + 0.14 * well_uv(row, col)[1]
    rx, ry = int(14 * k), int(10 * k)
    key = ("liq", rx, ry, tuple(colour))

    def make():
        S = 3
        big = pygame.Surface(((2 * rx + 2) * S, (2 * ry + 2) * S), pygame.SRCALPHA)
        r_ = pygame.Rect(S, S, 2 * rx * S, 2 * ry * S)
        pygame.draw.ellipse(big, tuple(R.lighten(colour, 0.25)) + (235,), r_)
        pygame.draw.ellipse(big, tuple(colour) + (245,), r_.inflate(-int(rx * 0.5 * S), -int(ry * 0.5 * S)).move(0, S))
        pygame.draw.ellipse(big, tuple(R.lighten(colour, -0.12)) + (230,), r_.inflate(-int(rx * 1.0 * S), -int(ry * 1.0 * S)).move(0, 2 * S))
        pygame.draw.arc(big, (255, 255, 255, 170), r_.inflate(-2 * S, -2 * S), 3.5, 5.4, S)
        return pygame.transform.smoothscale(big, (2 * rx + 2, 2 * ry + 2))
    sp = cached(key, make)
    s.blit(sp, (int(x - rx - 1), int(y - ry)))


def stop_bottle(s, bx, by):
    """A clear glass reagent bottle with a blue screw cap and a printed label."""
    w, h = 70, 104
    sh = real.contact_shadow(w + 10, 12, 100)
    s.blit(sh, (bx - 8, by + h - 8))
    m = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(m, (255, 255, 255, 255), (0, 18, w, h - 18), border_radius=14)
    pygame.draw.rect(m, (255, 255, 255, 255), (w // 2 - 15, 4, 30, 20))
    body = real.shaded_mask(m, (212, 226, 230), real.cyl_profile(w, 0.27, 0.07, 0.6, 0.6), 150)
    s.blit(body, (bx, by))
    gfx.alpha_rect(s, (bx + 4, by + 46, w - 8, h - 50), (250, 250, 246), 120, 10)      # liquid inside
    cap = pygame.Surface((36, 18), pygame.SRCALPHA)
    pygame.draw.rect(cap, (255, 255, 255, 255), cap.get_rect(), border_radius=3)
    s.blit(real.shaded_mask(cap, (40, 90, 176), real.cyl_profile(36, 0.3, 0.1, 0.4, 0.6), 255), (bx + w // 2 - 18, by - 10))
    for i in range(5):
        pygame.draw.line(s, (26, 60, 130), (bx + w // 2 - 14 + i * 7, by - 8), (bx + w // 2 - 14 + i * 7, by + 6), 1)
    lab = pygame.Rect(bx + 8, by + 34, w - 16, 50)
    pygame.draw.rect(s, (252, 252, 248), lab)
    pygame.draw.rect(s, (224, 60, 50), (lab.x, lab.y, lab.w, 10))
    draw_text(s, "STOP", (lab.centerx, lab.y), 9, WHITE, center=True, bold=True)
    draw_text(s, "1 M H2SO4", (lab.centerx, lab.y + 14), 10, INK, center=True, bold=True)
    draw_text(s, "corrosive", (lab.centerx, lab.y + 30), 9, (190, 60, 50), center=True)


def scene_tmb(st, s, v):
    gfx.bench(s, (236, 236, 222))
    if not hasattr(st, "_samples"):
        r = st.rng
        st._samples = [[r.choice([0.0, 0.03, 0.08, 0.15, 0.3, 0.5]) for _ in range(8)] for _ in range(8)]
    s.blit(cached(("plate96b",), _plate_body), (0, 0))
    stopped = st.state == "stopped"
    for rr in range(8):
        for c in range(12):
            if c < 2:
                std = getattr(st.ctx, "elisa_std", None)
                if std:
                    conc = std[rr] if rr < 7 else 0.0
                else:
                    conc = 1.0 / (2 ** rr) if rr < 7 else 0.0
            elif c < 10:
                conc = st._samples[rr][c - 2]
            else:
                continue
            inten = clamp(1 - math.exp(-3.4 * conc * v) + 0.3 * v ** 3, 0, 1)
            inten = round(inten * 24) / 24.0           # quantised so the liquid sprites can be cached
            col = mix((246, 244, 228), TMB_YELLOW, inten) if stopped else mix((236, 240, 244), TMB_BLUE, inten)
            draw_well_liquid(s, rr, c, col)
    # the standards are marked with a lab marker on the plate edge, as people do
    a, b = plate_point(0.046, 0.03), plate_point(0.19, 0.97)
    pygame.draw.line(s, (30, 40, 120), (a[0] + 4, PLATE_TL[1] - 6), (b[0] + 4, PLATE_TL[1] - 6), 3)
    draw_text(s, "std", ((a[0] + b[0]) / 2 + 6, PLATE_TL[1] - 24), 13, (30, 40, 120), center=True, bold=True)
    draw_text(s, "samples", (plate_point(0.5, 0)[0], PLATE_TL[1] - 24), 13, (30, 40, 120), center=True, bold=True)
    pygame.draw.line(s, (30, 40, 120), (plate_point(0.24, 0)[0], PLATE_TL[1] - 6), (plate_point(0.83, 0)[0], PLATE_TL[1] - 6), 3)
    if stopped:
        txt = "Acid stops the enzyme and turns oxidised TMB from blue to yellow. The plate is read at 450 nm."
    elif st.state == "over":
        txt = "Too late: the top standards saturated and the blank turned blue, so the curve is flat at the top."
    else:
        txt = "HRP turns TMB blue. Stop when the standards form a clear gradient, before the top ones max out and the blank colours."
    std = getattr(st.ctx, "elisa_std", None)
    if std:
        r = getattr(st.ctx, "elisa_r", 2)
        off = [abs(math.log(max(1e-6, std[k]) * r ** k)) / math.log(r) for k in range(1, 7)]
        txt += (" Columns 1-2 are your 1:%d series: the steps are even." % r if max(off) < 0.25 else
                " Columns 1-2 are your 1:%d series: the uneven steps will bend the standard curve." % r)
    note_card(s, (676, 270, 258, 196), "Stopped" if stopped else "TMB developing", txt, TMB_YELLOW if stopped else SKY)
    stop_bottle(s, 724, 138)


# ----------------------------------------------------------------- serial dilution
@register("elisa_dilute")
class ElisaDilute(Stage):
    title = "Serial dilution"
    instr = ("Make the dilution series asked for, from well 1 to well 8. Click a well to draw up liquid, click another to "
             "dispense, and press Mix after every transfer. Set the pipette volume with + / - or the mouse wheel.")
    limit = 120

    def setup(self):
        # ELISA standards are 1:2 or 1:3 series (steeper steps fall below the assay range); difficulty comes from
        # the factor and the final volume (transfer volumes stay multiples of 5 uL)
        self.r, self.D = self.rng.choice(self.lv([(2, 100.0)], [(2, 100.0), (3, 100.0), (2, 150.0)],
                                                 [(3, 150.0), (2, 150.0), (3, 100.0), (3, 200.0)]))
        self.T = self.D / (self.r - 1)
        self.vol = [self.D + self.T] + [self.D] * 7
        self.mass = [self.D + self.T] + [0.0] * 7     # concentration x volume, stock = 1.0
        self.mixed = [True] * 8
        self.setv = 20
        self.tip = None                   # (volume, mass) in the pipette
        self.last = None
        self.mixing = 0
        self.bad_asp = 0
        self.wx = [110 + i * 106 for i in range(8)]
        self.wy = 262
        self.minus = gfx.Button((640, 430, 46, 40), "-", CARD, size=24)
        self.plus = gfx.Button((790, 430, 46, 40), "+", CARD, size=24)
        self.mixb = gfx.Button((470, 430, 130, 40), "Mix", SKY)
        self.doneb = gfx.Button((852, 430, 90, 40), "Done", SAND)
        self.waste = pygame.Rect(40, 410, 150, 66)
        self.hint = "1:%d means 1 part in %d parts total. Wells 2-8 already hold %g uL buffer." % (self.r, self.r, self.D)

    def conc(self, i):
        return self.mass[i] / self.vol[i] if self.vol[i] > 0 else 0.0

    def well_at(self, pos):
        for i, x in enumerate(self.wx):
            if abs(pos[0] - x) < 44 and self.wy - 60 < pos[1] < self.wy + 76:
                return i
        return None

    def tick(self, inp):
        if self.mixing:
            self.mixing -= 1
        self.mouse = inp.mouse
        self.inp = inp
        if self.minus.hit(inp) or inp.wheel < 0 or pygame.K_MINUS in inp.keys or pygame.K_DOWN in inp.keys:
            self.setv = max(5, self.setv - 5)
            audio.sfx("blip")
        if self.plus.hit(inp) or inp.wheel > 0 or pygame.K_PLUS in inp.keys or pygame.K_EQUALS in inp.keys or pygame.K_UP in inp.keys:
            self.setv = min(200, self.setv + 5)
            audio.sfx("blip")
        if (self.mixb.hit(inp) or pygame.K_m in inp.keys) and self.last is not None:
            self.mixed[self.last] = True
            self.mixing = 40
            audio.sfx("pour")
        if self.doneb.hit(inp):
            self.finish(self.result(), *self.notes())
            return
        if not inp.click:
            return
        if self.waste.collidepoint(inp.mouse) and self.tip:
            self.tip = None
            audio.sfx("splash")
            return
        i = self.well_at(inp.mouse)
        if i is None:
            return
        if self.tip is None:
            v = min(self.setv, self.vol[i])
            if v <= 0:
                return
            c = self.conc(i)
            if not self.mixed[i]:
                self.bad_asp += 1
                c_take = c * 0.45
                self.floaters.add(self.wx[i], self.wy - 80, "Not mixed!", RED, 18)
                audio.sfx("bad")
            else:
                c_take = c
                audio.sfx("click")
            m = min(self.mass[i], c_take * v)
            self.vol[i] -= v
            self.mass[i] -= m
            self.tip = (v, m)
            if v < self.setv:
                self.floaters.add(self.wx[i], self.wy - 100, "Air in the tip!", CORAL_D, 16)
        else:
            v, m = self.tip
            self.vol[i] += v
            self.mass[i] += m
            self.mixed[i] = False
            self.last = i
            self.tip = None
            audio.sfx("pour")
            self.floaters.add(self.wx[i], self.wy - 80, "+%g uL" % v, TEAL, 16)

    def share(self):
        """Your dilution series becomes the standard curve on the plate later."""
        self.ctx.elisa_std = [self.conc(k) for k in range(8)]
        self.ctx.elisa_r = self.r

    def result(self):
        self.share()
        tot = 0.0
        for k in range(1, 8):
            ideal = 1.0 / self.r ** k
            c = self.conc(k)
            if c <= 0:
                sc_c = 0
            else:
                err = abs(math.log(c / ideal)) / math.log(self.r)
                sc_c = clamp(1 - err * 1.6, 0, 1)
            sc_v = clamp(1 - abs(self.vol[k] - self.D) / self.D * 2, 0, 1)
            tot += 0.75 * sc_c + 0.25 * sc_v
        sc_v0 = clamp(1 - abs(self.vol[0] - self.D) / self.D * 2, 0, 1)
        return 100 * (tot + sc_v0) / 8

    def notes(self):
        good = 0
        for k in range(1, 8):
            c = self.conc(k)
            if c > 0 and abs(math.log(c * self.r ** k)) < 0.15:
                good += 1
        out = ["%d of 7 dilutions on target. A 1:%d series moves %g uL into %g uL each time." % (good, self.r, round(self.T, 1), self.D)]
        if self.bad_asp:
            out.append("Liquid drawn from an unmixed well does not have the concentration you think.")
        if any(abs(v - self.D) > 5 for v in self.vol):
            out.append("Remove %g uL from the last well so every well holds the same volume." % round(self.T, 1))
        return out

    def partial(self):
        return self.result() * 0.8

    def autoplay(self):
        self.setv = self.T
        for k in range(7):
            self.mixed[k] = True
            c = self.conc(k)
            self.vol[k] -= self.T
            self.mass[k] -= c * self.T
            self.vol[k + 1] += self.T
            self.mass[k + 1] += c * self.T
        c = self.conc(7)
        self.vol[7] -= self.T
        self.mass[7] -= c * self.T
        self.finish(self.result(), *self.notes())

    def draw_well(self, s, i, x):
        y = self.wy
        body = pygame.Rect(x - 36, y - 40, 72, 112)
        # clear polystyrene well (a magnified view of one well of the row): shaded cylinder
        m = cached(("dmask", body.w, body.h), lambda: _well_mask(body.w, body.h))
        s.blit(cached(("dwell", body.w, body.h), lambda: real.shaded_mask(m, (222, 230, 238), real.cyl_profile(body.w, 0.25, 0.06, 0.5, 0.62), 120)), body.topleft)
        c = self.conc(i)
        inten = clamp(math.log10(1 + 99 * c) / 2, 0, 1)
        col = mix((248, 246, 244), SAMPLE, inten)
        lvl = clamp(self.vol[i] / (2.2 * self.D), 0, 1)
        h = int((body.h - 14) * lvl)
        if h > 2:
            liq = pygame.Rect(body.x + 4, body.bottom - 4 - h, body.w - 8, h)
            qcol = tuple(int(round(v_ / 6.0) * 6) for v_ in col)
            lm = cached(("lmask", liq.w, liq.h), lambda: _well_mask(liq.w, liq.h, 10))
            s.blit(cached(("dliq", liq.w, liq.h, qcol), lambda: real.shaded_mask(lm, qcol, real.cyl_profile(liq.w, 0.25, 0.06, 0.3, 0.75), 225)), liq.topleft)
            ring_ellipse(s, R.lighten(qcol, 0.25), (liq.x, liq.y - 5, liq.w, 10), R.lighten(qcol, -0.2), 1)
            if not self.mixed[i]:          # a dense plume that has not mixed in yet
                for k in range(3):
                    gfx.alpha_circle(s, SAMPLE, (liq.centerx + (k - 1) * 9, liq.y + 10 + k * 6), 7 - k, 120)
                gfx.alpha_rect(s, (liq.x + 8, liq.y + 4, liq.w - 16, max(2, h // 3)), SAMPLE, 80, 6)
        ring_ellipse(s, (232, 238, 244), (body.x - 2, body.y - 8, body.w + 4, 16), (150, 160, 172), 2)
        if self.mixing and self.last == i:
            for k in range(5):
                a = self.t * 0.3 + k * 1.26
                gfx.alpha_circle(s, WHITE, (x + 22 * math.cos(a), body.bottom - 30 + 8 * math.sin(a)), 3, 220)
        draw_text(s, str(i + 1), (x, body.y - 30), 15, INK, center=True, bold=True)
        draw_text(s, "%g uL" % round(self.vol[i], 1), (x, body.bottom + 8), 14, INK_SOFT, center=True, bold=True)
        if not self.mixed[i]:
            draw_text(s, "mix me", (x, body.bottom + 26), 13, CORAL_D, center=True, bold=True)

    def render(self, s):
        gfx.bench(s, (232, 236, 220))
        gfx.card(s, (40, TOP + 8, W - 80, 66), CARD)
        draw_text(s, "Make a 1:%d serial dilution of the standard, wells 1 to 8. Every well must end with %g uL." % (self.r, self.D),
                  (W // 2, TOP + 18), 17, INK, center=True, bold=True)
        draw_text(s, "Well 1 holds %g uL of standard. Wells 2-8 hold %g uL of buffer." % (round(self.D + self.T, 1), self.D),
                  (W // 2, TOP + 44), 15, INK_SOFT, center=True)
        # the row of wells sits in its plate frame (shown magnified)
        fr = pygame.Rect(self.wx[0] - 54, self.wy + 22, self.wx[-1] - self.wx[0] + 108, 58)
        gfx.shadow(s, fr, 6, (3, 5), 50, 6)
        gfx.plastic_rect(s, fr, (226, 232, 238), 6, 0.3)
        for i, x in enumerate(self.wx):
            self.draw_well(s, i, x)
        # waste: a plastic beaker
        wr = self.waste
        sh = real.contact_shadow(wr.w + 8, 12, 90)
        s.blit(sh, (wr.x - 6, wr.bottom - 8))
        m = cached(("wmask", wr.w, wr.h), lambda: _well_mask(wr.w, wr.h, 8))
        s.blit(cached(("waste", wr.w, wr.h), lambda: real.shaded_mask(m, (226, 232, 236), real.cyl_profile(wr.w, 0.25, 0.06, 0.5, 0.62), 170)), wr.topleft)
        gfx.alpha_rect(s, (wr.x + 6, wr.y + 30, wr.w - 12, wr.h - 36), (232, 210, 220), 170, 6)
        draw_text(s, "waste", (wr.centerx, wr.y + 14), 14, (40, 40, 120), center=True, bold=True, vcenter=True)
        gfx.screen_rect(s, (694, 430, 90, 40))
        draw_text(s, "%d uL" % self.setv, (739, 450), 18, (150, 255, 180), center=True, bold=True, mono=True, vcenter=True)
        draw_text(s, "Pipette volume", (739, 408), 13, INK_SOFT, center=True, bold=True)
        inp = getattr(self, "inp", None)
        self.minus.draw(s, inp)
        self.plus.draw(s, inp)
        self.mixb.enabled = self.last is not None and not self.mixed[self.last]
        self.mixb.draw(s, inp)
        self.doneb.draw(s, inp)
        m = getattr(self, "mouse", (480, 360))
        amt = 0.0 if self.tip is None else clamp(self.tip[0] / 200.0 + 0.15, 0, 1)
        gfx.pipette(s, m, SAMPLE, amt, plunger=0 if self.tip else 1, scale=0.7)


def _well_mask(w, h, r=14):
    m = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=r)
    return m


# ----------------------------------------------------------------- standard curve
def curve_od(c):
    return 0.05 + 2.6 * c / (c + 420.0)


def curve_conc(od):
    return 420.0 * (od - 0.05) / (2.65 - od)


def draw_curve(s, rect, od=None, stds=True):
    r = pygame.Rect(rect)
    ax = pygame.Rect(r.x + 50, r.y + 22, r.w - 66, r.h - 70)
    gfx.rrect(s, ax, (252, 252, 248), None, 0, 4, 0, False)
    xmax, ymax = 1000.0, 2.2

    def P(c, o):
        return (ax.x + ax.w * c / xmax, ax.bottom - ax.h * o / ymax)
    for c in range(0, 1001, 200):
        x = P(c, 0)[0]
        pygame.draw.line(s, (226, 226, 222), (x, ax.y), (x, ax.bottom), 1)
        draw_text(s, str(c), (x, ax.bottom + 5), 12, INK_SOFT, center=True)
    for o in (0.5, 1.0, 1.5, 2.0):
        y = P(0, o)[1]
        pygame.draw.line(s, (226, 226, 222), (ax.x, y), (ax.right, y), 1)
        draw_text(s, "%.1f" % o, (ax.x - 6, y - 8), 12, INK_SOFT, right=True)
    gfx.line(s, INK, ax.bottomleft, ax.bottomright, 2)
    gfx.line(s, INK, ax.bottomleft, ax.topleft, 2)
    draw_text(s, "Concentration (pg/mL)", (ax.centerx, ax.bottom + 24), 13, INK, center=True, bold=True)
    draw_text(s, "OD 450", (r.x + 4, r.y), 13, INK, bold=True)
    pts = [P(c, curve_od(c)) for c in range(0, 1001, 10)]
    pygame.draw.lines(s, mix(TURQ, WHITE, 0.55), False, pts, 7)
    pygame.draw.lines(s, TURQ, False, pts, 3)
    if stds:
        for c in (0, 31.25, 62.5, 125, 250, 500, 1000):
            gfx.circle(s, CORAL, P(c, curve_od(c)), 6, 2)
    if od is not None:
        y = P(0, od)[1]
        for x in range(ax.x, ax.right, 12):
            gfx.line(s, VIOLET, (x, y), (x + 6, y), 2)
        gfx.tag(s, ax.right - 150, y - 30, "unknown: OD %.2f" % od, (236, 228, 248), 12)


def q_curve(rng):
    c = rng.choice([150, 200, 250, 300, 350, 400, 450, 500, 600])
    od = round(curve_od(c), 2)
    c = int(round(curve_conc(od) / 10.0) * 10)
    wrong = {int(round(c * f / 10.0) * 10) for f in (0.5, 1.6, 2.2)}
    wrong.discard(c)
    opts = [c] + sorted(wrong)[:3]
    return dict(q="Read the unknown sample off the standard curve. What is its concentration?",
                options=["%d pg/mL" % o for o in opts], answer=0,
                why="Follow the OD across to the curve, then straight down to the concentration axis.",
                pic=lambda s, r: draw_curve(s, r, od))


def q_curve_dil(rng):
    c = rng.choice([200, 250, 300, 400])
    od = round(curve_od(c), 2)
    c = int(round(curve_conc(od) / 10.0) * 10)
    dil = rng.choice([5, 10])
    opts = [c * dil, c, max(1, c // dil), c * dil * 2]
    return dict(q="This serum sample was diluted 1:%d before the assay. What is the concentration in the serum?" % dil,
                options=["%d pg/mL" % o for o in opts], answer=0,
                why="Read the diluted sample off the curve (%d pg/mL), then multiply by the dilution factor (x%d)." % (c, dil),
                pic=lambda s, r: draw_curve(s, r, od))


TECH = dict(
    key="elisa", name="ELISA", full="Sandwich enzyme-linked immunosorbent assay", wing="Proteins", icon="elisa",
    blurb="Measures how much of a protein is in a liquid. Two antibodies trap it in a plastic well and an enzyme makes "
          "a colour whose strength follows the amount of protein.",
    facts=[
        "ELISA was described in 1971 by Eva Engvall and Peter Perlmann in Stockholm, and independently by Anton Schuurs and Bauke van Weemen in the Netherlands.",
        "It replaced radioimmunoassay for many uses by swapping radioactive labels for enzymes that make a coloured product.",
        "A 96-well plate has 8 rows (A-H) and 12 columns (1-12), 9 mm apart; its footprint is an industry standard so robots can handle any brand.",
        "HRP turns TMB blue. Sulfuric acid stops the reaction and turns the product yellow, which is read at 450 nm.",
        "A sandwich ELISA needs two antibodies that bind different parts (epitopes) of the same protein.",
        "Home pregnancy tests use the same sandwich idea on a paper strip to detect the hormone hCG.",
        "Plotted against log concentration, ELISA standard curves are S-shaped, so they are usually fitted with a four-parameter logistic curve rather than a straight line.",
    ],
    quiz=[
        dict(q="A sample's OD is higher than your top standard. What do you do?", options=["Dilute it and run it again",
             "Extrapolate the curve", "Report the top standard's value", "Read it at a different wavelength"], answer=0,
             why="Values outside the standard curve are unreliable. Dilute into the range and multiply back."),
        dict(q="Why do you subtract the blank?", options=["To remove the colour from background and the reagents themselves",
             "To correct for pipetting errors", "To convert OD to concentration", "To normalise to total protein"], answer=0,
             why="The blank has every reagent but no antigen, so its OD is background."),
        dict(q="What does the stop solution do?", options=["Acid stops HRP and turns the blue product yellow",
             "It washes away unbound antibody", "It fixes the cells", "It blocks the plate"], answer=0,
             why="Stopping fixes the colour at one moment so the whole plate can be read together."),
    ],
    music=dict(name="Plate Reader Waltz", bpm=132, beats=3, root=55, mode="maj", prog=[0, 4, 5, 3, 0, 1, 4, 0],
               lead="bell", comp="waltz", drums="none",
               motif=[(4, 2), (5, 1), (4, 1), (2, 2), (0, 4), (1, 2)]),
    stages=[
        ("elisa_layers", dict(heading="Steps added to the well", tint=(236, 236, 222), limit=50,
                              steps=[("Capture antibody", TURQ, "The capture antibody sticks to the plastic and will hold the antigen."),
                                     ("Block (BSA)", (220, 220, 225), "Blocking protein covers the bare plastic."),
                                     ("Sample (antigen)", CORAL, "The antigen in your sample binds the capture antibody."),
                                     ("Biotinylated detection antibody", LAV, "A second antibody, carrying biotin, binds another epitope of the antigen."),
                                     ("Streptavidin-HRP", YELLOW, "Streptavidin grips biotin tightly and brings the HRP enzyme."),
                                     ("TMB substrate", (150, 170, 240), "HRP turns TMB blue: more antigen, more blue."),
                                     ("Stop solution (acid)", (246, 220, 120), "Acid stops the enzyme; the colour turns yellow.")])),
        ("elisa_dilute", dict()),
        ("quiz", dict(title="Read the standard curve", n=3, tint=(236, 236, 222),
                      questions=[q_curve, q_curve_dil,
                                 dict(q="Why run every standard and sample in duplicate?", options=[
                                     "To spot pipetting errors and average out well-to-well noise", "Because the reader needs two wells",
                                     "To double the signal", "To make a 1:2 dilution"], answer=0,
                                      why="Duplicates that disagree show a pipetting mistake; their mean is more precise.")])),
        ("stop", dict(title="Stop the colour", scene=scene_tmb, dur=9.0, ideal=0.5, window=(0.3, 0.74),
                      readout=lambda v: "TMB %s" % mmss(v * 30 * 60),
                      instr="The plate turns blue as HRP works. Add the stop solution when the standards show a clear gradient, "
                            "before the top ones max out and the blank turns blue.",
                      early_msg="Too pale: the low standards cannot be told apart from the blank.",
                      late_msg="Too late: the top standards are saturated and the background is rising.",
                      over_msg="Far too long: the whole plate is dark blue.",
                      good_msg="Stopped with a clean gradient across the standards.")),
    ],
)
TECHS = [TECH]
