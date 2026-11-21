# -*- coding: utf-8 -*-
"""Regenerates DESIGN.md from the technique data (run after changing techniques)."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the game folder, one level up
sys.path.insert(0, os.path.join(HERE, "game"))
import core  # noqa: E402
from techniques import TECHS, WINGS  # noqa: E402
from stage import STAGES  # noqa: E402
from station import stage_title, STAR_AT  # noqa: E402

out = ["# Lab Simulator: design", "",
       "The 20 techniques, grouped in four wings around the board, and the minigames played at each bench.",
       "Every step scores 0-100; the average of the steps gives 1, 2 or 3 stars (%d, %d, %d points)." % STAR_AT,
       "Each technique has its own procedurally composed tune.", ""]
for wing in WINGS:
    out += ["## %s" % wing, ""]
    for t in [t for t in TECHS if t["wing"] == wing]:
        m = t["music"]
        out += ["### %d. %s" % (TECHS.index(t) + 1, t["full"]), "", t["blurb"], "",
                "*Music: %s* (%s, %d bpm, %s lead)" % (m.get("name", ""), m.get("mode", "maj"), m.get("bpm", 100), m.get("lead", "flute")), ""]
        for k, (kind, p) in enumerate(t["stages"]):
            instr = p.get("instr", STAGES[kind].instr).replace("\n", " ")
            out.append("%d. **%s.** %s" % (k + 1, stage_title(kind, p), instr))
        out.append("")
out += ["## The board", "",
        "28 benches in a loop: the 20 techniques in wing order, with Start, two Lab notebook, two Seminar,",
        "one Coffee, one Contamination and one Conference bench between them. See README.md for the rules.", ""]
text = core.pretty("\n".join(out).replace(" deg C", "°C"))
open(os.path.join(HERE, "DESIGN.md"), "w", encoding="utf-8", newline="\n").write(text)
print("DESIGN.md: %d lines" % len(out))
