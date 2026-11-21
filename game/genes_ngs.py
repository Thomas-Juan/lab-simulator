# -*- coding: utf-8 -*-
"""Next-generation (Illumina) sequencing: call bases cycle by cycle, align reads, read a volcano plot."""
import math
import random
import pygame
import audio
import gfx
import render as R
from stage import Stage, register, TOP, BOTTOM
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, CORAL, CORAL_D, TURQ, TEAL, LAV, VIOLET, SKY, NIGHT,
                  WHITE, GREEN, RED, YELLOW, BASE_COL, draw_text, draw_wrapped, mix, clamp)
from genes_common import float_x, desktop, rand_seq, cell_row, ring, window, screen_window, aa_polyline, plot_box, base_tile
from genes_sanger import typed

SBS = {"A": (70, 225, 100), "C": (90, 150, 255), "G": (250, 222, 70), "T": (245, 80, 80)}
# two-colour chemistry (NextSeq / NovaSeq): T green, C red, A both channels, G no light
SBS2 = {"A": (250, 196, 70), "C": (245, 80, 80), "T": (70, 225, 100), "G": None}


@register("ngs_sbs")
class SBS_Stage(Stage):
    title = "Sequencing by synthesis"
    instr = ("Each cycle adds one fluorescent base to every cluster, then the camera takes a picture. "
             "Call the colour of the circled cluster: A green, C blue, G yellow, T red. "
             "Expert: the second cluster is read on a two-colour instrument.")

    def setup(self):
        rng = self.rng
        self.T = pygame.Rect(36, TOP + 14, 560, 440)
        self.cyc_per = self.p.get("cycles", self.lv(8, 10, 12))
        self.two = self.level == 2
        self.bleed = self.lv(0.12, 0.22, 0.36)
        self.pace = self.lv(1.25, 1.0, 0.82)
        self.streak = 0
        self.best = 0
        self.total = 2 * self.cyc_per
        self.clusters = []
        for _ in range(130):
            x = rng.uniform(self.T.x + 16, self.T.right - 16)
            y = rng.uniform(self.T.y + 16, self.T.bottom - 16)
            self.clusters.append([x, y, rng.uniform(4, 8), rand_seq(rng, self.total + 2), rng.uniform(0.65, 1.15)])
        self.targets = [rng.randrange(len(self.clusters)) for _ in range(2)]
        while self.targets[1] == self.targets[0]:
            self.targets[1] = rng.randrange(len(self.clusters))
        self.cyc = 0
        self.f = 0
        self.called = False
        self.calls = []
        self.correct = 0
        self.btns = [gfx.Button((640 + i * 72, BOTTOM - 62, 62, 46), b, SBS[b], size=22) for i, b in enumerate("ACGT")]
        self.hint = "Keys A C G T, or click the buttons."

    def target(self):
        return self.clusters[self.targets[0 if self.cyc < self.cyc_per else 1]]

    def base_now(self):
        return self.target()[3][self.cyc % self.cyc_per + (0 if self.cyc < self.cyc_per else self.cyc_per)]

    def cyc_len(self):
        return int((170 - 75 * self.cyc / self.total) * self.pace)

    def col_of(self, b, phase):
        """Colour of a base in the image; None = dark (G in two-colour chemistry)."""
        return SBS2[b] if (self.two and phase) else SBS[b]

    def tick(self, inp):
        self.f += 1
        flow = 34
        if self.f > flow and not self.called:
            for b in typed(inp, "ACGT") + [bt.label for bt in self.btns if bt.hit(inp)]:
                ok = b == self.base_now()
                self.calls.append((b, ok))
                self.called = True
                tx, ty = self.target()[:2]
                if ok:
                    self.correct += 1
                    self.streak += 1
                    self.best = max(self.best, self.streak)
                    audio.sfx("click")
                    self.floaters.add(tx, ty - 22, b, GREEN, 22)
                    if self.streak in (5, 10, 15, 20):
                        audio.sfx("ding")
                        self.floaters.add(self.T.centerx, self.T.y + 40, "%d in a row!" % self.streak, (120, 230, 200), 22)
                else:
                    self.streak = 0
                    self.shake = 6
                    audio.sfx("bad")
                    self.floaters.add(tx, ty - 22, "it was " + self.base_now(), RED, 18)
                self.f = max(self.f, self.cyc_len() - 18)
                break
        if self.f >= self.cyc_len():
            if not self.called:
                self.streak = 0
                self.calls.append(("-", False))
                audio.sfx("bad")
                self.floaters.add(self.target()[0], self.target()[1] - 22, "missed", CORAL_D, 18)
            self.cyc += 1
            self.f = 0
            self.called = False
            if self.cyc == self.cyc_per:
                audio.sfx("whoosh")
                if self.two:
                    self.floaters.add(self.T.centerx, self.T.y + 70, "Two-colour chemistry: G is dark!", YELLOW, 22)
            if self.cyc >= self.total:
                self.cyc = self.total - 1
                fb = ["%d of %d bases called right; best run %d in a row." % (self.correct, self.total, self.best),
                      "Each cycle reads one base in millions of clusters at once: that is what makes it 'massively parallel'."]
                if self.two:
                    fb.append("Two-colour instruments read G as no light, so a run of Gs and a dead cluster both look dark.")
                self.finish(100.0 * self.correct / self.total, *fb)

    def partial(self):
        return 100.0 * self.correct / self.total

    def autoplay(self):
        self.finish(90, "(autoplay)")

    def field(self):
        """Static dark tile: hexagonal nanowell pattern and faint unlit clusters."""
        if getattr(self, "_field", None) is None:
            T = self.T
            f = gfx.texture(T.w, T.h, (14, 14, 28), 30, 4, 77, 2).copy()
            for row in range(0, T.h // 11 + 1):
                for col in range(0, T.w // 13 + 1):
                    x = col * 13 + (6 if row % 2 else 0)
                    y = row * 11
                    pygame.draw.circle(f, (30, 32, 52), (x, y), 2)
            for c in self.clusters:
                R.gd.filled_circle(f, int(c[0] - T.x), int(c[1] - T.y), int(c[2]), (44, 46, 70))
                R.gd.aacircle(f, int(c[0] - T.x), int(c[1] - T.y), int(c[2]), (60, 62, 90))
            vg = pygame.Surface(T.size, pygame.SRCALPHA)
            for i in range(24):
                pygame.draw.rect(vg, (0, 0, 0, 7), (i * 3, i * 3, T.w - i * 6, T.h - i * 6), 3, border_radius=10)
            f.blit(vg, (0, 0))
            self._field = f
        return self._field

    def noise(self):
        """Camera read noise and faint background for the imaging channel (static per stage)."""
        if getattr(self, "_noise", None) is None:
            T = self.T
            sf = pygame.Surface(T.size)
            try:
                import numpy as np
                rng = np.random.default_rng(42)
                v = np.clip(rng.normal(6, 5, (T.w, T.h)), 0, 40)
                pygame.surfarray.blit_array(sf, np.stack([v * 0.9, v, v * 1.2], axis=2).astype(np.uint8))
            except Exception:
                sf.fill((4, 4, 6))
            self._noise = sf
        return self._noise

    def render(self, s):
        gfx.bench(s, LAV)
        T = self.T
        desktop(s, (4, TOP - 2, W - 8, 456))
        s.blit(self.field(), T.topleft)
        flow = 34
        k = self.cyc % self.cyc_per + (0 if self.cyc < self.cyc_per else self.cyc_per)
        if self.f < flow:
            x = T.x + T.w * self.f / flow
            gfx.alpha_rect(s, (T.x, T.y, x - T.x, T.h), (120, 170, 240), 30)
            for i in range(6):
                yy = T.y + (i + 0.5) * T.h / 6
                R.gd.filled_circle(s, int(x - 4 - (i % 2) * 6), int(yy), 3, (180, 210, 255, 120))
            aa_polyline(s, (170, 205, 255), [(x, T.y), (x, T.bottom)], 2)
        else:
            a = min(1.0, (self.f - flow) / 12.0)
            aq = round(a * 5) / 5.0
            phase = self.cyc >= self.cyc_per
            if aq > 0:     # each cluster is a blurred point of light; the whole image is cached per cycle
                key = (k, aq, phase)
                lit = getattr(self, "_lit", {})
                img = lit.get(key)
                if img is None:
                    img = pygame.Surface(T.size)
                    for c in self.clusters:
                        col = self.col_of(c[3][k], phase)
                        rr = int(c[2])
                        b = aq * c[4]
                        p = (c[0] - T.x, c[1] - T.y)
                        if col is not None:
                            gfx.glow(img, p, rr * 3, col, 0.5 * b)
                            gfx.glow(img, p, max(2, rr + 1), mix(col, WHITE, 0.5), 0.6 * b)
                        prev = self.col_of(c[3][k - 1], phase) if k > 0 else None
                        if prev is not None and (phase or self.level == 2):
                            gfx.glow(img, (p[0] + 1, p[1]), rr * 2, prev, self.bleed * aq)
                    if len(lit) > 8:
                        lit.clear()
                    lit[key] = img
                    self._lit = lit
                s.blit(img, T.topleft, special_flags=pygame.BLEND_ADD)
        if self.f >= flow:
            s.blit(self.noise(), T.topleft, special_flags=pygame.BLEND_ADD)
        tx, ty, tr = self.target()[:3]
        ring(s, WHITE, (tx, ty), tr + 8, 2)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            aa_polyline(s, WHITE, [(tx + dx * (tr + 11), ty + dy * (tr + 11)), (tx + dx * (tr + 21), ty + dy * (tr + 21))], 2)
        gfx.rrect(s, T, None, (70, 72, 80), 1, 4)
        gfx.tag(s, T.x + 10, T.bottom - 32, "flow cell  ·  tile 1101", (200, 198, 226), 12)
        # right panel
        Rr = pygame.Rect(616, TOP + 14, 324, 380)
        inner = window(s, Rr, "Imaging  ·  cycle %d of %d" % (self.cyc + 1, self.total), VIOLET)
        draw_text(s, "Cluster %d" % (1 if self.cyc < self.cyc_per else 2), (inner.right - 4, inner.y + 2), 14, MUTED, right=True, bold=True)
        zc = (inner.x + 64, inner.y + 66)
        R.aa_circle(s, (14, 14, 28), zc, 52, 3, INK, False)
        if self.f >= flow:
            a = min(1.0, (self.f - flow) / 12.0)
            ph = self.cyc >= self.cyc_per
            col = self.col_of(self.base_now(), ph)
            prev = self.col_of(self.target()[3][k - 1], ph) if k > 0 else None
            if (ph or self.level == 2) and prev is not None:
                gfx.glow(s, (zc[0] + 4, zc[1]), 40, prev, self.bleed * 1.3 * a)
            if col is not None:
                gfx.glow(s, zc, 50, col, 1.3 * round(a * 5) / 5.0)
                R.gd.filled_circle(s, zc[0], zc[1], 18, mix((44, 46, 70), mix(col, WHITE, 0.4), a))
            else:
                R.gd.filled_circle(s, zc[0], zc[1], 18, (34, 36, 54))
        else:
            draw_text(s, "adding bases", zc, 13, (190, 190, 210), center=True, vcenter=True)
        draw_text(s, "zoom", (zc[0], zc[1] + 58), 12, MUTED, center=True)
        frac = 1 - self.f / float(self.cyc_len())
        draw_text(s, "time to call", (inner.x + 140, inner.y + 40), 13, INK_SOFT, bold=True)
        gfx.bar(s, (inner.x + 140, inner.y + 62, 150, 16), frac if self.f >= flow else 1.0, CORAL)
        ph = self.cyc >= self.cyc_per
        if self.two and ph:
            draw_text(s, "two-colour chemistry:", (inner.x + 140, inner.y + 88), 13, CORAL_D, bold=True)
            draw_text(s, "A = red + green, G = dark", (inner.x + 140, inner.y + 105), 13, CORAL_D, bold=True)
        for i, b in enumerate("ACGT"):
            cx = inner.x + 16 + i * 74
            R.aa_circle(s, (20, 20, 34), (cx, inner.y + 150), 12, 2, INK, False)
            cc = self.col_of(b, ph)
            if cc is not None:
                R.gd.filled_circle(s, cx, inner.y + 150, 6, cc)
            draw_text(s, b, (cx + 18, inner.y + 140), 18, INK, bold=True)
        draw_text(s, "Read so far", (inner.x + 4, inner.y + 180), 14, INK_SOFT, bold=True)
        for j, (b, ok) in enumerate(self.calls[-20:]):
            x = inner.x + 4 + (j % 10) * 29
            y = inner.y + 204 + (j // 10) * 34
            gfx.rrect(s, (x, y, 26, 28), (204, 238, 206) if ok else (250, 204, 196), GREEN if ok else RED, 1, 5, 0.1)
            draw_text(s, b, (x + 13, y + 14), 16, INK, center=True, bold=True, mono=True, vcenter=True)
        for bt in self.btns:
            bt.draw(s)


@register("ngs_align")
class Align(Stage):
    title = "Align the reads"
    instr = ("Drag each read left or right until it matches the reference (or select it and use the arrow keys). "
             "Then click the reference base where the reads show a real variant.")
    limit = 100

    def setup(self):
        rng = self.rng
        n = self.lv(4, 4, 7)
        self.cw, self.x0 = self.lv(22, 22, 19), 104
        self.RL, self.L = self.lv(32, 36, 40), self.lv(12, 12, 14)
        step = (self.RL - self.L - 2) / float(n - 1)
        offs = [int(round(1 + i * step)) for i in range(n)]
        self.het = self.level == 2 and rng.random() < 0.5
        n_err = self.lv(1, 1, 2)
        for _ in range(600):
            ref = rand_seq(rng, self.RL)
            cover = {p: [i for i, o in enumerate(offs) if o <= p < o + self.L] for p in range(self.RL)}
            need = 4 if self.level == 2 else 2
            cand = [p for p in range(4, self.RL - 4) if len(cover[p]) >= need]
            if not cand:
                continue
            snp = rng.choice(cand)
            alt = rng.choice([b for b in "ACGT" if b != ref[snp]])
            carriers = list(cover[snp])
            if self.het:
                rng.shuffle(carriers)
                carriers = carriers[:len(carriers) // 2]
            reads = []
            for i, o in enumerate(offs):
                r = list(ref[o:o + self.L])
                if i in carriers:
                    r[snp - o] = alt
                reads.append(r)
            self.err_cols = []
            for k in rng.sample(range(n), n_err):
                o = offs[k]
                choices = [j for j in range(1, self.L - 1) if o + j != snp and o + j not in self.err_cols]
                j = rng.choice(choices)
                reads[k][j] = rng.choice([b for b in "ACGT" if b != reads[k][j]])
                self.err_cols.append(o + j)
            reads = ["".join(r) for r in reads]
            if all(self.unique(ref, rd, o) for rd, o in zip(reads, offs)):
                break
        self.ref, self.reads, self.true, self.snp = ref, reads, offs, snp
        self.off = []
        for o in offs:
            c = o
            while abs(c - o) < 3:
                c = rng.randint(0, self.RL - self.L)
            self.off.append(c)
        self.n = n
        self.locked = [False] * n
        self.sel = 0
        self.drag = None
        self.phase = "align"
        self.t_aligned = None
        self.wrong = 0
        self.found = False
        self.zyg = None
        self.rowh = 56 if n <= 4 else 35
        self.y_rows = TOP + 140 if n <= 4 else TOP + 132
        # in the line under the reads, so the question never hides the reads it is about
        self.zbtns = [gfx.Button((W - 382, TOP + 375, 150, 34), "Homozygous", (206, 226, 240), size=15),
                      gfx.Button((W - 222, TOP + 375, 150, 34), "Heterozygous", (240, 222, 206), size=15)]

    def unique(self, ref, rd, o):
        for c in range(0, self.RL - self.L + 1):
            if c != o and sum(1 for j in range(self.L) if ref[c + j] != rd[j]) < 4:
                return False
        return True

    def row_y(self, i):
        return self.y_rows + i * self.rowh

    def read_rect(self, i):
        return pygame.Rect(self.x0 + self.off[i] * self.cw, self.row_y(i), self.L * self.cw, 30 if self.n > 4 else 34)

    def try_lock(self, i):
        if self.off[i] == self.true[i] and not self.locked[i]:
            self.locked[i] = True
            audio.sfx("good")
            r = self.read_rect(i)
            self.particles.burst(r.centerx, r.centery, 14)
            if all(self.locked):
                self.phase = "snp"
                self.t_aligned = self.t
                audio.sfx("ding")
                self.floaters.add(W // 2, TOP + 110, "All aligned!", GREEN, 24)
            else:
                self.sel = [k for k in range(self.n) if not self.locked[k]][0]

    def tick(self, inp):
        if self.phase == "align":
            if inp.click:
                for i in range(self.n):
                    if not self.locked[i] and self.read_rect(i).collidepoint(inp.mouse):
                        self.drag = i
                        self.sel = i
                        self.grab = inp.mouse[0] - self.read_rect(i).x
                        audio.sfx("blip")
            if self.drag is not None:
                i = self.drag
                o = int(clamp(round((inp.mouse[0] - self.grab - self.x0) / float(self.cw)), 0, self.RL - self.L))
                if o != self.off[i]:
                    self.off[i] = o
                    audio.sfx("tick")
                if inp.release or not inp.down:
                    self.drag = None
                    self.try_lock(i)
            if self.phase == "align" and not self.locked[self.sel]:
                d = ("right" in inp.pressed) - ("left" in inp.pressed)
                if d:
                    self.off[self.sel] = int(clamp(self.off[self.sel] + d, 0, self.RL - self.L))
                    self.try_lock(self.sel)
            if "up" in inp.pressed or "down" in inp.pressed:
                free = [k for k in range(self.n) if not self.locked[k]]
                if free:
                    j = free.index(self.sel) if self.sel in free else 0
                    self.sel = free[(j + (1 if "down" in inp.pressed else -1)) % len(free)]
        elif self.phase == "snp" and inp.click:
            mx, my = inp.mouse
            if TOP + 60 <= my <= TOP + 100 and self.x0 <= mx < self.x0 + self.RL * self.cw:
                col = (mx - self.x0) // self.cw
                if col == self.snp:
                    self.found = True
                    audio.sfx("good")
                    self.particles.burst(mx, my, 26)
                    self.floaters.add(float_x(mx, "real variant", 18), my - 14, "real variant", GREEN, 18)
                    if self.level == 2:
                        self.phase = "zyg"
                    else:
                        self.end()
                else:
                    self.wrong += 1
                    audio.sfx("bad")
                    self.shake = 8
                    msg = "only one read: a sequencing error" if col in self.err_cols else "no variant here"
                    self.floaters.add(float_x(mx, msg, 16), my - 14, msg, RED, 16)
                    if self.wrong >= 3:
                        self.end()
        elif self.phase == "zyg":
            for k, b in enumerate(self.zbtns):
                if b.hit(inp):
                    self.zyg = (k == 1) == self.het
                    audio.sfx("good" if self.zyg else "bad")
                    if not self.zyg:
                        self.shake = 8
                    self.end()

    def end(self):
        secs = self.t_aligned / 60.0 if self.t_aligned else self.t / 60.0
        budget = self.lv(50, 40, 45)
        a = 60 if secs <= budget else max(30, 60 - (secs - budget) * 0.75)
        b = max(0, 40 - 15 * self.wrong) if self.found else 0
        fb = ["Reads aligned in %d s; %d wrong variant click%s." % (secs, self.wrong, "" if self.wrong == 1 else "s")]
        fb.append("A mismatch shared by several reads at one position is a real variant; a mismatch in one read is probably a sequencing error."
                  if self.found else "The variant was at position %d: the reads covering it disagree with the reference." % (self.snp + 1))
        if self.level == 2:
            a, b = a * 55 / 60.0, b * 30 / 40.0
            z = 15 if self.zyg else 0
            fb.append("It was %s: %s." % ("heterozygous" if self.het else "homozygous",
                                         "about half of the reads carry the other base" if self.het else "every read covering it carries the other base"))
            self.finish(a + b + z, *fb)
        else:
            self.finish(a + b, *fb)

    def partial(self):
        return 45.0 * sum(self.locked) / self.n + (40 if self.found else 0) * (0.75 if self.level == 2 else 1)

    def autoplay(self):
        self.finish(88, "(autoplay)")

    def render(self, s):
        gfx.bench(s, SKY)
        inner = screen_window(s, (40, TOP + 6, W - 80, 408), "Genome browser  ·  reads mapped to the reference", TEAL)
        x0, cw = self.x0, self.cw
        for i in range(self.RL):
            x = x0 + i * cw
            pygame.draw.line(s, (214, 216, 224), (x + cw // 2 - 1, TOP + 52), (x + cw // 2 - 1, TOP + 56 if i % 5 else TOP + 60))
            if i % 5 == 0:
                draw_text(s, str(i + 1), (x + cw // 2, TOP + 38), 11, MUTED, center=True, bold=True)
        draw_text(s, "Ref", (x0 - 12, TOP + 72), 15, INK, right=True, bold=True)
        fills = {i: (250, 236, 180) for i in range(self.RL)} if self.phase == "snp" else {}
        if self.found:
            fills = {self.snp: (204, 238, 206)}
        cell_row(s, x0, TOP + 66, self.ref, cw, 15 if cw < 22 else 16, fills, h=30)
        gfx.rrect(s, (x0 - 4, TOP + 62, self.RL * cw + 6, 38), None, (130, 134, 140), 1, 4)
        cov = [0] * self.RL
        for i in range(self.n):
            for j in range(self.L):
                cov[self.off[i] + j] += 1
        for j, c in enumerate(cov):
            if c:
                h = c * (6 if self.n <= 4 else 4)
                gfx.rrect(s, (x0 + j * cw + 2, TOP + 126 - h, cw - 4, h), mix(TURQ, WHITE, 0.35), None, 0, 2, 0.1, False)
        draw_text(s, "depth", (x0 - 12, TOP + 108), 12, MUTED, right=True, bold=True)
        for i in range(self.n):
            r = self.read_rect(i)
            y = self.row_y(i)
            draw_text(s, "read %d" % (i + 1), (x0 - 12, y + (9 if self.n <= 4 else 6)), 14, INK_SOFT, right=True, bold=True)
            fl = {j: ((206, 238, 206) if self.ref[self.off[i] + j] == b else (250, 196, 186)) for j, b in enumerate(self.reads[i])}
            sel = i == self.sel and not self.locked[i] and self.phase == "align"
            edge = GREEN if self.locked[i] else (CORAL if sel else INK)
            gfx.rrect(s, r.inflate(8, 6), (236, 250, 236) if self.locked[i] else (250, 250, 252), edge, 3 if (sel or self.locked[i]) else 2, 8, 0.06)
            cell_row(s, r.x, y + (4 if self.n <= 4 else 2), self.reads[i], cw, 15 if cw < 22 else 16, fl, h=26 if self.n <= 4 else 24)
            if self.locked[i]:
                # tick beside the placed read (the label column has no room left of it)
                tx = r.right + 10 if r.right + 26 <= inner.right else r.x - 26
                aa_polyline(s, GREEN, [(tx, y + 15), (tx + 5, y + 21), (tx + 14, y + 8)], 3)
        by = TOP + 388 if self.n > 4 else TOP + 380
        if self.phase == "snp":
            draw_text(s, "Now click the reference base where the reads show a real variant.", (W // 2, by), 17, CORAL_D, center=True, bold=True)
        elif self.phase == "zyg":
            draw_text(s, "Is this fish homozygous or heterozygous for the variant?", (60, TOP + 382), 16, INK, bold=True)
            for b in self.zbtns:
                b.draw(s)
        else:
            draw_text(s, "Green = matches the reference, red = mismatch. Drag a read to slide it.", (W // 2, by), 15, INK_SOFT, center=True)


ROLES = ["up", "down", "ns_big", "sig_small"]
ROLE_POS = {"up": (2.6, 9.0), "down": (-2.3, 7.0), "ns_big": (3.1, 0.6), "sig_small": (0.25, 7.5)}


def volcano_pic(letters, seed):
    def pic(s, r):
        rng = random.Random(seed)
        inner = window(s, r, "RNA-seq  ·  treated vs control", TEAL, 13)
        P = pygame.Rect(inner.x + 34, inner.y + 22, inner.w - 40, inner.h - 62)
        X = lambda v: P.centerx + v / 5.0 * (P.w / 2)
        Y = lambda v: P.bottom - v / 12.0 * P.h
        plot_box(s, P, [(X(v), str(v)) for v in (-4, -2, 0, 2, 4)], [(Y(v), str(v)) for v in (0, 4, 8)],
                 "log2 fold change", "-log10 p")
        clip = s.get_clip()
        s.set_clip(P.inflate(-2, -2))
        for xv in (-1, 1):
            for yy in range(P.y, P.bottom, 10):
                pygame.draw.line(s, MUTED, (X(xv), yy), (X(xv), yy + 5), 1)
        for xx in range(P.x, P.right, 10):
            pygame.draw.line(s, MUTED, (xx, Y(1.3)), (xx + 5, Y(1.3)), 1)
        for _ in range(320):
            x = rng.gauss(0, 0.9)
            y = abs(rng.gauss(0, 1.1)) + max(0, abs(x) - 0.6) * rng.uniform(0.5, 2.5)
            sig = abs(x) > 1 and y > 1.3
            col = (CORAL if x > 0 else TURQ) if sig else (180, 180, 190)
            px, py = int(X(clamp(x, -4.8, 4.8))), int(Y(min(y, 11.5)))
            R.gd.filled_circle(s, px, py, 3, col + ((210,) if sig else (150,)))
            R.gd.aacircle(s, px, py, 3, col + ((230,) if sig else (160,)))
        s.set_clip(clip)
        for role, letter in letters.items():
            x, y = ROLE_POS[role]
            gfx.circle(s, YELLOW, (X(x), Y(y)), 13)
            draw_text(s, letter, (X(x), Y(y)), 15, INK, center=True, bold=True, vcenter=True)
        draw_text(s, "p = 0.05", (P.right - 4, Y(1.3) - 16), 11, MUTED, right=True)
        draw_text(s, "up", (P.right - 8, P.y + 6), 12, CORAL, right=True, bold=True)
        draw_text(s, "down", (P.x + 8, P.y + 6), 12, TEAL, bold=True)
    return pic


def volcano_q(role, text, why):
    def gen(rng):
        lets = list("ABCD")
        rng.shuffle(lets)
        letters = dict(zip(ROLES, lets))
        return dict(q=text, pic=volcano_pic(letters, rng.random()), options=["Gene A", "Gene B", "Gene C", "Gene D"], keep_order=True,
                    answer="ABCD".index(letters[role]), why=why)
    return gen


VOLCANO = [
    volcano_q("up", "RNA-seq volcano plot. Which gene is significantly up in treated fish?",
              "It is right of +1 (more than two-fold up) and above the p = 0.05 line."),
    volcano_q("down", "Which gene is significantly down in treated fish?",
              "Left of -1 means more than two-fold down; high on the y-axis means a small p-value."),
    volcano_q("ns_big", "Which gene changes a lot but is NOT significant?",
              "A large fold change with a high p-value often comes from a gene with few reads or variable replicates."),
    volcano_q("sig_small", "Which gene is significant but changes less than two-fold?",
              "With many reads and consistent replicates, even small changes reach significance. Whether they matter biologically is another question."),
]

TECH = dict(
    key="ngs", name="NGS", full="Next-generation sequencing", wing="Genes & genomes", icon="ngs",
    blurb="Reads hundreds of millions of short DNA fragments at once, to sequence whole genomes or count every RNA in a sample (RNA-seq).",
    facts=[
        "Illumina sequencing grows clusters of identical copies of each fragment on a glass flow cell, so every spot gives a strong signal for the camera.",
        "Each fluorescent nucleotide carries a reversible block, so exactly one base is added per cycle; the block and dye are then removed.",
        "Two-colour instruments such as the NextSeq and NovaSeq read G as the absence of light, so a run of Gs looks dark.",
        "Sequencing a human genome cost about 100 million US dollars in 2001. Today it costs a few hundred.",
        "Paired-end sequencing reads both ends of each fragment, which helps to place reads in repeats and to find rearrangements.",
        "In RNA-seq, the number of reads that map to a gene is used as a measure of how strongly it is expressed.",
        "A FASTQ file stores each read with a quality score for every base, written as one text character per base.",
        "The zebrafish reference genome is about 1.4 billion bases, and about 70% of human genes have at least one zebrafish counterpart.",
    ],
    quiz=[
        dict(q="Why are fragments amplified into clusters before sequencing?", options=["One molecule gives too little light to image", "To remove errors", "To make them longer", "To add the adapters"],
             answer=0, why="Thousands of identical copies glow together, so the camera can see each cycle's colour."),
        dict(q="In RNA-seq, what does the read count of a gene measure?", options=["How much of its mRNA was in the sample", "Its length only", "How many copies of the gene are in the genome", "Its protein level"],
             answer=0, why="More transcripts give more fragments and more reads (after correcting for gene length and depth)."),
        dict(q="Why are short reads aligned to a reference genome?", options=["To find where each read came from", "To make them longer", "To remove the adapters", "To call the colours"],
             answer=0, why="Each read is only 50-300 bases; mapping places it in the genome so you can count reads or spot variants."),
    ],
    music=dict(name="Flow Cell Flicker", bpm=172, beats=4, root=52, mode="dor", prog=[0, 3, 0, 3, 6, 5, 4, 4],
               lead="square", comp="drive", drums="dnb",
               motif=[(0, 1), (2, 1), (4, 1), (7, 1), (6, 2), (4, 2), (5, 1), (4, 1), (2, 2), (0, 4)]),
    stages=[
        ("ngs_sbs", dict()),
        ("ngs_align", dict()),
        ("quiz", dict(title="Volcano plot", instr="Each dot is one gene from an RNA-seq comparison. Find the gene asked for.", questions=VOLCANO, n=3, tint=LAV)),
    ],
)
TECHS = [TECH]
