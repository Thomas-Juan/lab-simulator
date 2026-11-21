# -*- coding: utf-8 -*-
"""A station on the board: one technique played as a run of stages.

intro card -> (briefing -> stage -> result card with a fun fact) x n -> final score and stars."""
import math
import random
import pygame
import audio
import gfx
from core import (W, H, INK, INK_SOFT, MUTED, CARD, PAPER, SAND, CORAL, CORAL_D, TURQ, LAV, NIGHT, WHITE, GREEN, RED,
                  YELLOW, clamp, mix, draw_text, draw_wrapped, wrap)
from stage import STAGES

STAR_AT = (40, 65, 85)
LEVELS = [("Student", "More time and wider margins. At most 2 stars.", (196, 226, 222)),
          ("Researcher", "The standard bench.", SAND),
          ("Expert", "Less time, tighter margins. Earns the gold Expert seal.", (240, 196, 120))]


def stars_for(score):
    return sum(1 for s in STAR_AT if score >= s)


def stage_title(kind, params):
    return params.get("title") or getattr(STAGES.get(kind), "title", kind)


def wing_col(tech):
    from techniques import WINGS
    return WINGS.get(tech["wing"], SAND)


class Station:
    overlay = False

    def __init__(self, app, tech, practice=False):
        self.app = app
        self.tech = tech
        self.practice = practice          # free play: nothing is saved
        self.headless = app.headless
        self.rng = random.Random()
        self.col = wing_col(tech)
        self.phase = "intro"
        self.i = -1
        self.stage = None
        self.scores = []
        self.t = 0
        self.pt = 0
        self.fact = None
        self.paused = False
        self.pmenu = 0
        self.particles = gfx.Particles()
        self.start_btn = gfx.Button((W // 2 - 110, 452, 220, 46), "Start", SAND, size=20)
        self.go_btn = gfx.Button((W // 2 - 90, 0, 180, 44), "Go!", SAND, size=20)
        self.next_btn = gfx.Button((W // 2 - 90, 0, 180, 44), "Next", SAND, size=20)
        self.back_btn = gfx.Button((W // 2 - 230, 446, 210, 46), "Back to the board", SAND)
        self.again_btn = gfx.Button((W // 2 + 20, 446, 210, 46), "Play again", (196, 226, 222))
        self.result = None
        store = app.data["opt"] if practice or app.slot is None else app.slot
        self.level = int(store.get("level", 1))
        self.level_btns = [gfx.Button((120 + k * 132, 452, 126, 46), LEVELS[k][0], LEVELS[k][2], size=16) for k in range(3)]
        self.start_btn.rect = pygame.Rect(W - 90 - 30 - 220, 452, 220, 46)
        self.buf = None
        audio.music(tech["key"])

    # ------------------------------------------------------------ flow
    def begin_stage(self):
        self.i += 1
        kind, params = self.tech["stages"][self.i]
        self.stage = STAGES[kind](self, **params)
        self.phase = "brief"
        self.pt = 0

    def end_stage(self):
        self.scores.append(self.stage.score)
        self.fact = self.next_fact()
        self.phase = "result"
        self.pt = 0
        audio.sfx("good" if self.stage.score >= 65 else "ding" if self.stage.score >= 40 else "bad")

    def next_fact(self):
        facts = self.tech["facts"]
        slot = None if self.practice else self.app.slot
        seen = set(slot["facts"]) if slot else set()
        ids = ["%s:%d" % (self.tech["key"], k) for k in range(len(facts))]
        unseen = [k for k, fid in enumerate(ids) if fid not in seen]
        k = (unseen[0] if unseen else self.rng.randrange(len(facts)))
        if slot is not None and ids[k] not in seen:
            slot["facts"].append(ids[k])
            self.new_fact = True
        else:
            self.new_fact = False
        return facts[k]

    def finish(self):
        total = sum(self.scores) / max(1, len(self.scores))
        st = stars_for(total)
        if self.level == 0:
            st = min(st, 2)
        flawless = len(self.scores) > 1 and min(self.scores) >= 90
        expert = self.level == 2 and st >= 1
        best_before = None
        new_best = False
        if not self.practice:
            slot = self.app.slot
            rec = slot["best"].get(self.tech["key"])
            best_before = dict(rec) if rec else None
            if rec is None:
                rec = slot["best"][self.tech["key"]] = {"score": round(total), "stars": st}
                new_best = True
            else:
                if st > rec["stars"] or (st == rec["stars"] and total > rec["score"]):
                    rec["stars"] = st
                    rec["score"] = max(rec["score"], round(total))
                    new_best = True
            if expert and not rec.get("expert"):
                rec["expert"] = True
                new_best = True
            if flawless:
                slot["coffee"] += 1
            slot["plays"][self.tech["key"]] = slot["plays"].get(self.tech["key"], 0) + 1
            self.app.save()
        self.result = {"score": total, "stars": st, "new_best": new_best, "before": best_before,
                       "flawless": flawless, "expert": expert, "level": self.level}
        self.phase = "final"
        self.pt = 0
        audio.music("results")
        audio.sfx("win" if st >= 2 else "ding" if st == 1 else "lose")

    def leave(self):
        self.app.pop()
        top = self.app.stack[-1] if self.app.stack else None
        if top is not None and hasattr(top, "resume"):
            top.resume(self.tech["key"], self.result)

    # ------------------------------------------------------------ update
    def update(self, inp):
        self.t += 1
        self.pt += 1
        self.inp = inp
        self.particles.update()
        if self.paused:
            self.update_pause(inp)
            return
        if "back" in inp.pressed and self.phase in ("brief", "play", "result"):
            self.paused = True
            self.pmenu = 0
            audio.sfx("blip")
            return
        if self.phase == "intro":
            for k, b in enumerate(self.level_btns):
                if b.hit(inp) or (pygame.K_1 + k) in inp.keys:
                    self.level = k
                    store = self.app.data["opt"] if self.practice or self.app.slot is None else self.app.slot
                    store["level"] = k
                    audio.sfx("click")
            if self.start_btn.hit(inp) or inp.ok():
                audio.sfx("click")
                self.begin_stage()
            elif "back" in inp.pressed:
                self.leave()
        elif self.phase == "brief":
            self.go_btn.rect.y = 382
            if self.pt > 10 and (self.go_btn.hit(inp) or inp.ok()):
                audio.sfx("whoosh")
                self.phase = "play"
        elif self.phase == "play":
            self.stage.update(inp)
            if self.stage.done:
                self.stage.post_tick()
                if self.stage.ready():
                    self.end_stage()
        elif self.phase == "result":
            self.stage.update(_NOINPUT)
            self.next_btn.rect.y = 440
            if self.pt > 20 and (self.next_btn.hit(inp) or inp.ok()):
                audio.sfx("click")
                if self.i + 1 < len(self.tech["stages"]):
                    self.begin_stage()
                else:
                    self.finish()
        elif self.phase == "final":
            if self.pt == 30 or self.pt == 50 or self.pt == 70:
                k = (self.pt - 30) // 20
                if k < self.result["stars"]:
                    audio.sfx("coffee")
                    self.particles.burst(W // 2 + (k - 1) * 70, 236, 26, speed=5)
            if self.pt > 30 and (self.back_btn.hit(inp) or inp.ok() or "back" in inp.pressed):
                audio.sfx("click")
                self.leave()
            elif self.pt > 30 and self.again_btn.hit(inp):
                audio.sfx("click")
                self.app.pop()
                self.app.push(Station(self.app, self.tech, self.practice))

    PAUSE_ITEMS = ["Resume", "Restart this step", "Leave the station"]

    def update_pause(self, inp):
        rects = [pygame.Rect(W // 2 - 140, 230 + k * 56, 280, 46) for k in range(3)]
        if "up" in inp.pressed:
            self.pmenu = (self.pmenu - 1) % 3
        if "down" in inp.pressed:
            self.pmenu = (self.pmenu + 1) % 3
        choice = None
        for k, r in enumerate(rects):
            if r.collidepoint(inp.mouse):
                if inp.moved:
                    self.pmenu = k
                if inp.click:
                    choice = k
        if inp.ok():
            choice = self.pmenu
        if "back" in inp.pressed:
            choice = 0
        if choice is None:
            return
        audio.sfx("click")
        self.paused = False
        if choice == 1:
            self.i -= 1
            self.begin_stage()
        elif choice == 2:
            self.leave()

    # ------------------------------------------------------------ draw
    def hud(self, s):
        gfx.hud_bar(s, 46)
        pygame.draw.rect(s, self.col, (0, 0, 10, 46))
        gfx.alpha_circle(s, self.col, (36, 23), 19, 45)
        gfx.icon(s, self.tech["icon"], (36, 23), 30)
        x = 60 + draw_text(s, self.tech["name"], (60, 11), 19, INK, bold=True)
        n = len(self.tech["stages"])
        if self.stage:
            draw_text(s, "·  Step %d of %d:  %s" % (self.i + 1, n, self.stage.title), (x + 10, 13), 16, INK_SOFT, bold=True)
        # progress dots
        for k in range(n):
            c = (W - 220 + k * 18, 23)
            done = k < len(self.scores)
            gfx.circle(s, (GREEN if self.scores[k] >= 65 else YELLOW if self.scores[k] >= 40 else CORAL) if done else (CARD if k != self.i else SAND), c, 6)
        if self.stage and self.stage.limit is not None:
            left = self.stage.left()
            box = pygame.Rect(W - 100, 8, 88, 30)
            hot = left <= 5 and not self.stage.done
            gfx.rrect(s, box, (250, 210, 200) if hot else (232, 240, 228), INK, 2, 15)
            draw_text(s, "%d:%02d" % (int(math.ceil(left)) // 60, int(math.ceil(left)) % 60), box.center, 17,
                      RED if hot else INK, center=True, bold=True, mono=True, vcenter=True)
        # bottom hint
        if self.stage:
            hint = self.stage.hint or self.stage.instr
            gfx.alpha_rect(s, (0, H - 26, W, 26), CARD, 215)
            pygame.draw.line(s, INK, (0, H - 26), (W, H - 26), 1)
            line = wrap(hint, 14, W - 140)[0] if hint else ""
            draw_text(s, line, (14, H - 21), 14, INK_SOFT)
            draw_text(s, "Esc: pause", (W - 12, H - 21), 13, MUTED, right=True)

    def draw(self, s):
        if self.phase == "intro":
            self.draw_intro(s)
        elif self.phase == "final":
            self.draw_final(s)
        else:
            if self.stage.shake and self.phase == "play":
                if self.buf is None:
                    self.buf = pygame.Surface((W, H))
                self.stage.draw(self.buf)
                k = self.stage.shake
                s.fill((20, 20, 26))
                s.blit(self.buf, (int(math.sin(k * 2.1) * min(6, k)), int(math.cos(k * 1.7) * min(4, k) * 0.6)))
            else:
                self.stage.draw(s)
            self.hud(s)
            if self.phase == "brief":
                self.draw_brief(s)
            elif self.phase == "result":
                self.draw_result(s)
        self.particles.draw(s)
        if self.paused:
            gfx.dim(s, 150)
            gfx.card(s, (W // 2 - 180, 160, 360, 250), CARD)
            draw_text(s, "Paused", (W // 2, 180), 24, INK, center=True, bold=True)
            for k, it in enumerate(self.PAUSE_ITEMS):
                r = pygame.Rect(W // 2 - 140, 230 + k * 56, 280, 46)
                gfx.rrect(s, r, SAND if k == self.pmenu else CARD, INK, 2, 10)
                draw_text(s, it, r.center, 18, INK, center=True, bold=True, vcenter=True)

    def draw_intro(self, s):
        gfx.bench(s, mix(self.col, WHITE, 0.4), "intro")
        card = pygame.Rect(90, 40, W - 180, 470)
        gfx.card(s, card, CARD)
        gfx.header(s, card, self.col, 92)
        gfx.circle(s, CARD, (card.x + 66, card.y + 47), 36)
        gfx.icon(s, self.tech["icon"], (card.x + 66, card.y + 47), 46)
        draw_text(s, self.tech["wing"].upper(), (card.x + 120, card.y + 14), 13, WHITE, bold=True)
        draw_text(s, self.tech["name"], (card.x + 120, card.y + 32), 30, WHITE, bold=True, shadow=mix(self.col, INK, 0.5))
        if self.tech["full"] != self.tech["name"]:
            draw_text(s, self.tech["full"], (card.x + 122, card.y + 68), 15, WHITE, bold=True)
        y = draw_wrapped(s, self.tech["blurb"], (card.x + 40, card.y + 112), 17, card.w - 80, INK)
        draw_text(s, "At this bench you will:", (card.x + 40, y + 10), 15, MUTED, bold=True)
        y += 36
        for k, (kind, params) in enumerate(self.tech["stages"]):
            gfx.circle(s, SAND, (card.x + 56, y + 11), 11)
            draw_text(s, str(k + 1), (card.x + 56, y + 11), 13, INK, center=True, bold=True, vcenter=True)
            draw_text(s, stage_title(kind, params), (card.x + 76, y + 2), 16, INK, bold=True)
            if len(self.tech["stages"]) <= 4:
                instr = params.get("instr", getattr(STAGES.get(kind), "instr", ""))
                first = instr.split(". ")[0].rstrip(".") + "." if instr else ""
                lines = wrap(first, 14, card.w - 160)
                if lines:
                    draw_text(s, lines[0] + (" ..." if len(lines) > 1 else ""), (card.x + 78, y + 23), 14, MUTED)
                y += 46
            else:
                y += 28
        mus = self.tech.get("music", {}).get("name")
        if mus:
            wmus = draw_text(s, mus, (card.right - 24, card.y + 70), 14, WHITE, right=True, bold=True, shadow=mix(self.col, INK, 0.5))
            nx, ny = card.right - 24 - wmus - 18, card.y + 80
            gfx.alpha_circle(s, WHITE, (nx, ny), 4, 255)
            pygame.draw.line(s, WHITE, (nx + 3, ny), (nx + 3, ny - 13), 2)
            pygame.draw.line(s, WHITE, (nx + 3, ny - 13), (nx + 9, ny - 9), 2)
        if not self.practice:
            rec = self.app.slot["best"].get(self.tech["key"])
            if rec:
                draw_text(s, "Your best: %d" % rec["score"], (card.right - 120, card.bottom - 92), 15, INK_SOFT, center=True, bold=True)
                gfx.stars(s, card.right - 120, card.bottom - 60, rec["stars"], 12, 28)
        draw_text(s, LEVELS[self.level][1], (120, 428), 14, INK_SOFT, bold=True)
        for k, b in enumerate(self.level_btns):
            b.col = LEVELS[k][2] if k == self.level else CARD
            b.draw(s, getattr(self, "inp", None))
            if k == self.level:
                gfx.rrect(s, b.rect.inflate(6, 6), None, CORAL, 3, 12)
        self.start_btn.draw(s, getattr(self, "inp", None))

    def draw_brief(self, s):
        gfx.dim(s, 110)
        r = pygame.Rect(W // 2 - 300, 120, 600, 330)
        gfx.card(s, r, CARD)
        draw_text(s, "Step %d of %d" % (self.i + 1, len(self.tech["stages"])), (r.centerx, r.y + 18), 14, MUTED, center=True, bold=True)
        draw_text(s, self.stage.title, (r.centerx, r.y + 40), 26, INK, center=True, bold=True)
        draw_wrapped(s, self.stage.instr, (r.x + 40, r.y + 94), 18, r.w - 80, INK, center=True)
        if self.stage.limit:
            gfx.tag(s, r.centerx, r.y + 210, "Time limit: %d s" % self.stage.limit, (250, 220, 200), 14, center=True)
        self.go_btn.draw(s)

    def draw_result(self, s):
        gfx.dim(s, 120)
        r = pygame.Rect(W // 2 - 320, 70, 640, 430)
        gfx.card(s, r, CARD)
        sc = self.stage.score
        shown = min(sc, int(sc * min(1, self.pt / 40.0)))
        col = GREEN if sc >= 65 else YELLOW if sc >= 40 else CORAL
        draw_text(s, self.stage.title, (r.centerx, r.y + 16), 18, MUTED, center=True, bold=True)
        draw_text(s, "%d" % shown, (r.centerx, r.y + 40), 52, mix(col, INK, 0.25), center=True, bold=True)
        gfx.bar(s, (r.x + 120, r.y + 108, r.w - 240, 16), shown / 100.0, col)
        if shown < sc:
            verdict = ""
        else:
            verdict = "Excellent work" if sc >= 85 else "Good work" if sc >= 65 else "Getting there" if sc >= 40 else "Try that again later"
        draw_text(s, verdict, (r.centerx, r.y + 132), 17, INK, center=True, bold=True)
        y = r.y + 162
        for f in self.stage.feedback[:3]:
            y = draw_wrapped(s, f, (r.x + 40, y), 15, r.w - 80, INK_SOFT, center=True) + 2
        fr = pygame.Rect(r.x + 30, max(y + 8, r.y + 236), r.w - 60, 130)
        gfx.rrect(s, fr, (252, 244, 224), INK, 2, 12)
        draw_text(s, "Did you know?" + ("   (new page in your lab notebook)" if self.new_fact else ""), (fr.x + 18, fr.y + 12), 15, CORAL_D, bold=True)
        draw_wrapped(s, self.fact, (fr.x + 18, fr.y + 36), 16, fr.w - 36, INK)
        self.next_btn.rect.y = r.bottom - 58
        self.next_btn.label = "Next step" if self.i + 1 < len(self.tech["stages"]) else "See results"
        self.next_btn.draw(s)

    def draw_final(self, s):
        gfx.menu_bg(s, self.t / 60.0)
        r = pygame.Rect(W // 2 - 330, 40, 660, 470)
        gfx.card(s, r, CARD)
        gfx.header(s, r, self.col, 64)
        draw_text(s, self.tech["name"] + " complete", (r.centerx, r.y + 18), 26, WHITE, center=True, bold=True, shadow=mix(self.col, INK, 0.5))
        res = self.result
        shown = min(res["score"], res["score"] * min(1, self.pt / 30.0))
        draw_text(s, "Score %d" % round(shown), (r.centerx, r.y + 84), 30, INK, center=True, bold=True)
        for k in range(3):
            lit = k < res["stars"] and self.pt >= 30 + k * 20
            gfx.star(s, W // 2 + (k - 1) * 70, 236, 26, lit)
        tags = [LEVELS[res["level"]][0]]
        if res["new_best"] and not self.practice:
            tags.append("New best!")
        if res["expert"]:
            tags.append("Expert seal")
        if res["flawless"]:
            tags.append("Flawless: +1 coffee" if not self.practice else "Flawless")
        if self.pt > 80:
            x = W // 2 - sum(gfx.text_surf(t_, 15, INK, True).get_width() + 26 for t_ in tags) // 2
            for t_ in tags:
                col = YELLOW if t_ == "New best!" else (240, 196, 120) if t_ == "Expert seal" else (196, 236, 200) if t_.startswith("Flawless") else CARD
                x += gfx.tag(s, x, 274, t_, col, 15) + 8
        y = 316
        for k, ((kind, params), sc) in enumerate(zip(self.tech["stages"], self.scores)):
            col = GREEN if sc >= 65 else YELLOW if sc >= 40 else CORAL
            draw_text(s, stage_title(kind, params), (r.x + 150, y), 15, INK)
            gfx.bar(s, (r.x + 400, y + 3, 150, 12), sc / 100.0, col)
            draw_text(s, str(sc), (r.x + 580, y), 15, INK, bold=True)
            y += 22
        draw_text(s, "Stars at %d, %d and %d points" % STAR_AT, (r.centerx, r.y + 140), 13, MUTED, center=True)
        self.back_btn.rect.y = self.again_btn.rect.y = r.bottom - 60
        self.back_btn.label = "Back to the board" if not self.practice else "Back"
        self.back_btn.draw(s)
        self.again_btn.draw(s)


class _NoInput:
    mouse = (-100, -100)
    click = down = release = rclick = False
    wheel = 0
    moved = 0
    keys = set()
    pressed = set()
    held = set()
    text = ""

    def ok(self):
        return False

    def axis(self):
        return 0, 0


_NOINPUT = _NoInput()
