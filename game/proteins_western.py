# -*- coding: utf-8 -*-
"""Western blot: transfer sandwich, rolling out bubbles, antibody steps, exposure on the imager."""
import math
import pygame
import audio
import gfx
import render as R
import real
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, TEAL, LAV, VIOLET, WHITE,
                  GREEN, RED, YELLOW, GEL, clamp, mix, lerp, draw_text, draw_wrapped)
from stage import Stage, OrderStage, register, TOP, BOTTOM
from proteins_common import cached, note_card, draw_band

SPONGE = (52, 54, 60)            # black fibre pad
PAPER_W = (246, 245, 240)        # Whatman blotting paper
MEMBRANE = (244, 243, 238)       # wet nitrocellulose


def layer_texture(kind, w, h):
    """Material of one sandwich layer, as a surface."""
    if kind == "sponge":
        def make():
            sf = gfx.texture(w, h, SPONGE, 3, 14, 71, 2).copy()
            rnd = __import__("random").Random(w * 7 + h)
            for _ in range(w * h // 18):
                x, y = rnd.randrange(w), rnd.randrange(h)
                c = rnd.choice(((30, 30, 34), (78, 80, 88), (40, 42, 48)))
                sf.set_at((x, y), c)
            return sf
        return cached(("sponge2", w, h), make)
    if kind == "paper":
        def make():
            sf = gfx.texture(w, h, PAPER_W, 2, 6, 72, 2).copy()
            rnd = __import__("random").Random(w + h * 3)
            for _ in range(w * h // 90):       # paper fibres
                x, y = rnd.randrange(w), rnd.randrange(h)
                a = rnd.uniform(0, 6.28)
                pygame.draw.line(sf, (228, 226, 220), (x, y), (x + math.cos(a) * 4, y + math.sin(a) * 4), 1)
            return sf
        return cached(("paper2", w, h), make)
    if kind == "gel":
        return cached(("gelt2", w, h), lambda: gfx.texture(w, h, (200, 214, 226), 20, 4, 73, 2))
    return cached(("memb2", w, h), lambda: gfx.texture(w, h, MEMBRANE, 5, 4, 74, 2))


def kind_of(label):
    l = label.lower()
    return "sponge" if "sponge" in l else "paper" if "paper" in l else "gel" if l == "gel" else "membrane"


def cassette_half(s, rect, col):
    """One half of a wet-transfer cassette: moulded plastic with a grid of flow holes."""
    rect = pygame.Rect(rect)
    gfx.plastic_rect(s, rect, col, 6, 0.3)
    hole = R.lighten(col, -0.45)
    for gx in range(rect.x + 10, rect.right - 14, 18):
        pygame.draw.rect(s, hole, (gx, rect.y + 3, 10, max(2, rect.h - 6)), border_radius=2)


@register("western_stack")
class WesternStack(OrderStage):
    """The sandwich order stage, drawn with real materials and the two halves of the cassette.
    Each play uses either nitrocellulose or PVDF."""

    def setup(self):
        steps = list(self.p["steps"])
        if self.rng.random() < 0.5:
            i = next(k for k, st in enumerate(steps) if st[0] == "Membrane")
            steps[i] = ("PVDF membrane", (240, 240, 236),
                        "PVDF goes between the gel and the anode. It is hydrophobic, so it was wetted in methanol first.")
        self.p = dict(self.p, steps=steps)
        super().setup()

    def render(self, s):
        cards, self.cards = self.cards, [c for c in self.cards if not c["placed"]]
        tl, bl = self.p.get("top_label", ""), self.p.get("bottom_label", "")
        self.p["top_label"] = ""
        super().render(s)
        self.cards = cards
        self.p["top_label"] = tl
        bot = self.slot_rect(0)
        top = self.slot_rect(len(self.steps) - 1)
        cassette_half(s, (bot.x - 12, bot.bottom + 4, bot.w + 24, 14), (40, 40, 44))
        if self.next == len(self.steps):
            cassette_half(s, (top.x - 12, top.y - 18, top.w + 24, 14), (236, 70, 64))
            draw_text(s, tl, (top.centerx, top.y - 40), 13, INK_SOFT, center=True, bold=True)
        for c in self.cards:
            r = pygame.Rect(c["rect"])
            if not c["placed"] or r.w < 20 or r.h < 8:
                continue
            label = self.steps[c["i"]][0]
            k = kind_of(label)
            th = {"sponge": r.h, "paper": int(r.h * 0.62), "gel": int(r.h * 0.5), "membrane": int(r.h * 0.3)}[k]
            lay = pygame.Rect(r.x, r.bottom - th, r.w, th)
            sh = real.contact_shadow(lay.w, 6, 60)
            s.blit(sh, (lay.x - 3, lay.bottom - 6))
            tex = layer_texture(k, lay.w, lay.h)
            s.blit(tex, lay.topleft)
            if k == "gel":
                gfx.alpha_rect(s, (lay.x, lay.y, lay.w, 2), WHITE, 140)
                for i in range(5):           # stop short of the "Gel" label on the right
                    gfx.alpha_rect(s, (lay.x + 20 + i * 46, lay.centery - 1, 26, 3), (60, 70, 150), 150, 1)
            pygame.draw.line(s, (255, 255, 255), lay.topleft, lay.topright, 1)
            pygame.draw.line(s, R.lighten(tex.get_at((2, 2))[:3], -0.35), lay.bottomleft, lay.bottomright, 1)
            col = (230, 230, 236) if k == "sponge" else INK_SOFT
            draw_text(s, label, (r.right - 8, lay.centery), 12, col, right=True, bold=True, vcenter=True)


# ----------------------------------------------------------------- rolling
@register("western_roll")
class WesternRoll(Stage):
    title = "Roll out the bubbles"
    instr = ("Air bubbles between gel and membrane block the transfer. Hold the mouse button to press the roller "
             "and roll up or down to push every bubble off the edge. Roll steadily: jerking the roller makes the "
             "membrane slide on the gel.")
    limit = 25

    def setup(self):
        self.mem = pygame.Rect(240, 110, 480, 340)
        n = int(round(self.p.get("bubbles", 12) * self.lv(0.67, 1.0, 1.33)))
        self.half = self.lv(96, 82, 68)            # half-width of the roller
        self.slip_v = self.lv(46, 34, 26)          # faster than this (px per frame) and the membrane slides
        self.slips = 0
        self.slip_cool = 0
        self.slip_dx = 0.0
        self.crept = self.level == 0               # a bubble creeps back in once, except for students
        self.bub = []
        for _ in range(n):
            self.bub.append([self.rng.uniform(self.mem.x + 30, self.mem.right - 30),
                             self.rng.uniform(self.mem.y + 50, self.mem.bottom - 50), self.rng.uniform(7, 15)])
        self.total = n
        self.prev = None
        self.roll = (480, 300)
        self.spin = 0.0
        self.down = False
        self.hint = "Hold and roll vertically. Bubbles leave over the top or bottom edge."

    def tick(self, inp):
        x, y = inp.mouse
        px, py = self.prev or (x, y)
        self.prev = (x, y)
        self.roll = (x, y)
        self.down = inp.down
        vy = y - py
        if self.slip_cool:
            self.slip_cool -= 1
        if inp.down:
            self.spin += vy * 0.2
            if abs(vy) > self.slip_v and not self.slip_cool and self.mem.collidepoint(x, y):
                self.slips += 1
                self.slip_cool = 45
                self.slip_dx += self.rng.choice((-5, 5))
                self.shake = 14
                audio.sfx("bad")
                self.floaters.add(x, y - 50, "Too fast: the membrane slid!", RED, 18)
            if 0.3 < abs(vy) <= self.slip_v and abs(x - px) < 24:     # a jerk skids over the bubbles
                lo, hi = min(py, y), max(py, y)
                for b in self.bub:
                    if abs(b[0] - x) < self.half + b[2] * 0.3 and lo - 14 - b[2] <= b[1] <= hi + 14 + b[2]:
                        b[1] = y + math.copysign(15 + b[2], vy)
        if not self.crept and len(self.bub) <= self.total // 2:
            self.crept = True
            self.bub.append([self.rng.uniform(self.mem.x + 40, self.mem.right - 40), self.mem.bottom - 30, 11])
            self.total += 1
            audio.sfx("whoosh")
            self.floaters.add(self.mem.centerx, self.mem.bottom - 60, "Air crept in at the edge", CORAL_D, 16)
        keep = []
        for b in self.bub:
            if b[1] < self.mem.y - 4 or b[1] > self.mem.bottom + 4:
                audio.sfx("pop")
                self.particles.burst(b[0], clamp(b[1], self.mem.y, self.mem.bottom), 8, cols=(WHITE, SKY), speed=3)
                self.floaters.add(b[0], clamp(b[1], self.mem.y, self.mem.bottom) - 20, "pop", TEAL, 15)
            else:
                keep.append(b)
        self.bub = keep
        if not self.bub:
            audio.sfx("good")
            self.share()
            slow = 5 if self.t > 60 * self.limit * 0.72 else 0
            self.finish(100 - slow - 12 * self.slips, "No bubbles left in %d s: the transfer will be even." % (self.t / 60),
                        "The membrane slid %d time%s: expect doubled, blurred bands." % (self.slips, "" if self.slips == 1 else "s")
                        if self.slips else "No slips: the bands will stay sharp.")

    def share(self):
        """Bubbles left under the membrane block transfer there; slips double the bands."""
        m = self.mem
        self.ctx.wb_bubbles = [((b[0] - m.x) / m.w, (b[1] - m.y) / m.h, b[2] / m.w) for b in self.bub]
        self.ctx.wb_slips = self.slips

    def partial(self):
        self.share()
        return max(0, 100 * (self.total - len(self.bub)) / self.total * 0.85 - 12 * self.slips)

    def autoplay(self):
        self.ctx.wb_bubbles = []
        self.ctx.wb_slips = 0
        self.finish(95, "(autoplay)")

    def _static(self):
        def make():
            sf = pygame.Surface((W, H))
            gfx.bench(sf, SKY)
            tray = self.mem.inflate(130, 96)
            sh = real.contact_shadow(tray.w + 20, 22, 110)
            sf.blit(sh, (tray.x - 14, tray.bottom - 16))
            gfx.plastic_rect(sf, tray, (42, 42, 46), 14, 0.25)
            for gx in range(tray.x + 16, tray.right - 16, 22):           # the cassette's grid of flow holes
                for gy in range(tray.y + 14, tray.bottom - 12, 22):
                    pygame.draw.rect(sf, (24, 24, 28), (gx, gy, 12, 12), border_radius=3)
                    pygame.draw.line(sf, (70, 70, 76), (gx + 1, gy + 12), (gx + 11, gy + 12), 1)
            sp = self.mem.inflate(56, 56)
            sf.blit(layer_texture("sponge", sp.w, sp.h), sp.topleft)
            fp = self.mem.inflate(28, 28)
            sh = real.contact_shadow(fp.w, 10, 60)
            sf.blit(sh, (fp.x - 6, fp.bottom - 8))
            sf.blit(layer_texture("paper", fp.w, fp.h), fp.topleft)
            pygame.draw.rect(sf, (212, 210, 204), fp, 1)
            # wet nitrocellulose on the gel: the prestained ladder shows through faintly
            sf.blit(layer_texture("membrane", self.mem.w, self.mem.h), self.mem.topleft)
            gfx.alpha_rect(sf, (self.mem.x, self.mem.y, self.mem.w, self.mem.h), (200, 214, 230), 40)
            lx = self.mem.x + 30
            for j, (yy, col) in enumerate(((40, (90, 100, 170)), (70, (190, 70, 110)), (100, (90, 100, 170)),
                                            (140, (90, 100, 170)), (190, (190, 70, 110)), (250, (90, 100, 170)))):
                gfx.alpha_rect(sf, (lx, self.mem.y + yy, 44, 4), col, 120, 2)
            for i in range(6):
                gfx.alpha_rect(sf, (self.mem.x + 90 + i * 64, self.mem.y + 14, 44, 3), (190, 204, 220), 140, 1)
            pygame.draw.rect(sf, (206, 206, 200), self.mem, 1)
            # a pencil mark in the corner, as everyone does to orient the membrane
            pygame.draw.line(sf, (110, 110, 116), (self.mem.right - 26, self.mem.y + 10), (self.mem.right - 12, self.mem.y + 24), 2)
            return sf
        return cached(("wroll2",), make)

    def render(self, s):
        if self.slip_dx:
            s.blit(self._static(), (0, 0))
            m = self.mem
            s.blit(self._static(), (m.x + int(self.slip_dx), m.y), m)       # the membrane, shifted on the gel
            gfx.alpha_rect(s, (m.x + int(self.slip_dx) - (2 if self.slip_dx > 0 else -m.w), m.y, 2, m.h), (90, 90, 100), 160)
        else:
            s.blit(self._static(), (0, 0))
        for bx, by, br in self.bub:
            # trapped air under a wet membrane: a flattened, lighter patch with a dark meniscus rim
            gfx.alpha_circle(s, (255, 255, 255), (bx, by), br, 110)
            R.aa_ring(s, (bx, by), br, 2, (150, 160, 170))
            gfx.alpha_circle(s, WHITE, (bx - br * 0.35, by - br * 0.4), max(2, br * 0.25), 230)
        x, y = self.roll
        press = 3 if self.down else 0
        # a blot roller: steel frame, clear acrylic cylinder, black grip
        for sx in (-1, 1):
            gfx.line(s, (120, 124, 132), (x + sx * 80, y + press), (x + sx * 12, y + 48), 5)
            gfx.line(s, (226, 228, 232), (x + sx * 80 - 1, y + press - 1), (x + sx * 12 - 1, y + 47), 2)
        gfx.plastic_rect(s, (x - 14, y + 42, 28, 54), (36, 36, 40), 10, 0.4)
        r = pygame.Rect(0, 0, 160, 26)
        r.center = (x, y + press)
        sh = real.contact_shadow(r.w, 10, 80 if self.down else 50)
        s.blit(sh, (r.x - 4, r.bottom - (2 if self.down else -6)))
        m = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=12)
        prof = real.np.linspace(0, 1, r.h, dtype=real.np.float32) if real.np is not None else None
        cyl = real.shaded_mask(pygame.transform.rotate(m, 90), (214, 226, 232), real.cyl_profile(r.h, 0.3, 0.08, 0.5, 0.65), 200)
        s.blit(pygame.transform.rotate(cyl, -90), r.topleft)
        for k in range(5):
            yy = r.y + 3 + (self.spin * 3 + k * 5) % (r.h - 6)
            pygame.draw.line(s, (190, 200, 206), (r.x + 12, yy), (r.right - 12, yy), 1)
        gfx.metal_rect(s, (r.x - 6, r.centery - 5, 8, 10), (200, 202, 208), 2)
        gfx.metal_rect(s, (r.right - 2, r.centery - 5, 8, 10), (200, 202, 208), 2)
        panel = pygame.Rect(W - 196, TOP + 6, 180, 40)
        gfx.card(s, panel, CARD, INK, 10, 1, False)
        draw_text(s, "Bubbles left: %d" % len(self.bub), panel.center, 16, INK, center=True, bold=True, vcenter=True)


# ----------------------------------------------------------------- exposure
def scene_exposure(st, s, v):
    gfx.bench(s, (200, 200, 210))
    if not hasattr(st, "_amt"):
        r = st.rng
        st._amt = [r.choice([0.25, 0.4, 0.55, 0.7, 0.85]) for _ in range(6)]
        st._amt[r.randrange(6)] = 1.0
    # the imager's software on a monitor: inverted view, dark bands on a light membrane
    mon = pygame.Rect(118, 58, 604, 424)
    sh = real.contact_shadow(mon.w, 18, 90)
    s.blit(sh, (mon.x, mon.bottom - 6))
    gfx.plastic_rect(s, mon, (34, 34, 38), 12, 0.2)
    scr = mon.inflate(-20, -20)
    pygame.draw.rect(s, (236, 236, 240), scr)
    bar = pygame.Rect(scr.x, scr.y, scr.w, 24)
    pygame.draw.rect(s, (60, 64, 80), bar)
    draw_text(s, "Image Lab - Chemi Hi Sensitivity - exposure", (bar.x + 10, bar.centery), 12, (226, 230, 240), bold=True, vcenter=True)
    gfx.led(s, (bar.right - 14, bar.centery), (240, 80, 70) if st.state == "run" else (120, 120, 130), st.state == "run", 4)
    mem = pygame.Rect(scr.x + 150, scr.y + 40, scr.w - 170, scr.h - 60)
    bgv = 248 - int(46 * v ** 2)
    pygame.draw.rect(s, (bgv, bgv, bgv + 2), mem)
    noise = gfx.texture(mem.w, mem.h, (8, 8, 8), 4, int(6 + 10 * v), 82, 1)
    s.blit(noise, mem.topleft, special_flags=pygame.BLEND_RGB_SUB)
    lw = mem.w / 7
    peak = 0
    slips = getattr(st.ctx, "wb_slips", 0)
    holes = getattr(st.ctx, "wb_bubbles", [])
    clip = s.get_clip()
    s.set_clip(mem)
    for k in range(6):
        cx = mem.x + lw * (k + 1)
        for row, (y, amt) in enumerate(((mem.y + 90, st._amt[k]), (mem.y + 206, 0.75))):
            inten = amt * v / 0.8
            peak = max(peak, inten)
            g = round(clamp(inten, 0, 1) * 20) / 20.0      # quantised so band sprites are reused
            if g > 0.02:
                # bands grow wider and fuzzier as they approach saturation
                draw_band(s, cx, y, lw * (0.7 + 0.12 * g), 7 + 5 * g, (14, 14, 18), int(250 * g), 0.4, 0.6 + 0.8 * g, k * 7 + row)
                if slips:            # the membrane slid during the transfer: a second, offset ghost band
                    draw_band(s, cx + 4, y + 7, lw * 0.66, 6, (14, 14, 18), int(110 * g), 0.4, 1.4, k * 7 + row + 3)
                if inten >= 1.0:
                    draw_band(s, cx, y, lw * 0.62, 6, (230, 30, 30), 255, 0.4, 0.3, k * 7 + row + 1)
    for u, vv, rr in holes:          # no transfer where air was trapped: blank, sharp-edged spots
        c = (mem.x + u * mem.w, mem.y + vv * mem.h)
        gfx.alpha_circle(s, (bgv + 4, bgv + 4, bgv + 6), c, max(5, rr * mem.w * 1.1), 255)
        R.aa_ring(s, c, max(5, rr * mem.w * 1.1), 1, (bgv - 30, bgv - 30, bgv - 28))
    s.set_clip(clip)
    pygame.draw.rect(s, (150, 150, 156), mem, 1)
    if holes or slips:
        msg = []
        if holes:
            msg.append("White spots: bubbles blocked the transfer.")
        if slips:
            msg.append("Doubled bands: the membrane slid.")
        draw_wrapped(s, " ".join(msg), (scr.x + 12, scr.bottom - 110), 12, 128, (150, 60, 50))
    # annotation panel of the software
    draw_text(s, "Target", (scr.x + 12, mem.y + 74), 13, (40, 44, 60), bold=True)
    draw_text(s, "55 kDa", (scr.x + 12, mem.y + 92), 12, (90, 94, 110))
    draw_text(s, "GAPDH", (scr.x + 12, mem.y + 190), 13, (40, 44, 60), bold=True)
    draw_text(s, "36 kDa (loading)", (scr.x + 12, mem.y + 208), 12, (90, 94, 110))
    gfx.alpha_rect(s, (scr.x + 12, scr.bottom - 34, 14, 14), (230, 30, 30), 255, 2)
    draw_text(s, "saturated", (scr.x + 32, scr.bottom - 34), 12, (90, 94, 110), bold=True)
    # signal meter
    card = pygame.Rect(744, 196, 190, 220)
    gfx.card(s, card, CARD)
    draw_text(s, "Brightest band", (card.centerx, card.y + 14), 15, INK, center=True, bold=True)
    m = pygame.Rect(card.centerx - 24, card.y + 46, 48, 140)
    gfx.rrect(s, m, (236, 236, 240), INK, 2, 8, 0)
    f = clamp(peak, 0, 1.15) / 1.15
    hh = int((m.h - 6) * f)
    if hh > 4:
        gfx.rrect(s, (m.x + 3, m.bottom - 3 - hh, m.w - 6, hh), RED if peak >= 1 else TURQ, None, 0, 5, 0.2)
    y100 = m.bottom - 3 - int((m.h - 6) / 1.15)
    gfx.line(s, RED, (m.x - 10, y100), (m.right + 10, y100), 2)
    draw_text(s, "max", (m.right + 12, y100 - 8), 12, RED, bold=True)


TECH = dict(
    key="western", name="Western blot", full="Western blot (immunoblot)", wing="Proteins", icon="western",
    blurb="Proteins separated by SDS-PAGE are moved onto a membrane and detected with antibodies, to show whether a "
          "particular protein is there and roughly how much.",
    facts=[
        "The name is a play on the Southern blot for DNA, invented by Edwin Southern in 1975. The RNA version became the northern blot.",
        "Transfer of proteins from gels to nitrocellulose was described by Towbin, Staehelin and Gordon in 1979.",
        "PVDF membranes are so hydrophobic that they must be wetted in methanol before use.",
        "Ponceau S is a red stain that washes off. It shows whether the transfer worked before you add antibodies.",
        "In ECL detection, the HRP enzyme oxidises luminol, which gives off light at about 425 nm.",
        "Milk is a cheap blocking agent, but it contains the phosphoprotein casein and biotin, so BSA is used for phospho-specific antibodies and streptavidin detection.",
        "Wet transfer runs in a tank, often overnight in the cold. Semi-dry transfer between plate electrodes takes under an hour.",
    ],
    quiz=[
        dict(q="In the transfer sandwich, where does the membrane go?", options=["Between the gel and the anode (+)",
             "Between the gel and the cathode (-)", "On both sides of the gel", "It does not matter"], answer=0,
             why="SDS-coated proteins are negative and move towards the positive electrode, so they leave the gel into the membrane on that side."),
        dict(q="Why block the membrane before adding the primary antibody?", options=["To stop antibodies sticking to the bare membrane",
             "To fix the proteins", "To remove SDS", "To activate HRP"], answer=0,
             why="Membranes bind any protein. Blocking fills the empty sites so the antibody binds only its target."),
        dict(q="Your strongest bands show red (saturated) pixels on the imager. What should you do?", options=["Take a shorter exposure",
             "Add more ECL", "Use more primary antibody", "Quantify them anyway"], answer=0,
             why="Saturated pixels have hit the camera's maximum, so they no longer reflect the amount of protein."),
    ],
    music=dict(name="Transfer Sandwich Blues", bpm=84, beats=4, root=48, mode="blues", prog=[0, 0, 2, 0, 4, 2, 0, 4],
               lead="organ", comp="walk", drums="shuffle", swing=0.3,
               motif=[(0, 2), (1, 1), (2, 1), (3, 2), (2, 2), (4, 3), (3, 1), (0, 4)]),
    stages=[
        ("western_stack", dict(title="Build the transfer sandwich", style="stack", heading="Transfer cassette",
                               bottom_label="Black side: cathode (-)", top_label="Red side: anode (+)", tint=SKY,
                               instr="Stack the layers from the black (-) side up to the red (+) side. Proteins carry SDS and move towards +.",
                               steps=[("Sponge pad", (170, 170, 182), "The sponges press the stack together evenly."),
                                      ("Filter paper", WHITE, "Wet filter paper carries buffer and current."),
                                      ("Gel", GEL, "The gel faces the cathode side: proteins leave it towards +."),
                                      ("Membrane", (250, 236, 200), "The membrane sits between the gel and the anode, where the proteins land."),
                                      ("Filter paper", (246, 246, 246), "A second wet filter paper on the anode side."),
                                      ("Sponge pad", (160, 160, 172), "Roll out air bubbles first, then add this pad and close the cassette.")],
                               limit=45)),
        ("western_roll", dict(bubbles=12)),
        ("order", dict(title="Antibody steps", heading="Detection",
                       instr="Put the detection steps in order.",
                       steps=[("Block (milk or BSA)", SAND, "Blocking covers the empty membrane so antibodies do not stick everywhere."),
                              ("Primary antibody, 4 deg C overnight", SKY, "The primary antibody binds your protein."),
                              ("Wash off unbound primary", (230, 236, 240), "TBST washes remove antibody that did not bind."),
                              ("HRP-linked secondary antibody", LAV, "The secondary recognises the primary's species and carries the enzyme."),
                              ("Wash off unbound secondary", (230, 236, 240), "Leftover HRP would light up the whole membrane."),
                              ("ECL substrate, then image", YELLOW, "HRP turns the substrate into light where your protein is.")],
                       limit=45)),
        ("stop", dict(title="Expose the blot", scene=scene_exposure, dur=9.0, ideal=0.7, window=(0.45, 0.8), ease=1.0,
                      readout=lambda v: "%3d s" % (v * 120),
                      instr="The imager collects light from the bands. Stop when the bands are clear but before the "
                            "brightest one saturates (turns red).",
                      early_msg="Too short: the weak bands are lost in the background.",
                      late_msg="Saturated: band intensity no longer tracks the amount of protein.",
                      over_msg="Everything saturated: this image cannot be quantified.",
                      good_msg="Strong bands, none saturated: ready to quantify.")),
    ],
)
TECHS = [TECH]
