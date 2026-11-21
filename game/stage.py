# -*- coding: utf-8 -*-
"""Minigame ("stage") base class, the stage registry and the generic stage types
shared by several techniques: Quiz, Order, Calc, Stop and Match.

A technique (see techniques.py) is a list of stages played one after another at a
station on the board. Every stage scores 0-100.

Writing a stage
---------------
    @register("mystage")
    class MyStage(Stage):
        title = "Default title"            # can be overridden with title=... in the params
        instr = "One or two sentences on how to play."
        limit = 30                          # seconds, or None for no timer (params: limit=...)

        def setup(self):                    # called once; self.p holds the params, self.rng a Random
            ...
        def tick(self, inp):                # called every frame (60 per second) while playing
            ...                             # call self.finish(score, "feedback line", ...) when done
        def render(self, s):                # draw the playing field (y from 48 to 540; HUD is drawn on top)
            ...
        def partial(self):                  # score to give when the timer runs out (default 0)
            ...
        def autoplay(self):                 # tests only: finish the stage as a good player would
            self.finish(90, "auto")

Input (core.Input): inp.mouse, inp.click, inp.down, inp.release, inp.wheel, inp.keys (raw key codes),
inp.pressed (actions: ok, space, left, right, up, down, back), inp.text (typed characters).
Escape is handled by the station (pause menu), never by stages.
Difficulty: self.level is 0 (Student), 1 (Researcher) or 2 (Expert). Timers (self.limit) are already
scaled by the base class; scale your own tolerances, speeds and counts with self.lv(easy, normal, hard).
Helpers: self.floaters.add(x, y, "+10"), self.particles.burst(x, y), audio.sfx(name),
self.hint = "short reminder shown at the bottom".
Sound effects: blip, click, good, bad, pour, pop, tick, buzz, beep, ding, whoosh, splash, win, lose."""
import math
import random
import pygame
import audio
import gfx
from core import (W, H, INK, INK_SOFT, MUTED, CARD, PAPER, PAPER2, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, TEAL,
                  LAV, VIOLET, NIGHT, WHITE, GREEN, RED, YELLOW, clamp, mix, draw_text, draw_wrapped, wrap, text_w)

STAGES = {}
TOP = 52          # playing field starts below the HUD bar
BOTTOM = H - 30   # and ends above the hint line


def register(name):
    def deco(cls):
        STAGES[name] = cls
        cls.kind = name
        return cls
    return deco


class Stage:
    kind = "stage"
    title = "Stage"
    instr = ""
    limit = None
    end_delay = 50          # frames the final state stays on screen before the result card

    def __init__(self, ctx, **p):
        self.ctx = ctx
        self.p = p
        self.rng = getattr(ctx, "rng", None) or random.Random()
        self.title = p.get("title", self.title)
        self.instr = p.get("instr", self.instr)
        self.limit = p.get("limit", self.limit)
        # difficulty: 0 Student, 1 Researcher, 2 Expert (chosen at the station); timers scale with it
        self.level = int(getattr(ctx, "level", 1))
        if self.limit:
            self.limit = round(self.limit * (1.3, 1.0, 0.8)[self.level])
        self.t = 0
        self.score = 0
        self.done = False
        self.feedback = []
        self.hint = p.get("hint", "")
        self.particles = gfx.Particles()
        self.floaters = gfx.Floaters()
        self.shake = 0
        self.setup()

    # -- to override
    def setup(self):
        pass

    def tick(self, inp):
        pass

    def render(self, s):
        gfx.bench(s)

    def partial(self):
        return 0

    def autoplay(self):
        self.finish(90, "(autoplay)")

    # -- helpers
    def lv(self, easy, normal, hard):
        """Pick a value for the current difficulty level."""
        return (easy, normal, hard)[self.level]

    def left(self):
        if self.limit is None:
            return None
        return max(0.0, self.limit - self.t / 60.0)

    def finish(self, score, *feedback):
        if self.done:
            return
        self.score = int(round(clamp(score, 0, 100)))
        self.feedback = [f for f in feedback if f]
        self.done = True
        self.t_done = self.t

    def update(self, inp):
        self.particles.update()
        self.floaters.update()
        if self.shake:
            self.shake -= 1
        if self.done:
            return
        self.t += 1
        if self.limit is not None and self.left() <= 0:
            audio.sfx("buzz")
            self.finish(self.partial(), "Time ran out.")
            return
        if self.limit is not None and self.left() <= 5 and self.t % 60 == 0:
            audio.sfx("tick")
        self.tick(inp)

    def draw(self, s):
        self.render(s)
        self.particles.draw(s)
        self.floaters.draw(s)

    def ready(self):
        """True once the result card may be shown."""
        return self.done and self.t_done is not None and getattr(self, "_post", 0) >= self.end_delay

    def post_tick(self):
        self._post = getattr(self, "_post", 0) + 1

    t_done = None


def cached_pic(s, q, rect):
    """Draw q["pic"] into rect once, then reuse the result (pictures are static)."""
    key = (rect.x, rect.y, rect.w, rect.h)
    if q.get("_pic_key") != key:
        layer = pygame.Surface((W, H))
        layer.blit(s, (0, 0))          # opaque copy of what is behind, so anti-aliasing blends correctly
        q["pic"](layer, pygame.Rect(rect))
        q["_pic_surf"] = layer.subsurface(pygame.Rect(rect).clip(layer.get_rect())).copy()
        q["_pic_key"] = key
    s.blit(q["_pic_surf"], rect.topleft)


def pic_frame(s, rect, fill=CARD):
    gfx.card(s, rect, fill, INK, 12)


# ======================================================================= Quiz
@register("quiz")
class QuizStage(Stage):
    """Multiple choice with an optional picture.

    params: questions = list of dicts or callables(rng) -> dict with keys
        q (question), options (list of str), answer (index into options), why (explanation),
        pic (optional callable(surface, rect) drawing a picture in rect)
    n = how many questions to ask (default 3, drawn at random)."""
    title = "Quick check"
    instr = "Click the right answer (or press 1-4)."

    def setup(self):
        qs = list(self.p.get("questions", []))
        self.rng.shuffle(qs)
        n = self.p.get("n", 3)
        self.qs = []
        for q in qs[:n]:
            q = q(self.rng) if callable(q) else dict(q)
            opts = list(enumerate(q["options"]))
            if not q.get("keep_order"):
                self.rng.shuffle(opts)
            q["_opts"] = opts
            self.qs.append(q)
        self.i = 0
        self.right = 0
        self.chosen = None
        self.next_btn = gfx.Button((W - 200, BOTTOM - 54, 160, 42), "Next", SAND)

    def layout(self):
        q = self.qs[self.i]
        has_pic = q.get("pic") is not None
        x0 = 500 if has_pic else 120
        width = W - x0 - 40
        return has_pic, x0, width

    def sizes(self):
        """Font sizes (question, options) that make this question fit the card."""
        q = self.qs[self.i]
        if "_sz" not in q:
            has_pic, x0, width = self.layout()
            for qs, os_, lh, gap in ((20, 17, 22, 8), (18, 15, 19, 6), (17, 14, 18, 5)):
                y = TOP + 44 + len(wrap(q["q"], qs, width, True)) * int(qs * 1.38) + 14
                for _, txt in q["_opts"]:
                    y += max(36, 12 + len(wrap(txt, os_, width - 60)) * lh) + gap
                why_h = len(wrap(q.get("why", ""), 15, width - 180)) * 21
                if y + why_h + 16 <= BOTTOM - 20:
                    break
            q["_sz"] = (qs, os_, lh, gap)
        return q["_sz"]

    def option_rects(self):
        has_pic, x0, width = self.layout()
        q = self.qs[self.i]
        qs, os_, lh, gap = self.sizes()
        y = TOP + 44 + len(wrap(q["q"], qs, width, True)) * int(qs * 1.38) + 14
        rects = []
        for k, (_, txt) in enumerate(q["_opts"]):
            lines = wrap(txt, os_, width - 60)
            h = max(36, 12 + len(lines) * lh)
            rects.append(pygame.Rect(x0, y, width, h))
            y += h + gap
        return rects

    def tick(self, inp):
        if not self.qs:
            self.finish(100)
            return
        q = self.qs[self.i]
        rects = self.option_rects()
        if self.chosen is None:
            pick = None
            for k, r in enumerate(rects):
                if inp.click and r.collidepoint(inp.mouse):
                    pick = k
                if (pygame.K_1 + k) in inp.keys or (pygame.K_KP1 + k) in inp.keys:
                    pick = k
            if pick is not None:
                self.chosen = pick
                if q["_opts"][pick][0] == q["answer"]:
                    self.right += 1
                    audio.sfx("good")
                    self.particles.burst(rects[pick].right - 30, rects[pick].centery, 14)
                else:
                    audio.sfx("bad")
                    self.shake = 12
        else:
            if self.next_btn.hit(inp) or inp.ok():
                audio.sfx("click")
                self.i += 1
                self.chosen = None
                if self.i >= len(self.qs):
                    n = len(self.qs)
                    self.finish(100.0 * self.right / n, "%d of %d answers right." % (self.right, n))
                    self.i = n - 1
                    self.chosen = -1

    def render(self, s):
        gfx.bench(s, self.p.get("tint", LAV))
        if not self.qs:
            return
        q = self.qs[self.i]
        has_pic, x0, width = self.layout()
        if has_pic:
            r = pygame.Rect(30, TOP + 16, 440, BOTTOM - TOP - 30)
            pic_frame(s, r)
            cached_pic(s, q, r.inflate(-16, -16))
        gfx.card(s, (x0 - 20, TOP + 10, width + 40, BOTTOM - TOP - 20), CARD)
        draw_text(s, "Question %d of %d" % (self.i + 1, len(self.qs)), (x0, TOP + 22), 13, MUTED, bold=True)
        qs, os_, lh, gap = self.sizes()
        draw_wrapped(s, q["q"], (x0, TOP + 44), qs, width, INK, bold=True)
        answered = self.chosen is not None
        for k, r in enumerate(self.option_rects()):
            idx, txt = q["_opts"][k]
            col = CARD
            if answered:
                if idx == q["answer"]:
                    col = (196, 236, 200)
                elif k == self.chosen:
                    col = (248, 200, 190)
            dx = int(math.sin(self.shake * 1.7) * 5) if (answered and k == self.chosen and idx != q["answer"]) else 0
            gfx.rrect(s, r.move(dx, 0), col, INK, 2, 10)
            gfx.circle(s, SAND, (r.x + 22 + dx, r.y + 18), 12)
            draw_text(s, str(k + 1), (r.x + 22 + dx, r.y + 18), 14, INK, center=True, bold=True, vcenter=True)
            draw_wrapped(s, txt, (r.x + 46 + dx, r.y + 7), os_, r.w - 60, INK, lh=lh)
        if answered and self.chosen != -1:
            why = q.get("why", "")
            rr = self.option_rects()[-1]
            y = rr.bottom + 10
            if why:
                draw_wrapped(s, why, (x0, y), 15, width - 180, INK_SOFT)
            self.next_btn.draw(s)


# ======================================================================= Order
@register("order")
class OrderStage(Stage):
    """Put the steps of a protocol in order by clicking them one after another.

    params: steps = [step, ...] in the correct order; a step is a str or (label, colour) or
            (label, colour, explanation).
            style = "list" (protocol sheet) or "stack" (layers build up from the bottom, e.g. a blot sandwich)
            heading = text above the protocol sheet."""
    title = "Protocol order"
    instr = "Click the steps in the order you would do them."
    limit = 60

    def setup(self):
        self.steps = []
        for st in self.p["steps"]:
            if isinstance(st, str):
                st = (st, SAND, "")
            elif len(st) == 2:
                st = (st[0], st[1], "")
            self.steps.append(st)
        n = len(self.steps)
        order = list(range(n))
        while n > 1 and order == list(range(n)):
            self.rng.shuffle(order)
        self.cards = []
        cols = 2 if n > 5 else 1
        cw = 250 if cols == 2 else 360
        for k, i in enumerate(order):
            c, r = k % cols, k // cols
            rect = pygame.Rect(40 + c * (cw + 16), TOP + 50 + r * 56, cw, 46)
            self.cards.append({"i": i, "rect": rect, "home": rect.copy(), "placed": False, "shake": 0})
        self.next = 0
        self.mistakes = 0
        self.last_why = ""
        self.style = self.p.get("style", "list")

    def slot_rect(self, k):
        n = len(self.steps)
        if self.style == "stack":
            h = min(40, int((BOTTOM - TOP - 110) / n))
            return pygame.Rect(600, BOTTOM - 60 - (k + 1) * h, 300, h - 2)
        h = min(46, int((BOTTOM - TOP - 90) / n))
        return pygame.Rect(600, TOP + 50 + k * h, 320, h - 6)

    def tick(self, inp):
        for c in self.cards:
            if c["shake"]:
                c["shake"] -= 1
            if c["placed"]:
                tgt = self.slot_rect(c["slot"])
                c["rect"].x += (tgt.x - c["rect"].x) * 0.25
                c["rect"].y += (tgt.y - c["rect"].y) * 0.25
                c["rect"].w += (tgt.w - c["rect"].w) * 0.25
                c["rect"].h += (tgt.h - c["rect"].h) * 0.25
        if inp.click:
            for c in self.cards:
                if not c["placed"] and c["rect"].collidepoint(inp.mouse):
                    if c["i"] == self.next:
                        c["placed"] = True
                        c["slot"] = self.next
                        self.last_why = self.steps[c["i"]][2]
                        self.next += 1
                        audio.sfx("click")
                        self.floaters.add(inp.mouse[0], inp.mouse[1] - 10, "step %d" % self.next, GREEN, 16)
                        if self.next == len(self.steps):
                            audio.sfx("good")
                            sc = 100 - self.lv(10, 15, 20) * self.mistakes
                            self.finish(sc, "Perfect order!" if not self.mistakes else "%d wrong click%s." % (self.mistakes, "s" if self.mistakes > 1 else ""))
                    else:
                        self.mistakes += 1
                        c["shake"] = 16
                        audio.sfx("bad")
                        self.floaters.add(inp.mouse[0], inp.mouse[1] - 10, "not yet", RED, 16)
                    break

    def partial(self):
        return max(0, 100 * self.next / len(self.steps) - 15 * self.mistakes - 20)

    def autoplay(self):
        self.finish(85)

    def render(self, s):
        gfx.bench(s, self.p.get("tint", SAND))
        gfx.card(s, (580, TOP + 10, 360, BOTTOM - TOP - 20), (250, 248, 240))
        draw_text(s, self.p.get("heading", "Protocol"), (760, TOP + 18), 18, INK, center=True, bold=True)
        if self.style == "stack":
            r = self.slot_rect(0)
            gfx.metal_rect(s, (r.x - 10, r.bottom + 4, r.w + 20, 12), (90, 92, 104), 3)
            top = self.slot_rect(len(self.steps) - 1)
            draw_text(s, self.p.get("bottom_label", ""), (r.centerx, r.bottom + 18), 13, INK_SOFT, center=True, bold=True)
            draw_text(s, self.p.get("top_label", ""), (top.centerx, top.y - 22), 13, INK_SOFT, center=True, bold=True)
        else:
            for k in range(len(self.steps)):
                r = self.slot_rect(k)
                gfx.rrect(s, r, None, mix(CARD, INK, 0.25), 1, 8)
                draw_text(s, str(k + 1), (r.x - 14, r.centery), 14, MUTED, center=True, bold=True, vcenter=True)
        gfx.tag(s, 40, TOP + 12, "Steps: click them in order", CARD, 15)
        for c in self.cards:
            r = pygame.Rect(c["rect"])
            dx = int(math.sin(c["shake"] * 1.6) * 6) if c["shake"] else 0
            label, col, _ = self.steps[c["i"]]
            fill = col if not c["placed"] else mix(col, WHITE, 0.2)
            gfx.rrect(s, r.move(dx, 0), fill, INK, 2, 8)
            sz = 15 if r.h > 28 else 13
            while sz > 10 and text_w(label, sz, True) > r.w - 12:
                sz -= 1
            draw_text(s, label, (r.centerx + dx, r.centery), sz, INK, center=True, bold=True, vcenter=True)
        if self.last_why:
            lines = wrap(self.last_why, 15, 500)
            box = pygame.Rect(30, BOTTOM - 26 - len(lines) * 21, 540, len(lines) * 21 + 16)
            gfx.card(s, box, CARD, INK, 10)
            draw_wrapped(s, self.last_why, (box.x + 14, box.y + 8), 15, 500, INK_SOFT)


# ======================================================================= Calc
@register("calc")
class CalcStage(Stage):
    """Type a number. params: problems = list of dicts or callables(rng) -> dict with
    text, answer (float), unit, tol (relative tolerance, default 0.02), why, pic (optional callable(s, rect)).
    n = number of problems (default 2)."""
    title = "Bench maths"
    instr = "Type the answer and press Enter. Use the keypad or the keyboard."

    def setup(self):
        ps = list(self.p.get("problems", []))
        self.rng.shuffle(ps)
        self.ps = [(q(self.rng) if callable(q) else dict(q)) for q in ps[:self.p.get("n", 2)]]
        self.i = 0
        self.entry = ""
        self.res = None      # None | (ok_level, score)
        self.total = 0
        keys = ["7", "8", "9", "4", "5", "6", "1", "2", "3", "0", ".", "<"]
        self.pad = []
        for k, lab in enumerate(keys):
            self.pad.append(gfx.Button((640 + (k % 3) * 66, 192 + (k // 3) * 52, 58, 44), lab, CARD, size=20))
        self.enter = gfx.Button((640, 410, 190, 40), "Enter", SAND)
        self.next_btn = gfx.Button((640, 430, 190, 40), "Next", SAND)

    def add(self, ch):
        if ch == "<":
            self.entry = self.entry[:-1]
        elif ch == "." and "." in self.entry:
            return
        elif len(self.entry) < 10:
            self.entry += ch
        audio.sfx("blip")

    def check(self):
        q = self.ps[self.i]
        try:
            v = float(self.entry)
        except ValueError:
            audio.sfx("bad")
            return
        a = float(q["answer"])
        tol = q.get("tol", 0.02) * self.lv(1.5, 1.0, 0.75)
        err = abs(v - a) / max(abs(a), 1e-9)
        if err <= tol:
            sc, lvl = 100, 2
        elif err <= tol * 4 + 0.02:
            sc, lvl = 50, 1
        else:
            sc, lvl = 0, 0
        self.res = (lvl, sc)
        self.total += sc
        audio.sfx("good" if lvl == 2 else "bad")
        if lvl == 2:
            self.particles.burst(735, 200, 20)

    def tick(self, inp):
        if not self.ps:
            self.finish(100)
            return
        if self.res is None:
            for ch in inp.text:
                if ch in "0123456789.":
                    self.add(ch)
                elif ch == ",":
                    self.add(".")
            if pygame.K_BACKSPACE in inp.keys:
                self.add("<")
            for b in self.pad:
                if inp.click and b.rect.collidepoint(inp.mouse):
                    self.add(b.label)
            if (self.enter.hit(inp) or pygame.K_RETURN in inp.keys or pygame.K_KP_ENTER in inp.keys) and self.entry:
                self.check()
        else:
            if self.next_btn.hit(inp) or pygame.K_RETURN in inp.keys or pygame.K_KP_ENTER in inp.keys:
                self.i += 1
                self.entry = ""
                self.res = None
                audio.sfx("click")
                if self.i >= len(self.ps):
                    self.i = len(self.ps) - 1
                    self.res = (-1, 0)
                    self.finish(self.total / len(self.ps))

    def partial(self):
        return self.total / max(1, len(self.ps))

    def render(self, s):
        gfx.bench(s, self.p.get("tint", SKY))
        if not self.ps:
            return
        q = self.ps[self.i]
        left = pygame.Rect(30, TOP + 12, 570, BOTTOM - TOP - 24)
        gfx.card(s, left, CARD)
        draw_text(s, "Problem %d of %d" % (self.i + 1, len(self.ps)), (50, TOP + 24), 13, MUTED, bold=True)
        y = draw_wrapped(s, q["text"], (50, TOP + 46), 18, 530, INK)
        if q.get("pic"):
            pr = pygame.Rect(50, y + 10, 530, left.bottom - y - 24)
            if pr.h > 60:
                cached_pic(s, q, pr)
        gfx.card(s, (620, TOP + 12, 320, BOTTOM - TOP - 24), (250, 248, 240))
        disp = pygame.Rect(640, TOP + 40, 280, 64)
        gfx.rrect(s, disp, (232, 240, 228), INK, 2, 8)
        cur = "_" if (self.t // 30) % 2 == 0 and self.res is None else ""
        draw_text(s, self.entry + cur, (disp.right - 16, disp.y + 14), 30, INK, right=True, bold=True, mono=True)
        draw_text(s, q.get("unit", ""), (disp.x + 10, disp.bottom + 6), 15, INK_SOFT, bold=True)
        if self.res is None:
            for b in self.pad:
                b.draw(s)
            self.enter.draw(s)
        else:
            lvl = self.res[0]
            if lvl >= 0:
                msg = ["Not quite.", "Close, but not precise enough.", "Correct!"][lvl]
                draw_text(s, msg, (780, TOP + 136), 20, [RED, CORAL_D, GREEN][lvl], center=True, bold=True)
                ans = q.get("show", "%g" % round(float(q["answer"]), 3))
                draw_text(s, "Answer: %s %s" % (ans, q.get("unit", "")), (780, TOP + 166), 16, INK, center=True, bold=True)
                draw_wrapped(s, q.get("why", ""), (640, TOP + 196), 14, 280, INK_SOFT)
                self.next_btn.draw(s)


# ======================================================================= Stop
@register("stop")
class StopStage(Stage):
    """A process runs on its own; click (or press Space) to stop it at the right moment.

    params: scene = callable(stage, surface, v) that draws the process at progress v (0..1);
                    stage.state is "run", "stopped" or "over".
            dur = seconds from v=0 to v=1 (the process fails at v=1)
            ideal = best v; window = (lo, hi) v range that still scores
            rounds = how many runs (default 1); speed_up = multiply dur each round
            ease = exponent applied to time (v = f**ease; >1 starts slow and speeds up)
            over_msg = feedback when it runs past 1; early_msg / late_msg for stopping outside the window
            start_msg = text on the button before starting (default: process starts immediately)
            readout = callable(v) -> str shown on a display (e.g. "45 s", "98 deg C")"""
    title = "Stop in time"
    instr = "Click or press Space to stop at the right moment."

    def setup(self):
        self.dur = self.p.get("dur", 6.0) * self.lv(1.15, 1.0, 0.85)
        self.ideal = self.p.get("ideal", 0.8)
        lo, hi = self.p.get("window", (0.65, 0.95))
        ideal = self.p.get("ideal", 0.8)
        k = self.lv(1.3, 1.0, 0.7)
        self.window = (max(0.0, ideal - (ideal - lo) * k), min(0.995, ideal + (hi - ideal) * k))
        self.rounds = self.p.get("rounds", 1)
        self.r = 0
        self.scores = []
        self.v = 0.0
        self.f = 0.0
        self.state = "run"
        self.wait = 0
        self.msgs = []
        self.jitter = self.p.get("jitter", 0.0)
        self.cur_dur = self.dur * (1 + self.rng.uniform(-self.jitter, self.jitter))

    def tick(self, inp):
        if self.state == "run":
            self.f += 1.0 / (60 * self.cur_dur)
            self.v = self.f ** self.p.get("ease", 1.0)
            if inp.click or "space" in inp.pressed or pygame.K_RETURN in inp.keys:
                self.stop()
            elif self.v >= 1.0:
                self.v = 1.0
                self.state = "over"
                audio.sfx("buzz")
                self.scores.append(0)
                self.msgs.append(self.p.get("over_msg", "Too late: it ran over."))
                self.floaters.add(W // 2, 120, "Too late!", RED, 28)
                self.shake = 20
                self.wait = 80
        else:
            self.wait -= 1
            if self.wait <= 0:
                self.r += 1
                if self.r >= self.rounds:
                    sc = sum(self.scores) / len(self.scores)
                    self.finish(sc, *self.summary())
                else:
                    self.v = self.f = 0.0
                    self.state = "run"
                    self.cur_dur = self.dur * (self.p.get("speed_up", 1.0) ** self.r) * (1 + self.rng.uniform(-self.jitter, self.jitter))

    def summary(self):
        seen = []
        for m in self.msgs:
            if m not in seen:
                seen.append(m)
        return seen[:3]

    def stop(self):
        self.state = "stopped"
        lo, hi = self.window
        v = self.v
        if v < lo:
            sc = 0
            self.msgs.append(self.p.get("early_msg", "Stopped too early."))
            audio.sfx("bad")
            self.floaters.add(W // 2, 120, "Too early", CORAL_D, 26)
        elif v > hi:
            sc = 0
            self.msgs.append(self.p.get("late_msg", "Stopped too late."))
            audio.sfx("bad")
            self.floaters.add(W // 2, 120, "Too late", CORAL_D, 26)
        else:
            d = abs(v - self.ideal) / max(1e-6, (self.ideal - lo) if v < self.ideal else (hi - self.ideal))
            sc = 100 - 55 * clamp(d, 0, 1) ** 1.3
            audio.sfx("good" if sc >= 75 else "ding")
            self.floaters.add(W // 2, 120, "Perfect!" if sc >= 92 else "Good" if sc >= 70 else "OK", GREEN, 28)
            if sc >= 75:
                self.particles.burst(W // 2, 220, 20)
            self.msgs.append(self.p.get("good_msg", "Stopped at the right moment."))
        self.scores.append(sc)
        self.wait = 70

    def autoplay(self):
        self.finish(88)

    def render(self, s):
        sc = self.p.get("scene")
        if sc:
            sc(self, s, self.v)
        else:
            gfx.bench(s)
            r = pygame.Rect(180, 260, 600, 40)
            gfx.bar(s, r, self.v, CORAL)
            lo, hi = self.window
            gfx.alpha_rect(s, (r.x + r.w * lo, r.y - 10, r.w * (hi - lo), r.h + 20), GREEN, 70)
        if self.rounds > 1:
            gfx.tag(s, W - 20 - 100, TOP + 6, "Run %d of %d" % (min(self.r + 1, self.rounds), self.rounds), CARD, 14)
        ro = self.p.get("readout")
        if ro:
            box = pygame.Rect(W - 190, TOP + 34, 170, 44)
            gfx.rrect(s, box, (40, 44, 56), INK, 2, 8)
            draw_text(s, ro(self.v), box.center, 22, (140, 255, 170), center=True, bold=True, mono=True, vcenter=True)


# ======================================================================= Match
def _mid(r, text, bold):
    """Top y that centres wrapped 15 px text vertically in rect r."""
    n = len(wrap(text, 15, r.w - 20, bold))
    return r.centery - (n * int(15 * 1.38)) // 2 + 1



@register("match")
class MatchStage(Stage):
    """Connect each item on the left with its partner on the right.

    params: pairs = [(left, right) or (left, right, why)], n = pairs per round (default all, max 6),
            left_title / right_title, left_col / right_col (fill colours), draw_left / draw_right optional
            callables(surface, rect, label) to draw an item instead of text."""
    title = "Match"
    instr = "Click an item on the left, then its partner on the right."
    limit = 60

    def setup(self):
        pairs = [p if len(p) == 3 else (p[0], p[1], "") for p in self.p["pairs"]]
        self.rng.shuffle(pairs)
        self.pairs = pairs[:self.p.get("n", min(6, len(pairs)))]
        n = len(self.pairs)
        self.lorder = list(range(n))
        self.rorder = list(range(n))
        self.rng.shuffle(self.lorder)
        self.rng.shuffle(self.rorder)
        self.sel = None
        self.matched = set()
        self.mistakes = 0
        self.why = ""
        self.flash = {}

    def rects(self):
        n = len(self.pairs)
        h = min(62, int((BOTTOM - TOP - 90) / n) - 8)
        L = [pygame.Rect(80, TOP + 60 + k * (h + 10), 300, h) for k in range(n)]
        R = [pygame.Rect(W - 380, TOP + 60 + k * (h + 10), 300, h) for k in range(n)]
        return L, R

    def tick(self, inp):
        for k in list(self.flash):
            self.flash[k] -= 1
            if self.flash[k] <= 0:
                del self.flash[k]
        self.mouse = inp.mouse
        if not inp.click:
            return
        L, R = self.rects()
        for k, r in enumerate(L):
            i = self.lorder[k]
            if r.collidepoint(inp.mouse) and i not in self.matched:
                self.sel = i
                audio.sfx("blip")
                return
        for k, r in enumerate(R):
            j = self.rorder[k]
            if r.collidepoint(inp.mouse) and j not in self.matched and self.sel is not None:
                if j == self.sel:
                    self.matched.add(j)
                    self.why = self.pairs[j][2]
                    audio.sfx("good")
                    self.particles.burst(r.x, r.centery, 12)
                    if len(self.matched) == len(self.pairs):
                        self.finish(100 - self.lv(10, 15, 20) * self.mistakes, "All matched." if not self.mistakes else "%d wrong match%s." % (self.mistakes, "es" if self.mistakes > 1 else ""))
                else:
                    self.mistakes += 1
                    self.flash[("r", j)] = 20
                    audio.sfx("bad")
                self.sel = None
                return

    def partial(self):
        return max(0, 100 * len(self.matched) / len(self.pairs) - 15 * self.mistakes - 20)

    def render(self, s):
        gfx.bench(s, self.p.get("tint", SKY))
        L, R = self.rects()
        if self.p.get("left_title"):
            gfx.tag(s, L[0].centerx, TOP + 14, self.p["left_title"], CARD, 15, center=True)
        if self.p.get("right_title"):
            gfx.tag(s, R[0].centerx, TOP + 14, self.p["right_title"], CARD, 15, center=True)
        lpos = {self.lorder[k]: r for k, r in enumerate(L)}
        rpos = {self.rorder[k]: r for k, r in enumerate(R)}
        for i in self.matched:
            gfx.line(s, GREEN, lpos[i].midright, rpos[i].midleft, 4)
        for k, r in enumerate(L):
            i = self.lorder[k]
            col = self.p.get("left_col", SAND)
            if i in self.matched:
                col = (196, 236, 200)
            gfx.rrect(s, r, col, CORAL if self.sel == i else INK, 4 if self.sel == i else 2, 10)
            if self.p.get("draw_left"):
                self.p["draw_left"](s, r, self.pairs[i][0])
            else:
                draw_wrapped(s, self.pairs[i][0], (r.x + 10, _mid(r, self.pairs[i][0], True)), 15, r.w - 20, INK, bold=True, center=True)
        for k, r in enumerate(R):
            j = self.rorder[k]
            col = self.p.get("right_col", CARD)
            if j in self.matched:
                col = (196, 236, 200)
            if ("r", j) in self.flash:
                col = (248, 190, 180)
            gfx.rrect(s, r, col, INK, 2, 10)
            if self.p.get("draw_right"):
                self.p["draw_right"](s, r, self.pairs[j][1])
            else:
                draw_wrapped(s, self.pairs[j][1], (r.x + 10, _mid(r, self.pairs[j][1], False)), 15, r.w - 20, INK, center=True)
        if self.sel is not None:
            gfx.line(s, CORAL, lpos[self.sel].midright, getattr(self, "mouse", lpos[self.sel].midright), 3)
        if self.why:
            lines = wrap(self.why, 15, W - 200)
            box = pygame.Rect(80, BOTTOM - 22 - len(lines) * 21, W - 160, len(lines) * 21 + 14)
            gfx.card(s, box, CARD, INK, 10)
            draw_wrapped(s, self.why, (box.x + 20, box.y + 7), 15, box.w - 40, INK_SOFT, center=True)
