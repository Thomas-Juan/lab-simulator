# -*- coding: utf-8 -*-
"""The board: a loop of 28 benches around the lab. Roll the die, move, play what you land on.

20 spaces are techniques; the others are Start (grant renewed: +1 coffee each lap), Lab notebook
(a fun fact), Seminar (a question; right answer = +1 coffee), Coffee (+1), Contamination (back 3)
and Conference (play any technique). A coffee can be spent to move one space more or less after a roll."""
import math
import random
import pygame
import audio
import gfx
from core import (W, H, INK, INK_SOFT, MUTED, CARD, PAPER, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, TEAL, LAV, VIOLET,
                  NIGHT, WHITE, GREEN, RED, YELLOW, clamp, mix, draw_text, draw_wrapped, wrap, text_w)
from techniques import TECHS, BY_KEY, WINGS
from station import Station, stars_for

SCREENS = {}
_ROOM = None   # filled in by main.py: Pause, Notebook, Binder, Ending

LAYOUT = ["START", "pcr", "gel", "extract", "NOTEBOOK", "clone", "transform", "SEMINAR",
          "sanger", "qpcr", "ngs", "COFFEE", "crispr", "ish", "CONFERENCE",
          "sds", "western", "elisa", "CONTAMINATION", "purify", "if", "SEMINAR",
          "culture", "count", "transfect", "NOTEBOOK", "facs", "inject"]
N = len(LAYOUT)
SPECIAL = {
    "START": ("Start", "Grant renewed: +1 coffee every time you pass.", YELLOW),
    "NOTEBOOK": ("Lab notebook", "Read a page from someone's lab notebook.", (252, 244, 224)),
    "SEMINAR": ("Seminar", "Answer a question from the audience. Right: +1 coffee.", (205, 226, 240)),
    "COFFEE": ("Coffee", "The break-room coffee machine works today: +1 coffee.", (226, 200, 170)),
    "CONTAMINATION": ("Contamination!", "Mould in the incubator. Go back 3 spaces.", (226, 236, 190)),
    "CONFERENCE": ("Conference", "Pick any technique to try.", (232, 214, 240)),
}

RANKS = [(0, "Summer student"), (8, "Master's student"), (18, "PhD student"), (30, "Postdoc"), (42, "Group leader"),
         (54, "Professor"), (60, "Nobel laureate")]
TW, TH = 96, 74            # top and bottom row tiles
SW, SH = 96, 64            # side tiles
X0, Y0 = 50, 50


def rank(stars):
    name = RANKS[0][1]
    for need, nm in RANKS:
        if stars >= need:
            name = nm
    return name


def next_rank(stars):
    for need, nm in RANKS:
        if stars < need:
            return need, nm
    return None


def tile_rect(i):
    """Clockwise: top row 0-8 left to right, right column 9-13, bottom row 14-22 right to left, left column 23-27."""
    if i <= 8:
        return pygame.Rect(X0 + i * TW, Y0, TW - 4, TH)
    if i <= 13:
        return pygame.Rect(X0 + 8 * TW, Y0 + TH + 4 + (i - 9) * SH, SW - 4, SH - 4)
    if i <= 22:
        return pygame.Rect(X0 + (22 - i) * TW, Y0 + TH + 4 + 5 * SH, TW - 4, TH)
    return pygame.Rect(X0, Y0 + TH + 4 + (27 - i) * SH, SW - 4, SH - 4)


def total_stars(slot):
    return sum(r["stars"] for r in slot["best"].values())


class Board:
    overlay = False

    def __init__(self, app):
        self.app = app
        self.t = 0
        self.state = "idle"
        self.die = 1
        self.roll_t = 0
        self.target = 0
        self.steps = 0
        self.hop = 0
        self.dir = 1
        self.popup = None
        self.particles = gfx.Particles()
        self.floaters = gfx.Floaters()
        self.hover = None
        self.pos_draw = None
        self.roll_btn = gfx.Button((W // 2 - 80, 360, 160, 46), "Roll the die", SAND, size=18)
        self.go_btn = gfx.Button((W // 2 - 60, 384, 120, 40), "Move", SAND)
        self.minus_btn = gfx.Button((W // 2 - 196, 384, 120, 40), "-1  coffee", (226, 200, 170), size=15)
        self.plus_btn = gfx.Button((W // 2 + 76, 384, 120, 40), "+1  coffee", (226, 200, 170), size=15)
        self.nb_btn = gfx.Button((150, 434, 130, 34), "Lab notebook", CARD, size=15)
        self.bind_btn = gfx.Button((W - 300, 434, 130, 34), "Protocol binder", CARD, size=14)
        audio.music("board")
        for t in TECHS:
            audio.prepare(t["key"])
            break

    @property
    def slot(self):
        return self.app.slot

    def resume(self, key=None, result=None):
        """Called when a station or a sub-screen closes."""
        audio.music("board")
        self.state = "idle"
        self.popup = None
        if result is not None and result["stars"] >= 1:
            self.particles.burst(*tile_rect(LAYOUT.index(key)).center, n=30) if key in LAYOUT else None
        self.check_wings()
        if not self.slot["done"] and all(self.slot["best"].get(t["key"], {"stars": 0})["stars"] >= 1 for t in TECHS):
            self.slot["done"] = True
            self.app.save()
            Ending = SCREENS["Ending"]
            self.app.push(Ending(self.app))

    def check_wings(self):
        """A wing whose five techniques all have a star earns a certificate and two coffees, once."""
        done = self.slot.setdefault("wings", [])
        for wing in WINGS:
            techs = [t for t in TECHS if t["wing"] == wing]
            if wing not in done and all(self.slot["best"].get(t["key"], {"stars": 0})["stars"] >= 1 for t in techs):
                done.append(wing)
                self.slot["coffee"] += 2
                self.popup = {"kind": "msg", "title": "%s wing complete" % wing,
                              "text": "You passed all five %s techniques. The lab manager hands you two coffees and a certificate for the wall." % wing}
                audio.sfx("win")
                self.particles.burst(W // 2, 200, 50, speed=6)
                self.app.save()
                return

    # ------------------------------------------------------------ update
    def update(self, inp):
        self.t += 1
        self.inp = inp
        self.slot["time"] = self.slot.get("time", 0) + 1 / 60.0
        self.particles.update()
        self.floaters.update()
        self.hover = None
        for i in range(N):
            if tile_rect(i).collidepoint(inp.mouse):
                self.hover = i
        if self.popup:
            self.update_popup(inp)
            return
        if "back" in inp.pressed:
            Pause = SCREENS["Pause"]
            self.app.push(Pause(self.app))
            return
        if self.nb_btn.hit(inp) or "tab" in inp.pressed:
            Notebook = SCREENS["Notebook"]
            self.app.push(Notebook(self.app))
            return
        if self.bind_btn.hit(inp):
            Binder = SCREENS["Binder"]
            self.app.push(Binder(self.app, practice=False))
            return
        if self.state == "idle":
            if self.roll_btn.hit(inp) or inp.ok():
                self.state = "rolling"
                self.roll_t = 0
                audio.sfx("dice")
        elif self.state == "rolling":
            self.roll_t += 1
            if self.roll_t % 4 == 0 and self.roll_t < 36:
                self.die = random.randint(1, 6)
                if self.roll_t % 8 == 0:
                    audio.sfx("click")
            if self.roll_t >= 40:
                self.steps = self.die
                self.slot["rolls"] = self.slot.get("rolls", 0) + 1
                self.state = "adjust" if self.slot["coffee"] > 0 else "move"
                self.hop = 0
        elif self.state == "adjust":
            self.minus_btn.enabled = self.steps > 1
            self.plus_btn.enabled = self.steps < 7
            if self.minus_btn.hit(inp) and self.steps > 1:
                self.spend(-1)
            elif self.plus_btn.hit(inp) and self.steps < 7:
                self.spend(1)
            elif self.go_btn.hit(inp) or inp.ok():
                self.state = "move"
                self.hop = 0
            elif "left" in inp.pressed and self.steps > 1:
                self.spend(-1)
            elif "right" in inp.pressed and self.steps < 7:
                self.spend(1)
        elif self.state == "move":
            self.hop += 1
            if self.hop >= 14:
                self.hop = 0
                self.slot["pos"] = (self.slot["pos"] + self.dir) % N
                self.steps -= 1
                audio.sfx("step")
                if self.slot["pos"] == 0 and self.dir == 1:
                    self.slot["coffee"] += 1
                    self.slot["laps"] = self.slot.get("laps", 0) + 1
                    r = tile_rect(0)
                    self.floaters.add(r.centerx, r.y + 10, "Grant renewed! +1 coffee", TEAL, 18)
                    audio.sfx("coffee")
                if self.steps <= 0:
                    quiet = self.dir == -1
                    self.dir = 1
                    self.land(quiet)
                    self.app.save()

    def spend(self, d):
        self.slot["coffee"] -= 1
        self.steps += d
        audio.sfx("coffee")
        self.floaters.add(W // 2, 340, "-1 coffee", CORAL_D, 16)
        if self.slot["coffee"] <= 0:
            self.state = "move"
            self.hop = 0

    def land(self, quiet=False):
        what = LAYOUT[self.slot["pos"]]
        self.state = "idle"
        if quiet:
            return
        if what in BY_KEY:
            self.popup = {"kind": "tech", "tech": BY_KEY[what]}
            audio.prepare(what)          # compose its tune while the player reads the card
        elif what == "NOTEBOOK":
            fid, fact, tech = self.random_fact()
            new = fid not in self.slot["facts"]
            if new:
                self.slot["facts"].append(fid)
            self.popup = {"kind": "fact", "fact": fact, "tech": tech, "new": new}
            audio.sfx("page")
        elif what == "SEMINAR":
            tech = random.choice(TECHS)
            q = dict(random.choice(tech["quiz"]))
            opts = list(enumerate(q["options"]))
            random.shuffle(opts)
            self.popup = {"kind": "seminar", "q": q, "opts": opts, "tech": tech, "chosen": None}
        elif what == "COFFEE":
            self.slot["coffee"] += 1
            self.popup = {"kind": "msg", "title": "Coffee", "text": "The break-room coffee machine works today. +1 coffee.\nSpend coffee after a roll to move one space more or less."}
            audio.sfx("coffee")
        elif what == "CONTAMINATION":
            self.popup = {"kind": "msg", "title": "Contamination!", "text": "Mould is growing in the shared incubator. Everyone goes back three benches while it is cleaned.", "back": 3}
            audio.sfx("lose")
        elif what == "CONFERENCE":
            self.popup = {"kind": "msg", "title": "Conference", "text": "You heard a talk on a method you want to try. Choose any technique.", "conf": True}
            audio.sfx("ding")
        elif what == "START":
            self.slot["coffee"] += 1
            self.popup = {"kind": "msg", "title": "Landed on Start", "text": "Your grant report was praised. One more coffee."}

    def random_fact(self):
        pool = []
        for t in TECHS:
            for k, f in enumerate(t["facts"]):
                fid = "%s:%d" % (t["key"], k)
                if fid not in self.slot["facts"]:
                    pool.append((fid, f, t))
        if not pool:
            t = random.choice(TECHS)
            k = random.randrange(len(t["facts"]))
            return "%s:%d" % (t["key"], k), t["facts"][k], t
        return random.choice(pool)

    # ------------------------------------------------------------ popups
    def popup_rect(self):
        return pygame.Rect(W // 2 - 290, 120, 580, 310)

    def update_popup(self, inp):
        p = self.popup
        r = self.popup_rect()
        if p["kind"] == "tech":
            play = gfx.Button((r.centerx - 200, r.bottom - 62, 190, 44), "Go to the bench", SAND)
            skip = gfx.Button((r.centerx + 10, r.bottom - 62, 190, 44), "Not now", CARD)
            if play.hit(inp) or inp.ok():
                audio.sfx("click")
                self.popup = None
                self.app.push(Station(self.app, p["tech"]))
            elif skip.hit(inp) or "back" in inp.pressed:
                audio.sfx("click")
                self.popup = None
        elif p["kind"] == "seminar":
            if p["chosen"] is None:
                for k, rr in enumerate(self.seminar_rects()):
                    if (inp.click and rr.collidepoint(inp.mouse)) or (pygame.K_1 + k) in inp.keys:
                        p["chosen"] = k
                        if p["opts"][k][0] == p["q"]["answer"]:
                            self.slot["coffee"] += 1
                            audio.sfx("good")
                            self.particles.burst(rr.right - 20, rr.centery, 20)
                            self.floaters.add(rr.centerx, rr.y, "+1 coffee", TEAL, 18)
                        else:
                            audio.sfx("bad")
            else:
                ok = gfx.Button((r.centerx - 80, r.bottom - 10, 160, 40), "OK", SAND)
                if ok.hit(inp) or inp.ok():
                    self.popup = None
        else:
            ok = gfx.Button((r.centerx - 80, r.bottom - 62, 160, 44), "OK", SAND)
            if ok.hit(inp) or inp.ok() or "back" in inp.pressed:
                audio.sfx("click")
                self.popup = None
                if p.get("back"):
                    self.dir = -1
                    self.steps = p["back"]
                    self.state = "move"
                    self.hop = 0
                    self.back_quiet = True
                if p.get("conf"):
                    Binder = SCREENS["Binder"]
                    self.app.push(Binder(self.app, practice=False, conference=True))

    def seminar_rects(self):
        r = self.popup_rect()
        p = self.popup
        y = r.y + 44 + len(wrap(p["q"]["q"], 18, r.w - 60, True)) * 25 + 10
        out = []
        for k, (_, txt) in enumerate(p["opts"]):
            h = max(34, 10 + len(wrap(txt, 15, r.w - 110)) * 20)
            out.append(pygame.Rect(r.x + 30, y, r.w - 60, h))
            y += h + 6
        return out

    # ------------------------------------------------------------ draw
    def draw_tile(self, s, i, hot):
        r = tile_rect(i)
        what = LAYOUT[i]
        if hot:
            r = r.move(0, -3)
        if what in BY_KEY:
            t = BY_KEY[what]
            col = WINGS[t["wing"]]
            rec = self.slot["best"].get(what)
            gfx.shadow(s, r, 6, (2, 3), 80, 4)
            s.blit(gfx.texture(r.w, r.h, (246, 246, 240), 6, 5, 77 + i, 2), r.topleft)
            gfx.rrect(s, r, None, (150, 150, 146), 1, 3)
            tape = pygame.Rect(r.x + 4, r.y + 3, r.w - 8, 11)
            gfx.alpha_rect(s, tape, col, 225, 1)
            for k in range(0, tape.w, 6):
                pygame.draw.line(s, mix(col, WHITE, 0.25), (tape.x + k, tape.y + 2), (tape.x + k + 3, tape.y + 2), 1)
            big = r.h > 66
            ic = (r.centerx - (0 if big else 6), r.y + (31 if big else 30))
            gfx.icon(s, t["icon"], ic, 24 if big else 22)
            name = t["name"]
            sz = 13
            while sz > 9 and text_w(name, sz, True) > r.w - (8 if big else 22):
                sz -= 1
            draw_text(s, name, (r.centerx - (0 if big else 6), r.y + (43 if big else 40)), sz, INK, center=True, bold=True)
            n = rec["stars"] if rec else 0
            if rec and rec.get("expert"):
                gfx.rrect(s, r.inflate(4, 4), None, (214, 160, 40), 3, 6)
                gfx.circle(s, (240, 196, 80), (r.x + 9, r.y + 22), 6, 1, (150, 104, 20))
            if big:
                for k in range(3):
                    gfx.star(s, r.centerx + (k - 1) * 14, r.bottom - 7, 5.5, k < n)
            else:
                for k in range(3):
                    gfx.star(s, r.right - 10, r.y + 22 + k * 12, 4.5, k < n)
        else:
            name, desc, col = SPECIAL[what]
            gfx.shadow(s, r, 6, (2, 3), 80, 4)
            gfx.rrect(s, r, col, (110, 110, 106), 1, 4, 0.06, True)
            self.special_icon(s, what, (r.centerx, r.y + r.h * 0.4), r.h)
            draw_text(s, name, (r.centerx, r.bottom - 17), 12 if len(name) < 13 else 11, INK, center=True, bold=True)

    def special_icon(self, s, what, c, h):
        x, y = int(c[0]), int(c[1])
        k = h / 74.0
        if what == "START":
            draw_text(s, "GO", (x, y), int(24 * k) + 4, CORAL_D, center=True, bold=True, vcenter=True)
        elif what == "NOTEBOOK":
            gfx.rrect(s, (x - 14 * k, y - 16 * k, 28 * k, 30 * k), (250, 250, 240), INK, 2, 3)
            for j in range(3):
                pygame.draw.line(s, MUTED, (x - 9 * k, y - 8 * k + j * 7 * k), (x + 9 * k, y - 8 * k + j * 7 * k), 1)
        elif what == "SEMINAR":
            gfx.rrect(s, (x - 18 * k, y - 16 * k, 36 * k, 22 * k), CARD, INK, 2, 2)
            pygame.draw.line(s, INK, (x, y + 6 * k), (x, y + 14 * k), 2)
            draw_text(s, "?", (x, y - 6 * k), int(16 * k) + 4, CORAL_D, center=True, bold=True, vcenter=True)
        elif what == "COFFEE":
            gfx.rrect(s, (x - 12 * k, y - 10 * k, 22 * k, 22 * k), CARD, INK, 2, 4)
            pygame.draw.circle(s, INK, (int(x + 12 * k), int(y)), int(6 * k), 2)
            for j in (-5, 1):
                pygame.draw.arc(s, MUTED, (x + j * k - 3, y - 24 * k, 8, 12 * k), 1.6, 4.6, 2)
        elif what == "CONTAMINATION":
            for dx, dy in ((-8, -4), (6, -8), (2, 6), (-4, 8)):
                gfx.circle(s, (170, 200, 90), (x + dx * k, y + dy * k), 5 * k, 1)
        elif what == "CONFERENCE":
            gfx.rrect(s, (x - 16 * k, y - 14 * k, 32 * k, 20 * k), (60, 70, 120), INK, 2, 2)
            gfx.line(s, YELLOW, (x - 10 * k, y - 4 * k), (x + 8 * k, y - 8 * k), 2)

    def token_pos(self):
        i = self.slot["pos"]
        c = pygame.Vector2(tile_rect(i).center)
        if self.state == "move" and self.steps > 0:
            j = (i + self.dir) % N
            c2 = pygame.Vector2(tile_rect(j).center)
            f = self.hop / 14.0
            p = c.lerp(c2, f)
            p.y -= math.sin(f * math.pi) * 26
            return p
        return c + pygame.Vector2(0, math.sin(self.t / 20.0) * 2)

    def draw_token(self, s, p):
        squash = 0.0
        if self.state == "move" and self.steps > 0:
            f = self.hop / 14.0
            squash = max(0.0, 1 - f * 6) if f < 0.2 else 0.0
        gfx.scientist(s, int(p.x), int(p.y) + 22, self.t / 60.0, squash)

    def draw(self, s):
        global _ROOM
        if _ROOM is None:
            import real
            outer = pygame.Rect(X0 - 8, Y0 - 8, 9 * TW + 12, TH * 2 + 5 * SH + 4 + 16)
            inner = pygame.Rect(X0 + TW - 2, Y0 + TH + 2, 7 * TW - 2 + 4, 5 * SH + 4 - 2)
            _ROOM = real.lab_room((outer, inner))
        s.blit(_ROOM, (0, 0))
        # central panel
        inner = pygame.Rect(X0 + TW + 6, Y0 + TH + 10, 8 * TW - TW - 16 + 4, 5 * SH - 12)
        gfx.card(s, inner, (252, 248, 238), INK, 16)
        slot = self.slot
        st = total_stars(slot)
        mastered = sum(1 for t in TECHS if slot["best"].get(t["key"], {"stars": 0})["stars"] >= 1)
        draw_text(s, "Lab Simulator", (inner.x + 24, inner.y + 14), 26, INK, bold=True)
        draw_text(s, rank(st), (inner.x + 26, inner.y + 50), 16, CORAL_D, bold=True)
        nr = next_rank(st)
        if nr:
            draw_text(s, "%d more stars to become %s" % (nr[0] - st, nr[1]), (inner.x + 26, inner.y + 72), 13, MUTED)
        # stats
        sx = inner.right - 250
        gfx.star(s, sx, inner.y + 30, 12, True)
        draw_text(s, "%d / 60 stars" % st, (sx + 18, inner.y + 21), 16, INK, bold=True)
        draw_text(s, "%d / 20 techniques passed" % mastered, (sx - 10, inner.y + 46), 14, INK_SOFT)
        for k in range(min(slot["coffee"], 8)):
            self.cup(s, sx + k * 22, inner.y + 82)
        draw_text(s, "coffee" if slot["coffee"] else "no coffee left", (sx + min(slot["coffee"], 8) * 22 + 6, inner.y + 74), 13, MUTED)
        # hovered tile info or the turn
        info = self.hover if self.hover is not None else None
        mid = pygame.Rect(inner.x + 20, inner.y + 98, inner.w - 40, 92)
        if info is not None and self.state in ("idle", "adjust") and not self.popup:
            what = LAYOUT[info]
            gfx.rrect(s, mid, CARD, INK, 2, 10)
            if what in BY_KEY:
                t = BY_KEY[what]
                gfx.icon(s, t["icon"], (mid.x + 40, mid.centery), 44)
                draw_text(s, t["full"], (mid.x + 80, mid.y + 10), 17, INK, bold=True)
                draw_wrapped(s, t["blurb"], (mid.x + 80, mid.y + 34), 13, mid.w - 100, INK_SOFT)
            else:
                name, desc, col = SPECIAL[what]
                draw_text(s, name, (mid.x + 20, mid.y + 14), 17, INK, bold=True)
                draw_wrapped(s, desc, (mid.x + 20, mid.y + 40), 14, mid.w - 40, INK_SOFT)
        else:
            what = LAYOUT[slot["pos"]]
            here = BY_KEY[what]["full"] if what in BY_KEY else SPECIAL[what][0]
            draw_text(s, "You are at: " + here, (mid.centerx, mid.y + 10), 15, INK_SOFT, center=True, bold=True)
            if self.state in ("idle", "rolling"):
                draw_text(s, "Roll the die to move around the lab. Hover over a bench to read about it.", (mid.centerx, mid.y + 34), 13, MUTED, center=True)
        # die and controls
        rot = (math.sin(self.roll_t * 0.7) * 25) if self.state == "rolling" else 0
        dy = -abs(math.sin(self.roll_t / 5.0)) * 16 if self.state == "rolling" else 0
        gfx.die(s, (inner.x + 70, int(inner.y + 228 + dy)), self.die, 54, rot)
        if self.state == "idle" and not self.popup:
            self.roll_btn.rect.center = (W // 2, inner.y + 228)
            self.roll_btn.draw(s, getattr(self, 'inp', None))
        elif self.state == "adjust":
            for b in (self.minus_btn, self.go_btn, self.plus_btn):
                b.rect.centery = inner.y + 228
            self.go_btn.label = "Move %d" % self.steps
            self.minus_btn.draw(s, getattr(self, 'inp', None))
            self.go_btn.draw(s, getattr(self, 'inp', None))
            self.plus_btn.draw(s, getattr(self, 'inp', None))
        self.nb_btn.rect.topleft = (inner.x + 20, inner.bottom - 46)
        self.bind_btn.rect.topright = (inner.right - 20, inner.bottom - 46)
        self.nb_btn.draw(s, getattr(self, 'inp', None))
        self.bind_btn.draw(s, getattr(self, 'inp', None))
        # wing legend
        for k, (wing, wc) in enumerate(WINGS.items()):
            x = inner.centerx - 118 + (k % 2) * 128
            y = inner.bottom - 44 + (k // 2) * 18
            gfx.rrect(s, (x, y + 2, 12, 12), wc, INK, 1, 3, 0.2)
            draw_text(s, wing, (x + 17, y), 12, INK_SOFT, bold=True)
        # tiles, with a pulsing light under the bench you are on
        here = tile_rect(slot["pos"])
        pulse = 0.5 + 0.5 * math.sin(self.t / 14.0)
        gfx.alpha_rect(s, here.inflate(12 + 4 * pulse, 12 + 4 * pulse).move(-2 * pulse, -2 * pulse), YELLOW, int(70 + 60 * pulse), 14)
        for i in range(N):
            self.draw_tile(s, i, i == self.hover)
        if self.state == "adjust" and not self.popup:
            tr = tile_rect((slot["pos"] + self.steps) % N)
            gfx.rrect(s, tr.inflate(8, 8), None, CORAL, 3, 12)
        self.draw_token(s, self.token_pos())
        self.particles.draw(s)
        self.floaters.draw(s)
        if self.popup:
            self.draw_popup(s)

    def cup(self, s, x, y):
        pygame.draw.circle(s, INK, (x + 8, y), 4, 2)
        gfx.rrect(s, (x - 8, y - 8, 15, 16), CARD, INK, 2, 3)
        gfx.rrect(s, (x - 6, y - 6, 11, 5), (120, 80, 50), None, 0, 2, 0.2)

    def draw_popup(self, s):
        p = self.popup
        gfx.dim(s, 130)
        r = self.popup_rect()
        if p["kind"] == "seminar":
            r = r.inflate(0, 90).move(0, 10)
        gfx.card(s, r, CARD)
        if p["kind"] == "tech":
            t = p["tech"]
            col = WINGS[t["wing"]]
            gfx.header(s, r, col, 70)
            gfx.circle(s, CARD, (r.x + 50, r.y + 37), 27)
            gfx.icon(s, t["icon"], (r.x + 50, r.y + 37), 36)
            draw_text(s, t["full"], (r.x + 92, r.y + 22), 22, WHITE, bold=True, shadow=mix(col, INK, 0.5))
            draw_wrapped(s, t["blurb"], (r.x + 30, r.y + 88), 16, r.w - 60, INK)
            rec = self.slot["best"].get(t["key"])
            if rec:
                draw_text(s, "Best score %d" % rec["score"], (r.centerx - 60, r.bottom - 100), 14, INK_SOFT, bold=True)
                gfx.stars(s, r.centerx + 60, r.bottom - 92, rec["stars"], 10, 24)
            else:
                draw_text(s, "%d steps, about %d minutes" % (len(t["stages"]), max(2, len(t["stages"]))), (r.centerx, r.bottom - 100), 14, INK_SOFT, center=True, bold=True)
            gfx.Button((r.centerx - 200, r.bottom - 62, 190, 44), "Go to the bench", SAND).draw(s)
            gfx.Button((r.centerx + 10, r.bottom - 62, 190, 44), "Not now", CARD).draw(s)
        elif p["kind"] == "fact":
            t = p["tech"]
            draw_text(s, "Lab notebook", (r.centerx, r.y + 18), 22, INK, center=True, bold=True)
            draw_text(s, t["full"] + ("   ·   new page" if p["new"] else ""), (r.centerx, r.y + 50), 14, CORAL_D, center=True, bold=True)
            draw_wrapped(s, p["fact"], (r.x + 40, r.y + 86), 18, r.w - 80, INK, center=True)
            gfx.Button((r.centerx - 80, r.bottom - 62, 160, 44), "OK", SAND).draw(s)
        elif p["kind"] == "seminar":
            q = p["q"]
            draw_text(s, "Seminar question  ·  " + p["tech"]["name"], (r.x + 30, r.y + 24), 14, CORAL_D, bold=True)
            if p["chosen"] is None:
                draw_text(s, "click an answer or press its number", (r.right - 30, r.y + 24), 13, MUTED, right=True)
            draw_wrapped(s, q["q"], (r.x + 30, self.popup_rect().y + 44), 18, r.w - 60, INK, bold=True, lh=25)
            for k, rr in enumerate(self.seminar_rects()):
                idx, txt = p["opts"][k]
                col = CARD
                if p["chosen"] is not None:
                    if idx == q["answer"]:
                        col = (196, 236, 200)
                    elif k == p["chosen"]:
                        col = (248, 200, 190)
                gfx.rrect(s, rr, col, INK, 2, 8)
                draw_text(s, str(k + 1), (rr.x + 16, rr.y + 8), 14, MUTED, bold=True)
                draw_wrapped(s, txt, (rr.x + 40, rr.y + 7), 15, rr.w - 60, INK)
            if p["chosen"] is not None:
                last = self.seminar_rects()[-1]
                draw_wrapped(s, q.get("why", ""), (r.x + 30, last.bottom + 8), 14, r.w - 60, INK_SOFT)
                gfx.Button((r.centerx - 80, r.bottom - 10, 160, 40), "OK", SAND).draw(s)
        else:
            draw_text(s, p["title"], (r.centerx, r.y + 22), 24, INK, center=True, bold=True)
            draw_wrapped(s, p["text"], (r.x + 50, r.y + 80), 18, r.w - 100, INK, center=True)
            gfx.Button((r.centerx - 80, r.bottom - 62, 160, 44), "OK", SAND).draw(s)
