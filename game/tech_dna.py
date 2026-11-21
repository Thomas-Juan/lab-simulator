# -*- coding: utf-8 -*-
"""DNA wing: PCR, agarose gel, extraction, cloning, transformation (one module per technique)."""
from dna_pcr import TECH as PCR
from dna_gel import TECH as GEL
from dna_extract import TECH as EXTRACT
from dna_clone import TECH as CLONE
from dna_transform import TECH as TRANSFORM

TECHS = [PCR, GEL, EXTRACT, CLONE, TRANSFORM]
