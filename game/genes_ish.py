# -*- coding: utf-8 -*-
"""Whole-mount in situ hybridisation on zebrafish embryos."""
import math
import random
import pygame
import audio
import gfx
import render as R
from stage import Stage, register, TOP, BOTTOM
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, TURQ, TEAL, LAV, VIOLET, SKY,
                  WHITE, GREEN, RED, YELLOW, draw_text, draw_wrapped, mix, clamp)
from genes_common import embryo, window, aa_polyline, scope_field, brightfield

PROBE = (120, 70, 170)


_dish = {}


def dish(s, c, r, medium=(226, 238, 242)):
    """Glass dish of buffer seen from above (cached)."""
    key = (r, medium)
    sp = _dish.get(key)
    if sp is None:
        n = 2 * r + 30
        sp = pygame.Surface((n, n), pygame.SRCALPHA)
        cc = (n // 2, n // 2)
        R.aa_circle(sp, (246, 250, 253), cc, r + 11, 2, INK, False)
        R.aa_circle(sp, (232, 240, 246), cc, r + 3, 1, mix(INK, WHITE, 0.6), False)
        tx = gfx.texture(2 * r, 2 * r, medium, 40, 4, 61, 2)
        disc = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        disc.blit(tx, (0, 0))
        m = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        R.gd.filled_circle(m, r, r, r - 1, (255, 255, 255, 255))
        R.gd.aacircle(m, r, r, r - 1, (255, 255, 255, 255))
        disc.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        sp.blit(disc, (cc[0] - r, cc[1] - r))
        pygame.draw.arc(sp, WHITE, (cc[0] - r - 7, cc[1] - r - 7, 2 * r + 14, 2 * r + 14), 2.0, 2.9, 4)
        pygame.draw.arc(sp, WHITE, (cc[0] - r - 7, cc[1] - r - 7, 2 * r + 14, 2 * r + 14), 5.1, 5.5, 3)
        hl = pygame.Surface((n, n), pygame.SRCALPHA)
        pygame.draw.ellipse(hl, (255, 255, 255, 34), (cc[0] - r * 0.7, cc[1] - r * 0.85, r * 0.9, r * 0.5))
        sp.blit(hl, (0, 0))
        _dish[key] = sp
    s.blit(sp, (c[0] - sp.get_width() // 2, c[1] - sp.get_height() // 2))


def probe(s, x, y, t):
    """A DIG-labelled RNA probe: a short purple squiggle with a DIG tag."""
    pts = [(x - 7 + i * 2, y + math.sin(i * 1.3 + t) * 2.2) for i in range(8)]
    aa_polyline(s, PROBE, pts, 2)
    gfx.circle(s, YELLOW, (x + 8, y + math.sin(9.1 + t) * 2.2), 2.6, 1, mix(YELLOW, INK, 0.5), False)


def side_panel(s, title, lines):
    inner = window(s, (636, TOP + 92, 298, 312), title, VIOLET)
    y = inner.y + 2
    for txt, size, col, bold in lines:
        if txt is None:
            y += size
            continue
        y = draw_wrapped(s, txt, (inner.x + 6, y), size, inner.w - 12, col, bold=bold) + 6
    return inner, y


def protk_scene(st, s, v):
    gfx.bench(s, LAV)
    c = (330, TOP + 236)
    scope_field(s, c, 206)
    mins = v * 16
    L = 360
    rnd = random.Random(7)
    tmp = pygame.Surface((int(L * 1.12), int(L * 0.5)), pygame.SRCALPHA)
    embryo(tmp, (tmp.get_width() // 2, int(tmp.get_height() * 0.42)), L, 24)
    frag = clamp((v - 0.82) / 0.18, 0, 1)
    ox, oy = c[0] - tmp.get_width() // 2, c[1] - tmp.get_height() // 2
    if frag <= 0:
        s.blit(tmp, (ox, oy))
    else:
        cut = int(tmp.get_width() * 0.58)
        left = tmp.subsurface((0, 0, cut, tmp.get_height()))
        right = pygame.transform.rotozoom(tmp.subsurface((cut, 0, tmp.get_width() - cut, tmp.get_height())), -18 * frag, 1.0)
        s.blit(left, (ox - 14 * frag, oy))
        s.blit(right, (ox + cut + 26 * frag, oy + 10 * frag))
        for i in range(int(18 * frag)):
            gfx.circle(s, (240, 226, 190), (c[0] + rnd.randint(-120, 160), c[1] + rnd.randint(-50, 70)), rnd.randint(2, 5), 1, mix(INK, WHITE, 0.5), False)
    # the skin becomes porous
    pores = clamp(v / 0.62, 0, 1)
    for i in range(int(40 * pores)):
        t = 0.2 + rnd.random() * 0.7
        x = ox + L * (0.04 + t)
        y = c[1] - 0.05 * L + rnd.choice((-1, 1)) * L * (0.055 - 0.035 * t) + 0.4 * L * 0.0
        gfx.alpha_circle(s, WHITE, (x, y), 2, 190)
    # probes: outside first, inside once the tissue is permeable
    inside = clamp((v - 0.25) / 0.4, 0, 1)
    for i in range(40):
        a = i * 2.39 + st.t * 0.01
        if i / 40.0 < inside:
            x = ox + L * (0.12 + (i * 37 % 100) / 100.0 * 0.78)
            y = c[1] - 0.05 * L + math.sin(i * 1.7) * L * 0.03 - 0.05 * L * 0
        else:
            rr = 160 + 30 * math.sin(i * 0.7 + st.t * 0.02)
            x, y = c[0] + math.cos(a) * rr, c[1] + math.sin(a) * rr * 0.8
        probe(s, x, y, st.t * 0.05 + i)
    lines = [("Proteinase K, 10 ug/mL, room temperature", 14, INK_SOFT, False),
             ("Digest only until the probe can get in. Too long and the embryo falls apart. The right time depends on the embryo's age.", 14, INK_SOFT, False)]
    inner, y = side_panel(s, "24 hpf embryo", lines)
    probe(s, inner.x + 16, y + 10, st.t * 0.05)
    draw_text(s, "DIG-labelled RNA probe", (inner.x + 36, y + 2), 14, INK)
    if st.state != "run":
        draw_text(s, "Best: about 10 min", (inner.x + 6, y + 36), 16, GREEN, bold=True)
        draw_text(s, "You: %.1f min" % mins, (inner.x + 6, y + 62), 16, INK, bold=True)


GENES = [("myl7", 48, "heart", "heart muscle"), ("kdrl", 24, "vessels", "blood vessels")]
STRENGTH = [("strong", 0.15), ("medium", 0.22), ("weak", 0.32)]


@register("ish_stain")
class StainStage(Stage):
    """Watch the NBT/BCIP colour develop in the antisense embryo and in a sense-probe control;
    stop when the pattern is strong and the control is still clean."""
    title = "Watch the colour"
    instr = ("The purple stain develops over hours. Top: antisense probe (the real pattern). Bottom: sense probe "
             "(should stay clean). Click or press Space when the pattern is strong and the control still pale.")

    def setup(self):
        rng = self.rng
        n = self.p.get("rounds", self.lv(2, 2, 3))
        genes = GENES[:]
        rng.shuffle(genes)
        self.plan = []
        for k in range(n):
            g = genes[k % len(genes)]
            st = rng.choice(STRENGTH[:2]) if self.level == 0 else rng.choice(STRENGTH)
            self.plan.append((g, st))
        self.r = 0
        self.scores = []
        self.notes = []
        self.dur = self.lv(10.0, 9.0, 7.5)
        self.b0 = self.lv(0.56, 0.5, 0.42)
        self.start_round()

    def start_round(self):
        (self.gene, self.hpf, self.kind, self.what), (self.sname, self.tau) = self.plan[self.r]
        self.v = 0.0
        self.state = "run"
        self.wait = 0
        self.b0r = clamp(self.b0 + self.rng.uniform(-0.09, 0.09), 0.3, 0.7)
        grid = [i / 200.0 for i in range(201)]
        self.best_v = max(grid, key=self.quality)
        self.q_best = self.quality(self.best_v)

    def sig(self, v):
        return 1 - math.exp(-v / self.tau)

    def bg(self, v):
        return clamp((v - self.b0r) / (1 - self.b0r), 0, 1) ** 1.4

    def quality(self, v):
        return self.sig(v) - 1.25 * self.bg(v)

    def hours(self, v):
        m = int(v * 300)
        return "%d:%02d h" % (m // 60, m % 60)

    def tick(self, inp):
        if self.state == "run":
            self.v += 1.0 / (60 * self.dur)
            if inp.click or "space" in inp.pressed or pygame.K_RETURN in inp.keys:
                q = self.quality(self.v)
                sc = clamp(100 - self.lv(120, 150, 200) * (1 - q / self.q_best), 0, 100) if q > 0 else 0
                self.end_round(sc)
            elif self.v >= 1.0:
                self.v = 1.0
                self.end_round(0, over=True)
        else:
            self.wait -= 1
            if self.wait <= 0 or (self.wait < 120 and inp.click):
                self.r += 1
                if self.r >= len(self.plan):
                    self.r -= 1
                    self.wait = 10 ** 6
                    fb = ["Stops: " + ", ".join(self.notes) + "."]
                    fb.append("Weakly expressed genes need longer, so background has more time to rise. The sense control shows how much of the colour is background.")
                    self.finish(sum(self.scores) / len(self.scores), *fb)
                else:
                    self.start_round()

    def end_round(self, sc, over=False):
        self.scores.append(sc)
        self.state = "over" if over else "stopped"
        self.wait = 220
        self.notes.append("%s %s (best about %s)" % (self.gene, self.hours(self.v), self.hours(self.best_v)))
        if over:
            audio.sfx("buzz")
            self.shake = 16
            self.floaters.add(330, TOP + 40, "Overstained!", RED, 26)
            self.msg = "Overstained: both embryos are purple and the pattern is lost."
        elif self.v < self.best_v and sc < 85:
            audio.sfx("bad")
            self.floaters.add(330, TOP + 40, "Too early", CORAL_D, 26)
            self.msg = "Stopped early: the pattern is still faint."
        elif sc < 85:
            audio.sfx("bad")
            self.shake = 8
            self.floaters.add(330, TOP + 40, "Too late", CORAL_D, 26)
            self.msg = "Too late: the sense control is turning purple, so background is up."
        else:
            audio.sfx("good")
            self.particles.burst(330, TOP + 120, 24)
            self.floaters.add(330, TOP + 40, "Perfect stain" if sc >= 95 else "Good stain", GREEN, 26)
            self.msg = "Strong pattern on a clean background."

    def partial(self):
        return sum(self.scores) / max(1, len(self.plan))

    def autoplay(self):
        self.finish(88, "(autoplay)")

    def draw_embryo(self, s, c, L, sig, bg):
        if self.kind == "heart":
            embryo(s, c, L, 48, heart=sig, bg=bg, pigment=False)
        else:
            embryo(s, c, L, 24, vessels=sig, bg=bg)

    def render(self, s):
        gfx.bench(s, LAV)
        c = (330, TOP + 236)
        scope_field(s, c, 206)
        v = self.v
        sig, bg = self.sig(v), self.bg(v)
        self.draw_embryo(s, (c[0] + 6, c[1] - 74), 300, sig, bg)
        self.draw_embryo(s, (c[0] + 6, c[1] + 92), 300, 0.0, bg * 1.05)
        for txt, y in (("antisense", c[1] - 150), ("sense control", c[1] + 18)):
            gfx.tag(s, c[0] - 150, y, txt, (250, 250, 246), 12)
        lines = [("NBT/BCIP staining  ·  %d hpf" % self.hpf, 14, INK_SOFT, True),
                 ("%s marks %s. Expression: %s." % (self.gene, self.what, self.sname), 14, INK_SOFT, False)]
        if self.hpf == 48:
            lines.append(("Raised in PTU: no pigment.", 13, MUTED, False))
        inner, y = side_panel(s, "%s probe  ·  embryo %d of %d" % (self.gene, self.r + 1, len(self.plan)), lines)
        box = pygame.Rect(inner.right - 120, inner.y - 40 - 52, 120, 40)
        gfx.screen_rect(s, box, (30, 38, 34))
        draw_text(s, self.hours(v), box.center, 20, (140, 255, 170), center=True, bold=True, mono=True, vcenter=True)
        if self.level == 0:
            draw_text(s, "A good stain looks like this:", (inner.x + 6, y + 2), 13, INK_SOFT, bold=True)
            ph = pygame.Rect(inner.x + 6, y + 22, inner.w - 12, 92)
            s.blit(brightfield(ph.w, ph.h, 21), ph.topleft)
            pygame.draw.rect(s, (120, 120, 126), ph, 1)
            clip = s.get_clip()
            s.set_clip(ph)
            bv = self.best_v
            self.draw_embryo(s, (ph.centerx + 4, ph.centery + 4), 200, self.sig(bv), self.bg(bv))
            s.set_clip(clip)
            y = ph.bottom + 6
        if self.state != "run":
            draw_wrapped(s, self.msg, (inner.x + 6, y + 6), 14, inner.w - 12, GREEN if self.scores[-1] >= 85 else CORAL_D, bold=True)
            draw_text(s, "Best: about %s" % self.hours(self.best_v), (inner.x + 6, inner.bottom - 22), 14, INK, bold=True)
        if len(self.plan) > 1:
            gfx.tag(s, W - 20 - 110, TOP + 6, "Embryo %d of %d" % (self.r + 1, len(self.plan)), CARD, 14)


ISH_ORDER = [
    ("Fix in 4% PFA", (200, 220, 240), "Paraformaldehyde cross-links the tissue and keeps the mRNA in place."),
    ("Proteinase K", (240, 210, 190), "A short digest opens the tissue; a brief re-fix in PFA follows."),
    ("Prehybridise", SAND, "Hybridisation buffer without probe blocks sticky sites first."),
    ("Hybridise probe, 65-70 deg C", LAV, "The DIG-labelled antisense RNA probe pairs with the mRNA; the high temperature keeps binding specific."),
    ("Stringent SSC washes", SKY, "Low salt at high temperature washes off loosely bound probe."),
    ("Block", (230, 230, 210), "Serum or blocking reagent stops the antibody sticking everywhere."),
    ("Anti-DIG antibody with AP", PEACH, "The antibody finds the DIG on the probe and brings alkaline phosphatase."),
    ("NBT/BCIP colour reaction", (200, 170, 220), "Alkaline phosphatase turns NBT/BCIP into a purple precipitate where the mRNA is."),
]


def two_embryos(labels_patterned):
    def pic(s, r):
        for k, name in enumerate(("Probe 1", "Probe 2")):
            c = (r.centerx, r.y + 90 + k * (r.h // 2))
            pat = labels_patterned == k
            ph = pygame.Rect(r.x + 4, c[1] - 76, r.w - 8, r.h // 2 - 16)
            s.blit(brightfield(ph.w, ph.h, 11 + k), ph.topleft)
            pygame.draw.rect(s, (90, 90, 96), ph, 1)
            gfx.tag(s, ph.x + 8, ph.y + 8, name, (250, 250, 246), 14)
            embryo(s, c, 330, 48, heart=0.9 if pat else 0.0, bg=0.12, pigment=False)
    return pic


def control_q(rng):
    k = rng.randrange(2)
    return dict(q="Same gene, two probes: one antisense, one sense. Which one is the antisense probe?", pic=two_embryos(k),
                options=["Probe 1", "Probe 2"], keep_order=True, answer=k,
                why="The antisense probe is complementary to the mRNA and gives the pattern. The sense probe has the mRNA's own sequence, cannot pair with it, and shows the background.")


CONTROLS = [
    control_q,
    dict(q="Why is the probe labelled with digoxigenin (DIG)?", options=["Animals do not make DIG, so the anti-DIG antibody finds only the probe", "DIG is fluorescent", "DIG makes the probe bind harder", "DIG protects the probe from RNase"],
         answer=0, why="DIG is a steroid from foxglove plants; no zebrafish molecule carries it."),
    dict(q="Why hybridise at 65-70 deg C in a formamide buffer?", options=["Only closely matched probe-mRNA pairs stay bound", "To kill bacteria", "To speed up the colour reaction", "To fix the tissue"],
         answer=0, why="High stringency melts weak, partial matches, so the signal comes from the right mRNA."),
    dict(q="Why are embryos older than about 1 day often raised in PTU before an in situ?", options=["It blocks pigment that would hide the stain", "It kills the embryos gently", "It makes the probe enter", "It stops the heart"],
         answer=0, why="PTU (phenylthiourea) blocks melanin synthesis, so the embryos stay transparent."),
]

TECH = dict(
    key="ish", name="In situ", full="Whole-mount in situ hybridisation", wing="Genes & genomes", icon="ish",
    blurb="Shows where in the embryo a gene is switched on, by letting a labelled RNA probe pair with its mRNA, then using an antibody-linked enzyme to leave a purple stain where the probe sits.",
    facts=[
        "In situ hybridisation was first described in 1969, by Gall and Pardue and by John and colleagues, using radioactive probes.",
        "Digoxigenin comes from foxglove plants (Digitalis). Animals do not make it, so an anti-DIG antibody binds only the probe.",
        "Alkaline phosphatase removes a phosphate from BCIP, which then reduces NBT to an insoluble purple-blue precipitate.",
        "Zebrafish embryos are often raised in PTU to block melanin, so that pigment does not hide the stain.",
        "Large in situ screens, many from the Thisse lab, put expression patterns for thousands of zebrafish genes on the ZFIN database.",
        "myl7 (also called cmlc2) is expressed in heart muscle cells and kdrl in the cells lining blood vessels; both are classic markers.",
        "Hybridisation chain reaction (HCR) is a newer, fluorescent in situ method that amplifies the signal without an enzyme and can show several genes in one embryo.",
    ],
    quiz=[
        dict(q="What does the antisense probe bind?", options=["The gene's mRNA", "The protein", "The genomic DNA only", "The antibody"],
             answer=0, why="It is complementary to the mRNA, so the stain shows where the gene is transcribed."),
        dict(q="What makes the purple colour?", options=["Alkaline phosphatase acting on NBT/BCIP", "The probe itself", "GFP", "Peroxidase acting on DAB"],
             answer=0, why="The anti-DIG antibody carries alkaline phosphatase, which turns NBT/BCIP into a purple precipitate."),
        dict(q="What is the sense probe used for?", options=["A background control", "To amplify the signal", "To detect the protein", "To fix the embryo"],
             answer=0, why="It has the same sequence as the mRNA, so it should not bind; any colour it gives is background."),
    ],
    music=dict(name="Sixty-Five Degrees", bpm=80, beats=3, root=57, mode="harm", prog=[0, 3, 4, 0, 5, 3, 6, 4],
               lead="whistle", comp="waltz", drums="none",
               motif=[(4, 2), (3, 1), (2, 1), (0, 2), (1, 2), (2, 2), (4, 2)]),
    stages=[
        ("order", dict(title="The protocol", instr="Click the steps of a whole-mount in situ in the right order.", steps=ISH_ORDER,
                       heading="In situ, days 1-3", tint=LAV, limit=70)),
        ("stop", dict(title="Proteinase K", instr="Proteinase K opens the tissue for the probe. Click (or Space) to stop the digest at the right time.",
                      scene=protk_scene, dur=7.0, ideal=0.625, window=(0.44, 0.81), rounds=2, jitter=0.15,
                      readout=lambda v: "%4.1f min" % (v * 16),
                      early_msg="Too short: the probe cannot get into the tissue, so the stain will be weak.",
                      late_msg="Too long: the tissue is damaged and embryos fall apart in the washes.",
                      over_msg="The embryo fell apart. Proteinase K time must match the embryo's age.",
                      good_msg="Well digested: the probe can reach the cells and the embryo is intact.")),
        ("ish_stain", dict()),
        ("quiz", dict(title="Controls", instr="Antisense, sense and why the protocol works.", questions=CONTROLS, n=3, tint=LAV)),
    ],
)
TECHS = [TECH]
