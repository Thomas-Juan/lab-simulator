# -*- coding: utf-8 -*-
"""Headless check that on-screen text is readable: no two labels overlap and no text runs off
the screen. Every draw_text call onto the screen is recorded with its rectangle; after each
sampled frame the rectangles are compared.

    python tests/check_text.py              every minigame (3 levels) and every menu screen
    python tests/check_text.py tech_dna     one wing
    add --shots to save a screenshot of each frame that has a problem (tests/shots/text_*.png)

Text drawn into cached layers (then blitted) is not seen; screenshots cover those."""
import os
import random
import sys
import tempfile
import traceback

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "game"))
sys.path.insert(0, HERE)

import pygame  # noqa: E402
import core  # noqa: E402

LOG = []
SHOTS = "--shots" in sys.argv


def install(screen):
    """Wrap draw_text in every module so calls onto the screen are logged."""
    orig = core.draw_text

    def logged(surf, t, pos, size=18, color=core.INK, center=False, bold=False, right=False, mono=False,
               shadow=None, vcenter=False):
        w = orig(surf, t, pos, size, color, center, bold, right, mono, shadow, vcenter)
        if surf is screen:
            s = core.text_surf(core.pretty(str(t)), size, color, bold, mono)
            x, y = pos
            if center:
                x -= s.get_width() // 2
            elif right:
                x -= s.get_width()
            if vcenter:
                y -= s.get_height() // 2
            # the ink box: text height without the font's empty line gap above and below
            h = s.get_height()
            LOG.append((pygame.Rect(int(x), int(y + h * 0.18), s.get_width(), max(1, int(h * 0.7))), str(t)))
        return w
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, "draw_text", None) is orig:
            setattr(mod, "draw_text", logged)
    # cards and filled panels drawn later hide the text under them
    import gfx
    if not getattr(gfx, "_text_check", False):
        gfx._text_check = True
        o_card, o_rrect, o_dim = gfx.card, gfx.rrect, gfx.dim

        def card(s, rect, *a, **k):
            if s is screen:
                LOG.append((pygame.Rect(rect), None))
            return o_card(s, rect, *a, **k)

        def rrect(s, rect, fill, *a, **k):
            if s is screen and fill is not None and (len(fill) < 4 or fill[3] > 200):
                LOG.append((pygame.Rect(rect), None))
            return o_rrect(s, rect, fill, *a, **k)

        def dim(s, a=140, *r, **k):
            if s is screen and a >= 100:
                LOG.append((pygame.Rect(0, 0, core.W, core.H), "DIM"))
            return o_dim(s, a, *r, **k)
        gfx.card, gfx.rrect, gfx.dim = card, rrect, dim


def check(where, problems, screen):
    raw = LOG[:]
    del LOG[:]
    clip = screen.get_clip()
    rects = []
    for k, (r, t) in enumerate(raw):
        if t is None or t == "DIM":
            continue
        # hidden if a later card covers most of it, or a later strong dim puts it in the background
        hidden = False
        for r2, t2 in raw[k + 1:]:
            if t2 == "DIM" or (t2 is None and r2.contains(r.inflate(-4, -4))):
                hidden = True
                break
        if not hidden:
            rects.append((r, t))
    found = []
    for r, t in rects:
        if t.strip() and not where.startswith("screen: notebook") and (r.left < -1 or r.right > core.W + 1 or r.top < -1 or r.bottom > core.H + 1):
            found.append("off screen: %r at %s" % (t[:50], tuple(r)))
    for i in range(len(rects)):
        a, ta = rects[i]
        if not ta.strip():
            continue
        for j in range(i + 1, len(rects)):
            b, tb = rects[j]
            if not tb.strip() or (ta == tb and abs(a.x - b.x) <= 3 and abs(a.y - b.y) <= 3):
                continue
            c = a.clip(b)
            if c.w > 2 and c.h > 2 and c.w * c.h > 0.12 * min(a.w * a.h, b.w * b.h):
                found.append("overlap: %r / %r" % (ta[:40], tb[:40]))
    for f in found:
        key = (where.split("#")[0], f)
        if key not in problems:
            problems[key] = where
            if SHOTS:
                os.makedirs(os.path.join(HERE, "shots"), exist_ok=True)
                pygame.image.save(screen, os.path.join(HERE, "shots", "text_%d.png" % len(problems)))


def stages(screen, problems, techs):
    import stage as stg
    from run_stages import Ctx, monkey
    for t in techs:
        for i, (kind, params) in enumerate(t["stages"]):
            for level in (0, 1, 2):
                try:
                    st = stg.STAGES[kind](Ctx(t, i * 7 + level, level), **params)
                    inp = core.Input()
                    inp.bot = monkey(i * 13 + level)
                    for f in range(420):
                        inp.update([])
                        st.update(inp)
                        if st.done:
                            st.post_tick()
                        screen.fill((0, 0, 0))
                        del LOG[:]
                        st.draw(screen)
                        if f % 15 == 0:
                            check("%s step %d (%s) L%d#%d" % (t["key"], i + 1, kind, level, f), problems, screen)
                        if st.ready():
                            break
                    st.autoplay()
                    screen.fill((0, 0, 0))
                    del LOG[:]
                    st.draw(screen)
                    check("%s step %d (%s) L%d end" % (t["key"], i + 1, kind, level), problems, screen)
                except Exception:
                    problems[("%s %d" % (t["key"], i), "CRASH")] = traceback.format_exc()[-300:]


def screens(screen, problems):
    import main as game
    from board import Board
    from station import Station
    from techniques import TECHS
    core.SAVE_FILE = os.path.join(tempfile.mkdtemp(), "s.json")
    app = game.App(headless=True)
    app.screen = screen
    app.data["slots"][0] = core.new_slot()
    app.slot_i = 0
    sl = app.data["slots"][0]
    sl["best"] = {t["key"]: {"score": 70 + i, "stars": 1 + i % 3, "expert": i % 4 == 0} for i, t in enumerate(TECHS[:12])}
    sl["facts"] = ["%s:%d" % (t["key"], k) for t in TECHS for k in range(3)]
    sl["coffee"] = 5

    def shot(name, stack, frames=3, mouse=(5, 5)):
        app.stack = stack
        app.fade = 0

        def bot(inp):
            inp.mouse = mouse
            inp.keys, inp.pressed, inp.click = set(), set(), False
        app.inp.bot = bot
        for _ in range(frames):
            del LOG[:]
            app.frame([])
        check("screen: " + name, problems, screen)
    shot("title", [game.Title(app)])
    shot("slots", [game.Title(app), game.Slots(app)])
    shot("options", [game.Title(app), game.Options(app)])
    b = Board(app)
    shot("board", [game.Title(app), b])
    for i in range(28):
        from board import tile_rect
        shot("board hover %d" % i, [game.Title(app), b], 2, tile_rect(i).center)
    shot("how to", [game.Title(app), b, game.HowTo(app)])
    shot("pause", [game.Title(app), b, game.Pause(app)])
    shot("notebook", [game.Title(app), b, game.Notebook(app)])
    shot("binder", [game.Title(app), b, game.Binder(app)])
    shot("free play", [game.Title(app), game.Binder(app, practice=True)])
    shot("ending", [game.Title(app), b, game.Ending(app)], 5)
    for kind in ("tech", "fact", "seminar", "msg"):
        for t in TECHS:
            if kind == "tech":
                b.popup = {"kind": "tech", "tech": t}
            elif kind == "fact":
                b.popup = {"kind": "fact", "fact": max(t["facts"], key=len), "tech": t, "new": True}
            elif kind == "seminar":
                q = max(t["quiz"], key=lambda q: len(q["q"]) + sum(len(o) for o in q["options"]))
                b.popup = {"kind": "seminar", "q": q, "opts": list(enumerate(q["options"])), "tech": t, "chosen": 0}
            else:
                b.popup = {"kind": "msg", "title": "Contamination!", "text": "Mould is growing in the shared incubator. Everyone goes back three benches while it is cleaned."}
            shot("board popup %s %s" % (kind, t["key"]), [game.Title(app), b], 1)
            if kind == "msg":
                break
    b.popup = None
    b.state = "adjust"
    b.steps = 4
    shot("board adjust", [game.Title(app), b])
    b.state = "idle"
    for t in TECHS:
        for level in (0, 2):
            st = Station(app, t)
            st.level = level
            shot("station intro %s L%d" % (t["key"], level), [game.Title(app), b, st], 2)
        st.begin_stage()
        shot("station brief %s" % t["key"], [game.Title(app), b, st], 2)
        st.phase = "play"
        st.stage.autoplay()
        st.stage.feedback = ["A long feedback line that explains what went wrong and what to do next time, written out in full.",
                             "A second line of feedback with a number: 12.5 µL in 24 tubes."] + st.stage.feedback
        for _ in range(st.stage.end_delay + 2):
            st.stage.post_tick()
        st.end_stage()
        st.fact = max(t["facts"], key=len)
        shot("station result %s" % t["key"], [game.Title(app), b, st], 45)
        st.scores = [95, 60, 30, 88, 72, 91][:len(t["stages"])]
        st.i = len(t["stages"]) - 1
        st.finish()
        shot("station final %s" % t["key"], [game.Title(app), b, st], 95)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    pygame.init()
    screen = pygame.display.set_mode((core.W, core.H))
    import importlib
    techs = importlib.import_module(args[0]).TECHS if args else importlib.import_module("techniques").TECHS
    install(screen)
    problems = {}
    if not args:
        screens(screen, problems)
        install(screen)
    stages(screen, problems, techs)
    for (where, what), first in sorted(problems.items()):
        print("%-40s %s" % (first if what != "CRASH" else where, what if what != "CRASH" else first))
    print("%d text problem(s)" % len(problems))


if __name__ == "__main__":
    main()
