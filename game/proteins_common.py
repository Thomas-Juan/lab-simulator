# -*- coding: utf-8 -*-
"""Drawing helpers shared by the Proteins wing: instruments, cables, antibodies, a magnifier,
note cards and a small surface cache."""
import math
import pygame
import gfx
import render as R
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, TEAL, LAV, VIOLET,
                  NIGHT, WHITE, GREEN, RED, YELLOW, BLUE, clamp, mix, lerp, draw_text, draw_wrapped, wrap)
from stage import TOP, BOTTOM

STEEL = (186, 192, 204)
BROMO = (58, 84, 200)          # bromophenol blue
COOM = (34, 52, 140)           # Coomassie-stained band
PINK = (226, 80, 150)
BUFFER = (206, 226, 240)       # running buffer
DARK = (46, 48, 62)            # instrument housings
SCREEN_TXT = (150, 255, 180)

_cache = {}


def cached(key, make):
    """Build a surface once with make() and keep it."""
    s = _cache.get(key)
    if s is None:
        if len(_cache) > 600:
            _cache.clear()
        s = _cache[key] = make()
    return s


def mmss(sec):
    sec = int(sec)
    return "%d:%02d" % (sec // 60, sec % 60)


def note_card(s, rect, title, text, col=SAND, size=14):
    """A small paper card with a coloured title tab."""
    rect = pygame.Rect(rect)
    gfx.card(s, rect, CARD, INK, 12)
    gfx.header(s, rect, col, 26, 12)
    draw_text(s, title, (rect.x + 14, rect.y + 15), 14, INK, bold=True, vcenter=True)
    draw_wrapped(s, text, (rect.x + 14, rect.y + 40), size, rect.w - 28, INK)


def screen_text(s, rect, txt, size=20, col=SCREEN_TXT):
    rect = pygame.Rect(rect)
    gfx.screen_rect(s, rect)
    draw_text(s, txt, rect.center, size, col, center=True, bold=True, mono=True, vcenter=True)


def wire(s, a, b, col=(30, 30, 36), sag=40, w=5):
    """A cable hanging between a and b (quadratic curve), ink outline."""
    mx, my = (a[0] + b[0]) / 2, max(a[1], b[1]) + sag
    pts = []
    for i in range(25):
        t = i / 24.0
        x = (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * mx + t * t * b[0]
        y = (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * my + t * t * b[1]
        pts.append((x, y))
    pygame.draw.lines(s, INK, False, pts, w + 3)
    pygame.draw.lines(s, col, False, pts, w)
    hl = R.lighten(col, 0.45)
    pygame.draw.lines(s, hl, False, [(x - 1, y - 1) for x, y in pts], 1)


def jack(s, c, col):
    gfx.circle(s, (40, 40, 46), c, 11, 2)
    gfx.circle(s, col, c, 7, 1)


def power_supply(s, rect, volts="200 V", on=True, t=0):
    """Electrophoresis power pack: painted case, display, LEDs and the two jacks. Returns jack centres."""
    r = pygame.Rect(rect)
    gfx.metal_rect(s, r, (210, 214, 222), 12)
    gfx.rrect(s, (r.x + 8, r.y + 8, r.w - 16, 22), (62, 70, 92), INK, 2, 6, 0.15)
    draw_text(s, "POWER PAC 300", (r.x + 18, r.y + 19), 11, (220, 226, 240), bold=True, vcenter=True)
    screen_text(s, (r.x + 14, r.y + 38, r.w - 28, 38), volts if on else "--- V", 21)
    gfx.led(s, (r.right - 26, r.y + 19), GREEN if on and (t // 20) % 2 else (90, 170, 100), on)
    jm = (r.x + 40, r.bottom - 22)
    jp = (r.right - 40, r.bottom - 22)
    jack(s, jm, (30, 30, 30))
    jack(s, jp, RED)
    draw_text(s, "-", (jm[0] + 18, jm[1] - 10), 16, INK, bold=True)
    draw_text(s, "+", (jp[0] - 28, jp[1] - 11), 16, RED, bold=True)
    return jm, jp


def antibody(s, base, up=True, col=TURQ, size=1.0, ang=0.0):
    """IgG as a Y: two arms and a stem, rounded, anti-aliased. base = end of the stem."""
    x, y = base
    d = -1 if up else 1
    k = size
    ca, sa = math.cos(ang), math.sin(ang)

    def P(dx, dy):
        return (x + dx * ca - dy * sa, y + dx * sa + dy * ca)
    fork = P(0, d * 17 * k)
    la = P(-11 * k, d * 31 * k)
    ra = P(11 * k, d * 31 * k)
    for a, b in ((P(0, 0), fork), (fork, la), (fork, ra)):
        gfx.line(s, INK, a, b, 7 * k + 1)
    for a, b in ((P(0, 0), fork), (fork, la), (fork, ra)):
        gfx.line(s, col, a, b, 4 * k)
    for p in (la, ra, P(0, 0)):
        gfx.circle(s, col, p, 2.6 * k + 1, 1, INK, False)
    gfx.line(s, R.lighten(col, 0.5), P(-1.2 * k, d * 2 * k), P(-1.2 * k, d * 14 * k), 1)


def magnifier(s, src, center, r, bg=(252, 250, 246)):
    """A round magnifier bubble joined to the point src by two tangent lines. Returns its clip rect."""
    cx, cy = center
    dx, dy = src[0] - cx, src[1] - cy
    dist = math.hypot(dx, dy) or 1
    base = math.atan2(dy, dx)
    off = math.asin(clamp(r / dist, -1, 1))
    for sgn in (-1, 1):
        a = base + sgn * (math.pi / 2 - off) * 0.9
        p = (cx + math.cos(a) * r, cy + math.sin(a) * r)
        gfx.line(s, mix(INK, WHITE, 0.4), p, src, 2)
    gfx.alpha_circle(s, (60, 40, 100), (cx + 6, cy + 9), r + 4, 50)
    gfx.circle(s, (232, 236, 244), center, r + 7, 2, INK, False)
    gfx.circle(s, bg, center, r, 2, mix(INK, WHITE, 0.3), False)
    pygame.draw.arc(s, WHITE, (cx - r + 10, cy - r + 10, 2 * r - 20, 2 * r - 20), 1.9, 2.8, 4)
    gfx.circle(s, (40, 40, 50), src, 5, 1)
    return pygame.Rect(cx - r, cy - r, 2 * r, 2 * r)


def bubbles_up(s, rect, t, n=10, col=WHITE, speed=1.4, a=170):
    """Electrolysis bubbles rising inside rect."""
    rect = pygame.Rect(rect)
    for i in range(n):
        x = rect.x + 6 + (i * 37.3) % max(1, rect.w - 12)
        y = rect.bottom - (t * speed + i * 23.7) % max(1, rect.h)
        rr = 1.5 + (i % 3) * 0.8
        gfx.alpha_circle(s, col, (x + math.sin(t * 0.1 + i) * 2, y), rr + 1, a)


def heat_shimmer(s, x, y, w, t, col=(255, 170, 120)):
    for i in range(5):
        xx = x + i * w / 5
        yy = y - (t * 0.8 + i * 23) % 60
        a = int(160 * (1 - ((t * 0.8 + i * 23) % 60) / 60.0))
        pts = [(xx + 6 * math.sin((yy + k * 4) / 7.0 + i), yy - k * 4) for k in range(6)]
        surf_line(s, col, pts, a)


def surf_line(s, col, pts, a):
    if len(pts) < 2 or a <= 0:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0 = int(min(xs)) - 3, int(min(ys)) - 3
    sf = pygame.Surface((int(max(xs) - x0) + 6, int(max(ys) - y0) + 6), pygame.SRCALPHA)
    pygame.draw.lines(sf, col + (a,), False, [(x - x0, y - y0) for x, y in pts], 2)
    s.blit(sf, (x0, y0))


def tank_glass(s, rect, r=10):
    """Outline of a clear plastic tank with two thin vertical highlights."""
    rect = pygame.Rect(rect)
    gfx.alpha_rect(s, (rect.x + 7, rect.y + 8, 4, rect.h - 16), WHITE, 150, 2)
    gfx.alpha_rect(s, (rect.x + 14, rect.y + 8, 2, rect.h - 16), WHITE, 100, 1)
    gfx.alpha_rect(s, (rect.right - 12, rect.y + 8, 3, rect.h - 16), WHITE, 110, 1)
    gfx.rrect(s, rect, None, INK, 2, r)


def ring_ellipse(s, fill, rect, border=INK, w=2):
    """Filled ellipse with a clean anti-aliased outline (supersampled, cached by size and colour)."""
    rect = pygame.Rect(rect)
    if rect.w < 4 or rect.h < 4:
        return
    key = ("ell", rect.w, rect.h, tuple(fill) if fill else None, tuple(border), w)

    def make():
        S = 3
        big = pygame.Surface((rect.w * S, rect.h * S), pygame.SRCALPHA)
        pygame.draw.ellipse(big, tuple(border) + (255,), big.get_rect())
        inner = big.get_rect().inflate(-2 * w * S, -2 * w * S)
        if fill is not None:
            pygame.draw.ellipse(big, tuple(fill) + (255,), inner)
        else:
            pygame.draw.ellipse(big, (0, 0, 0, 0), inner)
        return pygame.transform.smoothscale(big, rect.size)
    s.blit(cached(key, make), rect.topleft)


# =================================================================== realistic layer
import real  # noqa: E402

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None


def band_sprite(w, h, col, alpha=255, smile=0.0, fuzz=1.0, seed=0):
    """A gel band as a real scan shows it: soft Gaussian edges, slightly darker centre, a faint smile."""
    w, h = max(3, int(w)), max(2, int(h))
    key = ("band", w, h, tuple(col), int(alpha), round(smile, 2), round(fuzz, 2), seed)

    def make():
        pad = int(3 + 3 * fuzz)
        sw, sh = w + 2 * pad, h + 2 * pad + int(abs(smile) * 4) + 2
        sf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        if np is None:
            pygame.draw.rect(sf, tuple(col) + (alpha,), (pad, pad, w, h), border_radius=h // 2)
            return sf
        x = np.arange(sw, dtype=np.float32) - sw / 2
        y = np.arange(sh, dtype=np.float32)
        u = x / (w / 2)
        cy = pad + h / 2 + smile * 3 * (u ** 2)
        ax = np.clip(1.0 - np.maximum(0, np.abs(u) - 0.82) / (0.18 + 0.25 * fuzz), 0, 1) ** 1.5
        dy = (y[None, :] - cy[:, None]) / (h / 2 * (0.85 + 0.3 * fuzz))
        prof = np.exp(-dy ** 2 * 1.6)
        rng = np.random.default_rng(seed)
        grain = 1 + rng.normal(0, 0.05, (sw, sh)).astype(np.float32)
        a = np.clip(prof * ax[:, None] * grain * alpha, 0, 255).astype(np.uint8)
        pygame.surfarray.pixels3d(sf)[:] = np.array(col[:3], dtype=np.uint8)
        pygame.surfarray.pixels_alpha(sf)[:] = a
        return sf
    return cached(key, make)


def draw_band(s, cx, y, w, h, col, alpha=255, smile=0.0, fuzz=1.0, seed=0):
    sp = band_sprite(w, h, col, alpha, smile, fuzz, seed)
    s.blit(sp, (int(cx - sp.get_width() / 2), int(y - sp.get_height() / 2)))


def cable(s, a, b, col=(30, 30, 36), sag=40, w=5):
    """A rubber lead hanging between a and b: shaded body, no cartoon outline."""
    mx, my = (a[0] + b[0]) / 2, max(a[1], b[1]) + sag
    pts = []
    for i in range(31):
        t = i / 30.0
        x = (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * mx + t * t * b[0]
        y = (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * my + t * t * b[1]
        pts.append((x, y))
    sh = [(x + 3, y + 5) for x, y in pts]
    surf_line(s, (10, 10, 20), sh, 50)
    pygame.draw.lines(s, R.lighten(col, -0.45), False, pts, w + 2)
    pygame.draw.lines(s, col, False, pts, w)
    pygame.draw.lines(s, R.lighten(col, 0.4), False, [(x - 1, y - 1.5) for x, y in pts], max(1, w // 3))


def banana_plug(s, c, col):
    """A 4 mm safety plug seen from the side, top at c."""
    x, y = c
    gfx.plastic_rect(s, (x - 7, y, 14, 22), col, 4, 0.4)
    gfx.metal_rect(s, (x - 3, y + 21, 6, 8), (196, 198, 204), 2)


def power_pack(s, rect, volts="200 V", on=True, t=0):
    """Electrophoresis power supply: moulded grey case, red LED digits, keys and safety jacks.
    Returns the jack centres (black, red)."""
    r = pygame.Rect(rect)
    sh = real.contact_shadow(r.w, 14, 90)
    s.blit(sh, (r.x - 6, r.bottom - 12))
    gfx.plastic_rect(s, r, (214, 216, 220), 10, 0.3)
    gfx.plastic_rect(s, (r.x + 6, r.y + 6, r.w - 12, 24), (58, 66, 84), 6, 0.2)
    draw_text(s, "PowerPac", (r.x + 14, r.y + 18), 12, (226, 232, 244), bold=True, vcenter=True)
    disp = pygame.Rect(r.x + 12, r.y + 38, r.w - 24, 36)
    gfx.screen_rect(s, disp, (24, 10, 10))
    txt = volts if on else "  0 V"
    draw_text(s, txt, disp.center, 22, (255, 70, 50) if on else (110, 40, 34), center=True, bold=True, mono=True, vcenter=True)
    if on:
        gfx.alpha_rect(s, disp.inflate(-10, -12), (255, 60, 40), 22, 4)
    for i in range(3):
        gfx.plastic_rect(s, (r.x + 14 + i * 26, r.y + 80, 20, 12), (236, 236, 238), 3, 0.4)
    gfx.led(s, (r.right - 22, r.y + 86), GREEN, on and (t // 20) % 2 == 0, 4)
    jm = (r.x + 36, r.bottom - 20)
    jp = (r.right - 36, r.bottom - 20)
    for c, colr in ((jm, (36, 36, 40)), (jp, (200, 40, 40))):
        gfx.circle(s, colr, c, 10, 1, R.lighten(colr, -0.5))
        gfx.circle(s, (26, 26, 30), c, 4, 0, None, False)
    return jm, jp


def heat_block(s, rect, temp="95.0", t=0):
    """A dry block heater: cream housing, anodised aluminium block with wells, LCD. Returns well centres."""
    r = pygame.Rect(rect)
    sh = real.contact_shadow(r.w + 20, 18, 100)
    s.blit(sh, (r.x - 14, r.bottom - 14))
    gfx.plastic_rect(s, r, (232, 230, 222), 14, 0.25)
    blk = pygame.Rect(r.x + 16, r.y - 26, r.w - 32, 40)
    gfx.metal_rect(s, blk, (176, 182, 192), 6)
    wells = []
    for i in range(4):
        cx = blk.x + 40 + i * (blk.w - 80) / 3
        gfx.ellipse(s, (54, 58, 66), (cx - 16, blk.y + 8, 32, 14), 0)
        gfx.ellipse(s, (96, 100, 110), (cx - 16, blk.y + 8, 32, 6), 0)
        wells.append((cx, blk.y + 14))
    disp = pygame.Rect(r.x + 18, r.bottom - 54, 132, 36)
    gfx.screen_rect(s, disp, (30, 40, 34))
    draw_text(s, temp + " deg C", disp.center, 17, (150, 255, 170), center=True, bold=True, mono=True, vcenter=True)
    gfx.led(s, (r.right - 34, r.bottom - 36), RED, (t // 20) % 2 == 0, 5)
    draw_text(s, "HEAT", (r.right - 34, r.bottom - 22), 10, INK_SOFT, center=True, bold=True)
    for i in range(2):
        gfx.plastic_rect(s, (r.x + 166 + i * 30, r.bottom - 48, 22, 22), (200, 200, 196), 5, 0.4)
    return wells, blk


def mini_tank(s, tank, buffer_top, running=False, t=0, lid=True):
    """A clear vertical mini gel tank (front view): polycarbonate walls, running buffer, the green
    electrode core and a lid with leads. Returns the plug tops (black, red) if lid."""
    sh = real.contact_shadow(tank.w + 30, 20, 110)
    s.blit(sh, (tank.x - 20, tank.bottom - 16))
    buf = pygame.Rect(tank.x + 6, buffer_top, tank.w - 12, tank.bottom - buffer_top - 6)
    gfx.alpha_rect(s, buf, (198, 218, 232), 196, 6)
    gfx.alpha_rect(s, (buf.x, buf.y, buf.w, 3), WHITE, 120, 1)
    # green electrode core seen behind the cassette
    core = pygame.Rect(tank.x + 20, tank.y + 30, tank.w - 40, tank.h - 46)
    gfx.alpha_rect(s, (core.x, core.y, 18, core.h), (60, 150, 90), 200, 4)
    gfx.alpha_rect(s, (core.right - 18, core.y, 18, core.h), (60, 150, 90), 200, 4)
    gfx.alpha_rect(s, (core.x, core.bottom - 16, core.w, 16), (60, 150, 90), 200, 4)
    pygame.draw.line(s, (220, 222, 228), (core.x + 24, core.bottom - 22), (core.right - 24, core.bottom - 22), 1)
    return buf


def tank_front(s, tank, running=False, t=0):
    """Glass front of the tank and the lid with its plugs, drawn over the contents."""
    s.blit(real.glass(tank.w, tank.h, (220, 236, 244), 40, 10), tank.topleft)
    if running:
        bubbles_up(s, (tank.x + 24, tank.bottom - 70, tank.w - 48, 56), t, 14, a=150)
    lid = pygame.Rect(tank.x - 6, tank.y - 22, tank.w + 12, 26)
    gfx.plastic_rect(s, lid, (64, 150, 98), 8, 0.35)
    pm, pp = (lid.right - 84, lid.y - 16), (lid.right - 40, lid.y - 16)
    banana_plug(s, pm, (40, 40, 44))
    banana_plug(s, pp, (200, 40, 40))
    return pm, pp
