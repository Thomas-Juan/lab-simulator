# -*- coding: utf-8 -*-
"""Molecular cloning: find restriction sites, choose enzymes, match sticky ends, set up the ligation."""
import math
import pygame
import audio
import gfx
from stage import Stage, register, TOP, BOTTOM
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, TEAL, LAV, VIOLET,
                  WHITE, GREEN, RED, YELLOW, BASE_COL, clamp, mix, draw_text, draw_wrapped, text_w)

from dna_common import plasmid, float_x

SITES = {"EcoRI": ("GAATTC", CORAL), "BamHI": ("GGATCC", TURQ), "HindIII": ("AAGCTT", VIOLET)}
COLS, ROWS = 50, 10


@register("clone_sites")
class SitesStage(Stage):
    title = "Find the restriction sites"
    instr = "Click every EcoRI site (GAATTC) and every BamHI site (GGATCC) in the plasmid sequence. Clicking elsewhere costs points."
    limit = 50

    def setup(self):
        rng = self.rng
        n = COLS * ROWS
        want = self.lv([("EcoRI", 3)], [("EcoRI", 3), ("BamHI", 2)], [("EcoRI", 2), ("BamHI", 2), ("HindIII", 2)])
        self.enz = {name: SITES[name] for name, _ in want}
        self.penalty = self.lv(5, 8, 12)
        n_decoy = self.lv(0, 2, 4)
        names = " and ".join("every %s site (%s)" % (nm, SITES[nm][0]) for nm, _ in want)
        self.instr = ("Click %s in the plasmid sequence. Read every letter of the site: one wrong base and the enzyme does not cut. "
                      "Clicking elsewhere costs points." % names)
        while True:
            seq = [rng.choice("ACGT") for _ in range(n)]
            self.sites = []
            self.decoys = []
            used = set()

            def spot():
                for _try in range(200):
                    row, col = rng.randrange(ROWS), rng.randrange(COLS - 6)
                    i = row * COLS + col
                    if not any(j in used for j in range(i - 2, i + 8)):
                        return i
                return i
            for name, k in want:
                for _ in range(k):
                    i = spot()
                    for j, ch in enumerate(SITES[name][0]):
                        seq[i + j] = ch
                    used.update(range(i, i + 6))
                    self.sites.append([i, name, False])
            for _ in range(n_decoy):          # near misses: a real site with one base changed
                name = rng.choice([nm for nm, _ in want])
                motif = list(SITES[name][0])
                pos = rng.choice([0, 1, 4, 5])
                motif[pos] = rng.choice([b for b in "ACGT" if b != motif[pos]])
                i = spot()
                for j, ch in enumerate(motif):
                    seq[i + j] = ch
                used.update(range(i, i + 6))
                self.decoys.append((i, name))
            text = "".join(seq)
            real = sum(text.count(m) for m, _ in SITES.values())
            if real == len(self.sites):
                break
        self.seq = text
        self.wrong = 0
        self.flash = []
        self.x0, self.y0, self.cw, self.lh = 64, TOP + 66, 10.4, 36

    def index_at(self, pos):
        col = int((pos[0] - self.x0) // self.cw)
        row = int((pos[1] - self.y0 + 6) // self.lh)
        if 0 <= col < COLS and 0 <= row < ROWS and (pos[1] - self.y0 + 6) % self.lh < 26:
            return row * COLS + col
        return None

    def tick(self, inp):
        self.flash = [[i, t - 1] for i, t in self.flash if t > 1]
        if not inp.click:
            return
        i = self.index_at(inp.mouse)
        if i is None:
            return
        for site in self.sites:
            if site[0] <= i < site[0] + 6:
                if not site[2]:
                    site[2] = True
                    audio.sfx("good")
                    self.floaters.add(inp.mouse[0], inp.mouse[1] - 20, site[1] + "!", SITES[site[1]][1], 18)
                    self.particles.burst(inp.mouse[0], inp.mouse[1], 10)
                    if all(x[2] for x in self.sites):
                        self.finish(100 - self.penalty * self.wrong, *self.summary())
                return
        self.wrong += 1
        self.flash.append([i, 30])
        self.shake = 6
        audio.sfx("bad")
        for d, name in self.decoys:
            if d <= i < d + 6:
                self.near = getattr(self, "near", 0) + 1
                msg = "not %s: one base off" % name
                self.floaters.add(float_x(inp.mouse[0], msg, 15), inp.mouse[1] - 20, msg, RED, 15)
                return
        self.floaters.add(inp.mouse[0], inp.mouse[1] - 20, "-%d" % self.penalty, RED, 15)

    def summary(self):
        fb = ["Found all %d sites%s." % (len(self.sites), "" if not self.wrong else ", with %d wrong click%s" % (self.wrong, "" if self.wrong == 1 else "s"))]
        if getattr(self, "near", 0):
            fb.append("You clicked a near miss: enzymes need the exact sequence, so one changed base means no cut.")
        ends = {"EcoRI": "AATT", "BamHI": "GATC", "HindIII": "AGCT"}
        fb.append("These enzymes cut after the first base of their site, leaving 4-base sticky ends (%s)." %
                  ", ".join(ends[nm] for nm in self.enz))
        return fb

    def partial(self):
        return max(0, 100 * sum(1 for x in self.sites if x[2]) / len(self.sites) - self.penalty * self.wrong - 10)

    def autoplay(self):
        self.finish(92, "(autoplay)")

    def letters_layer(self):
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        hl = set()
        for site in self.sites:
            if site[2]:
                hl.update(range(site[0], site[0] + 6))
        for k, ch in enumerate(self.seq):
            row, col = divmod(k, COLS)
            x = self.x0 + col * self.cw
            y = self.y0 + row * self.lh
            draw_text(layer, ch, (x, y), 17, mix(BASE_COL[ch], INK, 0.2), mono=True, bold=k in hl)
            if col == 0:
                draw_text(layer, str(k + 1), (self.x0 - 10, y + 3), 11, MUTED, right=True)
        return layer

    def update(self, inp):
        was = self.done
        Stage.update(self, inp)
        if self.done and not was and self.feedback == ["Time ran out."]:
            found = sum(1 for x in self.sites if x[2])
            self.feedback = ["Found %d of %d sites before time ran out." % (found, len(self.sites))]
            if self.wrong:
                self.feedback.append("%d clicks on ordinary sequence: read the letters before you click." % self.wrong)

    def render(self, s):
        gfx.bench(s, SAND)
        card = pygame.Rect(30, TOP + 12, 580, BOTTOM - TOP - 24)
        gfx.card(s, card, CARD)
        gfx.header(s, card, (60, 66, 88), 30)
        draw_text(s, "pJuan-kdrl.dna   ·   500 bp shown", (card.x + 16, card.y + 9), 14, WHITE, bold=True)
        bad = {i for i, _ in self.flash}
        for row in range(ROWS):
            y = self.y0 + row * self.lh
            for k in range(0, COLS + 1, 10):
                x = self.x0 + k * self.cw
                pygame.draw.line(s, (200, 196, 210), (x - 1, y - 6), (x - 1, y - 3), 1)
        for site in self.sites:
            if site[2]:
                row, col = divmod(site[0], COLS)
                x = self.x0 + col * self.cw
                y = self.y0 + row * self.lh
                c = SITES[site[1]][1]
                gfx.rrect(s, (x - 3, y - 3, 6 * self.cw + 5, 27), mix(c, WHITE, 0.55), mix(c, INK, 0.3), 1, 6, 0.1)
        for i in bad:
            row, col = divmod(i, COLS)
            gfx.rrect(s, (self.x0 + col * self.cw - 2, self.y0 + row * self.lh - 2, self.cw + 3, 25), (250, 190, 180), None, 0, 4, 0.0, False)
        key = tuple(x[2] for x in self.sites)
        if getattr(self, "_layer_key", None) != key:
            self._layer_key = key
            self._layer = self.letters_layer()
        s.blit(self._layer, (0, 0))
        for site in self.sites:
            if site[2]:
                row, col = divmod(site[0], COLS)
                x = self.x0 + (col + 1) * self.cw
                y = self.y0 + row * self.lh
                gfx.line(s, INK, (x, y - 4), (x, y + 23), 2)
                draw_text(s, site[1], (x + self.cw * 2.0, y - 17), 11, mix(SITES[site[1]][1], INK, 0.45), center=True, bold=True)
        side = pygame.Rect(640, TOP + 12, 300, BOTTOM - TOP - 24)
        gfx.card(s, side, (250, 248, 240))
        draw_text(s, "Enzymes", (790, TOP + 26), 18, INK, center=True, bold=True)
        step = 140 if len(self.enz) < 3 else 112
        for k, (name, (motif, col)) in enumerate(self.enz.items()):
            y = TOP + 62 + k * step
            box = pygame.Rect(660, y, 260, step - 16)
            gfx.rrect(s, box, mix(col, WHITE, 0.72), INK, 2, 12, 0.08)
            draw_text(s, name, (676, y + 10), 19, INK, bold=True)
            found = sum(1 for x in self.sites if x[1] == name and x[2])
            tot = sum(1 for x in self.sites if x[1] == name)
            draw_text(s, "%d / %d" % (found, tot), (box.right - 14, y + 12), 16, GREEN if found == tot else INK_SOFT, right=True, bold=True)
            comp = {"A": "T", "T": "A", "G": "C", "C": "G"}
            cw = 18
            x0 = box.x + 64
            ty, by = (y + 48, y + 80) if step == 140 else (y + 40, y + 66)
            draw_text(s, "5'", (x0 - 28, ty + 2), 13, MUTED, bold=True)
            draw_text(s, "3'", (x0 - 28, by + 2), 13, MUTED, bold=True)
            for j, ch in enumerate(motif):
                draw_text(s, ch, (x0 + j * cw, ty), 20, INK, mono=True, bold=True)
                draw_text(s, comp[ch], (x0 + j * cw, by), 20, INK, mono=True, bold=True)
            cut = [(x0 + cw - 2, ty - 2), (x0 + cw - 2, ty + 28), (x0 + 5 * cw - 2, ty + 28), (x0 + 5 * cw - 2, by + 26)]
            pygame.draw.lines(s, mix(col, INK, 0.3), False, cut, 3)
        if len(self.enz) < 3:
            draw_wrapped(s, "These sites are palindromes: the other strand reads the same 5' to 3'. The staggered cut leaves sticky ends.", (660, TOP + 350), 14, 260, INK_SOFT)

# ------------------------------------------------------------------ quiz: choose the enzymes
ENZ = ["EcoRI", "BamHI", "HindIII", "XhoI", "NotI", "XbaI"]
ECOL = {"EcoRI": CORAL, "BamHI": TURQ, "HindIII": VIOLET, "XhoI": (214, 150, 60), "NotI": (86, 170, 92), "XbaI": (70, 120, 200)}


def map_question(rng):
    a, b, c, d = rng.sample(ENZ, 4)
    mcs = [a, c, b, d]
    rng.shuffle(mcs)

    def pic(s, r):
        cx, cy, rad = r.x + 150, r.y + 130, 84
        plasmid(s, (cx, cy), rad, [(1.9, 3.3, CORAL, "AmpR"), (3.9, 4.5, (214, 190, 90), "ori")], "", "")
        draw_text(s, "vector", (cx - 12, cy + 10), 16, INK, center=True, bold=True, vcenter=True)
        for k, e in enumerate(mcs):
            ang = -0.95 + k * 0.3
            x, y = cx + math.cos(ang) * (rad + 6), cy + math.sin(ang) * (rad + 6)
            pygame.draw.line(s, ECOL[e], (cx + math.cos(ang) * (rad - 8), cy + math.sin(ang) * (rad - 8)), (x + math.cos(ang) * 16, y + math.sin(ang) * 16), 3)
            draw_text(s, e, (x + math.cos(ang) * 22, y + math.sin(ang) * 22 - 8), 14, mix(ECOL[e], INK, 0.2), bold=True)
        draw_text(s, "MCS", (cx + math.cos(-0.5) * (rad - 28), cy + math.sin(-0.5) * (rad - 28)), 12, INK_SOFT, center=True, bold=True, vcenter=True)
        iy = r.bottom - 92
        ix0, ix1 = r.x + 40, r.right - 40
        gfx.rrect(s, (ix0, iy, ix1 - ix0, 24), (250, 222, 170), INK, 2, 6, 0.12)
        draw_text(s, "insert (your gene)", ((ix0 + ix1) // 2, iy + 4), 13, INK, center=True, bold=True)
        gfx.poly(s, (230, 190, 120), [(ix0 + 8, iy + 30), (ix0 + 40, iy + 30), (ix0 + 40, iy + 26), (ix0 + 50, iy + 33), (ix0 + 40, iy + 40), (ix0 + 40, iy + 36), (ix0 + 8, iy + 36)], 1)
        draw_text(s, "start", (ix0 + 56, iy + 27), 12, INK_SOFT, bold=True)
        for x, e in ((ix0, a), ((ix0 + ix1) // 2 + 60, c), (ix1, b)):
            pygame.draw.line(s, ECOL[e], (x, iy - 10), (x, iy + 34), 3)
            draw_text(s, e, (x, iy - 28), 14, mix(ECOL[e], INK, 0.2), center=True, bold=True)
        draw_text(s, "Sites at the ends were added with the PCR primers.", (r.centerx, r.bottom - 22), 13, INK_SOFT, center=True)

    opts = ["%s + %s" % (a, b), "%s + %s" % (a, c), "%s alone" % a, "%s + %s" % (b, d)]
    return dict(q="Which enzymes clone the insert into the vector in one orientation, without cutting inside the insert?", options=opts, answer=0, pic=pic,
                why="%s and %s flank the insert and are both in the MCS. Two different ends force one orientation. %s also cuts inside the insert, and one enzyme alone lets the insert go in either way." % (a, b, c))


STATIC_CLONE_Q = [
    dict(q="After ligation, you get many colonies but none has the insert. The most likely cause?", options=["The vector closed on itself", "The insert was too short", "Too much ampicillin", "The ligase worked too well"],
         answer=0, why="A vector cut with one enzyme, or not dephosphorylated, can re-ligate without an insert. Phosphatase treatment or two enzymes prevent it."),
    dict(q="What does DNA ligase do?", options=["Seals the sugar-phosphate backbone between two DNA ends", "Cuts DNA at specific sites", "Copies DNA", "Adds a poly-A tail"],
         answer=0, why="Ligase forms the phosphodiester bond that joins the ends, using ATP."),
]


# ------------------------------------------------------------------ match: enzyme -> sticky end
OVERHANGS = [
    ("EcoRI   G^AATTC", "5' AATT", "EcoRI cuts between G and A on both strands, leaving a 4-base 5' overhang: AATT."),
    ("BamHI   G^GATCC", "5' GATC", "BamHI leaves a GATC 5' overhang."),
    ("HindIII   A^AGCTT", "5' AGCT", "HindIII leaves an AGCT 5' overhang."),
    ("XhoI   C^TCGAG", "5' TCGA", "XhoI leaves a TCGA 5' overhang."),
    ("NotI   GC^GGCCGC", "5' GGCC", "NotI recognises 8 bases, so its sites are rare in random sequence."),
    ("PstI   CTGCA^G", "3' TGCA", "When the cut is near the 3' end of the site, the single-stranded tail is on the 3' end."),
    ("KpnI   GGTAC^C", "3' GTAC", "KpnI leaves a 3' overhang."),
    ("EcoRV   GAT^ATC", "blunt", "EcoRV cuts both strands in the same place: blunt ends, which ligate less efficiently."),
]


def draw_site(s, r, label):
    """Enzyme name above its recognition site (^ marks the cut), centred in the card."""
    name, site = label.split()
    draw_text(s, name, (r.centerx, r.centery - 20), 16, INK, center=True, bold=True)
    draw_text(s, site, (r.centerx, r.centery + 1), 16, INK_SOFT, center=True, bold=True, mono=True)


def draw_end(s, r, label):
    """The left end of a DNA fragment after cutting: top strand 5'->3', bottom 3'->5'."""
    cw = 13
    x0 = r.x + 40
    yt, yb = r.y + 7, r.y + 25
    kind, _, bases = label.partition(" ")
    if label == "blunt":
        kind, bases = "blunt", ""
    n = len(bases)
    start = x0 + n * cw
    gfx.rrect(s, (start, yt + 2, r.right - 20 - start, 10), CORAL, INK, 1, 4, 0.2)
    gfx.rrect(s, (start, yb + 2, r.right - 20 - start, 10), TURQ, INK, 1, 4, 0.2)
    for x in range(int(start) + 8, r.right - 24, 10):
        pygame.draw.line(s, mix(SAND, INK, 0.3), (x, yt + 12), (x, yb + 2), 2)
    if kind == "5'":
        for k, ch in enumerate(bases):
            gfx.rrect(s, (x0 + k * cw, yt, cw - 1, 14), mix(CORAL, WHITE, 0.6), mix(CORAL, INK, 0.3), 1, 3, 0.1)
            draw_text(s, ch, (x0 + k * cw + 2, yt - 2), 14, INK, bold=True, mono=True)
    elif kind == "3'":
        for k, ch in enumerate(bases[::-1]):
            gfx.rrect(s, (x0 + k * cw, yb, cw - 1, 14), mix(TURQ, WHITE, 0.6), mix(TURQ, INK, 0.3), 1, 3, 0.1)
            draw_text(s, ch, (x0 + k * cw + 2, yb - 2), 14, INK, bold=True, mono=True)
    draw_text(s, label + (" overhang" if kind != "blunt" else " end"), (r.centerx + 20, r.bottom - 20), 13, INK_SOFT, center=True, bold=True)


# ------------------------------------------------------------------ calc: insert amount
def ratio_problem(rng):
    vec = rng.choice([3000, 4000, 5000, 6000])
    ins = rng.choice([500, 750, 1000, 1500, 2000])
    ng = rng.choice([50, 100])
    ratio = rng.choice([3, 3, 1])
    ans = ng * ins / float(vec) * ratio

    def pic(s, r):
        cx, cy = r.x + 90, r.y + r.h // 2
        rad = min(56, r.h // 2 - 24)
        plasmid(s, (cx, cy), rad, [(2.2, 3.6, CORAL, "")], "vector", "%d bp" % vec)
        w = int((r.w - 230) * ins / 2000.0)
        gfx.rrect(s, (r.x + 210, cy - 12, max(30, w), 24), (250, 222, 170), INK, 2, 6, 0.12)
        draw_text(s, "%d bp insert" % ins, (r.x + 210, cy + 18), 14, INK, bold=True)
    return dict(text="Vector: %d bp, %d ng in the reaction. Insert: %d bp. You want a %d:1 molar ratio of insert to vector. How many ng of insert do you add?" % (vec, ng, ins, ratio),
                answer=ans, unit="ng", tol=0.03, pic=pic,
                why="ng insert = ng vector × (insert bp / vector bp) × ratio = %d x %d / %d x %d." % (ng, ins, vec, ratio))


TECH = dict(
    key="clone", name="Cloning", full="Molecular cloning (restriction digest and ligation)", wing="DNA", icon="clone",
    blurb="Cuts a gene out with restriction enzymes and pastes it into a plasmid vector, so bacteria can copy it or cells can express it.",
    facts=[
        "Restriction enzymes evolved as bacterial defences against viruses. Bacteria protect their own DNA by methylating the same sites.",
        "Werner Arber, Daniel Nathans and Hamilton Smith shared the 1978 Nobel Prize in Physiology or Medicine for discovering restriction enzymes.",
        "In 1973 Stanley Cohen, Herbert Boyer and colleagues made the first recombinant plasmids that could be copied in E. coli.",
        "EcoRI is named after its source: Escherichia coli strain RY13, and it was the first enzyme found in that strain.",
        "Most recognition sites are palindromes: GAATTC reads the same 5' to 3' on both strands.",
        "T4 DNA ligase comes from a bacteriophage. It can join blunt ends too, though much less efficiently than sticky ends.",
        "Gibson assembly, published in 2009, joins overlapping DNA fragments without any restriction enzymes.",
    ],
    quiz=[
        STATIC_CLONE_Q[1],
        dict(q="Why cut the vector and the insert with two different enzymes?", options=["The insert can only go in one way round", "It makes the DNA shorter", "It removes the antibiotic gene", "Ligase needs two enzymes"],
             answer=0, why="Two different, incompatible ends force directional cloning and stop the vector closing on itself."),
        dict(q="What is a sticky end?", options=["A short single-stranded overhang left by a staggered cut", "A methylated base", "The end of a blunt fragment", "A primer binding site"],
             answer=0, why="Staggered cuts leave unpaired bases that base-pair with a matching overhang."),
    ],
    music=dict(name="Restriction Rondo", bpm=120, beats=4, root=48, mode="harm", prog=[0, 3, 4, 0, 5, 3, 4, 4], lead="harpsi", comp="alberti",
               drums="none", motif=[(0, 1), (2, 1), (4, 1), (7, 1), (6, 2), (4, 2), (5, 1), (4, 1), (3, 1), (2, 1), (1, 4)]),
    stages=[
        ("clone_sites", {}),
        ("quiz", dict(title="Plan the cloning", questions=[map_question] + STATIC_CLONE_Q, n=3,
                      instr="Choose the enzymes for directional cloning, then answer two questions on ligation.")),
        ("match", dict(title="Sticky ends", pairs=OVERHANGS, n=5, left_title="Enzyme and cut site", right_title="End it leaves",
                       draw_left=draw_site, draw_right=draw_end, instr="Read where each enzyme cuts (^) and connect it to the end it leaves. The red strand is 5' to 3'.")),
        ("calc", dict(title="Set up the ligation", problems=[ratio_problem, ratio_problem], n=2,
                      instr="Work out how much insert to add for the molar ratio you want.")),
    ],
)
TECHS = [TECH]
