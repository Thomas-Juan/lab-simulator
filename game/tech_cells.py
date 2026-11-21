# -*- coding: utf-8 -*-
"""Cells & embryos wing: cell culture, cell counting, transfection, FACS and zebrafish microinjection."""
from cells_culture import TECH as CULTURE
from cells_count import TECH as COUNT
from cells_transfect import TECH as TRANSFECT
from cells_facs import TECH as FACS
from cells_inject import TECH as INJECT

TECHS = [CULTURE, COUNT, TRANSFECT, FACS, INJECT]
