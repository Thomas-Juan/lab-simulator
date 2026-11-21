# -*- coding: utf-8 -*-
"""Drawing helpers in the Juan Lab ligne-claire style, rendered richly: anti-aliased ink
outlines, soft light from above, gentle gradients, soft shadows, glass highlights and
procedural textures. Everything is drawn in code; there are no image files.

Building blocks for minigames (all cached, so they are cheap to call every frame):
    rrect, card, circle, ellipse, poly, line        anti-aliased shapes with shading
    glass_rect, metal_rect, screen_rect, led, knob  instrument parts
    tube, pipette, petri, flask, cell, gel_slab, band, embryo-free lab objects
    glow(s, c, r, col)                              additive light (fluorescence, UV, LEDs)
    texture(w, h, base, scale, amp, seed)           noise texture surface (agar, gel, membrane, paper)
    bench, sky_bg                                   backgrounds"""
import math
import random
import pygame
import render as R
import real
from render import glow, lighten
from core import (W, H, INK, INK_SOFT, MUTED, CARD, PAPER, PAPER2, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ,
                  TEAL, LAV, VIOLET, NIGHT, WHITE, GREEN, RED, YELLOW, BLUE, GEL, DYE, draw_text, mix, clamp,
                  text_surf, pretty)

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

SHADOW = (60, 40, 100)


# ------------------------------------------------------------------ shapes
def rrect(s, rect, fill, border=INK, w=2, r=8, shade=0.07, gloss=True):
    """Anti-aliased rounded rectangle with a soft vertical shading and top highlight.
    shade=0 and gloss=False give a flat fill."""
    rect = pygame.Rect(rect)
    if rect.w < 2 or rect.h < 2:
        return
    fill = tuple(fill) if fill is not None else None
    border = tuple(border) if border is not None else None
    s.blit(R.rrect_surf(rect.w, rect.h, fill, border, w, r, shade if fill else 0, gloss), rect.topleft)


def shadow(s, rect, r=12, off=(4, 6), a=70, blur=8):
    rect = pygame.Rect(rect)
    sh = R.soft_shadow(rect.w, rect.h, r, SHADOW, a, blur)
    pad = blur * 2
    s.blit(sh, (rect.x - pad + off[0], rect.y - pad + off[1]))


_grain_add = None
_grain_sub = None
_cards = R.LRU(160)


def _grains():
    global _grain_add, _grain_sub
    if _grain_add is None:
        _grain_add = pygame.Surface((W, H))
        _grain_sub = pygame.Surface((W, H))
        if np is not None:
            rng = np.random.default_rng(11)
            n = rng.normal(0, 1, (W, H))
            a = np.clip(n * 4, 0, 10).astype(np.uint8)
            b = np.clip(-n * 4, 0, 10).astype(np.uint8)
            pygame.surfarray.pixels3d(_grain_add)[:] = a[..., None]
            pygame.surfarray.pixels3d(_grain_sub)[:] = b[..., None]
    return _grain_add, _grain_sub


def card(s, rect, fill=CARD, border=INK, r=14, w=2, drop=True):
    """A paper card: soft shadow, faint paper grain, gentle light from above."""
    rect = pygame.Rect(rect)
    if drop:
        shadow(s, rect, r)
    key = (rect.w, rect.h, tuple(fill), tuple(border) if border else None, r, w)
    sf = _cards.get(key)
    if sf is None:
        sf = R.rrect_surf(rect.w, rect.h, tuple(fill), tuple(border) if border else None, w, r, 0.035, True).copy()
        ga, gs = _grains()
        area = pygame.Rect(0, 0, min(rect.w, W), min(rect.h, H))
        sf.blit(ga, (0, 0), area, special_flags=pygame.BLEND_RGB_ADD)
        sf.blit(gs, (0, 0), area, special_flags=pygame.BLEND_RGB_SUB)
        _cards.put(key, sf)
    s.blit(sf, rect.topleft)


def circle(s, col, c, r, w=2, border=INK, shade=True):
    R.aa_circle(s, col, c, r, w, border, shade)


def ellipse(s, col, rect, w=2, border=INK):
    R.aa_ellipse(s, col, rect, w, border)


def poly(s, col, pts, w=2, border=INK):
    R.aa_poly(s, col, pts, w, border)


def line(s, col, a, b, w=2):
    R.aa_line(s, col, a, b, w)


_alpha = R.LRU(400)


def alpha_rect(s, rect, col, a, r=0):
    rect = pygame.Rect(rect)
    if rect.w < 1 or rect.h < 1:
        return
    key = (rect.size, tuple(col[:3]), int(a), r)
    sf = _alpha.get(key)
    if sf is None:
        if r:
            sf = R.rrect_surf(rect.w, rect.h, tuple(col[:3]) + (int(clamp(a, 0, 255)),), None, 0, r, 0, False)
        else:
            sf = pygame.Surface(rect.size, pygame.SRCALPHA)
            sf.fill(tuple(col[:3]) + (int(clamp(a, 0, 255)),))
        _alpha.put(key, sf)
    s.blit(sf, rect.topleft)


_acirc = R.LRU(300)


def alpha_circle(s, col, c, r, a):
    r = max(1, int(r))
    key = (r, tuple(col[:3]), int(clamp(a, 0, 255)))
    sf = _acirc.get(key)
    if sf is None:
        sf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        R.gd.filled_circle(sf, r + 1, r + 1, r, tuple(col[:3]) + (key[2],))
        R.gd.aacircle(sf, r + 1, r + 1, r, tuple(col[:3]) + (key[2],))
        _acirc.put(key, sf)
    s.blit(sf, (int(c[0]) - r - 1, int(c[1]) - r - 1))


def dim(s, a=140, col=NIGHT):
    alpha_rect(s, (0, 0, W, H), col, a)


_tex = R.LRU(60)


def texture(w, h, base, scale=40, amp=18, seed=0, octaves=3, alpha=None):
    """Surface of size (w, h) filled with `base` modulated by smooth noise (+-amp)."""
    w, h = max(1, int(w)), max(1, int(h))
    key = (w, h, tuple(base), scale, amp, seed, octaves, alpha)
    sf = _tex.get(key)
    if sf is not None:
        return sf
    if np is None:
        sf = pygame.Surface((w, h), pygame.SRCALPHA)
        sf.fill(tuple(base) + ((alpha,) if alpha is not None else (255,)))
        return _tex.put(key, sf)
    n = R.value_noise(w, h, scale, seed, octaves) - 0.5
    rgb = np.array(base[:3], dtype=np.float32)[None, None, :] + n[..., None] * amp * 2
    sf = R.to_surface(rgb)
    if alpha is not None:
        a = pygame.Surface((w, h), pygame.SRCALPHA)
        a.blit(sf, (0, 0))
        pygame.surfarray.pixels_alpha(a)[:] = alpha
        sf = a
    return _tex.put(key, sf)


# ------------------------------------------------------------------ backgrounds
_bg = {}


def _lab_wall(tint):
    """Tiled lab wall with light from above, a socket rail and a birch bench top."""
    wall = mix(PAPER, tint, 0.2)
    b = pygame.Surface((W, H))
    if np is None:
        b.fill(wall)
        return b
    rng = np.random.default_rng(3)
    img = np.zeros((H, W, 3), dtype=np.float32)
    img[:] = np.array(wall, dtype=np.float32)
    tw, th = 64, 32
    top = H - 70
    for row in range(0, top // th + 1):
        off = (row % 2) * tw // 2
        for col in range(-1, W // tw + 2):
            x0, y0 = col * tw + off, row * th
            x1, y1 = x0 + tw, min(y0 + th, top)
            if y0 >= top:
                continue
            xa, xb = max(0, x0), min(W, x1)
            if xb <= xa:
                continue
            v = rng.normal(0, 3.2)
            img[y0:y1, xa:xb] += v
            img[y0:y0 + 2, xa:xb] += 9            # bevel highlight
            img[y1 - 2:y1, xa:xb] -= 7            # bevel shade
            img[y0:y1, xa:xa + 1] += 5
            img[y0:y1, max(xa, xb - 1):xb] -= 5
            img[y0:y0 + 1, xa:xb] -= 26           # grout
            if 0 <= x0 < W:
                img[y0:y1, x0:x0 + 1] -= 24
    n = R.value_noise(W, H, 90, 5, 3)
    img += (n[..., None] - 0.5) * 10
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    light = 1.06 - 0.16 * ((xx - W * 0.5) / W) ** 2 * 2.2 - 0.12 * (yy / H) ** 1.5
    img *= light[..., None]
    # contact shadow above the bench and the bench itself
    img[top - 16:top] *= np.linspace(1.0, 0.82, 16, dtype=np.float32)[:, None, None]
    benchtop = np.array(mix(SAND, (238, 214, 172), 0.4), dtype=np.float32)
    front = np.array(mix(SAND, CORAL_D, 0.22), dtype=np.float32)
    gn = R.value_noise(W, 70, 6, 9, 2)
    streak = R.value_noise(W, 70, 60, 10, 2)
    grainline = np.sin(yy[:70] * 0.9 + streak * 9.0 + gn * 1.2 + np.sin(xx[:70] / 37.0) * 0.8) * 0.5 + 0.5
    grainline = grainline * 0.8 + R.value_noise(W, 70, 2, 12, 1) * 0.2
    img[top:top + 22] = benchtop + (grainline[:22, :, None] - 0.5) * 14 + np.linspace(12, -6, 22)[:, None, None]
    img[top + 22:H] = front + (grainline[22:70, :, None] - 0.5) * 16 + np.linspace(-4, -26, H - top - 22)[:, None, None]
    img[top + 1:top + 3] += 30
    img[top + 22:top + 24] -= 30
    out = R.to_surface(img)
    pygame.draw.line(out, INK, (0, top), (W, top), 2)
    pygame.draw.line(out, mix(front.astype(int).tolist(), INK, 0.5), (0, top + 22), (W, top + 22), 1)
    return out


def bench(s, tint=SKY, key="bench"):
    """Lab wall with tiles and a birch bench top. Cached per tint."""
    k = ("bench", tuple(tint))
    b = _bg.get(k)
    if b is None:
        if len(_bg) > 12:
            for old in [x for x in _bg if x != "sky"][:4]:
                del _bg[old]
        b = _bg[k] = real.lab_background(tint)
    s.blit(b, (0, 0))


def _sky():
    b = pygame.Surface((W, H))
    if np is None:
        b.fill((200, 220, 215))
        return b
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    f = (yy / H) ** 1.25
    top = np.array((138, 204, 204), dtype=np.float32)
    bot = np.array((250, 226, 192), dtype=np.float32)
    img = top + (bot - top) * f[..., None]
    sx, sy = W * 0.8, 120
    d = np.sqrt((xx - sx) ** 2 + (yy - sy) ** 2)
    img += np.clip(1 - d / 330, 0, 1)[..., None] ** 2 * np.array((60, 40, 10), dtype=np.float32)
    img += (R.value_noise(W, H, 200, 2, 2)[..., None] - 0.5) * 8
    out = R.to_surface(img)
    # sun
    R.aa_circle(out, (255, 236, 180), (sx, sy), 46, 0, None, False)
    R.aa_circle(out, (255, 246, 214), (sx, sy), 36, 0, None, False)
    # far mesas (lavender), then two dune ridges with Moebius-style hatching
    mesa = [(0, H)]
    for x in range(0, W + 6, 6):
        def plateau(x, a, b, hgt, edge=26):
            return hgt * min(1.0, max(0.0, (x - a) / edge), max(0.0, (b - x) / edge)) if a - edge < x < b + edge else 0.0
        h = 150 + 22 * math.sin(x / 260.0 + 1.3) + plateau(x, 130, 300, 70) + plateau(x, 610, 740, 46, 20) + plateau(x, 860, 990, 30)
        mesa.append((x, H - h))
    mesa.append((W, H))
    R.aa_poly(out, (205, 186, 222), mesa, 0, None)
    pygame.draw.lines(out, mix((205, 186, 222), INK, 0.35), False, mesa[1:-1], 2)
    rnd = random.Random(4)
    for lay, (base, col, amp1, amp2, ph) in enumerate(((128, (238, 200, 146), 30, 18, 0.0), (62, (228, 172, 122), 22, 10, 2.0))):
        pts = [(0, H)] + [(x, H - base - amp1 * math.sin(x / 140.0 + ph) - amp2 * math.sin(x / 47.0 + 1 + ph)) for x in range(0, W + 10, 10)] + [(W, H)]
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        R.aa_poly(layer, col, pts, 0, None)
        hatch = pygame.Surface((W, H), pygame.SRCALPHA)
        shade = mix(col, CORAL_D, 0.35)
        for i in range(260 if lay == 0 else 200):
            x = rnd.uniform(0, W)
            yb = H - base - amp1 * math.sin(x / 140.0 + ph) - amp2 * math.sin(x / 47.0 + 1 + ph)
            slope = math.cos(x / 140.0 + ph) * amp1 / 140.0 + math.cos(x / 47.0 + 1 + ph) * amp2 / 47.0
            if slope < -0.05:
                y = yb + rnd.uniform(6, 40)
                pygame.draw.line(hatch, shade + (150,), (x, y), (x + 7, y - 5), 1)
        mask = pygame.Surface((W, H), pygame.SRCALPHA)
        R.aa_poly(mask, (255, 255, 255), pts, 0, None)
        hatch.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        layer.blit(hatch, (0, 0))
        out.blit(layer, (0, 0))
        pygame.draw.lines(out, INK, False, pts[1:-1], 2)
    return out


_cloud = {}


def _cloud_sprite(i):
    c = _cloud.get(i)
    if c is None:
        w, h = 190, 70
        c = pygame.Surface((w, h), pygame.SRCALPHA)
        rnd = random.Random(i)
        blobs = [(30, 40, 26), (62, 30, 30), (100, 26, 34), (138, 34, 28), (165, 44, 20)]
        for x, y, r in blobs:
            R.gd.filled_circle(c, x, y + rnd.randint(-3, 3), r + 2, INK)
        pygame.draw.rect(c, INK, (10, 44, 172, 24), border_radius=12)
        for x, y, r in blobs:
            R.gd.filled_circle(c, x, y, r, (244, 240, 250))
        pygame.draw.rect(c, (244, 240, 250), (12, 44, 168, 22), border_radius=11)
        pygame.draw.rect(c, (226, 218, 240), (16, 54, 160, 10), border_radius=5)
        _cloud[i] = c
    return c


def menu_bg(s, t=0.0):
    """Menus: the lab, more out of focus and a little darker, so cards stand out."""
    b = _bg.get("menu")
    if b is None:
        b = real.lab_background((200, 220, 230))
        b = real._blur(b, 4)
        d = pygame.Surface((W, H), pygame.SRCALPHA)
        d.fill((20, 24, 40, 40))
        b.blit(d, (0, 0))
        _bg["menu"] = b
    s.blit(b, (0, 0))


def sky_bg(s, t=0.0):
    """Title / board backdrop: sky, sun, mesas and hatched dunes, with drifting clouds."""
    b = _bg.get("sky")
    if b is None:
        b = _bg["sky"] = _sky()
    s.blit(b, (0, 0))
    for i in range(4):
        x = (i * 290 + t * (6 + i * 2.5)) % (W + 320) - 200
        y = 34 + i * 30
        sp = _cloud_sprite(i)
        if i % 2:
            sp = pygame.transform.smoothscale(sp, (140, 52)) if ("c%d" % i) not in _cloud else _cloud["c%d" % i]
            _cloud["c%d" % i] = sp
        s.blit(sp, (x, y))


# ------------------------------------------------------------------ UI
class Button:
    def __init__(self, rect, label, col=SAND, key=None, size=18):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.col = col
        self.key = key
        self.size = size
        self.enabled = True

    def hot(self, inp):
        return self.enabled and self.rect.collidepoint(inp.mouse)

    def hit(self, inp):
        return self.enabled and ((inp.click and self.rect.collidepoint(inp.mouse)) or (self.key is not None and self.key in inp.keys))

    def draw(self, s, inp=None):
        hot = inp is not None and self.hot(inp)
        pressed = hot and getattr(inp, "down", False)
        col = tuple(self.col) if self.enabled else (214, 210, 204)
        if hot and not pressed:
            col = mix(col, WHITE, 0.22)
        lift = 0 if pressed else (2 if hot else 0)
        r = self.rect.move(0, -lift + (2 if pressed else 0))
        shadow(s, self.rect, 10, (2, 4), 55, 6)
        rrect(s, self.rect.move(0, 3), mix(col, INK, 0.42), INK, 2, 10, 0, False)
        rrect(s, r, col, INK, 2, 10, 0.12, True)
        draw_text(s, self.label, r.center, self.size, INK if self.enabled else MUTED, center=True, bold=True, vcenter=True)


_stars = R.LRU(60)


def star(s, x, y, r, filled=True, col=YELLOW):
    key = (round(r * 2) / 2, filled, tuple(col))
    sp = _stars.get(key)
    if sp is None:
        S = 3
        n = int(r * 2 + 6)
        big = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
        c = n * S / 2

        def pts(rr, dx=0, dy=0):
            return [(c + dx + math.sin(i * math.pi / 5) * (rr if i % 2 == 0 else rr * 0.45),
                     c + dy - math.cos(i * math.pi / 5) * (rr if i % 2 == 0 else rr * 0.45)) for i in range(10)]
        rr = r * S
        pygame.draw.polygon(big, INK, pts(rr + 2.2 * S))
        fill = col if filled else (238, 232, 222)
        pygame.draw.polygon(big, fill, pts(rr))
        if filled:
            pygame.draw.polygon(big, lighten(fill, 0.45), pts(rr * 0.5, -rr * 0.12, -rr * 0.16))
            pygame.draw.polygon(big, lighten(fill, -0.12), [(c, c)] + pts(rr)[4:8])
        sp = _stars.put(key, pygame.transform.smoothscale(big, (n, n)))
    s.blit(sp, (int(x - sp.get_width() / 2), int(y - sp.get_height() / 2)))


def stars(s, x, y, n, r=12, gap=30, total=3):
    for i in range(total):
        star(s, x + (i - (total - 1) / 2) * gap, y, r, i < n)


def bar(s, rect, frac, col=TURQ, back=CARD, border=INK):
    rect = pygame.Rect(rect)
    rad = rect.h // 2
    rrect(s, rect, mix(back, INK, 0.06), border, 2, rad, 0.0, False)
    if frac > 0:
        f = rect.inflate(-4, -4)
        f.w = max(f.h, int(f.w * clamp(frac, 0, 1)))
        rrect(s, f, col, None, 0, f.h // 2, 0.18, True)


def tag(s, x, y, txt, col=SAND, size=14, center=False):
    w = text_surf(pretty(str(txt)), size, INK, True).get_width() + 18
    if center:
        x -= w // 2
    rrect(s, (x, y, w, size + 12), col, INK, 2, (size + 12) // 2, 0.12)
    draw_text(s, txt, (x + 9, y + (size + 12) // 2), size, INK, bold=True, vcenter=True)
    return w


def header(s, rect, col, h, r=14):
    """Fill the top h pixels of a card drawn at rect with a coloured band (rounded top corners)."""
    rect = pygame.Rect(rect)
    band_ = R.rrect_surf(rect.w - 4, h + r, tuple(col), None, 0, r - 2, 0.1, True)
    s.blit(band_, (rect.x + 2, rect.y + 2), pygame.Rect(0, 0, rect.w - 4, h))
    pygame.draw.line(s, INK, (rect.x + 1, rect.y + h + 2), (rect.right - 2, rect.y + h + 2), 2)


_hud = {}


def hud_bar(s, h=46, col=CARD):
    """A top bar with a soft gradient and a shadow below it."""
    k = (h, tuple(col))
    sf = _hud.get(k)
    if sf is None:
        sf = pygame.Surface((W, h + 8), pygame.SRCALPHA)
        sf.blit(R.vgrad((W, h), lighten(col, 0.4), lighten(col, -0.05)), (0, 0))
        for i in range(8):
            pygame.draw.line(sf, (40, 30, 70, int(50 * (1 - i / 8.0))), (0, h + i), (W, h + i))
        pygame.draw.line(sf, INK, (0, h), (W, h), 2)
        _hud[k] = sf
    s.blit(sf, (0, 0))


def panel_title(s, rect, text, col, size=18):
    """Coloured header strip across the top of a card."""
    rect = pygame.Rect(rect)
    hdr = pygame.Rect(rect.x, rect.y, rect.w, size + 22)
    rrect(s, hdr, col, INK, 2, 12, 0.14)
    draw_text(s, text, (hdr.x + 16, hdr.centery), size, WHITE, bold=True, vcenter=True, shadow=mix(col, INK, 0.5))
    return hdr.bottom


# ------------------------------------------------------------------ instrument parts
def metal_rect(s, rect, col=(206, 210, 218), r=8, w=2):
    """Brushed stainless steel (or painted metal of colour col) with a bevel."""
    rect = pygame.Rect(rect)
    if rect.w < 3 or rect.h < 3:
        return
    s.blit(real.steel(rect.w, rect.h, r, tuple(col[:3])), rect.topleft)


def plastic_rect(s, rect, col=(232, 232, 228), r=8, gloss=0.25):
    """Moulded instrument housing."""
    rect = pygame.Rect(rect)
    if rect.w < 3 or rect.h < 3:
        return
    s.blit(real.plastic(rect.w, rect.h, tuple(col[:3]), r, gloss), rect.topleft)


def screen_rect(s, rect, col=(26, 34, 40), r=6):
    """An instrument display: bezel, dark glass with a faint glare."""
    rect = pygame.Rect(rect)
    if rect.w < 8 or rect.h < 8:
        return
    s.blit(real.lcd(rect.w, rect.h, r, tuple(col[:3])), rect.topleft)


def led(s, c, col=GREEN, on=True, r=5):
    circle(s, col if on else mix(col, (60, 60, 60), 0.7), c, r, 1)
    if on:
        alpha_circle(s, col, c, r * 2.2, 50)


def knob(s, c, r, angle=0.0, col=(70, 74, 86)):
    circle(s, col, c, r, 2)
    a = angle - math.pi / 2
    line(s, WHITE, (c[0] + math.cos(a) * r * 0.25, c[1] + math.sin(a) * r * 0.25), (c[0] + math.cos(a) * r * 0.8, c[1] + math.sin(a) * r * 0.8), 3)


def glass_rect(s, rect, tint=(220, 236, 244), a=110, r=8):
    """Clear glass or acrylic: faint tint, bright edges and one highlight streak."""
    rect = pygame.Rect(rect)
    if rect.w < 4 or rect.h < 4:
        return
    s.blit(real.glass(rect.w, rect.h, tuple(tint[:3]), min(255, int(a * 0.7)), r), rect.topleft)


# ------------------------------------------------------------------ lab objects
_tubes = R.LRU(300)


def _tube_sprite(w, h, liquid, level, cap, open_):
    key = (w, h, liquid, round(level, 2), cap, open_)
    sp = _tubes.get(key)
    if sp is not None:
        return sp
    S = 3
    pad = 14
    big = pygame.Surface(((w + 2 * pad) * S, (h + pad) * S), pygame.SRCALPHA)
    ox, oy = pad * S, (pad - 6) * S
    X = lambda v: ox + v * S
    Y = lambda v: oy + v * S
    body = [(X(0), Y(9)), (X(w), Y(9)), (X(w), Y(h * 0.62)), (X(w * 0.6), Y(h)), (X(w * 0.4), Y(h)), (X(0), Y(h * 0.62))]
    inner = [(X(1), Y(10)), (X(w - 1), Y(10)), (X(w - 1), Y(h * 0.62)), (X(w * 0.58), Y(h - 1)), (X(w * 0.42), Y(h - 1)), (X(1), Y(h * 0.62))]
    pygame.draw.polygon(big, INK, body)
    pygame.draw.polygon(big, (236, 244, 250, 255), inner)
    if liquid is not None and level > 0:
        top = h - (h - 11) * clamp(level, 0, 1)
        liq = pygame.Surface(big.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(liq, tuple(liquid[:3]) + (235,), inner)
        cut = pygame.Surface(big.get_size(), pygame.SRCALPHA)
        cut.fill((255, 255, 255, 255))
        pygame.draw.rect(cut, (0, 0, 0, 0), (0, 0, big.get_width(), Y(top)))
        liq.blit(cut, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        big.blit(liq, (0, 0))
        dark = lighten(liquid, -0.25)
        pygame.draw.line(big, lighten(liquid, 0.35), (X(1.5), Y(top) + S), (X(w - 1.5), Y(top) + S), S * 2)
        pygame.draw.polygon(big, dark, [(X(w * 0.42), Y(h - 1)), (X(w * 0.58), Y(h - 1)), (X(w * 0.66), Y(h * 0.84)), (X(w * 0.34), Y(h * 0.84))]) if level > 0.25 else None
    # glass highlights
    pygame.draw.line(big, (255, 255, 255, 200), (X(w * 0.22), Y(13)), (X(w * 0.22), Y(h * 0.6)), max(2, int(w * 0.12 * S)))
    pygame.draw.line(big, (255, 255, 255, 110), (X(w * 0.78), Y(14)), (X(w * 0.78), Y(h * 0.5)), max(1, int(w * 0.05 * S)))
    # cap with hinge
    capc = tuple(cap[:3])
    if open_:
        cr = pygame.Rect(X(-10), Y(5), 8 * S, (w + 4) * S)
        pygame.draw.rect(big, INK, cr.inflate(4, 4), border_radius=3 * S)
        pygame.draw.rect(big, capc, cr, border_radius=3 * S)
        pygame.draw.line(big, lighten(capc, 0.35), (cr.x + 2 * S, cr.y + 3 * S), (cr.x + 2 * S, cr.bottom - 3 * S), S)
        pygame.draw.rect(big, INK, (X(-3), Y(7), 4 * S, 3 * S))
        pygame.draw.rect(big, INK, (X(-1), Y(7), (w + 2) * S, 3 * S), border_radius=S)
        pygame.draw.rect(big, (238, 244, 250), (X(0), Y(7) + S, w * S, S))
    else:
        cr = pygame.Rect(X(-3), Y(0), (w + 6) * S, 9 * S)
        pygame.draw.rect(big, INK, cr.inflate(4, 4), border_radius=3 * S)
        g = R.vgrad(cr.size, lighten(capc, 0.3), lighten(capc, -0.18))
        m = pygame.Surface(cr.size, pygame.SRCALPHA)
        pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=3 * S)
        gs = pygame.Surface(cr.size, pygame.SRCALPHA)
        gs.blit(g, (0, 0))
        gs.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        big.blit(gs, cr.topleft)
        pygame.draw.rect(big, INK, (X(w + 3), Y(2), 4 * S, 5 * S), border_radius=S)
        pygame.draw.rect(big, capc, (X(w + 3) + S, Y(2) + S, 2 * S, 3 * S))
        pygame.draw.line(big, (255, 255, 255, 150), (cr.x + 3 * S, cr.y + 2 * S), (cr.right - 3 * S, cr.y + 2 * S), S)
    sp = pygame.transform.smoothscale(big, (w + 2 * pad, h + pad))
    return _tubes.put(key, sp)


def tube(s, x, y, w=22, h=54, liquid=None, level=0.5, cap=CORAL, label=None, open_=False, lsize=11):
    """1.5 mL microcentrifuge tube (milky polypropylene) with its top-left corner at (x, y)."""
    w, h = max(6, int(round(w))), max(14, int(round(h)))
    real.tube(s, x, y, w, h, tuple(liquid[:3]) if liquid is not None else None, level if liquid is not None else 0,
              tuple(cap[:3]) if cap is not None else None, open_)
    if label:
        draw_text(s, label, (x + w / 2, y + h * 0.36), lsize, INK, center=True, bold=True)


def pipette(s, tip, liquid=None, amount=0.0, col=(236, 236, 240), plunger=0.0, scale=1.0):
    """Air-displacement pipette (P20), upright, with the end of its tip at `tip`."""
    real.pipette(s, tip, liquid, amount, plunger, scale)


_petri = R.LRU(40)


def petri(s, c, r, agar=(242, 220, 160), rim=True):
    """Polystyrene Petri dish with agar, lit from the upper left, casting a soft shadow."""
    real.petri(s, c, r, agar)


def sphere_shade(r):
    return R.sphere_light(r, 45)


def flask(s, x, y, col=CORAL, level=0.5, liquid=(240, 150, 150)):
    """T-flask lying flat, seen from the side, with a vented cap."""
    pts = [(x, y + 70), (x + 90, y + 70), (x + 90, y + 10), (x + 60, y + 10), (x + 50, y), (x + 22, y), (x + 14, y + 10), (x, y + 10)]
    R.aa_poly(s, (236, 244, 250), pts, 0, None)
    lv = y + 70 - 58 * level
    alpha_rect(s, (x + 2, lv, 87, y + 69 - lv), liquid, 220, 2)
    pygame.draw.line(s, lighten(liquid, 0.3), (x + 3, lv + 1), (x + 88, lv + 1), 2)
    pygame.draw.line(s, WHITE, (x + 8, y + 16), (x + 8, y + 62), 3)
    R.aa_poly(s, None, pts, 2, INK)
    rrect(s, (x + 92, y + 22, 28, 28), col, INK, 2, 5, 0.18)
    for i in range(3):
        pygame.draw.line(s, lighten(col, -0.3), (x + 98 + i * 7, y + 26), (x + 98 + i * 7, y + 46), 2)


def cell(s, c, r, col=PEACH, nucleus=VIOLET, w=2):
    circle(s, col, c, r, w)
    circle(s, nucleus, (c[0] + r * 0.15, c[1] - r * 0.1), r * 0.38, 1, mix(nucleus, INK, 0.4))
    alpha_circle(s, lighten(nucleus, -0.3), (c[0] + r * 0.22, c[1] - r * 0.14), max(1, r * 0.12), 200)


def blur(surf, k=4):
    k = max(1, int(k))
    if k <= 1:
        return surf
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (max(1, w // k), max(1, h // k)))
    return pygame.transform.smoothscale(small, (w, h))


def gel_slab(s, rect, wells=8, well_w=None, top=14, col=GEL, vertical=False):
    """Agarose (horizontal) or polyacrylamide (vertical) gel seen from above; returns well rects."""
    rect = pygame.Rect(rect)
    s.blit(texture(rect.w, rect.h, col, 30, 6, 41, 2), rect.topleft)
    alpha_rect(s, (rect.x + 4, rect.y + 4, rect.w // 3, rect.h - 8), WHITE, 22, 6)
    rrect(s, rect, None, INK, 2, 6)
    out = []
    ww = well_w or int(rect.w / (wells + 1) * 0.62)
    gap = rect.w / (wells + 1)
    for i in range(wells):
        cx = rect.x + gap * (i + 1)
        wr = pygame.Rect(int(cx - ww / 2), rect.y + top, ww, 10 if not vertical else 16)
        rrect(s, wr, mix(col, INK, 0.42), INK, 1, 2, -0.15, False)
        out.append(wr)
    return out


def band(s, cx, y, w, strength=1.0, col=(255, 160, 220), glow=True):
    a = int(clamp(strength, 0, 1) * 255)
    if a <= 0:
        return
    if glow:
        alpha_rect(s, (cx - w / 2 - 4, y - 6, w + 8, 12), col, a // 5, 6)
        alpha_rect(s, (cx - w / 2 - 2, y - 4, w + 4, 8), col, a // 3, 4)
    alpha_rect(s, (cx - w / 2, y - 3, w, 6), col, a, 3)
    alpha_rect(s, (cx - w / 2 + 2, y - 2, w - 4, 2), lighten(col, 0.5), a // 2, 1)


# ------------------------------------------------------------------ particles
class Particles:
    def __init__(self):
        self.p = []

    def burst(self, x, y, n=16, cols=(CORAL, TURQ, YELLOW, LAV), speed=4.0, life=50, g=0.15, size=4):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(0.3, 1) * speed
            self.p.append([x, y, math.cos(a) * v, math.sin(a) * v - speed * 0.3, life, random.choice(cols), size, g,
                           random.uniform(0, math.tau), random.random() < 0.5])

    def update(self):
        for q in self.p:
            q[0] += q[2]
            q[1] += q[3]
            q[3] += q[7]
            q[2] *= 0.985
            q[4] -= 1
            q[8] += 0.2
        self.p = [q for q in self.p if q[4] > 0]

    def draw(self, s):
        for x, y, _, _, life, col, size, _, rot, conf in self.p:
            r = max(1.5, size * min(1, life / 20))
            if conf:   # confetti: a spinning rectangle
                w = abs(math.cos(rot)) * r * 2 + 1
                pygame.draw.rect(s, col, (x - w / 2, y - r * 0.6, w, r * 1.2))
            else:
                R.gd.filled_circle(s, int(x), int(y), int(r), col)
                R.gd.aacircle(s, int(x), int(y), int(r), mix(col, INK, 0.35))


class Floaters:
    """Rising score texts (+10, Spilled!, ...) with a white outline."""
    def __init__(self):
        self.f = []

    def add(self, x, y, txt, col=GREEN, size=20):
        self.f.append([x, y, txt, col, 60, size])

    def update(self):
        for q in self.f:
            q[1] -= 0.8
            q[4] -= 1
        self.f = [q for q in self.f if q[4] > 0]

    def draw(self, s):
        for x, y, txt, col, life, size in self.f:
            t = pretty(str(txt))
            fg = text_surf(t, size, tuple(col), True)
            ol = text_surf(t, size, (255, 255, 255), True)
            px, py = int(x - fg.get_width() / 2), int(y)
            a = 255 if life > 15 else int(255 * life / 15)
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)):
                ol.set_alpha(a)
                s.blit(ol, (px + dx, py + dy))
            fg.set_alpha(a)
            s.blit(fg, (px, py))
            fg.set_alpha(None)
            ol.set_alpha(None)


# ------------------------------------------------------------------ technique icons (board tiles, cards)
def icon(s, key, c, size=40):
    """Small picture of a technique's key object, centred on c, roughly size x size.
    Drawn by icons.py when it provides draw(s, key, c, size); otherwise the pictograms below."""
    try:
        import icons
        if icons.draw(s, key, c, size):
            return
    except ImportError:
        pass
    _icon_old(s, key, c, size)


def _icon_old(s, key, c, size=40):
    x, y = c
    k = size / 40.0
    if key == "pcr":
        for i in range(3):
            tube(s, x - 17 * k + i * 12 * k, y - 16 * k, 9 * k, 30 * k, (240, 160, 90), 0.4, [CORAL, TURQ, YELLOW][i])
    elif key == "gel":
        rrect(s, (x - 18 * k, y - 16 * k, 36 * k, 32 * k), GEL, INK, 2, 3)
        for i, yy in enumerate((-8, -2, 5, 10)):
            pygame.draw.rect(s, DYE if i == 0 else (240, 120, 200), (x - 13 * k + (i % 2) * 14 * k, y + yy * k, 10 * k, 3 * k))
    elif key == "extract":
        tube(s, x - 8 * k, y - 18 * k, 16 * k, 36 * k, (250, 250, 250), 0.6, TURQ)
        pygame.draw.lines(s, INK, False, [(x - 3 * k, y + 2 * k), (x + 2 * k, y - 2 * k), (x - 2 * k, y - 6 * k), (x + 3 * k, y - 10 * k)], 2)
    elif key in ("clone",):
        pygame.draw.circle(s, TURQ, (x, y), int(15 * k), max(3, int(5 * k)))
        pygame.draw.circle(s, INK, (x, y), int(18 * k), 2)
        pygame.draw.arc(s, CORAL, (x - 15 * k, y - 15 * k, 30 * k, 30 * k), 0.2, 1.4, max(3, int(6 * k)))
    elif key == "transform":
        petri(s, (int(x), int(y)), int(15 * k))
        for dx, dy, cc in ((-6, -4, WHITE), (5, 3, BLUE), (2, -7, WHITE), (-3, 7, BLUE), (8, -3, WHITE)):
            circle(s, cc, (x + dx * k, y + dy * k), 2.6 * k, 1)
    elif key == "sanger":
        rrect(s, (x - 18 * k, y - 14 * k, 36 * k, 28 * k), CARD, INK, 2, 3)
        for i, b in enumerate("ACGTA"):
            from core import BASE_COL
            px = x - 14 * k + i * 7 * k
            pygame.draw.lines(s, BASE_COL[b], False, [(px - 3 * k, y + 10 * k), (px, y - 8 * k + (i % 2) * 6 * k), (px + 3 * k, y + 10 * k)], 2)
    elif key == "qpcr":
        rrect(s, (x - 18 * k, y - 15 * k, 36 * k, 30 * k), CARD, INK, 2, 3)
        for j, cc in enumerate((CORAL, TURQ)):
            pts = [(x - 15 * k + i * 3 * k, y + 10 * k - 20 * k / (1 + math.exp(-(i - 4 - j * 3) * 0.9))) for i in range(11)]
            pygame.draw.lines(s, cc, False, pts, 2)
    elif key == "sds":
        rrect(s, (x - 14 * k, y - 18 * k, 28 * k, 36 * k), (220, 226, 236), INK, 2, 2)
        for i, yy in enumerate((-10, -4, 3, 9)):
            pygame.draw.rect(s, (60, 80, 170), (x - 10 * k + (i % 2) * 11 * k, y + yy * k, 9 * k, 3 * k))
    elif key == "western":
        rrect(s, (x - 16 * k, y - 16 * k, 32 * k, 32 * k), (250, 250, 246), INK, 2, 2)
        for i in range(3):
            pygame.draw.ellipse(s, INK, (x - 13 * k + i * 9 * k, y - 3 * k, 8 * k, 5 * k))
    elif key == "elisa":
        rrect(s, (x - 18 * k, y - 13 * k, 36 * k, 26 * k), CARD, INK, 2, 3)
        for i in range(4):
            for j in range(3):
                pygame.draw.circle(s, mix(YELLOW, (240, 240, 230), i / 3.0), (int(x - 12 * k + i * 8 * k), int(y - 7 * k + j * 7 * k)), max(2, int(3 * k)))
    elif key == "culture":
        if True:
            rrect(s, (x - 16 * k, y - 10 * k, 26 * k, 22 * k), (240, 246, 250), INK, 2, 3)
            pygame.draw.rect(s, (240, 150, 150), (x - 14 * k, y + 2 * k, 22 * k, 8 * k))
            rrect(s, (x + 10 * k, y - 4 * k, 8 * k, 8 * k), CORAL, INK, 2, 2)
    elif key == "count":
        rrect(s, (x - 17 * k, y - 17 * k, 34 * k, 34 * k), (235, 242, 246), INK, 2, 2)
        for i in range(1, 4):
            pygame.draw.line(s, MUTED, (x - 17 * k + i * 8.5 * k, y - 17 * k), (x - 17 * k + i * 8.5 * k, y + 17 * k), 1)
            pygame.draw.line(s, MUTED, (x - 17 * k, y - 17 * k + i * 8.5 * k), (x + 17 * k, y - 17 * k + i * 8.5 * k), 1)
        for dx, dy in ((-9, -8), (6, -2), (-2, 9), (10, 10)):
            pygame.draw.circle(s, PEACH, (int(x + dx * k), int(y + dy * k)), max(2, int(3 * k)))
    elif key == "transfect":
        cell(s, (x, y + 4 * k), 13 * k)
        for dx, dy in ((-14, -14), (12, -16), (0, -19)):
            circle(s, YELLOW, (x + dx * k, y + dy * k), 3.5 * k, 1)
    elif key == "facs":
        rrect(s, (x - 16 * k, y - 16 * k, 32 * k, 32 * k), CARD, INK, 2, 3)
        rnd = random.Random(3)
        for _ in range(18):
            pygame.draw.circle(s, GREEN if rnd.random() < 0.5 else RED, (int(x + rnd.gauss(0, 6) * k), int(y + rnd.gauss(0, 6) * k)), 1)
        pygame.draw.rect(s, CORAL, (x - 7 * k, y - 7 * k, 14 * k, 14 * k), 1)
    elif key == "micro":
        circle(s, NIGHT, (x, y), 17 * k)
        circle(s, (60, 200, 90), (x - 5 * k, y - 3 * k), 5 * k, 0)
        circle(s, (80, 120, 255), (x + 6 * k, y + 5 * k), 4 * k, 0)
        circle(s, (240, 70, 90), (x + 4 * k, y - 8 * k), 3 * k, 0)
    elif key == "crispr":
        for i in range(6):
            yy = y - 15 * k + i * 6 * k
            dx = math.sin(i * 1.1) * 9 * k
            pygame.draw.line(s, TURQ, (x - dx, yy), (x + dx, yy), 3)
        pygame.draw.lines(s, CORAL, False, [(x - 16 * k, y - 4 * k), (x + 16 * k, y + 6 * k)], 3)
    elif key == "inject":
        circle(s, (250, 230, 170), (x + 2 * k, y + 5 * k), 12 * k)
        circle(s, (255, 250, 240), (x + 2 * k, y - 4 * k), 5 * k, 1)
        pygame.draw.line(s, INK, (x - 18 * k, y - 18 * k), (x, y), 2)
    elif key == "ish":
        ellipse(s, (240, 236, 220), (x - 18 * k, y - 8 * k, 36 * k, 16 * k))
        pygame.draw.ellipse(s, (100, 50, 140), (x - 9 * k, y - 4 * k, 9 * k, 7 * k))
    elif key == "ngs":
        rrect(s, (x - 17 * k, y - 15 * k, 34 * k, 30 * k), NIGHT, INK, 2, 3)
        rnd = random.Random(7)
        from core import BASE_COL
        for _ in range(14):
            cc = BASE_COL["ACGT"[rnd.randrange(4)]]
            cc = (240, 240, 80) if cc == (30, 30, 30) else cc
            pygame.draw.circle(s, cc, (int(x + rnd.uniform(-13, 13) * k), int(y + rnd.uniform(-11, 11) * k)), max(1, int(2 * k)))
    elif key == "purify":
        rrect(s, (x - 7 * k, y - 18 * k, 14 * k, 30 * k), (240, 246, 250), INK, 2, 2)
        pygame.draw.rect(s, (150, 206, 196), (x - 5 * k, y - 2 * k, 10 * k, 12 * k))
        pygame.draw.polygon(s, INK, [(x - 7 * k, y + 12 * k), (x + 7 * k, y + 12 * k), (x, y + 19 * k)], 2)
    else:
        circle(s, SAND, c, 14 * k)


_dice = R.LRU(20)


def die(s, c, n, size=56, rot=0.0):
    """A chunky die with a visible side face; rot (degrees) tilts it while rolling."""
    key = (n, size)
    sp = _dice.get(key)
    if sp is None:
        d = int(size * 0.14)
        sp = pygame.Surface((size + d + 4, size + d + 4), pygame.SRCALPHA)
        R.aa_poly(sp, (226, 214, 196), [(2 + 6, 2), (2 + size + d - 4, 2 + d - 2), (2 + size + d, 2 + size + d - 6),
                                        (2 + d, 2 + size + d), (2, 2 + size - 6)], 0, None)
        sp.blit(R.rrect_surf(size, size, (230, 218, 200), INK, 2, 12, 0, False), (2 + d, 2 + d))
        sp.blit(R.rrect_surf(size, size, (255, 252, 244), INK, 2, 12, 0.08, True), (2, 2))
        pos = {1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)], 4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
               5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)], 6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)]}[n]
        pr = max(3, size // 10)
        for dx, dy in pos:
            px, py = int(2 + size / 2 + dx * size * 0.27), int(2 + size / 2 + dy * size * 0.27)
            col = CORAL if n == 1 else INK
            R.gd.filled_circle(sp, px, py, pr + (2 if n == 1 else 0), col)
            R.gd.aacircle(sp, px, py, pr + (2 if n == 1 else 0), col)
            R.gd.filled_circle(sp, px + 1, py + 1, max(1, pr // 2), lighten(col, 0.25))
        sp = _dice.put(key, sp)
    img = pygame.transform.rotozoom(sp, rot, 1.0) if rot else sp
    shadow(s, (c[0] - size // 2 + 6, c[1] - size // 2 + 10, size, size), 12, (0, 0), 60, 6)
    s.blit(img, (int(c[0] - img.get_width() / 2), int(c[1] - img.get_height() / 2)))


def scientist(s, x, y, t=0.0, squash=0.0, coat=WHITE):
    """The player's token: a scientist in a lab coat with safety glasses; (x, y) = feet."""
    sq = 1 - squash * 0.25
    alpha_circle(s, NIGHT, (x, y + 2), 13, 45)
    h = 30 * sq
    body = [(x - 14, y), (x - 11, y - h * 0.8), (x - 6, y - h), (x + 6, y - h), (x + 11, y - h * 0.8), (x + 14, y)]
    poly(s, coat, body)
    line(s, mix(coat, INK, 0.3), (x, y - h + 3), (x, y - 2), 1)
    rrect(s, (x + 3, y - h * 0.62, 6, 8), (120, 180, 230), INK, 1, 2, 0.1)
    hy = y - h - 11 * sq
    circle(s, PEACH, (x, hy), 12)
    pygame.draw.arc(s, (96, 64, 50), (x - 13, hy - 14, 26, 22), 0.15, 3.0, 6)
    rrect(s, (x - 11, hy - 4, 22, 8), (190, 232, 240), INK, 2, 4, 0.2)
    alpha_rect(s, (x - 8, hy - 3, 6, 2), WHITE, 200, 1)
    pygame.draw.arc(s, INK, (x - 4, hy + 2, 8, 6), 3.5, 5.9, 2)
