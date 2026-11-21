# -*- coding: utf-8 -*-
"""SDS-PAGE: denature the samples, predict the bands, load a vertical gel, run it."""
import math
import pygame
import audio
import gfx
import render as R
import real
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, LAV, VIOLET, WHITE,
                  GREEN, RED, YELLOW, clamp, mix, lerp, draw_text, draw_wrapped)
from stage import Stage, OrderStage, register, TOP, BOTTOM
from proteins_common import (STEEL, BROMO, COOM, PINK, BUFFER, cached, mmss, note_card, magnifier, heat_shimmer,
                             draw_band, cable, power_pack, heat_block, mini_tank, tank_front)

LADDER = [250, 150, 100, 75, 50, 37, 25, 20, 15, 10]       # kDa, a common prestained protein standard
LADDER_COL = {75: (210, 60, 110), 25: (210, 60, 110)}
PRESTAIN = (52, 70, 160)                                   # the blue bands of a prestained ladder
GEL_CLEAR = (222, 230, 236)
GEL_STAINED = (188, 204, 228)


def rf(kda):
    """Relative mobility in a ~12% gel: roughly linear in log(mass)."""
    return clamp(1.22 - 0.44 * math.log10(kda), 0.04, 0.97)


# ----------------------------------------------------------------- denaturing
def scene_denature(st, s, v):
    gfx.bench(s, PEACH)
    wells, blk = heat_block(s, (40, 352, 340, 110), "95.0", st.t)
    level = 0.55 - 0.3 * clamp((v - 0.7) / 0.3, 0, 1)
    popped = v >= 0.97
    caps = [(232, 232, 228), (232, 232, 228), (60, 120, 200), (60, 120, 200)]
    for i, (x, y) in enumerate(wells):
        gfx.tube(s, x - 12, y - 52, 24, 64, BROMO, level, caps[i], open_=popped and i % 2 == 0)
        if v > 0.6:   # condensation under the lid
            for k in range(int((v - 0.6) * 16)):
                gfx.alpha_circle(s, (236, 244, 255), (x - 7 + (k * 7) % 16, y - 46 + (k * 5) % 7), 1.4, 200)
    # the block's front face hides the lower half of the tubes
    gfx.metal_rect(s, (blk.x, blk.y + 18, blk.w, 24), (170, 176, 186), 5)
    heat_shimmer(s, blk.x + 30, blk.y - 50, blk.w - 60, st.t, (255, 220, 200))
    # inset: what happens to the protein chain (a diagram, so it lives in a UI magnifier)
    c = (650, 296)
    rect = magnifier(s, (wells[3][0], wells[3][1] - 30), c, 156)
    if not hasattr(st, "_fold"):
        r = st.rng
        st._fold, st._lin, st._clump = [], [], []
        ang = 0.0
        for i in range(34):
            ang += r.uniform(1.0, 2.4)
            rad = 16 + 36 * abs(math.sin(i * 0.7))
            st._fold.append((math.cos(ang) * rad, math.sin(ang) * rad))
            st._lin.append((-136 + i * 8.2, 9 * math.sin(i * 1.3)))
            st._clump.append((r.gauss(0, 20), r.gauss(0, 16)))
    u = clamp(v / 0.38, 0, 1)
    u = u * u * (3 - 2 * u)
    a = clamp((v - 0.78) / 0.22, 0, 1)
    pts = []
    for i in range(34):
        fx, fy = st._fold[i]
        lx, ly = st._lin[i]
        cx, cy = st._clump[i]
        x, y = lerp(fx, lx, u), lerp(fy, ly, u)
        x, y = lerp(x, cx, a), lerp(y, cy, a)
        pts.append((c[0] + x, c[1] - 14 + y))
    nsds = int(u * 32 * (1 - a * 0.6))
    for i in range(nsds):
        p = pts[i % 34]
        side = 1 if i % 2 else -1
        q = (p[0] + 5 * side, p[1] + 18 * side)
        gfx.line(s, (150, 140, 120), p, q, 2)
        gfx.circle(s, CORAL, q, 4.5, 1, INK, False)
    chain = mix(VIOLET, RED, a * 0.6)
    pygame.draw.lines(s, R.lighten(chain, -0.45), False, pts, 8)
    pygame.draw.lines(s, chain, False, pts, 6)
    for p in pts:
        R.gd.filled_circle(s, int(p[0]), int(p[1]), 3, chain)
    pygame.draw.lines(s, R.lighten(chain, 0.45), False, [(x - 1, y - 2) for x, y in pts], 2)
    if u > 0.5 and a < 0.5:
        for i in range(2, 34, 6):
            draw_text(s, "-", (pts[i][0] + 6, pts[i][1] - 36), 20, CORAL_D, center=True, bold=True)
    if v < 0.12:
        lab = "Folded protein"
    elif v < 0.38:
        lab = "Unfolding in hot SDS"
    elif v < 0.78:
        lab = "Linear chain coated with SDS (-)"
    else:
        lab = "Drying out, some proteins clumping"
    # two short lines, so the label stays inside the round magnifier
    draw_wrapped(s, lab, (c[0] - 105, rect.bottom - 80), 16, 210, RED if v >= 0.78 else INK, bold=True, center=True)
    gfx.tag(s, 210, 474, "Samples in Laemmli buffer: SDS, reducing agent, glycerol, dye", (250, 246, 236), 12, center=True)
    if st.state != "run":
        lo, hi = st.window
        st.ctx.sds_denat = "short" if (st.state == "stopped" and st.v < lo) else "long" if (st.state == "over" or st.v > hi) else "ok"


# ----------------------------------------------------------------- the gel cassette
def _cassette_static(gel, stack_h, wells, stained):
    """Glass plates with the gel between them, spacers at the sides, wells at the top (cached)."""
    plate = pygame.Rect(gel.x - 18, gel.y - 34, gel.w + 36, gel.h + 44)
    key = ("cass", gel.x, gel.y, gel.w, gel.h, stack_h, len(wells), stained)

    def make():
        sf = pygame.Surface((W, H), pygame.SRCALPHA)
        # back (spacer) plate, taller, then the gel slab, then the short front plate
        sf.blit(real.glass(plate.w, plate.h, (226, 238, 242), 70, 3), plate.topleft)
        for x in (plate.x + 4, plate.right - 16):
            gfx.alpha_rect(sf, (x, plate.y + 6, 12, plate.h - 10), (246, 246, 244), 210, 2)
        body = gfx.texture(gel.w, gel.h, GEL_STAINED if stained else GEL_CLEAR, 40, 3, 61, 2)
        b2 = pygame.Surface(gel.size, pygame.SRCALPHA)
        b2.blit(body, (0, 0))
        g = pygame.Surface(gel.size, pygame.SRCALPHA)
        g.fill((255, 255, 255, 236 if not stained else 248))
        b2.blit(g, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        sf.blit(b2, gel.topleft)
        # stacking gel: a touch whiter; the interface line
        gfx.alpha_rect(sf, (gel.x, gel.y, gel.w, stack_h), WHITE, 45)
        pygame.draw.line(sf, (176, 190, 200, 160), (gel.x, gel.y + stack_h), (gel.right, gel.y + stack_h), 1)
        # wells: clear slots between gel teeth, with darker walls
        for w in wells:
            gfx.alpha_rect(sf, w, (196, 214, 228), 210, 1)
            pygame.draw.line(sf, (150, 166, 180, 220), w.bottomleft, w.bottomright, 2)
            pygame.draw.line(sf, (170, 184, 196, 200), w.topleft, w.bottomleft, 1)
            pygame.draw.line(sf, (170, 184, 196, 200), w.topright, w.bottomright, 1)
        front = pygame.Rect(plate.x, gel.y + 6, plate.w, plate.bottom - gel.y - 6)
        sf.blit(real.glass(front.w, front.h, (230, 240, 244), 30, 3), front.topleft)
        return sf
    return cached(key, make), plate


def scene_run(st, s, v):
    gfx.bench(s, LAV)
    if not hasattr(st, "_lanes"):
        r = st.rng
        pool = [("Myosin", 200), ("b-Gal", 116), ("BSA", 66), ("Tubulin", 50), ("Actin", 42), ("GAPDH", 36),
                ("GFP", 27), ("Myoglobin", 17), ("Lysozyme", 14), ("Histone H4", 11)]
        st._lanes = [r.sample(pool, r.randint(2, 4)) for _ in range(6)]
    running = st.state == "run"
    stained = st.state == "stopped"
    jm, jp = power_pack(s, (736, 196, 196, 150), "200 V", running, st.t)
    tank = pygame.Rect(300, 98, 380, 386)
    gel = pygame.Rect(342, 150, 296, 300)
    stack_h = 46
    lanes = 7
    lw = gel.w / (lanes + 1)
    wells = [pygame.Rect(int(gel.x + lw * (k + 1) - lw * 0.32), gel.y + 2, int(lw * 0.64), 14) for k in range(lanes)]
    mini_tank(s, tank, gel.y - 22, running, st.t)
    layer, plate = _cassette_static(gel, stack_h, wells, stained)
    top = gel.y + 12
    length = gel.h - 14
    stack_frac = (stack_h - 12) / length
    front = top + v * length

    def ypos(kda):
        if v <= stack_frac:
            return front - 2
        return top + stack_frac * length + (v - stack_frac) * length * rf(kda) / 0.97

    s.blit(layer, (0, 0))
    # what happened earlier at this bench: heating time and how well each well was loaded
    fills = getattr(st.ctx, "sds_fill", None)
    bleed = getattr(st.ctx, "sds_bleed", None)
    srcs = getattr(st.ctx, "sds_bleed_src", None)     # which well each spill came from
    pierced = set(getattr(st.ctx, "sds_pierced", []))
    denat = getattr(st.ctx, "sds_denat", "ok")

    def amount(k):
        return clamp(fills[k], 0.1, 1.0) if fills and k < len(fills) else 1.0
    clip = s.get_clip()
    s.set_clip(gel.inflate(-2, -2))
    interface = top + stack_frac * length
    for k in range(lanes):
        cx = wells[k].centerx
        a = amount(k)
        if k == 0:
            for kd in LADDER:
                col = LADDER_COL.get(kd, PRESTAIN)
                if stained:
                    col = mix(col, COOM, 0.4)
                draw_band(s, cx, ypos(kd), lw * 0.62, 4, col, int(235 * a), 0.2, 0.6, kd)
        elif stained:
            main = 0.6 if denat != "ok" else 1.0
            for name, kd in st._lanes[k - 1]:
                draw_band(s, cx, ypos(kd), lw * 0.66, 5 if kd > 30 else 4, COOM, int(245 * a * main), 0.35, 0.9, k * 31 + kd)
                if denat == "short":       # still partly folded: compact forms run too far and smear
                    for j in range(3):
                        draw_band(s, cx, ypos(kd * (0.62 + 0.08 * j)), lw * 0.6, 6, COOM, int(70 * a), 0.3, 1.6, k * 37 + kd + j)
            if denat == "long":             # clumped protein stuck at the top of the resolving gel
                draw_band(s, cx, interface + 4, lw * 0.66, 7, COOM, int(200 * a), 0.2, 1.4, k * 5)
            if k in pierced:                # sample leaked under the gel: a streak down the lane
                for yy in range(int(interface), gel.bottom - 4, 9):
                    draw_band(s, cx + 2, yy, lw * 0.4, 8, COOM, int(55 * a), 0.0, 1.8, yy)
            if bleed and k < len(bleed) and bleed[k] > 0.04:   # sample spilled in from a neighbouring well
                src = srcs[k] if srcs and k < len(srcs) and srcs[k] is not None else None
                if src is None or src == k:
                    other = []
                elif src == 0:
                    other = [("ladder", kd) for kd in LADDER]
                else:
                    other = st._lanes[min(src, 6) - 1]
                for name, kd in other:
                    draw_band(s, cx, ypos(kd), lw * 0.6, 4, COOM, int(min(160, 600 * bleed[k])), 0.3, 1.2, k * 53 + kd)
        if not stained and front < gel.bottom:
            draw_band(s, cx, front, lw * 0.7, 5, BROMO, 170 if running else 120, 0.3, 1.2, k)
    s.set_clip(clip)
    pm, pp = tank_front(s, tank, running, st.t)
    cable(s, jm, (pm[0], pm[1] + 2), (34, 34, 38), 50)
    cable(s, jp, (pp[0], pp[1] + 2), (190, 40, 40), 40)
    # size scale on a UI strip next to the tank
    strip = pygame.Rect(232, gel.y - 10, 58, gel.h + 20)
    gfx.card(s, strip, CARD, INK, 8, 1, False)
    draw_text(s, "kDa", (strip.centerx, strip.y + 4), 12, INK_SOFT, center=True, bold=True)
    if v > stack_frac + 0.1:
        for kd in (250, 100, 50, 25, 15):
            y = ypos(kd)
            if strip.y + 18 < y < strip.bottom - 8:
                draw_text(s, str(kd), (strip.right - 8, y - 7), 12, INK_SOFT, right=True, bold=True)
                pygame.draw.line(s, INK_SOFT, (strip.right - 4, y), (strip.right + 6, y), 1)
    if running:
        txt = "Lane 1 is a prestained ladder. The blue dye front runs ahead of the proteins. Stop when it nears the bottom."
    elif st.state == "over":
        txt = "The dye front ran off the gel, taking the smallest proteins with it."
    else:
        txt = "Stained with Coomassie blue: every protein now shows as a band, sorted by size."
        issues = []
        if denat == "short":
            issues.append("Short heating: ghost bands.")
        elif denat == "long":
            issues.append("Overheated: clumps at the top.")
        if fills and any(f < 0.6 for f in fills[1:7]):
            issues.append("Faint lanes: little sample loaded.")
        if pierced:
            issues.append("Pierced well: a streak.")
        if bleed and any(b > 0.04 for b in bleed[1:7]):
            issues.append("Spill: bands in the next lane.")
        if issues:
            txt = " ".join(issues)
    note_card(s, (712, 352, 228, 134), "Coomassie stain" if stained else "Running at 200 V", txt, SKY if running else SAND, 13)


# ----------------------------------------------------------------- predicting the bands
PROTEINS = [("Myosin heavy chain", 200, PEACH, "Big proteins are held back most by the gel's mesh."),
            ("Beta-galactosidase", 116, SAND, "Beta-galactosidase is a 116 kDa subunit; the tetramer falls apart in SDS."),
            ("Phosphorylase b", 97, (236, 220, 190), "Phosphorylase b, about 97 kDa, is a classic size standard."),
            ("Serum albumin", 66, SKY, "Albumin is a classic size marker at about 66 kDa."),
            ("Tubulin", 50, (210, 230, 210), "Alpha- and beta-tubulin both run at about 50 kDa."),
            ("Actin", 42, LAV, "Actin is a common loading control at 42 kDa."),
            ("GAPDH", 36, (226, 214, 240), "GAPDH, another loading control, runs at about 36 kDa."),
            ("GFP", 27, (190, 236, 190), "GFP runs at about 27 kDa."),
            ("Myoglobin", 17, (246, 206, 196), "Myoglobin is about 17 kDa."),
            ("Lysozyme", 14, (250, 214, 214), "Small proteins slip through the pores and run furthest.")]


@register("sds_predict")
class SdsPredict(OrderStage):
    """Order a random set of proteins from the top of the gel to the bottom (more of them at higher levels)."""
    title = "Predict the bands"

    def setup(self):
        n = self.lv(5, 6, 7)
        pick = sorted(self.rng.sample(PROTEINS, n), key=lambda q: -q[1])
        self.p = dict(self.p, steps=[("%s, %s kDa" % (nm, ("~%d" % kd) if kd >= 200 else kd), col, why) for nm, kd, col, why in pick])
        super().setup()


# ----------------------------------------------------------------- loading the gel
@register("sds_load")
class SdsLoad(Stage):
    title = "Load the gel"
    instr = ("Bring the pipette tip into the glowing well and hold the mouse button to release the sample. "
             "Move slowly: fast moves make your hand shake. Stay inside the well; below it you pierce the gel. "
             "Release the button before moving to the next well.")
    limit = 60

    def setup(self):
        self.n = self.p.get("wells", 8)
        self.gel = pygame.Rect(210, 150, 540, 330)
        gap = self.gel.w / (self.n + 1)
        ww = int(gap * self.p.get("well_frac", 0.5) * self.lv(1.25, 1.0, 0.82))
        self.wells = [pygame.Rect(int(self.gel.x + gap * (i + 1) - ww / 2), self.gel.y, ww, 46) for i in range(self.n)]
        self.fill = [0.0] * self.n          # amount delivered inside each well (0..1)
        self.cur = 0
        self.left_in_tip = 1.0
        self.need_release = False
        self.spilled = 0.0
        self.punctures = 0
        self.punct_cool = 0
        self.cracks = []
        self.base_tremor = self.lv(2.6, 4.0, 5.4)
        self.move_k = self.lv(0.6, 0.9, 1.15)
        self.tremor = self.base_tremor
        self.bleed = [0.0] * self.n           # sample that landed in the wrong well
        self.bleed_src = [None] * self.n      # and the well it was meant for
        self.pierced = set()
        self.ph = [self.rng.uniform(0, 6.28) for _ in range(4)]
        self.tip = (480, 120)
        self.drops = []
        self.blobs = []
        self.hint = "Move slowly. Hold to release, then let go. Lane 1 is the ladder."

    def tip_pos(self, inp):
        target = self.base_tremor + 0.18 * self.cur + min(14, inp.moved * self.move_k)   # tired hands by the last wells
        self.tremor += (target - self.tremor) * 0.08
        t, a = self.t, self.tremor
        dx = a * (math.sin(t * 0.11 + self.ph[0]) + 0.5 * math.sin(t * 0.29 + self.ph[1]))
        dy = a * 0.6 * (math.sin(t * 0.13 + self.ph[2]) + 0.5 * math.sin(t * 0.37 + self.ph[3]))
        return (inp.mouse[0] + dx, inp.mouse[1] + dy)

    def tick(self, inp):
        self.tip = self.tip_pos(inp)
        if self.punct_cool:
            self.punct_cool -= 1
        if not inp.down:
            self.need_release = False
        x, y = self.tip
        well = self.wells[self.cur]
        for d in self.drops:
            d[1] += 2.2
            d[2] -= 1
        self.drops = [d for d in self.drops if d[2] > 0]
        pierced = any(w.left <= x <= w.right and w.bottom + 6 < y < w.bottom + 40 for w in self.wells)
        if pierced and inp.down and not self.punct_cool:
            self.punctures += 1
            self.punct_cool = 60
            for i, w in enumerate(self.wells):
                if w.left <= x <= w.right:
                    self.pierced.add(i)
            self.shake = 14
            self.cracks.append((x, y))
            audio.sfx("bad")
            self.floaters.add(x, y - 30, "Pierced the gel!", RED, 18)
        if inp.down and self.left_in_tip > 0 and not self.need_release:
            amt = min(self.left_in_tip, 1 / 50.0)
            self.left_in_tip -= amt
            inside = well.left + 1 <= x <= well.right - 1 and well.top - 14 <= y <= well.bottom + 2
            if inside:
                self.fill[self.cur] += amt
                if self.t % 6 == 0:
                    self.drops.append([x, y, 12])
            else:
                self.spilled += amt
                for j, w in enumerate(self.wells):
                    if j != self.cur and w.left <= x <= w.right and w.top - 14 <= y <= w.bottom:
                        self.bleed[j] += amt
                        self.bleed_src[j] = self.cur
                if self.t % 4 == 0:
                    self.blobs.append([x + self.rng.uniform(-6, 6), y + self.rng.uniform(-4, 4), 60])
                if self.t % 30 == 0:
                    audio.sfx("splash")
                    self.floaters.add(x, y - 30, "Spilling!", CORAL_D, 16)
            if self.left_in_tip <= 0:
                f = self.fill[self.cur]
                if f > 0.9:
                    audio.sfx("good")
                    self.particles.burst(well.centerx, well.y, 10, cols=(BROMO, SKY, WHITE))
                    self.floaters.add(well.centerx, well.y - 30, "Loaded", GREEN, 18)
                else:
                    audio.sfx("ding")
                    self.floaters.add(well.centerx, well.y - 30, "%d%% in" % (f * 100), CORAL_D, 18)
                self.cur += 1
                self.left_in_tip = 1.0
                self.need_release = True
                if self.cur >= self.n:
                    self.cur = self.n - 1
                    self.left_in_tip = 0
                    self.share()
                    self.finish(self.result(), *self.notes())
        for b in self.blobs:
            b[2] -= 0.3
        self.blobs = [b for b in self.blobs if b[2] > 0]

    def share(self):
        """Pass the loading result on: it decides how the bands look when the gel is stained."""
        self.ctx.sds_fill = list(self.fill)
        self.ctx.sds_bleed = list(self.bleed)
        self.ctx.sds_bleed_src = list(self.bleed_src)
        self.ctx.sds_pierced = sorted(self.pierced)

    def result(self):
        return 100 * sum(self.fill) / self.n - 8 * self.punctures

    def notes(self):
        out = ["%d of %d wells loaded cleanly; %d%% of the sample went into the right wells." %
               (sum(1 for f in self.fill if f > 0.9), self.n, 100 * sum(self.fill) / self.n)]
        if self.spilled > 0.3:
            out.append("Sample outside the well floats into the buffer or a neighbouring lane.")
        if self.punctures:
            out.append("A pierced well bottom lets the sample leak under the gel.")
        return out

    def partial(self):
        self.share()
        return self.result() * 0.9

    def autoplay(self):
        self.fill = [0.97] * self.n
        self.share()
        self.finish(88, "(autoplay)")

    def _static(self):
        def make():
            sf = pygame.Surface((W, H))
            gfx.bench(sf, SKY)
            g = self.gel
            tank = pygame.Rect(g.x - 46, g.y - 26, g.w + 92, 360)
            mini_tank(sf, tank, g.y - 16)
            layer, plate = _cassette_static(g, 56, self.wells, False)
            sf.blit(layer, (0, 0))
            # sample rack: white polypropylene, tubes stand in it
            rack = pygame.Rect(26, 214, 110, 250)
            sh = real.contact_shadow(rack.w + 10, 14, 90)
            sf.blit(sh, (rack.x - 10, rack.bottom - 12))
            gfx.plastic_rect(sf, rack, (238, 238, 234), 8, 0.3)
            for i in range(self.n):
                x = 42 + (i % 2) * 40
                y = 236 + (i // 2) * 58
                gfx.ellipse(sf, (196, 198, 194), (x - 2, y + 30, 30, 10), 0)
            return sf
        return cached(("sdsload2", self.n), make)

    def _front(self):
        def make():
            sf = pygame.Surface((W, H), pygame.SRCALPHA)
            g = self.gel
            tank = pygame.Rect(g.x - 46, g.y - 26, g.w + 92, 360)
            sf.blit(real.glass(tank.w, tank.h, (220, 236, 244), 34, 10), tank.topleft)
            return sf
        return cached(("sdsloadfront", self.n), make)

    def render(self, s):
        s.blit(self._static(), (0, 0))
        for i, w in enumerate(self.wells):
            if self.fill[i] > 0:
                h = int(w.h * min(1, self.fill[i]) * 0.8)
                col = BROMO if i else mix(BROMO, PINK, 0.4)
                gfx.alpha_rect(s, (w.x + 2, w.bottom - h - 1, w.w - 4, h), col, 215, 2)
                gfx.alpha_rect(s, (w.x + 3, w.bottom - h - 1, w.w - 6, 2), R.lighten(col, 0.4), 160, 1)
            if i == self.cur and not self.done:
                pulse = 0.5 + 0.5 * math.sin(self.t * 0.15)
                gfx.rrect(s, w.inflate(8 + 4 * pulse, 8 + 4 * pulse), None, YELLOW, 3, 6)
        for cx, cy in self.cracks:
            for k in range(4):
                a = k * 1.6 + 0.4
                gfx.line(s, (246, 252, 255), (cx, cy), (cx + math.cos(a) * 12, cy + math.sin(a) * 9), 1)
        for b in self.blobs:
            gfx.alpha_circle(s, BROMO, (b[0], b[1]), 7, b[2] * 2)
        for d in self.drops:
            gfx.alpha_circle(s, BROMO, (d[0], d[1]), 3, 230)
        s.blit(self._front(), (0, 0))
        # lane numbers written on the glass plate with a marker
        for i, w in enumerate(self.wells):
            draw_text(s, "L" if i == 0 else str(i), (w.centerx, w.y - 22), 13, (40, 60, 120), center=True, bold=True)
        for i in range(self.n):
            x = 42 + (i % 2) * 40
            y = 236 + (i // 2) * 58 - 20
            gfx.tube(s, x, y, 24, 52, BROMO, 0.2 if i < self.cur or self.done else 0.6,
                     (220, 70, 140) if i == 0 else (236, 236, 232))
            draw_text(s, "L" if i == 0 else str(i), (x + 12, y + 18), 11, (30, 40, 100), center=True, bold=True)
        dx = int(math.sin(self.shake * 1.7) * 5) if self.shake else 0
        gfx.pipette(s, (self.tip[0] + dx, self.tip[1]), BROMO, self.left_in_tip, plunger=1 - self.left_in_tip, scale=0.8)
        panel = pygame.Rect(W - 200, TOP + 6, 184, 52)
        gfx.card(s, panel, CARD, INK, 10, 1, False)
        draw_text(s, "Loaded", (panel.x + 12, panel.y + 6), 13, INK_SOFT, bold=True)
        gfx.bar(s, (panel.x + 12, panel.y + 26, panel.w - 24, 14), sum(self.fill) / self.n, TURQ)
        if self.need_release and not self.done:
            gfx.tag(s, W // 2, TOP + 8, "Release the button, then go to the next well", (252, 236, 200), 14, center=True)


TECH = dict(
    key="sds", name="SDS-PAGE", full="SDS polyacrylamide gel electrophoresis", wing="Proteins", icon="sds",
    blurb="Separates proteins by size. SDS unfolds them and coats them with negative charge, so in an electric field "
          "they move through the gel at a speed set by their length.",
    facts=[
        "Ulrich Laemmli published his gel system in 1970, in a paper on the head proteins of bacteriophage T4. It is one of the most cited papers in biology.",
        "SDS binds about 1.4 g per gram of protein, which gives every protein roughly the same charge per unit length.",
        "The stacking gel has a lower pH (6.8) and larger pores than the resolving gel (pH 8.8). There, slow glycine ions squeeze the proteins into a thin band before they separate.",
        "Bromophenol blue is small and runs ahead of almost every protein, so it marks the dye front.",
        "Glycerol in the loading buffer makes the sample denser than the running buffer, so it sinks into the well.",
        "Reducing agents such as DTT or beta-mercaptoethanol break disulfide bonds, so subunits held together by them run as separate bands.",
        "Unpolymerised acrylamide is a neurotoxin; wear gloves when casting gels. APS supplies free radicals and TEMED speeds up polymerisation.",
    ],
    quiz=[
        dict(q="What does SDS do to proteins in SDS-PAGE?", options=["Unfolds them and gives them a uniform negative charge",
             "Breaks disulfide bonds", "Stains them blue", "Cuts them into peptides"], answer=0,
             why="SDS is a detergent. Disulfide bonds are broken by the reducing agent, not by SDS."),
        dict(q="Why is the stacking gel at pH 6.8?", options=["Glycine is nearly uncharged there, so proteins are squeezed into a thin band",
             "Proteins are most stable at pH 6.8", "It makes the gel set faster", "Bromophenol blue is only blue at pH 6.8"], answer=0,
             why="Slow glycine behind and fast chloride ahead create a moving boundary that stacks the proteins."),
        dict(q="A 50 kDa protein runs at 100 kDa in a non-reducing gel but at 50 kDa when reduced. Most likely it is:",
             options=["A dimer held together by a disulfide bond", "Degraded", "Glycosylated", "Not denatured"], answer=0,
             why="Reducing agents break disulfide bonds and release the two 50 kDa subunits."),
    ],
    music=dict(name="Laemmli March", bpm=112, beats=4, root=50, mode="maj", prog=[0, 3, 4, 0, 5, 1, 4, 4],
               lead="brass", comp="drive", drums="march",
               motif=[(0, 1), (0, 1), (4, 2), (4, 1), (5, 1), (4, 2), (2, 2), (1, 2), (0, 4)]),
    stages=[
        ("stop", dict(title="Denature the samples", scene=scene_denature, dur=9.0, ideal=0.5, window=(0.3, 0.76),
                      readout=lambda v: "%s, 95 deg C" % mmss(v * 600),
                      instr="Samples sit at 95 deg C in Laemmli buffer. Stop at about 5 minutes: long enough to unfold the "
                            "proteins, not so long that the tubes dry out and fragile proteins clump.",
                      early_msg="Too short: some proteins are still folded and will run at the wrong size.",
                      late_msg="Too long: the sample starts to evaporate, and some proteins (membrane proteins especially) can clump.",
                      over_msg="Ten minutes at 95 deg C with the lids popped: the samples dried down, and some proteins, especially membrane proteins, clumped.",
                      good_msg="About 5 minutes at 95 deg C: unfolded and coated with SDS.")),
        ("sds_predict", dict(title="Predict the bands", heading="Gel: top to bottom",
                             instr="Click the proteins in the order their bands appear, from the top of the gel (largest) to the bottom (smallest).",
                             steps=[], limit=45)),
        ("sds_load", dict(wells=8, well_frac=0.42)),
        ("stop", dict(title="Run the gel", scene=scene_run, dur=11.0, ideal=0.9, window=(0.72, 0.985),
                      readout=lambda v: "%s  200 V" % mmss(v * 45 * 60),
                      instr="Proteins run from the black (-) electrode to the red (+). Stop when the blue dye front is near "
                            "the bottom of the gel, before it runs out.",
                      early_msg="Stopped early: the bands are still bunched together near the top.",
                      late_msg="Very close to the edge: the smallest proteins may be lost.",
                      over_msg="The dye front ran off the gel, and the smallest proteins with it.",
                      good_msg="Good separation: the dye front is just above the bottom.")),
    ],
)
TECHS = [TECH]
