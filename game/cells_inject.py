# -*- coding: utf-8 -*-
"""Zebrafish embryo microinjection: calibrating the bolus, then injecting one-cell embryos."""
import math
import random
import pygame
import audio
import gfx
import render as R
from stage import Stage, register, TOP, BOTTOM
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, LAV, VIOLET, NIGHT, WHITE,
                  GREEN, RED, YELLOW, clamp, mix, draw_text, draw_wrapped)
from cells_common import scope_mask, scope_card, field_bg, field_rect, masked_field, soften, tremor, ell_pts

PHENOL = (214, 60, 104)
OIL = (222, 214, 182)
YOLK = (196, 166, 106)
CYTO = (226, 224, 212)
GLASS = (214, 230, 236)
_SPR = {}


def d_um(v_nl):
    """Diameter (µm) of a sphere holding v_nl nanolitres (1 nL = 10^6 µm³, V = πd³/6)."""
    return (6.0 * v_nl * 1e6 / math.pi) ** (1 / 3.0)


def needle(s, tip, fill=0.6, angle=-0.62, length=300, width=11):
    """Pulled borosilicate capillary from the upper left, as it looks under transmitted light:
    clear glass with dark refractive edges and a bright inner line, a pink column of injection
    mix inside, and a bevelled opening at the tip."""
    x, y = tip
    dx, dy = -math.cos(angle), math.sin(angle)
    nx, ny = -dy, dx
    end = (x + dx * length, y + dy * length)
    bev = 7
    outer = [(x + dx * bev + nx * 1.2, y + dy * bev + ny * 1.2), (x, y),
             (end[0] - nx * width, end[1] - ny * width), (end[0] + nx * width, end[1] + ny * width)]
    R.aa_poly(s, GLASS, outer, 0, None)
    w2 = width * 0.56
    inner = [(x + dx * 24, y + dy * 24), (end[0] + nx * w2, end[1] + ny * w2), (end[0] - nx * w2, end[1] - ny * w2)]
    R.aa_poly(s, mix(GLASS, PHENOL, 0.3 + 0.55 * fill), inner, 0, None)
    # refraction: dark outer edges, a bright line just inside each wall
    for side in (1, -1):
        a = (x + nx * 0.6 * side, y + ny * 0.6 * side)
        b = (end[0] + nx * width * side, end[1] + ny * width * side)
        gfx.line(s, (70, 80, 88), a, b, 2)
        a2 = (x + dx * 14 + nx * 1.4 * side, y + dy * 14 + ny * 1.4 * side)
        b2 = (end[0] + nx * (width - 3) * side, end[1] + ny * (width - 3) * side)
        gfx.line(s, (250, 254, 255), a2, b2, 1)
    gfx.line(s, (70, 80, 88), outer[0], outer[1], 1)


def _yolk_sprite(seed, pink):
    """The yolk under transmitted light: dense, amber-grey, darker towards its edge, granular."""
    key = ("yolk", seed, int(pink * 10))
    sp = _SPR.get(key)
    if sp is not None:
        return sp
    r = YR
    S = 3
    n = 2 * r + 4
    col = mix(YOLK, PHENOL, pink * 0.6)
    big = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
    c = n * S // 2
    tex = gfx.texture(2 * r * S, 2 * r * S, col, 5 * S, 14, 400 + seed, 3)
    disc = pygame.Surface((2 * r * S, 2 * r * S), pygame.SRCALPHA)
    disc.blit(tex, (0, 0))
    try:
        import numpy as np
        yy, xx = np.mgrid[0:2 * r * S, 0:2 * r * S].astype(np.float32)
        d = np.sqrt((xx - r * S) ** 2 + (yy - r * S) ** 2) / (r * S)
        shade = np.clip(1.08 - 0.45 * d ** 2.4, 0.4, 1.2)
        arr = pygame.surfarray.pixels3d(disc)
        arr[:] = np.clip(arr.astype(np.float32) * shade.T[..., None], 0, 255).astype(np.uint8)
        del arr
        a = pygame.surfarray.pixels_alpha(disc)
        a[:] = np.where(d.T <= 1.0, 255, 0).astype(np.uint8)
        del a
    except Exception:
        pass
    big.blit(disc, (c - r * S, c - r * S))
    rnd = random.Random(seed)
    for _ in range(60):                       # yolk platelets
        a, dd = rnd.uniform(0, math.tau), r * S * math.sqrt(rnd.random()) * 0.9
        pygame.draw.circle(big, R.lighten(col, -0.35 if rnd.random() < 0.6 else 0.25) + (150,),
                           (int(c + math.cos(a) * dd), int(c + math.sin(a) * dd)), rnd.randint(2, 5))
    pygame.draw.circle(big, R.lighten(col, -0.55) + (200,), (c, c), r * S, 2 * S)
    sp = soften(pygame.transform.smoothscale(big, (n, n)), 1.3)
    _SPR[key] = sp
    return sp


def _chorion_sprite(seed):
    """The chorion: a clear, thin shell seen as a dark outer line and a bright inner line
    (refraction), with a faint reflection and a few specks stuck to it."""
    key = ("chor", seed)
    sp = _SPR.get(key)
    if sp is not None:
        return sp
    r = CHOR
    S = 3
    n = 2 * r + 8
    big = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
    c = n * S // 2
    pygame.draw.circle(big, (244, 248, 246, 40), (c, c), r * S)
    pygame.draw.circle(big, (70, 76, 80, 220), (c, c), r * S, int(1.2 * S))
    pygame.draw.circle(big, (255, 255, 255, 200), (c, c), int((r - 1.6) * S), S)
    pygame.draw.circle(big, (120, 128, 130, 90), (c, c), int((r - 3.2) * S), S)
    pygame.draw.arc(big, (255, 255, 255, 150), (c - (r - 7) * S, c - (r - 7) * S, 2 * (r - 7) * S, 2 * (r - 7) * S), 1.9, 2.7, 2 * S)
    rnd = random.Random(seed + 7)
    for _ in range(5):
        a = rnd.uniform(0, math.tau)
        pygame.draw.circle(big, (90, 96, 92, 200), (int(c + math.cos(a) * r * S), int(c + math.sin(a) * r * S)), rnd.randint(2, 4))
    sp = soften(pygame.transform.smoothscale(big, (n, n)), 1.15)
    _SPR[key] = sp
    return sp


def _bolus(s, c, rad, a=190):
    """A drop of phenol-red injection mix: translucent pink, a darker refractive rim, a highlight."""
    rad = max(2, int(rad))
    R.gd.filled_circle(s, int(c[0]), int(c[1]), rad, PHENOL + (int(a * 0.8),))
    R.gd.aacircle(s, int(c[0]), int(c[1]), rad, R.lighten(PHENOL, -0.45))
    if rad >= 5:
        R.gd.aacircle(s, int(c[0]), int(c[1]), rad - 1, R.lighten(PHENOL, -0.25))
        R.gd.filled_circle(s, int(c[0] - rad * 0.35), int(c[1] - rad * 0.35), max(1, rad // 4), (255, 226, 236))
        R.gd.filled_circle(s, int(c[0] + rad * 0.2), int(c[1] + rad * 0.25), max(1, rad // 3), R.lighten(PHENOL, 0.25) + (120,))


_LAYER = {}
VIEW = pygame.Rect(30, 52 + 70, 960 - 60, 340)


def _trench_bg():
    """A camera image through the stereomicroscope: 1.5 % agarose in a dish lit from below, with a
    moulded trench whose walls show as soft dark and bright lines; vignetting at the corners."""
    if "bg" in _LAYER:
        return _LAYER["bg"]
    b = pygame.Surface((W, H))
    gfx.bench(b, PEACH)
    v = VIEW
    gfx.shadow(b, v, 18)
    b.blit(R.rrect_surf(v.w + 16, v.h + 16, (16, 16, 20), (60, 62, 70), 2, 20, 0, False), (v.x - 8, v.y - 8))
    img = field_rect(v.w, v.h, (214, 210, 194), 7).copy()
    tr = pygame.Rect(0, 300 - CHOR - 12 - v.y, v.w, 2 * CHOR + 24)
    band = pygame.Surface(tr.size, pygame.SRCALPHA)
    band.blit(R.vgrad(tr.size, (150, 146, 132), (196, 192, 178)), (0, 0))
    band.set_alpha(120)
    img.blit(band, tr.topleft)
    for k, (col, w_) in enumerate((((96, 92, 82), 3), ((250, 250, 244), 2))):
        pygame.draw.line(img, col, (0, tr.y + k * 3), (v.w, tr.y + k * 3), w_)
    pygame.draw.line(img, (250, 250, 244), (0, tr.bottom), (v.w, tr.bottom), 2)
    pygame.draw.line(img, (130, 126, 114), (0, tr.bottom + 3), (v.w, tr.bottom + 3), 2)
    try:
        import numpy as np
        yy, xx = np.mgrid[0:v.h, 0:v.w].astype(np.float32)
        d = np.sqrt(((xx - v.w / 2) / (v.w * 0.62)) ** 2 + ((yy - v.h / 2) / (v.h * 0.85)) ** 2)
        vig = pygame.Surface(v.size, pygame.SRCALPHA)
        vig.fill((10, 10, 14, 0))
        pygame.surfarray.pixels_alpha(vig)[:] = (np.clip((d - 0.55) / 0.5, 0, 1) ** 2 * 200).astype(np.uint8).T
        img.blit(vig, (0, 0))
    except Exception:
        pass
    mask = R.rrect_surf(v.w, v.h, (255, 255, 255), None, 0, 14, 0, False)
    im2 = pygame.Surface(v.size, pygame.SRCALPHA)
    im2.blit(img, (0, 0))
    im2.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    b.blit(im2, v.topleft)
    draw_text(b, "stereomicroscope, 4x  ·  agarose injection trench", (v.x + 4, v.bottom + 12), 12, (196, 198, 206), bold=True)
    _LAYER["bg"] = b
    return b


def _oil_field(s, c, R_):
    field_bg(s, c, R_, OIL, 3)


# ------------------------------------------------------------------ calibration
PXUM = 1.3          # screen pixels per micrometre in the calibration view


def _reticle():
    """Stage micrometer: 10 µm divisions, numbered every 100 µm, etched on the slide under the oil."""
    if "ret" in _LAYER:
        return _LAYER["ret"]
    sf = pygame.Surface((W, H), pygame.SRCALPHA)
    x0, ry = 330, 390
    for um in range(0, 201, 10):
        x = x0 + um * PXUM
        h = 22 if um % 100 == 0 else 14 if um % 50 == 0 else 8
        gfx.line(sf, (44, 42, 40), (x, ry), (x, ry - h), 2 if um % 50 == 0 else 1)
        if um % 100 == 0:
            draw_text(sf, str(um), (x, ry + 4), 13, (44, 42, 40), center=True, bold=True)
    gfx.line(sf, (44, 42, 40), (x0, ry), (x0 + 200 * PXUM, ry), 2)
    draw_text(sf, "µm", (x0 + 200 * PXUM + 14, ry - 8), 13, (44, 42, 40), bold=True)
    sf = soften(sf, 1.25)
    _LAYER["ret"] = sf
    return sf


@register("inject_calib")
class InjectCalib(Stage):
    title = "Calibrate the needle"
    instr = ("Hold the mouse button (or Space) to push injection mix into a drop of mineral oil. Release when the bolus "
             "has the right diameter on the micrometer scale. The volume of a sphere is πd³/6.")

    def setup(self):
        self.targets = self.p.get("targets", [(1.0, "1 nL is a sphere about 124 µm across."),
                                              (0.5, "0.5 nL: about 0.1 mm across."),
                                              (2.0, "Twice the volume makes the diameter only 1.26 times larger.")])
        self.r = 0
        self.vol = 0.0
        self.state = "ready"       # ready, push, show
        self.wait = 0
        self.scores = []
        self.res = []
        self.tip = (330, 236)
        self.hint = "Hold to inject, release at the target size."
        self.slope = self.lv(185, 220, 300)
        # on the Expert bench every needle flows differently (tip size, clogging): watch, do not count
        self.rates = [0.6 * (self.rng.uniform(0.7, 1.35) if self.level == 2 else self.rng.uniform(0.9, 1.1) if self.level == 1 else 1.0)
                      for _ in self.targets]

    def tick(self, inp):
        hold = inp.down or "space" in inp.held
        if self.state == "ready":
            if (inp.click or "space" in inp.pressed) or (hold and self.t > 20):
                self.state = "push"
                audio.sfx("pour")
        elif self.state == "push":
            self.vol += self.rates[min(self.r, len(self.rates) - 1)] / 60.0
            if not hold or self.vol > 6:
                self.evaluate()
        else:
            self.wait -= 1
            if self.wait <= 0:
                self.r += 1
                self.vol = 0
                if self.r >= len(self.targets):
                    fb = ["Target %.1f nL, you injected %.2f nL." % (t, v) for t, v in self.res]
                    # the 1 nL bolus is the one you will inject: its error carries into the next step
                    ratio = [v / t for t, v in self.res if abs(t - 1.0) < 1e-6]
                    self.ctx.inject_cal = ratio[0] if ratio else (self.res[0][1] / self.res[0][0])
                    fb.append("Your 1 nL setting actually delivers %.2f nL, so in the next step the bolus grows that much faster (or slower) than expected; judge it by the ring." % self.ctx.inject_cal)
                    self.finish(sum(self.scores) / len(self.scores), *fb)
                else:
                    self.state = "ready"

    def evaluate(self):
        tv = self.targets[self.r][0]
        err = abs(self.vol / tv - 1)
        sc = clamp(100 - self.slope * err, 0, 100)
        self.scores.append(sc)
        self.res.append((tv, self.vol))
        self.state = "show"
        self.wait = 110
        audio.sfx("good" if sc >= 75 else "bad")
        self.floaters.add(560, 120, "%.2f nL" % self.vol, GREEN if sc >= 75 else CORAL_D, 26)
        if sc >= 80:
            self.particles.burst(560, 236, 16)

    def partial(self):
        return sum(self.scores) / len(self.targets)

    def autoplay(self):
        self.ctx.inject_cal = 0.97
        self.finish(90, "Target 1.0 nL, you injected 0.97 nL.")

    def render(self, s):
        gfx.bench(s, PEACH)
        c, R_ = (440, 290), 214
        scope_card(s, c, R_)
        x0, ry = 330, 390
        tip = self.tip
        ox, oy = c[0] - R_, c[1] - R_

        # the oil and the micrometer never change: photograph them once, then draw the moving parts on a copy
        if "calbase" not in _LAYER:
            def base(f, cc):
                field_bg(f, cc, R_, OIL, 3)
                f.blit(_reticle(), (-ox, -oy))
            tmp0 = pygame.Surface((2 * R_, 2 * R_), pygame.SRCALPHA)
            base(tmp0, (R_, R_))
            from cells_common import photo_finish
            _LAYER["calbase"] = photo_finish(tmp0, 1.0)
            _LAYER["calmask"] = R._ellipse_surf(2 * R_, 2 * R_, (255, 255, 255, 255), None, 0)
        # draw straight onto the screen; the opaque eyepiece surround hides whatever lies outside the field
        s.blit(_LAYER["calbase"], (c[0] - R_, c[1] - R_))
        clip = s.get_clip()
        s.set_clip(pygame.Rect(c[0] - R_, c[1] - R_, 2 * R_, 2 * R_))
        f = s
        t = tip
        ox = oy = 0
        if self.vol > 0:
            rad = d_um(self.vol) / 2 * PXUM
            cx = t[0] + rad
            _bolus(f, (cx, t[1]), rad, 220)
            R.gd.aacircle(f, int(cx), int(t[1]), int(rad) - 3, (255, 190, 206))
            for ex in (cx - rad, cx + rad):          # guide lines from the edges down to the scale
                for yy in range(int(t[1]), ry - oy - 24, 10):
                    pygame.draw.line(f, (90, 80, 70), (ex, yy), (ex, yy + 5), 1)
        needle(f, t, 0.7, angle=-0.42, length=230, width=24)
        s.set_clip(clip)
        from cells_common import _scope_overlay, EYE
        s.blit(_scope_overlay(R_, EYE, False), (c[0] - R_ - 14, c[1] - R_ - 14))
        draw_text(s, "mineral oil on a stage micrometer, 10x", (c[0], c[1] + R_ + 1), 11, (170, 172, 180), center=True)
        p = pygame.Rect(690, TOP + 20, 250, 420)
        gfx.card(s, p, CARD)
        k = min(self.r, len(self.targets) - 1)
        tv, tip_txt = self.targets[k]
        draw_text(s, "Bolus %d of %d" % (k + 1, len(self.targets)), (p.x + 16, p.y + 14), 16, MUTED, bold=True)
        draw_text(s, "Target: %.1f nL" % tv, (p.x + 16, p.y + 40), 24, INK, bold=True)
        y = draw_wrapped(s, tip_txt, (p.x + 16, p.y + 80), 15, p.w - 32, INK_SOFT)
        draw_wrapped(s, "V = πd³/6\n1 nL = 10⁶ µm³", (p.x + 16, y + 12), 16, p.w - 32, INK, bold=True)
        if self.state == "show":
            v = self.res[-1][1]
            draw_text(s, "d = %d µm" % round(d_um(v)), (p.x + 16, p.y + 250), 20, INK, bold=True)
            draw_text(s, "V = %.2f nL" % v, (p.x + 16, p.y + 280), 20, INK, bold=True)
        elif self.state == "ready":
            draw_wrapped(s, "Hold the mouse button to start.", (p.x + 16, p.y + 250), 15, p.w - 32, CORAL_D, bold=True)


# ------------------------------------------------------------------ injecting embryos
CHOR, YR = 46, 26          # chorion and yolk radius: the chorion is roughly twice as wide as the embryo


class Embryo:
    def __init__(self, x, y, rng, t_div):
        self.x, self.y = x, y
        self.ang = rng.uniform(-math.pi, math.pi)
        self.t_div = t_div             # frames until the first cleavage
        self.inj = None                # (dx, dy, vol, where)
        self.burst = False
        self.score = 0.0
        self.grains = [(rng.uniform(0, math.tau), rng.uniform(0, YR - 4)) for _ in range(16)]

    def cells(self, t):
        """Cell count at frame t (1, 2 or 4): the second cleavage follows about 15 min after the first."""
        if t < self.t_div:
            return 1
        return 2 if t < self.t_div + 900 else 4

    def yolk_c(self):
        return self.x - math.cos(self.ang) * 5, self.y - math.sin(self.ang) * 5

    def caps(self, t):
        """The clear cytoplasm on top of the yolk at the animal pole, as ellipses (cx, cy, radial, tangential).
        One cap (the blastodisc) at the one-cell stage, then two or four blastomeres side by side.
        The inner half of each ellipse lies under the yolk, so what shows is a dome on the yolk surface."""
        yx, yy = self.yolk_c()
        dx, dy = math.cos(self.ang), math.sin(self.ang)
        px, py = -dy, dx
        n = self.cells(t)
        if n == 1:
            k = clamp(t / max(1, self.t_div), 0, 1)       # cytoplasm keeps streaming to the animal pole
            rad, tan = 10 + 4 * k, 17 + 4 * k
            d = YR - 2
            return [(yx + dx * d, yy + dy * d, rad, tan)]
        if n == 2:
            d = YR - 1
            return [(yx + dx * d + px * sgn * 9.5, yy + dy * d + py * sgn * 9.5, 12, 10.5) for sgn in (-1, 1)]
        out = []
        for sgn in (-1, 1):
            for off, d in ((5.5, YR + 1), (13.5, YR - 3)):
                out.append((yx + dx * d + px * sgn * off, yy + dy * d + py * sgn * off, 8, 7))
        return out

    def in_cap(self, px, py, t):
        ca, sa = math.cos(self.ang), math.sin(self.ang)
        for cx, cy, rad, tan in self.caps(t):
            ux, uy = px - cx, py - cy
            r_, t_ = ux * ca + uy * sa, -ux * sa + uy * ca
            if (r_ / rad) ** 2 + (t_ / tan) ** 2 < 1:
                return True
        return False

    def where(self, px, py, t):
        yx, yy = self.yolk_c()
        if math.hypot(px - yx, py - yy) < YR:
            return "yolk"
        if self.in_cap(px, py, t):
            return "cell"
        if math.hypot(px - self.x, py - self.y) < CHOR:
            return "space"
        return None

    def draw(self, s, t):
        seed = int(self.x)
        ch = _chorion_sprite(seed % 5)
        s.blit(ch, (int(self.x - ch.get_width() / 2), int(self.y - ch.get_height() / 2)))
        if self.burst:
            rnd = random.Random(seed)
            for k in range(14):
                a = k * 0.45
                d = rnd.uniform(8, 30)
                R.gd.filled_circle(s, int(self.x + math.cos(a) * d), int(self.y + math.sin(a) * d * 0.8), rnd.randint(3, 6), mix(YOLK, (200, 160, 90), rnd.random()))
            gfx.alpha_rect(s, (self.x - 24, self.y + CHOR + 5, 48, 18), (120, 30, 20), 140, 9)
            draw_text(s, "burst", (self.x, self.y + CHOR + 14), 12, WHITE, center=True, bold=True, vcenter=True)
            return
        n = self.cells(t)
        for cx, cy, rad, tan in self.caps(t):       # clear cytoplasm (blastodisc / blastomeres) as domes on the yolk
            pts = ell_pts(cx, cy, rad, tan, self.ang, 28)
            R.gd.filled_polygon(s, pts, (212, 210, 198, 235))
            hl = ell_pts(cx + math.cos(self.ang) * rad * 0.25 - math.sin(self.ang) * tan * 0.2,
                         cy + math.sin(self.ang) * rad * 0.25 + math.cos(self.ang) * tan * 0.2, rad * 0.45, tan * 0.55, self.ang, 18)
            R.gd.filled_polygon(s, hl, (244, 244, 236, 140))
            pygame.draw.aalines(s, (96, 92, 80), True, pts)
        yx, yy = self.yolk_c()
        pink = 0.3 if (self.inj and self.inj[3] in ("yolk", "cell")) else 0.0
        yk = _yolk_sprite(seed % 7, pink)
        s.blit(yk, (int(yx - yk.get_width() / 2), int(yy - yk.get_height() / 2)))
        if n == 1 and self.t_div - t < 150:      # the first cleavage furrow appears at the top of the dome
            (cx, cy, rad, tan), = self.caps(t)
            dx, dy = math.cos(self.ang), math.sin(self.ang)
            gfx.line(s, (100, 96, 84), (cx + dx * rad * 0.95, cy + dy * rad * 0.95), (cx + dx * rad * 0.35, cy + dy * rad * 0.35), 2)
        if self.inj:
            dx_, dy_, vol, wh = self.inj
            _bolus(s, (self.x + dx_, self.y + dy_), 8 * vol ** (1 / 3.0), 190 if wh != "space" else 130)
        lab = "%d-cell" % n
        col = INK if n == 1 else CORAL_D
        gfx.alpha_rect(s, (self.x - 24, self.y + CHOR + 5, 48, 18), (20, 20, 24) if n == 1 else (120, 30, 20), 120, 9)
        draw_text(s, lab, (self.x, self.y + CHOR + 14), 12, WHITE, center=True, bold=True, vcenter=True)


@register("inject_embryos")
class InjectEmbryos(Stage):
    title = "Inject the embryos"
    instr = ("Put the needle tip into the yolk or the cell of each embryo and hold the button to inject. Release when the pink "
             "bolus fills the dashed ring. Inject them all at the one-cell stage, before they divide. Your needle setting "
             "from the calibration decides how fast the bolus grows.")
    limit = 50

    def setup(self):
        n = self.p.get("n", self.lv(5, 6, 7))
        lo, hi = self.lv((22, 52), (16, 46), (12, 38))
        divs = [self.rng.uniform(lo, hi) for _ in range(n)]
        gap = 820 / n
        self.emb = [Embryo(70 + gap * (i + 0.5), 300, self.rng, int(divs[i] * 60)) for i in range(n)]
        self.amp = self.lv(1.4, 2.2, 3.2)
        self.size_ok = self.lv((0.7, 1.4), (0.75, 1.3), (0.82, 1.2))
        self.burst_at = self.lv(3.5, 3.0, 2.5)
        cal = getattr(self.ctx, "inject_cal", None)
        self.cal = clamp(cal, 0.5, 2.0) if cal else 1.0      # your needle setting from the calibration step
        self.agar_t = 0
        self.seed = self.rng.uniform(0, 100)
        self.tip = (480, 300)
        self.cur = None            # (embryo, where, dx, dy) while injecting
        self.vol = 0.0
        self.hint = "Tip in the yolk or cell, hold to inject, release at the ring. A furrow means it is about to divide."

    def tick(self, inp):
        tx, ty = tremor(self.t, self.seed, self.amp)
        if self.agar_t:
            self.agar_t -= 1
        self.tip = (inp.mouse[0] + tx, inp.mouse[1] + ty)
        if self.cur is None and inp.click:
            for e in self.emb:
                wh = e.where(self.tip[0], self.tip[1], self.t)
                if wh is None:
                    continue
                if e.inj or e.burst:
                    self.floaters.add(e.x, e.y - 60, "already injected", MUTED, 15)
                else:
                    self.cur = (e, wh, self.tip[0] - e.x, self.tip[1] - e.y)
                    self.vol = 0.0
                    audio.sfx("pop")
                break
            else:
                if not self.agar_t:
                    self.floaters.add(self.tip[0], self.tip[1] - 30, "tip in the agarose", MUTED, 15)
                    self.agar_t = 40
        if self.cur is not None:
            e, wh, dx, dy = self.cur
            self.vol += self.cal / 48          # a needle set too high flows faster, too low flows slower
            if self.vol > self.burst_at:
                e.burst = True
                e.inj = (dx, dy, self.vol, wh)
                e.where_ = wh
                self.cur = None
                self.shake = 14
                audio.sfx("buzz")
                self.floaters.add(e.x, e.y - 60, "too much: burst!", RED, 18)
            elif not inp.down:
                self.release()
        if all(e.inj or e.burst for e in self.emb) and self.cur is None:
            self.finish(self.total(), *self.feedback_lines())

    def release(self):
        e, wh, dx, dy = self.cur
        self.cur = None
        e.inj = (dx, dy, self.vol, wh)
        lo, hi = self.size_ok
        size = 1.0 if lo <= self.vol <= hi else 0.6 if lo - 0.25 <= self.vol <= hi + 0.3 else 0.25
        loc = 1.0 if wh in ("yolk", "cell") else 0.15
        n = e.cells(self.t)
        stg = 1.0 if n == 1 else 0.55 if n == 2 else 0.3
        e.score = size * loc * stg
        e.where_, e.stage_ = wh, n
        if wh == "space":
            msg = "outside the embryo"
        elif n > 1:
            msg = "%d-cell: uneven" % n
        elif size < 1:
            msg = "too small" if self.vol < lo else "too big"
        else:
            msg = "good bolus"
        good = e.score > 0.8
        audio.sfx("good" if good else "bad")
        self.floaters.add(e.x, e.y - 60, msg, GREEN if good else CORAL_D, 16)
        if good:
            self.particles.burst(e.x, e.y - 20, 10, cols=(PHENOL, YOLK, WHITE), speed=2.5)

    def total(self):
        return 100.0 * sum(e.score for e in self.emb) / len(self.emb)

    def feedback_lines(self):
        good = sum(1 for e in self.emb if e.score > 0.8)
        fb = ["%d of %d embryos got a good bolus at the one-cell stage." % (good, len(self.emb))]
        if any(getattr(e, "where_", "") == "space" for e in self.emb):
            fb.append("Mix left between the chorion and the embryo never gets in: aim for the yolk or the cell.")
        if any(getattr(e, "stage_", 1) > 1 for e in self.emb):
            fb.append("After the first division the mix is shared less evenly between cells, so the embryo can be mosaic.")
        if any(e.burst for e in self.emb):
            fb.append("A bolus several times too large can rupture the yolk.")
        if abs(self.cal - 1) > 0.15:
            fb.append("Your calibration left the injection pressure or pulse %s, so the bolus grew %.1f times %s than it should."
                      % ("set too high" if self.cal > 1 else "set too low", self.cal if self.cal > 1 else 1 / self.cal, "faster" if self.cal > 1 else "slower"))
        return fb[:4]

    def partial(self):
        return self.total()

    def autoplay(self):
        self.finish(92, "6 of 6 embryos got a good bolus at the one-cell stage.")

    def render(self, s):
        s.blit(_trench_bg(), (0, 0))
        for e in self.emb:
            e.draw(s, self.t)
        if self.cur is not None:
            e, wh, dx, dy = self.cur
            cx, cy = e.x + dx, e.y + dy
            _bolus(s, (cx, cy), 8 * self.vol ** (1 / 3.0), 200)
            r = 8                                    # the target size, as a dashed ring
            for k in range(16):
                a = k * math.tau / 16 + self.t * 0.05
                pygame.draw.arc(s, (30, 30, 36), (cx - r, cy - r, 2 * r, 2 * r), a, a + 0.2, 2)
        needle(s, self.tip, 0.6, length=320, width=16)
        mins = int(self.t / 60.0)
        draw_text(s, "%d min into the session (sped up). At 28.5 °C each embryo divides about 45 min after fertilisation." % mins,
                  (W - 34, VIEW.bottom + 12), 12, (196, 198, 206), right=True, bold=True)
        gfx.tag(s, W - 200, TOP + 12, "Injected %d / %d" % (sum(1 for e in self.emb if e.inj), len(self.emb)), CARD, 15)


QUIZ = [
    dict(q="Why inject zebrafish embryos at the one-cell stage?", options=["So the mix reaches every cell of the embryo",
         "Because the chorion is softer later", "Because the yolk is absent later", "Because only then is the embryo transparent"],
         answer=0, why="Material injected later spreads less evenly, so expression or editing can be mosaic."),
    dict(q="Why is phenol red added to the injection mix?", options=["To see the bolus and check its size",
         "To keep the pH at 7.4 in the embryo", "To kill bacteria on the chorion", "To make the needle slide in"],
         answer=0, why="The red dye makes the bolus visible, so you can calibrate the volume and see each injection."),
    dict(q="A bolus in oil measures 0.1 mm across. About how much did you inject?", options=["0.5 nL", "0.05 nL", "5 nL", "50 nL"],
         answer=0, why="V = πd³/6 = π × (100 µm)³ / 6 ≈ 5.2 × 10⁵ µm³ ≈ 0.5 nL."),
    dict(q="Can mRNA injected into the yolk of a one-cell embryo reach the cell?",
         options=["Yes, cytoplasmic streaming carries it into the cell", "No, the yolk is sealed off from the cell",
                  "Only if it is injected after the 8-cell stage", "Only proteins can move from the yolk"],
         answer=0, why="In early zebrafish embryos the yolk and the cells are connected, so yolk injections work for mRNA and morpholinos."),
    dict(q="How long does a zebrafish embryo stay at the one-cell stage at 28.5 °C?", options=["About 40-45 minutes",
         "About 5 minutes", "About 4 hours", "About a day"], answer=0, why="The first cleavage happens at about 0.75 hours after fertilisation."),
]

TECH = dict(
    key="inject", name="Microinjection", full="Zebrafish embryo microinjection", wing="Cells & embryos", icon="inject",
    blurb="Injecting a nanolitre of mRNA, DNA, morpholino or Cas9 into freshly fertilised zebrafish eggs with a fine glass needle.",
    facts=[
        "At 28.5 °C a zebrafish embryo stays at the one-cell stage for about 45 minutes; the first cleavage comes at about 0.75 hours.",
        "Soon after fertilisation, cytoplasm streams towards the animal pole and forms the cell on top of the yolk.",
        "In the earliest stages the yolk is connected to the cells, so mRNA injected into the yolk still reaches them.",
        "A bolus about 0.1 mm across holds roughly 0.5 nL, because the volume of a sphere is πd³/6.",
        "Phenol red is added to injection mixes so the bolus can be seen and measured.",
        "One zebrafish pair can lay a couple of hundred eggs in a morning, so a single session can inject hundreds of embryos.",
        "Injection needles are pulled from glass capillaries on a heated puller; the closed tip is opened by breaking it with fine forceps.",
        "Zebrafish embryos are transparent, so fluorescent reporters injected in the morning can be watched in living embryos the same day.",
    ],
    quiz=QUIZ,
    music=dict(name="Yolk Sac Serenade", bpm=84, beats=4, root=52, mode="pent", prog=[0, 3, 4, 0, 2, 3, 1, 0],
               lead="whistle", comp="pad", drums="shuffle", swing=0.18,
               motif=[(2, 2), (3, 1), (4, 1), (5, 3), (4, 1), (3, 2), (2, 2), (0, 4)]),
    stages=[
        ("inject_calib", {}),
        ("inject_embryos", {}),
        ("quiz", dict(title="Injection know-how", questions=QUIZ, n=3, tint=PEACH,
                      instr="Three questions from the injection room.")),
    ],
)
TECHS = [TECH]
