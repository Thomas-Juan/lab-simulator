# -*- coding: utf-8 -*-
"""qPCR: set the threshold, read amplification and melt curves, compute fold change by 2^-ddCt."""
import math
import random
import pygame
import audio
import gfx
import render as R
from render import lighten
from stage import Stage, register, TOP, BOTTOM
from genes_common import plot_box, aa_polyline, window, desktop
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, CORAL, CORAL_D, TURQ, TEAL, LAV, VIOLET, SKY, WHITE,
                  GREEN, RED, YELLOW, BLUE, draw_text, draw_wrapped, mix, clamp)

CURVE_COLS = [CORAL, TURQ, VIOLET, (214, 150, 60), BLUE, GREEN]


def logistic(c, ch, fmax, s=1.0 / math.log(2)):
    return fmax / (1 + math.exp(-(c - ch) / s))


def plot_axes(s, P, ylab="dRn (log)", xlab="Cycle", log=True):
    yt = [(P.bottom - (d + 3) / 4.0 * P.h, ["0.001", "0.01", "0.1", "1", "10"][d + 3]) for d in range(-3, 2)]
    xt = [(P.x + c / 40.0 * P.w, str(c)) for c in range(0, 41, 10)]
    plot_box(s, P, xt, yt, xlab, ylab)


def ymap(P, v):
    return P.bottom - (math.log10(max(v, 1e-3)) + 3) / 4.0 * P.h


def xmap(P, c):
    return P.x + c / 40.0 * P.w


@register("qpcr_threshold")
class Threshold(Stage):
    title = "Set the threshold"
    instr = ("Move the mouse to place the threshold line, then click. Put it above the baseline noise "
             "and in the straight (exponential) part of every curve. Then check the wells: click the one "
             "with a problem, or 'All wells fine'.")
    limit = 90

    def setup(self):
        self.rounds = self.p.get("rounds", self.lv(2, 2, 3))
        self.r = 0
        self.scores = []
        self.msgs = []
        self.flags_ok = 0
        kinds = ["ntc", "failed"] + (["none"] if self.level > 0 else [])
        self.rng.shuffle(kinds)
        self.anoms = (kinds * 2)[:self.rounds]
        self.new_plot()

    def new_plot(self):
        rng = self.rng
        n = self.lv(4, 5, 6)
        lo_n, hi_n = self.lv((0.002, 0.005), (0.003, 0.007), (0.006, 0.011))
        self.noise_lvl = rng.uniform(lo_n, hi_n)
        self.anom = self.anoms[self.r]
        self.curves = []
        chs = sorted(rng.sample(range(17, 32), n))
        failed = rng.randrange(n) if self.anom == "failed" else None
        for k in range(n):
            ch, fm = chs[k] + rng.uniform(0, 0.9), rng.uniform(1.3, 3.0)
            if k == failed:
                fm = 0
            vals = [(logistic(c, ch, fm) if fm else 0) + abs(rng.gauss(0, self.noise_lvl)) + self.noise_lvl * 0.2 for c in range(1, 41)]
            self.curves.append(("Sample %d" % (k + 1), CURVE_COLS[k], vals, fm))
        if self.anom == "ntc":
            nch = rng.uniform(36.0, 37.5)
            ntc = [logistic(c, nch, 0.5) + abs(rng.gauss(0, self.noise_lvl)) + self.noise_lvl * 0.2 for c in range(1, 41)]
        else:
            ntc = [abs(rng.gauss(0, self.noise_lvl)) + self.noise_lvl * 0.2 for c in range(1, 41)]
        self.curves.append(("NTC", (150, 150, 150), ntc, 0))
        self.bad = {"ntc": len(self.curves) - 1, "failed": failed, "none": None}[self.anom]
        self.lo = max(max(v for v in c[2][:10]) for c in self.curves)
        self.lo *= 1.15
        self.hi = 0.08 * min(c[3] for c in self.curves[:-1] if c[3] > 0)   # still near-exponential (> 1.8-fold per cycle)
        self.thr = min(5.0, self.hi * 6)   # starts in the plateau: the player has to place it
        self.state = "aim"
        self.wait = 0
        self.flag = "pending"
        self.r_score = 0

    def ct(self, vals, thr):
        for i in range(1, len(vals)):
            if vals[i - 1] < thr <= vals[i]:
                a, b = math.log10(vals[i - 1]), math.log10(vals[i])
                return i + (math.log10(thr) - a) / (b - a)
        return None

    def P(self):
        return pygame.Rect(86, TOP + 72, 526, 330)

    def panel(self):
        L = pygame.Rect(676, TOP + 6, 262, 438)
        return L, pygame.Rect(L.x + 10, L.y + 41, L.w - 20, L.h - 51)

    def row_rect(self, k):
        _, inner = self.panel()
        return pygame.Rect(inner.x, inner.y + 88 + k * 30, inner.w, 28)

    def fine_btn(self):
        _, inner = self.panel()
        return gfx.Button((inner.x + 20, inner.y + 96 + len(self.curves) * 30, inner.w - 40, 34), "All wells fine", (206, 236, 210), size=15)

    def tick(self, inp):
        self._mouse = inp.mouse
        P = self.P()
        if self.state == "aim":
            if P.collidepoint(inp.mouse) and (inp.moved or inp.click):
                d = (P.bottom - inp.mouse[1]) / P.h * 4 - 3
                self.thr = 10 ** clamp(d, -2.95, 0.95)
            if "up" in inp.pressed:
                self.thr *= 1.12
            if "down" in inp.pressed:
                self.thr /= 1.12
            if (inp.click and P.collidepoint(inp.mouse)) or pygame.K_RETURN in inp.keys:
                self.set_line()
        elif self.state == "flag":
            pick = None
            if inp.click:
                for k in range(len(self.curves)):
                    if self.row_rect(k).collidepoint(inp.mouse):
                        pick = k
                if self.fine_btn().rect.collidepoint(inp.mouse):
                    pick = -1
            if pick is not None:
                self.judge_flag(pick)
        else:
            self.wait -= 1
            if self.wait <= 0 or (self.wait < 150 and inp.click):
                self.r += 1
                if self.r >= self.rounds:
                    self.r -= 1
                    fb = ["Threshold rounds: " + ", ".join("%d" % sc for sc in self.scores) + ".  Problem wells spotted: %d of %d." % (self.flags_ok, self.rounds)]
                    self.finish(sum(self.scores) / len(self.scores), *(fb + list(dict.fromkeys(self.msgs))[:2]))
                    self.wait = 10 ** 6
                else:
                    self.new_plot()

    def set_line(self):
        ly, llo, lhi = math.log10(self.thr), math.log10(self.lo), math.log10(self.hi)
        mid, half = (llo + lhi) / 2, (lhi - llo) / 2
        y = ymap(self.P(), self.thr) - 20
        if llo <= ly <= lhi:
            sc = 100 - self.lv(30, 40, 55) * ((ly - mid) / half) ** 2
            self.msgs.append("Inside the exponential phase: the Cts are reliable.")
            audio.sfx("good")
            self.particles.burst(xmap(self.P(), 30), ymap(self.P(), self.thr), 18)
            self.floaters.add(350, y, "Good threshold", GREEN, 22)
        elif ly < llo:
            sc = max(0, 35 - 70 * (llo - ly))
            self.msgs.append("Too low: baseline noise crosses the line and gives false early Cts.")
            audio.sfx("bad")
            self.shake = 10
            self.floaters.add(350, y, "In the noise", RED, 22)
        else:
            sc = max(0, 35 - 70 * (ly - lhi))
            self.msgs.append("Too high: the curves are bending into the plateau, where Ct is imprecise.")
            audio.sfx("bad")
            self.shake = 10
            self.floaters.add(350, y, "Near the plateau", RED, 22)
        self.r_score = sc
        self.state = "flag"

    def judge_flag(self, pick):
        ok = (pick == -1 and self.bad is None) or (pick == self.bad)
        explain = {"ntc": "The NTC amplified very late: primer dimer (check the melt curve) or a trace of contamination.",
                   "failed": "One sample never rose: a failed reaction, often a pipetting slip or missing template.",
                   "none": "Every sample rose and the NTC stayed flat: the plate is fine."}[self.anom]
        self.msgs.append(explain)
        if ok:
            self.flags_ok += 1
            audio.sfx("ding")
            self.floaters.add(806, TOP + 60, "Well spotted", GREEN, 20)
        else:
            audio.sfx("bad")
            self.shake = 8
            self.floaters.add(806, TOP + 60, "Not that one", RED, 20)
        self.flag = "ok" if ok else "wrong"
        self.scores.append(0.75 * self.r_score + (25 if ok else 0))
        self.state = "shown"
        self.wait = 300

    def partial(self):
        return sum(self.scores) / max(1, self.rounds)

    def autoplay(self):
        self.finish(90, "(autoplay)")

    def render(self, s):
        gfx.bench(s, SKY)
        P = self.P()
        desktop(s, (4, TOP - 2, W - 8, 456))
        window(s, (P.x - 76, TOP + 6, P.w + 104, P.h + 112), "Amplification plot  ·  SYBR Green" + ("   ·   plate %d of %d" % (self.r + 1, self.rounds)), TEAL)
        plot_axes(s, P)
        if self.state != "aim":
            yl, yh = ymap(P, self.lo), ymap(P, self.hi)
            gfx.alpha_rect(s, (P.x + 2, yl, P.w - 4, P.bottom - yl - 2), (150, 150, 160), 55)
            gfx.alpha_rect(s, (P.x + 2, yh, P.w - 4, yl - yh), GREEN, 50)
            draw_text(s, "baseline noise", (P.right - 8, P.bottom - 20), 13, MUTED, right=True, bold=True)
            draw_text(s, "exponential phase", (P.right - 8, yh + 4), 13, (40, 120, 50), right=True, bold=True)
        clip = s.get_clip()
        s.set_clip(P.inflate(-2, -2))
        for k, (name, col, vals, _) in enumerate(self.curves):
            pts = [(xmap(P, c + 1), ymap(P, v)) for c, v in enumerate(vals)]
            hl = self.state == "flag" and self.row_rect(k).collidepoint(getattr(self, "_mouse", (0, 0)))
            aa_polyline(s, col, pts, 4 if hl else (2.5 if name != "NTC" else 2))
        y = ymap(P, self.thr)
        tcol = CORAL_D if self.state == "aim" else INK
        aa_polyline(s, tcol, [(P.x, y), (P.right, y)], 3)
        s.set_clip(clip)
        gfx.rrect(s, (P.right + 4, y - 11, 20, 22), tcol, lighten(tcol, -0.4), 1, 4, 0.2)
        for k in (-4, 0, 4):
            pygame.draw.line(s, WHITE, (P.right + 9, y + k), (P.right + 18, y + k), 1)
        draw_text(s, "threshold", (P.x + 8, y - 19), 13, tcol, bold=True)
        L, inner = self.panel()
        window(s, L, "Wells", VIOLET)
        plate = pygame.Rect(inner.x + 6, inner.y + 2, inner.w - 12, 50)
        gfx.plastic_rect(s, plate, (236, 238, 244), 6, 0.3)
        for k in range(12):
            for j in range(2):
                c = (plate.x + 14 + k * ((plate.w - 28) / 11.0), plate.y + 15 + j * 20)
                idx = k if j == 0 and k < len(self.curves) else None
                col = self.curves[idx][1] if idx is not None else (214, 216, 224)
                gfx.circle(s, col, c, 7, 1, mix(col, INK, 0.5))
        head = "Which well has a problem?" if self.state == "flag" else "Ct at this threshold"
        draw_text(s, head, (inner.x + 4, inner.y + 62), 15, CORAL_D if self.state == "flag" else INK, bold=True)
        for k, (name, col, vals, _) in enumerate(self.curves):
            rr = self.row_rect(k)
            if self.state == "flag" and rr.collidepoint(getattr(self, "_mouse", (0, 0))):
                gfx.rrect(s, rr, (252, 240, 214), CORAL, 1, 5, 0, False)
            if self.state == "shown" and k == self.bad:
                gfx.rrect(s, rr, (250, 220, 210), RED, 1, 5, 0, False)
            yy = rr.y + 4
            aa_polyline(s, col, [(inner.x + 6, yy + 10), (inner.x + 32, yy + 10)], 4)
            draw_text(s, name, (inner.x + 42, yy + 1), 15, INK)
            c = self.ct(vals, self.thr)
            txt = "%.1f" % c if c is not None else "-"
            bad = name == "NTC" and c is not None
            draw_text(s, txt, (inner.right - 8, yy + 1), 15, RED if bad else INK, right=True, bold=True, mono=True)
            if self.state != "aim" and c is not None:
                gfx.circle(s, col, (xmap(P, c), y), 5, 2)
        if self.state == "flag":
            self.fine_btn().draw(s)
        elif self.state == "shown":
            msg = self.msgs[-1]
            draw_wrapped(s, msg, (inner.x + 4, inner.y + 96 + len(self.curves) * 30), 13, inner.w - 8, GREEN if self.flag == "ok" else CORAL_D, bold=True)
        if self.state != "shown":
            draw_wrapped(s, "NTC = no-template control. It should not cross the threshold, or only very late from primer dimer.",
                         (inner.x + 4, inner.bottom - 40), 13, inner.w - 8, INK_SOFT)


def melt_pic(kinds):
    def pic(s, r):
        inner = window(s, r, "Melt curve  ·  SYBR Green", TEAL, 13)
        n = len(kinds)
        hgt = inner.h // n
        for k, (label, peaks) in enumerate(kinds):
            P = pygame.Rect(inner.x + 40, inner.y + 22 + k * hgt, inner.w - 50, hgt - 50)
            xt = [(P.x + (T - 65) / 30.0 * P.w, "%d deg C" % T) for T in (70, 80, 90)]
            plot_box(s, P, xt, [], "", "")
            col = CORAL if k == 0 else TURQ
            pts = []
            for i in range(0, P.w, 2):
                T = 65 + 30.0 * i / P.w
                v = sum(h * math.exp(-((T - m) / w) ** 2) for m, h, w in peaks)
                pts.append((P.x + i, P.bottom - 4 - v * (P.h - 14)))
            R.gd.filled_polygon(s, [(P.x, P.bottom - 2)] + pts + [(pts[-1][0], P.bottom - 2)], col + (40,))
            aa_polyline(s, col, pts, 2.5)
            draw_text(s, label, (P.x + 8, P.y + 6), 15, INK, bold=True)
            draw_text(s, "-dF/dT", (P.x - 6, P.y - 16), 11, MUTED)
    return pic


def amp_pic(cts):
    def pic(s, r):
        inner = window(s, r, "Amplification plot", TEAL, 13)
        P = pygame.Rect(inner.x + 44, inner.y + 26, inner.w - 54, inner.h - 70)
        plot_axes(s, P)
        for k, (name, ch) in enumerate(cts):
            col = [CORAL, TURQ, VIOLET][k]
            pts = [(xmap(P, c / 2.0), ymap(P, logistic(c / 2.0, ch, 2.0) + 0.004)) for c in range(2, 81)]
            aa_polyline(s, col, pts, 2.5)
            ct = ch - math.log2(19)
            gfx.circle(s, col, (xmap(P, ct), ymap(P, 0.1)), 6)
            gfx.tag(s, P.x + 10, P.y + 8 + k * 26, "%s: Ct %.0f" % (name, ct), mix(col, WHITE, 0.7), 13)
        aa_polyline(s, INK, [(P.x, ymap(P, 0.1)), (P.right, ymap(P, 0.1))], 2)
        draw_text(s, "threshold", (P.right - 6, ymap(P, 0.1) - 17), 12, INK_SOFT, right=True, bold=True)
    return pic


def q_fold(rng):
    a = rng.randint(17, 22)
    d = rng.choice([1, 2, 3, 4])
    lg = math.log2(19)
    return dict(q="Same gene, same efficiency (100%). How much more starting template is in X than in Y?",
                pic=amp_pic([("X", a + lg), ("Y", a + d + lg)]),
                options=["%d times" % 2 ** d, "%d times" % d, "%d times" % (2 ** d * 2), "The same amount"], answer=0,
                why="Each cycle doubles the product, so %d cycles earlier means 2^%d = %d times more template." % (d, d, 2 ** d))


READ = [
    q_fold,
    dict(q="SYBR Green melt curves of two wells. Which well contains only the specific product?",
         pic=melt_pic([("Well A", [(84, 1.0, 1.3)]), ("Well B", [(84, 0.8, 1.3), (75, 0.45, 1.8)])]),
         options=["Well A", "Well B", "Both", "Neither"], answer=0,
         why="One sharp peak means one product. The extra low-temperature peak in B is short primer dimer, which also binds SYBR Green."),
    dict(q="The no-template control gives a Ct of 36 and this melt curve. What is it?",
         pic=melt_pic([("NTC", [(75, 0.6, 1.9)]), ("Sample", [(84, 1.0, 1.3)])]),
         options=["Primer dimer", "Contamination with the target", "Genomic DNA", "A pipetting error in the sample"], answer=0,
         why="Its melting temperature is far below the real product, so it is primer dimer, not your amplicon."),
    dict(q="Why do we divide by a reference gene such as actb1 or eef1a1l1?",
         options=["To correct for different amounts of RNA and cDNA in each sample", "To make the Ct values smaller", "Because SYBR Green needs it", "To remove primer dimers"],
         answer=0, why="The reference gene should not change between conditions, so it reports how much material went in."),
    dict(q="Why must the threshold be in the exponential phase?",
         options=["There the product doubles every cycle, so Ct reflects the starting amount", "Fluorescence is highest there", "The plateau is too noisy to see", "It is a rule with no reason"],
         answer=0, why="In the plateau, reagents run out and curves converge, so they no longer reflect how much template you started with."),
]


def ddct(rng):
    rc = round(rng.uniform(16.5, 19.5), 1)
    tc = round(rc + rng.uniform(5, 9), 1)
    rt = round(rc + rng.uniform(-0.6, 0.6), 1)
    shift = rng.choice([-3.0, -2.0, -1.5, 1.0, 2.0, 2.5])
    tt = round(tc + (rt - rc) + shift + rng.uniform(-0.2, 0.2), 1)
    dd = (tt - rt) - (tc - rc)
    ans = 2 ** (-dd)

    def pic(s, r):
        T = pygame.Rect(r.x, r.y, r.w, 104)
        gfx.rrect(s, T, WHITE, (150, 154, 160), 1, 3, 0, False)
        gfx.header(s, T, TEAL, 28, 8)
        cols = [T.x + 14, T.x + 200, T.x + 350]
        for j, h in enumerate(["Sample", "Gene X  Ct", "Reference  Ct"]):
            draw_text(s, h, (cols[j], T.y + 16), 14, WHITE, bold=True, vcenter=True)
        for i, (name, a, b) in enumerate((("Control", tc, rc), ("Treated", tt, rt))):
            y = T.y + 44 + i * 30
            if i:
                pygame.draw.line(s, (226, 226, 232), (T.x + 8, y - 6), (T.right - 8, y - 6))
            draw_text(s, name, (cols[0], y), 17, INK, bold=True)
            draw_text(s, "%.1f" % a, (cols[1] + 20, y), 17, CORAL_D, bold=True, mono=True)
            draw_text(s, "%.1f" % b, (cols[2] + 30, y), 17, TEAL, bold=True, mono=True)
        draw_text(s, "fold change = 2^-ddCt", (r.x + 10, r.y + 120), 15, INK_SOFT, mono=True)
        draw_text(s, "ddCt = (X - ref)treated - (X - ref)control", (r.x + 10, r.y + 142), 15, INK_SOFT, mono=True)
    return dict(text="Fold change of gene X in treated compared with control fish (assume 100% efficiency)?", answer=ans,
                unit="fold (1 = no change)", tol=0.06, pic=pic, show="%.2f" % ans,
                why="dCt control = %.1f, dCt treated = %.1f, so ddCt = %.1f and 2^-ddCt = %.2f. Below 1 means less expression." % (tc - rc, tt - rt, dd, ans))


def dilution(rng):
    f = rng.choice([10, 4, 8])
    a = math.log2(f)
    return dict(text="You dilute a cDNA %d-fold. At 100%% efficiency, by how many cycles does the Ct shift?" % f, answer=a, unit="cycles", tol=0.03,
                show="%.2f" % a, why="Each cycle doubles the product, so the shift is log2(%d) = %.2f cycles. A 10-fold dilution should shift Ct by 3.32." % (f, a))


TECH = dict(
    key="qpcr", name="qPCR", full="Quantitative real-time PCR", wing="Genes & genomes", icon="qpcr",
    blurb="Measures how much of a DNA or cDNA sequence is in a sample by watching fluorescence rise during PCR, cycle by cycle.",
    facts=[
        "SYBR Green fluoresces strongly only when bound to double-stranded DNA, so the signal rises as the product builds up.",
        "At 100% efficiency the product doubles every cycle, so a difference of 3.3 cycles is a 10-fold difference in template.",
        "The cycle at which a curve crosses the threshold is called Ct, or Cq in the MIQE guidelines.",
        "TaqMan probes are cut by the 5' to 3' exonuclease activity of Taq polymerase, which frees the reporter dye from its quencher.",
        "Livak and Schmittgen described the 2^-ddCt method in 2001; it is one of the most cited methods papers.",
        "The MIQE guidelines, published in 2009, list what a qPCR study should report so others can judge and repeat it.",
        "Reverse transcriptase, which turns RNA into cDNA for RT-qPCR, was discovered in 1970 by Howard Temin and David Baltimore.",
    ],
    quiz=[
        dict(q="Sample A has Ct 22 and sample B Ct 25 for the same gene. Which had more template?", options=["A, about 8 times more", "B, about 8 times more", "A, 3 times more", "They are equal"],
             answer=0, why="Lower Ct means the threshold was reached earlier: 2^3 = 8 times more."),
        dict(q="What does a melt curve check?", options=["That only one product was amplified", "The efficiency", "The RNA quality", "The threshold"],
             answer=0, why="Each product melts at its own temperature; extra peaks mean extra products."),
        dict(q="Why include a no-RT control in RT-qPCR?", options=["To detect amplification from genomic DNA", "To measure primer dimers only", "To set the threshold", "To normalise the data"],
             answer=0, why="Without reverse transcriptase there is no cDNA, so any signal comes from contaminating DNA."),
    ],
    music=dict(name="Threshold Trance", bpm=126, beats=4, root=50, mode="min", prog=[0, 0, 5, 5, 3, 3, 4, 4],
               lead="synth", comp="arp", drums="techno",
               motif=[(0, 1), (0, 1), (7, 2), (5, 1), (4, 1), (2, 2), (0, 1), (0, 1), (7, 2), (9, 2), (7, 2)]),
    stages=[
        ("qpcr_threshold", dict()),
        ("quiz", dict(title="Read the curves", instr="Amplification and melt curves: what do they say?", questions=READ, n=3, tint=SKY)),
        ("calc", dict(title="Fold change", instr="Work out relative expression with the 2^-ddCt method. Type the number and press Enter.",
                      problems=[ddct, ddct, dilution], n=2)),
    ],
)
TECHS = [TECH]
