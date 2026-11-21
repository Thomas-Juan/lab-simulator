# -*- coding: utf-8 -*-
"""The 20 techniques, gathered from the four wing modules.

A technique is a dict:
    key     short id, also the music key ("pcr")
    name    short name shown on the board ("PCR")
    full    full name ("Polymerase chain reaction")
    wing    one of WINGS
    icon    key for gfx.icon()
    blurb   one or two plain sentences: what the technique is for
    facts   list of true fun facts, one or two sentences each (at least 6)
    quiz    list of {q, options, answer, why} for the board's Seminar tiles (at least 3)
    music   tune spec for audio.py (see audio.TUNE_HELP)
    stages  list of (stage kind, params) played in order (see stage.py)"""
from tech_dna import TECHS as DNA
from tech_genes import TECHS as GENES
from tech_proteins import TECHS as PROTEINS
from tech_cells import TECHS as CELLS

WINGS = {
    "DNA": (224, 97, 63),
    "Genes & genomes": (42, 157, 153),
    "Proteins": (110, 90, 158),
    "Cells & embryos": (214, 150, 60),
}

TECHS = DNA + GENES + PROTEINS + CELLS
BY_KEY = {t["key"]: t for t in TECHS}
