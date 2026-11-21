# -*- coding: utf-8 -*-
# /// script
# dependencies = [
#   "pygame-ce",
#   "numpy",
# ]
# ///
"""Lab Simulator - entry point, menus, notebook, protocol binder and saving.

The same file runs on the desktop (python main.py) and in a browser (pygbag build)."""
import asyncio
import math
import os
import random
import sys
import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
import gfx
import audio
from core import (text_w, W, H, INK, INK_SOFT, MUTED, CARD, PAPER, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, TEAL, LAV, VIOLET,
                  NIGHT, WHITE, GREEN, YELLOW, clamp, mix, draw_text, draw_wrapped, wrap)
from techniques import TECHS, BY_KEY, WINGS
from station import Station
from board import Board, total_stars, rank, fit_label

for _t in TECHS:
    audio.register(_t["key"], _t["music"])


def fmt_time(sec):
    sec = int(sec)
    return "%d h %02d min" % (sec // 3600, sec // 60 % 60) if sec >= 3600 else "%d min" % (sec // 60)


_LOGO = []


def _logo():
    """The title logo (game/logo.png), loaded once; None if the file is missing."""
    if not _LOGO:
        try:
            _LOGO.append(pygame.image.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")).convert_alpha())
        except Exception:
            _LOGO.append(None)
    return _LOGO[0]


class Menu:
    """Vertical menu, keyboard or mouse."""
    def __init__(self, items, x, y, width=300, gap=52):
        self.items = items
        self.i = 0
        self.x, self.y, self.width, self.gap = x, y, width, gap

    def rect(self, k):
        return pygame.Rect(self.x, self.y + k * self.gap, self.width, self.gap - 10)

    def update(self, inp):
        if "up" in inp.pressed:
            self.i = (self.i - 1) % len(self.items)
            audio.sfx("blip")
        if "down" in inp.pressed:
            self.i = (self.i + 1) % len(self.items)
            audio.sfx("blip")
        for k in range(len(self.items)):
            if self.rect(k).collidepoint(inp.mouse):
                if inp.moved and self.i != k:
                    self.i = k
                    audio.sfx("blip")
                if inp.click:
                    audio.sfx("click")
                    return self.items[k]
        if inp.ok():
            audio.sfx("click")
            return self.items[self.i]
        return None

    def draw(self, s):
        for k, it in enumerate(self.items):
            r = self.rect(k)
            sel = k == self.i
            if sel:
                gfx.rrect(s, r.move(0, 3), mix(SAND, INK, 0.45), INK, 2, 10, 0, False)
            gfx.rrect(s, r.move(0, -2 if sel else 0), SAND if sel else CARD, INK, 2, 10)
            draw_text(s, it, r.move(0, -2 if sel else 0).center, 19, INK, center=True, bold=True, vcenter=True)


# ====================================================================== splash
class Splash:
    """The Juan Lab logo for two seconds at start-up. Any key or click skips it."""
    overlay = False
    LENGTH = 150                    # frames, fades included
    FADE = 24

    def __init__(self, app):
        self.app = app
        self.t = 0
        try:
            img = pygame.image.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "juanlab.png")).convert_alpha()
            self.logo = pygame.transform.smoothscale(img, (150, 150))
        except Exception:
            self.logo = None

    def update(self, inp):
        self.t += 1
        if (inp.pressed or inp.keys or inp.click) and self.t < self.LENGTH - self.FADE:
            self.t = self.LENGTH - self.FADE
        if self.t >= self.LENGTH:
            self.app.stack[-1] = Title(self.app)
            self.app.fade = 14

    def draw(self, s):
        s.fill(PAPER)
        if self.logo is not None:
            s.blit(self.logo, (W // 2 - 75, 128))
        draw_text(s, "Juan Lab", (W // 2, 330), 36, INK, center=True, bold=True, vcenter=True)
        draw_text(s, "Uppsala University", (W // 2, 372), 17, MUTED, center=True, vcenter=True)
        a = 1 - min(1, self.t / self.FADE, (self.LENGTH - self.t) / self.FADE)
        if a > 0:
            gfx.dim(s, int(255 * a), (14, 14, 22))


# ====================================================================== title
class Title:
    overlay = False

    def __init__(self, app):
        self.app = app
        self.t = 0
        self.menu = None
        self.has = None
        audio.music("title")
        self.refresh()

    def refresh(self):
        last = self.app.data["opt"].get("last")
        has = last is not None and self.app.data["slots"][last] is not None
        if has != self.has:
            self.has = has
            items = (["Continue"] if has else []) + ["New game / load", "Free play", "Options"] + ([] if core.WEB else ["Quit"])
            self.menu = Menu(items, W // 2 - 150, 300 - (10 if has else 0))
        return last

    def update(self, inp):
        self.t += 1
        audio.music("title")
        last = self.refresh()
        c = self.menu.update(inp)
        if c == "Continue":
            self.app.slot_i = last
            self.app.push(Board(self.app))
        elif c == "New game / load":
            self.app.push(Slots(self.app))
        elif c == "Free play":
            self.app.push(Binder(self.app, practice=True))
        elif c == "Options":
            self.app.push(Options(self.app))
        elif c == "Quit":
            self.app.running = False

    def resume(self, *a):
        audio.music("title")

    def draw(self, s):
        gfx.menu_bg(s, self.t / 60.0)
        # orbiting technique icons
        for k, t in enumerate(TECHS):
            a = k / len(TECHS) * math.tau + self.t / 900.0
            x = W / 2 + math.cos(a) * 400
            y = 205 + math.sin(a) * 150
            if y > 250:
                continue
            gfx.circle(s, CARD, (x, y), 24)
            gfx.icon(s, t["icon"], (x, y), 30)
        gfx.card(s, (W // 2 - 330, 62, 660, 220), CARD, INK, 20)
        logo = _logo()
        if logo is not None:
            s.blit(logo, (W // 2 - logo.get_width() // 2, 74))
        else:
            draw_text(s, "Lab Simulator", (W // 2, 120), 52, INK, center=True, bold=True)
        self.menu.draw(s)
        draw_text(s, "Mouse to play  ·  Esc to pause  ·  F11 full screen", (W // 2, H - 24), 13, (220, 222, 230), center=True)


class Slots:
    overlay = False

    def __init__(self, app):
        self.app = app
        self.i = 0
        self.confirm = None
        self.t = 0

    def rects(self):
        return [pygame.Rect(W // 2 - 300, 120 + k * 112, 600, 98) for k in range(3)]

    def update(self, inp):
        self.t += 1
        slots = self.app.data["slots"]
        if "back" in inp.pressed:
            if self.confirm is not None:
                self.confirm = None
            else:
                self.app.pop()
            return
        if "up" in inp.pressed:
            self.i = (self.i - 1) % 3
        if "down" in inp.pressed:
            self.i = (self.i + 1) % 3
        pick = None
        for k, r in enumerate(self.rects()):
            dele = pygame.Rect(r.right - 110, r.bottom - 38, 96, 28)
            if r.collidepoint(inp.mouse):
                if inp.moved:
                    self.i = k
                if inp.click:
                    if slots[k] and dele.collidepoint(inp.mouse):
                        self.confirm = k
                        audio.sfx("blip")
                        return
                    pick = k
        if self.confirm is not None:
            if pygame.K_y in inp.keys or (inp.click and pick == self.confirm):
                slots[self.confirm] = None
                if self.app.data["opt"].get("last") == self.confirm:
                    self.app.data["opt"]["last"] = None
                self.app.save()
                self.confirm = None
                audio.sfx("pop")
            elif inp.click or pygame.K_n in inp.keys:
                self.confirm = None
            return
        if inp.ok():
            pick = self.i
        if pick is None:
            return
        audio.sfx("click")
        if slots[pick] is None:
            slots[pick] = core.new_slot()
        self.app.slot_i = pick
        self.app.data["opt"]["last"] = pick
        self.app.save()
        self.app.pop()
        self.app.push(Board(self.app))
        if not slots[pick].get("intro_seen"):
            slots[pick]["intro_seen"] = True
            self.app.push(HowTo(self.app))

    def draw(self, s):
        gfx.menu_bg(s, self.t / 60.0)
        draw_text(s, "Choose a lab notebook", (W // 2, 60), 28, INK, center=True, bold=True)
        for k, r in enumerate(self.rects()):
            sl = self.app.data["slots"][k]
            gfx.card(s, r, SAND if k == self.i else CARD)
            if sl is None:
                draw_text(s, "Notebook %d  ·  empty: start a new game" % (k + 1), (r.x + 24, r.centery), 19, INK, bold=True, vcenter=True)
            else:
                st = total_stars(sl)
                passed = sum(1 for v in sl["best"].values() if v["stars"] >= 1)
                draw_text(s, "Notebook %d  ·  %s" % (k + 1, rank(st)), (r.x + 24, r.y + 14), 19, INK, bold=True)
                draw_text(s, "%d / 60 stars   ·   %d / 20 techniques   ·   %d notebook pages   ·   %s" %
                          (st, passed, len(sl["facts"]), fmt_time(sl.get("time", 0))), (r.x + 24, r.y + 46), 14, INK_SOFT)
                dele = pygame.Rect(r.right - 110, r.bottom - 38, 96, 28)
                gfx.rrect(s, dele, (248, 210, 200), INK, 2, 8)
                draw_text(s, "Delete", dele.center, 14, INK, center=True, bold=True, vcenter=True)
                if self.confirm == k:
                    gfx.alpha_rect(s, r, (250, 220, 210), 235, 14)
                    draw_text(s, "Delete this notebook? Click it again (or press Y) to delete, anywhere else to keep.", r.center, 15, CORAL_D, center=True, bold=True, vcenter=True)
        draw_text(s, "Esc: back", (W // 2, H - 30), 14, (220, 222, 230), center=True)


class HowTo:
    overlay = True

    def __init__(self, app):
        self.app = app
        self.btn = gfx.Button((W // 2 - 90, 446, 180, 42), "Let's go", SAND, size=19)

    def update(self, inp):
        if self.btn.hit(inp) or inp.ok() or "back" in inp.pressed:
            audio.sfx("click")
            self.app.pop()

    def draw(self, s):
        gfx.dim(s, 140)
        r = pygame.Rect(W // 2 - 360, 30, 720, 476)
        gfx.card(s, r, CARD)
        draw_text(s, "Welcome to the lab", (W // 2, 46), 28, INK, center=True, bold=True)
        lines = [
            ("Board", "Roll the dice to move between the 28 benches. Twenty of them are techniques; land on one to play it."),
            ("Techniques", "Each technique is a short run of hands-on steps: find reagents, pipette, calculate, time a reaction, read the result."),
            ("Stars", "Every step scores up to 100. The average gives 1 to 3 stars. Pass all 20 techniques to run your own lab."),
            ("Levels", "Choose Student (more time, at most 2 stars), Researcher or Expert (tighter, earns a gold seal) at each bench."),
            ("Coffee", "You earn coffee from Start, Coffee and Seminar benches, flawless runs and finished wings. Spend one after a roll to move a bench more or less."),
            ("Notebook", "Each step ends with a true fact about the technique. They are kept in your lab notebook."),
            ("Binder", "Any technique you have played can be replayed from the protocol binder to improve your stars."),
        ]
        y = 98
        for head, txt in lines:
            gfx.tag(s, r.x + 30, y, head, SAND, 14)
            y = draw_wrapped(s, txt, (r.x + 160, y + 1), 15, r.w - 190, INK) + 9
        self.btn.draw(s)


class Options:
    overlay = False

    def __init__(self, app):
        self.app = app
        self.i = 0
        self.t = 0

    def items(self):
        o = self.app.data["opt"]
        return [("Music", o["music"]), ("Sound effects", o["sfx"]), ("Full screen", "on" if o["full"] else "off"), ("Back", None)]

    def update(self, inp):
        self.t += 1
        o = self.app.data["opt"]
        n = len(self.items())
        if "up" in inp.pressed:
            self.i = (self.i - 1) % n
        if "down" in inp.pressed:
            self.i = (self.i + 1) % n
        d = ("right" in inp.pressed) - ("left" in inp.pressed)
        for k in range(n):
            r = pygame.Rect(W // 2 - 220, 150 + k * 64, 440, 52)
            if r.collidepoint(inp.mouse):
                if inp.moved:
                    self.i = k
                if inp.click:
                    d = 1 if inp.mouse[0] > r.centerx else -1
                    if k >= 2:
                        d = 1
        if inp.ok():
            d = 1
        if "back" in inp.pressed or (self.i == 3 and d):
            self.app.save()
            self.app.pop()
            return
        if d:
            audio.sfx("blip")
            if self.i == 0:
                o["music"] = clamp(o["music"] + d, 0, 10)
            elif self.i == 1:
                o["sfx"] = clamp(o["sfx"] + d, 0, 10)
            elif self.i == 2:
                o["full"] = not o["full"]
                self.app.apply_display()
            audio.set_volumes(o["music"], o["sfx"])

    def draw(self, s):
        gfx.menu_bg(s, self.t / 60.0)
        draw_text(s, "Options", (W // 2, 80), 30, INK, center=True, bold=True)
        for k, (name, v) in enumerate(self.items()):
            r = pygame.Rect(W // 2 - 220, 150 + k * 64, 440, 52)
            gfx.card(s, r, SAND if k == self.i else CARD)
            draw_text(s, name, (r.x + 20, r.centery), 19, INK, bold=True, vcenter=True)
            if isinstance(v, int):
                gfx.bar(s, (r.right - 220, r.centery - 8, 160, 16), v / 10.0, TURQ)
                draw_text(s, "‹  ›", (r.right - 30, r.centery), 18, INK, center=True, bold=True, vcenter=True)
            elif v is not None:
                draw_text(s, v, (r.right - 30, r.centery), 18, INK, right=True, bold=True, vcenter=True)
        draw_text(s, "Click the left or right half of a bar, or use the arrow keys", (W // 2, H - 40), 14, (220, 222, 230), center=True)


class Pause:
    overlay = True

    def __init__(self, app):
        self.app = app
        self.menu = Menu(["Back to the board", "How to play", "Options", "Save and quit to title"], W // 2 - 160, 200, 320)

    def update(self, inp):
        if "back" in inp.pressed:
            self.app.pop()
            return
        c = self.menu.update(inp)
        if c == "Back to the board":
            self.app.pop()
        elif c == "How to play":
            self.app.pop()
            self.app.push(HowTo(self.app))
        elif c == "Options":
            self.app.push(Options(self.app))
        elif c == "Save and quit to title":
            self.app.save()
            self.app.stack = [Title(self.app)]

    def draw(self, s):
        gfx.dim(s, 140)
        gfx.card(s, (W // 2 - 200, 130, 400, 300), CARD)
        draw_text(s, "Paused", (W // 2, 150), 26, INK, center=True, bold=True)
        self.menu.draw(s)


# ====================================================================== notebook
class Notebook:
    overlay = False

    def __init__(self, app):
        self.app = app
        self.scroll = 0
        self.t = 0
        self.content_h = 0

    def update(self, inp):
        self.t += 1
        if "back" in inp.pressed or "tab" in inp.pressed or (inp.click and pygame.Rect(W - 150, 14, 130, 36).collidepoint(inp.mouse)):
            audio.sfx("click")
            self.app.pop()
            return
        self.scroll -= inp.wheel * 50
        y = inp.axis()[1]
        self.scroll += y * 8
        self.scroll = clamp(self.scroll, 0, max(0, self.content_h - (H - 90)))

    def draw(self, s):
        gfx.bench(s, PEACH, "nb")
        slot = self.app.slot
        seen = set(slot["facts"])
        total = sum(len(t["facts"]) for t in TECHS)
        clip = pygame.Rect(30, 70, W - 60, H - 80)
        gfx.card(s, clip.inflate(0, 6), (252, 248, 236))
        s.set_clip(clip)
        y = 84 - self.scroll
        for t in TECHS:
            got = [(k, f) for k, f in enumerate(t["facts"]) if "%s:%d" % (t["key"], k) in seen]
            col = WINGS[t["wing"]]
            pygame.draw.rect(s, col, (50, y + 2, 8, 22))
            draw_text(s, "%s  (%d / %d)" % (t["full"], len(got), len(t["facts"])), (68, y), 18, INK, bold=True)
            y += 30
            if not got:
                draw_text(s, "No pages yet. Play this technique or land on a Lab notebook bench.", (68, y), 14, MUTED)
                y += 26
            for k, f in got:
                pygame.draw.circle(s, col, (74, y + 9), 4)
                y = draw_wrapped(s, f, (86, y), 15, W - 170, INK) + 6
            y += 12
        s.set_clip(None)
        self.content_h = y + self.scroll - 84
        gfx.hud_bar(s, 66, PAPER)
        draw_text(s, "Lab notebook", (34, 18), 26, INK, bold=True)
        draw_text(s, "%d of %d pages" % (len(seen & {"%s:%d" % (t["key"], k) for t in TECHS for k in range(len(t["facts"]))}), total), (250, 26), 15, INK_SOFT, bold=True)
        gfx.Button((W - 150, 14, 130, 36), "Close", SAND, size=16).draw(s)
        draw_text(s, "Mouse wheel or arrow keys to scroll", (W - 170, 26), 13, MUTED, right=True)


# ====================================================================== binder (choose a technique)
class Binder:
    """Grid of the 20 techniques. practice=True: free play from the title (nothing saved).
    In a game: replay any technique you have played; conference=True: every technique is open."""
    overlay = False

    def __init__(self, app, practice=False, conference=False):
        self.app = app
        self.practice = practice
        self.conference = conference
        self.t = 0
        self.hover = None

    def cell(self, k):
        c, r = k % 5, k // 5
        return pygame.Rect(40 + c * 178, 96 + r * 104, 168, 94)

    def open_(self, t):
        if self.practice or self.conference:
            return True
        return t["key"] in self.app.slot["plays"] or t["key"] in self.app.slot["best"]

    def update(self, inp):
        self.t += 1
        if "back" in inp.pressed or (inp.click and pygame.Rect(W - 150, 20, 130, 36).collidepoint(inp.mouse)):
            audio.sfx("click")
            self.close()
            return
        prev, self.hover = self.hover, None
        for k, t in enumerate(TECHS):
            if self.cell(k).collidepoint(inp.mouse):
                if prev != k:
                    audio.prepare(t["key"])
                self.hover = k
                if inp.click:
                    if self.open_(t):
                        audio.sfx("click")
                        if self.conference:
                            self.app.pop()
                        self.app.push(Station(self.app, t, practice=self.practice))
                    else:
                        audio.sfx("bad")

    def close(self):
        self.app.pop()
        top = self.app.stack[-1] if self.app.stack else None
        if top is not None and hasattr(top, "resume"):
            top.resume()

    def resume(self, *a):
        audio.music("board" if not self.practice else "title")
        if not self.practice and self.app.stack[-2:-1] and hasattr(self.app.stack[-2], "resume"):
            pass

    def draw(self, s):
        gfx.menu_bg(s, self.t / 60.0)
        title = "Free play" if self.practice else "Conference: choose any technique" if self.conference else "Protocol binder"
        gfx.card(s, (24, 16, 560, 70), CARD, INK, 12)
        draw_text(s, title, (40, 24), 26, INK, bold=True)
        if not self.practice and not self.conference:
            draw_text(s, "Replay a technique you have already played to improve your stars.", (40, 62), 14, INK_SOFT)
        elif self.practice:
            draw_text(s, "Every technique, for practice. Nothing is saved.", (40, 62), 14, INK_SOFT)
        gfx.Button((W - 150, 20, 130, 36), "Close", SAND, size=16).draw(s)
        for k, t in enumerate(TECHS):
            r = self.cell(k)
            op = self.open_(t)
            hot = k == self.hover
            rr = r.move(0, -3 if hot and op else 0)
            gfx.card(s, rr, CARD if op else (226, 222, 216))
            col = WINGS[t["wing"]]
            gfx.header(s, rr, col if op else (190, 186, 180), 10)
            gfx.icon(s, t["icon"], (rr.x + 34, rr.y + 50), 36)
            # short name large, full name small below, status line at the bottom
            tw = rr.w - 74
            nsz, nlines = fit_label(t["name"], tw, 15, 12)
            for k, ln in enumerate(nlines):
                draw_text(s, ln, (rr.x + 64, rr.y + 20 + k * (nsz + 3)), nsz, INK if op else MUTED, bold=True)
            full = wrap(t["full"], 11, tw) if len(nlines) == 1 else []
            if full and full[0] != t["name"]:
                if len(full) > 2:
                    full = full[:2]
                    full[1] = full[1].rstrip(" ,") + "…"
                for k, ln in enumerate(full):
                    draw_text(s, ln, (rr.x + 64, rr.y + 40 + k * 14), 11, INK_SOFT if op else MUTED)
            if not self.practice:
                rec = self.app.slot["best"].get(t["key"])
                for j in range(3):
                    gfx.star(s, rr.right - 52 + j * 18, rr.bottom - 14, 7, bool(rec) and j < rec["stars"])
                if not op:
                    draw_text(s, "not visited", (rr.x + 12, rr.bottom - 21), 12, MUTED)
        if self.hover is not None:
            t = TECHS[self.hover]
            gfx.alpha_rect(s, (0, H - 34, W, 34), CARD, 230)
            draw_text(s, t["blurb"] if len(t["blurb"]) < 130 else t["blurb"][:127] + "...", (W // 2, H - 26), 14, INK_SOFT, center=True)


# ====================================================================== ending
class Ending:
    overlay = False

    def __init__(self, app):
        self.app = app
        self.t = 0
        self.p = gfx.Particles()
        self.btn = gfx.Button((W // 2 - 110, 440, 220, 46), "Back to the lab", SAND, size=18)
        audio.music("results")
        audio.sfx("win")

    def update(self, inp):
        self.t += 1
        self.p.update()
        if self.t % 20 == 0:
            self.p.burst(random.randint(100, W - 100), random.randint(60, 200), 24, speed=5)
        if self.t > 60 and (self.btn.hit(inp) or inp.ok() or "back" in inp.pressed):
            self.app.pop()
            top = self.app.stack[-1]
            if hasattr(top, "resume"):
                top.resume()

    def draw(self, s):
        gfx.menu_bg(s, self.t / 60.0)
        slot = self.app.slot
        r = pygame.Rect(W // 2 - 340, 50, 680, 450)
        gfx.card(s, r, (252, 248, 236), INK, 18)
        gfx.rrect(s, (r.x + 14, r.y + 14, r.w - 28, r.h - 28), None, CORAL, 3, 12)
        draw_text(s, "Your own lab", (W // 2, r.y + 40), 34, INK, center=True, bold=True)
        draw_wrapped(s, "You passed all 20 techniques, from PCR to zebrafish microinjection. "
                     "The department has given you a bench, a freezer and a coffee machine of your own.",
                     (r.x + 70, r.y + 100), 18, r.w - 140, INK, center=True)
        st = total_stars(slot)
        draw_text(s, "%d / 60 stars  ·  %s" % (st, rank(st)), (W // 2, r.y + 200), 20, CORAL_D, center=True, bold=True)
        draw_text(s, "%d notebook pages  ·  %d dice rolls  ·  %s in the lab" % (len(slot["facts"]), slot.get("rolls", 0), fmt_time(slot.get("time", 0))),
                  (W // 2, r.y + 236), 15, INK_SOFT, center=True)
        draw_text(s, "Keep playing to collect all 60 stars and every notebook page.", (W // 2, r.y + 290), 15, INK, center=True)
        draw_text(s, "Juan Lab  ·  Uppsala University", (W // 2, r.y + 330), 14, MUTED, center=True)
        self.btn.draw(s)
        self.p.draw(s)


import board as _board
_board.SCREENS.update(Pause=Pause, Notebook=Notebook, Binder=Binder, Ending=Ending)


# ====================================================================== app
class App:
    def __init__(self, headless=False):
        pygame.init()
        self.headless = headless
        self.data = core.load_all()
        self.data["opt"]["full"] = False
        self.slot_i = None
        self.screen = None
        self.apply_display()
        pygame.display.set_caption(core.TITLE)
        try:
            pygame.display.set_icon(pygame.image.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")))
        except Exception:
            pass
        if not headless:
            audio.init()
            audio.set_volumes(self.data["opt"]["music"], self.data["opt"]["sfx"])
        try:
            pygame.key.start_text_input()
        except Exception:
            pass
        self.inp = core.Input()
        self.clock = pygame.time.Clock()
        self.running = True
        self.show_fps = False
        self.stack = [Title(self) if headless else Splash(self)]

    @property
    def slot(self):
        return self.data["slots"][self.slot_i] if self.slot_i is not None else None

    def apply_display(self):
        if core.WEB:
            self.screen = pygame.display.set_mode((W, H))
            return
        flags = pygame.SCALED | pygame.RESIZABLE
        if self.data["opt"]["full"] and not self.headless:
            flags |= pygame.FULLSCREEN
        try:
            self.screen = pygame.display.set_mode((W, H), flags, vsync=1)
        except pygame.error:
            self.screen = pygame.display.set_mode((W, H))

    def push(self, sc):
        self.stack.append(sc)
        if not getattr(sc, "overlay", False):
            self.fade = 14

    def pop(self):
        top = self.stack.pop()
        if not getattr(top, "overlay", False):
            self.fade = 14
        if not self.stack:
            self.running = False

    def save(self):
        core.save_all(self.data)

    def frame(self, events, steps=1):
        self.inp.update(events)
        self.stack[-1].update(self.inp)
        for _ in range(steps - 1):
            if not self.stack:
                break
            self.inp.update([])
            self.stack[-1].update(self.inp)
        if not self.stack:
            return
        k = len(self.stack) - 1
        while k > 0 and self.stack[k].overlay:
            k -= 1
        for sc in self.stack[k:]:
            sc.draw(self.screen)
        if getattr(self, "fade", 0) > 0:
            gfx.dim(self.screen, int(255 * (self.fade / 14.0) ** 1.5), (14, 14, 22))
            self.fade -= 1
        if self.show_fps:
            draw_text(self.screen, "%d fps  sound %s" % (self.clock.get_fps(), "on" if audio.ok else "off"), (W // 2, H - 20), 14, CORAL_D, center=True, bold=True)

    async def run(self):
        dt = 16
        while self.running and self.stack:
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F3:
                    self.show_fps = not self.show_fps
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                    self.data["opt"]["full"] = not self.data["opt"]["full"]
                    self.apply_display()
            self.frame(events, 1 if dt < 25 else 2 if dt < 42 else 3)
            pygame.display.flip()
            dt = self.clock.tick(core.FPS)
            await asyncio.sleep(0)
        if self.slot_i is not None:
            self.save()
        pygame.quit()


async def main():
    await App().run()


if __name__ == "__main__":
    asyncio.run(main())
