# -*- coding: utf-8 -*-
"""Cell counting with a haemocytometer (improved Neubauer chamber)."""
import math
import pygame
import audio
import gfx
from stage import Stage, register, TOP, BOTTOM
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, LAV, NIGHT, WHITE, GREEN,
                  RED, clamp, mix, draw_text, draw_wrapped)
import render as R
from cells_common import rounded, dead_cell as _dead, field_rect, photo_finish, soften

LIVE_EDGE = (110, 120, 110)
DEAD = (64, 92, 176)
SQ = pygame.Rect(80, 108, 340, 340)     # the large corner square on screen
FIELD = pygame.Rect(46, 74, 408, 408)   # what the microscope shows (with neighbouring squares)
CR = 10                                  # cell radius


def dead_cell(s, x, y, r=CR):
    _dead(s, x, y, r)


def live_cell(s, x, y, r=CR):
    rounded(s, x, y, r, kind="live")


def mark(s, x, y, ok):
    """Small drawn tick (ok) or cross."""
    if ok:
        gfx.line(s, (40, 150, 70), (x - 5, y), (x - 1, y + 5), 3)
        gfx.line(s, (40, 150, 70), (x - 1, y + 5), (x + 6, y - 5), 3)
    else:
        gfx.line(s, (200, 60, 50), (x - 5, y - 5), (x + 5, y + 5), 3)
        gfx.line(s, (200, 60, 50), (x - 5, y + 5), (x + 5, y - 5), 3)


def ring(s, x, y, r, col, w=2):
    for k in range(w):
        R.gd.aacircle(s, int(x), int(y), int(r) - k, col)


_GRID = {}


def grid_layer(hint):
    """The chamber as seen at 10x: faintly blue trypan background, etched grid lines, triple lines round the large square."""
    if hint in _GRID:
        return _GRID[hint]
    f = pygame.Surface(FIELD.size)
    f.blit(field_rect(FIELD.w, FIELD.h, (206, 210, 204), 11), (0, 0))
    lines = pygame.Surface(FIELD.size, pygame.SRCALPHA)
    ox, oy = FIELD.x, FIELD.y
    small = SQ.w / 4
    for i in range(-2, 7):
        x = SQ.x + i * small - ox
        y = SQ.y + i * small - oy
        for (a, b), col in ((((x + 1, 0), (x + 1, FIELD.h)), (240, 242, 238, 160)), (((x, 0), (x, FIELD.h)), (96, 100, 98, 200))):
            pygame.draw.line(lines, col, a, b, 1)
        pygame.draw.line(lines, (240, 242, 238, 160), (0, y + 1), (FIELD.w, y + 1), 1)
        pygame.draw.line(lines, (96, 100, 98, 200), (0, y), (FIELD.w, y), 1)
    for name, a, b in (("top", SQ.topleft, SQ.topright), ("left", SQ.topleft, SQ.bottomleft),
                       ("bottom", SQ.bottomleft, SQ.bottomright), ("right", SQ.topright, SQ.bottomright)):
        col = (60, 64, 62, 230)
        if hint:
            col = (40, 150, 70) if name in ("top", "left") else (200, 60, 50)
        horiz = a[1] == b[1]
        for off in (-3, 0, 3):
            if horiz:
                pygame.draw.line(lines, col, (0, a[1] + off - oy), (FIELD.w, a[1] + off - oy), 1 if not hint else 2)
            else:
                pygame.draw.line(lines, col, (a[0] + off - ox, 0), (a[0] + off - ox, FIELD.h), 1 if not hint else 2)
    f.blit(soften(lines, 1.3), (0, 0))
    f = photo_finish(f, 1.0)
    vig = pygame.Surface(FIELD.size, pygame.SRCALPHA)
    for k in range(18):
        pygame.draw.rect(vig, (30, 40, 60, int(4 + k * 1.2)), (0, 0, FIELD.w, FIELD.h), 18 - k)
    f.blit(vig, (0, 0))
    _GRID[hint] = f
    return f


@register("count_cells")
class CountCells(Stage):
    title = "Count the live cells"
    instr = ("Click every live (bright, unstained) cell that counts in the large square. Blue cells took up trypan blue: "
             "they are dead, skip them. Count cells touching the top or left line, not the bottom or right line.")
    limit = 90

    def setup(self):
        self.round = 0
        self.rounds = self.p.get("rounds", self.lv(2, 2, 3))
        self.data = []          # per square: (your live count, right live count, dead in square, border errors)
        self.scores = []
        self.new_square()
        self.done_btn = gfx.Button((560, 420, 180, 44), "Done counting", SAND)
        self.reveal = 0
        self.hint = "Live cells only. Top and left lines count; bottom and right lines do not."

    def touches(self, c):
        x, y = c["x"], c["y"]
        lim = CR + 2
        inside_x = SQ.left - lim < x < SQ.right + lim
        inside_y = SQ.top - lim < y < SQ.bottom + lim
        return {"top": abs(y - SQ.top) < lim and inside_x, "left": abs(x - SQ.left) < lim and inside_y,
                "bottom": abs(y - SQ.bottom) < lim and inside_x, "right": abs(x - SQ.right) < lim and inside_y}

    def counts(self, c):
        if not c["live"]:
            return False
        t = self.touches(c)
        if t["bottom"] or t["right"]:
            return False
        inside = SQ.collidepoint(c["x"], c["y"])
        return inside or t["top"] or t["left"]

    def counts_dead(self, c):
        """Dead cells follow the same border rule as live ones (top and left lines in, bottom and right out)."""
        if c["live"]:
            return False
        t = self.touches(c)
        if t["bottom"] or t["right"]:
            return False
        return SQ.collidepoint(c["x"], c["y"]) or t["top"] or t["left"]

    def free(self, x, y):
        return all(math.hypot(x - c["x"], y - c["y"]) > 2 * CR + 4 for c in self.cells)

    def add(self, x, y, live):
        if self.free(x, y):
            self.cells.append({"x": x, "y": y, "live": live, "mark": False, "ph": self.rng.uniform(0, 6.3)})
            return True
        return False

    def new_square(self):
        r = self.rng
        self.cells = []
        per_edge = self.lv([2, 2, 3], [2, 3, 3], [3, 3, 4])
        for edge in ("top", "left", "bottom", "right"):
            for k in range(r.choice(per_edge)):
                for _ in range(30):
                    a = r.uniform(30, SQ.w - 30)
                    off = r.uniform(-3, 3)
                    x, y = {"top": (SQ.x + a, SQ.top + off), "bottom": (SQ.x + a, SQ.bottom + off),
                            "left": (SQ.left + off, SQ.y + a), "right": (SQ.right + off, SQ.y + a)}[edge]
                    # the first cell on every border is live, so the border rule always matters
                    if self.add(x, y, k == 0 or r.random() < 0.75):
                        break
        n_live = r.randint(*self.lv((12, 16), (16, 24), (22, 30)))
        n_dead = r.randint(*self.lv((2, 4), (3, 6), (5, 9)))
        for live, n in ((True, n_live), (False, n_dead)):
            placed = 0
            while placed < n:
                x = r.uniform(SQ.left + CR + 7, SQ.right - CR - 7)
                y = r.uniform(SQ.top + CR + 7, SQ.bottom - CR - 7)
                placed += self.add(x, y, live)
        for _ in range(60):     # cells in the neighbouring squares (outside the large square)
            x, y = r.uniform(FIELD.left + 12, FIELD.right - 12), r.uniform(FIELD.top + 12, FIELD.bottom - 12)
            if not SQ.inflate(2 * CR + 10, 2 * CR + 10).collidepoint(x, y):
                self.add(x, y, r.random() < 0.8)
        self.reveal = 0

    def on_border(self, c):
        t = self.touches(c)
        return any(t.values())

    def grade(self):
        errors = border = dead = 0
        for c in self.cells:
            want = self.counts(c)
            c["ok"] = want == c["mark"]
            c["want"] = want
            if not c["ok"]:
                errors += 1
                if self.on_border(c):
                    border += 1          # breaking the border rule costs most: it biases every count
                elif not c["live"]:
                    dead += 1
        n = sum(c["want"] for c in self.cells)
        other = errors - border
        sc = max(0, 100 - self.lv(25, 24, 22) * border - self.lv(10, 12, 14) * other)
        self.scores.append(sc)
        marked = sum(c["mark"] for c in self.cells)
        dead_in = sum(1 for c in self.cells if self.counts_dead(c))
        self.data.append((marked, n, dead_in, border))
        self.ctx.count_data = list(self.data)
        if errors:
            msg = "%d border error%s" % (border, "s" if border != 1 else "") if border else "%d error%s" % (errors, "s" if errors > 1 else "")
        else:
            msg = "Exact count!"
        self.floaters.add(840, 470, msg, GREEN if errors <= 1 else CORAL_D, 24)
        audio.sfx("good" if errors <= 1 else "bad")
        if errors <= 1:
            self.particles.burst(840, 470, 18)
        if border:
            self.shake = 10
        self.last = (marked, n, errors)
        self.counted_dead = getattr(self, "counted_dead", 0) + dead
        self.reveal = 150
        self._lkey = None

    def tick(self, inp):
        if self.reveal:
            self.reveal -= 1
            if self.reveal == 0:
                self.round += 1
                if self.round >= self.rounds:
                    fb = ["Square %d: you marked %d; the right count was %d." % (i + 1, m, n) for i, (m, n, _, _) in enumerate(self.data)]
                    nb = sum(d[3] for d in self.data)
                    if nb:
                        fb.append("%d cell%s on the borders handled wrongly: count the top and left lines only, so no cell is counted "
                                  "twice in neighbouring squares." % (nb, "s" if nb > 1 else ""))
                    elif getattr(self, "counted_dead", 0):
                        fb.append("Blue cells took up trypan blue: they are dead and must not be counted.")
                    else:
                        fb.append("Your counts go into the next step, where you turn them into a concentration.")
                    self.finish(sum(self.scores) / len(self.scores), *fb[-4:])
                else:
                    self.new_square()
            return
        if self.done_btn.hit(inp) or "ok" in inp.pressed:
            self.grade()
            return
        if inp.click:
            for c in self.cells:
                if math.hypot(inp.mouse[0] - c["x"], inp.mouse[1] - c["y"]) < CR + 4:
                    c["mark"] = not c["mark"]
                    audio.sfx("click" if c["mark"] else "blip")
                    break

    def partial(self):
        return sum(self.scores) / self.rounds

    def autoplay(self):
        self.ctx.count_data = [(20, 20, 4, 0), (22, 22, 5, 0)]
        self.finish(93, "Square 1: exact count.")

    def render(self, s):
        gfx.bench(s, SKY)
        gfx.card(s, FIELD.inflate(16, 16), (16, 16, 20), (60, 62, 70))
        key = (self.round, bool(self.reveal), tuple(c["mark"] for c in self.cells), len(self.cells))
        if getattr(self, "_lkey", None) != key:      # the field only changes when you click, so it is cached
            lay = pygame.Surface(FIELD.size)
            lay.blit(grid_layer(self.round == 0), (0, 0))
            ox, oy = FIELD.topleft
            for c in self.cells:
                x, y = c["x"] - ox, c["y"] - oy
                if c["live"]:
                    live_cell(lay, x, y)
                else:
                    dead_cell(lay, x, y)
                if c["mark"]:
                    ring(lay, x, y, CR + 5, CORAL, 3)
                if self.reveal and not c["ok"]:
                    ring(lay, x, y, CR + 8, RED, 3)
                elif self.reveal and c["want"]:
                    ring(lay, x, y, CR + 8, GREEN, 2)
            self._layer, self._lkey = lay, key
        s.blit(self._layer, FIELD.topleft)
        draw_text(s, "10x brightfield  ·  trypan blue  ·  cells drawn enlarged", (FIELD.centerx, FIELD.bottom + 8), 11, (170, 172, 180), center=True)
        # rule panel
        p = pygame.Rect(490, TOP + 14, 440, 450)
        gfx.card(s, p, CARD)
        draw_text(s, "Square %d of %d" % (min(self.round + 1, self.rounds), self.rounds), (p.x + 18, p.y + 14), 18, INK, bold=True)
        d = pygame.Rect(p.x + 24, p.y + 56, 120, 120)
        gfx.rrect(s, d, (214, 224, 232), None, 0, 2, 0, False)
        gfx.line(s, (40, 150, 70), d.topleft, d.topright, 4)
        gfx.line(s, (40, 150, 70), d.topleft, d.bottomleft, 4)
        gfx.line(s, (200, 60, 50), d.bottomleft, d.bottomright, 4)
        gfx.line(s, (200, 60, 50), d.topright, d.bottomright, 4)
        for x, y, ok in ((d.x + 50, d.top, True), (d.left, d.y + 70, True), (d.x + 70, d.bottom, False), (d.right, d.y + 40, False)):
            rounded(s, x, y, 8, kind="live")
            mark(s, x + 16, y - 14, ok)
        draw_wrapped(s, "Count cells inside the square and on the top and left lines. Skip cells on the bottom and right lines.",
                     (d.right + 34, d.y), 15, p.right - d.right - 50, INK)
        live_cell(s, p.x + 36, p.y + 214)
        draw_text(s, "live: bright, keeps trypan blue out", (p.x + 56, p.y + 204), 15, INK)
        dead_cell(s, p.x + 36, p.y + 246)
        draw_text(s, "dead: stained blue, do not count", (p.x + 56, p.y + 236), 15, INK)
        marked = sum(c["mark"] for c in self.cells)
        draw_text(s, "Marked: %d" % marked, (p.x + 18, p.y + 290), 30, CORAL_D, bold=True)
        if self.reveal:
            m, n, e = self.last
            draw_text(s, "Right count: %d" % n, (p.x + 18, p.y + 332), 18, INK, bold=True)
        else:
            self.done_btn.draw(s, None)


# ------------------------------------------------------------------ maths
def _grid_pic(counts):
    counts = list(counts) + [None] * (4 - len(counts))

    def pic(s, rect):
        size = min(rect.h - 10, 220)
        g = pygame.Rect(rect.x + 20, rect.y + 4, size, size)
        s.blit(gfx.texture(g.w, g.h, (214, 224, 232), 30, 5, 92, 2), g.topleft)
        # improved Neubauer: corner squares 4 x 4, centre square 5 x 5, side squares 4 x 5
        cs3 = g.w / 3.0
        for bx in range(3):
            for by in range(3):
                nx, ny = (5 if bx == 1 else 4), (5 if by == 1 else 4)
                x0, y0 = g.x + bx * cs3, g.y + by * cs3
                for i in range(1, nx):
                    pygame.draw.line(s, (168, 180, 190), (x0 + cs3 * i / nx, y0), (x0 + cs3 * i / nx, y0 + cs3), 1)
                for i in range(1, ny):
                    pygame.draw.line(s, (168, 180, 190), (x0, y0 + cs3 * i / ny), (x0 + cs3, y0 + cs3 * i / ny), 1)
        for i in range(1, 3):
            pygame.draw.line(s, (110, 122, 134), (g.x + cs3 * i, g.y), (g.x + cs3 * i, g.bottom), 3)
            pygame.draw.line(s, (110, 122, 134), (g.x, g.y + cs3 * i), (g.right, g.y + cs3 * i), 3)
        gfx.rrect(s, g, None, INK, 2, 2)
        cs = g.w / 3
        for (cx, cy), n in zip(((0, 0), (2, 0), (0, 2), (2, 2)), counts):
            r = pygame.Rect(g.x + cx * cs + 3, g.y + cy * cs + 3, cs - 6, cs - 6)
            if n is None:
                continue
            gfx.rrect(s, r, (250, 236, 200), CORAL, 2, 4)
            draw_text(s, str(n), r.center, 18, INK, center=True, bold=True, vcenter=True)
        draw_wrapped(s, "The four large corner squares. Each is 1 mm × 1 mm and the chamber is 0.1 mm deep: 0.1 µL per square.",
                     (g.right + 18, g.y + 10), 14, rect.right - g.right - 24, INK_SOFT)
    return pic


def _own_counts():
    from cells_common import ctx_get
    data = ctx_get("count_data")
    return [d[0] for d in data] if data else None


def _conc_q(rng):
    own = _own_counts()
    if own:
        counts = own[:4]
        dil = 2
        mix_txt = "mixed 1:1 with trypan blue (dilution factor 2)"
        intro = "These are the live cells you marked in the chamber (%s)." % ", ".join(str(c) for c in counts)
    else:
        counts = [rng.randint(30, 60) for _ in range(4)]
        dil = rng.choice([2, 2, 5, 10])
        mix_txt = "mixed 1:1 with trypan blue (dilution factor 2)" if dil == 2 else "diluted %d-fold in total" % dil
        intro = "You counted these live cells in the four corner squares."
    n = len(counts)
    mean = sum(counts) / float(n)
    ans = mean * dil * 1e4
    return dict(text="%s The sample was %s. How many cells per mL are in the original suspension?" % (intro, mix_txt),
                answer=ans, unit="cells/mL", tol=0.02, show="%.3g × 10⁴" % (ans / 1e4), pic=_grid_pic(counts),
                why="Mean %.2f per square × %d (dilution) × 10⁴ (one square holds 0.1 µL) = %.3g cells/mL." % (mean, dil, ans))


def _viab_pic(live, dead):
    def pic(s, rect):
        x, y = rect.x + 30, rect.y + 30
        for yy in (y, y + 50):
            fr = pygame.Rect(x - 18, yy - 20, 160, 40)
            s.blit(gfx.texture(fr.w, fr.h, (214, 224, 232), 20, 5, 93, 2), fr.topleft)
            gfx.rrect(s, fr, None, (120, 130, 140), 1, 6)
        for i in range(5):
            live_cell(s, x + i * 30, y)
        draw_text(s, "%d live" % live, (x + 160, y - 10), 18, INK, bold=True)
        for i in range(2):
            dead_cell(s, x + i * 30, y + 50)
        draw_text(s, "%d dead (blue)" % dead, (x + 160, y + 40), 18, INK, bold=True)
    return pic


def _viab_q(rng):
    from cells_common import ctx_get
    data = ctx_get("count_data")
    if data:
        live = sum(d[1] for d in data)
        dead = max(1, sum(d[2] for d in data))
    else:
        live = rng.randint(120, 200)
        dead = rng.randint(6, 40)
    v = 100.0 * live / (live + dead)
    return dict(text="Across the squares you counted %d live (unstained) cells and %d blue cells. What is the viability "
                     "in percent?" % (live, dead), answer=v, unit="% viable", tol=0.01, pic=_viab_pic(live, dead),
                show="%.1f" % v, why="Viability = live / (live + dead) = %d / %d = %.1f %%." % (live, live + dead, v))


def _seed_q(rng):
    wells = rng.choice([6, 12, 24])
    per = rng.choice({6: [1, 2, 3], 12: [0.5, 1], 24: [0.25, 0.5]}[wells])
    own = _own_counts()
    conc = round(sum(own) / float(len(own)) * 2 / 10.0, 1) if own and sum(own) > 0 else rng.choice([4, 5, 8, 10])
    ans = per * 1e5 * wells / (conc * 1e5)
    return dict(text="Your suspension holds %g × 10⁵ cells/mL. You want %g × 10⁵ cells in each of %d wells. How many mL of "
                     "suspension do you need in total?" % (conc, per, wells), answer=ans, unit="mL", tol=0.02,
                why="Cells needed: %g × 10⁵ × %d = %.3g cells. Divided by %g × 10⁵ per mL = %.3g mL." % (per, wells, per * 1e5 * wells, conc, ans))


QUIZ = [
    dict(q="Why do live cells stay unstained by trypan blue?", options=["Their intact membrane keeps the dye out",
         "They digest the dye", "The dye only binds DNA in dividing cells", "Live cells are too small to see the colour"],
         answer=0, why="Trypan blue crosses only damaged membranes, so dead cells turn blue."),
    dict(q="Where does the factor 10⁴ in the haemocytometer formula come from?",
         options=["One large square holds 0.1 µL, and 1 mL is 10⁴ times more", "It is the magnification of the objective",
                  "It corrects for the trypan blue dilution", "It is the number of small squares"], answer=0,
         why="1 mm × 1 mm × 0.1 mm = 0.1 mm³ = 0.1 µL. 1 mL / 0.1 µL = 10⁴."),
    dict(q="Why count cells on the top and left lines but not on the bottom and right lines?",
         options=["So no cell is counted twice in neighbouring squares", "Because those cells are dead",
                  "Because the chamber is deeper there", "It is only a convention for blood cells"], answer=0,
         why="Every square takes the cells on two of its borders, so each border cell belongs to exactly one square."),
    dict(q="Why should a trypan blue count be read within a few minutes?", options=["With longer exposure live cells also take up the dye",
         "The dye fades in light", "The chamber dries out in seconds", "The cells divide"], answer=0,
         why="Trypan blue is toxic over time, so waiting makes viability look worse than it is."),
]

TECH = dict(
    key="count", name="Cell counting", full="Cell counting with a haemocytometer", wing="Cells & embryos", icon="count",
    blurb="Counting cells in a chamber of known volume under the microscope, to know how many cells you have and how many are alive.",
    facts=[
        "Louis-Charles Malassez designed a haemocytometer in 1874 to count blood cells.",
        "In an improved Neubauer chamber each large corner square is 1 mm × 1 mm and 0.1 mm deep, so it holds 0.1 µL.",
        "Trypan blue is excluded by intact membranes, so only dead or damaged cells turn blue.",
        "Counts are most reliable with a few dozen cells per square; dilute the sample if the squares are crowded.",
        "Wallace Coulter patented the Coulter counter in 1953: it counts cells by the change in electrical resistance as each passes through a tiny opening.",
        "Counting on only two of the four borders of each square means no cell is counted twice.",
        "A typical confluent T75 flask of HeLa cells holds roughly 8 million cells.",
    ],
    quiz=QUIZ,
    music=dict(name="Grid Counting Gavotte", bpm=116, beats=4, root=55, mode="maj", prog=[0, 4, 5, 1, 3, 0, 1, 4],
               lead="harpsi", comp="alberti", drums="tick", swing=0.0,
               motif=[(0, 1), (1, 1), (2, 1), (3, 1), (4, 2), (4, 2), (5, 1), (4, 1), (3, 1), (2, 1), (1, 4)]),
    stages=[
        ("count_cells", {}),
        ("cells_calc", dict(title="Cells per mL", problems=[_conc_q, _viab_q, _seed_q], n=3, tint=SKY,
                      instr="Turn your counts into a concentration. Type the answer and press Enter.")),
    ],
)
TECHS = [TECH]
