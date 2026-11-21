# -*- coding: utf-8 -*-
"""Headless test of the whole game: menus, board, stations, notebook, binder, ending.

    python tests/run_game.py            a scripted player plays many turns, then a random monkey
    python tests/run_game.py --shots    also save screenshots to tests/shots/game_*.png
    python tests/run_game.py --stub     use dummy techniques (to test the board alone)

The scripted player presses Enter on every screen and finishes every stage with autoplay(),
so it walks the whole loop: title, new game, how-to, rolls, coffee, popups, stations, results."""
import os
import random
import sys
import tempfile
import traceback
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "game"))

import pygame  # noqa: E402
import core  # noqa: E402

SHOTS = "--shots" in sys.argv


def stub_modules():
    wings = {"tech_dna": "DNA", "tech_genes": "Genes & genomes", "tech_proteins": "Proteins", "tech_cells": "Cells & embryos"}
    keys = {"tech_dna": ["pcr", "gel", "extract", "clone", "transform"], "tech_genes": ["sanger", "qpcr", "ngs", "crispr", "ish"],
            "tech_proteins": ["sds", "western", "elisa", "purify", "if"], "tech_cells": ["culture", "count", "transfect", "facs", "inject"]}
    for mod, wing in wings.items():
        m = types.ModuleType(mod)
        m.TECHS = [dict(key=k, name=k.upper(), full=k.title() + " technique", wing=wing, icon=k if k != "if" else "micro",
                        blurb="A stub technique used to test the board.", facts=["Fact %d about %s." % (i, k) for i in range(6)],
                        quiz=[dict(q="Stub question %d?" % i, options=["right", "wrong"], answer=0, why="Because.") for i in range(3)],
                        music=dict(name="Stub tune", bpm=100), stages=[("stop", {}), ("order", dict(steps=["a", "b", "c"]))])
                   for k in keys[mod]]
        sys.modules[mod] = m


def shot(app, name):
    if SHOTS:
        os.makedirs(os.path.join(HERE, "shots"), exist_ok=True)
        pygame.image.save(app.screen, os.path.join(HERE, "shots", "game_%s.png" % name))


def main():
    if "--stub" in sys.argv:
        stub_modules()
    core.SAVE_FILE = os.path.join(tempfile.mkdtemp(), "save.json")
    import main as game
    from station import Station
    from board import Board
    app = game.App(headless=True)
    rng = random.Random(1)
    state = {"f": 0, "mode": "script"}
    seen = set()

    def bot(inp):
        state["f"] += 1
        f = state["f"]
        inp.keys, inp.pressed, inp.held, inp.text = set(), set(), set(), ""
        inp.click = inp.release = False
        inp.wheel = 0
        top = app.stack[-1]
        name = type(top).__name__
        if state["mode"] == "script":
            inp.mouse = (5, 5)
            if isinstance(top, Station) and top.phase == "play" and not top.stage.done:
                top.stage.autoplay()
                return
            if f % 12 == 0:
                inp.keys.add(pygame.K_RETURN)
                inp.pressed.add("ok")
            elif f % 12 == 6:
                inp.keys.add(rng.choice([pygame.K_1, pygame.K_2]))
            if name not in seen:
                seen.add(name)
            return
        # monkey
        if rng.random() < 0.1:
            inp.mouse = (rng.randrange(core.W), rng.randrange(core.H))
        inp.click = rng.random() < 0.08
        inp.down = inp.click or (inp.down and rng.random() < 0.9)
        if rng.random() < 0.05:
            k = rng.choice([pygame.K_RETURN, pygame.K_SPACE, pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT,
                            pygame.K_1, pygame.K_2, pygame.K_TAB, pygame.K_ESCAPE if rng.random() < 0.15 else pygame.K_RETURN])
            inp.keys.add(k)
            for a, ks in core.KEYMAP.items():
                if k in ks:
                    inp.pressed.add(a)
        if rng.random() < 0.03:
            inp.text = rng.choice("0123456789")
        if isinstance(top, Station) and top.phase == "play" and not top.stage.done and rng.random() < 0.002:
            top.stage.autoplay()

    app.inp.bot = bot
    problems = 0
    stations = 0
    last_station = None
    for f in range(14000):
        if f == 9000:
            state["mode"] = "monkey"
            print("  scripted part: %d stations finished, screens seen: %s" % (stations, ", ".join(sorted(seen))))
        try:
            app.frame([])
        except Exception:
            problems += 1
            print("  FAIL at frame %d on %s" % (f, type(app.stack[-1]).__name__))
            traceback.print_exc()
            if problems > 5:
                break
            app.stack = [game.Title(app)]
        if not app.stack or not app.running:
            app.stack = [game.Title(app)]
            app.running = True
        top = app.stack[-1]
        if isinstance(top, Station) and top.phase == "final" and top is not last_station:
            last_station = top
            stations += 1
            if stations <= 3:
                shot(app, "final_%d" % stations)
        if f in (30, 400, 2000, 9000) or (f % 5000 == 0 and f):
            shot(app, "f%d_%s" % (f, type(top).__name__))
    slot = app.slot
    if slot:
        print("  slot: pos=%d coffee=%d laps=%d rolls=%d best=%d facts=%d done=%s" % (
            slot["pos"], slot["coffee"], slot.get("laps", 0), slot.get("rolls", 0), len(slot["best"]), len(slot["facts"]), slot["done"]))
    # force the ending
    try:
        from techniques import TECHS
        app.slot_i = 0
        if app.data["slots"][0] is None:
            app.data["slots"][0] = core.new_slot()
        for t in TECHS:
            app.data["slots"][0]["best"][t["key"]] = {"score": 70, "stars": 2}
        app.data["slots"][0]["done"] = False
        app.stack = [game.Title(app), Board(app)]
        app.stack[-1].resume()
        app.frame([])
        assert type(app.stack[-1]).__name__ == "Ending", type(app.stack[-1]).__name__
        shot(app, "ending")
        for sc in (game.Notebook(app), game.Binder(app), game.Binder(app, practice=True), game.Options(app), game.Slots(app)):
            app.stack = [game.Title(app), Board(app), sc]
            app.frame([])
            shot(app, type(sc).__name__)
    except Exception:
        problems += 1
        traceback.print_exc()
    print("%d station runs, %d problem(s)" % (stations, problems))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
