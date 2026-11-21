# -*- coding: utf-8 -*-
"""Helpers shared by the DNA-wing techniques: gel pictures, band migration, hand tremor,
and the drawn lab equipment (freezer box, electrophoresis tank, UV transilluminator,
power supply, water bath, ice bucket, centrifuge rotor, colonies, spreader, tips).
Static parts are rendered once and cached."""
import math
import random
import pygame
import core
import gfx
import render as R
import real
from core import (W, H, INK, INK_SOFT, MUTED, CARD, GEL, DYE, WHITE, CORAL, CORAL_D, TURQ, SAND, RED, NIGHT,
                  draw_text, clamp, mix, text_surf, pretty)

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

LADDER_1KB = [10000, 8000, 6000, 5000, 4000, 3000, 2000, 1500, 1000, 500]
LADDER_100 = [3000, 2000, 1500, 1200, 1000, 900, 800, 700, 600, 500, 400, 300, 200, 100]   # a 100 bp Plus ladder
UV_BAND = (255, 170, 130)
UV_GLOW = (255, 140, 110)
BUFFER = (150, 196, 226)
AGAROSE = (228, 238, 243)

_cache = {}


def cached(key, make):
    v = _cache.get(key)
    if v is None:
        if len(_cache) > 400:
            _cache.clear()
        v = _cache[key] = make()
    return v


def float_x(x, txt, size, margin=14):
    """x for a rising floater text (centred on x) so the whole text stays on screen."""
    hw = core.text_w(txt, size, bold=True) / 2.0 + 4
    return clamp(x, margin + hw, W - margin - hw)


def fmt_bp(n):
    if n >= 1000:
        v = n / 1000.0
        return ("%g kb" % round(v, 1))
    return "%d bp" % n


def mobility(size):
    """Distance travelled relative to the bromophenol-blue dye front (1.0 ~ 300 bp in 1 % agarose)."""
    return 1.0 - 0.55 * math.log10(size / 300.0)


class Tremor:
    """Smooth hand tremor: a sum of slow sines with random phases."""
    def __init__(self, rng):
        self.ph = [(rng.uniform(0, math.tau), rng.uniform(0, math.tau)) for _ in range(3)]
        self.fr = [0.07, 0.13, 0.23]

    def at(self, t, amp):
        x = sum(math.sin(t * f + p[0]) / (k + 1) for k, (f, p) in enumerate(zip(self.fr, self.ph)))
        y = sum(math.sin(t * f * 1.1 + p[1]) / (k + 1) for k, (f, p) in enumerate(zip(self.fr, self.ph)))
        return x * amp * 0.6, y * amp * 0.6


def flask_shape(x, y, w, h):
    """Erlenmeyer flask outline points: (x, y) is the top of the neck centre."""
    nw = w * 0.22
    return [(x - nw, y), (x + nw, y), (x + nw, y + h * 0.32), (x + w / 2, y + h), (x - w / 2, y + h), (x - nw, y + h * 0.32)]


def tube_surface(w, h, liquid, level, cap=CORAL, blue_mix=None):
    """A tube drawn on its own transparent surface (for rotating)."""
    sf = pygame.Surface((w + 30, h + 20), pygame.SRCALPHA)
    gfx.tube(sf, 15, 10, w, h, liquid, level, cap)
    return sf


# ------------------------------------------------------------------ small effects
def soft_blob(s, c, r, col=(255, 255, 255), strength=0.3):
    """Additive soft light: fog, breath, steam (brightens what is under it)."""
    gfx.glow(s, c, r, tuple(int(v * strength) for v in col), 1.0)


def steam(s, x, y, t, n=3, h=60, a=70, spread=30, col=WHITE):
    """Rising wisps of steam above (x, y)."""
    for k in range(n):
        ph = (t * 0.012 + k / float(n)) % 1.0
        yy = y - ph * h
        xx = x + (k - (n - 1) / 2.0) * spread + math.sin(t * 0.03 + k * 2) * 8 * ph
        r = 10 + 22 * ph
        gfx.alpha_circle(s, col, (xx, yy), r, int(a * (1 - ph) * min(1, ph * 6)))


def ice_crystal(s, x, y, r, col=(255, 255, 255)):
    for k in range(3):
        a = k * math.pi / 3
        dx, dy = math.cos(a) * r, math.sin(a) * r
        pygame.draw.aaline(s, col, (x - dx, y - dy), (x + dx, y + dy))
        for sgn in (-1, 1):
            bx, by = x + sgn * dx * 0.55, y + sgn * dy * 0.55
            for b in (-0.6, 0.6):
                ca = a + b + (math.pi if sgn < 0 else 0)
                pygame.draw.aaline(s, col, (bx, by), (bx + math.cos(ca) * r * 0.35, by + math.sin(ca) * r * 0.35))


def frost_layer(w, h, seed=1, density=1.0):
    """Translucent white frost: noisy patches thicker at the edges, plus ice crystals."""
    def make():
        sf = pygame.Surface((w, h), pygame.SRCALPHA)
        if np is not None:
            n = R.value_noise(w, h, 16, seed, 3)
            yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
            edge = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
            e = np.clip(1 - edge / 34.0, 0, 1) ** 1.6
            a = np.clip((n - 0.45) * 2.2 * density + e * 0.9, 0, 1) * 170
            pygame.surfarray.pixels3d(sf)[:] = 255
            pygame.surfarray.pixels_alpha(sf)[:] = a.T.astype(np.uint8)
        rnd = random.Random(seed)
        for _ in range(int(w * h / 2600 * density)):
            ice_crystal(sf, rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(2.5, 6), (255, 255, 255, 220))
        return sf
    return cached(("frost", w, h, seed, density), make)


def cardboard(w, h, seed=5, col=(196, 156, 104)):
    """Corrugated cardboard: warm noise with faint fibre streaks."""
    def make():
        sf = gfx.texture(w, h, col, 14, 12, seed, 3).copy()
        rnd = random.Random(seed)
        for _ in range(int(w * h / 900)):
            x, y = rnd.uniform(0, w), rnd.uniform(0, h)
            ln = rnd.uniform(4, 12)
            c = mix(col, (90, 60, 30), rnd.uniform(0.1, 0.25))
            pygame.draw.aaline(sf, c, (x, y), (x + ln, y + rnd.uniform(-1.5, 1.5)))
        return sf
    return cached(("card", w, h, seed, col), make)


def cap_sprite(r, col, label="", hot=False, size=9):
    """A 1.5 mL tube seen from above: the closed lid (shaded polypropylene, a raised lip, a
    recessed centre), its hinge and a label written on the lid with a marker."""
    def make():
        S = 3
        n = 2 * r + 16
        N = n * S
        big = pygame.Surface((N, N), pygame.SRCALPHA)
        cx = cy = N / 2.0
        R_ = r * S
        if np is not None:
            yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
            dx, dy = xx - cx, yy - cy
            d = np.sqrt(dx * dx + dy * dy) / R_
            lit = -(dx + dy) / (R_ * 1.414)                       # light from the upper left
            shade = 1.02 + 0.10 * lit - 0.12 * d ** 2
            lip = (d > 0.78) & (d <= 1.0)
            shade = np.where(lip, 0.96 + 0.22 * lit * np.clip((d - 0.78) / 0.22, 0, 1) - 0.08, shade)
            recess = d < 0.58
            shade = np.where(recess, 0.93 - 0.06 * lit + 0.04 * (1 - d / 0.58), shade)
            ring = np.abs(d - 0.58) < 0.035
            shade = np.where(ring, shade - 0.12, shade)
            spec = np.exp(-(((dx + 0.42 * R_) / (0.22 * R_)) ** 2 + ((dy + 0.5 * R_) / (0.12 * R_)) ** 2)) * 0.5
            rgb = np.clip(np.array(col[:3], dtype=np.float32)[None, None, :] * shade[..., None] + spec[..., None] * 255, 0, 255)
            alpha = np.clip((1.0 - d) * R_ / S + 0.5, 0, 1) * 255
            # hinge strap and tab to the right
            tab = (dx > R_ * 0.82) & (dx < R_ * 1.32) & (np.abs(dy) < R_ * 0.32)
            rgb = np.where(tab[..., None], np.array(col[:3], dtype=np.float32)[None, None, :] * (0.82 + 0.1 * (dy < 0))[..., None], rgb)
            alpha = np.where(tab, 255, alpha)
            pygame.surfarray.pixels3d(big)[:] = rgb.astype(np.uint8).transpose(1, 0, 2)
            pygame.surfarray.pixels_alpha(big)[:] = alpha.astype(np.uint8).T
        else:
            pygame.draw.circle(big, col, (int(cx), int(cy)), R_)
        sf = pygame.transform.smoothscale(big, (n, n))
        out = pygame.Surface((n + 6, n + 6), pygame.SRCALPHA)
        sh = R.soft_shadow(2 * r, 2 * r, r, (30, 20, 10), 110, 3)
        out.blit(sh, (n // 2 - r - 6 + 2, n // 2 - r - 6 + 3))
        out.blit(sf, (0, 0))
        if label:
            ink = (20, 24, 60) if sum(col[:3]) > 330 else (250, 250, 246)
            ang = (hash(label) % 9 - 4) * 1.5
            t = marker_text(label, size + 5, ink, ang, max_w=int(1.7 * r))
            out.blit(t, (n // 2 - t.get_width() // 2, n // 2 - t.get_height() // 2))
        return out
    return cached(("cap", r, tuple(col), label, hot, size), make)


def pipette_tip(s, tip, col=(250, 246, 210), length=46, liquid=None):
    """A disposable tip (clear or yellow polypropylene) used as a cursor; no outline, just shading."""
    x, y = tip
    pts = [(x, y), (x - 5, y - length), (x + 5, y - length)]
    R.aa_poly(s, mix(col, (200, 200, 190), 0.25), pts, 0, None)
    R.aa_poly(s, mix(col, WHITE, 0.35), [(x, y), (x - 1.5, y - length), (x + 1.5, y - length)], 0, None)
    if liquid is not None:
        R.aa_poly(s, liquid, [(x, y), (x - 1.6, y - length * 0.3), (x + 1.6, y - length * 0.3)], 0, None)
    R.aa_line(s, mix(col, (90, 90, 80), 0.55), pts[0], pts[1], 1)
    R.aa_line(s, mix(col, (90, 90, 80), 0.55), pts[0], pts[2], 1)
    collar = pygame.Rect(x - 7, y - length - 8, 14, 9)
    s.blit(real.plastic(collar.w, collar.h, mix(col, (180, 180, 170), 0.2), 3, 0.3), collar.topleft)


def cable(s, a, b, col=(40, 40, 46), sag=40, w=5):
    """A sagging silicone lead from a to b, shaded as a round cable with a soft shadow."""
    mx, my = (a[0] + b[0]) / 2.0, max(a[1], b[1]) + sag
    pts = []
    for k in range(31):
        t = k / 30.0
        x = (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * mx + t * t * b[0]
        y = (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * my + t * t * b[1]
        pts.append((x, y))
    dark = mix(col, (0, 0, 0), 0.45)
    for p, q in zip(pts, pts[1:]):
        R.aa_line(s, dark, p, q, w + 1)
    for p, q in zip(pts, pts[1:]):
        R.aa_line(s, col, (p[0] - 0.5, p[1] - 0.5), (q[0] - 0.5, q[1] - 0.5), max(1, w - 1))
    pygame.draw.aalines(s, mix(col, WHITE, 0.55), False, [(x - 1, y - w * 0.3) for x, y in pts])


def agarose_slab(w, h, col=AGAROSE, seed=41):
    """Translucent agarose seen from above, with a soft sheen."""
    def make():
        sf = gfx.texture(w, h, col, 34, 5, seed, 2).copy()
        sh = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(0, w + h, 2):
            a = int(26 * max(0.0, math.sin(i / float(w + h) * math.pi * 3)) ** 3)
            if a:
                pygame.draw.line(sh, (255, 255, 255, a), (i, 0), (i - h, h), 2)
        sf.blit(sh, (0, 0))
        return sf
    return cached(("agar", w, h, col, seed), make)


def well(s, r, fill=0.0, col=DYE, uv=False):
    """A well punched by the comb, seen from above: a dark slot with a lit lower lip."""
    r = pygame.Rect(r)
    base = (34, 30, 48) if uv else mix(AGAROSE, (60, 70, 80), 0.45)
    gfx.rrect(s, r, base, None, 0, 2, -0.25, False)
    pygame.draw.line(s, mix(base, (0, 0, 0), 0.35), (r.x + 1, r.y), (r.right - 2, r.y), 2)
    pygame.draw.line(s, mix(base, WHITE, 0.45), (r.x + 2, r.bottom - 1), (r.right - 3, r.bottom - 1), 1)
    if fill > 0:
        f = r.inflate(-2, -2)
        f.h = max(2, int(f.h * min(1.0, fill)))
        f.bottom = r.bottom - 1
        gfx.rrect(s, f, col, None, 0, 2, 0.2, False)


def tank_static(g, terminals_left=True):
    """Horizontal electrophoresis tank around the gel rect g (top view): a clear acrylic box full of
    TAE buffer, a UV-transparent gel tray, platinum wire electrodes along both ends and the
    black (-) and red (+) sockets. Returns (surface, tank rect)."""
    t = g.inflate(90, 60)

    def make():
        sf = pygame.Surface(t.size, pygame.SRCALPHA)
        o = pygame.Rect(0, 0, t.w, t.h)
        # buffer seen through the floor of the tank: slightly blue, darker towards the walls
        buf = pygame.Surface(o.size, pygame.SRCALPHA)
        if np is not None:
            yy, xx = np.mgrid[0:o.h, 0:o.w].astype(np.float32)
            edge = np.minimum(np.minimum(xx, o.w - 1 - xx), np.minimum(yy, o.h - 1 - yy))
            v = 0.86 + 0.14 * np.clip(edge / 40.0, 0, 1)
            base = np.array((186, 208, 220), np.float32)
            rgb = np.clip(base[None, None, :] * v[..., None] + (R.value_noise(o.w, o.h, 50, 61, 2)[..., None] - 0.5) * 6, 0, 255)
            pygame.surfarray.pixels3d(buf)[:] = rgb.astype(np.uint8).transpose(1, 0, 2)
            pygame.surfarray.pixels_alpha(buf)[:] = 255
        else:
            buf.fill((186, 208, 220))
        m = R.rrect_surf(o.w, o.h, (255, 255, 255), None, 0, 14, 0, False)
        buf.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        sf.blit(buf, (0, 0))
        # acrylic walls: thick clear rim with bright inner and outer edges
        sf.blit(real.glass(o.w, o.h, (226, 240, 246), 90, 14), (0, 0))
        inner = o.inflate(-16, -16)
        sf.blit(R.rrect_surf(inner.w, inner.h, None, (120, 150, 164, 150), 1, 10, 0, False), inner.topleft)
        sf.blit(R.rrect_surf(inner.w - 2, inner.h - 2, None, (255, 255, 255, 120), 1, 9, 0, False), (inner.x + 1, inner.y + 1))
        # gel tray with its raised side rails
        tray = pygame.Rect(g.x - t.x - 10, g.y - t.y - 8, g.w + 20, g.h + 16)
        sf.blit(real.glass(tray.w, tray.h, (236, 244, 248), 70, 6), tray.topleft)
        for x in (tray.x + 2, tray.right - 8):
            sf.blit(real.plastic(6, tray.h - 4, (214, 226, 232), 3, 0.4), (x, tray.y + 2))
        # platinum electrodes: a thin bright wire along each end
        for y in (inner.y + 10, inner.bottom - 10):
            pygame.draw.line(sf, (120, 124, 132), (inner.x + 12, y + 1), (inner.right - 12, y + 1), 2)
            pygame.draw.line(sf, (236, 238, 242), (inner.x + 12, y), (inner.right - 12, y), 1)
        tx = 17 if terminals_left else t.w - 17
        jack(sf, (tx, inner.y + 10), 11, (34, 34, 38))
        jack(sf, (tx, inner.bottom - 10), 11, (200, 40, 36))
        return sf
    return cached(("tank", g.x, g.y, g.w, g.h, terminals_left), make), t


def draw_tank(s, g, terminals_left=True):
    sf, t = tank_static(g, terminals_left)
    gfx.shadow(s, t, 14, (3, 6), 60, 8)
    s.blit(sf, t.topleft)
    return t


def tank_terminals(g, terminals_left=True):
    """Centres of the (black -, red +) terminals of the tank around gel rect g."""
    t = g.inflate(90, 60)
    tx = t.x + (17 if terminals_left else t.w - 17)
    return (tx, t.y + 18), (tx, t.bottom - 18)


def buffer_over(s, g, t):
    """Buffer covering the gel: a light blue film with a slowly drifting sheen."""
    gfx.alpha_rect(s, g, BUFFER, 28, 4)
    sheen = cached(("sheen", g.w, g.h), lambda: _sheen(g.w, g.h))
    x = ((t * 0.35) % (g.w + 400)) - 200
    clip = s.get_clip()
    s.set_clip(g)
    s.blit(sheen, (g.x + x - 100, g.y))
    s.set_clip(clip)


def _sheen(w, h):
    sf = pygame.Surface((220, h), pygame.SRCALPHA)
    R.aa_poly(sf, (255, 255, 255, 30), [(140, 0), (210, 0), (70, h), (0, h)], 0, None)
    R.aa_poly(sf, (255, 255, 255, 22), [(110, 0), (124, 0), (-16, h), (-30, h)], 0, None)
    return sf


def electrode_bubbles(s, g, t):
    """Gas bubbles at the electrodes while current runs (twice as many at the cathode: 2 H2 per O2)."""
    inner = g.inflate(90, 60).inflate(-16, -16)
    for i in range(36):
        x = inner.x + 16 + (i * 37) % (inner.w - 32)
        for y0, every in ((inner.y + 10, 1), (inner.bottom - 10, 2)):
            if i % every:
                continue
            yy = y0 - ((t * 0.6 + i * 13) % 10) + 4
            pygame.draw.circle(s, (250, 252, 255), (int(x), int(yy)), 2)
            pygame.draw.circle(s, mix(BUFFER, INK, 0.4), (int(x), int(yy)), 2, 1)


def _band_sprite(w, strength, col):
    w = max(6, int(w))
    k = round(clamp(strength, 0, 1.5), 1)

    def make():
        pad = 10
        sf = pygame.Surface((w + 2 * pad, 2 * pad + 6))
        sf.fill((0, 0, 0))
        if np is not None:
            ww, hh = sf.get_size()
            yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
            dy = (yy - hh / 2.0) / 3.2
            ex = np.clip(np.minimum(xx - pad + 2, ww - pad + 2 - xx) / 4.0, 0, 1)
            core = np.exp(-dy ** 2) * ex
            halo = np.exp(-(dy / 3.0) ** 2) * np.clip(np.minimum(xx, ww - xx) / pad, 0, 1) * 0.35
            a = np.clip((core + halo) * k, 0, 1.4)
            arr = np.zeros((hh, ww, 3), dtype=np.float32)
            for i in range(3):
                arr[..., i] = col[i] * a + 255 * np.clip(core * k - 0.8, 0, 1) * 0.6
            pygame.surfarray.blit_array(sf, np.clip(arr, 0, 255).astype(np.uint8).transpose(1, 0, 2))
        return sf
    return cached(("band", w, k, col), make)


def uv_band(s, cx, y, w, strength=1.0, col=UV_GLOW):
    """A stained band glowing under UV (additive, for dark backgrounds)."""
    if strength <= 0.02:
        return
    sp = _band_sprite(w, strength, col)
    s.blit(sp, (int(cx - sp.get_width() / 2), int(y - sp.get_height() / 2)), special_flags=pygame.BLEND_ADD)


def uv_gel(s, g, label=True):
    """The gel lying on a UV transilluminator: violet-lit filter glass in a dark housing."""
    def make():
        sf = pygame.Surface((g.w + 40, g.h + 40), pygame.SRCALPHA)
        o = pygame.Rect(0, 0, g.w + 40, g.h + 40)
        sf.blit(real.plastic(o.w, o.h, (46, 48, 56), 12, 0.15), (0, 0))
        screen = o.inflate(-16, -16)
        glow = pygame.Surface(screen.size)
        glow.fill((26, 12, 50))
        gfx.glow(glow, (screen.w // 2, screen.h // 2), max(screen.w, screen.h) * 0.75, (70, 30, 130), 1.0)
        sf.blit(glow, screen.topleft)
        gel = gfx.texture(g.w, g.h, (36, 20, 60), 30, 5, 43, 2)
        sf.blit(gel, (20, 20))
        pygame.draw.rect(sf, (90, 66, 140), (20, 20, g.w, g.h), 1, border_radius=3)
        pygame.draw.line(sf, (130, 110, 180), (21, 21), (20 + g.w - 2, 21), 1)
        return sf
    s.blit(cached(("uvgel", g.w, g.h), make), (g.x - 20, g.y - 20))
    if label:
        draw_text(s, "UV transilluminator  302 nm", (g.right - 6, g.bottom - 20), 12, (190, 170, 236), right=True, bold=True)


def gel_picture(s, rect, lanes, ladder=LADDER_1KB, uv=True, labels=True, lane_names=None, span=(10000, 80)):
    """Draw a stained gel. uv=True: a gel-documentation photo (black background, white bands, as
    printed from the imager); uv=False: the unstained gel with blue loading-dye bands.
    lanes: list of lists of band sizes (lane 0 is usually the ladder). Band position is
    logarithmic in size between span[0] (top) and span[1] (bottom)."""
    rect = pygame.Rect(rect)
    lab_w = 64 if labels else 0
    g = pygame.Rect(rect.x + lab_w, rect.y + 22, rect.w - lab_w, rect.h - 28)
    if uv:
        s.blit(_imager_gel(g.w + 10, g.h + 10), (g.x - 5, g.y - 5))
    else:
        s.blit(agarose_slab(g.w, g.h), g.topleft)
        gfx.rrect(s, g, None, (150, 170, 180), 1, 6)
    n = len(lanes)
    gap = g.w / (n + 0.5)
    ww = min(42, gap * 0.7)
    top = g.y + 22
    hgt = g.h - 34
    hi, lo = math.log10(span[0]), math.log10(span[1])

    def ypos(size):
        return top + (hi - math.log10(size)) / (hi - lo) * hgt

    for i, bands in enumerate(lanes):
        cx = g.x + gap * (i + 0.75)
        if uv:
            wr = pygame.Rect(int(cx - ww / 2), g.y + 8, int(ww), 7)
            pygame.draw.rect(s, (52, 52, 56), wr, border_radius=1)
            pygame.draw.rect(s, (12, 12, 14), wr.inflate(-2, -2), border_radius=1)
        else:
            well(s, (cx - ww / 2, g.y + 8, ww, 8), uv=False)
        if lane_names:
            draw_text(s, lane_names[i], (cx, rect.y), 13, INK_SOFT, center=True, bold=True)
        for b in bands:
            sz, st = (b if isinstance(b, tuple) else (b, 1.0))
            y = ypos(sz)
            if y < g.bottom - 4:
                if uv:
                    uv_band(s, cx, y, ww, st, (235, 235, 230))
                else:
                    gfx.band(s, cx, y, ww, st, DYE)
        if i == 0 and labels:
            last = -99
            for sz in ladder:
                y = ypos(sz)
                if y < g.bottom - 4 and y - last > 12:
                    draw_text(s, fmt_bp(sz), (g.x - 12, y - 8), 13, INK, right=True)
                    last = y
    return g


def power_supply(s, rect, volts, minutes, on, t=0):
    """Electrophoresis power supply (moulded grey housing, dark front panel, LCD, membrane keys,
    LED and red/black output sockets). Returns (black, red) socket centres."""
    r = pygame.Rect(rect)
    s.blit(R.soft_shadow(r.w, r.h, 12, (10, 10, 20), 90, 8), (r.x - 16 + 4, r.y - 16 + 8))
    s.blit(real.plastic(r.w, r.h, (198, 202, 208), 12, 0.3), r.topleft)
    face = r.inflate(-14, -14)
    s.blit(real.plastic(face.w, face.h, (64, 70, 82), 8, 0.12), face.topleft)
    draw_text(s, "PowerPac 300", (face.x + 10, face.y + 6), 11, (214, 220, 230), bold=True)
    scr = pygame.Rect(face.x + 10, face.y + 22, face.w - 20, 56)
    gfx.screen_rect(s, scr, (40, 56, 46) if on else (34, 40, 38))
    on_col = (170, 255, 190) if on else (70, 96, 82)
    draw_text(s, "%3d V" % volts, (scr.right - 10, scr.y + 5), 19, on_col, right=True, bold=True, mono=True)
    draw_text(s, "%02d:%02d" % (int(minutes), int(minutes * 60) % 60), (scr.right - 10, scr.y + 29), 17, on_col, right=True, bold=True, mono=True)
    for k, lab in enumerate(("V", "mA", "min")):
        kr = pygame.Rect(face.x + 10 + k * 34, scr.bottom + 8, 30, 16)
        s.blit(real.plastic(kr.w, kr.h, (96, 104, 118), 4, 0.3), kr.topleft)
        draw_text(s, lab, kr.center, 10, (226, 230, 236), center=True, bold=True, vcenter=True)
    gfx.led(s, (face.right - 22, scr.bottom + 16), (90, 230, 120), on and (t // 30) % 2 == 0, 4)
    jb, jr = (r.x + r.w * 0.33, r.bottom - 24), (r.x + r.w * 0.67, r.bottom - 24)
    jack(s, jb, 11, (34, 34, 38))
    jack(s, jr, 11, (200, 40, 36))
    return jb, jr


def water_bath(s, rect, t, temp="42.0"):
    """Digital water bath, front view: stainless tank, rippling water, control strip with a red
    LED display. Returns the water rect."""
    r = pygame.Rect(rect)
    s.blit(R.soft_shadow(r.w, r.h, 12, (10, 10, 20), 90, 8), (r.x - 16 + 4, r.y - 16 + 8))
    gfx.metal_rect(s, r, (206, 210, 216), 10)
    water = pygame.Rect(r.x + 14, r.y + 34, r.w - 28, r.h - 78)

    def make():
        sf = pygame.Surface(water.size, pygame.SRCALPHA)
        sf.blit(R.vgrad(water.size, (166, 206, 222), (78, 130, 160)), (0, 0))
        # the stainless inner wall shows through near the top
        sf.blit(R.vgrad((water.w, 10), (150, 156, 164), (120, 150, 166)), (0, 0))
        pygame.draw.rect(sf, (110, 116, 124), sf.get_rect(), 2)
        rack = pygame.Surface(water.size, pygame.SRCALPHA)
        for x in range(10, water.w - 10, 22):
            pygame.draw.line(rack, (200, 210, 216, 70), (x, water.h * 0.55), (x, water.h - 6), 2)
        pygame.draw.line(rack, (200, 210, 216, 80), (8, water.h * 0.55), (water.w - 8, water.h * 0.55), 2)
        sf.blit(rack, (0, 0))
        return sf
    s.blit(cached(("bathw", water.w, water.h), make), water.topleft)
    for k in range(4):
        y = water.y + 30 + k * (water.h - 34) / 4.0
        pts = [(water.x + 6 + i * 8, y + math.sin(i * 0.7 + t * 0.06 + k) * 1.6) for i in range((water.w - 12) // 8)]
        if len(pts) > 1:
            pygame.draw.aalines(s, (190, 226, 240), False, pts)
    pts = [(water.x + i * 6, water.y + 8 + math.sin(i * 0.5 + t * 0.1) * 2.0) for i in range(water.w // 6 + 1)]
    pygame.draw.lines(s, (226, 242, 250), False, pts, 2)
    pan = pygame.Rect(r.x + 14, r.bottom - 38, r.w - 28, 28)
    s.blit(real.plastic(pan.w, pan.h, (54, 58, 66), 5, 0.12), pan.topleft)
    scr = pygame.Rect(pan.x + 4, pan.y + 3, 104, pan.h - 6)
    gfx.screen_rect(s, scr, (30, 12, 10))
    draw_text(s, temp + " deg C", scr.center, 14, (255, 90, 60), center=True, bold=True, mono=True, vcenter=True)
    gfx.led(s, (pan.right - 14, pan.centery), (255, 150, 60), (t // 40) % 2 == 0, 4)
    for k in range(2):
        kr = pygame.Rect(pan.right - 70 + k * 24, pan.y + 6, 20, 16)
        s.blit(real.plastic(kr.w, kr.h, (90, 96, 108), 4, 0.3), kr.topleft)
        draw_text(s, "+" if k else "-", kr.center, 12, WHITE, center=True, bold=True, vcenter=True)
    return water


def ice_bucket(s, rect):
    """A blue polyethylene ice bucket heaped with crushed ice."""
    r = pygame.Rect(rect)

    def make():
        S = 2
        W2, H2 = (r.w + 20) * S, (r.h + 34) * S
        big = pygame.Surface((W2, H2), pygame.SRCALPHA)
        body = [(10 * S, 34 * S), ((r.w + 10) * S, 34 * S), ((r.w - 6) * S, (r.h + 30) * S), (26 * S, (r.h + 30) * S)]
        mask = pygame.Surface((W2, H2), pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255), body)
        prof = np.ones(W2, np.float32)
        if np is not None:
            prof[10 * S:(r.w + 10) * S] = real.cyl_profile(r.w * S, 0.25, 0.1, 0.12, 0.74)
        big.blit(real.shaded_mask(mask, (52, 104, 186), prof, 255), (0, 0))
        rnd = random.Random(7)
        for k in range(110):
            x = rnd.uniform(14, r.w + 6)
            dome = 14 * math.sin(min(1.0, max(0.0, (x - 10) / r.w)) * math.pi)
            y = 30 - dome * rnd.uniform(0.3, 1.0) + rnd.uniform(-3, 6)
            sz = rnd.uniform(4, 10)
            pts = [((x + math.cos(a) * sz * rnd.uniform(0.6, 1.0)) * S, (y + math.sin(a) * sz * rnd.uniform(0.5, 0.9)) * S)
                   for a in [i * math.tau / 6 + rnd.uniform(-0.3, 0.3) for i in range(6)]]
            shade = rnd.randint(196, 236)
            pygame.draw.polygon(big, (shade - 30, shade - 12, shade, 235), pts)
            pygame.draw.polygon(big, (shade, shade + 8 if shade < 247 else 255, 255, 220), pts[:4])
            pygame.draw.line(big, (255, 255, 255, 240), pts[0], pts[1], S)
        rim = pygame.Rect(6 * S, 30 * S, (r.w + 8) * S, 9 * S)
        rm = pygame.Surface(rim.size, pygame.SRCALPHA)
        pygame.draw.rect(rm, (255, 255, 255, 255), rm.get_rect(), border_radius=4 * S)
        big.blit(real.shaded_mask(rm, (72, 128, 206), real.cyl_profile(rim.w, 0.25, 0.1, 0.12, 0.78), 255), rim.topleft)
        return pygame.transform.smoothscale(big, (r.w + 20, r.h + 34))
    s.blit(R.soft_shadow(r.w, 14, 7, (10, 10, 20), 90, 6), (r.x - 12, r.bottom - 14))
    s.blit(cached(("ice", r.w, r.h), make), (r.x - 10, r.y - 34))


def stopwatch(s, c, rad, sec, zone=(40, 50)):
    """A mechanical stopwatch: chrome case and crown, white dial, minute track, target zone, hand."""
    x, y = c
    crown = pygame.Rect(x - 7, y - rad - 20, 14, 12)
    s.blit(real.steel(crown.w, crown.h, 3), crown.topleft)
    s.blit(real.steel(8, 8, 2), (x - 4, y - rad - 10))
    s.blit(R.soft_shadow(2 * rad + 16, 2 * rad + 16, rad + 8, (10, 10, 20), 90, 8), (x - rad - 24 + 4, y - rad - 24 + 8))
    s.blit(_chrome_ring(rad + 9, 10), (x - rad - 9, y - rad - 9))
    gfx.circle(s, (250, 250, 246), c, rad, 0, None, False)
    z0, z1 = zone
    pts = [c]
    for k in range(int(z0 * 2), int(z1 * 2) + 1):
        a = k / 120.0 * math.tau - math.pi / 2
        pts.append((x + math.cos(a) * (rad - 6), y + math.sin(a) * (rad - 6)))
    R.aa_poly(s, (182, 230, 182), pts, 0, None)
    for k in range(60):
        a = k * math.tau / 60 - math.pi / 2
        l0 = rad - (10 if k % 5 == 0 else 5)
        gfx.line(s, (30, 30, 34) if k % 5 == 0 else (110, 110, 118), (x + math.cos(a) * l0, y + math.sin(a) * l0),
                 (x + math.cos(a) * (rad - 2), y + math.sin(a) * (rad - 2)), 2 if k % 5 == 0 else 1)
    for k in (0, 15, 30, 45):
        a = k / 60.0 * math.tau - math.pi / 2
        draw_text(s, str(k), (x + math.cos(a) * (rad - 22), y + math.sin(a) * (rad - 22)), 12, (40, 40, 46), center=True, bold=True, vcenter=True)
    a = sec / 60.0 * math.tau - math.pi / 2
    gfx.line(s, (200, 40, 30), (x - math.cos(a) * 10, y - math.sin(a) * 10), (x + math.cos(a) * (rad - 8), y + math.sin(a) * (rad - 8)), 2)
    gfx.circle(s, (200, 40, 30), c, 4, 0, None, False)
    gl = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
    pygame.draw.ellipse(gl, (255, 255, 255, 50), (rad * 0.3, rad * 0.12, rad * 1.0, rad * 0.55))
    s.blit(gl, (x - rad, y - rad))


def helix(s, x0, y, length, amp=8, period=34, cols=(CORAL, TURQ)):
    """A short stretch of double helix drawn sideways from x0, length pixels long."""
    n = max(8, int(length / 3))
    pa = [(x0 + i * length / n, y + math.sin(i * length / n / period * math.tau) * amp) for i in range(n + 1)]
    pb = [(x0 + i * length / n, y - math.sin(i * length / n / period * math.tau) * amp) for i in range(n + 1)]
    step = period / 6.0
    x = x0 + step / 2
    while x < x0 + length:
        ph = (x - x0) / period * math.tau
        ya, yb = y + math.sin(ph) * amp, y - math.sin(ph) * amp
        pygame.draw.line(s, mix(SAND, INK, 0.25), (x, ya), (x, yb), 2)
        x += step
    back, front = (pb, pa)
    pygame.draw.lines(s, INK, False, back, 6)
    pygame.draw.lines(s, mix(cols[1], WHITE, 0.25), False, back, 4)
    pygame.draw.lines(s, INK, False, front, 6)
    pygame.draw.lines(s, cols[0], False, front, 4)
    pygame.draw.aalines(s, mix(cols[0], WHITE, 0.5), False, [(px, py - 1) for px, py in front])


def metal_disc(r, base=(196, 200, 210)):
    """A spun-metal disc (centrifuge rotor): concentric brushing and a conic highlight."""
    def make():
        n = 2 * r + 4
        sf = pygame.Surface((n, n), pygame.SRCALPHA)
        if np is not None:
            yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
            dx, dy = xx - n / 2.0, yy - n / 2.0
            d = np.sqrt(dx * dx + dy * dy)
            th = np.arctan2(dy, dx)
            rng = np.random.default_rng(r)
            rings = rng.normal(0, 1, int(r) + 4)[np.clip(d.astype(int), 0, int(r) + 3)]
            v = 0.0 + 26 * np.cos(2 * (th + 0.6)) + 6 * rings - 14 * (d / r) ** 3
            v = np.where(d > r - 2.5, -150.0, v)
            rgb = np.clip(np.array(base, dtype=np.float32)[None, None, :] + v[..., None], 0, 255).astype(np.uint8)
            pygame.surfarray.pixels3d(sf)[:] = rgb.transpose(1, 0, 2)
            alpha = np.clip((r - d) * 1.5 + 0.5, 0, 1) * 255
            pygame.surfarray.pixels_alpha(sf)[:] = alpha.T.astype(np.uint8)
        else:
            pygame.draw.circle(sf, base, (n // 2, n // 2), r)
        return sf
    return cached(("disc", r, base), make)


# ------------------------------------------------------------------ plates and colonies
def colony_sprite(r, kind, seed=0):
    """A bacterial colony seen from above: a low glossy dome with an entire, slightly wavy edge.
    'blue' colonies on X-gal are opaque blue, darker in the centre; white ones are cream."""
    r = max(2, int(round(r)))

    def make():
        S = 3
        n = 2 * r + 8
        N = n * S
        big = pygame.Surface((N, N), pygame.SRCALPHA)
        c = N / 2.0
        if kind == "blue":
            base, edge, core = (78, 118, 196), (150, 176, 220), (34, 56, 128)
        else:
            base, edge, core = (240, 234, 212), (250, 246, 232), (214, 200, 166)
        if np is not None:
            rnd = np.random.default_rng(seed * 31 + r)
            yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
            dx, dy = xx - c, yy - c
            th = np.arctan2(dy, dx)
            wav = 1 + 0.05 * np.sin(th * 5 + rnd.uniform(0, 6)) + 0.03 * np.sin(th * 11 + rnd.uniform(0, 6))
            d = np.sqrt(dx * dx + dy * dy) / (r * S * wav)
            lit = -(dx + dy) / (r * S * 1.414)
            t = np.clip(d, 0, 1)
            colr = np.array(core, np.float32) * (1 - t[..., None]) ** 1.5 + np.array(base, np.float32) * (1 - (1 - t[..., None]) ** 1.5)
            colr = np.where((d > 0.82)[..., None], np.array(edge, np.float32), colr)
            shade = 1.0 + 0.10 * lit - 0.08 * d ** 2
            spec = np.exp(-(((dx + 0.38 * r * S) / (0.2 * r * S)) ** 2 + ((dy + 0.42 * r * S) / (0.13 * r * S)) ** 2)) * 0.6
            rgb = np.clip(colr * shade[..., None] + spec[..., None] * 255, 0, 255)
            alpha = np.clip((1 - d) * r * S / S * 1.2 + 0.4, 0, 1) * (235 if kind != "blue" else 250)
            pygame.surfarray.pixels3d(big)[:] = rgb.astype(np.uint8).transpose(1, 0, 2)
            pygame.surfarray.pixels_alpha(big)[:] = alpha.astype(np.uint8).T
        else:
            pygame.draw.circle(big, base, (int(c), int(c)), r * S)
        sp = pygame.transform.smoothscale(big, (n, n))
        out = pygame.Surface((n + 2, n + 2), pygame.SRCALPHA)
        out.blit(R.soft_shadow(2 * r, 2 * r, r, (60, 40, 10), 70, 2), (n // 2 - r - 4 + 1, n // 2 - r - 4 + 2))
        out.blit(sp, (0, 0))
        return out
    return cached(("col", r, kind, seed), make)


def colony(s, x, y, r, kind, seed=0):
    sp = colony_sprite(r, kind, seed)
    s.blit(sp, (int(x - sp.get_width() / 2), int(y - sp.get_height() / 2)))


def spreader(s, pos):
    """An L-shaped glass cell spreader (a 'hockey stick'): clear rod with bright edges."""
    x, y = pos
    foot = [(x - 42, y), (x + 40, y)]
    handle = [(x + 40, y), (x + 92, y - 128)]
    gfx.alpha_circle(s, NIGHT, (x + 4, y + 7), 28, 26)
    for a, b in (foot, handle):
        R.aa_line(s, (150, 170, 176), a, b, 8)
        R.aa_line(s, (214, 230, 234), a, b, 5)
        R.aa_line(s, (255, 255, 255), (a[0], a[1] - 2), (b[0], b[1] - 2), 1)
    gfx.alpha_circle(s, (214, 230, 234), (x + 40, y), 4, 255)


def toothpick(s, tip):
    """A wooden toothpick (birch), lighter on its lit side."""
    x, y = tip
    R.aa_line(s, (150, 112, 66), (x, y), (x + 32, y - 76), 5)
    R.aa_line(s, (222, 186, 132), (x - 0.5, y - 0.5), (x + 31.5, y - 76.5), 3)
    R.aa_line(s, (246, 222, 180), (x - 1, y - 2), (x + 30, y - 75), 1)


def magnifier(s, src_surface, focus, centre, rad, zoom=2.6):
    """A hand lens: chrome rim, black handle, the view enlarged and a glint on the glass."""
    cx, cy = centre
    grab = int(rad * 2 / zoom)
    src = pygame.Rect(0, 0, grab, grab)
    src.center = (int(focus[0]), int(focus[1]))
    src.clamp_ip(src_surface.get_rect())
    big = pygame.transform.smoothscale(src_surface.subsurface(src).copy(), (rad * 2, rad * 2))
    lens = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
    lens.blit(big, (0, 0))
    m = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
    m.blit(R._ellipse_surf(rad * 2 - 1, rad * 2 - 1, (255, 255, 255, 255), None, 0), (0, 0))
    lens.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    a, b = (cx + rad * 0.72, cy + rad * 0.72), (cx + rad * 1.3, cy + rad * 1.3)
    gfx.alpha_circle(s, NIGHT, (cx + 8, cy + 12), rad + 8, 50)
    R.aa_line(s, (20, 20, 24), a, b, 16)
    R.aa_line(s, (70, 70, 78), (a[0] - 2, a[1] - 2), (b[0] - 2, b[1] - 2), 5)
    s.blit(_chrome_ring(rad + 8, 8), (cx - rad - 8, cy - rad - 8))
    s.blit(lens, (cx - rad, cy - rad))
    gl = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
    pygame.draw.ellipse(gl, (255, 255, 255, 60), (rad * 0.25, rad * 0.18, rad * 0.9, rad * 0.5))
    gl.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    s.blit(gl, (cx - rad, cy - rad))


def ring_band(s, c, rad, width, col, a0=0.0, a1=math.tau, outline=INK, arrow=False):
    """A thick ring or arc (angles in radians, clockwise from 3 o'clock), optionally ending in an arrowhead."""
    S = 3
    pad = width + 12
    n = int(2 * (rad + pad))
    big = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
    cc = n * S / 2.0
    ro, ri = (rad + width / 2.0) * S, (rad - width / 2.0) * S
    steps = max(8, int(abs(a1 - a0) * rad / 4))
    end = a1 - (0.18 if arrow else 0.0)
    outer = [(cc + math.cos(a0 + (end - a0) * k / steps) * ro, cc + math.sin(a0 + (end - a0) * k / steps) * ro) for k in range(steps + 1)]
    inner = [(cc + math.cos(a0 + (end - a0) * k / steps) * ri, cc + math.sin(a0 + (end - a0) * k / steps) * ri) for k in range(steps + 1)]
    pts = outer + inner[::-1]
    if arrow:
        tip = (cc + math.cos(a1) * rad * S, cc + math.sin(a1) * rad * S)
        wo, wi = ro + width * 0.5 * S, ri - width * 0.5 * S
        head = [(cc + math.cos(end) * wo, cc + math.sin(end) * wo), tip, (cc + math.cos(end) * wi, cc + math.sin(end) * wi)]
        pts = outer + [head[0], head[1], head[2]] + inner[::-1]
    if outline:
        pygame.draw.polygon(big, outline, pts, 0)
        shrink = []
        for x, y in pts:
            dx, dy = x - cc, y - cc
            d = math.hypot(dx, dy) or 1
            k = 1 - 2.2 * S / d if d > (rad * S) else 1 + 2.2 * S / d
            shrink.append((cc + dx * k, cc + dy * k))
        pygame.draw.polygon(big, col, shrink, 0)
    else:
        pygame.draw.polygon(big, col, pts, 0)
    sp = pygame.transform.smoothscale(big, (n, n))
    s.blit(sp, (int(c[0] - n / 2), int(c[1] - n / 2)))


def plasmid(s, c, rad, features=(), label="", size_txt=""):
    """A plasmid map: backbone ring plus coloured feature arcs [(a0, a1, colour, name)]."""
    ring_band(s, c, rad, 6, (210, 216, 226))
    for a0, a1, col, name in features:
        ring_band(s, c, rad, 16, col, a0, a1, INK, arrow=True)
        am = (a0 + a1) / 2.0
        tx, ty = c[0] + math.cos(am) * (rad + 30), c[1] + math.sin(am) * (rad + 30)
        draw_text(s, name, (tx, ty), 13, mix(col, INK, 0.45), center=True, bold=True, vcenter=True)
    if label:
        draw_text(s, label, (c[0], c[1] - 10), 16, INK, center=True, bold=True, vcenter=True)
    if size_txt:
        draw_text(s, size_txt, (c[0], c[1] + 12), 13, INK_SOFT, center=True, vcenter=True)


def marker_font(size):
    """A handwriting face for labels written with a lab marker (falls back to the UI font)."""
    key = ("mfont", size)
    f = _cache.get(key)
    if f is None:
        path = None
        try:
            path = pygame.font.match_font(["inkfree", "segoeprint", "bradleyhand", "noteworthy", "comicsansms"], bold=True)
        except Exception:
            path = None
        f = pygame.font.Font(path, size) if path else core.font(size, True)
        _cache[key] = f
    return f


def marker_text(text, size, col=(28, 32, 70), angle=0.0, max_w=None):
    """Text as if written with a fine marker: handwriting face, slight tilt."""
    def make():
        t = marker_font(size).render(pretty(text), True, col)
        if max_w and t.get_width() > max_w:
            t = pygame.transform.smoothscale(t, (max_w, max(4, int(t.get_height() * max_w / t.get_width()))))
        if angle:
            t = pygame.transform.rotozoom(t, angle, 1.0)
        return t
    return cached(("mtext", text, size, col, round(angle, 1), max_w), make)


def _chrome_ring(R_, w):
    """A polished metal ring of outer radius R_ and width w (cached)."""
    def make():
        S = 3
        n = 2 * R_ + 2
        N = n * S
        big = pygame.Surface((N, N), pygame.SRCALPHA)
        if np is not None:
            yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
            dx, dy = xx - N / 2.0, yy - N / 2.0
            d = np.sqrt(dx * dx + dy * dy) / S
            th = np.arctan2(dy, dx)
            inside = (d <= R_) & (d >= R_ - w)
            v = 170 + 70 * np.cos(2 * (th + 0.8)) + 25 * np.cos((d - (R_ - w / 2.0)) / w * np.pi * 2)
            rgb = np.clip(np.stack([v, v + 3, v + 8], axis=2), 0, 255).astype(np.uint8)
            a = np.clip(np.minimum(R_ - d, d - (R_ - w)) * 2 + 0.5, 0, 1) * 255
            pygame.surfarray.pixels3d(big)[:] = rgb.transpose(1, 0, 2)
            pygame.surfarray.pixels_alpha(big)[:] = np.where(inside | (a > 0), a, 0).astype(np.uint8).T
        return pygame.transform.smoothscale(big, (n, n))
    return cached(("chrome", R_, w), make)


def _jack(r, col):
    """A banana socket seen from the front/top: shaded plastic collar around a metal hole."""
    def make():
        S = 3
        n = 2 * r + 6
        N = n * S
        big = pygame.Surface((N, N), pygame.SRCALPHA)
        if np is not None:
            yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
            dx, dy = xx - N / 2.0, yy - N / 2.0
            d = np.sqrt(dx * dx + dy * dy) / (r * S)
            lit = -(dx + dy) / (r * S * 1.414)
            shade = 1.0 + 0.25 * lit * np.clip(d, 0, 1) - 0.1 * d ** 2
            rgb = np.array(col, np.float32)[None, None, :] * shade[..., None]
            hole = d < 0.42
            rgb = np.where(hole[..., None], np.array((150, 150, 156), np.float32) * (0.6 + 0.4 * (d[..., None] / 0.42)), rgb)
            rgb = np.where((d < 0.22)[..., None], np.array((24, 24, 28), np.float32), rgb)
            spec = np.exp(-(((dx + 0.4 * r * S) / (0.22 * r * S)) ** 2 + ((dy + 0.45 * r * S) / (0.14 * r * S)) ** 2)) * 0.55
            rgb = np.clip(rgb + spec[..., None] * 255, 0, 255)
            a = np.clip((1 - d) * r * 1.5 + 0.5, 0, 1) * 255
            pygame.surfarray.pixels3d(big)[:] = rgb.astype(np.uint8).transpose(1, 0, 2)
            pygame.surfarray.pixels_alpha(big)[:] = a.astype(np.uint8).T
        return pygame.transform.smoothscale(big, (n, n))
    return cached(("jack", r, tuple(col)), make)


def jack(s, c, r, col):
    sp = _jack(int(r), col)
    s.blit(R.soft_shadow(2 * r, 2 * r, r, (10, 10, 20), 90, 3), (int(c[0]) - r - 6 + 2, int(c[1]) - r - 6 + 3))
    s.blit(sp, (int(c[0]) - sp.get_width() // 2, int(c[1]) - sp.get_height() // 2))


def _imager_gel(w, h, seed=43):
    """A gel-documentation photo background: black, a faintly lit gel, sensor noise."""
    def make():
        sf = pygame.Surface((w, h))
        if np is not None:
            rng = np.random.default_rng(seed)
            yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
            v = 22 + 10 * np.exp(-(((xx - w / 2) / (w * 0.7)) ** 2 + ((yy - h / 2) / (h * 0.8)) ** 2))
            v += rng.normal(0, 2.2, (h, w))
            v += (R.value_noise(w, h, 40, seed, 2) - 0.5) * 6
            arr = np.clip(np.stack([v, v, v + 1], axis=2), 0, 255).astype(np.uint8)
            pygame.surfarray.blit_array(sf, arr.transpose(1, 0, 2))
        else:
            sf.fill((26, 26, 28))
        return sf
    return cached(("imager", w, h, seed), make)


