# -*- coding: utf-8 -*-
"""Wing "Genes & genomes": Sanger, qPCR, NGS, CRISPR-Cas9 and in situ hybridisation (board order)."""
from genes_sanger import TECH as SANGER
from genes_qpcr import TECH as QPCR
from genes_ngs import TECH as NGS
from genes_crispr import TECH as CRISPR
from genes_ish import TECH as ISH

TECHS = [SANGER, QPCR, NGS, CRISPR, ISH]
