# -*- coding: utf-8 -*-
"""Lipofection: getting plasmid DNA into cultured cells with cationic lipids."""
import math
import random
import pygame
import audio
import gfx
import render as R
from stage import Stage, register, TOP, BOTTOM
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, LAV, VIOLET, NIGHT, WHITE,
                  GREEN, RED, YELLOW, BLUE, clamp, mix, lerp, draw_text, draw_wrapped)
import real
from cells_common import ell_pts, scope_mask, scope_card, field_bg, masked_field, soften, fluo_cell_sprite, photo_finish

LIPID = (246, 206, 84)
DNA = (60, 110, 210)
GFP = (90, 230, 110)
HEAD = (232, 110, 80)
CW, CH = 34, 22          # half-width and height of a cell seen from the side

_SPR = {}


def _vesicle_sprite(r, dna):
    key = (int(r), dna)
    sp = _SPR.get(key)
    if sp is not None:
        return sp
    S = 3
    n = int(2 * r + 8)
    big = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
    c = n * S // 2
    rr = r * S
    pygame.draw.circle(big, (255, 236, 160, 230), (c, c), int(rr))
    pygame.draw.circle(big, (250, 222, 130), (c, c), int(rr * 0.62))
    k = max(8, int(r * 1.6))
    for ring, rad, sz in ((0, rr, 1.25), (1, rr * 0.62, 1.0)):
        for j in range(k if ring == 0 else max(6, int(k * 0.62))):
            a = j * math.tau / (k if ring == 0 else max(6, int(k * 0.62)))
            pygame.draw.circle(big, HEAD, (int(c + math.cos(a) * rad), int(c + math.sin(a) * rad)), max(2, int(S * sz)))
    if dna:
        pts = [(c + math.cos(t * 0.5) * rr * 0.32 + math.sin(t * 2.3) * rr * 0.12, c + math.sin(t * 0.5) * rr * 0.32 + math.cos(t * 1.9) * rr * 0.12)
               for t in [i * math.tau * 2 / 24 for i in range(25)]]
        pygame.draw.lines(big, DNA, False, pts, max(2, S))
    pygame.draw.circle(big, (255, 255, 255, 170), (int(c - rr * 0.4), int(c - rr * 0.4)), max(2, int(rr * 0.16)))
    sp = pygame.transform.smoothscale(big, (n, n))
    _SPR[key] = sp
    return sp


def plasmid(s, x, y, r=6, col=DNA):
    for k in range(2):
        R.gd.aacircle(s, int(x), int(y), int(r) - k, col)
    pts = [(x + math.cos(a) * r, y + math.sin(a) * r) for a in (0.3, 1.9, 3.6, 5.0)]
    for px, py in pts:
        R.gd.filled_circle(s, int(px), int(py), 2, R.lighten(col, 0.35))


def vesicle(s, x, y, r=8):
    sp = _vesicle_sprite(r, False)
    s.blit(sp, (int(x - sp.get_width() / 2), int(y - sp.get_height() / 2)))


def lipoplex(s, x, y, r=8):
    sp = _vesicle_sprite(r, True)
    s.blit(sp, (int(x - sp.get_width() / 2), int(y - sp.get_height() / 2)))


def _cell_sprite(glow):
    """An adherent cell seen in cross-section: a flattened translucent dome (no outline), a darker
    perinuclear zone and a grey nucleus with a nucleolus. GFP adds a green tint (the glow itself is
    added separately, as light)."""
    g = int(glow * 10)
    key = ("cell", g)
    sp = _SPR.get(key)
    if sp is not None:
        return sp
    S = 3
    w, h = (2 * CW + 14), (CH + 12)
    big = pygame.Surface((w * S, h * S), pygame.SRCALPHA)
    cx, base = w * S // 2, (h - 2) * S
    gg = g / 10.0

    def dome(cw, ch, lift=0):
        return [(cx + cw * S * math.cos(t), base - lift * S - ch * S * math.sin(t) ** 0.8) for t in [i * math.pi / 36 for i in range(37)]]
    cyto = mix((214, 196, 196), (150, 230, 150), gg * 0.8)
    pygame.draw.polygon(big, R.lighten(cyto, -0.28) + (230,), dome(CW, CH) + [(cx - CW * S, base), (cx + CW * S, base)])
    pygame.draw.polygon(big, cyto + (190,), dome(CW - 1.3, CH - 1.4) + [(cx - (CW - 1.3) * S, base), (cx + (CW - 1.3) * S, base)])
    inner = pygame.Surface((w * S, h * S), pygame.SRCALPHA)
    pygame.draw.polygon(inner, R.lighten(cyto, -0.12) + (150,), dome(CW * 0.55, CH * 0.8, 1) + [(cx - CW * 0.55 * S, base), (cx + CW * 0.55 * S, base)])
    big.blit(soften(inner, 2.4), (0, 0))
    nuc = mix((136, 132, 156), (110, 160, 120), gg * 0.35)
    pygame.draw.ellipse(big, nuc + (230,), (cx - 11 * S, base - 15 * S, 22 * S, 12 * S))
    pygame.draw.circle(big, R.lighten(nuc, -0.4) + (230,), (cx + 3 * S, base - 9 * S), int(2.2 * S))
    sp = pygame.transform.smoothscale(big, (w, h))
    _SPR[key] = sp
    return sp


_DISH = {}


def _dish_layer():
    """Cross-section of a polystyrene dish with pink medium: clear walls and floor, a meniscus,
    light falling in from above, and the shelf-lit lab behind seen through the medium."""
    if "bg" in _DISH:
        return _DISH["bg"]
    sf = pygame.Surface((W, H), pygame.SRCALPHA)
    med = pygame.Rect(40, TOP + 96, W - 80, 468 - TOP - 96)
    tex = gfx.texture(med.w, med.h, (236, 176, 190), 60, 5, 61, 2)
    m = pygame.Surface(med.size, pygame.SRCALPHA)
    m.blit(tex, (0, 0))
    m.blit(R.vgrad(med.size, (255, 255, 255), (214, 196, 204)), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    m.set_alpha(244)
    sf.blit(m, med.topleft)
    rays = pygame.Surface(med.size, pygame.SRCALPHA)       # soft light shafts from the microscope lamp
    for i in range(5):
        x = 80 + i * 190
        pygame.draw.polygon(rays, (255, 255, 255, 26), [(x, 0), (x + 60, 0), (x + 110, med.h), (x + 30, med.h)])
    sf.blit(soften(rays, 6), med.topleft)
    pygame.draw.line(sf, (255, 240, 244, 230), (med.x, med.y + 1), (med.right, med.y + 1), 3)       # meniscus
    pygame.draw.line(sf, (190, 120, 140, 160), (med.x, med.y + 4), (med.right, med.y + 4), 1)
    for x in (30, W - 40):                              # clear walls
        sf.blit(real.glass(10, 468 - TOP - 80 + 16, (224, 236, 240), 120, 3), (x, TOP + 80))
    sf.blit(real.glass(W - 60, 16, (224, 236, 240), 150, 3), (30, 468))
    _DISH["bg"] = sf
    return sf


# ------------------------------------------------------------------ cryo-EM view of the complexes
def _cryo_vesicle(r, lamellae=1, dna=False, seed=0):
    """A lipid vesicle as cryo-EM shows it: dark bilayer rings on a grey ice background; a
    lipoplex is multilamellar (onion rings) with DNA strands between the layers."""
    key = ("cryo", int(r), lamellae, dna, seed % 3)
    sp = _SPR.get(key)
    if sp is not None:
        return sp
    S = 3
    n = int(2 * r + 10)
    big = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
    c = n * S // 2
    rnd = random.Random(seed)
    for k in range(lamellae):
        rr = (r - k * 3.2) * S
        if rr < 3 * S:
            break
        pts = [(c + math.cos(t) * rr * (1 + 0.04 * math.sin(3 * t + seed)), c + math.sin(t) * rr * (1 + 0.04 * math.sin(3 * t + seed)))
               for t in [i * math.tau / 48 for i in range(48)]]
        pygame.draw.polygon(big, (40, 40, 44, 200), pts, int(1.1 * S))
        inner = [((x - c) * (rr - 1.6 * S) / rr + c, (y - c) * (rr - 1.6 * S) / rr + c) for x, y in pts]
        pygame.draw.polygon(big, (40, 40, 44, 170), inner, max(1, int(0.9 * S)))
        if dna and k < lamellae - 1:
            for j in range(10):
                a = j * math.tau / 10 + rnd.uniform(-0.1, 0.1)
                rd = rr - 2.4 * S
                pygame.draw.circle(big, (30, 30, 34, 200), (int(c + math.cos(a) * rd), int(c + math.sin(a) * rd)), max(1, int(0.7 * S)))
    sp = soften(pygame.transform.smoothscale(big, (n, n)), 1.2)
    _SPR[key] = sp
    return sp


def _cryo_dna(s, x, y, ph, length=34):
    pts = [(x + math.cos(ph) * t + math.sin(t * 0.25 + ph) * 4, y + math.sin(ph) * t + math.cos(t * 0.2 + ph) * 4) for t in range(-length // 2, length // 2, 2)]
    pygame.draw.aalines(s, (36, 36, 40), False, pts)
    pygame.draw.aalines(s, (60, 60, 64), False, [(px + 1, py) for px, py in pts])


def _complex_scene(st, s, v):
    gfx.bench(s, LAV)
    if not hasattr(st, "_parts"):
        r = random.Random(11)
        st._parts = []
        for i in range(16):
            mx, my = r.uniform(-0.72, 0.72), r.uniform(-0.72, 0.72)
            st._parts.append((mx + r.uniform(-0.25, 0.25), my + r.uniform(-0.25, 0.25), mx + r.uniform(-0.25, 0.25),
                              my + r.uniform(-0.25, 0.25), mx, my, i % 5, r.uniform(0, 6.3)))
        st._groups = [(r.uniform(-0.5, 0.5), r.uniform(-0.5, 0.5)) for _ in range(5)]
    # the real thing: a tube of Opti-MEM with DNA and lipid, on the bench
    gfx.tube(s, 120, 330, 40, 104, (232, 196, 206), 0.55, (238, 238, 232))
    from cells_common import label as _label
    _label(s, (100, 448, 84, 18), "DNA + lipid", 10)
    c, R_ = (370, 286), 176
    scope_card(s, c, R_)
    m = clamp(v / 0.42, 0, 1)
    agg = clamp((v - 0.67) / 0.33, 0, 1)

    def field(f, cc):
        field_bg(f, cc, R_, (138, 138, 140), 2)
        for dx, dy, lx, ly, mx, my, g, ph in st._parts:
            wob = (math.sin(st.t * 0.05 + ph) * 0.02, math.cos(st.t * 0.04 + ph) * 0.02)
            gx, gy = st._groups[g]
            if m < 1:
                _cryo_dna(f, cc[0] + (lerp(dx, mx, m) + wob[0]) * R_, cc[1] + (lerp(dy, my, m) + wob[1]) * R_, ph)
                sp = _cryo_vesicle(11, 1, False, int(ph * 10))
            else:
                sp = _cryo_vesicle(14, 3, True, int(ph * 10))
            if m < 1:
                x, y = cc[0] + (lerp(lx, mx, m) - wob[0]) * R_, cc[1] + (lerp(ly, my, m) - wob[1]) * R_
            else:
                x = cc[0] + (lerp(mx, gx + math.cos(ph) * 0.07, agg) + wob[0] * (1 - agg)) * R_
                y = cc[1] + (lerp(my, gy + math.sin(ph) * 0.07, agg) + wob[1] * (1 - agg)) * R_
            f.blit(sp, (int(x - sp.get_width() / 2), int(y - sp.get_height() / 2)))
    masked_field(s, c, R_, field, blur=1.0)
    gfx.rrect(s, (c[0] - 60, c[1] + R_ - 30, 50, 4), (240, 240, 240), None, 0, 1, 0, False)
    draw_text(s, "250 nm", (c[0] - 35, c[1] + R_ - 46), 11, (240, 240, 240), center=True, bold=True)
    draw_text(s, "cryo-electron micrograph (illustration)", (c[0], c[1] + R_ - 3), 11, (170, 172, 180), center=True)
    p = pygame.Rect(580, TOP + 100, 350, 300)
    gfx.card(s, p, CARD)
    draw_text(s, "In serum-free medium", (p.x + 16, p.y + 14), 17, INK, bold=True)
    for k, (txt, kind) in enumerate((("plasmid DNA (negative)", "dna"), ("cationic lipid vesicle (positive)", "ves"), ("lipoplex: DNA between lipid layers", "plex"))):
        y = p.y + 62 + k * 36
        gfx.circle(s, (138, 138, 140), (p.x + 32, y), 15, 1, (90, 90, 96), False)
        if kind == "dna":
            _cryo_dna(s, p.x + 32, y, 0.4, 20)
        else:
            sp = _cryo_vesicle(9 if kind == "ves" else 13, 1 if kind == "ves" else 3, kind == "plex", 3)
            s.blit(sp, (p.x + 32 - sp.get_width() // 2, y - sp.get_height() // 2))
        draw_text(s, txt, (p.x + 56, y - 9), 14, INK)
    draw_wrapped(s, "The kit says: incubate about 15 minutes at room temperature, then add the complexes to the cells.",
                 (p.x + 16, p.y + 172), 15, p.w - 32, INK_SOFT)
    gfx.bar(s, (p.x + 16, p.y + 240, p.w - 32, 18), v, CORAL)
    lo, hi = getattr(st, "window", (1 / 3.0, 2 / 3.0))
    gfx.alpha_rect(s, (p.x + 16 + (p.w - 32) * lo, p.y + 234, (p.w - 32) * (hi - lo), 30), GREEN, 80)
    if getattr(st, "state", "run") != "run":          # remember whether the stop was early or late for the next step
        st.ctx.complex_v = (v, lo, hi)
    draw_text(s, "0", (p.x + 16, p.y + 262), 12, MUTED)
    draw_text(s, "30 min", (p.right - 16, p.y + 262), 12, MUTED, right=True)


# ------------------------------------------------------------------ delivery
@register("transfect_shoot")
class TransfectShoot(Stage):
    title = "Deliver the lipoplexes"
    instr = ("Move the pipette along the dish and click to let a drop of lipoplexes fall onto the cells. It must land on top "
             "of a cell (the nucleus area); each cell needs one. The cell takes it up by endocytosis and starts making GFP. "
             "You have only a few spare drops. (A game shortcut: in a real dish the drops spread through the medium and "
             "nobody aims at single cells.)")
    limit = 45

    def setup(self):
        self.ammo = self.ammo0 = self.lv(10, 9, 8)
        self.goal = 7
        # how well the complexes formed in the previous step: late incubation gives big aggregates that sink unevenly
        prev = getattr(self.ctx, "scores", None)
        q = prev[-1] if prev else 100
        self.agg = q < 60
        cv = getattr(self.ctx, "complex_v", None)
        self.early = bool(self.agg and cv is not None and cv[0] < cv[1])    # stopped before the complexes had formed
        self.wobble = self.lv(0.2, 0.25, 0.35) * (3.0 if self.agg else 1.0)
        self.shot_v = 8.0 * (0.8 if self.agg else 1.0)
        self.cool = 0
        self.shots = []
        self.settled = []
        self.trans = 0
        self.end_t = None
        self.cells = []
        for i in range(7):
            # cells crawl back and forth around their place on the dish floor (never into each other)
            amp = self.rng.uniform(*self.lv((6, 14), (12, 24), (18, 30)))
            per = self.rng.uniform(*self.lv((200, 300), (150, 240), (110, 180)))
            home = 110 + i * 123
            ph = self.rng.uniform(0, 6.3)
            self.cells.append({"home": home, "amp": amp, "w": math.tau / per, "ph": ph, "hit": None,
                               "x": home + amp * math.sin(ph), "vx": 0.0})
        self.launcher = (480, TOP + 70)
        self.mouse = (480, 300)
        self.hint = "Click to drop a lipoplex. It takes a moment to sink: drop ahead of moving cells."
        self.hit_w = self.lv(0.7, 0.62, 0.55)     # how much of a cell's width counts as landing on it
        self.wasted = 0
        if self.agg:
            self.hint = ("Your complexes had not finished forming: much of the DNA is free and delivery is poor. Aim carefully."
                         if self.early else "Your complexes formed badly: the large aggregates sink slowly and drift. Aim carefully.")

    def tick(self, inp):
        self.mouse = inp.mouse
        if self.cool:
            self.cool -= 1
        for c in self.cells:
            nx = self.cell_x(c, self.t)
            c["vx"] = nx - c["x"]
            c["x"] = nx
        self.launcher = (int(clamp(inp.mouse[0], 70, W - 70)), self.launcher[1])
        if inp.click and self.ammo > 0 and not self.cool:
            lx, ly = self.launcher
            self.shots.append({"x": lx, "y": ly + 30, "vx": 0.0, "vy": self.shot_v * 0.8})
            self.ammo -= 1
            self.cool = 14
            audio.sfx("pop")
        for sh in self.shots:
            sh["x"] += sh["vx"] + self.rng.uniform(-self.wobble, self.wobble)
            sh["y"] += sh["vy"]
            if sh["x"] < 50 or sh["x"] > W - 50:
                sh["vx"] *= -0.6
                sh["x"] = clamp(sh["x"], 50, W - 50)
            for c in self.cells:
                ex, ey = (sh["x"] - c["x"]) / float(CW * self.hit_w + 3), (sh["y"] - 466) / float(CH + 3)
                if ex * ex + ey * ey < 1:
                    sh["dead"] = True
                    if c["hit"] is None:
                        c["hit"] = self.t
                        c["ent"] = (sh["x"] - c["x"], sh["y"] - 456)
                        self.trans += 1
                        audio.sfx("good")
                        self.floaters.add(c["x"], 400, "uptake!", GREEN, 18)
                        self.particles.burst(sh["x"], sh["y"], 10, cols=(LIPID, GFP, WHITE), speed=2.5)
                    else:
                        self.wasted += 1
                        audio.sfx("blip")
                        self.floaters.add(c["x"], 400, "already has DNA", CORAL_D, 16)
                    break
            if sh["y"] > 462 and not sh.get("dead"):
                sh["dead"] = True
                self.settled.append([sh["x"], 120])
                self.wasted += 1
                self.floaters.add(sh["x"], 430, "missed", MUTED, 15)
        self.shots = [sh for sh in self.shots if not sh.get("dead")]
        for st in self.settled:
            st[1] -= 1
        self.settled = [st for st in self.settled if st[1] > 0]
        if self.end_t is None and (self.trans >= len(self.cells) or (self.ammo == 0 and not self.shots)):
            self.end_t = self.t + 90        # let the GFP come up before the result
        if self.end_t is not None and self.t >= self.end_t:
            self.ctx.transfect_frac = self.trans / float(len(self.cells))
            fb = ["%d of %d cells took up DNA with %d lipoplexes (%d wasted)." % (self.trans, len(self.cells), self.ammo0 - self.ammo, self.wasted)]
            if self.agg:
                fb.append("The complexes were stopped before they had formed, so less DNA was packed and delivery was poor."
                          if self.early else "The complexes were incubated too long, so they grew large and settled unevenly.")
            fb.append("Game shortcut: in a real dish the drops spread through the medium and every cell takes up many; nobody aims at single cells.")
            fb.append("In a real dish only part of the DNA escapes the endosome and reaches the nucleus; GFP appears after about a day.")
            self.finish(self.score_now(), *fb)

    def cell_x(self, c, t):
        return c["home"] + c["amp"] * math.sin(c["w"] * t + c["ph"])

    def score_now(self):
        spare = self.ammo0 - self.goal
        return max(0, min(100, 100.0 * self.trans / self.goal) - self.lv(4, 6, 8) * max(0, self.wasted - spare))

    def partial(self):
        self.ctx.transfect_frac = self.trans / float(len(self.cells))
        return self.score_now()

    def autoplay(self):
        self.ctx.transfect_frac = 6 / 7.0
        self.finish(100, "6 of 7 cells took up DNA.")

    def render(self, s):
        gfx.bench(s, LAV)
        s.blit(_dish_layer(), (0, 0))
        for c in self.cells:
            x = c["x"]
            glow = 0.0
            if c["hit"] is not None:
                glow = clamp((self.t - c["hit"] - 50) / 80.0, 0, 1)
            sp = _cell_sprite(glow)
            s.blit(sp, (int(x - sp.get_width() / 2), 468 - sp.get_height() + 2))
            if glow:
                R.glow(s, (x, 452), CW + 16, (30, 120, 40), glow)
            if c["hit"] is not None:
                k = clamp((self.t - c["hit"]) / 50.0, 0, 1)    # the vesicle is engulfed (endocytosis), then DNA moves to the nucleus
                ex, ey = c["ent"]
                vx, vy = x + ex * (1 - k) * 0.6, 456 + ey * (1 - k) * 0.4 + 2 * k
                if k < 1:
                    lipoplex(s, vx, vy, 7 * (1 - k * 0.35))
                    if k > 0.3:
                        for j in range(2):
                            R.gd.aacircle(s, int(vx), int(vy), int(7 * (1 - k * 0.35)) + 2 + j, (150, 120, 126))
                else:
                    R.gd.filled_circle(s, int(x + 2), 458, 3, DNA)
                    R.gd.aacircle(s, int(x + 2), 458, 3, R.lighten(DNA, -0.3))
        for x, life in self.settled:
            sp = _vesicle_sprite(6, True)
            sp.set_alpha(min(255, life * 3))
            s.blit(sp, (int(x - 7), 458))
            sp.set_alpha(None)
        for sh in self.shots:
            lipoplex(s, sh["x"], sh["y"], 8)
        lx, ly = self.launcher
        mx, my = self.mouse
        if self.ammo:
            for k in range(1, int((440 - ly) / 22)):
                gfx.alpha_circle(s, CORAL, (lx, ly + 30 + k * 22), 2.0, max(30, 200 - k * 12))
        gfx.pipette(s, (lx, ly + 30), LIPID, 0.6, scale=0.55)
        gfx.rrect(s, (40, TOP + 8, 26 + self.ammo0 * 22, 30), CARD, INK, 2, 15, 0.05)
        draw_text(s, "dish seen in cross-section", (60, TOP + 106), 12, (120, 70, 86), bold=True)
        for i in range(self.ammo0):
            if i < self.ammo:
                lipoplex(s, 60 + i * 22, TOP + 23, 7)
            else:
                gfx.alpha_circle(s, MUTED, (60 + i * 22, TOP + 23), 7, 60)
        gfx.tag(s, W - 40 - 170, TOP + 10, "Transfected: %d / %d" % (self.trans, len(self.cells)), CARD, 15)
        if self.agg:
            gfx.tag(s, W // 2 - 120, TOP + 10, "complexes aggregated: drops drift", (250, 220, 200), 13)


# ------------------------------------------------------------------ efficiency
EFF = [10, 25, 50, 80]


def _eff_q(rng, k=None):
    if k is None:
        k = rng.randrange(4)
    pct = EFF[k]
    seed = rng.randrange(10 ** 6)

    def pic(s, rect):
        r = random.Random(seed)
        f = pygame.Surface(rect.size)
        f.fill((4, 5, 8))
        pts = []
        tries = 0
        while len(pts) < 40 and tries < 3000:
            tries += 1
            x, y = r.uniform(22, rect.w - 22), r.uniform(22, rect.h - 40)
            if all(math.hypot(x - a, y - b) > 38 for a, b in pts):
                pts.append((x, y))
        green = set(r.sample(range(len(pts)), int(round(len(pts) * pct / 100.0))))
        for i, (x, y) in enumerate(pts):
            gfp = r.uniform(0.35, 1.0) if i in green else 0.0
            sp = fluo_cell_sprite(r.uniform(15, 21), r.uniform(10, 14), r.uniform(0, 3.1), gfp, i)
            f.blit(sp, (int(x - sp.get_width() / 2), int(y - sp.get_height() / 2)), special_flags=pygame.BLEND_ADD)
            if gfp:
                R.glow(f, (x, y), 26, (14, 60, 18), gfp)
        f = photo_finish(f, 1.4)
        s.blit(f, rect.topleft)
        gfx.rrect(s, (rect.right - 70, rect.bottom - 36, 50, 4), (230, 230, 230), None, 0, 1, 0, False)
        draw_text(s, "50 µm", (rect.right - 45, rect.bottom - 52), 11, (230, 230, 230), center=True, bold=True)
        draw_text(s, "Blue: DNA stain (all nuclei). Green: GFP.", (rect.centerx, rect.bottom - 22), 12, (220, 220, 230), center=True)
    return dict(q="Two days later. Blue: all nuclei. Green: cells making GFP. About what fraction was transfected?",
                options=["about %d %%" % e for e in EFF], answer=k, keep_order=True, pic=pic,
                why="Green cells divided by all nuclei. Easy lines such as HEK293 often pass 50 %.")


def _own_eff(rng):
    """The first efficiency picture shows your own dish: the share of cells you transfected, scaled to a dish."""
    from cells_common import ctx_get
    f = ctx_get("transfect_frac")
    if f is None:
        return None
    pct = f * 80          # even a perfect delivery reaches about 80 % in an easy line
    k = min(range(4), key=lambda i: abs(EFF[i] - pct))
    q = _eff_q(rng, k)
    q["q"] = "Your dish, two days later. Blue: all nuclei. Green: cells making GFP. About what fraction was transfected?"
    return q


QUIZ = [
    dict(q="Why do cationic lipids bind DNA?", options=["Their positive charges attract the negative phosphate backbone",
         "They recognise a sequence in the plasmid", "They are covalently linked to DNA by the kit", "They melt the double helix"],
         answer=0, why="Opposite charges attract: the lipid coats the DNA and the complex can fuse with or be taken up by the membrane."),
    dict(q="Why are DNA and lipid mixed in serum-free medium?", options=["Serum proteins interfere with complex formation",
         "Serum degrades plasmids instantly", "Serum makes the lipid toxic", "Serum turns GFP off"], answer=0,
         why="Complexes are formed without serum; once formed they can be added to cells in normal medium."),
    dict(q="Why is GFP expression from a transient transfection lost within one to two weeks?",
         options=["Plasmids do not replicate in most mammalian cells and are diluted at each division",
                  "GFP bleaches in the incubator", "The cells destroy all foreign proteins", "The lipid kills transfected cells"],
         answer=0, why="For permanent expression the DNA must integrate in the genome, selected with a drug such as G418 or puromycin."),
    dict(q="How do most lipoplexes enter the cell?", options=["By endocytosis", "Through ion channels",
         "Through the nuclear pore directly", "By diffusing across the membrane as free DNA"], answer=0,
         why="They are taken up into endosomes; only a small fraction of the DNA escapes and reaches the nucleus."),
]

TECH = dict(
    key="transfect", name="Transfection", full="Transfection by lipofection", wing="Cells & embryos", icon="transfect",
    blurb="Packing plasmid DNA into positively charged lipid particles so that cultured cells take it up and express the gene.",
    facts=[
        "Philip Felgner and colleagues introduced lipofection with the cationic lipid DOTMA in 1987.",
        "Cationic lipids carry positive charges that bind the negatively charged phosphate backbone of DNA.",
        "Most lipoplexes enter cells by endocytosis; only a small part of the DNA escapes the endosome and reaches the nucleus.",
        "Dividing cells transfect better: plasmids reach the nucleus most easily when the nuclear envelope breaks down in mitosis.",
        "GFP comes from the jellyfish Aequorea victoria. Osamu Shimomura, Martin Chalfie and Roger Tsien shared the 2008 Nobel Prize in Chemistry for it.",
        "Transient expression fades because plasmids do not replicate in most mammalian cells; stable lines need integration and drug selection.",
        "Lipid nanoparticles, a related idea, carry the mRNA in the COVID-19 mRNA vaccines.",
    ],
    quiz=QUIZ,
    music=dict(name="Lipoplex Disco", bpm=120, beats=4, root=50, mode="dor", prog=[0, 3, 0, 3, 5, 4, 3, 4],
               lead="synth", comp="stab", drums="disco", swing=0.0,
               motif=[(0, 1), (0, 1), (2, 1), (4, 1), (3, 2), (2, 1), (0, 1), (7, 3), (6, 1), (4, 4)]),
    stages=[
        ("stop", dict(title="Form the complexes", scene=_complex_scene, dur=8.0, ideal=0.5, window=(0.333, 0.667), jitter=0.0,
                      instr="DNA and lipid are coming together. Stop the incubation (click or Space) at about 15 minutes, as the kit asks; the green band shows the time that still works.",
                      readout=lambda v: "%d min" % int(v * 30),
                      early_msg="Too early: the DNA and the lipid had not finished forming complexes.",
                      late_msg="Too late: with many reagents the complexes keep growing into larger particles that transfect less well.",
                      over_msg="30 minutes and counting: large aggregates formed. Follow the kit's incubation time.",
                      good_msg="Complexes formed within the recommended time.")),
        ("transfect_shoot", {}),
        ("cells_quiz", dict(title="How well did it work?", questions=[_eff_q, _eff_q, QUIZ[2], QUIZ[3]], n=3, tint=LAV, lead=_own_eff,
                      instr="Judge the result under the fluorescence microscope.")),
    ],
)
TECHS = [TECH]
