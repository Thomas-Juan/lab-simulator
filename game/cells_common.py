# -*- coding: utf-8 -*-
"""Drawing helpers shared by the Cells & embryos techniques, aiming at photographic realism:
microscope fields as a camera sees them (uneven illumination, optical softness, sensor grain),
phase-contrast and brightfield cells, fluorescence cells, eyepiece framing, brushed steel and
hand tremor. Everything slow is cached."""
import math
import random
import pygame
import gfx
import render as R
from core import INK, NIGHT, CARD, WHITE, clamp, mix, draw_text

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

PHASE_BG = (150, 154, 146)       # phase-contrast background: mid grey, faintly green
BRIGHT_BG = (214, 210, 196)      # brightfield (halogen) background: warm light grey
EYE = (16, 16, 20)               # the black around an eyepiece / camera field


def ell_pts(cx, cy, a, b, ang, n=14):
    ca, sa = math.cos(ang), math.sin(ang)
    out = []
    for i in range(n):
        t = i * math.tau / n
        x, y = a * math.cos(t), b * math.sin(t)
        out.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return out


def soften(sf, k=1.7):
    """Optical softness: shrink by k and scale back up (keeps alpha)."""
    w, h = sf.get_size()
    sm = pygame.transform.smoothscale(sf, (max(1, int(w / k)), max(1, int(h / k))))
    return pygame.transform.smoothscale(sm, (w, h))


# ------------------------------------------------------------------ microscope field
_disc = R.LRU(24)


def _photo_field(w, h, col, seed):
    """A camera image of an empty field: smooth illumination fall-off, mottling and sensor grain."""
    if np is None:
        sf = pygame.Surface((w, h))
        sf.fill(col)
        return sf
    rng = np.random.default_rng(300 + seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w * 0.47, h * 0.45
    d = np.sqrt(((xx - cx) / (w * 0.6)) ** 2 + ((yy - cy) / (h * 0.6)) ** 2)
    illum = 1.08 - 0.22 * d ** 2
    mott = R.value_noise(w, h, max(8, w / 6), 40 + seed, 3) - 0.5
    img = np.array(col, dtype=np.float32)[None, None, :] * illum[..., None] + mott[..., None] * 12
    img += rng.normal(0, 2.6, (h, w, 1)).astype(np.float32)
    for _ in range(int(w * h / 9000)):        # out-of-focus dust specks
        x0, y0, r0 = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(3, 9)
        m = ((xx - x0) ** 2 + (yy - y0) ** 2) < r0 ** 2
        img[m] -= rng.uniform(3, 7)
    return R.to_surface(img)


def _field_disc(r, col, seed=0, glow=True):
    key = (r, tuple(col), seed)
    sf = _disc.get(key)
    if sf is not None:
        return sf
    n = 2 * r
    tex = _photo_field(n, n, col, seed)
    sf = pygame.Surface((n, n), pygame.SRCALPHA)
    sf.blit(tex, (0, 0))
    m = pygame.Surface((n, n), pygame.SRCALPHA)
    m.blit(R._ellipse_surf(n, n, (255, 255, 255, 255), None, 0), (0, 0))
    sf.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return _disc.put(key, sf)


def field_bg(s, c, r, col=PHASE_BG, seed=0):
    """Photographic microscope field disc (illumination fall-off, mottling, grain)."""
    r = int(r)
    s.blit(_field_disc(r, col, seed), (int(c[0]) - r, int(c[1]) - r))


def field_rect(w, h, col=BRIGHT_BG, seed=0):
    """Rectangular photographic field (a camera frame), cached."""
    key = ("rect", w, h, tuple(col), seed)
    sf = _disc.get(key)
    if sf is None:
        sf = _disc.put(key, _photo_field(w, h, col, seed))
    return sf


_over = R.LRU(16)


def _scope_overlay(r, col, dark):
    """Eyepiece: a soft field-stop edge and vignette inside, `col` (usually black) outside."""
    key = (r, tuple(col) if col else None, dark)
    sf = _over.get(key)
    if sf is not None:
        return sf
    n = 2 * r + 28
    sf = pygame.Surface((n, n), pygame.SRCALPHA)
    if np is not None:
        y, x = np.mgrid[0:n, 0:n].astype(np.float32)
        c = n / 2.0
        d = np.sqrt((x - c + 0.5) ** 2 + (y - c + 0.5) ** 2)
        edge = np.clip((d - (r - 3)) / 4.0, 0, 1)                    # soft field stop
        vig = np.clip((d / r - 0.62) / 0.38, 0, 1) ** 2 * (170 if dark else 120)
        a_in = np.maximum(vig, edge * 255)
        outside = d >= r + 1
        alpha = np.where(outside, 0 if col is None else 255, a_in).astype(np.uint8)
        base = np.array(EYE, np.float32)
        rgb = np.where(outside[..., None], np.array(col or EYE, np.float32), base)
        pygame.surfarray.pixels3d(sf)[:] = rgb.astype(np.uint8).transpose(1, 0, 2)
        pygame.surfarray.pixels_alpha(sf)[:] = alpha.T
        corner = pygame.Surface((n, n), pygame.SRCALPHA)
        pygame.draw.rect(corner, (255, 255, 255, 255), (2, 2, n - 4, n - 4), border_radius=12)
        sf.blit(corner, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return _over.put(key, sf)


def scope_mask(s, c, r, col=EYE, dark=False):
    """Frame a circular microscope field: black eyepiece surround, soft field stop and vignette.
    Draw it over the field contents, inside the card from scope_card()."""
    r = int(r)
    if col == CARD:
        col = EYE
    s.blit(_scope_overlay(r, col, dark), (int(c[0]) - r - 14, int(c[1]) - r - 14))


_grain = {}


def grain(w, h):
    """Sensor grain pair (add, sub) of size w x h."""
    k = (w, h)
    g = _grain.get(k)
    if g is None:
        a = pygame.Surface((w, h))
        b = pygame.Surface((w, h))
        if np is not None:
            rng = np.random.default_rng(w * 31 + h)
            n = rng.normal(0, 1, (w, h))
            pygame.surfarray.pixels3d(a)[:] = np.clip(n * 5, 0, 14).astype(np.uint8)[..., None]
            pygame.surfarray.pixels3d(b)[:] = np.clip(-n * 5, 0, 14).astype(np.uint8)[..., None]
        g = _grain[k] = (a, b)
    return g


def photo_finish(sf, blur=1.5):
    """Make a drawn field look photographed: optical softness plus sensor grain (in place-ish)."""
    w, h = sf.get_size()
    out = soften(sf, blur) if blur > 1.01 else sf.copy()
    ga, gs = grain(w, h)
    out.blit(ga, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    out.blit(gs, (0, 0), special_flags=pygame.BLEND_RGB_SUB)
    return out


def masked_field(s, c, r, draw_fn, dark=False, blur=1.5):
    """Draw a microscope field cut to a circle, photographed (soft, grainy), with eyepiece vignette.
    draw_fn(surface, centre) draws the contents on a temporary surface of size 2r x 2r."""
    r = int(r)
    tmp = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
    draw_fn(tmp, (r, r))
    tmp = photo_finish(tmp, blur)
    tmp.blit(R._ellipse_surf(2 * r, 2 * r, (255, 255, 255, 255), None, 0), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    s.blit(tmp, (int(c[0]) - r, int(c[1]) - r))
    s.blit(_scope_overlay(r, None, dark), (int(c[0]) - r - 14, int(c[1]) - r - 14))


def scope_card(s, c, r, col=EYE):
    """The dark eyepiece / camera frame that holds a microscope field; returns its rect."""
    if col == CARD:
        col = EYE
    box = pygame.Rect(int(c[0]) - r - 14, int(c[1]) - r - 14, 2 * r + 28, 2 * r + 28)
    gfx.shadow(s, box, 14)
    s.blit(R.rrect_surf(box.w, box.h, tuple(col), (60, 62, 70), 2, 14, 0.04, False), box.topleft)
    return box


# ------------------------------------------------------------------ phase-contrast cell sprites
_adh = R.LRU(400)


def _spindle(a, b, ang, cx, cy, n=28, sc=1.0, wob=(0.0, 0.0, 0.0)):
    """Irregular cell outline: an ellipse with tapered ends and a few lamellipodia bumps."""
    ca, sa = math.cos(ang), math.sin(ang)
    out = []
    for i in range(n):
        t = i * math.tau / n
        c, s_ = math.cos(t), math.sin(t)
        m = (1 + wob[0] * math.sin(2 * t + wob[1]) + wob[0] * 0.6 * math.sin(3 * t + wob[2])
             + wob[0] * 0.45 * math.sin(5 * t + wob[1] * 1.7) + wob[0] * 0.25 * math.sin(7 * t + wob[2] * 0.6))
        x = a * sc * m * math.copysign(abs(c) ** 0.8, c)
        y = b * sc * m * s_ * (1 - 0.12 * abs(c))
        out.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return out


def adherent_sprite(a, b, ang, fill=None, seed=0):
    """A spread adherent cell as phase contrast shows it: a soft bright halo outside a thin dark
    edge, a body barely darker than the background, a darker perinuclear zone, a grey nucleus with
    a faint bright rim and dark nucleoli. Translucent, so the field shows through."""
    a, b = max(4, int(round(a / 2.0)) * 2), max(3, int(round(b)))
    q = int(round((ang % math.tau) / math.tau * 32)) % 32
    seed %= 4
    key = (a, b, q, seed)
    sp = _adh.get(key)
    if sp is not None:
        return sp
    ang = q * math.tau / 32
    rnd = random.Random(seed * 97 + a * 7 + b)
    wob = (rnd.uniform(0.10, 0.2), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3))
    S = 3
    n = (2 * a + 18)
    c = n * S / 2
    halo = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
    pygame.draw.polygon(halo, (250, 252, 246, 130), _spindle(a + 2.4, b + 2.4, ang, c, c, sc=S, wob=wob))
    pygame.draw.polygon(halo, (0, 0, 0, 0), _spindle(a - 0.4, b - 0.4, ang, c, c, sc=S, wob=wob))
    halo = soften(halo, 2.2)
    big = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
    big.blit(halo, (0, 0))
    pygame.draw.polygon(big, (56, 60, 54, 200), _spindle(a, b, ang, c, c, sc=S, wob=wob))
    pygame.draw.polygon(big, (112, 116, 108, 150), _spindle(a - 1.1, b - 1.1, ang, c, c, sc=S, wob=wob))
    peri = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
    pygame.draw.polygon(peri, (96, 100, 92, 120), _spindle(a * 0.62, b * 0.78, ang, c, c, sc=S, wob=wob))
    big.blit(soften(peri, 2.2), (0, 0))
    nb = max(2.5, b * 0.6)
    na = min(a * 0.36, nb * 1.35)
    off = rnd.uniform(-0.15, 0.15) * a
    nc = (c + off * S * math.cos(ang), c + off * S * math.sin(ang))
    pygame.draw.polygon(big, (200, 204, 196, 120), _spindle(na + 1.0, nb + 1.0, ang, nc[0], nc[1], 20, S))
    pygame.draw.polygon(big, (112, 116, 108, 210), _spindle(na, nb, ang, nc[0], nc[1], 20, S))
    for k in range(rnd.choice((1, 2, 2, 3))):
        ox, oy = rnd.uniform(-0.45, 0.45) * na * S, rnd.uniform(-0.35, 0.35) * nb * S
        pygame.draw.circle(big, (52, 54, 48, 230), (int(nc[0] + ox * math.cos(ang) - oy * math.sin(ang)),
                                                     int(nc[1] + ox * math.sin(ang) + oy * math.cos(ang))), max(2, int(S * 1.3)))
    for k in range(9):     # granules and vesicles around the nucleus
        d = rnd.uniform(na + 1.5, a * 0.7) * rnd.choice((-1, 1)) * S
        w_ = rnd.uniform(-0.35, 0.35) * b * S
        col = (70, 72, 66, 160) if k % 3 else (230, 232, 224, 150)
        pygame.draw.circle(big, col, (int(nc[0] + d * math.cos(ang) - w_ * math.sin(ang)), int(nc[1] + d * math.sin(ang) + w_ * math.cos(ang))), max(1, S - 1))
    sp = pygame.transform.smoothscale(big, (n, n))
    sp = soften(sp, 1.25)
    return _adh.put(key, sp)


def adherent(s, cx, cy, a, b, ang, fill=None, edge=None, nuc=None, seed=0):
    sp = adherent_sprite(a, b, ang, fill, seed)
    s.blit(sp, (int(cx - sp.get_width() / 2), int(cy - sp.get_height() / 2)))


_rnd = R.LRU(120)


def round_sprite(r, kind="live"):
    """Round cell. 'live': phase-bright and refractile (bright core, thin dark ring, bright halo);
    'flat': rounding up but still attached (grey, faint halo); 'dead': took up trypan blue
    (dark blue, no halo, slightly crenated)."""
    r = max(3, int(round(r)))
    key = (r, kind)
    sp = _rnd.get(key)
    if sp is not None:
        return sp
    S = 3
    n = 2 * r + 14
    big = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
    c = n * S // 2
    R_ = r * S
    rnd = random.Random(r * 13 + len(kind))
    if kind == "dead":
        pts = [(c + math.cos(t) * R_ * (1 + 0.05 * math.sin(7 * t + 1)), c + math.sin(t) * R_ * (1 + 0.05 * math.sin(7 * t + 1)))
               for t in [i * math.tau / 40 for i in range(40)]]
        pygame.draw.polygon(big, (34, 46, 104, 245), pts)
        inner = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
        pygame.draw.circle(inner, (78, 104, 182, 200), (c - R_ // 6, c - R_ // 6), int(R_ * 0.72))
        big.blit(soften(inner, 2.0), (0, 0))
        for _ in range(7):
            a_, d_ = rnd.uniform(0, math.tau), rnd.uniform(0, R_ * 0.7)
            pygame.draw.circle(big, (26, 36, 90, 220), (int(c + math.cos(a_) * d_), int(c + math.sin(a_) * d_)), S)
    else:
        live = kind == "live"
        halo = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
        pygame.draw.circle(halo, (255, 255, 250, 210 if live else 110), (c, c), R_ + int(3.5 * S))
        big.blit(soften(halo, 2.6), (0, 0))
        pygame.draw.circle(big, (44, 48, 44, 235) if live else (70, 74, 68, 210), (c, c), R_)
        body = (236, 240, 230) if live else (158, 162, 152)
        core = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
        pygame.draw.circle(core, body + (255,), (c, c), R_ - int(1.4 * S))
        pygame.draw.circle(core, (255, 255, 252, 255) if live else R.lighten(body, 0.12) + (255,), (c - R_ // 6, c - R_ // 6), int(R_ * 0.5))
        big.blit(soften(core, 1.8), (0, 0))
        pygame.draw.circle(big, (40, 44, 40, 160), (c, c), R_, max(2, S))
        if live:
            pygame.draw.circle(big, (180, 184, 172, 140), (c + R_ // 6, c + R_ // 8), int(R_ * 0.32))
    sp = pygame.transform.smoothscale(big, (n, n))
    return _rnd.put(key, sp)


def rounded(s, cx, cy, r, fill=None, edge=None, kind="live"):
    """A rounded cell (detached or in suspension)."""
    sp = round_sprite(r, kind)
    s.blit(sp, (int(cx - sp.get_width() / 2), int(cy - sp.get_height() / 2)))


def dead_cell(s, x, y, r=10):
    rounded(s, x, y, r, kind="dead")


# ------------------------------------------------------------------ fluorescence cells
_fl = R.LRU(200)


def fluo_cell_sprite(a, b, ang, gfp, seed=0):
    """A cell in a fluorescence image on black: Hoechst-blue nucleus with chromatin texture and,
    if gfp > 0, cytoplasmic GFP whose brightness follows gfp (0..1). Drawn for additive blending."""
    a, b = max(5, int(a)), max(4, int(b))
    q = int(round((ang % math.tau) / math.tau * 24)) % 24
    key = (a, b, q, round(gfp, 1), seed % 5)
    sp = _fl.get(key)
    if sp is not None:
        return sp
    ang = q * math.tau / 24
    rnd = random.Random(seed * 31 + a)
    wob = (rnd.uniform(0.08, 0.18), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3))
    S = 2
    n = 2 * a + 24
    c = n * S / 2
    big = pygame.Surface((n * S, n * S))
    if gfp > 0.05:
        g = int(45 + 150 * gfp)
        pygame.draw.polygon(big, (int(g * 0.18), g, int(g * 0.22)), _spindle(a, b, ang, c, c, sc=S, wob=wob))
        pygame.draw.polygon(big, (int(g * 0.22), min(255, int(g * 1.15)), int(g * 0.28)), _spindle(a * 0.6, b * 0.75, ang, c, c, sc=S, wob=wob))
    nb = max(3, b * 0.62)
    na = min(a * 0.42, nb * 1.3)
    pygame.draw.polygon(big, (40, 70, 210), _spindle(na, nb, ang, c, c, 20, S))
    for _ in range(10):
        ox, oy = rnd.uniform(-0.6, 0.6) * na * S, rnd.uniform(-0.6, 0.6) * nb * S
        pygame.draw.circle(big, (90, 130, 255), (int(c + ox), int(c + oy)), max(1, S))
    sp = pygame.transform.smoothscale(big, (n, n))
    sp = soften(sp, 1.6)
    return _fl.put(key, sp)


# ------------------------------------------------------------------ materials
def steel(w, h, base=(206, 210, 216), seed=0):
    """Brushed stainless steel (delegates to the shared realistic material)."""
    import real
    return real.steel(w, h, 0, tuple(base))


def panel(s, rect, title=None, size=16):
    gfx.card(s, rect, CARD)
    if title:
        draw_text(s, title, (rect[0] + 16, rect[1] + 12), size, INK, bold=True)


def label(s, rect, text, size=11, col=(250, 250, 244), ink=(60, 60, 70)):
    """A printed sticker label on equipment."""
    rect = pygame.Rect(rect)
    gfx.shadow(s, rect, 2, (1, 1), 50, 2)
    s.blit(R.rrect_surf(rect.w, rect.h, tuple(col), (170, 170, 164), 1, 2, 0.03, False), rect.topleft)
    draw_text(s, text, rect.center, size, ink, center=True, bold=True, vcenter=True)


def tremor(t, seed, amp=2.5):
    """Smooth hand tremor offset (sum of sines)."""
    x = (math.sin(t * 0.071 + seed) * 0.6 + math.sin(t * 0.173 + seed * 2.1) * 0.3 + math.sin(t * 0.41 + seed * 0.7) * 0.1) * amp
    y = (math.sin(t * 0.083 + seed * 1.7) * 0.6 + math.sin(t * 0.191 + seed * 0.3) * 0.3 + math.sin(t * 0.37 + seed * 1.1) * 0.1) * amp
    return x, y


def score01(v, lo, hi):
    return clamp((v - lo) / (hi - lo), 0, 1)


# ------------------------------------------------------------------ steps that remember earlier steps
CTX = None      # the station context of the step being set up; question generators read it


def ctx_get(name, default=None):
    """A value an earlier step of this technique left on the station (None in tests)."""
    return getattr(CTX, name, default) if CTX is not None else default


def _ctx_stages():
    from stage import QuizStage, CalcStage, register

    @register("cells_quiz")
    class CellsQuiz(QuizStage):
        """QuizStage whose question generators can read what earlier steps did (ctx_get).
        params: lead = optional generator(rng) -> question or None; when it returns a question,
        that question is asked first (it replaces the last of the drawn ones)."""
        def setup(self):
            global CTX
            CTX = self.ctx
            try:
                super().setup()
                lead = self.p.get("lead")
                q = lead(self.rng) if lead else None
                if q:
                    opts = list(enumerate(q["options"]))
                    if not q.get("keep_order"):
                        self.rng.shuffle(opts)
                    q["_opts"] = opts
                    self.qs = [q] + self.qs[:max(0, len(self.qs) - 1)]
            finally:
                CTX = None

    @register("cells_calc")
    class CellsCalc(CalcStage):
        """CalcStage whose problem generators can read what earlier steps did (ctx_get)."""
        def setup(self):
            global CTX
            CTX = self.ctx
            try:
                super().setup()
            finally:
                CTX = None


_ctx_stages()
