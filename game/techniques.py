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

# The soundtrack: one grown-up track per technique (genre, tempo, key, mode, progression, lead sound).
# Each technique keeps the melodic hook ("motif") written in its own module.
MUSIC = {
    "pcr":       dict(name="Thermal Cycle", genre="funk", bpm=114, root=50, mode="dor", prog=[0, 3, 0, 4, 0, 3, 6, 4], lead="keys", swing=0.06),
    "gel":       dict(name="Ninety Volts", genre="halftime", bpm=140, root=48, mode="min", prog=[0, 5, 2, 6, 0, 5, 3, 4], lead="saw"),
    "extract":   dict(name="Spin Down", genre="shuffle", bpm=112, root=52, mode="blues", prog=[0, 0, 3, 0, 4, 3, 0, 4], lead="organ", swing=0.3),
    "clone":     dict(name="Sticky Ends", genre="minimal", bpm=124, root=45, mode="harm", prog=[0, 0, 5, 4, 0, 0, 5, 6], lead="saw"),
    "transform": dict(name="Heat Shock", genre="breakbeat", bpm=132, root=50, mode="mix", prog=[0, 6, 3, 0, 0, 6, 3, 4], lead="brass"),
    "sanger":    dict(name="Four Colours", genre="jazzfunk", bpm=104, root=53, mode="dor", prog=[0, 3, 6, 2, 5, 1, 4, 4], lead="keys", swing=0.22),
    "qpcr":      dict(name="Threshold", genre="trance", bpm=134, root=47, mode="min", prog=[0, 5, 2, 6, 0, 5, 3, 4], lead="saw"),
    "ngs":       dict(name="Flow Cell", genre="dnb", bpm=172, root=46, mode="min", prog=[0, 0, 5, 6, 0, 0, 3, 4], lead="saw"),
    "crispr":    dict(name="Cut Site", genre="halftime", bpm=88, root=49, mode="phr", prog=[0, 1, 0, 6, 0, 1, 5, 4], lead="brass"),
    "ish":       dict(name="Sixty-Five Degrees", genre="downtempo", bpm=84, root=50, mode="harm", prog=[0, 5, 3, 4, 0, 5, 1, 4], lead="keys"),
    "sds":       dict(name="Two Hundred Volts", genre="cinematic", bpm=120, root=48, mode="min", prog=[0, 5, 6, 4, 0, 5, 3, 4], lead="brass"),
    "western":   dict(name="Transfer", genre="shuffle", bpm=88, root=50, mode="blues", prog=[0, 3, 0, 0, 3, 3, 0, 4], lead="organ", swing=0.3),
    "elisa":     dict(name="Plate Reader", genre="latin", bpm=122, root=53, mode="dor", prog=[0, 3, 4, 3, 0, 3, 6, 4], lead="pluck"),
    "purify":    dict(name="Elution", genre="house", bpm=122, root=48, mode="min", prog=[0, 5, 3, 6, 0, 5, 3, 4], lead="keys"),
    "if":        dict(name="Confocal", genre="ambient", bpm=90, root=52, mode="lyd", prog=[0, 1, 0, 4, 0, 1, 5, 4], lead="lead_soft"),
    "culture":   dict(name="Laminar Flow", genre="downtempo", bpm=86, root=50, mode="dor", prog=[0, 3, 6, 4, 0, 3, 2, 4], lead="keys"),
    "count":     dict(name="Ten to the Fourth", genre="minimal", bpm=120, root=47, mode="min", prog=[0, 0, 5, 5, 3, 3, 4, 4], lead="pluck"),
    "transfect": dict(name="Lipid Bilayer", genre="house", bpm=118, root=50, mode="dor", prog=[0, 6, 3, 4, 0, 6, 3, 4], lead="saw"),
    "facs":      dict(name="Droplet Sort", genre="dnb", bpm=174, root=45, mode="min", prog=[0, 5, 3, 6, 0, 5, 2, 4], lead="saw"),
    "inject":    dict(name="One-Cell Stage", genre="cinematic", bpm=96, root=50, mode="harm", prog=[0, 5, 3, 4, 0, 5, 6, 4], lead="strings"),
}
for _t in TECHS:
    if _t["key"] in MUSIC:
        _hook = _t.get("music", {}).get("motif")
        _t["music"] = dict(MUSIC[_t["key"]], motif=_hook)
