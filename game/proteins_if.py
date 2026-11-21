# -*- coding: utf-8 -*-
"""Immunofluorescence and fluorescence microscopy: dyes and lasers, focusing, photobleaching, controls."""
import math
import pygame
import audio
import gfx
import render as R
import real
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, TEAL, LAV, VIOLET, WHITE,
                  GREEN, RED, YELLOW, clamp, mix, lerp, draw_text, draw_wrapped)
from stage import Stage, register, TOP, BOTTOM
from proteins_common import cached, note_card

EMIT = {"DAPI": (90, 120, 255), "Alexa Fluor 488": (70, 230, 110), "mCherry": (255, 80, 90), "Alexa Fluor 647": (200, 60, 230)}
ROOM = (22, 20, 36)            # the darkened microscope room


def soft_blur(img, k):
    """Defocus blur without blocky steps: shrink, then grow back in two smooth stages."""
    w, h = img.get_size()
    k = max(1, int(k))
    small = pygame.transform.smoothscale(img, (max(1, w // k), max(1, h // k)))
    mid = pygame.transform.smoothscale(small, (max(1, w // max(1, k // 2)), max(1, h // max(1, k // 2))))
    mid = pygame.transform.smoothscale(mid, (max(1, mid.get_width() // 2 + 1), max(1, mid.get_height() // 2 + 1)))
    return pygame.transform.smoothscale(mid, (w, h))


def _blob(rng, c, r, n=14):
    """An irregular cell outline (spread fibroblast-like) around c."""
    pts = []
    lobes = [rng.uniform(0.75, 1.35) for _ in range(5)]
    ph = rng.uniform(0, math.tau)
    for k in range(n):
        a = k * math.tau / n
        f = 1 + 0.28 * math.sin(a * 2 + ph) + 0.18 * math.sin(a * 3 + ph * 1.7)
        f *= lobes[k * 5 // n]
        pts.append((c[0] + math.cos(a) * r * f, c[1] + math.sin(a) * r * f * 0.86))
    return pts


def make_cells(rng, size, n=7):
    """A merged three-channel confocal image: DAPI nuclei (blue), tubulin with Alexa 488 (green) and
    phalloidin-568 actin (red), added together, with blur, background and camera noise."""
    blue = pygame.Surface((size, size))
    green = pygame.Surface((size, size))
    red = pygame.Surface((size, size))
    for ch in (blue, green, red):
        ch.fill((0, 0, 0))
    cells = []
    for _ in range(n):
        for _try in range(40):
            c = (rng.uniform(60, size - 60), rng.uniform(60, size - 60))
            if all(math.dist(c, o) > 104 for o in cells):
                break
        cells.append(c)
    for c in cells:
        r = rng.uniform(42, 60)
        outline = _blob(rng, c, r)
        # cytoplasmic tubulin haze and a dense microtubule network radiating from the centrosome
        R.gd.filled_polygon(green, [(int(x), int(y)) for x, y in outline], (6, 34, 10))
        cen = (c[0] + rng.uniform(-10, 10), c[1] + rng.uniform(-10, 10))
        for k in range(46):
            a = k * math.tau / 46 + rng.uniform(-0.2, 0.2)
            bend = rng.uniform(-0.8, 0.8)
            pts = []
            for j in range(10):
                d = 6 + j * r * rng.uniform(0.11, 0.135)
                aa = a + bend * (j / 9.0) ** 1.5
                pts.append((cen[0] + math.cos(aa) * d, cen[1] + math.sin(aa) * d * 0.88))
            g = rng.randint(70, 150)
            pygame.draw.aalines(green, (int(g * 0.2), g, int(g * 0.25)), False, pts)
        R.gd.filled_circle(green, int(cen[0]), int(cen[1]), 3, (70, 220, 90))          # centrosome
        # actin: cortical rim and straight stress fibres across the cell
        pygame.draw.aalines(red, (150, 30, 30), True, outline)
        pygame.draw.lines(red, (70, 12, 14), True, outline, 3)
        for _ in range(rng.randint(5, 9)):
            i, j = rng.randrange(len(outline)), rng.randrange(len(outline))
            if abs(i - j) < 4:
                continue
            p, q = outline[i], outline[j]
            col = rng.randint(90, 200)
            pygame.draw.aaline(red, (col, int(col * 0.16), int(col * 0.16)), p, q)
            pygame.draw.line(red, (col // 3, 6, 6), p, q, 3)
        # nucleus: textured DAPI with darker nucleoli
        nw, nh = int(rng.uniform(30, 40)), int(rng.uniform(24, 32))
        nuc = pygame.Rect(0, 0, nw, nh)
        nuc.center = (int(c[0] + rng.uniform(-6, 6)), int(c[1] + rng.uniform(-6, 6)))
        bright = rng.uniform(0.7, 1.0)
        tex = gfx.texture(nw, nh, (int(70 * bright), int(96 * bright), int(255 * bright)), 3, 50, int(c[0] * 7 + c[1]), 2).copy()
        m = pygame.Surface((nw, nh), pygame.SRCALPHA)
        pygame.draw.ellipse(m, (255, 255, 255, 255), m.get_rect())
        t2 = pygame.Surface((nw, nh), pygame.SRCALPHA)
        t2.blit(tex, (0, 0))
        t2.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        blue.blit(t2, nuc.topleft)
        for _ in range(2):
            q = (nuc.x + rng.uniform(0.3, 0.7) * nw, nuc.y + rng.uniform(0.3, 0.7) * nh)
            R.gd.filled_circle(blue, int(q[0]), int(q[1]), 3, (14, 20, 70))
    img = pygame.Surface((size, size))
    img.fill((3, 3, 5))
    for ch, glow_k in ((blue, 6), (green, 4), (red, 4)):
        soft = gfx.blur(ch, 2)                      # optical resolution: nothing is perfectly sharp
        img.blit(soft, (0, 0), special_flags=pygame.BLEND_ADD)
        img.blit(gfx.blur(ch, glow_k * 2), (0, 0), special_flags=pygame.BLEND_ADD)   # out-of-focus light
    # camera noise and a faint uneven background
    noise = gfx.texture(size, size, (6, 6, 8), 1, 9, 97, 1)
    img.blit(noise, (0, 0), special_flags=pygame.BLEND_ADD)
    return img


def _vignette(size):
    """Round eyepiece mask: room colour outside, a soft dark rim inside."""
    def make():
        m = pygame.Surface((size, size), pygame.SRCALPHA)
        m.fill(ROOM + (255,))
        pygame.draw.circle(m, (0, 0, 0, 0), (size // 2, size // 2), size // 2 - 2)
        rim = pygame.Surface((size, size), pygame.SRCALPHA)
        for k in range(30):
            a = int(170 * (k / 30.0) ** 2)
            pygame.draw.circle(rim, (0, 0, 0, a), (size // 2, size // 2), size // 2 - 30 + k, 2)
        m.blit(rim, (0, 0))
        return m
    return cached(("vign2", size), make)


def eyepiece(s, img, center, size, label="20 um"):
    r = pygame.Rect(0, 0, size, size)
    r.center = center
    gfx.alpha_circle(s, (0, 0, 0), (center[0] + 6, center[1] + 8), size // 2 + 12, 110)
    s.blit(img, r.topleft)
    s.blit(_vignette(size), r.topleft)
    # black anodised eyepiece tube with a soft highlight
    R.aa_ring(s, center, size // 2 + 10, 12, (24, 24, 30))
    pygame.draw.arc(s, (80, 80, 92), (center[0] - size // 2 - 8, center[1] - size // 2 - 8, size + 16, size + 16), 1.9, 3.0, 3)
    bx, by = r.right - 112, r.bottom - 66
    pygame.draw.line(s, WHITE, (bx, by), (bx + 50, by), 3)
    draw_text(s, label, (bx + 25, by + 5), 12, WHITE, center=True, bold=True)


KNOB_C = (872, 356)            # coaxial focus knobs on the side of the stand
COARSE_R, FINE_R = 46, 22


def _knob(s, c, r, ang, col=(150, 152, 160), ridges=36):
    """A knurled focus knob seen face-on: dark rubber rim with ridges, brushed centre."""
    gfx.circle(s, (30, 30, 36), c, r, 0, None, True)
    for k in range(ridges):
        a = ang + k * math.tau / ridges
        p1 = (c[0] + math.cos(a) * r * 0.78, c[1] + math.sin(a) * r * 0.78)
        p2 = (c[0] + math.cos(a) * (r - 2), c[1] + math.sin(a) * (r - 2))
        pygame.draw.line(s, (72, 72, 82) if k % 2 else (18, 18, 22), p1, p2, 2)
    gfx.circle(s, col, c, r * 0.72, 1, R.lighten(col, -0.5), True)
    a = ang
    gfx.line(s, (240, 240, 244), (c[0] + math.cos(a) * r * 0.3, c[1] + math.sin(a) * r * 0.3),
             (c[0] + math.cos(a) * r * 0.64, c[1] + math.sin(a) * r * 0.64), 3)


def _tube_at(sf, a, b, w, col, alpha=255):
    """A shaded cylinder from a to b (eyepiece tubes, objectives seen from the side)."""
    L = int(math.dist(a, b))
    if L < 2:
        return
    m = pygame.Surface((w, L), pygame.SRCALPHA)
    pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=max(1, w // 4))
    cyl = real.shaded_mask(m, col, real.cyl_profile(w, 0.3, 0.09, 0.45, 0.6), alpha)
    ang = math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))
    rot = pygame.transform.rotate(cyl, ang)
    cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    sf.blit(rot, (int(cx - rot.get_width() / 2), int(cy - rot.get_height() / 2)))


def _scope_body(s):
    """An upright fluorescence microscope seen from the side in a darkened room: pale grey stand,
    trinocular head with a camera, epifluorescence lamp house at the back, objective turret, black
    mechanical stage with a slide, condenser, and coaxial focus knobs on the stand."""
    def make():
        sf = pygame.Surface((W, H), pygame.SRCALPHA)
        body = (176, 180, 188)
        dark = (36, 37, 44)
        sf.blit(real.contact_shadow(360, 22, 150), (588, 440))
        # base with the transmitted-light field diaphragm
        gfx.plastic_rect(sf, (596, 410, 330, 44), body, 12, 0.22)
        gfx.circle(sf, (60, 62, 70), (668, 431), 13, 2, (30, 30, 36), True)
        gfx.circle(sf, (230, 236, 244), (668, 431), 5, 0, None, False)
        # stand: pillar at the back and the arm reaching forward into the head
        gfx.plastic_rect(sf, (838, 150, 70, 270), R.lighten(body, -0.06), 16, 0.18)
        gfx.alpha_rect(sf, (846, 160, 6, 250), WHITE, 40, 3)
        gfx.plastic_rect(sf, (650, 118, 262, 56), body, 14, 0.22)
        draw_text(sf, "JUAN LAB", (790, 146), 11, (96, 98, 108), center=True, bold=True)
        # epifluorescence lamp house with cooling fins at the back of the head
        gfx.plastic_rect(sf, (908, 122, 40, 44), (64, 66, 74), 8, 0.25)
        for k in range(5):
            pygame.draw.line(sf, (40, 42, 48), (914 + k * 7, 126), (914 + k * 7, 162), 2)
        gfx.alpha_circle(sf, (120, 140, 255), (948, 144), 9, 60)
        # filter turret wheel on the side of the head (green filter selected)
        gfx.circle(sf, (58, 60, 68), (742, 148), 15, 2, (24, 24, 28), True)
        gfx.circle(sf, (90, 210, 120), (742, 140), 4, 0, None, False)
        # trinocular head: eyepieces angled towards the viewer, camera on the top port
        gfx.plastic_rect(sf, (664, 90, 116, 32), R.lighten(body, 0.04), 10, 0.25)
        _tube_at(sf, (690, 96), (648, 62), 20, dark)
        _tube_at(sf, (712, 98), (672, 64), 20, (46, 47, 54))
        for ex, ey in ((648, 62), (672, 64)):
            gfx.circle(sf, (24, 24, 28), (ex, ey), 11, 0, None, True)
        gfx.plastic_rect(sf, (752, 64, 28, 30), (60, 62, 70), 4, 0.25)
        gfx.plastic_rect(sf, (738, 30, 56, 36), (28, 28, 32), 6, 0.3)
        gfx.led(sf, (786, 40), (90, 220, 120), True, 3)
        # objective turret under the head: 63x oil in place, 10x and 20x swung to the sides
        R.aa_ellipse(sf, (150, 154, 162), (680, 170, 96, 22), 1, (80, 82, 90))
        _tube_at(sf, (700, 182), (678, 214), 16, (196, 198, 204))
        _tube_at(sf, (756, 182), (778, 214), 16, (196, 198, 204))
        gfx.metal_rect(sf, (716, 180, 26, 56), (206, 208, 214), 5)
        pygame.draw.rect(sf, (40, 60, 160), (716, 206, 26, 4))               # dark blue: 63x
        pygame.draw.rect(sf, (20, 20, 22), (716, 213, 26, 3))                # black: oil immersion
        pygame.draw.line(sf, (230, 190, 40), (676, 204), (692, 206), 3)       # yellow: 10x
        pygame.draw.line(sf, (60, 170, 80), (766, 206), (782, 204), 3)        # green: 20x
        gfx.metal_rect(sf, (721, 234, 16, 8), (180, 182, 190), 2)
        # stage with slide, coverslip and a drop of immersion oil
        gfx.plastic_rect(sf, (632, 248, 210, 16), dark, 4, 0.25)
        sf.blit(real.glass(96, 7, (236, 244, 248), 170, 1), (668, 242))
        pygame.draw.rect(sf, (236, 236, 228), (668, 242, 24, 7))             # frosted label end
        gfx.alpha_circle(sf, (250, 240, 200), (729, 243), 4, 170)
        gfx.plastic_rect(sf, (806, 262, 14, 44), (44, 44, 50), 4, 0.3)        # stage XY controls
        gfx.circle(sf, (60, 60, 68), (813, 310), 8, 1, (24, 24, 28), True)
        # condenser below the stage on its arm
        gfx.metal_rect(sf, (708, 266, 42, 30), (120, 124, 134), 5)
        gfx.plastic_rect(sf, (748, 274, 92, 12), R.lighten(body, -0.1), 4, 0.2)
        gfx.circle(sf, (230, 236, 244), (729, 300), 6, 1, (60, 62, 70), False)
        # hub of the focus knobs
        gfx.circle(sf, R.lighten(body, -0.2), KNOB_C, COARSE_R + 6, 1, (90, 92, 100), True)
        return sf
    s.blit(cached(("scope3",), make), (0, 0))


@register("if_focus")
class IfFocus(Stage):
    title = "Focus the microscope"
    instr = ("Turn the focus until the cells are sharp, then press Capture (or Space). Drag the outer coarse knob, "
             "use the mouse wheel or the inner fine knob for fine focus. The sample drifts: keep it sharp, and do not "
             "linger, because the lamp bleaches the dye while you look.")
    limit = 60
    SIZE = 400

    def setup(self):
        self.fields = self.p.get("fields", 3)
        self.k = 0
        self.scores = []
        self.log = []
        self.lamp = 0.0                      # seconds of excitation light on the sample
        self.window = self.lv(0.09, 0.07, 0.05)
        self.new_field()
        self.cap = gfx.Button((600, 466, 320, 42), "Capture", SAND, size=20)
        self.drag = None
        self.flash = 0
        self.hint = "Outer knob: coarse. Inner knob or wheel: fine. Space captures."

    def new_field(self):
        self.lamp = 0.0                      # a new field has fresh, unbleached dye
        self.img = make_cells(self.rng, self.SIZE)
        self.levels = [self.img] + [soft_blur(self.img, k) for k in (2, 3, 4, 6, 8, 11, 15)]
        self.focus = self.rng.choice([0.08, 0.22, 0.78, 0.92])
        self.true = self.rng.uniform(0.38, 0.62)
        self.phase = self.rng.uniform(0, 6.28)
        self.amp = self.lv(0.006, 0.012, 0.02) * (1 + 0.35 * self.k)
        self.freq = self.lv(0.015, 0.02, 0.03)
        self.t0 = self.t

    def target(self):
        return self.true + self.amp * math.sin(self.t * self.freq + self.phase)

    def sharp(self):
        return clamp(1 - abs(self.focus - self.target()) / self.window, 0, 1)

    def dye(self):
        return math.exp(-self.lamp * self.lv(0.003, 0.005, 0.007))

    def tick(self, inp):
        self.inp = inp
        self.lamp += 1 / 60.0
        if self.flash:
            self.flash -= 1
        if inp.wheel:
            self.focus = clamp(self.focus + inp.wheel * 0.004, 0, 1)
            audio.sfx("tick") if self.t % 3 == 0 else None
        if "up" in inp.held:
            self.focus = clamp(self.focus + 0.004, 0, 1)
        if "down" in inp.held:
            self.focus = clamp(self.focus - 0.004, 0, 1)
        if inp.click:
            d = math.dist(inp.mouse, KNOB_C)
            if d < FINE_R:
                self.drag = ("fine", inp.mouse[1])
            elif d < COARSE_R + 4:
                self.drag = ("coarse", inp.mouse[1])
        if self.drag and inp.down:
            kind, y0 = self.drag
            dy = y0 - inp.mouse[1]
            self.focus = clamp(self.focus + dy * (0.004 if kind == "coarse" else 0.0006), 0, 1)
            self.drag = (kind, inp.mouse[1])
        if not inp.down:
            self.drag = None
        if self.cap.hit(inp) or "space" in inp.pressed:
            self.capture()

    def capture(self):
        sc = self.sharp()
        secs = (self.t - self.t0) / 60.0
        speed = clamp(1 - (secs - 4) / self.lv(26, 18, 12), 0, 1)
        field = sc * (0.85 + 0.15 * speed)
        self.scores.append(field)
        self.log.append((sc, secs))
        self.flash = 20
        if sc > 0.8:
            audio.sfx("good")
            self.particles.burst(300, 120, 12, cols=(WHITE, (120, 230, 140), (120, 140, 255)))
        elif sc > 0.4:
            audio.sfx("ding")
        else:
            audio.sfx("bad")
            self.shake = 12
        self.floaters.add(300, 110, "Sharp!" if sc > 0.8 else "A bit soft" if sc > 0.4 else "Blurry", GREEN if sc > 0.8 else CORAL_D, 24)
        self.k += 1
        self.ctx.if_dye = self.dye()
        self.ctx.if_lamp = self.lamp
        if self.k >= self.fields:
            avg = sum(self.scores) / len(self.scores)
            parts = ", ".join("%d%% in %d s" % (a * 100, b) for a, b in self.log)
            self.finish(100 * avg, "Sharpness per field: %s." % parts,
                        "%d s under the lamp on the last field bleached %d%% of its dye." % (self.lamp, (1 - self.dye()) * 100),
                        "Focus on the nuclei first: they are bright and have crisp edges.")
        else:
            self.new_field()

    def partial(self):
        self.ctx.if_dye = self.dye()
        self.ctx.if_lamp = self.lamp
        return 100 * sum(self.scores) / self.fields

    def autoplay(self):
        self.ctx.if_dye = 0.93
        self.ctx.if_lamp = 15.0
        self.finish(92, "(autoplay)")

    def render(self, s):
        s.fill(ROOM)
        d = abs(self.focus - self.target())
        idx = min(len(self.levels) - 1, int(d / (self.window * 0.32)))
        eyepiece(s, self.levels[idx], (300, 296), self.SIZE)
        if self.flash:
            gfx.alpha_circle(s, WHITE, (300, 296), self.SIZE // 2, self.flash * 10)
        draw_text(s, "Field %d of %d" % (min(self.k + 1, self.fields), self.fields), (300, TOP + 4), 16, (220, 220, 240), center=True, bold=True)
        _scope_body(s)
        _knob(s, KNOB_C, COARSE_R, self.focus * math.tau * 2)
        _knob(s, KNOB_C, FINE_R, self.focus * math.tau * 14, (214, 214, 224), 20)
        draw_text(s, "Focus knobs: outer coarse, inner fine", (700, 388), 12, (210, 210, 226), center=True, bold=True)
        # dye left: the lamp is on while you look
        bx = pygame.Rect(600, 336, 200, 44)
        gfx.rrect(s, bx, (40, 38, 60), (90, 88, 120), 1, 8, 0.1)
        draw_text(s, "Dye left", (bx.x + 10, bx.y + 5), 12, (210, 210, 230), bold=True)
        gfx.bar(s, (bx.x + 10, bx.y + 23, bx.w - 20, 12), self.dye(), (220, 90, 200), back=(30, 30, 40))
        self.cap.draw(s, getattr(self, "inp", None))


def scene_bleach(st, s, v):
    s.fill(ROOM)
    if not hasattr(st, "_img"):
        st._img = make_cells(st.rng, 380, 6)
        st._tmp = pygame.Surface((380, 380))
        st._noise = [gfx.texture(380, 380, (40, 40, 46), 1.2, 40, 90 + k, 1) for k in range(3)]
    dye0 = getattr(st.ctx, "if_dye", 1.0)       # what focusing under the lamp left
    remain = dye0 * math.exp(-1.65 * v * v)
    sig = v * remain / 0.33          # 1.0 at the best point (with a fresh sample)
    show = clamp(sig, 0, 1.0)
    st._tmp.blit(st._img, (0, 0))
    g = int(255 * show)
    st._tmp.fill((g, g, g), special_flags=pygame.BLEND_MULT)
    nz = st._noise[(st.t // 4) % 3]           # camera read noise, visible when the signal is weak
    nz.set_alpha(int(200 * (1 - show)))
    st._tmp.blit(nz, (0, 0), special_flags=0)
    nz.set_alpha(None)
    eyepiece(s, st._tmp, (290, 296), 380)
    panel = pygame.Rect(540, 160, 390, 250)
    gfx.rrect(s, panel, (44, 42, 66), INK, 2, 14, 0.1)
    draw_text(s, "Dye remaining", (panel.x + 24, panel.y + 20), 15, (230, 230, 240), bold=True)
    gfx.bar(s, (panel.x + 24, panel.y + 46, panel.w - 48, 18), remain, (220, 90, 200), back=(30, 30, 40))
    draw_text(s, "Signal in this frame", (panel.x + 24, panel.y + 80), 15, (230, 230, 240), bold=True)
    gfx.bar(s, (panel.x + 24, panel.y + 106, panel.w - 48, 18), show, (110, 220, 140), back=(30, 30, 40))
    y = draw_wrapped(s, "Every second of excitation light destroys some fluorophore. Longer exposure collects more "
                     "signal per frame, but the image fades as the dye bleaches.", (panel.x + 24, panel.y + 142), 13,
                     panel.w - 48, (200, 200, 220))
    if dye0 < 0.995:
        draw_wrapped(s, "Focusing on this field for %d s already bleached %d%% of its dye. Focus on a neighbouring "
                     "area, then move to fresh cells to capture." % (getattr(st.ctx, "if_lamp", 0), round((1 - dye0) * 100)), (panel.x + 24, y + 6), 13, panel.w - 48, (240, 190, 230))
    if st.state == "stopped":
        gfx.tag(s, 290, 482, "Captured", (196, 236, 200), 16, center=True)
    elif st.state == "over":
        gfx.tag(s, 290, 482, "Bleached", (250, 200, 196), 16, center=True)


def draw_fluor(s, r, label):
    col = EMIT.get(label.split(" (")[0], WHITE)
    c = (r.x + 30, r.centery)
    gfx.circle(s, (24, 22, 36), c, 18, 2)
    gfx.glow(s, c, 15, col, 0.9)
    gfx.circle(s, col, c, 7, 0)
    draw_wrapped(s, label, (r.x + 56, r.y + 8), 15, r.w - 64, INK, bold=True)


TECH = dict(
    key="if", name="Immunofluorescence", full="Immunofluorescence and fluorescence microscopy", wing="Proteins", icon="micro",
    blurb="Shows where a protein sits inside cells. Antibodies carrying fluorescent dyes bind the protein, and a "
          "microscope lights each dye with its own colour of light.",
    facts=[
        "Green fluorescent protein comes from the jellyfish Aequorea victoria. Osamu Shimomura, Martin Chalfie and Roger Tsien shared the 2008 Nobel Prize in Chemistry for it.",
        "Albert Coons and colleagues first attached a fluorescent dye to an antibody in 1941.",
        "Light emitted by a fluorophore has a longer wavelength than the light that excites it. The gap is called the Stokes shift, after George Stokes.",
        "Secondary antibodies amplify the signal because several of them can bind one primary antibody.",
        "Antifade mounting media slow photobleaching by scavenging the reactive oxygen that destroys fluorophores.",
        "Marvin Minsky filed a patent for the confocal microscope in 1957; its pinhole blocks out-of-focus light.",
        "Far-red dyes such as Alexa Fluor 647 help in tissues like zebrafish embryos, where natural autofluorescence is weaker at long wavelengths.",
    ],
    quiz=[
        dict(q="Your primary antibody was raised in rabbit. Which secondary do you use?", options=["Anti-rabbit IgG, e.g. made in goat",
             "Anti-goat IgG", "Anti-mouse IgG", "Any secondary works"], answer=0,
             why="The secondary must recognise the species of the primary."),
        dict(q="Why permeabilise fixed cells with a detergent such as Triton X-100?", options=["So antibodies can get through the membranes to proteins inside",
             "To fix the proteins", "To stain the nuclei", "To stop bleaching"], answer=0,
             why="Antibodies are large and cannot cross intact membranes."),
        dict(q="Which control shows that the secondary antibody alone does not stain the cells?", options=["Leave out the primary antibody",
             "Leave out the secondary antibody", "Use no DAPI", "Image at lower power"], answer=0,
             why="A secondary-only control reveals background from non-specific binding of the secondary."),
        dict(q="Two dyes bleed into each other's channels. What helps most?", options=["Choose dyes whose spectra overlap less, and image them one after another",
             "Increase the laser power", "Use a longer exposure", "Add more antibody"], answer=0,
             why="Well-separated spectra and sequential imaging reduce bleed-through."),
    ],
    music=dict(name="Confocal Nocturne", bpm=72, beats=4, root=52, mode="lyd", prog=[0, 1, 0, 4, 5, 1, 3, 4],
               lead="epiano", comp="pad", drums="none",
               motif=[(4, 3), (3, 1), (4, 2), (6, 2), (7, 6), (4, 2)]),
    stages=[
        ("match", dict(title="Dyes and lasers", left_title="Fluorophore", right_title="Excitation and emission",
                       instr="Match each dye to the laser that excites it and the colour it gives off.", tint=(60, 58, 84),
                       draw_left=draw_fluor, left_col=(250, 248, 240),
                       pairs=[("DAPI (binds DNA)", "405 nm laser, blue light around 460 nm", "DAPI binds DNA and marks nuclei; a 405 nm laser excites it on most confocals."),
                              ("Alexa Fluor 488 (like GFP)", "488 nm laser, green light around 520 nm", "The 488 nm line excites GFP and Alexa 488."),
                              ("mCherry (red protein)", "561 nm laser, red light around 610 nm", "mCherry is derived from DsRed, a red protein from a Discosoma sea anemone."),
                              ("Alexa Fluor 647 (far red)", "640 nm laser, far-red light around 670 nm", "Far-red light is hard to see by eye, but the camera picks it up well.")])),
        ("if_focus", dict(fields=3)),
        ("stop", dict(title="Capture before it fades", scene=scene_bleach, dur=8.0, ideal=0.55, window=(0.38, 0.78), rounds=2,
                      readout=lambda v: "exp %4d ms" % (v * 2000),
                      instr="The exposure rises step by step while the lamp bleaches the dye. Capture when the image is "
                            "brightest, before the fading wins.",
                      early_msg="Too dim: the image is mostly camera noise.",
                      late_msg="The dye had already faded: much of the signal was bleached away.",
                      over_msg="The sample bleached before you captured it.",
                      good_msg="Captured at a bright, clean point.")),
        ("quiz", dict(title="Antibodies and controls", n=3, tint=LAV,
                      questions=[
                          dict(q="Your primary antibody was raised in mouse. Which secondary do you use?", options=["Anti-mouse IgG, e.g. made in goat",
                               "Anti-rabbit IgG", "Anti-goat IgG", "Mouse IgG"], answer=0,
                               why="The secondary recognises the constant part of antibodies from the primary's species."),
                          dict(q="Why fix cells with formaldehyde before staining?", options=["It cross-links proteins and holds them in place",
                               "It makes the cells fluorescent", "It removes membranes", "It blocks non-specific binding"], answer=0,
                               why="Fixation freezes the cell's structure so washing does not wash proteins away."),
                          dict(q="What causes photobleaching?", options=["Light-driven chemical damage to the fluorophore, mostly by reactive oxygen",
                               "The camera heating up", "Antibodies falling off", "Evaporation of the mounting medium"], answer=0,
                               why="Each excitation has a small chance of destroying the dye. Less light and antifade media slow it."),
                          dict(q="Why do you block with serum from the species the secondary was made in?", options=[
                               "To occupy sites the secondary would otherwise stick to", "To fix the cells", "To feed the cells",
                               "To make the dye brighter"], answer=0,
                               why="Normal serum from the secondary's host species reduces background from the secondary.")])),
    ],
)
TECHS = [TECH]
