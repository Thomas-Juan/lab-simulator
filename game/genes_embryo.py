# -*- coding: utf-8 -*-
"""Zebrafish embryo, lateral view, head to the left, dechorionated (24 or 48 hpf).

Rendered once per size at 3x with numpy shading (a round body, a glossy granular yolk) and
smoothscaled down, then cached. In situ stains (NBT/BCIP purple) are separate cached layers
whose opacity is set per frame, so a developing stain costs only a few blits."""
import math
import random
import pygame
import render as R
from core import INK, mix, clamp

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

S = 3                      # supersampling factor
STAIN = (58, 34, 104)      # NBT/BCIP precipitate: dense blue-purple
EDGE = (78, 70, 62)        # refractive edge of tissue in brightfield
_cache = {}

PROFILE = {
    24: [(0, 0), (0.015, 0.055), (0.05, 0.088), (0.12, 0.096), (0.19, 0.082), (0.26, 0.066), (0.45, 0.056),
         (0.7, 0.041), (0.88, 0.022), (0.97, 0.008), (1.0, 0.0)],
    48: [(0, 0), (0.015, 0.06), (0.05, 0.093), (0.12, 0.1), (0.2, 0.086), (0.27, 0.068), (0.45, 0.057),
         (0.7, 0.042), (0.88, 0.022), (0.97, 0.008), (1.0, 0.0)],
}


def _interp(prof, t):
    for (a, wa), (b, wb) in zip(prof, prof[1:]):
        if a <= t <= b:
            f = (t - a) / (b - a)
            f = f * f * (3 - 2 * f)
            return wa + (wb - wa) * f
    return 0.0


class Geo:
    """Embryo geometry in sprite pixels (3x scale) for a given length L (display pixels)."""
    def __init__(self, L, hpf):
        self.L, self.hpf = L, hpf
        self.k = L * S
        self.w = int(L * 1.08 * S)
        self.h = int(L * 0.46 * S)
        self.x0 = int(L * 0.04 * S)
        self.cy = int(L * 0.17 * S)
        self.prof = PROFILE[48 if hpf >= 48 else 24]
        old = hpf >= 48
        self.yolk = (0.25, 0.105, 0.13, 0.1) if old else (0.27, 0.122, 0.165, 0.122)
        self.ext = (0.36, 0.56, 0.066) if old else (0.39, 0.68, 0.086)
        self.eye = (0.08, 0.012, 0.048) if old else (0.082, 0.036, 0.041)
        self.otic = (0.152, -0.012) if old else (0.158, 0.01)
        self.peri = (0.115, 0.118, 0.085, 0.058) if old else (0.088, 0.12, 0.042, 0.026)

    def P(self, u, v):
        return (self.x0 + u * self.k, self.cy + v * self.k)

    def spine(self, t):
        if self.hpf >= 48:
            return 0.012 * max(0.0, (0.22 - t) / 0.22)
        return 0.05 * max(0.0, (0.24 - t) / 0.24) ** 1.5

    def half(self, t):
        return _interp(self.prof, t)

    def body(self, n=120):
        top = [self.P(i / n, self.spine(i / n) - self.half(i / n)) for i in range(n + 1)]
        bot = [self.P(i / n, self.spine(i / n) + self.half(i / n)) for i in range(n + 1)]
        return top + bot[::-1]

    def fin(self):
        d0, v0 = (0.3, 0.6) if self.hpf >= 48 else (0.34, 0.66)
        fh = lambda t: 0.012 + 0.028 * min(1.0, (t - d0) / 0.25) if t > d0 else 0.012
        dors = [self.P(t, self.spine(t) - self.half(t) - fh(t)) for t in [d0 + i * (1.0 - d0) / 40 for i in range(41)]]
        tip = [self.P(1.0 + 0.03 * math.sin(a), self.spine(1.0) - 0.04 * math.cos(a)) for a in [i * math.pi / 8 for i in range(1, 8)]]
        vfh = lambda t: 0.01 + 0.026 * min(1.0, (t - v0) / 0.2)
        vent = [self.P(t, self.spine(t) + self.half(t) + vfh(t)) for t in [1.0 - i * (1.0 - v0) / 30 for i in range(31)]]
        return [self.P(d0 - 0.01, self.spine(d0) - self.half(d0) + 0.004)] + dors + tip + vent + [self.P(v0 - 0.01, self.spine(v0) + self.half(v0) - 0.004)]

    def ext_poly(self):
        a, b, th = self.ext
        yc, ry = self.yolk[1], self.yolk[3]
        ts = [a - 0.06 + i * (b - a + 0.06) / 30 for i in range(31)]
        top = [self.P(t, self.spine(t) + self.half(t) * 0.55) for t in ts]
        bot = []
        for t in reversed(ts):
            f = max(0.0, (t - a) / (b - a))
            bot.append(self.P(t, self.spine(t) + self.half(t) * 0.55 + th * (1 - f ** 2.2) + 0.012))
        return top + bot


def _shade_layer(g, mask_surf, base, cyl=True, yolk=False):
    """Colour a mask with numpy shading. cyl: round across the body axis; yolk: glossy ellipsoid."""
    w, h = mask_surf.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    if np is None:
        out.fill(base + (255,))
        out.blit(mask_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return out
    a = pygame.surfarray.array_alpha(mask_surf).T.astype(np.float32) / 255.0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    if yolk:
        u, v, rx, ry = g.yolk
        cx, cy = g.P(u, v)
        d = np.sqrt(((xx - cx) / (rx * g.k)) ** 2 + ((yy - cy) / (ry * g.k)) ** 2)
        shade = 1.08 - 0.28 * np.clip(d, 0, 1.4) ** 2
        hx, hy = cx - 0.45 * rx * g.k, cy - 0.5 * ry * g.k
        hl = np.exp(-(((xx - hx) / (0.35 * rx * g.k)) ** 2 + ((yy - hy) / (0.25 * ry * g.k)) ** 2)) * 0.25
        a0, b0, th = g.ext
        t = (xx - g.x0) / g.k
        ts = np.linspace(0, 1, 200)
        sp = np.array([g.spine(x) for x in ts])
        hw = np.array([g.half(x) for x in ts])
        top = g.cy + (np.interp(t, ts, sp) + np.interp(t, ts, hw) * 0.55) * g.k
        f = np.clip((t - a0) / (b0 - a0), 0, 1)
        bot = top + (th * (1 - f ** 2.2) + 0.012) * g.k
        mid, half_ = (top + bot) / 2, np.maximum((bot - top) / 2, 1)
        ext_shade = 1.06 - 0.26 * np.clip((yy - mid) / half_, -1.3, 1.3) ** 2
        shade = np.where(d <= 1.0, shade, ext_shade)
        n = R.value_noise(w, h, 5 * S, 13, 2)
        fine = R.value_noise(w, h, 1.6 * S, 14, 1)
        shade = shade + np.where(d <= 1.0, hl * 0.6, 0) + (n - 0.5) * 0.16 + (fine - 0.5) * 0.14
    else:
        t = np.clip((xx - g.x0) / g.k, 0, 1)
        ts = np.linspace(0, 1, 200)
        sp = np.array([g.spine(x) for x in ts])
        hw = np.array([max(1e-3, g.half(x)) for x in ts])
        sy = g.cy + np.interp(t, ts, sp) * g.k
        hh = np.interp(t, ts, hw) * g.k
        rel = np.clip((yy - sy) / hh, -1.4, 1.4)
        shade = 1.06 - 0.22 * rel ** 2 - 0.06 * rel
        shade = shade * (0.8 + 0.2 * np.clip((t - 0.04) / 0.3, 0, 1)) * (1 - 0.06 * np.clip(rel, 0, 1))
        n = R.value_noise(w, h, 9 * S, 17, 2)
        fib = np.sin(yy / (1.1 * S) + n * 6) * 0.025
        shade = shade + (n - 0.5) * 0.07 + fib
    rgb = np.array(base, dtype=np.float32)[None, None, :] * shade[..., None]
    pygame.surfarray.pixels3d(out)[:] = np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 0, 2)
    pygame.surfarray.pixels_alpha(out)[:] = (a * 255).astype(np.uint8).T
    return out


def _blur_arr(a, k):
    """Blur a float array (h, w) in 0..1 by scaling down by k and back up (cheap and smooth)."""
    h, w = a.shape
    g = np.clip(a * 255, 0, 255).astype(np.uint8)
    surf = pygame.surfarray.make_surface(np.stack([g.T] * 3, axis=2))
    small = pygame.transform.smoothscale(surf, (max(2, int(w / k)), max(2, int(h / k))))
    small = pygame.transform.smoothscale(small, (max(2, int(w / (k * 1.6))), max(2, int(h / (k * 1.6)))))
    up = pygame.transform.smoothscale(small, (w, h))
    return pygame.surfarray.array3d(up)[..., 0].T.astype(np.float32) / 255.0


def _refract(big, masks, k=7.0, dark=0.42, halo=70):
    """Brightfield edges: tissue looks darker just inside its outline (light is bent away) and a faint
    bright halo sits just outside. masks: list of float arrays (h, w), 0..1."""
    if np is None:
        return
    rgb = pygame.surfarray.pixels3d(big)
    al = pygame.surfarray.pixels_alpha(big)
    rim_all = None
    halo_all = None
    for m in masks:
        b = _blur_arr(m, k)
        rim = np.clip((m - b) * 2.6, 0, 1)
        hal = np.clip((b - m) * 2.0, 0, 1) * (1 - m)
        rim_all = rim if rim_all is None else np.maximum(rim_all, rim)
        halo_all = hal if halo_all is None else np.maximum(halo_all, hal)
    f = (1 - dark * rim_all).T[..., None]
    rgb[:] = np.clip(rgb.astype(np.float32) * f, 0, 255).astype(np.uint8)
    hz = (halo_all.T * halo).astype(np.uint8)
    empty = al < hz
    rgb[empty] = 255
    al[empty] = hz[empty]
    del rgb, al


def _mask_arr(size, pts_list):
    m = pygame.Surface(size, pygame.SRCALPHA)
    for pts in pts_list:
        pygame.draw.polygon(m, (255, 255, 255, 255), pts)
    return pygame.surfarray.array_alpha(m).T.astype(np.float32) / 255.0


def _poly_mask(size, pts):
    m = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.polygon(m, (255, 255, 255, 255), pts)
    return m


def _ellipse_pts(g, u, v, rx, ry, n=48, rot=0.0):
    out = []
    for i in range(n):
        a = i * math.tau / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        x, y = x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot)
        out.append(g.P(u + x, v + y))
    return out


def _sprite(L, hpf, pigment):
    """The embryo as a brightfield photograph: translucent grey-beige tissue, a denser granular
    yolk, structures visible as soft changes in density, edges from refraction (no drawn lines)."""
    key = ("sprite", L, hpf, pigment)
    if key in _cache:
        return _cache[key]
    g = Geo(L, hpf)
    size = (g.w, g.h)
    big = pygame.Surface(size, pygame.SRCALPHA)
    soft = (150, 140, 126)
    lw = max(2, int(1.2 * S))
    # median fin fold: almost clear, fine rays
    fin = g.fin()
    pygame.draw.polygon(big, (232, 228, 218, 95), fin)
    rays = pygame.Surface(size, pygame.SRCALPHA)
    for i in range(0, len(fin), 2):
        x, y = fin[i]
        pygame.draw.line(rays, (196, 188, 172, 60), (x, y), (x - 0.01 * g.k, y + (0.02 if y < g.cy else -0.02) * g.k), S)
    big.blit(rays, (0, 0))
    # yolk ball and extension: denser, granular, amber-grey
    ypts = _ellipse_pts(g, *g.yolk)
    ymask = _poly_mask(size, ypts)
    pygame.draw.polygon(ymask, (255, 255, 255, 255), g.ext_poly())
    big.blit(_shade_layer(g, ymask, (192, 162, 112), yolk=True), (0, 0))
    # pericardium (clear sac) and the heart inside it
    pu, pv, prx, pry = g.peri
    ppts = _ellipse_pts(g, pu, pv, prx, pry)
    pygame.draw.polygon(big, (226, 220, 208, 110), ppts)
    for p in _heart_shapes(g):
        pygame.draw.polygon(big, (204, 170, 160, 200), p)
    # body: translucent tissue with round shading
    body = g.body()
    bm = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.polygon(bm, (255, 255, 255, 222), body)
    big.blit(_shade_layer(g, bm, (210, 200, 182)), (0, 0))
    # internal structures as faint density changes, softened before they are added
    det = pygame.Surface(size, pygame.SRCALPHA)
    ts = [0.2 + i * 0.01 for i in range(76)]
    nt = [g.P(t, g.spine(t) - 0.009) for t in ts]
    nb = [g.P(t, g.spine(t) + 0.009) for t in ts]
    pygame.draw.polygon(det, (244, 240, 228, 150), nt + nb[::-1])          # notochord: clearer than muscle
    for t in ts[::2]:
        x, y = g.P(t, g.spine(t))
        pygame.draw.line(det, (196, 188, 170, 60), (x, y - 0.007 * g.k), (x + 0.003 * g.k, y + 0.007 * g.k), S)
    pygame.draw.lines(det, (170, 160, 142, 90), False, nt, S)
    pygame.draw.lines(det, (170, 160, 142, 90), False, nb, S)
    t = 0.24
    while t < 0.95:                                                          # chevron somite boundaries
        w = g.half(t) * 0.86
        x, y = g.P(t, g.spine(t))
        a = 0.016 * g.k
        pygame.draw.lines(det, (176, 166, 146, 72), False,
                          [(x + a, y - w * g.k), (x, y - w * 0.15 * g.k), (x, y + w * 0.15 * g.k), (x + a, y + w * g.k)], 2 * S)
        t += 0.0235
    # brain: ventricles read as clearer spaces, the midbrain-hindbrain boundary as a fold
    for (u, v, rx, ry) in ((0.05, -0.02, 0.022, 0.012), (0.115, -0.034, 0.02, 0.011), (0.17, -0.03, 0.026, 0.01)):
        pygame.draw.polygon(det, (246, 242, 232, 120), _ellipse_pts(g, u + 0.004, v + g.spine(u), rx, ry, 32))
    mx, my = g.P(0.1, g.spine(0.1) - 0.06)
    pygame.draw.arc(det, (170, 160, 142, 150), (mx - 0.03 * g.k, my - 0.01 * g.k, 0.06 * g.k, 0.08 * g.k), 0.2, 2.6, 2 * S)
    ox, oy = g.P(*g.otic)                                                    # otic vesicle with two otoliths
    orect = pygame.Rect(0, 0, 0.032 * g.k, 0.023 * g.k)
    orect.center = (ox, oy)
    pygame.draw.ellipse(det, (250, 248, 240, 190), orect)
    pygame.draw.ellipse(det, (160, 150, 132, 150), orect, 2 * S)
    for dx in (-0.008, 0.008):
        pygame.draw.circle(det, (120, 110, 96, 220), (int(ox + dx * g.k), int(oy + 0.002 * g.k)), int(0.0035 * g.k))
    if hpf >= 48:                                                            # pectoral fin bud
        fpts = _ellipse_pts(g, 0.3, 0.04, 0.045, 0.02, 32, -0.35)
        pygame.draw.polygon(det, (240, 236, 224, 150), fpts)
    det = pygame.transform.smoothscale(pygame.transform.smoothscale(det, (g.w // 2, g.h // 2)), size)
    big.blit(det, (0, 0))
    # eye: retina as a darker, soft-edged disc; the lens a bright refractive bead
    ex, ey, er = g.eye
    exp, eyp = g.P(ex, ey)
    rr = int(er * g.k)
    eye = pygame.Surface(size, pygame.SRCALPHA)
    if pigment:
        pygame.draw.circle(eye, (34, 30, 34, 255), (int(exp), int(eyp)), rr)
        pygame.draw.arc(eye, (150, 140, 96, 200), (exp - rr * 0.82, eyp - rr * 0.82, rr * 1.64, rr * 1.64), 3.4, 5.8, max(2, int(rr * 0.16)))
        pygame.draw.circle(eye, (60, 56, 62, 255), (int(exp + 0.2 * rr), int(eyp + 0.1 * rr)), int(rr * 0.4))
    else:
        pygame.draw.circle(eye, (176, 164, 146, 230), (int(exp), int(eyp)), rr)
        pygame.draw.circle(eye, (192, 180, 160, 230), (int(exp), int(eyp)), int(rr * 0.8))
        pygame.draw.circle(eye, (238, 232, 220, 255), (int(exp + 0.2 * rr), int(eyp + 0.1 * rr)), int(rr * 0.45))
        pygame.draw.circle(eye, (150, 140, 124, 200), (int(exp + 0.2 * rr), int(eyp + 0.1 * rr)), int(rr * 0.45), lw)
    eye = pygame.transform.smoothscale(pygame.transform.smoothscale(eye, (int(g.w / 2.2), int(g.h / 2.2))), size)
    big.blit(eye, (0, 0))
    if pigment:
        pygame.draw.circle(big, (236, 236, 232), (int(exp - 0.3 * rr), int(eyp - 0.32 * rr)), int(rr * 0.1))
    # melanophores at 48 hpf without PTU
    if pigment and hpf >= 48:
        rnd = random.Random(48)
        mel = pygame.Surface(size, pygame.SRCALPHA)
        for stripe, t0 in ((-0.85, 0.16), (0.82, 0.36)):
            t = t0
            while t < 0.95:
                x, y = g.P(t + rnd.uniform(-0.004, 0.004), g.spine(t) + stripe * g.half(t))
                r = rnd.uniform(0.0035, 0.006) * g.k
                for k in range(4):
                    a = rnd.uniform(0, math.tau)
                    pygame.draw.line(mel, (62, 46, 44, 230), (x, y), (x + math.cos(a) * r * 1.7, y + math.sin(a) * r * 1.2), S)
                pygame.draw.circle(mel, (44, 32, 32, 240), (int(x), int(y)), int(r))
                t += rnd.uniform(0.026, 0.045)
        for i in range(14):
            a = rnd.uniform(0.2, math.pi - 0.2)
            x, y = g.P(g.yolk[0] + math.cos(a) * g.yolk[2] * 0.7, g.yolk[1] + math.sin(a) * g.yolk[3] * 0.55)
            pygame.draw.circle(mel, (50, 36, 34, 230), (int(x), int(y)), int(rnd.uniform(0.003, 0.006) * g.k))
        big.blit(mel, (0, 0))
    # refraction at every outline instead of drawn lines
    if np is not None:
        _refract(big, [_mask_arr(size, [body]), _mask_arr(size, [ypts, g.ext_poly()]), _mask_arr(size, [fin])], k=6.0 * S / 3, dark=0.38, halo=60)
        ea = np.zeros((g.h, g.w), dtype=np.float32)
        yy, xx = np.ogrid[0:g.h, 0:g.w]
        ea[((xx - exp) ** 2 + (yy - eyp) ** 2) <= rr * rr] = 1.0
        _refract(big, [ea], k=3.0, dark=0.3, halo=0)
    # slight soft focus, as in a stereomicroscope photo
    sp = pygame.transform.smoothscale(big, (max(1, int(g.w / S * 0.78)), max(1, int(g.h / S * 0.78))))
    sp = pygame.transform.smoothscale(sp, (g.w // S, g.h // S))
    _cache[key] = (sp, g)
    return _cache[key]


def _heart_shapes(g):
    if g.hpf >= 48:
        v = _ellipse_pts(g, 0.098, 0.128, 0.03, 0.021, 32, 0.4)
        a = _ellipse_pts(g, 0.135, 0.112, 0.03, 0.018, 32, -0.3)
        return [a, v]
    tube = [g.P(0.068 + 0.04 * i / 12, 0.124 - 0.01 * math.sin(i / 12 * math.pi)) for i in range(13)]
    top = [(x, y - 0.0065 * g.k) for x, y in tube]
    bot = [(x, y + 0.0065 * g.k) for x, y in tube]
    return [top + bot[::-1]]


def _stain(L, hpf, kind):
    """Purple stain layer (SRCALPHA, display size) for kind = heart, vessels or bg."""
    key = ("stain", L, hpf, kind)
    if key in _cache:
        return _cache[key]
    g = Geo(L, hpf)
    size = (g.w, g.h)
    m = pygame.Surface(size, pygame.SRCALPHA)
    W8 = (255, 255, 255, 255)
    if kind == "heart":
        for p in _heart_shapes(g):
            pygame.draw.polygon(m, W8, p)
    elif kind == "vessels":
        ts = [0.2 + i * 0.01 for i in range(72)]
        da = [g.P(t, g.spine(t) + 0.02 * g.half(t) / 0.056 + 0.004) for t in ts]
        pcv = [g.P(t, g.spine(t) + 0.034 * g.half(t) / 0.056 + 0.006) for t in ts[:54]]
        pygame.draw.lines(m, W8, False, da, int(0.015 * g.k))
        pygame.draw.lines(m, W8, False, pcv, int(0.016 * g.k))
        # one intersegmental vessel per somite boundary, along the myosepta (same spacing as the chevrons);
        # at 24 hpf they are still sprouting, longer in front than towards the tail
        t = 0.24 + 0.0235 * 2
        while t < 0.82:
            w = g.half(t)
            x0, y0 = g.P(t, g.spine(t) + 0.02 * w / 0.056)
            grow = 0.82 if hpf >= 48 else max(0.12, 0.8 - 0.6 * (t - 0.27) / 0.55)
            x1, y1 = g.P(t - 0.004, g.spine(t) - w * grow)
            pygame.draw.line(m, W8, (x0, y0), (x1, y1), int(0.008 * g.k))
            t += 0.0235
        head = [g.P(0.04, 0.06), g.P(0.1, 0.05), g.P(0.18, 0.035), g.P(0.22, 0.03)]
        pygame.draw.lines(m, W8, False, head, int(0.012 * g.k))
        pygame.draw.lines(m, W8, False, [g.P(0.06, -0.01), g.P(0.12, -0.035), g.P(0.2, -0.02)], int(0.009 * g.k))
        for k in range(10):
            u = 0.03 + 0.017 * k
            x, y = g.P(u, 0.01 + 0.025 * math.sin(k * 2.1))
            pygame.draw.circle(m, (255, 255, 255, 150), (int(x), int(y)), int(0.007 * g.k))
    else:
        pygame.draw.polygon(m, W8, g.body())
        pygame.draw.polygon(m, W8, _ellipse_pts(g, *g.yolk))
        pygame.draw.polygon(m, W8, g.ext_poly())
    if np is not None:
        a = pygame.surfarray.array_alpha(m).astype(np.float32)
        n = R.value_noise(size[0], size[1], 3 * S, 23, 2).T
        a = a * (0.55 + 0.75 * n) if kind == "vessels" else a * (0.75 + 0.5 * n)
        lay = pygame.Surface(size, pygame.SRCALPHA)
        col = STAIN if kind != "bg" else (126, 100, 126)
        dark = np.clip(1.15 - n * 0.4, 0, 2)
        rgb = np.array(col, dtype=np.float32)[None, None, :] * dark[..., None]
        pygame.surfarray.pixels3d(lay)[:] = np.clip(rgb, 0, 255).astype(np.uint8)
        pygame.surfarray.pixels_alpha(lay)[:] = np.clip(a, 0, 255).astype(np.uint8)
    else:
        lay = m
        lay.fill(STAIN + (255,), special_flags=pygame.BLEND_RGBA_MULT)
    soft = 0.36 if kind == "vessels" else 0.55
    lay = pygame.transform.smoothscale(lay, (max(1, int(g.w / S * soft)), max(1, int(g.h / S * soft))))
    lay = pygame.transform.smoothscale(lay, (g.w // S, g.h // S))
    _cache[key] = lay
    return lay


def embryo(s, c, L, hpf=24, heart=0.0, vessels=0.0, bg=0.0, pigment=None, outline=INK):
    """Draw an embryo centred on c (the trunk axis passes about 0.05 L above c), length L px.
    heart / vessels / bg: purple in situ stain intensities 0..1."""
    L = int(L)
    hpf = 48 if hpf >= 48 else 24
    pigment = (hpf >= 48) if pigment is None else bool(pigment)
    sp, g = _sprite(L, hpf, pigment)
    x = int(c[0] - L / 2 - g.x0 / S)
    y = int(c[1] - 0.05 * L - g.cy / S)
    s.blit(sp, (x, y))
    for kind, val in (("bg", bg), ("vessels", vessels), ("heart", heart)):
        if val > 0.01:
            lay = _stain(L, hpf, kind)
            lay.set_alpha(int(clamp(val, 0, 1) * (150 if kind == "bg" else 255)))
            s.blit(lay, (x, y))
            lay.set_alpha(None)
    return dict(rect=pygame.Rect(x, y, sp.get_width(), sp.get_height()), geo=g)
