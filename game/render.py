# -*- coding: utf-8 -*-
"""Low-level rendering: anti-aliased shapes, gradients, soft shadows, glows and
procedural textures (numpy noise). Every expensive result is cached by size and colour,
so drawing a shape a second time costs one blit."""
import math
from collections import OrderedDict
import pygame
import pygame.gfxdraw as gd

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None


class LRU:
    def __init__(self, n):
        self.n = n
        self.d = OrderedDict()

    def get(self, k):
        v = self.d.get(k)
        if v is not None:
            self.d.move_to_end(k)
        return v

    def put(self, k, v):
        self.d[k] = v
        if len(self.d) > self.n:
            self.d.popitem(last=False)
        return v


def _c(col, k):
    """Lighten (k > 0) or darken (k < 0) a colour."""
    if k >= 0:
        return tuple(int(c + (255 - c) * k) for c in col[:3])
    return tuple(int(c * (1 + k)) for c in col[:3])


lighten = _c


def vgrad(size, top, bottom):
    """Vertical linear gradient surface (no alpha)."""
    w, h = max(1, int(size[0])), max(1, int(size[1]))
    g = pygame.Surface((1, 2))
    g.set_at((0, 0), top[:3])
    g.set_at((0, 1), bottom[:3])
    return pygame.transform.smoothscale(g, (w, h))


# ------------------------------------------------------------------ rounded rectangles
_rr = LRU(900)


def rrect_surf(w, h, fill, border, bw, r, shade=0.07, gloss=True):
    """Anti-aliased rounded rectangle (2x supersampled), with an optional soft vertical shading
    of the fill and a thin top highlight. Returns a SRCALPHA surface of size (w, h)."""
    key = (w, h, fill, border, bw, r, shade, gloss)
    s = _rr.get(key)
    if s is not None:
        return s
    S = 2
    W2, H2 = w * S, h * S
    big = pygame.Surface((W2, H2), pygame.SRCALPHA)
    R = max(0, min(r * S, W2 // 2, H2 // 2))
    inset = 0
    if border is not None and bw:
        pygame.draw.rect(big, border[:3] + (255,), big.get_rect(), border_radius=R)
        inset = bw * S
    if fill is not None:
        inner = pygame.Rect(inset, inset, W2 - 2 * inset, H2 - 2 * inset)
        if inner.w > 0 and inner.h > 0:
            mask = pygame.Surface(inner.size, pygame.SRCALPHA)
            ir = max(0, R - inset)
            pygame.draw.rect(mask, (255, 255, 255, fill[3] if len(fill) > 3 else 255), mask.get_rect(), border_radius=ir)
            if shade:
                tmp = pygame.Surface(inner.size, pygame.SRCALPHA)
                tmp.blit(vgrad(inner.size, _c(fill, shade), _c(fill, -shade * 0.8)), (0, 0))
                tmp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                mask = tmp
            else:
                mask.fill(fill[:3] + (255,), special_flags=pygame.BLEND_RGBA_MULT)
            if inset:
                pygame.draw.rect(big, (0, 0, 0, 0), inner, border_radius=ir)
            big.blit(mask, inner.topleft)
            if gloss and inner.h > 10 * S:
                hl = pygame.Surface((inner.w - 2 * ir if inner.w > 2 * ir + 4 else inner.w, max(2, S)), pygame.SRCALPHA)
                hl.fill((255, 255, 255, 70))
                big.blit(hl, (inner.x + (inner.w - hl.get_width()) // 2, inner.y + S))
    elif border is not None and bw:
        inner = pygame.Rect(inset, inset, W2 - 2 * inset, H2 - 2 * inset)
        if inner.w > 0 and inner.h > 0:
            pygame.draw.rect(big, (0, 0, 0, 0), inner, border_radius=max(0, R - inset))
    s = pygame.transform.smoothscale(big, (w, h))
    return _rr.put(key, s)


# ------------------------------------------------------------------ shadows and glows
_sh = LRU(300)


def soft_shadow(w, h, r, col=(60, 40, 100), a=70, blur=8):
    key = (w, h, r, col, a, blur)
    s = _sh.get(key)
    if s is not None:
        return s
    pad = blur * 2
    base = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    pygame.draw.rect(base, col + (a,), (pad, pad, w, h), border_radius=r)
    k = max(1, blur // 2)
    small = pygame.transform.smoothscale(base, (max(1, base.get_width() // k), max(1, base.get_height() // k)))
    small = pygame.transform.smoothscale(small, (max(1, small.get_width() // 2), max(1, small.get_height() // 2)))
    s = pygame.transform.smoothscale(small, base.get_size())
    return _sh.put(key, s)


_glow = LRU(200)


def glow_sprite(r, col, strength=1.0):
    """Radial glow (bright centre fading to nothing), for additive blending."""
    r = max(2, int(r))
    key = (r, col, round(strength, 2))
    s = _glow.get(key)
    if s is not None:
        return s
    n = 2 * r
    if np is not None:
        y, x = np.mgrid[0:n, 0:n].astype(np.float32)
        d = np.sqrt((x - r + 0.5) ** 2 + (y - r + 0.5) ** 2) / r
        a = np.clip(1 - d, 0, 1) ** 2 * strength
        arr = np.zeros((n, n, 3), dtype=np.uint8)
        for i in range(3):
            arr[..., i] = np.clip(col[i] * a, 0, 255).astype(np.uint8)
        s = pygame.surfarray.make_surface(arr.transpose(1, 0, 2))
    else:
        s = pygame.Surface((n, n))
        for k in range(r, 0, -1):
            f = (1 - k / r) ** 2 * strength
            pygame.draw.circle(s, tuple(int(c * f) for c in col), (r, r), k)
    return _glow.put(key, s)


def glow(surf, c, r, col, strength=1.0):
    sp = glow_sprite(r, col, strength)
    surf.blit(sp, (int(c[0]) - sp.get_width() // 2, int(c[1]) - sp.get_height() // 2), special_flags=pygame.BLEND_ADD)


_hl = LRU(200)


def sphere_light(r, a=80):
    """Soft highlight (upper left) and core shade (lower right) to make a disc look round."""
    r = max(2, int(r))
    key = (r, a)
    s = _hl.get(key)
    if s is not None:
        return s
    n = 2 * r + 2
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    if np is not None:
        y, x = np.mgrid[0:n, 0:n].astype(np.float32)
        cx = cy = r + 1
        d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / r
        inside = d <= 1.0
        dh = np.sqrt((x - cx + 0.38 * r) ** 2 + (y - cy + 0.42 * r) ** 2) / (0.62 * r)
        hi = np.clip(1 - dh, 0, 1) ** 1.6 * a
        sh = np.clip((d - 0.55) / 0.45, 0, 1) ** 2 * a * 0.55 * np.clip(((x - cx) + (y - cy)) / r + 0.6, 0, 1)
        alpha = np.where(inside, np.maximum(hi, sh), 0).astype(np.uint8)
        rgb = np.stack([np.where(hi >= sh, 255, 20).astype(np.uint8)] * 3, axis=2)
        pygame.surfarray.pixels3d(s)[:] = rgb.transpose(1, 0, 2)
        pygame.surfarray.pixels_alpha(s)[:] = alpha.T
    return _hl.put(key, s)


# ------------------------------------------------------------------ anti-aliased primitives
def _alpha_target(s):
    return bool(s.get_flags() & pygame.SRCALPHA)


def aa_circle(s, col, c, r, w=2, border=(31, 27, 51), shade=True):
    x, y, r = int(round(c[0])), int(round(c[1])), int(round(r))
    if r < 1:
        return
    if _alpha_target(s):      # gfxdraw blends badly into transparent pixels: use a supersampled sprite
        s.blit(_ellipse_surf(2 * r + 1, 2 * r + 1, tuple(col) if col is not None else None,
                             tuple(border) if (border is not None and w) else None, w), (x - r, y - r))
        ri = r - (w if (w and border is not None) else 0)
        if col is not None and shade and ri >= 5:
            s.blit(sphere_light(ri, 70 if ri > 10 else 50), (x - ri - 1, y - ri - 1))
        return
    if col is None:
        if w and border is not None:
            aa_ring(s, (x, y), r, w, border)
        return
    if w and border is not None:
        gd.filled_circle(s, x, y, r, border)
        gd.aacircle(s, x, y, r, border)
        ri = r - w
    else:
        ri = r
    if col is not None and ri >= 1:
        gd.filled_circle(s, x, y, ri, col)
        gd.aacircle(s, x, y, ri, col)
        if shade and ri >= 5:
            sp = sphere_light(ri, 70 if ri > 10 else 50)
            s.blit(sp, (x - ri - 1, y - ri - 1))
    elif col is None and ri >= 1 and w:
        pass


_ell = LRU(300)


def _ellipse_surf(w, h, col, border, bw):
    key = (w, h, col, border, bw)
    sf = _ell.get(key)
    if sf is None:
        S = 3
        big = pygame.Surface((w * S, h * S), pygame.SRCALPHA)
        if border is not None and bw:
            pygame.draw.ellipse(big, tuple(border[:3]) + (255,), big.get_rect())
            inner = big.get_rect().inflate(-2 * bw * S, -2 * bw * S)
            if col is not None:
                if inner.w > 0 and inner.h > 0:
                    pygame.draw.ellipse(big, tuple(col[:3]) + ((col[3],) if len(col) > 3 else (255,)), inner)
            elif inner.w > 0 and inner.h > 0:
                pygame.draw.ellipse(big, (0, 0, 0, 0), inner)
        elif col is not None:
            pygame.draw.ellipse(big, tuple(col[:3]) + ((col[3],) if len(col) > 3 else (255,)), big.get_rect())
        sf = _ell.put(key, pygame.transform.smoothscale(big, (w, h)))
    return sf


def aa_ellipse(s, col, rect, w=2, border=(31, 27, 51)):
    """Anti-aliased ellipse (supersampled, cached). col=None draws only the outline."""
    rect = pygame.Rect(rect)
    if rect.w < 2 or rect.h < 2:
        return
    s.blit(_ellipse_surf(rect.w, rect.h, tuple(col) if col is not None else None,
                         tuple(border) if (border is not None and w) else None, w), rect.topleft)


def aa_ring(s, c, r, w, col):
    """Anti-aliased ring (outline only) of radius r and width w."""
    r = int(round(r))
    if r < 1:
        return
    s.blit(_ellipse_surf(2 * r + 1, 2 * r + 1, None, tuple(col), max(1, int(w))), (int(round(c[0])) - r, int(round(c[1])) - r))


def aa_poly(s, col, pts, w=2, border=(31, 27, 51)):
    pts = [(int(round(x)), int(round(y))) for x, y in pts]
    if len(pts) < 3:
        return
    if _alpha_target(s):
        if col is not None:
            pygame.draw.polygon(s, col, pts)
        if w and border is not None:
            pygame.draw.polygon(s, border, pts, w)
        return
    if col is not None:
        gd.filled_polygon(s, pts, col)
        gd.aapolygon(s, pts, col)
    if w and border is not None:
        if w > 1:
            n = len(pts)
            for i in range(n):
                aa_line(s, border, pts[i], pts[(i + 1) % n], w)
            for p in pts:
                gd.filled_circle(s, p[0], p[1], max(0, w // 2), border)
        else:
            gd.aapolygon(s, pts, border)


def aa_line(s, col, a, b, w=2):
    if _alpha_target(s):
        pygame.draw.line(s, col, a, b, max(1, int(w)))
        return
    if w <= 1:
        pygame.draw.aaline(s, col, a, b)
        return
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L * w / 2, dx / L * w / 2
    pts = [(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)]
    gd.filled_polygon(s, pts, col)
    gd.aapolygon(s, pts, col)


# ------------------------------------------------------------------ procedural textures
def value_noise(w, h, scale, seed=0, octaves=3):
    """Smooth noise in [0, 1], shape (h, w), from upscaled random grids."""
    if np is None:
        return None
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), dtype=np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        gw, gh = max(2, int(w / scale) + 2), max(2, int(h / scale) + 2)
        g = (rng.random((gh, gw)) * 255).astype(np.uint8)
        surf = pygame.surfarray.make_surface(np.stack([g.T] * 3, axis=2))
        up = pygame.transform.smoothscale(surf, (w, h))
        out += pygame.surfarray.array3d(up)[..., 0].T.astype(np.float32) / 255.0 * amp
        tot += amp
        amp *= 0.5
        scale /= 2.5
    return out / tot


def grain(w, h, amount=10, seed=1):
    """Fine film-grain overlay as a SRCALPHA surface (neutral grey, low alpha)."""
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    if np is None:
        return s
    rng = np.random.default_rng(seed)
    a = (rng.random((w, h)) * amount).astype(np.uint8)
    pygame.surfarray.pixels3d(s)[:] = np.where(rng.random((w, h, 1)) > 0.5, 255, 0).astype(np.uint8)
    pygame.surfarray.pixels_alpha(s)[:] = a
    return s


def to_surface(rgb):
    """numpy (h, w, 3) float/uint8 -> Surface."""
    return pygame.surfarray.make_surface(np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 0, 2))
