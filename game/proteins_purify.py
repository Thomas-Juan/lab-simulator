# -*- coding: utf-8 -*-
"""His-tag affinity chromatography: protocol, fraction collection on a live UV trace, seminar."""
import math
import pygame
import audio
import gfx
import render as R
import real
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, TEAL, LAV, VIOLET, WHITE,
                  GREEN, RED, YELLOW, BLUE, clamp, mix, lerp, draw_text, draw_wrapped)
from stage import Stage, register, TOP, BOTTOM
from proteins_common import cached

RESIN = (150, 206, 196)        # Ni-NTA agarose is pale blue-green
TRACE = (110, 190, 255)
IMID = (120, 230, 140)
SCR = (22, 28, 38)


@register("purify_collect")
class PurifyCollect(Stage):
    title = "Collect the fractions"
    instr = ("The UV trace shows protein leaving the column. Hold the mouse button (or Space) to send the flow into your "
             "fraction tubes; release it to send it to waste. When the wash has brought the trace back to the baseline, "
             "press Elute (or E) to switch to 250 mM imidazole, then keep your His-tagged protein, not the rest.")
    end_delay = 170

    def setup(self):
        self.dur = self.p.get("dur", 32.0) * self.lv(1.12, 1.0, 0.85)
        self.xe = None                      # when you switch to elution buffer
        self.xp = None                      # the elution peak follows the switch
        self.auto = False
        self.sh_amp = self.lv(0.05, 0.09, 0.15)      # a host protein that sticks almost as well as yours
        self.sh_sep = self.lv(0.045, 0.034, 0.026)
        self.carry = 0.0                    # wash contaminants still on the column when you switched
        self.elute_btn = gfx.Button((140, 302, 210, 36), "Elute: 250 mM (E)", (214, 236, 214), size=15)
        self.x = 0.0
        self.got_t = 0.0
        self.got_o = 0.0
        self.tot_t = 0.0
        self.tot_o = 0.0
        self.keep = []           # (x0, x1) intervals
        self.on = False
        self.tubes = [[0.0, 0.0] for _ in range(25)]
        self.drip = []
        self.hint = "Hold to collect, release to send to waste."
        self.screen = pygame.Rect(40, TOP + 8, W - 80, 236)
        self.ax = pygame.Rect(self.screen.x + 64, self.screen.y + 36, self.screen.w - 92, self.screen.h - 66)

    def target(self, x):
        if self.xp is None:
            return 0.0
        w = 0.024 if x < self.xp else 0.042
        return 0.78 * math.exp(-((x - self.xp) / w) ** 2)

    def other(self, x):
        ft = 0.92 / (1 + math.exp(-(x - 0.07) / 0.01)) / (1 + math.exp(-(0.31 - x) / 0.018))
        wash = 0.17 * math.exp(-((x - 0.45) / 0.022) ** 2)
        if self.xe is not None and x > self.xe:
            wash = 0.0                       # whatever was still bound comes off with the elution instead
        out = ft + wash
        if self.xp is not None:
            out += self.sh_amp * math.exp(-((x - self.xp + self.sh_sep) / 0.014) ** 2)
            out += 0.3 * self.carry * math.exp(-((x - self.xp + 0.008) / 0.024) ** 2)   # comes off with yours
        return out

    def imid(self, x):
        if x < 0.36:
            return 10
        if self.xe is None or x < self.xe:
            return 20
        return 250

    def switch(self, auto=False):
        self.xe = self.x
        self.xp = self.x + 0.055
        # fraction of the wash peak (centre 0.45) that had not yet left the column
        self.carry = 0.5 * (1 - math.erf((self.x - 0.45) / 0.022))
        self.auto = auto
        audio.sfx("whoosh")
        self.floaters.add(self.P(self.x, 0.6)[0], self.ax.y + 30, "250 mM imidazole", (40, 150, 70), 16)
        if self.carry > 0.15:
            self.floaters.add(self.P(self.x, 0.6)[0], self.ax.y + 52, "Wash not finished!", RED, 16)
            self.shake = 10

    def tick(self, inp):
        self.inp = inp
        self.on = (inp.down and not self.elute_btn.rect.collidepoint(inp.mouse)) or "space" in inp.held
        if self.xe is None:
            self.elute_btn.enabled = self.x >= 0.36
            if self.elute_btn.enabled and (self.elute_btn.hit(inp) or pygame.K_e in inp.keys):
                self.switch()
            elif self.x >= 0.84:
                self.switch(auto=True)
        dx = 1.0 / (60 * self.dur)
        x0 = self.x
        self.x = min(1.0, self.x + dx)
        tt, oo = self.target(self.x) * dx, self.other(self.x) * dx
        self.tot_t += tt
        self.tot_o += oo
        if self.on:
            self.got_t += tt
            self.got_o += oo
            i = min(24, int(self.x * 25))
            self.tubes[i][0] += tt
            self.tubes[i][1] += oo
            if self.keep and abs(self.keep[-1][1] - x0) < 1e-9:
                self.keep[-1][1] = self.x
            else:
                self.keep.append([x0, self.x])
        if self.t % 8 == 0:
            self.drip.append([0.0])
        for d in self.drip:
            d[0] += 0.07
        self.drip = [d for d in self.drip if d[0] < 1]
        if self.x >= 1.0:
            total_target = 0.78 * (0.024 + 0.042) / 2 * math.sqrt(math.pi)
            self.ctx.purify = (self.got_t / total_target, self.got_t / max(1e-9, self.got_t + self.got_o))
            self.finish(self.result(), *self.notes())

    def result(self):
        total_target = 0.78 * (0.024 + 0.042) / 2 * math.sqrt(math.pi)
        T = self.got_t / total_target
        C = self.got_o / total_target
        return 100 * clamp(T / 0.88, 0, 1) - 60 * C      # cutting the tails for purity is good practice

    def notes(self):
        total_target = 0.78 * (0.024 + 0.042) / 2 * math.sqrt(math.pi)
        T = self.got_t / total_target
        purity = self.got_t / max(1e-9, self.got_t + self.got_o)
        out = ["You kept %d%% of your protein at about %d%% purity." % (T * 100, purity * 100)]
        if self.auto:
            out.append("You never switched buffer, so the run switched for you at the end.")
        elif self.carry > 0.15:
            out.append("You switched before the wash was over: weakly bound host proteins came off with yours.")
        if self.got_o > 0.02:
            out.append("The first big peak is the flow-through: host proteins that never bound the nickel.")
        if T < 0.7:
            out.append("Your protein comes off only after the switch to 250 mM imidazole.")
        return out

    def partial(self):
        return self.result()

    def autoplay(self):
        self.ctx.purify = (0.93, 0.95)
        self.finish(90, "(autoplay)")

    # ------------------------------------------------------------ drawing
    def P(self, x, y):
        ax = self.ax
        return (ax.x + ax.w * x, ax.bottom - ax.h * y)

    def _static(self):
        def make():
            sf = pygame.Surface((W, H))
            gfx.bench(sf, (210, 232, 214))
            # the chromatography software on a monitor: white plot, blue UV, green %B, as on an FPLC
            sc = self.screen
            gfx.plastic_rect(sf, sc, (40, 40, 44), 12, 0.2)
            inner = sc.inflate(-16, -16)
            pygame.draw.rect(sf, (250, 250, 252), inner)
            pygame.draw.rect(sf, (226, 230, 238), (inner.x, inner.y, inner.w, 22))
            draw_text(sf, "Run: His-GFP purification   |   Ni-NTA 1 mL   |   1 mL/min", (inner.x + 8, inner.y + 11), 12,
                      (60, 66, 86), bold=True, vcenter=True)
            ax = self.ax
            for i in range(11):
                x = ax.x + ax.w * i / 10
                pygame.draw.line(sf, (232, 234, 240), (x, ax.y), (x, ax.bottom), 1)
                if i < 10:
                    draw_text(sf, "%d" % (i * 3), (x, ax.bottom + 3), 10, (130, 136, 150), center=True)
            for i in range(5):
                y = ax.y + ax.h * i / 4
                pygame.draw.line(sf, (232, 234, 240), (ax.x, y), (ax.right, y), 1)
            pygame.draw.line(sf, (90, 96, 110), ax.bottomleft, ax.bottomright, 1)
            pygame.draw.line(sf, (90, 96, 110), ax.bottomleft, ax.topleft, 1)
            draw_text(sf, "mAU", (inner.x + 8, ax.y - 2), 11, (30, 90, 200), bold=True)
            draw_text(sf, "%B", (inner.x + 8, ax.y + 14), 11, (40, 150, 70), bold=True)
            draw_text(sf, "mL", (ax.right, ax.bottom + 3), 10, (130, 136, 150), right=True, bold=True)
            # lab stand with a clamp holding a glass column of Ni-NTA agarose
            col = pygame.Rect(76, 316, 46, 120)
            base = pygame.Rect(22, 490, 96, 14)
            sh = real.contact_shadow(base.w + 10, 10, 110)
            sf.blit(sh, (base.x - 6, base.bottom - 8))
            gfx.metal_rect(sf, base, (70, 74, 82), 4)
            gfx.metal_rect(sf, (36, 290, 7, 202), (196, 200, 206), 3)
            gfx.metal_rect(sf, (36, 328, 54, 9), (180, 184, 192), 3)
            gfx.metal_rect(sf, (66, 322, 12, 22), (150, 154, 162), 3)
            m = pygame.Surface(col.size, pygame.SRCALPHA)
            pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=6)
            buf = pygame.Rect(col.x + 3, col.y + 10, col.w - 6, 34)
            gfx.alpha_rect(sf, buf, (214, 230, 240), 200, 3)
            bed = pygame.Rect(col.x + 3, col.y + 44, col.w - 6, col.h - 52)
            sf.blit(gfx.texture(bed.w, bed.h, RESIN, 2, 12, 81, 1), bed.topleft)
            pygame.draw.rect(sf, (246, 246, 242), (bed.x, bed.bottom - 6, bed.w, 6))       # frit
            sf.blit(real.shaded_mask(m, (226, 238, 244), real.cyl_profile(col.w, 0.27, 0.07, 0.6, 0.55), 90), col.topleft)
            # printed label on the glass
            pygame.draw.rect(sf, (252, 252, 248), (col.x + 8, bed.y + 10, col.w - 16, 22))
            draw_text(sf, "Ni-NTA", (col.centerx, bed.y + 14), 10, INK, center=True, bold=True)
            gfx.plastic_rect(sf, (col.centerx - 5, col.y - 34, 10, 36), (236, 236, 238), 3, 0.3)
            gfx.plastic_rect(sf, (col.centerx - 7, col.bottom - 2, 14, 22), (236, 236, 238), 3, 0.3)
            # waste bottle: a translucent plastic carboy
            wb = pygame.Rect(150, 436, 76, 62)
            sh = real.contact_shadow(wb.w + 10, 10, 90)
            sf.blit(sh, (wb.x - 6, wb.bottom - 8))
            mw = pygame.Surface(wb.size, pygame.SRCALPHA)
            pygame.draw.rect(mw, (255, 255, 255, 255), mw.get_rect(), border_radius=12)
            sf.blit(real.shaded_mask(mw, (232, 234, 228), real.cyl_profile(wb.w, 0.27, 0.07, 0.4, 0.62), 200), wb.topleft)
            gfx.alpha_rect(sf, (wb.x + 4, wb.y + 28, wb.w - 8, wb.h - 32), (196, 214, 226), 150, 8)
            gfx.plastic_rect(sf, (wb.centerx - 14, wb.y - 12, 28, 14), (60, 64, 74), 3, 0.3)
            pygame.draw.rect(sf, (252, 252, 248), (wb.x + 14, wb.y + 10, wb.w - 28, 16))
            draw_text(sf, "WASTE", (wb.centerx, wb.y + 12), 10, (190, 60, 50), center=True, bold=True)
            # fraction collector: white housing with a tube rack
            rack = pygame.Rect(262, 376, 664, 120)
            sh = real.contact_shadow(rack.w + 20, 18, 110)
            sf.blit(sh, (rack.x - 10, rack.bottom - 12))
            gfx.plastic_rect(sf, rack, (236, 236, 232), 10, 0.25)
            gfx.plastic_rect(sf, (rack.x + 8, rack.bottom - 26, rack.w - 16, 18), (214, 214, 210), 5, 0.2)
            for i in range(25):
                cx = self.tube_x(i)
                gfx.ellipse(sf, (190, 192, 188), (cx - 10, rack.bottom - 30, 20, 7), 0)
            return sf
        return cached(("purify2",), make)

    def render(self, s):
        s.blit(self._static(), (0, 0))
        sc, ax = self.screen, self.ax
        # fractions collected so far, shaded as the software marks them, with tick marks
        for x0, x1 in self.keep:
            a, b = self.P(x0, 0), self.P(x1, 0)
            gfx.alpha_rect(s, (a[0], ax.y, max(1, b[0] - a[0] + 1), ax.h), (60, 180, 90), 40)
            pygame.draw.line(s, (200, 40, 40), (a[0], ax.bottom - 8), (a[0], ax.bottom), 1)
        phases = [("Load lysate", 0.0, 0.34)]
        if self.xe is None:
            phases.append(("Wash 20 mM", 0.36, max(0.6, self.x)))
        else:
            phases += [("Wash 20 mM", 0.36, self.xe), ("Elute 250 mM", self.xe, 1.0)]
        for label, a, b in phases:
            pa, pb = self.P(a, 0), self.P(b, 0)
            draw_text(s, label, ((pa[0] + pb[0]) / 2, ax.y + 2), 12, (90, 96, 116), center=True, bold=True)
            if a > 0:
                pygame.draw.line(s, (200, 204, 214), (pa[0], ax.y), (pa[0], ax.bottom), 1)
        n = max(2, int(self.x * 300))
        pts = [self.P(i / 300.0, self.target(i / 300.0) + self.other(i / 300.0)) for i in range(n)]
        imd = [self.P(i / 300.0, self.imid(i / 300.0) / 300.0) for i in range(n)]
        if len(pts) > 1:
            pygame.draw.lines(s, (60, 170, 80), False, imd, 2)
            pygame.draw.aalines(s, (30, 90, 210), False, pts)
            pygame.draw.lines(s, (30, 90, 210), False, pts, 2)
            gfx.circle(s, (30, 90, 210), pts[-1], 3, 0)
        # flow from the column through the valve
        col = pygame.Rect(76, 316, 46, 120)
        vx, vy = col.centerx, col.bottom + 30
        tgt = (self.tube_x(min(24, int(self.x * 25))), 396) if self.on else (188, 440)
        a = math.atan2(tgt[1] - vy, tgt[0] - vx)
        gfx.line(s, (220, 226, 232), (vx, vy), tgt, 3)
        pygame.draw.aaline(s, (170, 178, 188), (vx, vy + 2), (tgt[0], tgt[1] + 2))
        for d in self.drip:
            px = lerp(vx, tgt[0], d[0])
            py = lerp(vy, tgt[1], d[0]) - 12 * math.sin(d[0] * math.pi)
            gfx.alpha_circle(s, (200, 220, 240), (px, py), 3, 230)
        gfx.circle(s, (226, 228, 232), (vx, vy), 11, 1, (140, 144, 152))
        gfx.line(s, (40, 90, 170), (vx, vy), (vx + 20 * math.cos(a), vy + 20 * math.sin(a)), 4)
        # fraction tubes and the dispensing arm
        cur = min(24, int(self.x * 25))
        for i in range(25):
            x = self.tube_x(i) - 8
            t_, o_ = self.tubes[i]
            amt = t_ + o_
            if amt > 0:
                # His-GFP fractions are visibly green-yellow; flow-through is a faint grey-brown
                c = mix((222, 232, 240), (150, 210, 70) if t_ >= o_ else (190, 176, 150), clamp(amt * 120, 0.25, 1))
                lvl = 0.25 + clamp(amt * 60, 0, 0.5)
            else:
                c, lvl = None, 0
            gfx.tube(s, x, 404, 16, 56, c, lvl, (236, 236, 232))
        ax_x = self.tube_x(cur)
        gfx.metal_rect(s, (262, 370, 664, 10), (190, 194, 200), 4)
        gfx.plastic_rect(s, (ax_x - 12, 362, 24, 28), (60, 64, 76), 5, 0.3)
        gfx.led(s, (ax_x, 372), GREEN if self.on else (200, 70, 60), True, 4)
        lab = "COLLECTING" if self.on else "to waste  (hold to collect)"
        gfx.tag(s, 594, 336, lab, (196, 236, 200) if self.on else (236, 232, 222), 14, center=True)
        if self.xe is None and not self.done:
            if self.elute_btn.enabled and self.level == 0 and self.x > 0.5:
                pulse = 0.5 + 0.5 * math.sin(self.t * 0.2)
                gfx.rrect(s, self.elute_btn.rect.inflate(8 + 4 * pulse, 8 + 4 * pulse), None, YELLOW, 3, 12)
            self.elute_btn.draw(s, getattr(self, "inp", None))
        if self.done:
            self.draw_check(s)

    def draw_check(self, s):
        """After the run: a Coomassie gel of the collected fractions, the check everyone does next."""
        kept = [(i, t_, o_) for i, (t_, o_) in enumerate(self.tubes) if t_ + o_ > 1e-5]
        card = pygame.Rect(70, TOP + 16, 360, 220)
        gfx.card(s, card, CARD, INK, 12)
        draw_text(s, "Fractions on SDS-PAGE (Coomassie)", (card.x + 14, card.y + 10), 14, INK, bold=True)
        gel = pygame.Rect(card.x + 62, card.y + 36, card.w - 80, card.h - 50)
        s.blit(gfx.texture(gel.w, gel.h, (196, 210, 232), 30, 4, 71, 2), gel.topleft)
        pygame.draw.rect(s, (150, 160, 180), gel, 1)
        lanes = kept[:9]
        n = len(lanes) + 1
        lw = gel.w / (n + 0.5)
        ys = {"His-GFP": gel.y + gel.h * 0.48, "host": [gel.y + gel.h * f for f in (0.18, 0.3, 0.56, 0.7, 0.84)]}
        draw_text(s, "M", (gel.x + lw * 0.75, gel.y - 1), 11, INK_SOFT, center=True, bold=True)
        for j, f in enumerate((0.12, 0.25, 0.38, 0.5, 0.64, 0.8)):
            pygame.draw.line(s, (60, 80, 150), (gel.x + lw * 0.45, gel.y + gel.h * f), (gel.x + lw * 1.05, gel.y + gel.h * f), 3)
        peak = max([t_ + o_ for _, t_, o_ in lanes] + [1e-6])
        for k, (i, t_, o_) in enumerate(lanes):
            cx = gel.x + lw * (k + 1.75)
            a_t = clamp(t_ / peak, 0, 1)
            a_o = clamp(o_ / peak, 0, 1)
            if a_t > 0.02:
                pygame.draw.line(s, mix((196, 210, 232), (30, 46, 140), a_t), (cx - lw * 0.32, ys["His-GFP"]), (cx + lw * 0.32, ys["His-GFP"]), 4)
            if a_o > 0.02:
                for y in ys["host"]:
                    pygame.draw.line(s, mix((196, 210, 232), (30, 46, 140), a_o * 0.8), (cx - lw * 0.3, y), (cx + lw * 0.3, y), 2)
        if not lanes:
            draw_text(s, "No fractions collected", gel.center, 14, INK_SOFT, center=True, bold=True, vcenter=True)
        draw_text(s, "His-GFP", (gel.x - 4, ys["His-GFP"] - 7), 10, INK_SOFT, right=True, bold=True)


    def tube_x(self, i):
        return 288 + i * 25.8


TECH = dict(
    key="purify", name="Protein purification", full="His-tag affinity chromatography", wing="Proteins", icon="purify",
    blurb="Pulls one protein out of a cell extract. A tag of six histidines on the protein binds nickel ions on a column; "
          "everything else washes through, then imidazole releases the protein.",
    facts=[
        "The nickel-NTA resin and the histidine tag were developed by Erich Hochuli and colleagues at Roche in the late 1980s.",
        "Imidazole is the ring on histidine's side chain, so at high concentration it competes the His-tag off the nickel.",
        "EDTA strips nickel from the column because it holds metal ions more tightly than NTA does.",
        "Ni-NTA turns brown when strong reducing agents such as DTT reduce the nickel ions.",
        "Most of a protein's absorbance at 280 nm comes from tryptophan and tyrosine side chains.",
        "Cobalt resins usually bind His-tags less tightly than nickel, which often gives purer protein at a lower yield.",
        "A His6 tag adds only about 0.8 kDa, so it is often left on the protein.",
    ],
    quiz=[
        dict(q="Why does high imidazole elute a His-tagged protein?", options=["It competes with histidine for the nickel ions",
             "It denatures the protein", "It changes the pH to 3", "It cuts off the tag"], answer=0,
             why="Imidazole is the same ring that histidine uses to grip the nickel."),
        dict(q="Your lysis buffer contains 5 mM EDTA. What happens on the Ni-NTA column?", options=["EDTA strips the nickel and the protein does not bind",
             "Binding improves", "Nothing", "The protein is cleaved"], answer=0,
             why="EDTA chelates metal ions. Use EDTA-free protease inhibitors with nickel columns."),
        dict(q="Why wash with a low concentration of imidazole (about 20 mM)?", options=["To remove host proteins that bind the nickel weakly",
             "To elute the target", "To regenerate the column", "To reduce disulfide bonds"], answer=0,
             why="Some host proteins have a few histidines and bind weakly; low imidazole removes them while the His6 tag holds."),
        dict(q="Which protein absorbs light at 280 nm most strongly per molecule?", options=["One with many tryptophans",
             "One with many glycines", "One with many prolines", "One with a His-tag"], answer=0,
             why="Tryptophan absorbs strongly at 280 nm, tyrosine less, and most other amino acids hardly at all."),
    ],
    music=dict(name="Column Calypso", bpm=118, beats=4, root=53, mode="mix", prog=[0, 3, 4, 0, 6, 3, 4, 4],
               lead="marimba", comp="stab", drums="latin",
               motif=[(4, 1), (4, 1), (5, 1), (4, 1), (2, 2), (0, 1), (2, 1), (4, 3), (7, 5)]),
    stages=[
        ("order", dict(title="Purification protocol", heading="Ni-NTA protocol", tint=(210, 232, 214), limit=45,
                       steps=[("Equilibrate the column in binding buffer", SKY, "The resin must sit in the same buffer as the sample."),
                              ("Load the cleared lysate", SAND, "His-tagged protein binds the nickel; most host proteins flow through."),
                              ("Wash with 20 mM imidazole", (230, 236, 240), "Low imidazole removes weakly bound host proteins."),
                              ("Elute with 250 mM imidazole", LAV, "High imidazole competes the His-tag off the nickel."),
                              ("Check the fractions on SDS-PAGE", (196, 214, 236), "A gel shows which fractions hold pure protein."),
                              ("Pool pure fractions, dialyse out imidazole", PEACH, "Imidazole would interfere with later experiments, so it is removed.")])),
        ("purify_collect", dict(dur=32.0)),
        ("quiz", dict(title="Seminar on the column", n=3, tint=(210, 232, 214),
                      questions=[
                          dict(q="Your protein is in the flow-through, not in the elution. A likely reason:", options=[
                              "The His-tag is buried inside the folded protein", "Too little imidazole in the elution buffer",
                              "The column was too cold", "The protein is too small"], answer=0,
                               why="A tag hidden in the fold cannot reach the nickel. Purifying in urea, or moving the tag to the other end, can help."),
                          dict(q="Why did the Ni-NTA resin turn brown?", options=["A reducing agent such as DTT reduced the nickel",
                              "Too much protein bound", "The imidazole oxidised", "Bacteria grew on it"], answer=0,
                               why="Use low DTT, or TCEP, which is gentler on nickel."),
                          dict(q="Which peak on the UV trace is the flow-through?", options=["The large first peak while the lysate is loaded",
                              "The peak after the imidazole step", "The small peak during the wash", "There is no flow-through peak"], answer=0,
                               why="Most cell proteins do not bind and pass straight through during loading."),
                          dict(q="What is a GST-tagged protein purified on?", options=["Glutathione resin", "Nickel resin",
                              "Protein A beads", "Streptavidin beads"], answer=0,
                               why="Glutathione S-transferase binds glutathione; free glutathione elutes it.")])),
    ],
)
TECHS = [TECH]
