# -*- coding: utf-8 -*-
"""PCR: find the reagents, make the master mix, program the cycler, load and run the gel."""
import math
import pygame
import audio
import gfx
import real
import render as R
from stage import Stage, register, TOP, BOTTOM
from core import (W, H, INK, INK_SOFT, MUTED, CARD, PAPER, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, TEAL, LAV,
                  VIOLET, NIGHT, WHITE, GREEN, RED, YELLOW, BLUE, GEL, DYE, clamp, mix, draw_text, draw_wrapped)
from dna_common import (Tremor, mobility, fmt_bp, LADDER_100, UV_BAND, cap_sprite, cardboard, frost_layer, soft_blob,
                        draw_tank, buffer_over, electrode_bubbles, well, agarose_slab, uv_gel, uv_band, power_supply,
                        tank_terminals, cable, pipette_tip, ice_bucket, AGAROSE, marker_text)

# real tube-cap colours (polypropylene): red, blue, yellow, green, pink, violet, orange, natural, teal, white
CAPS = [(214, 58, 48), (52, 112, 206), (240, 198, 40), (70, 160, 80), (236, 110, 170), (130, 90, 190), (238, 132, 40),
        (236, 236, 228), (40, 160, 160), (250, 250, 248)]
GENES = ["kdrl", "myl7", "gfp", "actb1", "fli1"]


def pcr_targets(gene):
    return [("10x PCR", "10x PCR buffer (no Mg)"), ("dNTP", "dNTP mix, 10 mM each"), ("MgCl2", "MgCl2, 25 mM"),
            ("%s F" % gene, "Forward primer %s, 10 µM" % gene), ("%s R" % gene, "Reverse primer %s, 10 µM" % gene),
            ("Taq", "Taq DNA polymerase"), ("H2O", "Nuclease-free water")]


TARGETS = pcr_targets("kdrl")          # default list (kept for other modules)
DECOYS = [("10x Cut", "10x restriction buffer"), ("RNase A", "RNase A"), ("Prot K", "Proteinase K"),
          ("T4 lig", "T4 DNA ligase"), ("EcoRI", "EcoRI restriction enzyme"), ("BamHI", "BamHI restriction enzyme"),
          ("ddNTP", "ddNTPs (for Sanger sequencing)"), ("Ladder", "100 bp Plus DNA ladder"), ("Dye 6x", "6x loading dye"),
          ("BSA", "Bovine serum albumin"), ("RT", "Reverse transcriptase"), ("X-gal", "X-gal"), ("IPTG", "IPTG"),
          ("10x T4", "10x T4 ligase buffer"), ("Q5", "Q5 polymerase (for a different protocol)"), ("10x RT", "10x RT buffer")]
CELL = 44


@register("pcr_find")
class FindStage(Stage):
    title = "Raid the -20 deg C freezer"
    instr = "Find the 7 PCR reagents in the freezer box before your fingers freeze. Hover to read a label, click to take it. Wrong tubes cost 3 seconds."
    limit = 45

    def setup(self):
        self.box = pygame.Rect(40, TOP + 40, 9 * CELL, 9 * CELL)
        self.gene = self.rng.choice(GENES)
        try:
            self.ctx.pcr_gene = self.gene        # the gel at the end of the station shows this gene's band
        except Exception:
            pass
        self.targets = pcr_targets(self.gene)
        # the other genes' primers sit in the same box: you have to read which gene a tube is for
        others = [g for g in GENES if g != self.gene]
        decoys = list(DECOYS)
        for g in others:
            decoys += [("%s F" % g, "Forward primer %s, 10 µM" % g), ("%s R" % g, "Reverse primer %s, 10 µM" % g)]
        cells = list(range(81))
        self.rng.shuffle(cells)
        self.grid = {}
        for k, (short, full) in enumerate(self.targets):
            self.grid[cells[k]] = [short, full, CAPS[k % len(CAPS)], True]
        for c in cells[7:self.lv(50, 66, 76)]:
            short, full = self.rng.choice(decoys)
            self.grid[c] = [short, full, self.rng.choice(CAPS), False]
        self.penalty = self.lv(2, 3, 4)
        self.frosty = self.level == 2              # Expert: frost hides the labels until your hand is close
        self.instr = ("Find the 7 reagents for a PCR on the %s gene before your fingers freeze. Hover to read a label, click to take it. "
                      "Other genes' primers are in the box too. Wrong tubes cost %d seconds." % (self.gene, self.penalty))
        if self.frosty:
            self.instr += " The box is frosted over: labels clear only near your hand."
        self.found = []
        self.wrong = 0
        self.wrong_names = []
        self.hover = None
        self.mouse = (0, 0)
        self.mist = [[self.rng.uniform(0, W), self.rng.uniform(TOP, H), self.rng.uniform(20, 60)] for _ in range(14)]
        self.hint = "You need the %s primers. Labels are short: hover over a tube to read it in full." % self.gene

    def cell_at(self, pos):
        if not self.box.collidepoint(pos):
            return None
        return (pos[1] - self.box.y) // CELL * 9 + (pos[0] - self.box.x) // CELL

    def tick(self, inp):
        for m in self.mist:
            m[1] -= 0.3
            m[0] += math.sin(self.t * 0.01 + m[2]) * 0.2
            if m[1] < TOP - 40:
                m[1] = H + 20
        self.mouse = inp.mouse
        c = self.cell_at(inp.mouse)
        self.hover = c if c in self.grid else None
        if inp.click and self.hover is not None:
            short, full, cap, ok = self.grid[self.hover]
            cx = self.box.x + (self.hover % 9) * CELL + CELL // 2
            cy = self.box.y + (self.hover // 9) * CELL + CELL // 2
            if ok:
                del self.grid[self.hover]
                self.found.append(short)
                audio.sfx("good")
                self.particles.burst(cx, cy, 14, cols=(WHITE, SKY, cap))
                self.floaters.add(cx, cy - 20, "got it!", GREEN, 18)
                if len(self.found) == len(self.targets):
                    sc = 75 + 25 * min(1.0, self.left() / (self.limit * 0.5)) - 4 * self.wrong
                    fb = ["All 7 reagents for the %s PCR found with %d s to spare." % (self.gene, self.left())]
                    if self.wrong:
                        fb.append("Wrong tubes: %s (-%d s each)." % (", ".join(self.wrong_names[:4]), self.penalty))
                    else:
                        fb.append("No wrong tubes.")
                    if any(" F" in n or " R" in n for n in self.wrong_names):
                        fb.append("Primers for another gene amplify the wrong target: always check the gene name on the tube.")
                    self.finish(sc, *fb)
            else:
                self.wrong += 1
                self.wrong_names.append(short)
                self.t += 60 * self.penalty
                self.shake = 12
                audio.sfx("bad")
                self.floaters.add(cx, cy - 20, "-%d s: %s" % (self.penalty, short), RED, 16)
            self.hover = None

    def partial(self):
        return 85 * len(self.found) / len(self.targets) - 4 * self.wrong

    def autoplay(self):
        self.finish(88, "(autoplay)")

    def static(self):
        bg = getattr(self, "_bg", None)
        if bg is None:
            bg = self._bg = pygame.Surface((W, H))
            gfx.bench(bg, (150, 200, 235))
            # the open freezer drawer: frosted white enamel walls and a wire shelf
            fr = pygame.Rect(18, TOP + 4, 444, BOTTOM - TOP + 2)
            bg.blit(R.soft_shadow(fr.w, fr.h, 10, (10, 14, 30), 110, 10), (fr.x - 20 + 5, fr.y - 20 + 8))
            bg.blit(real.plastic(fr.w, fr.h, (236, 240, 244), 10, 0.2), fr.topleft)
            inner = fr.inflate(-18, -18)
            bg.blit(gfx.texture(inner.w, inner.h, (214, 226, 236), 26, 9, 3), inner.topleft)
            sh = pygame.Surface(inner.size, pygame.SRCALPHA)
            for k in range(10):          # inner walls darken towards the drawer edges
                pygame.draw.rect(sh, (40, 60, 90, 14), sh.get_rect().inflate(-k * 4, -k * 4), 2, border_radius=6)
            bg.blit(sh, inner.topleft)
            for x in range(inner.x + 12, inner.right, 22):
                pygame.draw.line(bg, (176, 186, 196), (x, inner.y), (x, inner.bottom), 2)
                pygame.draw.line(bg, (248, 250, 252), (x - 1, inner.y), (x - 1, inner.bottom), 1)
            bg.blit(frost_layer(inner.w, inner.h, 2, 0.9), inner.topleft)
            # the 81-place cardboard box with its cardboard grid insert
            b = self.box
            outer = b.inflate(14, 14)
            bg.blit(R.soft_shadow(outer.w, outer.h, 4, (20, 20, 40), 140, 6), (outer.x - 12 + 3, outer.y - 12 + 6))
            bg.blit(cardboard(outer.w, outer.h, 5, (160, 120, 78)), outer.topleft)
            pygame.draw.rect(bg, (120, 86, 52), outer, 1)
            bg.blit(cardboard(b.w, b.h, 6, (150, 114, 74)), b.topleft)
            for i in range(10):
                x, y = b.x + i * CELL, b.y + i * CELL
                pygame.draw.line(bg, (86, 60, 36), (x + 2, b.y), (x + 2, b.bottom), 2)
                pygame.draw.line(bg, (214, 180, 132), (x, b.y), (x, b.bottom), 2)
                pygame.draw.line(bg, (86, 60, 36), (b.x, y + 2), (b.right, y + 2), 2)
                pygame.draw.line(bg, (226, 194, 146), (b.x, y), (b.right, y), 2)
            bg.blit(frost_layer(outer.w, outer.h, 9, 0.45), outer.topleft)
            # a strip of lab tape written on with a marker
            tape = pygame.Rect(b.x + 6, b.y - 33, 250, 22)
            gfx.alpha_rect(bg, tape, (244, 238, 214), 240, 1)
            for k in range(0, tape.h, 3):
                pygame.draw.line(bg, (232, 224, 196), (tape.x, tape.y + k), (tape.x + 3, tape.y + k + 1), 1)
                pygame.draw.line(bg, (232, 224, 196), (tape.right - 1, tape.y + k), (tape.right - 4, tape.y + k + 1), 1)
            t = marker_text("PCR box  -20 °C  Juan lab", 16, (24, 34, 110), -1.0)
            bg.blit(t, (tape.x + 10, tape.centery - t.get_height() // 2))
        return bg

    def render(self, s):
        s.blit(self.static(), (0, 0))
        b = self.box
        mx, my = self.mouse
        for c, (short, full, cap, ok) in self.grid.items():
            cx = b.x + (c % 9) * CELL + CELL // 2
            cy = b.y + (c // 9) * CELL + CELL // 2
            hot = c == self.hover
            label = short
            if self.frosty and not hot and (cx - mx) ** 2 + (cy - my) ** 2 > 85 ** 2:
                label = None                       # frosted over: the writing cannot be read
            sp = cap_sprite(20 if hot else 17, mix(cap, WHITE, 0.2) if hot else cap, label)
            s.blit(sp, (cx - sp.get_width() // 2, cy - sp.get_height() // 2 - (2 if hot else 0)))
            if label is None:
                gfx.alpha_circle(s, (236, 244, 250), (cx, cy), 15, 120)
        for m in self.mist:
            soft_blob(s, (m[0], m[1]), m[2] * 1.6, (255, 255, 255), 0.16)
        # checklist
        gfx.card(s, (480, TOP + 10, 440, 250), CARD)
        draw_text(s, "Shopping list: %s PCR" % self.gene, (500, TOP + 22), 18, INK, bold=True)
        draw_text(s, "%d / 7" % len(self.found), (900, TOP + 24), 16, MUTED, right=True, bold=True)
        for k, (short, full) in enumerate(self.targets):
            y = TOP + 54 + k * 28
            got = short in self.found
            gfx.rrect(s, (500, y, 20, 20), (196, 236, 200) if got else CARD, INK, 2, 5, 0.1)
            if got:
                gfx.line(s, GREEN, (503, y + 10), (509, y + 16), 3)
                gfx.line(s, GREEN, (509, y + 16), (519, y + 3), 3)
            draw_text(s, full, (530, y), 16, MUTED if got else INK)
            if got:
                pygame.draw.line(s, MUTED, (530, y + 11), (530 + gfx.text_surf(gfx.pretty(full), 16, MUTED).get_width(), y + 11), 1)
        # magnifier
        lens = pygame.Rect(480, TOP + 276, 440, BOTTOM - TOP - 290)
        gfx.card(s, lens, (236, 244, 250))
        if self.hover is not None:
            short, full, cap, ok = self.grid[self.hover]
            gfx.circle(s, (250, 252, 255), (560, lens.centery), 62, 2)
            sp = cap_sprite(50, cap, short, size=17)
            s.blit(sp, (560 - sp.get_width() // 2, lens.centery - sp.get_height() // 2))
            pygame.draw.arc(s, WHITE, (506, lens.centery - 54, 108, 108), 2.0, 2.9, 4)
            draw_wrapped(s, full, (640, lens.y + 34), 20, 260, INK, bold=True)
        else:
            draw_wrapped(s, "Hover over a tube to read its label.", (500, lens.centery - 12), 17, 400, MUTED, center=True)

# ------------------------------------------------------------------ master mix
RECIPE = [("10x PCR buffer, Mg-free", 2.5), ("MgCl2, 25 mM", 1.5), ("dNTPs, 10 mM", 0.5), ("Forward primer, 10 µM", 1.0),
          ("Reverse primer, 10 µM", 1.0), ("Taq polymerase", 0.25), ("Water", 17.25)]
PER_TUBE = 24.0
LOSS = 1.02        # each dispense takes 2 % more than it delivers (pipetting loss)
MIXCOL = (236, 186, 120)


@register("pcr_mix")
class MixStage(Stage):
    title = "Make the master mix"
    instr = ("Type the total volume of each reagent for the whole master mix, then dispense it: 24 uL into every PCR tube. "
             "Pipettes are never perfect, so plan for it.")
    limit = 120

    def setup(self):
        self.samples = self.rng.randint(6, self.lv(10, 10, 9))
        self.controls = self.lv([], ["NTC"], ["+", "NTC"])
        self.n = self.samples + len(self.controls)        # tubes in the strip
        self.loss = self.lv(1.02, 1.02, 1.03)             # each dispense takes 2-3 % more than it delivers
        self.tol = self.lv(0.08, 0.05, 0.03)
        self.names = [str(i + 1) for i in range(self.samples)] + self.controls
        self.entries = [""] * len(RECIPE)
        self.focus = 0
        self.phase = "table"
        self.go = gfx.Button((660, BOTTOM - 70, 260, 46), "Make the mix", SAND)
        self.tubes = [None] * self.n      # None = not filled yet, else fraction filled
        self.left_ul = 0.0
        self.total = 0.0
        self.bad_rows = []
        self.mouse = (0, 0)
        if self.level == 0:
            self.instr += " Tip: make the mix for one reaction more than you need."
        elif self.level == 2:
            self.instr += " Your strip also needs a positive control and a no-template control."
        else:
            self.instr += " Your strip also needs a no-template control (NTC)."

    def row_rect(self, k):
        return pygame.Rect(410, TOP + 92 + k * 40, 150, 32)

    def tube_pos(self, i):
        per = 6
        return 330 + (i % per) * 92, TOP + 120 + (i // per) * 150

    def start_dispense(self):
        vals = []
        for e in self.entries:
            try:
                vals.append(float(e))
            except ValueError:
                vals.append(0.0)
        self.total = sum(vals)
        self.left_ul = self.total
        ks = [v / per for v, (_, per) in zip(vals, RECIPE)]
        kmed = sorted(ks)[len(ks) // 2]
        self.k = kmed
        self.bad_rows = [i for i, k in enumerate(ks) if kmed <= 0 or abs(k / kmed - 1) > self.tol]
        self.phase = "dispense"
        audio.sfx("pour")
        self.hint = "Click each PCR tube to give it 24 uL of master mix."

    def tick(self, inp):
        self.mouse = inp.mouse
        if self.phase == "table":
            for k in range(len(RECIPE)):
                if inp.click and self.row_rect(k).collidepoint(inp.mouse):
                    self.focus = k
                    audio.sfx("blip")
            e = self.entries[self.focus]
            for ch in inp.text:
                if ch == ",":
                    ch = "."
                if (ch.isdigit() or (ch == "." and "." not in e)) and len(e) < 7:
                    e += ch
            if pygame.K_BACKSPACE in inp.keys:
                e = e[:-1]
            self.entries[self.focus] = e
            if pygame.K_TAB in inp.keys or pygame.K_RETURN in inp.keys or pygame.K_KP_ENTER in inp.keys or pygame.K_DOWN in inp.keys:
                self.focus = (self.focus + 1) % len(RECIPE)
            if pygame.K_UP in inp.keys:
                self.focus = (self.focus - 1) % len(RECIPE)
            self.go.enabled = all(self.entries)
            if self.go.enabled and self.go.hit(inp):
                self.start_dispense()
        elif self.phase == "dispense" and inp.click:
            for i in range(self.n):
                x, y = self.tube_pos(i)
                if self.tubes[i] is None and pygame.Rect(x - 6, y - 10, 40, 80).collidepoint(inp.mouse):
                    self.fill_tube(i)
                    break

    def fill_tube(self, i):
        x, y = self.tube_pos(i)
        need = PER_TUBE * self.loss
        got = min(1.0, self.left_ul / need) if self.left_ul > 0 else 0.0
        self.left_ul = max(0.0, self.left_ul - need)
        self.tubes[i] = got
        if got >= 0.999:
            audio.sfx("click")
            self.floaters.add(x + 14, y - 20, "24 uL", GREEN, 16)
        elif got > 0:
            audio.sfx("bad")
            self.shake = 16
            self.floaters.add(x + 14, y - 20, "Ran out!", RED, 22)
        else:
            audio.sfx("bad")
            self.shake = 10
            self.floaters.add(x + 14, y - 20, "Empty!", RED, 22)
        if all(t is not None for t in self.tubes):
            self.score_it()

    def score_it(self):
        sc = 100
        fb = []
        short = [i for i, t in enumerate(self.tubes) if t < 0.999]
        extra = (self.k / self.n - 1) * 100 if self.n else 0
        fb.append("You needed %d tubes and made %.1f reactions' worth (%+.0f %%)." % (self.n, self.k, extra))
        if self.bad_rows:
            sc -= min(50, 12 * len(self.bad_rows))
            fb.append("Ratio off for: %s. Every reagent must be scaled by the same factor." % ", ".join(RECIPE[i][0] for i in self.bad_rows[:3]))
        if short:
            sc -= 35 + 5 * (len(short) - 1)
            names = ", ".join(self.names[i] for i in short)
            if self.controls and self.k < self.samples + 0.5:
                fb.append("The mix ran out at tube%s %s: you planned for the samples but forgot the controls." % ("" if len(short) == 1 else "s", names))
            else:
                fb.append("The mix ran out at tube%s %s. Always make 1 extra reaction (or 10 %% more): pipetting loses a little every time." % ("" if len(short) == 1 else "s", names))
            if "NTC" in [self.names[i] for i in short]:
                fb.append("The NTC was short of mix: a control that is not set up like the samples cannot tell you anything.")
        elif self.k > self.n * 1.5:
            sc -= 10
            fb.append("Enough mix, but far more than %d tubes need: that wastes Taq." % self.n)
        try:
            self.ctx.pcr_fill = dict(zip(self.names, [t if t is not None else 0.0 for t in self.tubes]))
            self.ctx.pcr_mix_eff = 0.5 if self.bad_rows else 1.0
            self.ctx.pcr_samples = self.samples
            self.ctx.pcr_controls = list(self.controls)
        except Exception:
            pass
        self.finish(sc, *fb)

    def partial(self):
        return 20 if self.phase == "dispense" else 0

    def autoplay(self):
        self.entries = ["%g" % (per * (self.n + 1)) for _, per in RECIPE]
        self.start_dispense()
        for i in range(self.n):
            need = PER_TUBE * self.loss
            self.tubes[i] = min(1.0, self.left_ul / need)
            self.left_ul = max(0.0, self.left_ul - need)
        self.score_it()

    def render(self, s):
        gfx.bench(s, SAND)
        if self.phase == "table":
            gfx.card(s, (30, TOP + 12, 560, BOTTOM - TOP - 24), CARD)
            draw_text(s, "Master mix recipe (per 25 uL reaction)", (50, TOP + 24), 20, INK, bold=True)
            draw_text(s, "Reagent", (50, TOP + 62), 14, MUTED, bold=True)
            draw_text(s, "per tube (uL)", (250, TOP + 62), 14, MUTED, bold=True)
            draw_text(s, "total in mix (uL)", (410, TOP + 62), 14, MUTED, bold=True)
            for k, (name, per) in enumerate(RECIPE):
                y = TOP + 92 + k * 40
                if k % 2 == 0:
                    gfx.alpha_rect(s, (42, y - 2, 536, 36), SAND, 40, 6)
                gfx.rrect(s, (50, y + 9, 12, 12), CAPS[k % len(CAPS)], INK, 1, 3, 0.2)
                draw_text(s, name, (70, y + 6), 16, INK)
                draw_text(s, "%g" % per, (300, y + 6), 16, INK, bold=True, center=True)
                r = self.row_rect(k)
                foc = k == self.focus
                gfx.screen_rect(s, r, (232, 240, 228) if not foc else (255, 246, 214))
                if foc:
                    gfx.rrect(s, r.inflate(4, 4), None, CORAL, 2, 8)
                cur = "_" if foc and (self.t // 30) % 2 == 0 else ""
                draw_text(s, self.entries[k] + cur, (r.right - 10, r.y + 5), 18, INK, right=True, bold=True, mono=True)
            y = TOP + 92 + len(RECIPE) * 40
            gfx.line(s, INK, (50, y), (570, y), 2)
            draw_text(s, "Total", (50, y + 8), 16, INK, bold=True)
            draw_text(s, "24", (300, y + 8), 16, INK, bold=True, center=True)
            gfx.card(s, (620, TOP + 12, 320, 272), (250, 248, 240))
            draw_text(s, "%d" % self.samples, (780, TOP + 22), 60, CORAL, center=True, bold=True)
            draw_text(s, "samples to set up", (780, TOP + 98), 16, INK, center=True, bold=True)
            ctl = {"NTC": "+ a no-template control (NTC)", "+": "+ a positive control"}
            yy = TOP + 124
            for c in self.controls:
                draw_text(s, ctl[c], (780, yy), 15, CORAL_D, center=True, bold=True)
                yy += 22
            draw_wrapped(s, "Each tube gets 24 uL of mix; the 1 uL of template goes in afterwards.", (640, yy + 8), 14, 280, INK_SOFT)
            draw_wrapped(s, "Click a box and type. Tab or Enter for the next one.", (640, TOP + 238), 13, 280, MUTED)
            for k in range(len(RECIPE)):
                gfx.tube(s, 664 + k * 34, TOP + 306, 18, 46, (236, 236, 240), 0.5, CAPS[k % len(CAPS)])
            ice_bucket(s, pygame.Rect(650, TOP + 338, 270, 40))
            self.go.draw(s)
        else:
            dx = int(math.sin(self.shake * 1.7) * 5) if self.shake else 0
            gfx.card(s, (30, TOP + 12, 250, BOTTOM - TOP - 24), CARD)
            draw_text(s, "Master mix", (155, TOP + 24), 18, INK, center=True, bold=True)
            frac = self.left_ul / max(1.0, self.total)
            gfx.tube(s, 105 + dx, TOP + 64, 100, 270, MIXCOL, frac * 0.97, TURQ)
            lab = marker_text("MM x%g" % round(self.k, 1), 22, (24, 34, 110), 4.0)
            s.blit(lab, (155 + dx - lab.get_width() // 2, TOP + 146))
            box = pygame.Rect(60, TOP + 352, 190, 34)
            gfx.screen_rect(s, box, (36, 44, 40))
            draw_text(s, "%.1f uL left" % self.left_ul, box.center, 17, (140, 255, 170) if self.left_ul > 0 else (255, 120, 110),
                      center=True, bold=True, mono=True, vcenter=True)
            draw_text(s, "%d tubes x 24 uL = %d uL" % (self.n, self.n * 24), (155, TOP + 400), 13, MUTED, center=True)
            gfx.card(s, (300, TOP + 12, 640, BOTTOM - TOP - 24), (250, 248, 240))
            draw_text(s, "PCR strip in the cooling block", (620, TOP + 24), 18, INK, center=True, bold=True)
            rows = (self.n + 5) // 6
            for row in range(rows):
                for i in range(row * 6, min(self.n, row * 6 + 6)):
                    x, y = self.tube_pos(i)
                    f = self.tubes[i]
                    lv = 0 if f is None else 0.55 * f
                    gfx.tube(s, x, y, 28, 62, MIXCOL, lv, (236, 236, 242) if f is None else (TURQ if f >= 0.999 else RED))
                y = self.tube_pos(row * 6)[1]
                blk = pygame.Rect(318, y + 48, 568, 46)
                gfx.metal_rect(s, blk, (196, 202, 212), 8)
                for i in range(row * 6, min(self.n, row * 6 + 6)):
                    x, _ = self.tube_pos(i)
                    nm = self.names[i]
                    draw_text(s, nm, (x + 14, blk.y + 10), 14, CORAL_D if nm in ("NTC", "+") else INK, center=True, bold=True)
                    f = self.tubes[i]
                    gfx.led(s, (x + 14, blk.bottom - 9), GREEN if f is not None and f >= 0.999 else RED, f is not None, 3)
            if self.mouse[0] > 300:
                gfx.pipette(s, self.mouse, MIXCOL, 0.7 if self.left_ul > 0 else 0, scale=0.8)

# ------------------------------------------------------------------ thermocycler
def sci(x):
    if x < 1e4:
        return "{:,}".format(int(x))
    e = int(math.floor(math.log10(x)))
    sup = str(e).translate(str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻"))
    return "%.1f × 10%s" % (x / 10 ** e, sup)


@register("pcr_cycler")
class CyclerStage(Stage):
    title = "Program the thermocycler"
    instr = "Set the temperatures, the extension time and the number of cycles for this primer pair and product, then press Run."
    limit = 90

    FIELDS = [("Denaturation", "deg C", 90, 1, 80, 100), ("Annealing", "deg C", 50, 1, 40, 75),
              ("Extension", "deg C", 65, 1, 55, 80), ("Extension time", "s", 15, 15, 15, 240), ("Cycles", "", 20, 5, 5, 50)]

    POLY = {
        # name: (denaturation ideal, full-score range, partial range, annealing offset from Tm, seconds per kb, description)
        "Taq": (95, (94, 98), (92, 99), -5, 60, "Taq (copies about 1 kb per minute)"),
        "Q5": (98, (97, 99), (95, 100), 3, 30, "Q5 high-fidelity (30 s per kb, anneal at Tm + 3)"),
    }

    def setup(self):
        self.gene = getattr(self.ctx, "pcr_gene", "kdrl")
        self.tm = self.rng.choice([56, 58, 60, 62, 64])
        self.size = self.rng.choice([500, 700, 1000, 1500, 2000])
        self.poly = "Q5" if (self.level == 2 and self.rng.random() < 0.5) else "Taq"
        self.anneal_tol = self.lv((4, 7), (3, 6), (2, 4))
        self.vals = [f[2] for f in self.FIELDS]
        if self.level == 0:
            self.instr += " Grey hints under each setting show the usual range."
        elif self.level == 2:
            self.instr += " Check which polymerase you have: they need different programs."
        self.btns = []
        for k in range(len(self.FIELDS)):
            y = TOP + 186 + k * 43
            self.btns.append((gfx.Button((300, y, 40, 36), "-", CARD, size=22), gfx.Button((440, y, 40, 36), "+", CARD, size=22)))
        self.run_btn = gfx.Button((300, BOTTOM - 54, 180, 38), "Run", SAND)
        self.running = False
        self.prog = 0.0
        self.eff = 1.0

    def evaluate(self):
        d, a, e, et, cy = self.vals
        dn, full_d, part_d, off, spk, _ = self.POLY[self.poly]
        self.extra = []
        pts, fb, eff = 0, [], 1.0
        if full_d[0] <= d <= full_d[1]:
            pts += 20
        elif part_d[0] <= d <= part_d[1]:
            pts += 10
            eff *= 0.8
            fb.append("For %s, denature at %d-%d deg C." % (self.poly, full_d[0], full_d[1]))
        elif d < part_d[0]:
            eff *= 0.2
            fb.append("At %d deg C the two strands do not separate properly: aim for %d." % (d, dn))
        else:
            eff *= 0.6
            fb.append("%d deg C wears out the polymerase quickly: %d is enough." % (d, dn))
        tgt = self.tm + off
        tol_full, tol_part = self.anneal_tol
        if abs(a - tgt) <= tol_full:
            pts += 20
        elif abs(a - tgt) <= tol_part:
            pts += 10
            eff *= 0.7
            if self.poly == "Taq":
                fb.append("With Taq, anneal about 5 deg C below the primer Tm, here near %d deg C." % tgt)
            else:
                fb.append("Q5's maker recommends annealing at the primer Tm + 3, here %d deg C." % tgt)
        else:
            eff *= 0.25
            fb.append("Annealing at %d deg C: too low gives extra bands from mismatched binding, too high and the primers do not bind. Aim near %d." % (a, tgt))
            if a < tgt:
                self.extra = [int(self.size * 0.55), int(self.size * 1.6)]
        if 70 <= e <= 74:
            pts += 20
        elif 68 <= e <= 76:
            pts += 10
            eff *= 0.8
            fb.append("%s works fastest at about 72 deg C." % self.poly)
        else:
            eff *= 0.4
            fb.append("Extension at %d deg C is far from the %s optimum of 72." % (e, self.poly))
        need = self.size / 1000.0 * spk
        if need <= et <= need * 2 + 30:
            pts += 20
        elif et >= need * 0.6:
            pts += 10
            eff *= 0.7
            fb.append("%s needs about %d s per kb: %s needs about %d s." % (self.poly, spk, fmt_bp(self.size), need))
        else:
            eff *= 0.3
            fb.append("%d s is too short for %s: the copies stay unfinished. Allow %d s per kb." % (et, fmt_bp(self.size), spk))
        if 25 <= cy <= 35:
            pts += 20
        elif 20 <= cy <= 40:
            pts += 12
            fb.append("25-35 cycles is usual: fewer gives little product, more only adds background once the reaction plateaus.")
        else:
            pts += 5
            fb.append("%d cycles is outside the useful range of 25-35." % cy)
        if not fb:
            fb.append("A textbook %s program: %d / %d / 72 deg C, %d s extension." % (self.poly, d, a, et))
        self.eff = eff
        return pts, fb

    def tick(self, inp):
        if not self.running:
            for k, (minus, plus) in enumerate(self.btns):
                _, _, _, step, lo, hi = self.FIELDS[k]
                row = pygame.Rect(40, minus.rect.y, 450, 36)
                delta = 0
                if minus.hit(inp):
                    delta = -1
                if plus.hit(inp):
                    delta = 1
                if inp.wheel and row.collidepoint(inp.mouse):
                    delta = 1 if inp.wheel > 0 else -1
                if delta:
                    self.vals[k] = clamp(self.vals[k] + delta * step, lo, hi)
                    audio.sfx("blip")
            if self.run_btn.hit(inp):
                self.running = True
                self.points, self.fb = self.evaluate()
                self.ctx.pcr_size = self.size
                self.ctx.pcr_eff = self.eff
                self.ctx.pcr_extra = getattr(self, "extra", [])
                audio.sfx("beep")
        else:
            self.prog = min(1.0, self.prog + 1 / 400.0)
            if self.prog >= 1.0:
                self.finish(self.points, *self.fb[:3])

    def partial(self):
        return self.evaluate()[0] * 0.5

    def autoplay(self):
        dn, _, _, off, spk, _ = self.POLY[self.poly]
        self.vals = [dn, self.tm + off, 72, int(math.ceil(self.size / 1000.0 * spk / 15.0) * 15), 30]
        self.points, self.fb = self.evaluate()
        self.finish(self.points, *self.fb)

    def hint_for(self, k):
        dn, full_d, _, off, spk, _ = self.POLY[self.poly]
        return ["usually %d-%d" % full_d, "about Tm %+d" % off, "usually 72", "about %d s per kb" % spk, "usually 25-35"][k]

    def machine(self):
        m = pygame.Rect(520, TOP + 12, 420, BOTTOM - TOP - 24)
        bg = getattr(self, "_mach", None)
        if bg is None:
            bg = self._mach = pygame.Surface((m.w + 30, m.h + 30), pygame.SRCALPHA)
            o = pygame.Rect(6, 6, m.w, m.h)
            # a benchtop thermal cycler: pale moulded housing, charcoal heated lid with its
            # pressure knob, a touchscreen and ventilation slots at the base
            bg.blit(R.soft_shadow(o.w, o.h, 18, (10, 10, 24), 120, 10), (o.x - 20 + 5, o.y - 20 + 10))
            bg.blit(real.plastic(o.w, o.h, (226, 226, 222), 18, 0.35), o.topleft)
            lid = pygame.Rect(o.x + 10, o.y + 8, o.w - 20, 90)
            bg.blit(real.plastic(lid.w, lid.h, (66, 70, 78), 14, 0.3), lid.topleft)
            for k in range(7):
                yy = lid.y + 40 + k * 6
                pygame.draw.line(bg, (40, 42, 48), (lid.x + 20, yy), (lid.right - 130, yy), 2)
                pygame.draw.line(bg, (96, 100, 110), (lid.x + 20, yy + 2), (lid.right - 130, yy + 2), 1)
            draw_text(bg, "Juan Lab Cycler", (lid.x + 21, lid.y + 13), 14, (36, 38, 44), bold=True)
            draw_text(bg, "Juan Lab Cycler", (lid.x + 20, lid.y + 12), 14, (188, 192, 200), bold=True)
            kc = (lid.right - 66, lid.y + 54)
            knob = pygame.Surface((70, 70), pygame.SRCALPHA)
            R.aa_circle(knob, (88, 92, 102), (35, 35), 30, 0, None, True)
            for k in range(24):
                a = k * math.tau / 24
                pygame.draw.line(knob, (60, 62, 70), (35 + math.cos(a) * 24, 35 + math.sin(a) * 24), (35 + math.cos(a) * 30, 35 + math.sin(a) * 30), 2)
            R.aa_circle(knob, (120, 124, 134), (35, 35), 16, 0, None, True)
            bg.blit(R.soft_shadow(56, 56, 28, (0, 0, 0), 120, 5), (kc[0] - 28 - 10 + 3, kc[1] - 28 - 10 + 4))
            bg.blit(knob, (kc[0] - 35, kc[1] - 35))
            pygame.draw.line(bg, (170, 170, 166), (o.x + 14, lid.bottom + 6), (o.right - 14, lid.bottom + 6), 1)
            for k in range(8):
                sx = o.x + 200 + k * 18
                bg.blit(R.rrect_surf(8, 22, (52, 54, 60), None, 0, 4, 0, False), (sx, o.bottom - 36))
            pw = (o.right - 34, o.bottom - 26)
            R.aa_circle(bg, (200, 202, 204), pw, 11, 0, None, True)
            pygame.draw.arc(bg, (70, 74, 84), (pw[0] - 6, pw[1] - 6, 12, 12), 2.2, 7.2, 2)
            pygame.draw.line(bg, (70, 74, 84), (pw[0], pw[1] - 8), (pw[0], pw[1] - 2), 2)
        return bg, m

    def render(self, s):
        gfx.bench(s, SKY)
        gfx.card(s, (30, TOP + 12, 470, 150), CARD)
        draw_text(s, "Your reaction", (50, TOP + 24), 18, INK, bold=True)
        draw_text(s, "Primers: %s F and R, Tm %d deg C" % (self.gene, self.tm), (50, TOP + 58), 16, INK)
        draw_text(s, "Product length: %s" % fmt_bp(self.size), (50, TOP + 84), 16, INK)
        draw_text(s, "Polymerase: " + self.POLY[self.poly][5], (50, TOP + 110), 15 if self.poly == "Q5" else 16,
                  CORAL_D if self.poly == "Q5" else INK, bold=self.poly == "Q5")
        gfx.card(s, (30, TOP + 176, 470, BOTTOM - TOP - 188), (250, 248, 240))
        for k, (name, unit, _, _, _, _) in enumerate(self.FIELDS):
            minus, plus = self.btns[k]
            draw_text(s, name, (50, minus.rect.y + (2 if self.level == 0 else 8)), 17, INK, bold=True)
            if self.level == 0:
                draw_text(s, self.hint_for(k), (52, minus.rect.y + 22), 12, MUTED)
            gfx.screen_rect(s, (346, minus.rect.y, 88, 36), (36, 44, 40))
            draw_text(s, "%d %s" % (self.vals[k], unit), (390, minus.rect.y + 18), 17, (140, 255, 170), center=True, bold=True, mono=True, vcenter=True)
            if not self.running:
                minus.draw(s)
                plus.draw(s)
        if not self.running:
            self.run_btn.draw(s)
        bg, m = self.machine()
        s.blit(bg, (m.x - 6, m.y - 6))
        gfx.led(s, (m.x + 160, m.y + 21), (255, 150, 60), self.running and (self.t // 20) % 2 == 0, 4)
        draw_text(s, "lid 105 deg C" if self.running else "lid off", (m.x + 172, m.y + 13), 12, (220, 224, 230), bold=True)
        graph = pygame.Rect(m.x + 22, m.y + 112, m.w - 44, 200)
        gfx.screen_rect(s, graph, (26, 32, 44))
        d, a, e, et, cy = self.vals
        segs = [(d, 120)]
        for _ in range(int(cy)):
            segs += [(d, 30), (a, 30), (e, max(15, et))]
        segs += [(e, 300), (12, 120)]
        tot = float(sum(t for _, t in segs))

        def ty(temp):
            return graph.bottom - 12 - (temp - 10) / 95.0 * (graph.h - 24)
        for tt in (95, 72, 55):       # temperature labels in a margin of their own, left of the trace
            pygame.draw.line(s, (54, 62, 82), (graph.x + 26, ty(tt)), (graph.right - 4, ty(tt)), 1)
            draw_text(s, "%d" % tt, (graph.x + 21, ty(tt)), 11, (150, 160, 190), right=True, vcenter=True)
        x = graph.x + 28
        pts = []
        upto = self.prog * tot if self.running else tot
        acc = 0
        for temp, dur in segs:
            w = dur / tot * (graph.w - 32)
            if acc <= upto:
                pts += [(x, ty(temp)), (x + w * clamp((upto - acc) / dur, 0, 1), ty(temp))]
            acc += dur
            x += w
        if len(pts) > 1:
            col = (255, 170, 90) if self.running else (120, 200, 230)
            pygame.draw.lines(s, mix(col, (26, 32, 44), 0.6), False, [(px, py + 1) for px, py in pts], 4)
            pygame.draw.aalines(s, col, False, pts)
            pygame.draw.lines(s, col, False, pts, 2)
            if self.running:
                gfx.glow(s, pts[-1], 12, (200, 120, 60))
        done = 0
        if self.running:
            per = (tot - 540) / max(1, cy)
            done = int(clamp((self.prog * tot - 120) / max(1, per), 0, cy))
        copies = (1 + self.eff) ** done
        draw_text(s, "Cycle %d / %d" % (done, cy), (m.x + 30, graph.bottom + 14), 18, INK, bold=True)
        draw_text(s, "Copies of the target per template:", (m.x + 30, graph.bottom + 44), 14, INK_SOFT)
        draw_text(s, sci(copies), (m.x + 30, graph.bottom + 62), 26, CORAL_D, bold=True)

# ------------------------------------------------------------------ load the gel
LANES = ["L", "1", "2", "3", "4", "5", "6", "NTC"]
GEL_R = pygame.Rect(160, TOP + 100, 610, 312)


RUN_R = pygame.Rect(120, TOP + 100, 540, 312)


def well_rects(g=GEL_R):
    gap = g.w / (len(LANES) + 1)
    return [pygame.Rect(int(g.x + gap * (i + 1) - 19), g.y + 26, 38, 13) for i in range(len(LANES))]


def lane_names(ctx):
    """Lane labels for this station's gel: the Expert strip has a positive control lane."""
    controls = getattr(ctx, "pcr_controls", None)
    if controls is not None and "+" in controls:
        return ["L", "1", "2", "3", "4", "5", "+", "NTC"]
    if controls is not None and "NTC" not in controls:   # no control was set up: every lane is a sample
        return ["L", "1", "2", "3", "4", "5", "6", "7"]
    return list(LANES)


@register("pcr_load")
class LoadStage(Stage):
    title = "Load the gel"
    instr = ("Move the pipette tip over the flashing well and hold the mouse button to push the sample in. "
             "Your hand shakes more when you move fast or hold too long. Hold Space to rest your elbow on the bench: "
             "steadier, but only for a few seconds at a time. Sample outside the well is lost.")
    limit = 70

    def setup(self):
        self.tremor = Tremor(self.rng)
        self.lanes = lane_names(self.ctx)
        shrink = self.lv(0, 0, 8)
        self.wells = [w.inflate(-shrink, 0) for w in well_rects()]
        self.cur = 0
        self.fill = [0.0] * len(self.lanes)
        self.spill = [0] * len(self.lanes)
        self.scores = []
        self.blobs = []
        self.speed = 0.0
        self.hold = 0
        self.tip = (480, 300)
        self.rest = 1.0              # elbow rest: drains while Space is held, recharges slowly
        self.resting = False
        self.base = self.lv(1.8, 2.5, 3.2)
        self.fatigue = self.lv(0.1, 0.2, 0.3)
        self.rate = self.lv(1 / 40.0, 1 / 50.0, 1 / 60.0)
        self.hint = "Slow and steady: approach the well, stop, then press. Space = rest your elbow."

    def amp(self):
        a = self.base + self.cur * self.fatigue + min(10, self.speed * 0.5) + min(8, max(0, self.hold - 70) * 0.06)
        return a * (0.45 if self.resting else 1.0)

    def tick(self, inp):
        self.speed = self.speed * 0.85 + inp.moved * 0.15
        want = "space" in inp.held or pygame.K_SPACE in inp.keys
        self.resting = want and self.rest > 0.02
        if self.resting:
            self.rest = max(0.0, self.rest - 1 / 150.0)
        else:
            self.rest = min(1.0, self.rest + 1 / 480.0)
        dx, dy = self.tremor.at(self.t, self.amp())
        self.tip = (inp.mouse[0] + dx, inp.mouse[1] + dy)
        if self.cur >= len(self.lanes):
            return
        if not inp.down:
            self.wait_release = False
        if inp.down and not getattr(self, "wait_release", False):
            self.hold += 1
            w = self.wells[self.cur]
            if w.inflate(-4, 0).collidepoint(self.tip):
                self.fill[self.cur] += self.rate
                if self.t % 8 == 0:
                    audio.sfx("blip")
                if self.fill[self.cur] >= 1.0:
                    sc = max(0, 100 - self.spill[self.cur] * 3)
                    self.scores.append(sc)
                    audio.sfx("good" if sc >= 70 else "ding")
                    self.floaters.add(w.centerx, w.y - 30, "loaded" if sc >= 90 else "%d %%" % sc, GREEN if sc >= 70 else CORAL_D, 18)
                    if sc >= 90:
                        self.particles.burst(w.centerx, w.centery, 10, cols=(DYE, LAV, WHITE), speed=2.5, size=3)
                    self.cur += 1
                    self.hold = 0
                    self.wait_release = True
                    if self.cur >= len(self.lanes):
                        self.done_all()
            elif GEL_R.collidepoint(self.tip) or any(x.collidepoint(self.tip) for x in self.wells):
                self.spill[self.cur] += 1
                if self.spill[self.cur] % 6 == 1:
                    self.blobs.append((self.tip[0], self.tip[1], self.rng.uniform(4, 8), self.t))
                    audio.sfx("splash")
                    self.shake = 6
                    if self.t - getattr(self, "_spill_t", -99) >= 40:    # one label at a time, or they pile up
                        self._spill_t = self.t
                        self.floaters.add(self.tip[0], self.tip[1] - 20, "spilled!", RED, 16)
        elif not inp.down:
            self.hold = 0

    def spilled_lanes(self):
        return [self.lanes[i] for i, x in enumerate(self.spill) if x]

    def done_all(self):
        avg = sum(self.scores) / len(self.lanes)
        try:
            self.ctx.pcr_lanes = list(self.scores)
        except Exception:
            pass
        sp = self.spilled_lanes()
        fb = ["All 8 wells loaded." if not sp else "Sample spilled at lane%s %s: those bands will be faint." % ("" if len(sp) == 1 else "s", ", ".join(sp))]
        best = sum(1 for x in self.scores if x >= 90)
        fb.append("%d of 8 wells loaded cleanly." % best)
        fb.append("Tip: rest your elbow (Space) for the last stretch, then press." if sp else "Steady hands.")
        self.finish(avg, *fb)

    def partial(self):
        return sum(self.scores) / len(self.lanes)

    def update(self, inp):
        was = self.done
        Stage.update(self, inp)
        if self.done and not was and self.feedback == ["Time ran out."]:
            sp = self.spilled_lanes()
            self.feedback = ["Time ran out with %d of 8 wells loaded." % self.cur]
            if sp:
                self.feedback.append("Sample spilled at lane%s %s. Stop moving before you press." % ("" if len(sp) == 1 else "s", ", ".join(sp)))

    def autoplay(self):
        self.scores = [95] * len(self.lanes)
        self.done_all()

    def render(self, s):
        gfx.bench(s, LAV)
        draw_tank(s, GEL_R)
        tb, tr = tank_terminals(GEL_R)
        cable(s, tb, (-30, tb[1] + 60), (34, 34, 40), 20)
        cable(s, tr, (-30, tr[1] + 30), (200, 50, 46), 20)
        s.blit(agarose_slab(GEL_R.w, GEL_R.h), GEL_R.topleft)
        gfx.rrect(s, GEL_R, None, mix(AGAROSE, INK, 0.5), 1, 4)
        for i, w in enumerate(self.wells):
            well(s, w, self.fill[i], DYE)
            if i == self.cur:
                p = 0.5 + 0.5 * math.sin(self.t * 0.2)
                gfx.rrect(s, w.inflate(8 + 4 * p, 8 + 4 * p), None, CORAL, 2, 5)
            draw_text(s, self.lanes[i], (w.centerx, w.y - 20), 13, CORAL_D if self.lanes[i] in ("+", "NTC") else INK, center=True, bold=True)
        for x, y, r, t0 in self.blobs:
            age = (self.t - t0) / 60.0
            gfx.alpha_circle(s, DYE, (x, y + age * 3), r + age * 6, max(0, 150 - age * 40))
        buffer_over(s, GEL_R, self.t)
        draw_text(s, "-", (tb[0], tb[1] - 1), 18, WHITE, center=True, bold=True, vcenter=True)
        draw_text(s, "+", (tr[0], tr[1] - 1), 18, WHITE, center=True, bold=True, vcenter=True)
        # steadiness meter and elbow rest
        gfx.card(s, (836, TOP + 70, 100, 330), CARD)
        draw_text(s, "Shake", (886, TOP + 80), 14, INK, center=True, bold=True)
        a = clamp((self.amp() - 1.0) / 15.0, 0, 1)
        tube_r = pygame.Rect(870, TOP + 104, 32, 130)
        gfx.rrect(s, tube_r, (236, 240, 236), INK, 2, 10, 0.0, False)
        hh = int((tube_r.h - 6) * a)
        if hh > 4:
            gfx.rrect(s, (tube_r.x + 3, tube_r.bottom - 3 - hh, tube_r.w - 6, hh), mix(GREEN, RED, a), None, 0, 8, 0.2)
        draw_text(s, "Elbow rest", (886, TOP + 244), 12, INK_SOFT, center=True, bold=True)
        gfx.bar(s, (848, TOP + 262, 76, 12), self.rest, TURQ if not self.resting else GREEN)
        draw_text(s, "Space" if not self.resting else "resting", (886, TOP + 278), 12, GREEN if self.resting else MUTED, center=True, bold=True)
        draw_text(s, "Well", (886, TOP + 312), 14, INK_SOFT, center=True, bold=True)
        draw_text(s, "%d / 8" % min(8, self.cur + 1), (886, TOP + 332), 20, INK, center=True, bold=True)
        amt = 1 - self.fill[self.cur] if self.cur < len(self.lanes) else 0
        gfx.pipette(s, (int(self.tip[0]), int(self.tip[1])), DYE, amt, plunger=1 if (self.cur < len(self.lanes) and self.fill[self.cur] > 0) else 0)

# ------------------------------------------------------------------ run the gel (scene for the generic stop stage)
def gel_run_scene(st, s, v):
    gfx.bench(s, LAV)
    uv = st.state != "run"
    size = getattr(st.ctx, "pcr_size", 1000)
    lanes_q = getattr(st.ctx, "pcr_lanes", [90] * 8)
    eff = getattr(st.ctx, "pcr_eff", 1.0) * getattr(st.ctx, "pcr_mix_eff", 1.0)
    extra = getattr(st.ctx, "pcr_extra", [])
    names = lane_names(st.ctx)
    fill = getattr(st.ctx, "pcr_fill", {})
    nsamp = getattr(st.ctx, "pcr_samples", 6)
    nlanes = sum(1 for n in names if n.isdigit())

    def tube_fill(name):
        """How much master mix the tube in this lane received (the gel shows the last samples set up)."""
        if name.isdigit():
            name = str(nsamp - nlanes + int(name))
        return fill.get(name, 1.0)
    wells = well_rects(RUN_R)
    y0 = wells[0].bottom + 2
    L = RUN_R.bottom - 6 - y0
    ps = pygame.Rect(752, TOP + 112, 188, 176)
    if not uv:
        draw_tank(s, RUN_R, terminals_left=False)
        s.blit(agarose_slab(RUN_R.w, RUN_R.h), RUN_R.topleft)
        gfx.rrect(s, RUN_R, None, mix(AGAROSE, INK, 0.5), 1, 4)
        for i, w in enumerate(wells):
            q = (lanes_q[i] if i < len(lanes_q) else 90) / 100.0
            well(s, w, 0.25, DYE)
            draw_text(s, names[i], (w.centerx, w.y - 20), 13, INK, center=True, bold=True)
            for frac, col in ((1.0, DYE), (0.42, (60, 150, 190))):
                y = y0 + v * L * frac
                if y < RUN_R.bottom - 3:
                    gfx.band(s, w.centerx, y, w.w, 0.45 + 0.4 * q, col, glow=False)
        buffer_over(s, RUN_R, st.t)
        electrode_bubbles(s, RUN_R, st.t)
        tb, tr = tank_terminals(RUN_R, False)
        draw_text(s, "-", (tb[0], tb[1] - 1), 18, WHITE, center=True, bold=True, vcenter=True)
        draw_text(s, "+", (tr[0], tr[1] - 1), 18, WHITE, center=True, bold=True, vcenter=True)
        jb, jr = power_supply(s, ps, 120, v * 45, True, st.t)
        cable(s, tb, jb, (34, 34, 40), 60)
        cable(s, tr, jr, (200, 50, 46), 30)
    else:
        uv_gel(s, RUN_R)
        last_y = -99
        for i, w in enumerate(wells):
            q = (lanes_q[i] if i < len(lanes_q) else 90) / 100.0
            well(s, w, 0, uv=True)
            draw_text(s, names[i], (w.centerx, w.y - 20), 13, (220, 210, 240), center=True, bold=True)
            if i == 0:
                bands = [(b, 0.9) for b in LADDER_100]
            elif names[i] == "NTC":
                bands = []
            else:
                k = q * (0.25 + 0.75 * eff) * tube_fill(names[i])
                bands = [(size, k)] + [(b, k * 0.45) for b in extra]
            for b, k in bands:
                y = y0 + v * L * mobility(b)
                if y < RUN_R.bottom - 4:
                    uv_band(s, w.centerx, y, w.w, k)
                    if i == 0 and y - last_y > 13:
                        draw_text(s, fmt_bp(b), (w.x - 6, y - 8), 12, (226, 214, 250), right=True, bold=True, shadow=(10, 6, 20))
                        last_y = y
        jb, jr = power_supply(s, ps, 0, v * 45, False, st.t)
        cable(s, jb, (jb[0] - 30, ps.bottom + 90), (34, 34, 40), 10)
        cable(s, jr, (jr[0] + 20, ps.bottom + 90), (200, 50, 46), 10)

PCR_RUN = dict(title="Run the gel", scene=gel_run_scene, dur=10, ideal=0.78, window=(0.55, 0.95),
               instr="Current is on: the purple loading dye runs towards the red (+) electrode. Click or press Space to stop when the dye front is about three quarters down the gel, before it runs off.",
               readout=lambda v: "120 V %02d min" % int(v * 45),
               over_msg="The dye ran off the end of the gel, and your smaller bands went with it.",
               early_msg="Stopped too early: the bands are still bunched up near the wells.",
               late_msg="Very close to the end: the smallest ladder bands are already gone.",
               good_msg="Well-separated bands, and your product is still on the gel.")


TECH = dict(
    key="pcr", name="PCR", full="Polymerase chain reaction", wing="DNA", icon="pcr",
    blurb="Copies one chosen stretch of DNA millions of times, so that it can be seen on a gel, sequenced or cloned.",
    facts=[
        "Kary Mullis came up with PCR in 1983 while driving at night in California. He shared the 1993 Nobel Prize in Chemistry for it.",
        "Taq polymerase comes from Thermus aquaticus, a bacterium first isolated from a hot spring in Yellowstone National Park.",
        "Early PCR used a polymerase that the heat destroyed, so fresh enzyme had to be added by hand after every cycle.",
        "Each cycle can double the target, so 30 cycles can in theory turn one molecule into about a billion copies (2^30).",
        "Taq does not proofread. When the exact sequence matters, labs use proofreading enzymes such as Pfu or Q5.",
        "Taq adds a single extra A to the 3' ends of its products. TA cloning uses this overhang to ligate PCR products into vectors.",
        "Magnesium ions are the polymerase cofactor. Too much magnesium makes primers bind less specifically and gives extra bands.",
    ],
    quiz=[
        dict(q="Why does PCR need a heat-stable polymerase?", options=["Every cycle heats the reaction to about 95 deg C", "It works faster in the cold", "Primers only bind when hot", "To cut the DNA"],
             answer=0, why="Denaturation at about 95 deg C would destroy an ordinary polymerase in the first cycle."),
        dict(q="What happens in the annealing step?", options=["The primers bind to their target sequences", "The two DNA strands separate", "The polymerase copies the DNA", "The product is cut"],
             answer=0, why="At the annealing temperature, usually a few degrees below the primer Tm, the primers find and bind their targets."),
        dict(q="Why make a master mix for one extra reaction?", options=["Pipetting loses a little each time, so an exact mix runs short", "Taq degrades in the tube", "To dilute the primers", "The extra tube is the template"],
             answer=0, why="Small losses add up with every dispense: making 1 extra reaction (or 10 % more) keeps the last tube full."),
        dict(q="What is the no-template control (NTC) for?", options=["To check reagents are not contaminated with DNA", "To measure the product size", "To check the gel", "To calibrate the cycler"],
             answer=0, why="The NTC has everything but template. A band there means something in the mix is contaminated."),
    ],
    music=dict(name="Thermocycler Funk", bpm=108, beats=4, root=50, mode="dor", prog=[0, 3, 0, 3, 0, 3, 4, 4], lead="epiano",
               comp="stab", drums="funk", swing=0.08, motif=[(0, 1), (0, 1), (2, 1), (4, 2), (3, 1), (2, 1), (0, 1), (4, 4), (2, 2), (0, 2)]),
    stages=[
        ("pcr_find", {}),
        ("pcr_mix", {}),
        ("pcr_cycler", {}),
        ("pcr_load", {}),
        ("stop", PCR_RUN),
    ],
)
TECHS = [TECH]
