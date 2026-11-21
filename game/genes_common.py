# -*- coding: utf-8 -*-
"""Drawing and sequence helpers shared by the Genes & genomes techniques:
sequences, anti-aliased plot frames and polylines, instrument windows, chromatograms,
base tiles and the zebrafish embryo (genes_embryo)."""
import math
import random
import pygame
import gfx
import render as R
import real
from render import lighten
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, CORAL, TURQ, TEAL, LAV, VIOLET, WHITE, GREEN, RED, YELLOW,
                  BASE_COL, draw_text, mix, clamp, text_surf)
from genes_embryo import embryo  # noqa: F401  (re-exported)

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

COMP = {"A": "T", "T": "A", "C": "G", "G": "C", "N": "N"}
BASE_TINT = {b: mix(c, WHITE, 0.82) for b, c in BASE_COL.items()}


def revcomp(s):
    return "".join(COMP[b] for b in reversed(s))


def comp(s):
    return "".join(COMP[b] for b in s)


def rand_seq(rng, n, gc=0.5):
    out = []
    for _ in range(n):
        out.append(rng.choice("GC") if rng.random() < gc else rng.choice("AT"))
    return "".join(out)


# ------------------------------------------------------------------ drawing helpers
def aa_polyline(s, col, pts, w=2):
    """Anti-aliased polyline of width w (1-4)."""
    if len(pts) < 2:
        return
    if w <= 1:
        pygame.draw.aalines(s, col, False, pts)
        return
    pygame.draw.lines(s, col, False, pts, int(w))
    o = (w - 1) / 2.0
    pygame.draw.aalines(s, col, False, [(x, y - o) for x, y in pts])
    pygame.draw.aalines(s, col, False, [(x, y + o) for x, y in pts])
    pygame.draw.aalines(s, col, False, [(x - o, y) for x, y in pts])
    pygame.draw.aalines(s, col, False, [(x + o, y) for x, y in pts])


def ring(s, col, c, r, w=2):
    """Anti-aliased circle outline."""
    x, y, r = int(round(c[0])), int(round(c[1])), int(round(r))
    pygame.draw.circle(s, col, (x, y), r, w)
    R.gd.aacircle(s, x, y, r, col)
    R.gd.aacircle(s, x, y, r - w + 1, col)


_win = R.LRU(60)


def window(s, rect, title, col=TEAL, size=15, drop=True):
    """Analysis-software window as on a real desktop: light grey title bar with an app icon in
    `col` and the minimise / maximise / close controls, a white work area, a thin grey frame.
    Returns the content rect (same geometry as before: title bar height = size + 16)."""
    rect = pygame.Rect(rect)
    h = size + 16
    key = (rect.size, tuple(col), size)
    base = _win.get(key)
    if base is None:
        base = pygame.Surface(rect.size, pygame.SRCALPHA)
        base.blit(R.rrect_surf(rect.w, rect.h, (250, 250, 251), (118, 122, 130), 1, 7, 0, False), (0, 0))
        bar = R.rrect_surf(rect.w - 2, h + 8, (236, 237, 240), None, 0, 6, 0.06, False)
        base.blit(bar, (1, 1), pygame.Rect(0, 0, rect.w - 2, h))
        pygame.draw.line(base, (204, 206, 212), (1, h + 1), (rect.w - 2, h + 1))
        pygame.draw.line(base, tuple(col), (1, h + 2), (rect.w - 2, h + 2), 2)
        ic = pygame.Rect(9, (h - 12) // 2 + 1, 12, 12)
        base.blit(R.rrect_surf(12, 12, tuple(col), lighten(col, -0.35), 1, 3, 0.2, True), ic.topleft)
        pygame.draw.line(base, WHITE, (ic.x + 3, ic.centery + 2), (ic.x + 6, ic.y + 3), 2)
        pygame.draw.line(base, WHITE, (ic.x + 6, ic.y + 3), (ic.right - 3, ic.bottom - 3), 2)
        cy = h // 2 + 1
        gx = rect.w - 16
        pygame.draw.line(base, (70, 72, 80), (gx - 4, cy - 4), (gx + 4, cy + 4), 2)
        pygame.draw.line(base, (70, 72, 80), (gx - 4, cy + 4), (gx + 4, cy - 4), 2)
        pygame.draw.rect(base, (70, 72, 80), (gx - 32, cy - 4, 9, 9), 1)
        pygame.draw.line(base, (70, 72, 80), (gx - 58, cy + 3), (gx - 49, cy + 3), 1)
        _win.put(key, base)
    if drop:
        gfx.shadow(s, rect, 8, (3, 5), 70, 7)
    s.blit(base, rect.topleft)
    draw_text(s, title, (rect.x + 28, rect.y + 1 + h // 2), size - 1, (40, 42, 52), bold=True, vcenter=True)
    return pygame.Rect(rect.x + 10, rect.y + h + 10, rect.w - 20, rect.h - h - 20)


_mon = R.LRU(20)


def monitor(s, rect, stand=True):
    """A flat-screen monitor whose screen is exactly `rect`, standing on the worktop (y = 470)."""
    rect = pygame.Rect(rect)
    bez = rect.inflate(22, 22)
    bez.h += 6
    if stand and bez.bottom < 462:
        neck = pygame.Rect(rect.centerx - 22, bez.bottom - 4, 44, 470 - bez.bottom + 6)
        sh = R.soft_shadow(220, 14, 7, (10, 10, 20), 110, 6)
        s.blit(sh, (rect.centerx - 110 - 12 + 6, 470 + 2 - 12))
        s.blit(real.steel(neck.w, neck.h, 4, (70, 72, 78), True), neck.topleft)
        foot = pygame.Rect(rect.centerx - 100, 466, 200, 10)
        s.blit(real.plastic(foot.w, foot.h, (52, 54, 60), 5, 0.4), foot.topleft)
    key = bez.size
    sp = _mon.get(key)
    if sp is None:
        sp = real.plastic(bez.w, bez.h, (40, 42, 48), 10, 0.35).copy()
        pygame.draw.rect(sp, (14, 14, 18), (9, 9, bez.w - 18, bez.h - 24))
        pygame.draw.circle(sp, (70, 200, 120), (bez.w - 22, bez.h - 9), 2)
        _mon.put(key, sp)
    gfx.shadow(s, bez, 10, (4, 8), 90, 9)
    s.blit(sp, bez.topleft)


_scope = R.LRU(10)


def brightfield(w, h, seed=3, warm=(248, 244, 232)):
    """Transmitted-light background of a stereomicroscope photo: warm, unevenly lit, a few specks."""
    key = ("bf", w, h, seed, warm)
    sp = _scope.get(key)
    if sp is not None:
        return sp
    sp = pygame.Surface((w, h))
    if np is not None:
        xx, yy = np.mgrid[0:w, 0:h].astype(np.float32)
        d = ((xx - w * 0.46) / (w * 0.7)) ** 2 + ((yy - h * 0.44) / (h * 0.7)) ** 2
        lum = 1.02 - 0.22 * d
        n = R.value_noise(w, h, 80, seed, 2).T
        base = np.array(warm, dtype=np.float32)
        arr = base[None, None, :] * (lum + (n - 0.5) * 0.05)[..., None]
        rng = np.random.default_rng(seed)
        arr += rng.normal(0, 1.6, (w, h, 1))
        pygame.surfarray.blit_array(sp, np.clip(arr, 0, 255).astype(np.uint8))
        rnd = random.Random(seed)
        for _ in range(int(w * h / 9000)):
            x, y = rnd.randrange(w), rnd.randrange(h)
            r = rnd.uniform(1, 2.6)
            pygame.draw.circle(sp, (178, 172, 160), (x, y), int(r))
    else:
        sp.fill(warm)
    return _scope.put(key, sp)


def scope_field(s, c, r):
    """What you see down a stereomicroscope: a round, warm brightfield inside the dark eyepiece."""
    key = ("field", r)
    sp = _scope.get(key)
    if sp is None:
        n = 2 * r + 44
        sp = pygame.Surface((n, n), pygame.SRCALPHA)
        cc = n // 2
        ring = R.rrect_surf(n, n, (34, 34, 38), None, 0, n // 2, 0.0, False)
        sp.blit(ring, (0, 0))
        R.aa_ring(sp, (cc, cc), cc - 1, 4, (90, 92, 98))
        R.aa_ring(sp, (cc, cc), cc - 7, 2, (60, 62, 68))
        bf = brightfield(2 * r, 2 * r, 5).copy().convert_alpha() if pygame.display.get_surface() else brightfield(2 * r, 2 * r, 5).copy()
        disc = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        disc.blit(bf, (0, 0))
        m = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        m.blit(R._ellipse_surf(2 * r, 2 * r, (255, 255, 255, 255), None, 0), (0, 0))
        disc.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        sp.blit(disc, (cc - r, cc - r))
        if np is not None:     # dark falloff at the edge of the field stop
            vg = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
            xx, yy = np.mgrid[0:2 * r, 0:2 * r].astype(np.float32)
            d = np.sqrt((xx - r) ** 2 + (yy - r) ** 2) / r
            a = np.clip((d - 0.8) / 0.2, 0, 1) ** 2 * 200 * (d <= 1.0)
            pygame.surfarray.pixels3d(vg)[:] = 10
            pygame.surfarray.pixels_alpha(vg)[:] = a.astype(np.uint8)
            sp.blit(vg, (cc - r, cc - r))
        _scope.put(key, sp)
    s.blit(sp, (int(c[0]) - sp.get_width() // 2, int(c[1]) - sp.get_height() // 2))


_desk = R.LRU(6)


def desktop(s, rect):
    """Close-up of a monitor showing the analysis computer's desktop (windows go on top)."""
    rect = pygame.Rect(rect)
    monitor(s, rect, stand=False)
    sp = _desk.get(rect.size)
    if sp is None:
        sp = R.vgrad(rect.size, (58, 74, 92), (28, 36, 50))
        if np is not None:
            n = R.value_noise(rect.w, rect.h, 160, 31, 2)
            arr = pygame.surfarray.pixels3d(sp)
            arr[:] = np.clip(arr.astype(np.float32) + (n.T[..., None] - 0.5) * 18, 0, 255).astype(np.uint8)
            del arr
        _desk.put(rect.size, sp)
    s.blit(sp, rect.topleft)


def screen_window(s, rect, title, col=TEAL, size=15):
    """A software window filling a monitor screen."""
    monitor(s, rect)
    return window(s, rect, title, col, size, drop=False)


def plot_box(s, P, xticks=(), yticks=(), xlab="", ylab="", grid=True, fill=WHITE):
    """White plot area with light gridlines, tick labels and axis titles.
    xticks / yticks: lists of (pixel position, label)."""
    P = pygame.Rect(P)
    pygame.draw.rect(s, fill, P)
    if grid:
        for x, _ in xticks:
            pygame.draw.line(s, (232, 234, 240), (x, P.y + 1), (x, P.bottom - 2))
        for y, _ in yticks:
            pygame.draw.line(s, (232, 234, 240), (P.x + 1, y), (P.right - 2, y))
    for x, lab in xticks:
        pygame.draw.line(s, INK_SOFT, (x, P.bottom), (x, P.bottom + 4))
        draw_text(s, lab, (x, P.bottom + 6), 12, MUTED, center=True)
    for y, lab in yticks:
        pygame.draw.line(s, INK_SOFT, (P.x - 4, y), (P.x, y))
        draw_text(s, lab, (P.x - 7, y), 12, MUTED, right=True, vcenter=True)
    pygame.draw.rect(s, (120, 124, 132), P, 1)
    if xlab:
        draw_text(s, xlab, (P.centerx, P.bottom + 22), 13, INK_SOFT, center=True, bold=True)
    if ylab:
        draw_text(s, ylab, (P.x, P.y - 19), 13, INK_SOFT, bold=True)


def base_tile(s, r, b, size=18, fill=None, edge=None, col=None):
    """One base in a rounded tile tinted by its colour."""
    r = pygame.Rect(r)
    gfx.rrect(s, r, fill or BASE_TINT.get(b, CARD), edge or mix(BASE_COL.get(b, INK), WHITE, 0.55), 1, 3, 0.0, False)
    draw_text(s, b, r.center, size, col or BASE_COL.get(b, INK), center=True, bold=True, mono=True, vcenter=True)


def cell_row(s, x0, y, seq, cw, size=18, fills=None, col=None, h=26):
    """Letters in tiles; fills: dict index -> fill colour (highlight)."""
    for i, b in enumerate(seq):
        r = pygame.Rect(int(x0 + i * cw), y, int(cw) - 2, h)
        f = (fills or {}).get(i)
        if col is not None and not f:
            gfx.rrect(s, r, (247, 247, 249), (226, 226, 232), 1, 3, 0.0, False)
            draw_text(s, b, r.center, size, col, center=True, bold=True, mono=True, vcenter=True)
        else:
            base_tile(s, r, b, size, f, INK if f else None, col)


_gel = R.LRU(20)
_band = R.LRU(200)


def dark_gel(s, rect, seed=5):
    """A gel-documentation photo: near-black agarose under UV, camera noise, a faint vignette."""
    rect = pygame.Rect(rect)
    key = (rect.size, seed)
    sp = _gel.get(key)
    if sp is None:
        sp = pygame.Surface(rect.size)
        if np is not None:
            rng = np.random.default_rng(seed)
            w, h = rect.size
            xx, yy = np.mgrid[0:w, 0:h].astype(np.float32)
            glow = 1 - 0.35 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 1.4)) ** 2)
            v = 22 * glow + rng.normal(0, 3.2, (w, h)) + (R.value_noise(w, h, 30, seed, 2).T - 0.5) * 8
            arr = np.clip(np.stack([v, v, v * 1.04], axis=2), 0, 255).astype(np.uint8)
            pygame.surfarray.blit_array(sp, arr)
        else:
            sp.fill((20, 20, 22))
        _gel.put(key, sp)
    s.blit(sp, rect.topleft)
    pygame.draw.rect(s, (60, 60, 64), rect, 1)


def uv_band(s, cx, y, w, a=1.0):
    """A DNA band in a greyscale gel photo: bright, soft-edged."""
    if a <= 0.02:
        return
    w = max(6, int(w))
    sp = _band.get(w)
    if sp is None:
        big = pygame.Surface((w + 16, 22), pygame.SRCALPHA)
        pygame.draw.ellipse(big, (236, 236, 232, 255), (6, 7, w + 4, 8))
        pygame.draw.rect(big, (250, 250, 248, 255), (10, 8, w - 4, 6), border_radius=3)
        small = pygame.transform.smoothscale(big, (max(2, (w + 16) // 3), 8))
        sp = pygame.transform.smoothscale(small, (w + 16, 22))
        _band.put(w, sp)
    sp.set_alpha(int(255 * min(1.0, a)))
    s.blit(sp, (int(cx - w / 2 - 8), int(y - 11)))
    sp.set_alpha(None)


# ------------------------------------------------------------------ chromatograms
def _trace_curves(w, peaks, width, noise=None, step=1.0):
    """x positions and one height array per base (0..~1), local coordinates."""
    xs = [i * step for i in range(int(w / step) + 2)]
    out = {}
    for b in "ACGT":
        pk = [(x, h) for x, h, bb in peaks if bb == b]
        if np is not None:
            X = np.array(xs, dtype=np.float32)
            v = np.zeros_like(X)
            for px, h in pk:
                d = (X - px) / width
                v += h * np.exp(-np.minimum(d * d, 30))
            if noise:
                v += np.array([noise(x, b) for x in xs], dtype=np.float32)
            out[b] = v.tolist()
        else:
            vals = []
            for x in xs:
                v = sum(h * math.exp(-((x - px) / width) ** 2) for px, h in pk if abs(x - px) < width * 3.5)
                vals.append(v + (noise(x, b) if noise else 0))
            out[b] = vals
    return xs, out


def trace_surface(w, h, peaks, width=8.0, noise=None, fill=False, lw=1.5):
    """Chromatogram (transparent background) rendered at 2x and smoothscaled.
    peaks: list of (x local px, height 0..1, base)."""
    K = 2
    big = pygame.Surface((w * K, h * K), pygame.SRCALPHA)
    xs, cv = _trace_curves(w * K, [(x * K, hh, b) for x, hh, b in peaks], width * K, noise and (lambda x, b: noise(x / K, b)), 2.0)
    base_y = h * K - 6 * K
    hmax = h * K - 16 * K
    for b in "CAGT":
        pts = [(x, base_y - min(1.25, v) * hmax) for x, v in zip(xs, cv[b])]
        if fill:
            poly = [(xs[0], base_y)] + pts + [(xs[-1], base_y)]
            R.gd.filled_polygon(big, poly, BASE_COL[b] + (34,))
        pygame.draw.lines(big, BASE_COL[b], False, pts, max(1, int(round(lw * K))))
    return pygame.transform.smoothscale(big, (w, h))


def peaks_trace(s, rect, peaks, width=8.0, hmax=None, noise=None, step=3, lw=1.5):
    """Draw a chromatogram for peaks given in screen x coordinates, clipped to rect."""
    rect = pygame.Rect(rect)
    local = [(x - rect.x, hh, b) for x, hh, b in peaks]
    s.blit(trace_surface(rect.w, rect.h, local, width, noise and (lambda x, b: noise(x + rect.x, b)), False, lw), rect.topleft)


def trace_pic(kind, seed=1):
    """Picture of a Sanger trace: good, noisy_start, decay, blob, mixed, het."""
    def pic(s, r):
        rng = random.Random(kind + str(seed))
        seq = rand_seq(rng, 26)
        label = {"good": "bases 300-325", "noisy_start": "bases 1-26", "decay": "bases 880-905",
                 "blob": "bases 60-85", "mixed": "bases 120-145", "het": "bases 210-235"}[kind]
        inner = window(s, r, "Trace viewer  ·  " + label, TEAL, 13)
        chart = pygame.Rect(inner.x, inner.y + 24, inner.w, inner.h - 44)
        gfx.rrect(s, chart, WHITE, None, 0, 4, 0, False)
        peaks = []
        sp = (chart.w - 16) / 26.0
        x0 = chart.x + 8 + sp / 2
        pw = sp * 0.3
        for i, b in enumerate(seq):
            x = x0 + i * sp
            h = rng.uniform(0.6, 0.95)
            if kind == "noisy_start" and i < 9:
                h *= rng.uniform(0.2, 0.6)
                peaks.append((x + sp * 0.4, rng.uniform(0.2, 0.5), rng.choice("ACGT")))
            if kind == "decay":
                h *= max(0.14, 1 - i / 28.0)
            if kind == "mixed":
                peaks.append((x + rng.uniform(-2, 2), h * rng.uniform(0.5, 0.9), rng.choice([c for c in "ACGT" if c != b])))
            if kind == "het" and i >= 12:
                peaks.append((x + sp * 0.12, h * rng.uniform(0.55, 0.8), rng.choice([c for c in "ACGT" if c != b])))
                h *= 0.75
            peaks.append((x, h, b))
            if x < chart.right - 6:
                draw_text(s, b, (x, inner.y + 4), 11, BASE_COL[b], center=True, bold=True, mono=True)
        if kind == "decay":
            peaks_trace(s, chart, [p for p in peaks if p[0] < chart.centerx], pw * 0.9)
            peaks_trace(s, chart, [p for p in peaks if p[0] >= chart.centerx], pw * 1.6)
        elif kind == "blob":
            peaks_trace(s, chart, peaks, pw)
            peaks_trace(s, chart, [(chart.x + chart.w * 0.55, 1.15, "T")], sp * 1.4)
        else:
            noise = None
            if kind == "noisy_start":
                noise = lambda x, b: (0.12 * (1 + math.sin(x * 0.7 + "ACGT".index(b))) if x < x0 + 9 * sp else 0)
            peaks_trace(s, chart, peaks, pw, noise=noise)
        pygame.draw.rect(s, (150, 154, 160), chart, 1)
        if kind == "het":
            cx = x0 + 11.5 * sp
            for yy in range(chart.y, chart.bottom, 10):
                pygame.draw.line(s, CORAL, (cx, yy), (cx, yy + 5), 2)
            draw_text(s, "cut site", (cx, chart.bottom + 3), 12, CORAL, center=True, bold=True)
    return pic
