# -*- coding: utf-8 -*-
"""CRISPR-Cas9: find PAMs, pick a guide, find the cut site, read the genotyping result."""
import math
import random
import pygame
import audio
import gfx
import render as R
from stage import Stage, register, TOP, BOTTOM
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, CORAL, CORAL_D, TURQ, TEAL, LAV, VIOLET, SKY, WHITE,
                  GREEN, RED, YELLOW, BASE_COL, GEL, draw_text, draw_wrapped, mix, clamp)
from genes_common import desktop, rand_seq, comp, cell_row, trace_pic, window, screen_window, aa_polyline, base_tile, dark_gel, uv_band, ring

PAM_FILL = (250, 222, 120)
CCN_FILL = (250, 196, 170)


def gen_exon(rng, n=64, line=32):
    for _ in range(2000):
        seq = rand_seq(rng, n)
        if "GGG" in seq or "CCC" in seq:
            continue
        # a PAM (NGG or CCN) that wraps across a line break could not be clicked: reject such sequences
        if any((seq[i + 1:i + 3] == "GG" or seq[i:i + 2] == "CC") for i in range(n - 2) if i // line != (i + 2) // line):
            continue
        ngg = [i for i in range(n - 2) if seq[i + 1:i + 3] == "GG" and i // line == (i + 2) // line]
        ccn = [i for i in range(n - 2) if seq[i:i + 2] == "CC" and i // line == (i + 2) // line]
        owner = {}
        ok = True
        for kind, lst in (("ngg", ngg), ("ccn", ccn)):
            for i in lst:
                for j in range(i, i + 3):
                    if j in owner:
                        ok = False
                    owner[j] = (kind, i)
        hi = max(6, int(6 * n / 64))
        if ok and 3 <= len(ngg) <= hi and 1 <= len(ccn) <= 4 and any(i >= 20 for i in ngg) and any(i < 20 for i in ngg):
            return seq, ngg, ccn, owner
    raise RuntimeError("could not make an exon")


@register("crispr_pam")
class FindPAM(Stage):
    title = "Find the PAMs"
    instr = ("Cas9 can only cut next to a PAM: the sequence NGG (any base, then two Gs). "
             "Click every NGG on the top strand (a CCN is a bonus: an NGG on the bottom strand). "
             "Then pick the PAM you will use for your guide.")
    limit = 55

    def setup(self):
        self.lines = self.lv(2, 2, 3)
        self.seq, self.ngg, self.ccn, self.owner = gen_exon(self.rng, 32 * self.lines)
        self.found = set()
        self.bonus = set()
        self.wrong = 0
        self.cw, self.x0 = 26, 64
        self.phase = "find"
        self.pick_wrong = 0
        self.pick = None
        self.gap = 140 if self.lines == 2 else 96
        self.y_first = TOP + 150 if self.lines == 2 else TOP + 136

    def letter_at(self, pos):
        x, y = pos
        for ln in range(self.lines):
            y0 = self.y_first + ln * self.gap
            if y0 - 4 <= y <= y0 + 60:
                i = int((x - self.x0) // self.cw)
                if 0 <= i < 32:
                    return ln * 32 + i
        return None

    def tick(self, inp):
        if not inp.click:
            return
        j = self.letter_at(inp.mouse)
        if j is None:
            return
        o = self.owner.get(j)
        if self.phase == "pick":
            if o and o[0] == "ngg":
                i = o[1]
                if i >= 20:
                    self.pick = i
                    audio.sfx("win")
                    self.particles.burst(inp.mouse[0], inp.mouse[1], 24)
                    self.floaters.add(inp.mouse[0], inp.mouse[1] - 20, "your guide", GREEN, 20)
                    self.end()
                else:
                    self.pick_wrong += 1
                    audio.sfx("bad")
                    self.shake = 10
                    self.floaters.add(inp.mouse[0], inp.mouse[1] - 20, "only %d bases before it" % i, RED, 17)
                    if self.pick_wrong >= 2:
                        self.end()
            return
        if o and o[0] == "ngg" and o[1] not in self.found:
            self.found.add(o[1])
            audio.sfx("good")
            self.particles.burst(inp.mouse[0], inp.mouse[1], 14)
            self.floaters.add(inp.mouse[0], inp.mouse[1] - 20, "PAM!", GREEN, 20)
            if len(self.found) == len(self.ngg):
                self.phase = "pick"
                audio.sfx("ding")
        elif o and o[0] == "ccn" and o[1] not in self.bonus:
            self.bonus.add(o[1])
            audio.sfx("ding")
            self.floaters.add(inp.mouse[0], inp.mouse[1] - 20, "bottom-strand PAM +5", TEAL, 18)
        elif not o:
            self.wrong += 1
            audio.sfx("bad")
            self.shake = 10
            self.floaters.add(inp.mouse[0], inp.mouse[1] - 20, "no PAM", RED, 18)

    def score_now(self):
        find = 100.0 * len(self.found) / len(self.ngg) - self.lv(6, 8, 10) * self.wrong + 5 * len(self.bonus)
        pick = 100 if (self.pick is not None and self.pick_wrong == 0) else 50 if self.pick is not None else 0
        return 0.85 * find + 0.15 * pick

    def end(self):
        fb = ["%d of %d NGG PAMs found, %d wrong clicks." % (len(self.found), len(self.ngg), self.wrong)]
        if self.pick is not None:
            fb.append("Your guide: the 20 bases before the PAM at base %d. It goes on to the Cas9 step." % (self.pick + 1))
            self.ctx.crispr_target = dict(seq=self.seq, pam=self.pick)
        elif self.phase == "pick":
            fb.append("A guide needs 20 bases of target next to the PAM, on its 5' side, inside the exon.")
        if self.bonus:
            fb.append("You also spotted %d PAM(s) on the bottom strand: guides can target either strand." % len(self.bonus))
        self.finish(self.score_now(), *fb)

    def partial(self):
        return max(0, self.score_now() - 10)

    def autoplay(self):
        self.finish(90, "(autoplay)")

    def render(self, s):
        gfx.bench(s, mix(SKY, TURQ, 0.3))
        desktop(s, (4, TOP - 2, W - 8, 456))
        window(s, (22, TOP + 2, W - 44, 92), "Gene view  ·  kdrl", TEAL, 13)
        gene_model(s, TOP + 62)
        inner = window(s, (22, TOP + 104, W - 44, 350), "Exon 2  ·  %d bp, both strands" % len(self.seq), TEAL)
        dx = 0
        for ln in range(self.lines):
            y0 = self.y_first + ln * self.gap
            top = self.seq[ln * 32:(ln + 1) * 32]
            fills_t, fills_b = {}, {}
            guides = []
            show = self.found if self.pick is None else {self.pick}
            for i in self.found:
                for j in range(i, i + 3):
                    if j // 32 == ln:
                        fills_t[j % 32] = PAM_FILL if (self.pick is None or i == self.pick) else (240, 232, 200)
            for i in show:
                if self.phase == "find" and self.level == 2:
                    continue
                seg = [j % 32 for j in range(max(0, i - 20), i) if j // 32 == ln]
                for j in seg:
                    fills_t.setdefault(j, (200, 236, 232))
                if seg:
                    guides.append((min(seg), max(seg)))
            for i in self.bonus:
                for j in range(i, i + 3):
                    if j // 32 == ln:
                        fills_b[j % 32] = CCN_FILL
            xa, xb = self.x0 + dx - 4, self.x0 + dx + 32 * self.cw + 2
            aa_polyline(s, (176, 172, 190), [(xa, y0 - 5), (xb, y0 - 5)], 3)
            aa_polyline(s, (200, 198, 210), [(xa, y0 + 59), (xb, y0 + 59)], 3)
            for g0, g1 in guides:
                gx0, gx1 = self.x0 + dx + g0 * self.cw, self.x0 + dx + (g1 + 1) * self.cw - 2
                aa_polyline(s, CORAL, [(gx0, y0 + 67), (gx1, y0 + 67)], 4)
            draw_text(s, "5'", (self.x0 - 26, y0 + 4), 15, INK_SOFT, bold=True)
            draw_text(s, "3'", (self.x0 + 32 * self.cw + 6, y0 + 4), 15, INK_SOFT, bold=True)
            draw_text(s, "3'", (self.x0 - 26, y0 + 34), 15, MUTED, bold=True)
            draw_text(s, "5'", (self.x0 + 32 * self.cw + 6, y0 + 34), 15, MUTED, bold=True)
            cell_row(s, self.x0 + dx, y0, top, self.cw, 18, fills_t)
            cell_row(s, self.x0 + dx, y0 + 30, comp(top), self.cw, 15, fills_b, col=MUTED)
            for i in range(32):
                x = self.x0 + dx + i * self.cw + self.cw // 2 - 1
                pygame.draw.line(s, (200, 200, 210), (x, y0 + 26), (x, y0 + 30))
        draw_text(s, "PAMs found: %d / %d" % (len(self.found), len(self.ngg)), (64, TOP + 410), 18, INK, bold=True)
        if self.phase == "pick" and self.pick is None:
            gfx.tag(s, W - 40 - 470, TOP + 404, "All found! Now click the PAM for your guide: it needs 20 bases before it.", (252, 236, 200), 14)
            return
        draw_text(s, "bottom strand: %d" % len(self.bonus), (300, TOP + 412), 15, TEAL, bold=True)
        draw_text(s, "Turquoise = protospacer; coral = guide RNA, which pairs with the other strand", (W - 40, TOP + 412), 13, INK_SOFT, right=True)


def gene_model(s, gy):
    """Exon-intron map of the gene with exon 2 highlighted."""
    """Drawn like a genome-browser gene track: thin intron line with arrows, coding exons as tall
    dark boxes, untranslated ends as short boxes."""
    aa_polyline(s, (60, 70, 120), [(110, gy), (850, gy)], 1)
    for x in range(150, 850, 34):
        aa_polyline(s, (60, 70, 120), [(x - 3, gy - 3), (x + 1, gy), (x - 3, gy + 3)], 1)
    exons = ((110, 50), (250, 90), (420, 60), (560, 70), (720, 60))
    for k, (x, w) in enumerate(exons):
        h = 18
        col = TEAL if k == 1 else (52, 62, 120)
        pygame.draw.rect(s, col, (x, gy - h // 2, w, h))
    pygame.draw.rect(s, (52, 62, 120), (110, gy - 5, 22, 10))
    pygame.draw.rect(s, (255, 255, 255), (110 + 22, gy - 9, 0, 18))
    pygame.draw.rect(s, (52, 62, 120), (780, gy - 5, 70, 10))
    draw_text(s, "ATG", (128, gy - 26), 11, GREEN, bold=True)
    draw_text(s, "exon 2", (295, gy - 26), 11, TEAL, center=True, bold=True)
    draw_text(s, "stop", (790, gy - 26), 11, RED, center=True, bold=True)


def no_runs(rng, n):
    out = []
    for _ in range(n):
        ch = rng.choice("ACGT")
        while out and ((out[-1] == "G" and ch == "G") or (out[-1] == "C" and ch == "C")):
            ch = rng.choice("ACGT")
        out.append(ch)
    return out


@register("crispr_cut")
class CutSite(Stage):
    title = "Where does Cas9 cut?"
    instr = ("The guide RNA leads Cas9 to the 20 bases next to the PAM. Cas9 cuts both strands 3 bases "
             "upstream of the PAM. Click the gap where it cuts.")
    limit = 60

    def setup(self):
        self.kinds = self.p.get("kinds", self.lv(["ngg", "ngg"], ["ngg", "ngg", "ccn"], ["ngg", "ccn", "ngg", "ccn"]))
        self.near = self.lv(40, 35, 20)
        self.mine = False
        self.r = 0
        self.scores = []
        self.cw, self.x0 = 28, 72
        self.new_round()

    def new_round(self):
        rng = self.rng
        kind = self.kinds[self.r]
        tgt = getattr(self.ctx, "crispr_target", None)
        self.mine = False
        if self.r == 0 and kind == "ngg" and tgt:
            ex, i = tgt["seq"], tgt["pam"]
            pre = ex[max(0, i - 21):i + 3]
            while len(pre) < 24:
                pre = rng.choice("AT") + pre
            post = "".join(no_runs(rng, 6))
            post = ("A" if post[0] == "G" else post[0]) + post[1:]
            seq = pre + post
            self.kind, self.seq, self.pam, self.proto, self.cut = "ngg", seq, [21, 22, 23], list(range(1, 21)), 18
            self.click = None
            self.anim = 0
            self.gap = None
            self.mine = True
            return
        while True:
            s = no_runs(rng, 30)
            if kind == "ngg":
                i = rng.randint(21, 26)
                if s[i] == "G" or (i + 3 < 30 and s[i + 3] == "G"):
                    continue
                s[i + 1] = s[i + 2] = "G"
                pam, proto, cut = list(range(i, i + 3)), list(range(i - 20, i)), i - 3
            else:
                j = rng.randint(2, 6)
                if s[j - 1] == "C" or s[j + 2] == "C":
                    continue
                s[j] = s[j + 1] = "C"
                pam, proto, cut = list(range(j, j + 3)), list(range(j + 3, j + 23)), j + 6
            seq = "".join(s)
            if kind == "ngg" and "CC" in seq:
                continue
            if kind == "ccn" and "GG" in seq:
                continue
            break
        self.kind, self.seq, self.pam, self.proto, self.cut = kind, seq, pam, proto, cut
        self.click = None
        self.anim = 0
        self.gap = None

    def gap_at(self, x):
        g = int(round((x - self.x0) / float(self.cw)))
        return g if 1 <= g <= 29 else None

    def tick(self, inp):
        if self.click is None:
            self.gap = self.gap_at(inp.mouse[0]) if TOP + 120 <= inp.mouse[1] <= TOP + 300 else None
            if inp.click and self.gap is not None:
                self.click = self.gap
                d = abs(self.click - self.cut)
                sc = 100 if d == 0 else self.near if d == 1 else 0
                self.scores.append(sc)
                if sc == 100:
                    audio.sfx("good")
                    self.floaters.add(self.x0 + self.cut * self.cw, TOP + 110, "Snip!", GREEN, 26)
                    self.particles.burst(self.x0 + self.cut * self.cw, TOP + 220, 22)
                else:
                    audio.sfx("bad")
                    self.shake = 10
                    self.floaters.add(self.x0 + self.click * self.cw, TOP + 110, "off by %d" % d, RED, 22)
        else:
            self.anim += 1
            if self.anim > 130 or (self.anim > 50 and inp.click):
                self.r += 1
                if self.r >= len(self.kinds):
                    self.r -= 1
                    self.anim = -10 ** 6
                    self.finish(sum(self.scores) / len(self.scores), "%d of %d cut sites exact." % (self.scores.count(100), len(self.kinds)),
                                "Cas9 cuts 3 bases from the PAM, inside the protospacer, and usually leaves blunt ends.")
                else:
                    self.new_round()

    def partial(self):
        return sum(self.scores) / len(self.kinds)

    def autoplay(self):
        self.finish(93, "(autoplay)")

    def render(self, s):
        gfx.bench(s, LAV)
        top = self.kind == "ngg"
        title = "Cas9 at work  ·  round %d of %d  ·  PAM on the %s strand" % (self.r + 1, len(self.kinds), "top" if top else "bottom")
        if self.mine:
            title += "  ·  your guide"
        inner = screen_window(s, (30, TOP + 10, W - 60, 392), title, VIOLET)
        y_t, y_b = TOP + 180, TOP + 216
        px0 = self.x0 + min(self.proto) * self.cw - 16
        px1 = self.x0 + (max(self.proto) + 1) * self.cw + 16
        split = self.click
        sh = min(12, self.anim * 0.5) if split is not None else 0
        # Cas9: a two-lobed protein clamped around the DNA
        cas = cas9_surface(px1 - px0 + 40, 190)
        s.blit(cas, (px0 - 20, y_t - 70))
        draw_text(s, "Cas9", ((px0 + px1) // 2, y_t - 68), 16, (80, 60, 130), center=True, bold=True)
        # backbones
        for row, yy in ((0, y_t - 4), (1, y_b + 32)):
            for half in (0, 1):
                xs = [self.x0 + i * self.cw for i in range(31)]
                if split is not None:
                    seg = [x + (-sh if (x - self.x0) / self.cw < split else sh) for x in xs if (((x - self.x0) / self.cw < split) == (half == 0))]
                else:
                    seg = xs if half == 0 else []
                if len(seg) > 1:
                    aa_polyline(s, (170, 165, 190), [(seg[0] - 2, yy), (seg[-1] - 2, yy)], 3)
        # guide RNA paired along the protospacer
        gy = y_b + 44 if top else y_t - 14
        g0 = self.x0 + min(self.proto) * self.cw
        g1 = self.x0 + (max(self.proto) + 1) * self.cw - 2
        aa_polyline(s, CORAL, [(g0, gy), (g1, gy)], 4)
        tail = [(g1 if top else g0, gy)] + [((g1 if top else g0) + (14 + 6 * math.sin(k)) * (1 if top else -1), gy + 12 * k * (1 if top else -1)) for k in range(1, 5)]
        aa_polyline(s, CORAL, tail, 3)
        draw_text(s, "guide RNA (pairs with the other strand)", ((g0 + g1) // 2, gy + 8 if top else gy - 24), 13, CORAL_D, center=True, bold=True)
        ft, fb = {}, {}
        for i in self.pam:
            (ft if top else fb)[i] = PAM_FILL
        for i in self.proto:
            (ft if top else fb)[i] = (200, 236, 232)
        for i, b in enumerate(self.seq):
            off = (-sh if i < split else sh) if split is not None else 0
            x = self.x0 + i * self.cw + off
            pygame.draw.line(s, (196, 196, 208), (x + self.cw // 2 - 1, y_t + 28), (x + self.cw // 2 - 1, y_b))
            base_tile(s, (x, y_t, self.cw - 3, 28), b, 17, ft.get(i), INK if i in ft else None)
            r = pygame.Rect(x, y_b, self.cw - 3, 28)
            if i in fb:
                base_tile(s, r, comp(b), 16, fb[i], INK)
            else:
                gfx.rrect(s, r, (246, 246, 248), (222, 222, 228), 1, 5, 0.06, False)
                draw_text(s, comp(b), r.center, 16, MUTED, center=True, bold=True, mono=True, vcenter=True)
        gfx.tag(s, self.x0 + (self.pam[1] + 0.5) * self.cw, (y_t - 34) if top else (y_b + 40), "PAM", PAM_FILL, 12, center=True)
        draw_text(s, "5'", (self.x0 - 34, y_t + 5), 15, INK_SOFT, bold=True)
        draw_text(s, "3'", (self.x0 - 34, y_b + 5), 15, MUTED, bold=True)
        if self.gap is not None and self.click is None:
            x = self.x0 + self.gap * self.cw - 2
            for yy in range(y_t - 8, y_b + 36, 8):
                pygame.draw.line(s, CORAL_D, (x, yy), (x, yy + 4), 2)
            scissors(s, (x, y_t - 22))
        if self.click is not None:
            x = self.x0 + self.cut * self.cw - 2
            if self.click != self.cut:
                aa_polyline(s, GREEN, [(x, y_t - 6), (x, y_b + 32)], 3)
                draw_text(s, "real cut", (x, y_t - 46), 13, GREEN, center=True, bold=True)
            else:
                scissors(s, (x, y_t - 22), True)
        if self.level < 2:
            draw_wrapped(s, "Count 3 bases from the PAM into the turquoise protospacer.", (50, TOP + 362), 15, W - 120, INK_SOFT)


_cas = {}


def cas9_surface(w, h):
    """Cas9 drawn like a molecular-surface rendering (as in structure figures): two lobes built
    from many lit atoms-spheres, semi-transparent so the DNA inside stays visible."""
    key = (w, h)
    sp = _cas.get(key)
    if sp is not None:
        return sp
    S = 2
    big = pygame.Surface((w * S, h * S), pygame.SRCALPHA)
    rnd = random.Random(9)
    lobes = [(0.32, 70, 0.3, 62, (186, 166, 226)), (0.66, 112, 0.33, 70, (166, 144, 216))]
    atoms = []
    for cxf, cy, rxf, ry, col in lobes:
        cx, rx = w * cxf, w * rxf
        R.gd.filled_ellipse(big, int(cx * S), int(cy * S), int(rx * 0.86 * S), int(ry * 0.84 * S), tuple(int(c * 0.82) for c in col))
    for cxf, cy, rxf, ry, col in lobes:
        cx, rx = w * cxf, w * rxf
        for _ in range(int(rx * ry / 16)):
            a = rnd.uniform(0, math.tau)
            d = rnd.random() ** 0.6
            x, y = cx + math.cos(a) * rx * d * 0.86, cy + math.sin(a) * ry * d * 0.84
            r = rnd.uniform(8, 13) * (1.1 - 0.35 * d)
            shade = rnd.uniform(-0.06, 0.06)
            atoms.append((y + r * 0.3, x, y, r, tuple(int(max(0, min(255, c * (1 + shade)))) for c in col)))
    for _, x, y, r, col in sorted(atoms):
        R.gd.filled_circle(big, int(x * S), int(y * S), int(r * S), col)
        big.blit(R.sphere_light(int(r * S), 75), (int(x * S - r * S - 1), int(y * S - r * S - 1)))
    sp = pygame.transform.smoothscale(big, (w, h))
    sp.set_alpha(170)
    _cas[key] = sp
    return sp


def scissors(s, c, closed=False):
    x, y = c
    a = 0.18 if closed else 0.5
    for sgn in (-1, 1):
        ex, ey = x + math.sin(a * sgn) * 16, y + math.cos(a * sgn) * 16
        aa_polyline(s, (90, 96, 110), [(x - math.sin(a * sgn) * 10, y - math.cos(a * sgn) * 10), (ex, ey)], 3)
        ring(s, CORAL, (x - math.sin(a * sgn) * 14, y - math.cos(a * sgn) * 14), 5, 2)
    gfx.circle(s, (200, 204, 214), (x, y), 2.5, 1)


def guide_q(rng):
    rows = [("2 of 9, near start", 50, "0", True),
            ("9 of 9 (last)", 55, "0", False),
            ("2 of 9, near start", 20, "0", False),
            ("3 of 9", 50, "3 (one with 1 mismatch)", False)]
    rng.shuffle(rows)
    ans = [k for k, r in enumerate(rows) if r[3]][0]

    def pic(s, r):
        inner = window(s, r, "Guide design  ·  candidate guides", TEAL, 13)
        cols = [inner.x + 6, inner.x + 64, inner.x + 230, inner.x + 296]
        for j, h in enumerate(["Guide", "Position", "GC %", "Off-targets"]):
            draw_text(s, h, (cols[j], inner.y + 6), 14, INK_SOFT, bold=True)
        for k, row in enumerate(rows):
            y = inner.y + 40 + k * 66
            gfx.rrect(s, (inner.x, y - 8, inner.w, 58), (250, 250, 252) if k % 2 else (242, 246, 248), None, 0, 6, 0, False)
            gfx.circle(s, SAND, (cols[0] + 18, y + 18), 15)
            draw_text(s, str(k + 1), (cols[0] + 18, y + 18), 17, INK, center=True, bold=True, vcenter=True)
            draw_wrapped(s, "exon " + row[0], (cols[1], y + 2), 14, 160, INK)
            draw_text(s, "%d" % row[1], (cols[2], y + 8), 16, RED if row[1] < 30 else INK, bold=True, mono=True)
            draw_wrapped(s, row[2], (cols[3], y + 2), 14, inner.right - cols[3], RED if row[2] != "0" else INK)
    return dict(q="You want a knockout. Which guide would you use?", pic=pic, keep_order=True,
                options=["Guide 1", "Guide 2", "Guide 3", "Guide 4"], answer=ans,
                why="Early coding exon, GC near 40-60% and no predicted off-targets. A frameshift in the last exon may leave most of the protein intact and escape mRNA decay.")


GUIDES = [
    guide_q,
    dict(q="Why target an early exon to make a knockout?", options=["A frameshift there truncates most of the protein", "Early exons are easier to sequence", "Cas9 only cuts early exons", "Late exons have no PAMs"],
         answer=0, why="The frameshift usually creates a premature stop codon, and the mRNA is often degraded by nonsense-mediated decay."),
    dict(q="How long is the part of the guide RNA that matches the target?", options=["About 20 bases", "3 bases", "About 200 bases", "The whole gene"],
         answer=0, why="The 20-nt spacer pairs with the target; the rest of the guide is the scaffold that binds Cas9."),
    dict(q="What usually repairs a Cas9 cut in a zebrafish embryo?", options=["Error-prone end joining (NHEJ)", "Perfect homologous recombination", "The guide RNA", "Reverse transcriptase"],
         answer=0, why="End joining often adds or deletes a few bases (indels), which is what disrupts the gene."),
]


def t7e1_pic(s, r):
    inner = window(s, r, "Gel  ·  PCR + T7 endonuclease I", TEAL, 13)
    gel = pygame.Rect(inner.x + 54, inner.y + 30, inner.w - 70, inner.h - 44)
    dark_gel(s, gel, 8)
    lanes = [("Ladder", None), ("uninjected", [(600, 1)]), ("injected", [(600, 0.8), (380, 0.45), (220, 0.45)])]
    ymap = lambda bp: gel.y + 26 + (math.log10(1000) - math.log10(bp)) / (math.log10(1000) - math.log10(100)) * (gel.h - 46)
    for k, (name, bands) in enumerate(lanes):
        cx = gel.x + gel.w * (k + 0.5) / 3
        gfx.rrect(s, (cx - 26, gel.y + 8, 52, 7), (14, 14, 22), None, 0, 2, 0, False)
        draw_text(s, name, (cx, gel.y - 20), 13, INK, center=True, bold=True)
        if bands is None:
            for bp in (1000, 700, 500, 300, 200, 100):
                uv_band(s, cx, ymap(bp), 46, 0.55)
                draw_text(s, str(bp), (gel.x - 6, ymap(bp) - 7), 11, MUTED, right=True)
        else:
            for bp, a in bands:
                uv_band(s, cx, ymap(bp), 52, a)


def hma_pic(s, r):
    inner = window(s, r, "Polyacrylamide gel  ·  same PCR product", TEAL, 13)
    gel = pygame.Rect(inner.x + 40, inner.y + 30, inner.w - 140, inner.h - 44)
    dark_gel(s, gel, 9)
    for k, (name, bands) in enumerate((("wild type", [(0.75, 1)]), ("injected", [(0.75, 0.8), (0.42, 0.5), (0.36, 0.5), (0.3, 0.35)]))):
        cx = gel.x + gel.w * (k + 0.5) / 2
        gfx.rrect(s, (cx - 30, gel.y + 8, 60, 7), (14, 14, 22), None, 0, 2, 0, False)
        draw_text(s, name, (cx, gel.y - 20), 13, INK, center=True, bold=True)
        for f, a in bands:
            uv_band(s, cx, gel.y + gel.h * f, 62, a)
    draw_text(s, "heteroduplexes", (gel.right + 6, gel.y + gel.h * 0.36 - 7), 11, MUTED)
    draw_text(s, "homoduplex", (gel.right + 6, gel.y + gel.h * 0.75 - 7), 11, MUTED)


GENOTYPE = [
    dict(q="Lane 3 shows two extra, smaller bands after T7 endonuclease I. What does it tell you?", pic=t7e1_pic,
         options=["The injected embryos carry indels", "The PCR failed", "The guide did not work", "There is genomic DNA contamination"],
         answer=0, why="Mutant and wild-type strands re-anneal into mismatched heteroduplexes, which T7E1 cuts."),
    dict(q="Heteroduplex mobility assay: why do the extra bands run more slowly?", pic=hma_pic,
         options=["Mismatched strands form bulges that slow DNA in polyacrylamide", "They are longer products", "They carry more dye", "They are single-stranded"],
         answer=0, why="Heteroduplexes of wild-type and indel strands are kinked, so they migrate slower than perfect homoduplexes."),
    dict(q="Trace from one F1 fish: clean until the cut site, then double peaks. Why?", pic=trace_pic("het", 3),
         options=["It is heterozygous for an indel", "It is homozygous wild type", "The sequencing reaction failed", "Cas9 is still cutting"],
         answer=0, why="The two alleles agree up to the indel; after it they are out of step, so each position shows two bases."),
    dict(q="An injected (F0) fish carries several different indels in its fin. What is this called?",
         options=["Mosaicism", "Heterozygosity", "Off-targeting", "Compensation"],
         answer=0, why="Cas9 keeps cutting after the first cell divisions, so different cells get different repairs. Stable lines come from the F1."),
]


TECH = dict(
    key="crispr", name="CRISPR", full="CRISPR-Cas9 genome editing", wing="Genes & genomes", icon="crispr",
    blurb="A guide RNA leads the Cas9 enzyme to one place in the genome, where it cuts both DNA strands. Repair errors then disrupt the gene.",
    facts=[
        "Repeated CRISPR sequences were first noticed in E. coli in 1987. Their role as a bacterial defence against viruses was shown in 2007.",
        "Jennifer Doudna and Emmanuelle Charpentier received the 2020 Nobel Prize in Chemistry for CRISPR-Cas9 genome editing.",
        "Cas9 from Streptococcus pyogenes needs an NGG PAM next to its target. The bacterium's own CRISPR array lacks a PAM, so Cas9 does not cut it.",
        "Cas9 cuts 3 bases upstream of the PAM and usually leaves blunt ends.",
        "In 2013 zebrafish were among the first animals edited with CRISPR-Cas9.",
        "Many zebrafish labs inject Cas9 protein and guide RNA together, as a ribonucleoprotein, into the one-cell embryo.",
        "When a mutant mRNA is degraded, related genes can be switched on to compensate. This transcriptional adaptation can hide a mutant's phenotype.",
    ],
    quiz=[
        dict(q="What does the PAM do?", options=["Lets Cas9 recognise a valid target next to the guide match", "Is cut by Cas9", "Carries the fluorescent label", "Ends the guide RNA"],
             answer=0, why="Cas9 first binds a PAM, then checks whether the neighbouring DNA matches the guide."),
        dict(q="Which strand can a guide target?", options=["Either strand, if there is a PAM on that strand", "Only the top strand", "Only the coding strand", "Only RNA"],
             answer=0, why="A CCN on the top strand is an NGG on the bottom strand."),
        dict(q="Why are F0 injected fish usually outcrossed before analysis?", options=["They are mosaic; the F1 carry single defined alleles", "They are always sterile", "Cas9 is toxic", "To remove the guide RNA"],
             answer=0, why="Different cells of an F0 fish carry different indels; each F1 fish inherits one allele."),
    ],
    music=dict(name="Guide RNA Groove", bpm=106, beats=4, root=48, mode="mix", prog=[0, 6, 3, 0, 0, 6, 4, 3],
               lead="brass", comp="stab", drums="funk", swing=0.08,
               motif=[(0, 2), (0, 1), (2, 1), (4, 1), (6, 1), (7, 2), (6, 1), (4, 1), (2, 2), (0, 4)]),
    stages=[
        ("crispr_pam", dict()),
        ("quiz", dict(title="Choose a guide", instr="Pick the guide RNA that will give a clean knockout.", questions=GUIDES, n=3, tint=SKY)),
        ("crispr_cut", dict()),
        ("quiz", dict(title="Did it work?", instr="Genotyping results from injected embryos and their offspring. What do they show?", questions=GENOTYPE, n=3, tint=LAV)),
    ],
)
TECHS = [TECH]
