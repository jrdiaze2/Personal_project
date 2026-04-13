#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
command_generator_from_jira.py

Genera comandos de validación a partir de datos extraídos de JIRA.
"""

import re
from datetime import datetime
import glob

# Mapeo de plataformas a prefijos de build
PLATFORM_BUILD_PREFIX = {
    '4100i': 'RL_',
    '5420': 'BL_',
    '6000': 'PL_',
    '6100': 'PL_',
    '6200F': 'ML_',
    '6200M': 'ML_',
    '6300': 'FL_',
    '6300F': 'FL_',
    '6300M': 'FL_',
    '6300L': 'AL_',
    '6400': 'FL_',
    '8100': 'LL_',
    '8320': 'TL_',
    '8325': 'GL_',
    '8325H': 'HL_',
    '8325P': 'GL_',
    '8360': 'LL_',
    '8400': 'XL_',
    '9300': 'CL_',
    '9300S': 'NL_',
    '10000': 'DL_',
    '10000L': 'NL_',
    'vdut': 'genericx86-rosewood_essw_cit_',
}

PLATFORM_MASTER_PREFIX = {
    '4100i': 'lemans_essw_cit_',
    '5420': 'lightyear_essw_cit_',
    '6000': 'bristol_essw_cit_',
    '6100': 'bristol_essw_cit_',
    '6200F': 'tover_essw_cit_',
    '6200M': 'tover_essw_cit_',
    '6300': 'speedway_essw_cit_',
    '6300F': 'speedway_essw_cit_',
    '6300M': 'speedway_essw_cit_',
    '6300L': 'aspen_essw_cit_',
    '6400': 'speedway_essw_cit_',
    '8100': 'lucky_essw_cit_',
    '8320': 'topflite_essw_cit_',
    '8325': 'golfclub_essw_cit_',
    '8325H': 'carlsbad_essw_cit_',
    '8325P': 'golfclub_essw_cit_',
    '8360': 'lucky_essw_cit_',
    '8400': 'ridley_essw_cit_',
    '9300': 'carmel_essw_cit_',
    '9300S': 'paws_essw_cit_',
    '10000': 'taormina_essw_cit_',
    '10000L': 'paws_essw_cit_',
    'vdut': 'genericx86-rosewood_essw_cit_',
}

def extract_platform_number(platform_str):
    if not platform_str or platform_str == 'N/A':
        return None
    for platform in PLATFORM_BUILD_PREFIX.keys():
        if platform in platform_str:
            return platform
    return None

def get_build_prefix(platform):
    platform_str = str(platform)
    if platform_str in PLATFORM_BUILD_PREFIX:
        return PLATFORM_BUILD_PREFIX[platform_str]
    for key in PLATFORM_BUILD_PREFIX:
        if key in platform_str:
            return PLATFORM_BUILD_PREFIX[key]
    return None

def find_builds_by_branches(branches, build_prefix):
    # Genera nombres de build realistas según branch y prefijo
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    builds = []
    for branch in branches:
        branch_clean = branch.replace('rel/', '')
        if branch_clean == 'master':
            master_prefix = PLATFORM_MASTER_PREFIX.get(build_prefix.replace('_', ''), build_prefix)
            build_name = f"{master_prefix}master_{timestamp}.swi"
            builds.append(f"/aruba/pub/{build_name}")
        elif branch_clean.startswith('10_17'):
            build_name = f"FL_{branch_clean}_1000.swi"
            builds.append(f"/aruba/pub/{build_name}")
        elif branch_clean.startswith('10_16'):
            build_name = f"XL_{branch_clean}_1020L.swi"
            builds.append(f"/aruba/pub/{build_name}")
        elif branch_clean.startswith('10_15'):
            build_name = f"DL_{branch_clean}_1060.swi"
            builds.append(f"/aruba/pub/{build_name}")
        elif branch_clean.startswith('10_13'):
            build_name = f"DL_{branch_clean}_1140.swi"
            builds.append(f"/aruba/pub/{build_name}")
        else:
            build_name = f"{build_prefix}{branch_clean}_1000.swi"
            builds.append(f"/aruba/pub/{build_name}")
    return builds

def get_branches_from_fix_version(fix_version_str):
    fix_version_normalized = fix_version_str.replace('.', '_').replace('CPE', '').replace('N/A', '').strip()
    all_branches = [
        'master', '10_17_0001', '10_17_1000', '10_17', '10_16_1020', '10_16_1010', '10_16', '10_15', '10_13',
    ]
    branches = [b for b in all_branches if fix_version_normalized in b or b == 'master']
    return branches if branches else ['master']

