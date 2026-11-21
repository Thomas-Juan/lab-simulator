# -*- coding: utf-8 -*-
"""Realistic technique icons: a small picture of each technique's key object.

Each icon is painted once on a 144 x 144 design canvas in the style of real.py (shaded plastic,
glass and steel, soft contact shadows, no cartoon ink outlines), then scaled down and cached per
size. draw(s, key, c, size) returns False for keys it does not know, so gfx.icon can fall back."""
import math
import random
import pygame
import render as R
import real
from render import lighten

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

N = 144                       # design canvas (3x a 48 px icon)
_cache = {}
BASE = {"A": (40, 160, 70), "C": (40, 100, 215), "G": (36, 36, 40), "T": (214, 50, 50)}


# ------------------------------------------------------------------ painting helpers
def _canvas():
    return pygame.Surface((N, N), pygame.SRCALPHA)


def shadow(cv, cx, cy, w, h, a=80):
    sh = R.soft_shadow(int(w), int(h), max(1, int(h) // 2), (20, 18, 30), a, max(3, int(h) // 2))
    cv.blit(sh, (int(cx - sh.get_width() / 2), int(cy - sh.get_height() / 2)))


def cyl(cv, rect, col, r=8, alpha=255, spec=0.3, edge=0.6, rim=0.45, rimw=4):
    """A vertical cylinder-like part: shaded across its width, with a darker rim of its own colour."""
    rect = pygame.Rect(rect)
    if rect.w < 2 or rect.h < 2:
        return
    m = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=int(r))
    cv.blit(real.shaded_mask(m, col, real.cyl_profile(rect.w, spec, 0.09, 0.45, edge), alpha), rect.topleft)
    if rim:
        cv.blit(real.soft_edge(m, lighten(col, -rim), rimw), rect.topleft)


def polyshape(cv, pts, col, alpha=255, spec=0.3, edge=0.6, rim=0.45, rimw=4, profile=True):
    """A shaded polygon (shading across its bounding box width)."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0 = int(min(xs)), int(min(ys))
    w, h = int(max(xs)) - x0 + 1, int(max(ys)) - y0 + 1
    m = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(m, (255, 255, 255, 255), [(x - x0, y - y0) for x, y in pts])
    prof = real.cyl_profile(w, spec, 0.09, 0.45, edge) if profile else None
    cv.blit(real.shaded_mask(m, col, prof, alpha), (x0, y0))
    if rim:
        cv.blit(real.soft_edge(m, lighten(col, -rim), rimw), (x0, y0))


def panel(cv, rect, col, r=10, border=None, bw=3, shade=0.08):
    rect = pygame.Rect(rect)
    cv.blit(R.rrect_surf(rect.w, rect.h, tuple(col), tuple(border) if border else None, bw, r, shade, True), rect.topleft)


def ball(cv, c, r, col, rim=0.4, rimw=3):
    R.aa_circle(cv, col, c, r, rimw, lighten(col, -rim), True)


def blur_layer(layer, k=3):
    w, h = layer.get_size()
    small = pygame.transform.smoothscale(layer, (max(1, w // k), max(1, h // k)))
    return pygame.transform.smoothscale(small, (w, h))


def arc_band(cv, c, r_in, r_out, a0, a1, col, head=False):
    """A curved band from angle a0 to a1 (degrees, clockwise from 12 o'clock), optional arrowhead."""
    cx, cy = c
    steps = max(4, int(abs(a1 - a0) / 4))
    end = a1 - (8 if head else 0)
    outer, inner = [], []
    for i in range(steps + 1):
        a = math.radians(a0 + (end - a0) * i / steps)
        outer.append((cx + math.sin(a) * r_out, cy - math.cos(a) * r_out))
        inner.append((cx + math.sin(a) * r_in, cy - math.cos(a) * r_in))
    pts = outer + inner[::-1]
    pygame.draw.polygon(cv, col, pts)
    if head:
        ae, at = math.radians(end), math.radians(a1)
        rm = (r_in + r_out) / 2
        wdt = (r_out - r_in) * 0.9
        pygame.draw.polygon(cv, col, [(cx + math.sin(ae) * (rm + wdt), cy - math.cos(ae) * (rm + wdt)),
                                      (cx + math.sin(at) * rm, cy - math.cos(at) * rm),
                                      (cx + math.sin(ae) * (rm - wdt), cy - math.cos(ae) * (rm - wdt))])


def band_blob(cv, rect, col, a=220, k=3):
    """A soft-edged band (gel or blot), blurred so it reads as a stain, not a rectangle."""
    rect = pygame.Rect(rect)
    pad = 8
    layer = pygame.Surface((rect.w + 2 * pad, rect.h + 2 * pad), pygame.SRCALPHA)
    pygame.draw.ellipse(layer, tuple(col[:3]) + (a,), (pad, pad, rect.w, rect.h))
    pygame.draw.rect(layer, tuple(col[:3]) + (a,), (pad + rect.h // 2, pad, max(1, rect.w - rect.h), rect.h))
    cv.blit(blur_layer(layer, k), (rect.x - pad, rect.y - pad))


# ------------------------------------------------------------------ icons
def i_pcr(cv):
    shadow(cv, 72, 124, 122, 14, 90)
    # top face of the aluminium cooling block, with the wells the tubes sit in
    cv.blit(real.steel(124, 22, 6, (176, 182, 192)), (10, 78))
    for i in range(4):
        pygame.draw.ellipse(cv, (96, 100, 110), (17 + i * 29, 82, 24, 11))
    # a strip of four PCR tubes with attached caps
    for i in range(4):
        x = 18 + i * 29
        pts = [(x, 22), (x + 22, 22), (x + 22, 62), (x + 15, 100), (x + 7, 100), (x, 62)]
        polyshape(cv, pts, (210, 218, 218), 200, rim=0.55, rimw=4)
        liq = [(x + 2, 68), (x + 20, 68), (x + 20, 70), (x + 14, 98), (x + 8, 98), (x + 2, 70)]
        polyshape(cv, liq, (232, 104, 70), 245, rim=0.3, rimw=2)
        cyl(cv, (x - 2, 12, 26, 12), (226, 230, 228), 4, 245, rim=0.4, rimw=3)
    pygame.draw.rect(cv, (210, 214, 212), (20, 14, 106, 5))
    # front face of the block hides the tube bottoms
    cv.blit(real.steel(124, 32, 6, (146, 152, 164)), (10, 92))
    for x in range(22, 126, 14):
        pygame.draw.line(cv, (150, 154, 162), (x, 100), (x, 118), 2)


def i_gel(cv):
    shadow(cv, 72, 128, 124, 14, 80)
    panel(cv, (8, 12, 128, 118), (36, 30, 46), 12, None, 0, 0.12)
    panel(cv, (18, 22, 108, 98), (62, 46, 92), 6, None, 0, 0.1)
    for i in range(5):
        pygame.draw.rect(cv, (28, 22, 40), (24 + i * 20, 30, 14, 6), border_radius=2)
    bands = [[44, 58, 70, 84, 98], [62], [62, 88], [76], [62, 96]]
    for i, lane in enumerate(bands):
        cx = 31 + i * 20
        for y in lane:
            R.glow(cv, (cx, y), 14, (190, 90, 70), 0.9)
            pygame.draw.rect(cv, (255, 214, 180), (cx - 7, y - 2, 14, 5), border_radius=2)


def i_extract(cv):
    shadow(cv, 72, 132, 60, 10, 80)
    # silica spin column (seen through the collection tube)
    cyl(cv, (52, 40, 40, 58), (178, 206, 232), 6, 200, rim=0.4, rimw=3)
    pygame.draw.ellipse(cv, (250, 250, 248), (54, 86, 36, 9))
    pygame.draw.ellipse(cv, (170, 170, 160), (54, 86, 36, 9), 2)
    # 2 mL collection tube
    pts = [(42, 44), (102, 44), (102, 104), (80, 132), (64, 132), (42, 104)]
    polyshape(cv, pts, (210, 218, 218), 170, rim=0.58, rimw=4)
    polyshape(cv, [(46, 112), (98, 112), (80, 128), (64, 128)], (226, 214, 160), 200, rim=0.2, rimw=2)
    cyl(cv, (38, 40, 68, 9), (222, 226, 224), 3, 235, rim=0.4, rimw=3)
    # column collar and lid above the tube
    cyl(cv, (46, 18, 52, 24), (120, 170, 222), 5, 245, rim=0.45, rimw=3)
    cyl(cv, (44, 8, 56, 12), (100, 150, 210), 4, 250, rim=0.45, rimw=3)


def i_clone(cv):
    c = (72, 72)
    pygame.draw.circle(cv, (150, 156, 164), c, 50, 9)
    pygame.draw.circle(cv, (225, 228, 232), c, 47, 3)
    arc_band(cv, c, 41, 59, 200, 290, (60, 160, 90), True)     # resistance gene
    arc_band(cv, c, 41, 59, 20, 92, (236, 132, 50), True)      # insert
    arc_band(cv, c, 43, 57, 120, 165, (70, 120, 210), False)   # origin
    for a in (14, 98, 182):
        r = math.radians(a)
        pygame.draw.line(cv, (40, 40, 48), (c[0] + math.sin(r) * 36, c[1] - math.cos(r) * 36),
                         (c[0] + math.sin(r) * 64, c[1] - math.cos(r) * 64), 4)
    ball(cv, c, 14, (238, 240, 244), 0.25, 2)


def i_transform(cv):
    sp = real.petri_sprite(54, (222, 182, 104))
    shadow(cv, 76, 116, 110, 22, 70)
    cv.blit(sp, (72 - sp.get_width() // 2, 72 - sp.get_height() // 2))
    rnd = random.Random(5)
    spots = [(48, 50, 1), (90, 44, 0), (62, 82, 0), (98, 82, 1), (44, 96, 0), (76, 106, 0), (80, 62, 1), (104, 62, 0), (58, 62, 0), (92, 100, 1)]
    for x, y, blue in spots:
        r = rnd.randint(8, 11)
        col = (64, 104, 188) if blue else (246, 240, 224)
        ball(cv, (x, y), r, col, 0.35 if blue else 0.2, 2)


def i_sanger(cv):
    shadow(cv, 72, 126, 124, 12, 70)
    panel(cv, (8, 16, 128, 108), (252, 252, 250), 10, (150, 154, 160), 3, 0.03)
    seq = "ACGTTGCAG"
    for i, b in enumerate(seq):
        pygame.draw.rect(cv, BASE[b], (17 + i * 12.5, 24, 9, 9), border_radius=2)
    for i, b in enumerate(seq):
        cx = 22 + i * 12.5
        hgt = 46 + (i * 17) % 30
        pts = [(cx + dx, 112 - hgt * math.exp(-(dx / 5.5) ** 2)) for dx in range(-16, 17, 2)]
        pygame.draw.lines(cv, BASE[b], False, pts, 4)
    pygame.draw.line(cv, (180, 184, 190), (14, 113), (130, 113), 2)


def i_qpcr(cv):
    shadow(cv, 72, 134, 70, 8, 80)
    pygame.draw.rect(cv, (150, 154, 162), (64, 108, 16, 18))
    pygame.draw.ellipse(cv, (120, 124, 132), (42, 122, 60, 12))
    panel(cv, (6, 12, 132, 100), (40, 42, 50), 8, None, 0, 0.1)
    panel(cv, (13, 19, 118, 84), (252, 252, 250), 3, None, 0, 0.02)
    pygame.draw.line(cv, (160, 164, 170), (22, 26), (22, 96), 2)
    pygame.draw.line(cv, (160, 164, 170), (22, 96), (126, 96), 2)
    pygame.draw.line(cv, (226, 70, 60), (22, 70), (126, 70), 2)
    for k, col in enumerate(((220, 60, 50), (40, 110, 210), (50, 160, 80), (236, 150, 40))):
        mid = 52 + k * 13
        pts = [(x, 94 - 62 / (1 + math.exp(-(x - mid) / 6.0))) for x in range(24, 126, 3)]
        pygame.draw.lines(cv, col, False, pts, 4)


def i_sds(cv):
    shadow(cv, 72, 132, 110, 12, 80)
    cv.blit(real.glass(104, 120, (206, 222, 230), 90, 4), (20, 10))       # long back plate with ears
    panel(cv, (26, 30, 92, 98), (186, 204, 226), 2, None, 0, 0.05)        # gel
    for i in range(6):
        pygame.draw.rect(cv, (150, 166, 190), (30 + i * 15, 30, 10, 9))
    for k, y in enumerate(range(46, 120, 9)):                              # prestained ladder: the only bands visible during a run
        band_blob(cv, (30, y, 10, 3), (200, 60, 110) if k in (3, 6) else (40, 56, 140), 210, 2)
    pygame.draw.rect(cv, (100, 90, 200), (45, 104, 70, 3))                 # bromophenol blue dye front
    cv.blit(real.glass(92, 98, (214, 228, 234), 50, 2), (26, 30))          # short front plate
    pygame.draw.rect(cv, (80, 170, 90), (20, 126, 104, 6), border_radius=2)


def i_western(cv):
    shadow(cv, 76, 128, 112, 12, 80)
    pts = [(32, 14), (124, 14), (124, 126), (20, 126), (20, 26)]
    polyshape(cv, pts, (246, 245, 238), 255, profile=False, rim=0.42, rimw=4)
    for y in (32, 46, 62, 82, 104):                                        # prestained ladder
        pygame.draw.rect(cv, (60, 90, 190) if y != 62 else (220, 70, 90), (27, y, 10, 3), border_radius=1)
    lanes = [(54, 1.0), (54, 0.6), (80, 0.9), (54, 0.35), (80, 0.5)]
    for i, (y, k) in enumerate(lanes):
        band_blob(cv, (46 + i * 15, y - 3, 13, 7), (30, 30, 36), int(250 * k), 3)
        band_blob(cv, (46 + i * 15, 98, 13, 5), (30, 30, 36), 120, 3)


def i_elisa(cv):
    shadow(cv, 76, 122, 128, 18, 80)
    plate = [(6, 30), (132, 18), (138, 108), (12, 126)]
    polyshape(cv, plate, (230, 234, 236), 235, spec=0.2, edge=0.85, rim=0.3, rimw=3)
    pygame.draw.polygon(cv, (210, 214, 218), [(6, 30), (18, 29), (12, 40)])
    for row in range(3):
        for col in range(4):
            fx, fy = col / 3.0, row / 2.0
            x = 26 + col * 27 + row * 1.5
            y = 44 - col * 3 + row * 27
            k = (col + row) / 5.0
            fill = (int(240 + 10 * k), int(176 + 66 * k), int(30 + 150 * k))
            pygame.draw.ellipse(cv, (176, 182, 188), (x - 12, y - 10, 24, 20))
            pygame.draw.ellipse(cv, fill, (x - 10, y - 7, 20, 16))
            pygame.draw.ellipse(cv, lighten(fill, 0.45), (x - 6, y - 5, 8, 4))


def i_purify(cv):
    shadow(cv, 72, 134, 50, 8, 80)
    pygame.draw.rect(cv, (150, 154, 162), (18, 26, 6, 106))                # stand rod
    cv.blit(real.steel(36, 12, 3, (170, 174, 182)), (20, 34))              # clamp
    cyl(cv, (52, 8, 40, 108), (214, 232, 238), 6, 110, rim=0.35, rimw=3)    # glass column
    cyl(cv, (55, 22, 34, 34), (236, 226, 150), 6, 120, rim=0, rimw=0)       # buffer above the bed
    cyl(cv, (55, 56, 34, 46), (150, 206, 196), 4, 245, rim=0.35, rimw=2)    # Ni-NTA agarose: pale blue-green
    rnd = random.Random(3)
    for _ in range(40):
        x, y = rnd.randint(58, 86), rnd.randint(58, 99)
        pygame.draw.circle(cv, (180, 226, 220) if rnd.random() < 0.5 else (120, 180, 176), (x, y), 2)
    pygame.draw.rect(cv, (246, 246, 240), (55, 101, 34, 4))                 # frit
    polyshape(cv, [(54, 114), (90, 114), (76, 126), (68, 126)], (220, 234, 238), 200, rim=0.35, rimw=2)
    cyl(cv, (60, 116, 24, 6), (60, 110, 200), 2, 250, rim=0.4, rimw=2)      # stopcock
    ball(cv, (72, 136), 4, (110, 200, 130), 0.3, 1)
    cv.blit(real.glass(40, 108, (214, 232, 238), 30, 6), (52, 8))


def i_micro(cv):
    field = pygame.Surface((N, N))
    field.fill((4, 6, 10))
    rnd = random.Random(9)
    fib = pygame.Surface((N, N), pygame.SRCALPHA)
    for _ in range(26):
        x, y = rnd.uniform(14, 130), rnd.uniform(14, 130)
        a = rnd.uniform(0, math.tau)
        pts = []
        for k in range(8):
            a += rnd.uniform(-0.35, 0.35)
            x += math.cos(a) * 7
            y += math.sin(a) * 7
            pts.append((x, y))
        pygame.draw.lines(fib, (80, 240, 110, 215), False, pts, 5)
    field.blit(blur_layer(fib, 2), (0, 0))
    for x, y, rx, ry in ((50, 54, 15, 11), (94, 46, 13, 10), (80, 92, 16, 12), (40, 98, 11, 9)):
        R.glow(field, (x, y), rx * 2, (30, 60, 200), 0.9)
        pygame.draw.ellipse(field, (110, 150, 255), (x - rx, y - ry, 2 * rx, 2 * ry))
        pygame.draw.ellipse(field, (160, 190, 255), (x - rx // 2, y - ry // 2, rx, ry))
    m = pygame.Surface((N, N), pygame.SRCALPHA)
    pygame.draw.circle(m, (255, 255, 255, 255), (72, 72), 62)
    disc = pygame.Surface((N, N), pygame.SRCALPHA)
    disc.blit(field, (0, 0))
    disc.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    pygame.draw.circle(cv, (40, 40, 46), (72, 72), 68)
    cv.blit(disc, (0, 0))
    pygame.draw.circle(cv, (90, 90, 98), (72, 72), 68, 3)


def i_culture(cv):
    shadow(cv, 66, 120, 118, 14, 90)
    body = [(8, 44), (90, 40), (108, 58), (108, 96), (90, 112), (8, 114)]
    polyshape(cv, body, (222, 230, 232), 130, spec=0.25, edge=0.8, rim=0.4, rimw=3)
    med = [(11, 84), (104, 80), (104, 94), (89, 108), (11, 110)]
    polyshape(cv, med, (232, 112, 128), 220, spec=0.25, edge=0.8, rim=0.25, rimw=2)
    pygame.draw.line(cv, (250, 190, 196), (12, 84), (103, 80), 3)
    panel(cv, (18, 52, 46, 20), (250, 250, 246), 3, None, 0, 0.02)
    pygame.draw.line(cv, (110, 110, 120), (22, 60), (56, 60), 2)
    pygame.draw.line(cv, (150, 150, 160), (22, 66), (48, 66), 2)
    cyl(cv, (106, 64, 18, 26), (214, 222, 226), 4, 200, rim=0.4, rimw=2)    # neck
    cyl(cv, (120, 58, 20, 38), (50, 110, 200), 5, 255, rim=0.45, rimw=3)    # vented cap
    for y in range(64, 92, 6):
        pygame.draw.line(cv, (36, 80, 160), (122, y), (138, y), 2)


def i_count(cv):
    shadow(cv, 74, 128, 126, 12, 70)
    panel(cv, (8, 8, 128, 128), (222, 234, 240), 8, (140, 156, 166), 3, 0.06)
    for k in range(5):
        v = 16 + k * 28
        for d, w_ in ((0, 3), (-4, 1), (4, 1)):
            pygame.draw.line(cv, (120, 136, 150), (16, v + d), (128, v + d), w_)
            pygame.draw.line(cv, (120, 136, 150), (v + d, 16), (v + d, 128), w_)
    for x, y in ((34, 36), (88, 42), (60, 74), (110, 96), (36, 104), (78, 112)):
        pygame.draw.circle(cv, (250, 252, 248), (x, y), 9)
        pygame.draw.circle(cv, (96, 100, 96), (x, y), 9, 3)
        pygame.draw.circle(cv, (255, 255, 255), (x - 2, y - 2), 3)
    pygame.draw.circle(cv, (70, 104, 186), (104, 64), 9)
    pygame.draw.circle(cv, (40, 64, 130), (104, 64), 9, 3)


def i_transfect(cv):
    shadow(cv, 66, 128, 100, 12, 70)
    ball(cv, (62, 80), 48, (240, 210, 196), 0.3, 4)
    pygame.draw.ellipse(cv, (176, 132, 176), (42, 66, 40, 32))
    pygame.draw.ellipse(cv, (126, 84, 136), (58, 76, 10, 8))
    for x, y, r in ((112, 34, 13), (122, 72, 11), (92, 22, 9), (104, 54, 8)):
        ball(cv, (x, y), r, (246, 214, 110), 0.38, 3)
        pygame.draw.circle(cv, (210, 168, 64), (x, y), max(2, r - 5), 2)
    ball(cv, (100, 70), 10, (246, 214, 110), 0.38, 3)


def i_facs(cv):
    shadow(cv, 72, 132, 124, 10, 70)
    panel(cv, (8, 8, 128, 124), (252, 252, 250), 6, (150, 154, 160), 3, 0.02)
    pygame.draw.line(cv, (90, 94, 100), (20, 18), (20, 120), 3)
    pygame.draw.line(cv, (90, 94, 100), (20, 120), (128, 120), 3)
    rnd = random.Random(2)
    pal = [(40, 70, 220), (30, 170, 230), (40, 190, 90), (240, 210, 40), (236, 110, 40), (220, 40, 40)]
    for cx, cy, sx, sy, n in ((78, 64, 14, 12, 420), (38, 104, 7, 6, 90)):
        for _ in range(n):
            x, y = rnd.gauss(cx, sx), rnd.gauss(cy, sy)
            d = math.hypot((x - cx) / sx, (y - cy) / sy)
            col = pal[max(0, min(5, int(5.5 - d * 2.2)))] if n > 100 else pal[0]
            if 22 < x < 126 and 12 < y < 118:
                pygame.draw.circle(cv, col, (int(x), int(y)), 2)
    pygame.draw.rect(cv, (20, 20, 24), (50, 38, 58, 52), 3)


def i_crispr(cv):
    back = (110, 140, 190)
    front = (60, 100, 170)
    pts1 = [(x, 86 + 20 * math.sin(x / 13.0)) for x in range(4, 141, 3)]
    pts2 = [(x, 86 - 20 * math.sin(x / 13.0)) for x in range(4, 141, 3)]
    pygame.draw.lines(cv, back, False, pts2, 6)
    for i, x in enumerate(range(10, 138, 9)):
        y1, y2 = 86 + 20 * math.sin(x / 13.0), 86 - 20 * math.sin(x / 13.0)
        pygame.draw.line(cv, BASE["ACGT"[i % 4]], (x, y1), (x, y2), 3)
    pygame.draw.lines(cv, front, False, pts1, 6)
    blob = pygame.Surface((N, N), pygame.SRCALPHA)
    for x, y, r in ((74, 58, 26), (98, 66, 20), (60, 80, 18), (90, 92, 18), (110, 48, 14)):
        ball(blob, (x, y), r, (180, 150, 214), 0.35, 3)
    blob.set_alpha(230)
    cv.blit(blob, (0, 0))
    pygame.draw.lines(cv, (236, 120, 40), False, [(112, 40), (124, 30), (132, 36), (128, 48), (136, 56)], 4)


def _embryo_disc(cv):
    pygame.draw.circle(cv, (74, 74, 80), (72, 72), 67)
    disc = pygame.Surface((N, N), pygame.SRCALPHA)
    pygame.draw.circle(disc, (244, 236, 214), (72, 72), 62)
    for r in range(62, 40, -4):
        pygame.draw.circle(disc, (90, 80, 60, 9), (72, 72), r, 4)
    cv.blit(disc, (0, 0))


def i_inject(cv):
    _embryo_disc(cv)
    R.aa_circle(cv, (232, 236, 236, 80), (80, 82), 46, 3, (150, 160, 160), False)
    pygame.draw.arc(cv, (255, 255, 255), (38, 40, 84, 84), 1.9, 2.9, 3)
    ball(cv, (80, 92), 30, (210, 166, 96), 0.35, 3)
    rnd = random.Random(1)
    for _ in range(26):
        a, d = rnd.uniform(0, math.tau), rnd.uniform(0, 24)
        pygame.draw.circle(cv, (232, 196, 128) if rnd.random() < 0.5 else (176, 132, 70), (int(80 + math.cos(a) * d), int(92 + math.sin(a) * d)), 2)
    pygame.draw.ellipse(cv, (238, 228, 208), (60, 54, 40, 18))
    pygame.draw.ellipse(cv, (184, 170, 148), (60, 54, 40, 18), 2)
    needle = [(2, 10), (14, 2), (66, 58), (64, 62)]
    pygame.draw.polygon(cv, (214, 228, 232), needle)
    pygame.draw.polygon(cv, (232, 96, 136), [(6, 10), (12, 5), (54, 48), (52, 50)])
    pygame.draw.line(cv, (100, 120, 130), (2, 10), (64, 62), 2)
    pygame.draw.line(cv, (100, 120, 130), (14, 2), (66, 58), 2)
    ball(cv, (64, 62), 5, (236, 120, 150), 0.3, 1)


def i_ish(cv):
    _embryo_disc(cv)
    body = [(30, 60), (52, 56), (90, 64), (128, 76), (128, 80), (90, 82), (52, 86), (30, 84)]
    polyshape(cv, body, (226, 214, 190), 230, spec=0.3, edge=0.85, rim=0.3, rimw=3, profile=False)
    pygame.draw.polygon(cv, (232, 226, 210), [(60, 58), (128, 72), (128, 84), (60, 88)], 2)
    ball(cv, (34, 72), 15, (226, 212, 186), 0.3, 3)
    ball(cv, (52, 92), 15, (206, 170, 110), 0.35, 3)
    ball(cv, (30, 68), 6, (60, 50, 44), 0.2, 1)
    stain = pygame.Surface((N, N), pygame.SRCALPHA)
    pygame.draw.ellipse(stain, (86, 32, 130, 230), (30, 80, 18, 12))
    pygame.draw.line(stain, (96, 40, 140, 170), (50, 78), (124, 78), 4)
    cv.blit(blur_layer(stain, 2), (0, 0))


def i_ngs(cv):
    shadow(cv, 72, 116, 124, 12, 70)
    cv.blit(real.glass(128, 84, (200, 214, 222), 150, 8), (8, 28))
    rnd = random.Random(4)
    cols = [(60, 230, 90), (240, 70, 60), (70, 130, 255), (250, 220, 60)]
    for k in range(4):
        y = 40 + k * 17
        pygame.draw.rect(cv, (18, 22, 38), (20, y, 104, 11), border_radius=5)
        pygame.draw.circle(cv, (80, 86, 96), (16, y + 5), 4)
        pygame.draw.circle(cv, (80, 86, 96), (128, y + 5), 4)
        for _ in range(9):
            x = rnd.randint(26, 118)
            c = rnd.choice(cols)
            R.glow(cv, (x, y + 5), 7, c, 1.0)
            pygame.draw.circle(cv, lighten(c, 0.5), (x, y + 5), 2)


ICONS = {"pcr": i_pcr, "gel": i_gel, "extract": i_extract, "clone": i_clone, "transform": i_transform,
         "sanger": i_sanger, "qpcr": i_qpcr, "sds": i_sds, "western": i_western, "elisa": i_elisa,
         "purify": i_purify, "micro": i_micro, "culture": i_culture, "count": i_count, "transfect": i_transfect,
         "facs": i_facs, "crispr": i_crispr, "inject": i_inject, "ish": i_ish, "ngs": i_ngs}


def sprite(key, size):
    size = max(8, int(round(size)))
    k = (key, size)
    sp = _cache.get(k)
    if sp is None:
        big = _cache.get((key, "big"))
        if big is None:
            big = _canvas()
            ICONS[key](big)
            _cache[(key, "big")] = big
        sp = pygame.transform.smoothscale(big, (size, size))
        _cache[k] = sp
    return sp


def draw(s, key, c, size=40):
    """Draw the icon for technique `key` centred on c. Returns False for an unknown key."""
    if key not in ICONS:
        return False
    sp = sprite(key, size * 1.08)
    s.blit(sp, (int(c[0] - sp.get_width() / 2), int(c[1] - sp.get_height() / 2)))
    return True
