# -*- coding: utf-8 -*-
"""Proteins wing: SDS-PAGE, Western blot, sandwich ELISA, His-tag purification,
immunofluorescence and fluorescence microscopy. Each technique lives in its own module."""
from proteins_sds import TECH as SDS
from proteins_western import TECH as WESTERN
from proteins_elisa import TECH as ELISA
from proteins_purify import TECH as PURIFY
from proteins_if import TECH as IF

TECHS = [SDS, WESTERN, ELISA, PURIFY, IF]
