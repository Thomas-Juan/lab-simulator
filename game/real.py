# -*- coding: utf-8 -*-
"""Realistic rendering of lab materials: polypropylene, polystyrene, glass, steel, resin worktops,
LCD screens, and the photographic lab background (sharp worktop, blurred shelves behind).

Objects are drawn without cartoon ink lines: edges come from shading (a darker rim of the
material's own colour), light comes from the upper left, and every object casts a soft
contact shadow. All results are cached sprites built at 3x and scaled down."""
import math
import random
import pygame
import render as R
from render import LRU, lighten

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

W, H = 960, 540
S = 3   # supersampling factor for sprites


# ------------------------------------------------------------------ shading profiles
def cyl_profile(n, spec=0.28, spec_w=0.06, spec_k=0.55, edge=0.62):
    """Brightness across a cylinder (left to right), 0..~1.4, with a specular streak."""
    u = (np.arange(n, dtype=np.float32) + 0.5) / n
    body = edge + (1 - edge) * np.sin(np.pi * u) ** 0.55
    hl = spec_k * np.exp(-((u - spec) / spec_w) ** 2)
    hl2 = 0.18 * np.exp(-((u - 0.82) / 0.035) ** 2)
    return body + hl + hl2


def shaded_mask(mask, base, profile=None, alpha=255, vert=None):
    """Colour a white SRCALPHA mask with `base`, modulated by a horizontal profile (cylinder)
    and an optional vertical profile. Returns a new SRCALPHA surface."""
    w, h = mask.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    if np is None:
        out.fill(tuple(base[:3]) + (alpha,))
        out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return out
    prof = np.ones(w, dtype=np.float32) if profile is None else profile
    rgb = np.array(base[:3], dtype=np.float32)[None, None, :] * prof[:, None, None]
    if vert is not None:
        rgb = rgb * vert[None, :, None]
    hi = np.clip(prof - 1.0, 0, None)[:, None, None] * 255 * 0.8
    rgb = np.clip(rgb + hi, 0, 255).astype(np.uint8)
    if rgb.shape[1] != h:
        rgb = np.broadcast_to(rgb, (w, h, 3)).copy()
    pygame.surfarray.pixels3d(out)[:] = rgb
    m = pygame.surfarray.pixels_alpha(mask)
    pygame.surfarray.pixels_alpha(out)[:] = (m.astype(np.uint16) * alpha // 255).astype(np.uint8)
    del m
    return out


def soft_edge(mask, col, width=2):
    """A thin darker rim along the inside of a mask's outline (the material's own edge)."""
    w, h = mask.get_size()
    m = mask.copy()
    shrunk = pygame.transform.smoothscale(m, (max(1, w - 2 * width), max(1, h - 2 * width)))
    rim = pygame.Surface((w, h), pygame.SRCALPHA)
    rim.fill(tuple(col[:3]) + (0,))
    rim.blit(mask, (0, 0))
    rim.fill(tuple(col[:3]) + (255,), special_flags=pygame.BLEND_RGBA_MULT)
    hole = pygame.Surface((w, h), pygame.SRCALPHA)
    hole.blit(shrunk, (width, width))
    if np is not None:
        a = pygame.surfarray.pixels_alpha(rim)
        b = pygame.surfarray.array_alpha(hole)
        a[:] = np.clip(a.astype(np.int16) - b.astype(np.int16), 0, 255).astype(np.uint8)
        del a
    return rim


def contact_shadow(w, h, a=90):
    """Elliptical soft shadow for an object resting on the bench."""
    return R.soft_shadow(max(2, w), max(2, h), max(1, h // 2), (20, 18, 30), a, max(3, h // 2))


# ------------------------------------------------------------------ microcentrifuge tube
_tubes = LRU(300)
PP = (236, 238, 232)          # milky polypropylene


def tube_sprite(w, h, liquid, level, cap, open_):
    key = (w, h, liquid, round(level, 2), cap, open_)
    sp = _tubes.get(key)
    if sp is not None:
        return sp
    pad = 14
    BW, BH = (w + 2 * pad) * S, (h + pad + 6) * S
    big = pygame.Surface((BW, BH), pygame.SRCALPHA)
    ox, oy = pad * S, 8 * S
    X = lambda v: int(ox + v * S)
    Y = lambda v: int(oy + v * S)
    capc = cap if cap is not None else PP
    # body mask: cylinder, then cone to a rounded tip
    body = [(X(0), Y(9)), (X(w), Y(9)), (X(w), Y(h * 0.6)), (X(w * 0.62), Y(h - 1)), (X(w * 0.38), Y(h - 1)), (X(0), Y(h * 0.6))]
    mask = pygame.Surface((BW, BH), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), body)
    pygame.draw.circle(mask, (255, 255, 255, 255), (X(w / 2), Y(h - 2)), int(w * 0.13 * S))
    prof = np.zeros(BW, dtype=np.float32) + 1.0
    if np is not None:
        prof[X(0):X(w)] = cyl_profile(X(w) - X(0), spec_k=0.45)
    plastic = shaded_mask(mask, (214, 218, 214), prof, 150)
    big.blit(plastic, (0, 0))
    # liquid inside, with a meniscus and a darker conical bottom
    if liquid is not None and level > 0:
        top = h - 1 - (h - 12) * min(1.0, max(0.0, level))
        inner = [(X(1.2), Y(10)), (X(w - 1.2), Y(10)), (X(w - 1.2), Y(h * 0.6)), (X(w * 0.6), Y(h - 2)), (X(w * 0.4), Y(h - 2)), (X(1.2), Y(h * 0.6))]
        lm = pygame.Surface((BW, BH), pygame.SRCALPHA)
        pygame.draw.polygon(lm, (255, 255, 255, 255), inner)
        pygame.draw.rect(lm, (0, 0, 0, 0), (0, 0, BW, Y(top)))
        pygame.draw.ellipse(lm, (255, 255, 255, 255), (X(1.2), Y(top) - 2 * S, X(w - 1.2) - X(1.2), 4 * S))
        lprof = prof * 0.85 + 0.15
        vert = None
        liq = shaded_mask(lm, liquid, lprof, 225, vert)
        big.blit(liq, (0, 0))
        pygame.draw.ellipse(big, lighten(liquid, 0.35) + (200,), (X(1.5), Y(top) - S, X(w - 1.5) - X(1.5), 3 * S), max(1, S))
    big.blit(soft_edge(mask, (120, 126, 128), 2 * S // 2 + 1), (0, 0))
    # graduation marks and frosted writing patch
    for i in range(3):
        yy = Y(h * 0.22 + i * h * 0.1)
        pygame.draw.line(big, (150, 156, 160, 160), (X(w * 0.62), yy), (X(w - 1.5), yy), max(1, S // 2))
    pygame.draw.rect(big, (255, 255, 255, 70), (X(w * 0.12), Y(h * 0.18), X(w * 0.5) - X(w * 0.12), int(h * 0.26 * S)), border_radius=S)
    # rim and cap (a Safe-Lock style lid on a hinge strap)
    rim = pygame.Rect(X(-2), Y(6), (w + 4) * S, 4 * S)
    cm = pygame.Surface(rim.size, pygame.SRCALPHA)
    pygame.draw.rect(cm, (255, 255, 255, 255), cm.get_rect(), border_radius=S)
    big.blit(shaded_mask(cm, (226, 228, 224), cyl_profile(rim.w, spec_k=0.3), 235), rim.topleft)
    if open_:
        lid = pygame.Rect(X(-12), Y(-2), 9 * S, (w + 2) * S)
        lmk = pygame.Surface(lid.size, pygame.SRCALPHA)
        pygame.draw.rect(lmk, (255, 255, 255, 255), lmk.get_rect(), border_radius=3 * S)
        big.blit(shaded_mask(lmk, capc, cyl_profile(lid.w, 0.35, 0.12, 0.35, 0.7), 240), lid.topleft)
        big.blit(soft_edge(lmk, lighten(capc, -0.45), 2), lid.topleft)
        pygame.draw.rect(big, (200, 204, 200, 230), (X(-4), Y(4), 4 * S, 3 * S))
    else:
        lid = pygame.Rect(X(-3), Y(0), (w + 6) * S, 7 * S)
        lmk = pygame.Surface(lid.size, pygame.SRCALPHA)
        pygame.draw.rect(lmk, (255, 255, 255, 255), lmk.get_rect(), border_radius=2 * S)
        vert = np.linspace(1.15, 0.8, lid.h).astype(np.float32) if np is not None else None
        big.blit(shaded_mask(lmk, capc, cyl_profile(lid.w, 0.3, 0.1, 0.35, 0.72), 245, vert), lid.topleft)
        big.blit(soft_edge(lmk, lighten(capc, -0.45), 2), lid.topleft)
        tab = pygame.Rect(X(w + 3), Y(1), 4 * S, 5 * S)
        pygame.draw.rect(big, lighten(capc, -0.15) + (240,), tab, border_radius=S)
        pygame.draw.rect(big, lighten(capc, -0.5) + (200,), (X(-6), Y(2), 3 * S, 4 * S), border_radius=S)
    sp = pygame.transform.smoothscale(big, (w + 2 * pad, h + pad + 6))
    return _tubes.put(key, sp)


def tube(s, x, y, w, h, liquid, level, cap, open_):
    sp = tube_sprite(int(w), int(h), liquid, level, cap, open_)
    sh = contact_shadow(int(w * 1.1), 6, 70)
    s.blit(sh, (int(x + w * 0.5 - sh.get_width() / 2 + 3), int(y + h - sh.get_height() / 2 + 1)))
    s.blit(sp, (int(x) - 14, int(y) - 8))


# ------------------------------------------------------------------ pipette (Gilson-style P20)
_pip = LRU(20)


def pipette_body(k):
    """The pipette without its tip, as a cached sprite; the tip end is at (cx, by)."""
    key = round(k, 2)
    sp = _pip.get(key)
    if sp is not None:
        return sp
    w, h = int(46 * k), int(210 * k)
    big = pygame.Surface((w * S, h * S), pygame.SRCALPHA)
    cx = w * S // 2
    u = k * S

    def part(rect, col, r, spec=0.3, edge=0.62, alpha=255):
        m = pygame.Surface((int(rect[2]), int(rect[3])), pygame.SRCALPHA)
        pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=int(r))
        big.blit(shaded_mask(m, col, cyl_profile(m.get_width(), spec, 0.08, 0.4, edge), alpha), (int(rect[0]), int(rect[1])))
        big.blit(soft_edge(m, lighten(col, -0.5), max(1, int(u * 0.8))), (int(rect[0]), int(rect[1])))
    # plunger button (yellow for a P20), rod, body with grip, display, ejector, shaft
    part((cx - 9 * u, 2 * u, 18 * u, 13 * u), (238, 200, 40), 4 * u)
    part((cx - 2.5 * u, 14 * u, 5 * u, 14 * u), (200, 204, 210), 2 * u)
    part((cx - 13 * u, 26 * u, 26 * u, 98 * u), (226, 228, 232), 10 * u)
    part((cx - 11 * u, 40 * u, 22 * u, 40 * u), (190, 194, 202), 8 * u, 0.3, 0.5)         # rubber grip
    for i in range(7):
        yy = int(44 * u + i * 5 * u)
        pygame.draw.line(big, (160, 164, 172, 200), (cx - 9 * u, yy), (cx + 9 * u, yy), max(1, int(u)))
    disp = pygame.Rect(int(cx - 8 * u), int(86 * u), int(16 * u), int(24 * u))
    pygame.draw.rect(big, (30, 32, 36), disp, border_radius=int(2 * u))
    for i, d in enumerate("020"):
        f = pygame.font.SysFont("consolas", max(8, int(7 * u)), bold=True)
        t = f.render(d, True, (240, 240, 230))
        big.blit(t, (disp.centerx - t.get_width() // 2, disp.y + int(1 * u) + i * int(7.5 * u)))
    part((cx + 9 * u, 30 * u, 8 * u, 30 * u), (214, 216, 220), 3 * u)                   # ejector button
    part((cx - 6 * u, 122 * u, 12 * u, 46 * u), (232, 234, 236), 3 * u)                  # shaft
    part((cx + 4 * u, 126 * u, 4 * u, 40 * u), (200, 204, 210), 2 * u)                   # ejector arm
    part((cx - 3.5 * u, 166 * u, 7 * u, 4 * u), (210, 212, 216), 1 * u)                  # tip cone
    sp = pygame.transform.smoothscale(big, (w, h))
    return _pip.put(key, (sp, w // 2, int(170 * k)))


def pipette(s, tip, liquid, amount, plunger, k):
    x, y = tip
    # disposable tip: clear polypropylene cone with a filling of liquid
    L = 46 * k
    pts = [(x, y), (x - 4.6 * k, y - L), (x + 4.6 * k, y - L)]
    R.aa_poly(s, (228, 232, 230), pts, 0, None)
    if liquid is not None and amount > 0:
        fy = y - (L - 6 * k) * min(1.0, amount)
        f = (y - fy) / L
        lp = [(x, y), (x - 4.2 * k * f, fy), (x + 4.2 * k * f, fy)]
        if abs(lp[1][0] - lp[2][0]) >= 1:
            R.aa_poly(s, tuple(liquid[:3]), lp, 0, None)
    R.aa_line(s, (255, 255, 255), (x - 2.2 * k, y - L + 4), (x - 0.6 * k, y - 6 * k), 1)
    R.aa_line(s, (140, 146, 150), pts[0], pts[1], 1)
    R.aa_line(s, (140, 146, 150), pts[0], pts[2], 1)
    sp, cx, by = pipette_body(k)
    s.blit(sp, (int(x - cx), int(y - L - by + int(2 * k) - plunger * 0)))


# ------------------------------------------------------------------ petri dish
_petri = LRU(40)


def petri_sprite(r, agar):
    key = (r, agar)
    sp = _petri.get(key)
    if sp is not None:
        return sp
    n = 2 * r + 24
    big = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
    c = n * S // 2
    R_ = r * S
    # polystyrene rim (clear), agar disc with a darker meniscus edge and subsurface glow
    pygame.draw.circle(big, (200, 210, 214, 120), (c, c), R_ + 8 * S)
    pygame.draw.circle(big, (236, 242, 244, 90), (c, c), R_ + 5 * S)
    disc = pygame.Surface((2 * R_, 2 * R_), pygame.SRCALPHA)
    if np is not None:
        yy, xx = np.mgrid[0:2 * R_, 0:2 * R_].astype(np.float32)
        d = np.sqrt((xx - R_) ** 2 + (yy - R_) ** 2) / R_
        n_ = R.value_noise(2 * R_, 2 * R_, 60 * S / 3, 7, 3)
        shade = 1.06 - 0.16 * d ** 3 + (n_ - 0.5) * 0.07 - 0.05 * ((xx + yy) / (2 * R_) - 1)
        rgb = np.clip(np.array(agar, dtype=np.float32)[None, None, :] * shade[..., None], 0, 255).astype(np.uint8)
        pygame.surfarray.pixels3d(disc)[:] = rgb.transpose(1, 0, 2)
        a = np.where(d <= 1.0, 245, 0).astype(np.uint8)
        pygame.surfarray.pixels_alpha(disc)[:] = a.T
    else:
        pygame.draw.circle(disc, agar, (R_, R_), R_)
    big.blit(disc, (c - R_, c - R_))
    pygame.draw.circle(big, lighten(agar, -0.25) + (160,), (c, c), R_, 2 * S)
    # rim highlights (light from the upper left) and the dish wall
    pygame.draw.circle(big, (130, 140, 146, 170), (c, c), R_ + 8 * S, 2 * S)
    pygame.draw.arc(big, (255, 255, 255, 230), (c - R_ - 6 * S, c - R_ - 6 * S, 2 * R_ + 12 * S, 2 * R_ + 12 * S), 1.7, 3.0, 3 * S)
    pygame.draw.arc(big, (255, 255, 255, 140), (c - R_ - 3 * S, c - R_ - 3 * S, 2 * R_ + 6 * S, 2 * R_ + 6 * S), 4.8, 5.5, 2 * S)
    sp = pygame.transform.smoothscale(big, (n, n))
    return _petri.put(key, sp)


def petri(s, c, r, agar):
    sp = petri_sprite(int(r), tuple(agar[:3]))
    sh = R.soft_shadow(int(r * 2 + 16), int(r * 2 + 16), int(r + 8), (20, 18, 30), 60, 10)
    s.blit(sh, (int(c[0] - sh.get_width() / 2 + 6), int(c[1] - sh.get_height() / 2 + 8)))
    s.blit(sp, (int(c[0]) - sp.get_width() // 2, int(c[1]) - sp.get_height() // 2))


# ------------------------------------------------------------------ materials for panels
_mat = LRU(200)


def steel(w, h, r=6, tone=(196, 200, 206), brushed=True):
    """Brushed stainless steel panel with a bevel."""
    key = ("steel", w, h, r, tone, brushed)
    sp = _mat.get(key)
    if sp is not None:
        return sp
    sp = pygame.Surface((w, h), pygame.SRCALPHA)
    if np is not None:
        rng = np.random.default_rng(w * 7 + h)
        streak = rng.normal(0, 1, (1, h)).astype(np.float32)
        streak = np.repeat(streak, w, axis=0)
        fine = rng.normal(0, 1, (w, h)).astype(np.float32) * 0.35
        lv = np.linspace(1.12, 0.86, h, dtype=np.float32)[None, :]
        lh = 1 + 0.06 * np.cos(np.linspace(-1.2, 1.8, w, dtype=np.float32))[:, None]
        base = np.array(tone, dtype=np.float32)
        rgb = base[None, None, :] * (lv * lh)[..., None] + (streak * (5 if brushed else 1.5) + fine * 3)[..., None]
        pygame.surfarray.pixels3d(sp)[:] = np.clip(rgb, 0, 255).astype(np.uint8)
        pygame.surfarray.pixels_alpha(sp)[:] = 255
    else:
        sp.fill(tone)
    m = R.rrect_surf(w, h, (255, 255, 255), None, 0, r, 0, False)
    sp.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    edge = R.rrect_surf(w, h, None, (90, 94, 102), 1, r, 0, False)
    sp.blit(edge, (0, 0))
    hl = R.rrect_surf(max(2, w - 4), max(2, h - 4), None, (255, 255, 255, 150), 1, max(0, r - 1), 0, False)
    sp.blit(hl, (2, 2), special_flags=0)
    return _mat.put(key, sp)


def plastic(w, h, col, r=8, gloss=0.25):
    """Moulded instrument plastic: soft vertical light, a faint top highlight, a thin darker rim."""
    key = ("plastic", w, h, col, r, gloss)
    sp = _mat.get(key)
    if sp is not None:
        return sp
    sp = R.rrect_surf(w, h, tuple(col), lighten(col, -0.38), 1, r, gloss * 0.6, True).copy()
    return _mat.put(key, sp)


def lcd(w, h, r=4, col=(26, 34, 40)):
    key = ("lcd", w, h, r, col)
    sp = _mat.get(key)
    if sp is not None:
        return sp
    sp = R.rrect_surf(w, h, (60, 62, 68), (24, 24, 28), 1, r, 0.1, False).copy()
    inner = R.rrect_surf(max(2, w - 6), max(2, h - 6), col, None, 0, max(0, r - 2), 0.18, False)
    sp.blit(inner, (3, 3))
    glare = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(glare, (255, 255, 255, 16), [(3, 3), (w * 0.55, 3), (w * 0.3, h - 3), (3, h - 3)])
    sp.blit(glare, (0, 0))
    return _mat.put(key, sp)


def glass(w, h, tint=(214, 232, 238), a=70, r=6):
    """Clear glass or acrylic: faint tint, bright Fresnel edges, one highlight streak."""
    key = ("glass", w, h, tint, a, r)
    sp = _mat.get(key)
    if sp is not None:
        return sp
    sp = R.rrect_surf(w, h, tuple(tint) + (a,), None, 0, r, 0, False).copy()
    sp.blit(R.rrect_surf(w, h, None, (255, 255, 255, 170), 2, r, 0, False), (0, 0))
    sp.blit(R.rrect_surf(w, h, None, (90, 110, 120, 140), 1, r, 0, False), (0, 0))
    sw = max(2, min(7, w // 16))
    streak = R.rrect_surf(sw, max(2, h - 14), (255, 255, 255, 90), None, 0, sw // 2, 0, False)
    sp.blit(streak, (max(4, min(12, w // 10)), 7))
    return _mat.put(key, sp)


# ------------------------------------------------------------------ the photographic lab background
def _bottle(surf, x, base_y, w, h, body, cap, label=True, rng=None):
    neck = max(4, int(w * 0.38))
    pygame.draw.rect(surf, body, (x, base_y - h, w, h), border_radius=max(2, w // 5))
    pygame.draw.rect(surf, body, (x + (w - neck) // 2, base_y - h - int(h * 0.16), neck, int(h * 0.2)))
    pygame.draw.rect(surf, cap, (x + (w - neck) // 2 - 2, base_y - h - int(h * 0.26), neck + 4, int(h * 0.12)), border_radius=2)
    if label:
        pygame.draw.rect(surf, (246, 244, 236), (x + 3, base_y - h * 0.62, w - 6, h * 0.34))
        pygame.draw.line(surf, (120, 120, 130), (x + 6, base_y - h * 0.5), (x + w - 8, base_y - h * 0.5), 2)
    pygame.draw.line(surf, lighten(body, 0.4), (x + w * 0.22, base_y - h + 6), (x + w * 0.22, base_y - 6), 3)


def lab_background(tint):
    """A lab seen past the bench: shelves with bottles, tip boxes and a centrifuge, blurred like a
    photo taken with the worktop in focus. Returns a W x H Surface."""
    rnd = random.Random(12)
    wall = (226, 226, 220)
    wall = tuple(int(wall[i] * 0.86 + tint[i] * 0.14) for i in range(3))
    img = pygame.Surface((W, H))
    img.blit(R.vgrad((W, H), lighten(wall, 0.08), lighten(wall, -0.12)), (0, 0))
    top = H - 70
    # window light on the left
    win = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.rect(win, (255, 252, 236, 70), (40, 50, 240, 250))
    pygame.draw.rect(win, (255, 255, 255, 40), (60, 70, 90, 210))
    img.blit(win, (0, 0))
    # two shelves of reagents
    for sy, n in ((150, 15), (300, 13)):
        pygame.draw.rect(img, (242, 240, 234), (0, sy, W, 10))
        pygame.draw.rect(img, (170, 166, 160), (0, sy + 10, W, 4))
        x = rnd.randint(10, 40)
        while x < W - 40:
            kind = rnd.random()
            if kind < 0.3:      # glass reagent bottle with blue cap (Duran)
                w = rnd.randint(30, 44)
                h = rnd.randint(60, 96)
                _bottle(img, x, sy, w, h, (208, 222, 226), (40, 90, 170))
            elif kind < 0.48:   # brown bottle
                w = rnd.randint(26, 36)
                h = rnd.randint(50, 80)
                _bottle(img, x, sy, w, h, (120, 70, 30), (30, 30, 34))
            elif kind < 0.66:   # white plastic bottle
                w = rnd.randint(28, 40)
                h = rnd.randint(54, 84)
                _bottle(img, x, sy, w, h, (240, 240, 236), rnd.choice([(220, 60, 50), (240, 200, 40), (50, 140, 80)]))
            elif kind < 0.84:   # pipette tip box
                w = rnd.randint(54, 66)
                h = rnd.randint(30, 38)
                lid = rnd.choice([(60, 120, 200), (240, 200, 60), (230, 230, 230), (90, 170, 90)])
                pygame.draw.rect(img, (232, 232, 228), (x, sy - h, w, h), border_radius=3)
                pygame.draw.rect(img, lid, (x - 2, sy - h - 8, w + 4, 10), border_radius=3)
            else:               # cardboard box
                w = rnd.randint(50, 80)
                h = rnd.randint(40, 70)
                pygame.draw.rect(img, (196, 160, 112), (x, sy - h, w, h))
                pygame.draw.rect(img, (246, 244, 236), (x + 8, sy - h + 10, w - 16, 16))
            x += w + rnd.randint(6, 22)
    # benchtop instruments far back: a centrifuge and a vortex
    pygame.draw.rect(img, (236, 236, 232), (W - 260, top - 120, 170, 120), border_radius=14)
    pygame.draw.rect(img, (70, 74, 84), (W - 240, top - 104, 130, 18), border_radius=4)
    pygame.draw.circle(img, (200, 202, 206), (W - 175, top - 50), 30)
    pygame.draw.rect(img, (60, 64, 72), (300, top - 60, 60, 60), border_radius=10)
    pygame.draw.circle(img, (220, 60, 50), (330, top - 66), 12)
    # gas and power rail along the back of the bench
    pygame.draw.rect(img, (214, 214, 210), (0, top - 30, W, 24))
    for x in range(80, W, 200):
        pygame.draw.rect(img, (246, 246, 244), (x, top - 26, 40, 16), border_radius=3)
    img = R.blur_surface(img, 5) if hasattr(R, "blur_surface") else _blur(img, 5)
    # the worktop: dark epoxy resin, in focus, with a soft reflection band and a contact shadow
    if np is not None:
        rng = np.random.default_rng(4)
        wt = np.zeros((W, 70, 3), dtype=np.float32)
        base = np.array((58, 60, 66), dtype=np.float32)
        yy = np.linspace(0, 1, 70, dtype=np.float32)[None, :, None]
        wt[:] = base * (1.25 - 0.45 * yy)
        wt += rng.normal(0, 3.5, (W, 70, 1)).astype(np.float32)
        spk = rng.random((W, 70)) > 0.985
        wt[spk] += 22
        refl = np.exp(-((yy - 0.18) / 0.08) ** 2) * 26
        wt += refl
        wsurf = pygame.surfarray.make_surface(np.clip(wt, 0, 255).astype(np.uint8))
        img.blit(wsurf, (0, top))
    else:
        pygame.draw.rect(img, (58, 60, 66), (0, top, W, 70))
    pygame.draw.line(img, (120, 124, 132), (0, top), (W, top), 2)
    sh = pygame.Surface((W, 14), pygame.SRCALPHA)
    for i in range(14):
        pygame.draw.line(sh, (10, 10, 20, int(70 * (1 - i / 14.0))), (0, i), (W, i))
    img.blit(sh, (0, top + 2))
    # vignette, like a lens
    if np is not None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        v = 1 - 0.22 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * 0.45) / (H * 0.7)) ** 2)
        arr = pygame.surfarray.pixels3d(img)
        arr[:] = np.clip(arr.astype(np.float32) * v.T[..., None], 0, 255).astype(np.uint8)
        del arr
    return img


def _blur(surf, k):
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (max(1, w // k), max(1, h // k)))
    small = pygame.transform.smoothscale(small, (max(1, w // (k + 2)), max(1, h // (k + 2))))
    return pygame.transform.smoothscale(small, (w, h))


# ------------------------------------------------------------------ the board: a lab room seen from above
def lab_room(ring):
    """Top-down lab: a speckled vinyl floor, walls at the edges and a continuous resin bench
    running round the room under `ring` (outer Rect, inner Rect). Returns a W x H Surface."""
    outer, inner = ring
    img = pygame.Surface((W, H))
    if np is None:
        img.fill((200, 204, 200))
        return img
    rng = np.random.default_rng(8)
    # floor: pale grey-green vinyl with speckles and soft light from the window side
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    base = np.array((206, 212, 204), dtype=np.float32)
    light = 1.04 - 0.10 * (xx / W) - 0.06 * (yy / H)
    fl = base[None, None, :] * light[..., None] + rng.normal(0, 3, (H, W, 1)).astype(np.float32)
    spk = rng.random((H, W))
    fl[spk > 0.992] -= 40
    fl[spk < 0.006] += 25
    n = R.value_noise(W, H, 120, 3, 2)
    fl += (n[..., None] - 0.5) * 10
    # floor seams every 160 px
    for x in range(0, W, 160):
        fl[:, x:x + 1] -= 10
    for y in range(0, H, 160):
        fl[y:y + 1, :] -= 10
    img = R.to_surface(fl)
    # walls round the edge
    wall = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.rect(wall, (232, 230, 222, 255), (0, 0, W, H))
    pygame.draw.rect(wall, (0, 0, 0, 0), outer.inflate(16, 16), border_radius=18)
    img.blit(wall, (0, 0))
    pygame.draw.rect(img, (190, 186, 178), outer.inflate(16, 16), 3, border_radius=18)
    # the bench ring: dark resin worktop with an edge highlight and a shadow on the floor
    sh = R.soft_shadow(inner.w, inner.h, 16, (10, 10, 20), 90, 10)
    img.blit(sh, (inner.x - 20 + 4, inner.y - 20 + 6))
    ringsurf = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.rect(ringsurf, (64, 66, 72, 255), outer, border_radius=14)
    pygame.draw.rect(ringsurf, (0, 0, 0, 0), inner, border_radius=12)
    tex = pygame.Surface((W, H), pygame.SRCALPHA)
    t = rng.normal(0, 4, (W, H)).astype(np.float32)
    arr = np.clip(np.stack([t] * 3, axis=2) + 128, 0, 255).astype(np.uint8)
    pygame.surfarray.pixels3d(tex)[:] = arr
    pygame.surfarray.pixels_alpha(tex)[:] = 255
    ringsurf.blit(tex, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    ringsurf.blit(tex, (0, 0), special_flags=pygame.BLEND_RGB_ADD) if False else None
    img.blit(ringsurf, (0, 0))
    pygame.draw.rect(img, (120, 124, 132), outer, 2, border_radius=14)
    pygame.draw.rect(img, (40, 42, 48), inner, 2, border_radius=12)
    return img
