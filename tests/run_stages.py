# -*- coding: utf-8 -*-
"""Headless smoke test for techniques and their stages.

    python tests/run_stages.py                 all techniques (needs techniques.py and every wing module)
    python tests/run_stages.py tech_dna        one wing module
    python tests/run_stages.py tech_dna pcr    one technique
    add --shots to save screenshots to tests/shots/ (frame 40 and frame 400 of each stage)

Each stage is played for 900 frames by a random "monkey" (mouse moves, clicks, keys, digits),
drawn every frame, then a fresh copy is finished with autoplay(). Any exception is reported."""
import importlib
import os
import random
import sys
import traceback

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "game"))

import pygame  # noqa: E402
import core  # noqa: E402
import stage as stg  # noqa: E402

REQUIRED = ["key", "name", "full", "wing", "icon", "blurb", "facts", "quiz", "music", "stages"]
WINGS = ["DNA", "Genes & genomes", "Proteins", "Cells & embryos"]


class Ctx:
    headless = True

    def __init__(self, tech, seed, level=1):
        self.tech = tech
        self.rng = random.Random(seed)
        self.level = level


def monkey(seed):
    r = random.Random(seed)
    state = {"m": (480, 300), "t": 0}

    def bot(inp):
        state["t"] += 1
        if r.random() < 0.08:
            state["m"] = (r.randrange(0, core.W), r.randrange(0, core.H))
        else:
            x, y = state["m"]
            state["m"] = (max(0, min(core.W - 1, x + r.randint(-12, 12))), max(0, min(core.H - 1, y + r.randint(-12, 12))))
        inp.mouse = state["m"]
        inp.click = r.random() < 0.06
        if inp.click:
            inp.down = True
        inp.release = inp.down and r.random() < 0.05
        if inp.release:
            inp.down = False
        inp.wheel = r.choice([0] * 20 + [1, -1])
        inp.keys = set()
        inp.text = ""
        inp.pressed = set()
        inp.held = set()
        if r.random() < 0.04:
            inp.text = r.choice("0123456789.")
        if r.random() < 0.03:
            k = r.choice([pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_RETURN, pygame.K_SPACE, pygame.K_BACKSPACE,
                          pygame.K_a, pygame.K_c, pygame.K_g, pygame.K_t, pygame.K_n, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN])
            inp.keys.add(k)
            for a, ks in core.KEYMAP.items():
                if k in ks:
                    inp.pressed.add(a)
        for a in ("left", "right", "up", "down", "space"):
            if r.random() < 0.05:
                inp.held.add(a)
    return bot


def check_tech(t):
    errs = []
    for k in REQUIRED:
        if k not in t:
            errs.append("missing field %s" % k)
    if t.get("wing") not in WINGS:
        errs.append("bad wing %r" % t.get("wing"))
    if len(t.get("facts", [])) < 6:
        errs.append("fewer than 6 facts")
    for q in t.get("quiz", []):
        if not (0 <= q["answer"] < len(q["options"])):
            errs.append("quiz answer out of range: %s" % q["q"])
    if len(t.get("quiz", [])) < 3:
        errs.append("fewer than 3 seminar questions")
    for kind, _ in t.get("stages", []):
        if kind not in stg.STAGES:
            errs.append("unknown stage kind %s" % kind)
    return errs


def run_stage(screen, t, i, kind, params, shots):
    cls = stg.STAGES[kind]
    inp = core.Input()
    inp.bot = monkey(i * 31 + len(t["key"]))
    st = cls(Ctx(t, i, i % 3), **params)
    frames = 0
    for f in range(900):
        inp.update([])
        st.update(inp)
        if st.done:
            st.post_tick()
        screen.fill((0, 0, 0))
        st.draw(screen)
        if shots and f in (40, 400):
            os.makedirs(os.path.join(HERE, "shots"), exist_ok=True)
            pygame.image.save(screen, os.path.join(HERE, "shots", "%s_%d_%s_f%d.png" % (t["key"], i, kind, f)))
        frames = f
        if st.ready():
            break
    monkey_score = st.score if st.done else None
    for level in (0, 1, 2):
        st2 = cls(Ctx(t, i + 100, level), **params)
        st2.autoplay()
        assert st2.done, "autoplay did not finish the stage (level %d)" % level
        assert 0 <= st2.score <= 100
    screen.fill((0, 0, 0))
    st2.draw(screen)
    return frames, monkey_score, st2.score


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    shots = "--shots" in sys.argv
    pygame.init()
    screen = pygame.display.set_mode((core.W, core.H))
    if args:
        mod = importlib.import_module(args[0])
        techs = mod.TECHS
        if len(args) > 1:
            techs = [t for t in techs if t["key"] == args[1]]
    else:
        techs = importlib.import_module("techniques").TECHS
    bad = 0
    for t in techs:
        errs = check_tech(t)
        for e in errs:
            print("  [%s] %s" % (t.get("key"), e))
        bad += len(errs)
        for i, (kind, params) in enumerate(t.get("stages", [])):
            if kind not in stg.STAGES:
                continue
            try:
                frames, ms, auto = run_stage(screen, t, i, kind, params, shots)
                print("  ok  %-10s %d %-10s monkey frames=%d score=%s auto=%d" % (t["key"], i, kind, frames, ms, auto))
            except Exception:
                bad += 1
                print("  FAIL %s stage %d (%s)" % (t["key"], i, kind))
                traceback.print_exc()
    print("%d technique(s), %d problem(s)" % (len(techs), bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
