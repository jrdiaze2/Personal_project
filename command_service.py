#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servicio de generación de comandos
Versión independiente para la web app - NO modifica los scripts originales
"""

import sys
import os
from collections import defaultdict
from datetime import datetime
import glob
import re

# Agregar path para importar módulos del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from jira_extractor import JiraExtractor

# ============================================================================
# CONSTANTES - Copiadas del script original para independencia
# ============================================================================

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

# Lista de todos los branches
ALL_BRANCHES = [
    'master',
    '10_17_0001',
    '10_17',
    '10_16_1020',
    '10_16_1010',
    '10_16',
    '10_15',
    '10_15_1060',
    '10_13_1150',
    '10_13_1140',
    '10_13'
]

# ============================================================================
# FUNCIONES AUXILIARES - Copiadas del script original
# ============================================================================

def extract_platform_number(platform_str):
    """Extrae el número de plataforma limpio"""
    if not platform_str or platform_str == 'N/A':
        return None
    
    # Convertir a mayúsculas para búsqueda
    upper_platform = platform_str.upper()
    
    # IMPORTANTE: Buscar primero variantes con letra (más específicas)
    platform_variants = {
        '10000L': '10000L',
        '9300S': '9300S',
        '8325H': '8325H',
        '8325P': '8325P',
        '8400X': '8400',
        '6300F': '6300F',
        '6300M': '6300M',
        '6300L': '6300L',
        '6200F': '6200F',
        '6200M': '6200M',
        '4100I': '4100i',
        'VDUT': 'vdut',
    }
    
    for variant, mapped in platform_variants.items():
        if variant in upper_platform:
            return mapped
    
    # Luego buscar plataformas base
    for platform in PLATFORM_BUILD_PREFIX.keys():
        if platform in platform_str:
            return platform
    
    # Finalmente intentar extraer número de 4-5 dígitos
    match = re.search(r'(\d{4,5})', platform_str)
    if match:
        num = match.group(1)
        if num in PLATFORM_BUILD_PREFIX:
            return num
    
    return None


def get_build_prefix(platform_num):
    """Obtiene el prefijo de build para una plataforma"""
    return PLATFORM_BUILD_PREFIX.get(platform_num, None)


def parse_fix_version_to_branch(fix_version):
    """Convierte Fix Version a formato de branch"""
    if not fix_version or fix_version in ['N/A', 'backlog']:
        return None
    
    # CPE16.1020 -> 10_16_1020
    if fix_version.startswith('CPE'):
        version_num = fix_version.replace('CPE', '').replace('.', '_')
        if len(version_num) >= 6:
            return f"10_{version_num}"
    
    # Halon 16.1005 -> 10_16_1005
    if 'halon' in fix_version.lower():
        match = re.search(r'(\d+)\.(\d+)', fix_version)
        if match:
            major = match.group(1).zfill(2)
            minor = match.group(2).zfill(4)
            return f"10_{major}_{minor}"
    
    # 16.11 -> 10_16
    match = re.search(r'(\d+)\.(\d+)', fix_version)
    if match:
        major = match.group(1).zfill(2)
        minor = match.group(2).zfill(2)
        if len(minor) == 2:
            return f"10_{major}"
        else:
            return f"10_{major}_{minor}"
    
    return None


def get_branches_from_fix_version(fix_version, finding_branch=None):
    """Obtiene la lista de branches desde Fix Version hasta master"""
    if not fix_version or fix_version in ['N/A', 'backlog']:
        if finding_branch and finding_branch != 'N/A':
            return [finding_branch]
        return None
    
    branch_from_fix = parse_fix_version_to_branch(fix_version)
    
    if not branch_from_fix:
        if finding_branch and finding_branch != 'N/A':
            return [finding_branch]
        return None
    
    if branch_from_fix not in ALL_BRANCHES:
        if finding_branch and finding_branch != 'N/A':
            return [finding_branch]
        return None
    
    start_index = ALL_BRANCHES.index(branch_from_fix)
    return ALL_BRANCHES[start_index:]


def find_builds_by_branches(build_prefix, platform_num, branches_filter=None):
    """Busca builds disponibles por branches"""
    if branches_filter is None:
        branches_filter = ALL_BRANCHES
    
    print(f"[DEBUG] platform_num recibido (inicio): {platform_num}")
    print(f"[DEBUG] branches_filter recibido: {branches_filter}")
    all_builds = []
    seen_filenames = set()

    for branch in branches_filter:
        if branch == 'master':
            print(f"[DEBUG] platform_num recibido: {platform_num}")
            print(f"[DEBUG] Claves PLATFORM_MASTER_PREFIX: {list(PLATFORM_MASTER_PREFIX.keys())}")
            master_prefix = PLATFORM_MASTER_PREFIX.get(platform_num)
            if master_prefix:
                pub_pattern = f"/aruba/pub/{master_prefix}master*.swi"
                print(f"[DEBUG] Buscando builds de master con patrón: {pub_pattern}")
                swi_files = glob.glob(pub_pattern)
                print(f"[DEBUG] Archivos encontrados para master: {swi_files}")
            else:
                print(f"[DEBUG] No se encontró master_prefix para plataforma {platform_num}")
                swi_files = []
        else:
            release_pattern = f"/aruba/release/rel_{branch}*"
            release_dirs = glob.glob(release_pattern)
            swi_files = []
            for release_dir in release_dirs:
                official_dir = os.path.join(release_dir, "official")
                if not os.path.exists(official_dir):
                    continue
                swi_pattern = os.path.join(official_dir, f"{build_prefix}{branch}*", f"{build_prefix}{branch}*.swi")
                swi_files.extend(glob.glob(swi_pattern))
            # Filtrado especial para branches base: excluir solo los sub-branches conocidos
            if branch in ['10_17', '10_16', '10_15', '10_13']:
                # Construir lista de sub-branches conocidos para este branch base
                sub_branches = [b for b in ALL_BRANCHES if b.startswith(branch + '_')]
                filtered_files = []
                for swi_file in swi_files:
                    filename = os.path.basename(swi_file)
                    # Verificar si pertenece a algún sub-branch conocido
                    belongs_to_sub = False
                    for sub in sub_branches:
                        if f"{build_prefix}{sub}" in filename:
                            belongs_to_sub = True
                            break
                    if not belongs_to_sub:
                        filtered_files.append(swi_file)
                swi_files = filtered_files
            for swi_file in swi_files:
                filename = os.path.basename(swi_file)
                if filename in seen_filenames:
                    continue
                seen_filenames.add(filename)
                mtime = os.path.getmtime(swi_file)
                all_builds.append({
                    'path': swi_file,
                    'branch': branch,
                    'mtime': mtime,
                    'mtime_str': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                })
    
    all_builds.sort(key=lambda x: (ALL_BRANCHES.index(x['branch']) if x['branch'] in ALL_BRANCHES else 999, -x['mtime']))
    
    branches_dict = defaultdict(list)
    for build in all_builds:
        if len(branches_dict[build['branch']]) < 2:
            branches_dict[build['branch']].append(build)
    
    return [build for builds in branches_dict.values() for build in builds]


class CommandService:
    """Servicio para generación de comandos desde JIRA"""
    
    COMMAND_TYPES = {
        '1': 'Normal',
        '2': 'ISSU (sin flags)',
        '3': 'ISSU con --issu-upgrade-on-ha',
        '4': 'ISSU con --issu-allow-same-version',
        '5': 'DRY_RUN',
        '6': 'CONFIG_RESTORE',
        '7': 'UPGRADE_DOWNGRADE',
        '8': 'HOTPATCH'
    }
    
    def __init__(self, token):
        """
        Inicializar servicio
        
        Args:
            token: Bearer token para JIRA
        """
        self.token = token
        self.extractor = JiraExtractor(token=token)
    
    def get_jira_data(self, jira_key):
        """
        Extraer datos de un JIRA key
        
        Args:
            jira_key: Key de JIRA (ej: AOSCX-12345)
            
        Returns:
            dict: Datos extraídos del JIRA con claves normalizadas
        """
        issue_data = self.extractor.get_issue_data(jira_key)
        if not issue_data:
            return None
        
        jira_data = self.extractor.parse_issue_data(issue_data)
        
        # Normalizar claves para consistencia con la web app
        # jira_extractor devuelve 'fix_versions' pero algunos lugares esperan 'fix_version'
        if jira_data and 'fix_versions' in jira_data:
            jira_data['fix_version'] = jira_data['fix_versions']
        
        return jira_data
    
    def find_available_builds(self, platform_num, branches_filter=None):
        """
        Buscar builds disponibles
        
        Args:
            platform_num: Número de plataforma (ej: 6400)
            branches_filter: Lista de branches a filtrar (opcional)
            
        Returns:
            list: Lista de builds agrupados por branch
        """
        build_prefix = get_build_prefix(platform_num)
        if not build_prefix:
            return []
        
        all_builds = find_builds_by_branches(build_prefix, platform_num, branches_filter)
        
        # Agrupar por branch
        branches_dict = defaultdict(list)
        for build_info in all_builds:
            branch = build_info['branch']
            branches_dict[branch].append(build_info)
        
        # Mantener solo los 2 más recientes por branch
        for branch in branches_dict:
            branches_dict[branch] = branches_dict[branch][:2]

        # Asegurar que 'master' siempre esté presente como clave
        if branches_filter and 'master' in branches_filter and 'master' not in branches_dict:
            branches_dict['master'] = []

        return branches_dict
    
    def find_patches_for_build(self, build_path):
        """
        Buscar patches disponibles para un build
        
        Args:
            build_path: Path completo del build
            
        Returns:
            list: Lista de patches [(nombre, path, fecha), ...]
        """
        build_base = os.path.basename(build_path).replace('.swi', '')
        
        # Extraer branch del nombre del build
        match = re.search(r'([A-Z]{2}_)?(\d{2}_\d{2}(?:_\d{4})?)', build_base)
        if not match:
            return []
        
        branch_from_build = match.group(2)
        
        # Buscar directorios de patches
        release_pattern = f"/aruba/release/rel_{branch_from_build}*"
        release_dirs = glob.glob(release_pattern)
        
        available_patches = []
        for release_dir in release_dirs:
            official_dir = os.path.join(release_dir, "official")
            if os.path.exists(official_dir):
                patch_dir = os.path.join(official_dir, build_base, "hot-patches")
                if os.path.isdir(patch_dir):
                    for f in os.listdir(patch_dir):
                        if f.endswith('.patch'):
                            patch_path = os.path.join(patch_dir, f)
                            mtime = os.path.getmtime(patch_path)
                            mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                            available_patches.append({
                                'name': f,
                                'path': patch_path,
                                'date': mtime_str,
                                'timestamp': mtime
                            })
        
        # Ordenar por fecha (más reciente primero)
        available_patches.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return available_patches
    
    def generate_command(self, jira_data, jira_key, command_type, platform_param, 
                        retries, builds, patch_path=None, additional_flags=None):
        """
        Generar un comando específico
        
        Args:
            jira_data: Datos del JIRA
            jira_key: Key de JIRA
            command_type: Tipo de comando ('1'-'8')
            platform_param: Parámetro -h
            retries: Número de reintentos
            builds: Lista de builds [más_reciente, segundo_más_reciente]
            patch_path: Path del patch (solo para HOTPATCH)
            additional_flags: Flags adicionales (opcional)
            
        Returns:
            dict: {
                'command': str,
                'build_primary': str,
                'build_secondary': str (opcional),
                'type': str
            }
        """
        test_case = jira_data.get('test_case', 'N/A')
        
        if test_case == 'N/A':
            raise ValueError("Test case no encontrado en datos de JIRA")
        
        command = None
        build_primary = builds[0]['path'] if builds else None
        build_secondary = builds[1]['path'] if len(builds) > 1 else None
        
        # Tipo 1: Normal
        if command_type == '1':
            command = (
                f"ht -t {test_case} "
                f"-i {build_primary} "
                f"-y "
                f"-h {platform_param} "
                f"-r {retries} "
                f"-m {jira_key}#NoKill"
            )
        
        # Tipos 2-3: ISSU multi-build
        elif command_type in ['2', '3']:
            if not build_secondary:
                raise ValueError("ISSU requiere 2 builds distintos")
            
            platform_issu = f"{platform_param}ISSU" if not platform_param.endswith('ISSU') else platform_param
            
            if command_type == '2':
                command = (
                    f"ht -t {test_case} "
                    f"-i {build_secondary} "
                    f"-y "
                    f"-h {platform_issu} "
                    f"-r {retries} "
                    f"-secBuildImage {build_primary} "
                    f"-m {jira_key}#NoKill"
                )
            else:  # command_type == '3'
                command = (
                    f"ht -t {test_case} "
                    f"-i {build_secondary} "
                    f"-y "
                    f"-h {platform_issu} "
                    f"-r {retries} "
                    f"-secBuildImage {build_primary} "
                    f"-passThru --issu-upgrade-on-ha "
                    f"-m {jira_key}#NoKill"
                )
        
        # Tipo 4: ISSU allow-same-version
        elif command_type == '4':
            platform_issu = f"{platform_param}ISSU" if not platform_param.endswith('ISSU') else platform_param
            command = (
                f"ht -t {test_case} "
                f"-i {build_primary} "
                f"-y "
                f"-h {platform_issu} "
                f"-r {retries} "
                f"-passThru --issu-allow-same-version "
                f"-m {jira_key}#NoKill"
            )
        
        # Tipo 5: DRY_RUN
        elif command_type == '5':
            command = (
                f"ht -t {test_case} "
                f"-i {build_primary} "
                f"-y "
                f"-h {platform_param} "
                f"-r {retries} "
                f"-passThru --dry-run "
                f"-m {jira_key}#NoKill"
            )
        
        # Tipo 6: CONFIG_RESTORE
        elif command_type == '6':
            command = (
                f"ht -t {test_case} "
                f"-i {build_primary} "
                f"-y "
                f"-h {platform_param} "
                f"-r {retries} "
                f"-passThru --config-restore "
                f"-m {jira_key}#NoKill"
            )
        
        # Tipo 7: UPGRADE_DOWNGRADE
        elif command_type == '7':
            if not build_secondary:
                raise ValueError("UPGRADE_DOWNGRADE requiere 2 builds distintos")
            
            command = (
                f"ht -t {test_case} "
                f"-i {build_secondary} "
                f"-y "
                f"-h {platform_param} "
                f"-r {retries} "
                f"-passThru --upgrade-downgrade "
                f"-secBuildImage {build_primary} "
                f"-m {jira_key}#NoKill"
            )
        
        # Tipo 8: HOTPATCH
        elif command_type == '8':
            if not patch_path:
                raise ValueError("HOTPATCH requiere selección de patch")
            
            command = (
                f"ht -t {test_case} "
                f"-y "
                f"-i {build_primary} "
                f"-passThru --hot-patch-on-setup "
                f"-h {platform_param} "
                f"-r {retries} "
                f"-m {jira_key}#NoKill "
                f"-p {patch_path}"
            )
        
        # Agregar flags adicionales si existen
        if additional_flags and command:
            command = command.replace(f"-m {jira_key}#NoKill", f"{additional_flags} -m {jira_key}#NoKill")
        
        return {
            'command': command,
            'build_primary': build_primary,
            'build_secondary': build_secondary,
            'type': self.COMMAND_TYPES.get(command_type, 'Unknown'),
            'type_id': command_type
        }
    
    def generate_commands_for_branches(self, jira_data, jira_key, command_type, 
                                      platform_param, retries, branches_dict, 
                                      patch_selections=None, additional_flags=None):
        """
        Generar comandos para múltiples branches
        
        Args:
            jira_data: Datos del JIRA
            jira_key: Key de JIRA
            command_type: Tipo de comando ('1'-'8')
            platform_param: Parámetro -h
            retries: Número de reintentos
            branches_dict: Dict de branches con sus builds
            patch_selections: Dict {branch: patch_path} para HOTPATCH
            additional_flags: Flags adicionales (opcional)
            
        Returns:
            list: Lista de comandos generados
        """
        commands = []
        
        for branch, builds in branches_dict.items():
            patch_path = None
            if command_type == '8' and patch_selections:
                patch_path = patch_selections.get(branch)
                if not patch_path:
                    continue  # Skip branch si no hay patch seleccionado
            
            try:
                cmd_info = self.generate_command(
                    jira_data, jira_key, command_type, platform_param,
                    retries, builds, patch_path, additional_flags
                )
                cmd_info['branch'] = branch
                cmd_info['build_date'] = builds[0]['mtime_str']
                commands.append(cmd_info)
            except ValueError as e:
                # Si falla (ej: ISSU sin 2 builds), generar comando normal
                if command_type in ['2', '3', '7']:
                    try:
                        cmd_info = self.generate_command(
                            jira_data, jira_key, '1', platform_param,
                            retries, builds, None, additional_flags
                        )
                        cmd_info['branch'] = branch
                        cmd_info['build_date'] = builds[0]['mtime_str']
                        cmd_info['warning'] = str(e)
                        commands.append(cmd_info)
                    except:
                        pass
        
        return commands
