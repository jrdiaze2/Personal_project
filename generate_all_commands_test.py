#!/usr/bin/env python3
"""
Script para generar los 8 tipos de comandos para un JIRA key específico
"""

import sys
import os

import re

# Agregar el directorio actual al path para importar el módulo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar funciones necesarias del script principal
from jira_extractor import JiraExtractor
from command_generator_from_jira import (
    extract_platform_number,
    get_build_prefix,
    find_builds_by_branches,
    get_branches_from_fix_version
)

def generate_all_command_types(jira_key, token):
    """Genera los 8 tipos de comandos para un JIRA key"""
    
    print(f"\n{'='*70}")
    print(f"GENERANDO 8 TIPOS DE COMANDOS PARA: {jira_key}")
    print(f"{'='*70}\n")
    
    # Extraer datos de JIRA
    print("Extrayendo datos de JIRA...")
    extractor = JiraExtractor(token=token)
    issue_data = extractor.get_issue_data(jira_key)
    
    if not issue_data:
        print(f"❌ No se pudo obtener datos del issue {jira_key}")
        return
    
    jira_data = extractor.parse_issue_data(issue_data)
    if not jira_data:
        print(f"❌ No se pudo parsear datos del issue {jira_key}")
        return
    
    # Mostrar datos extraídos
    print("\n✓ Datos extraídos:")
    print(f"  Test Case:      {jira_data.get('test_case', 'N/A')}")
    print(f"  Platform:       {jira_data.get('platform', 'N/A')}")
    print(f"  Finding Branch: {jira_data.get('finding_branch', 'N/A')}")
    print(f"  Fix Version/s:  {jira_data.get('fix_versions', 'N/A')}")
    
    # Obtener plataforma
    platform = jira_data.get('platform', 'N/A')
    platform_num = extract_platform_number(platform)
    
    if not platform_num:
        print(f"⚠ No se pudo detectar plataforma desde: {platform}")
        platform_num = '6400'  # Default
    
    print(f"\n✓ Plataforma detectada: {platform_num}")
    platform_param = platform_num
    
    # Obtener branches
    fix_version = jira_data.get('fix_versions', 'N/A')
    branches_to_use = get_branches_from_fix_version(fix_version)
    
    if not branches_to_use:
        finding_branch = jira_data.get('finding_branch', '').strip()
        if finding_branch:
            print(f"⚠ Usando solo Finding Branch: {finding_branch}")
            branches_to_use = [finding_branch]
        else:
            print(f"❌ No se pudo determinar branch")
            return
    
    print(f"✓ Branches a usar: {', '.join(branches_to_use)}")
    
    # Obtener prefijo de build
    build_prefix = get_build_prefix(platform_num)
    if not build_prefix:
        print(f"⚠ No se encontró prefijo de build para plataforma: {platform_num}")
        return
    
    print(f"✓ Prefijo de build: {build_prefix}")
    
    # Buscar builds
    print(f"\nBuscando builds...")
    all_builds = find_builds_by_branches(branches_to_use, build_prefix)
    
    if not all_builds:
        print("⚠ No se encontraron builds")
        return
    
    # Agrupar por branch y tomar los 2 más recientes
    from collections import defaultdict
    branches_dict = defaultdict(list)
    for build_path in all_builds:
        # Extraer branch del nombre del archivo
        match = re.search(r'([a-zA-Z0-9_]+)_2025', build_path)
        branch = match.group(1) if match else 'unknown'
        branches_dict[branch].append(build_path)

    for branch in branches_dict:
        branches_dict[branch] = branches_dict[branch][:2]

    test_case = jira_data.get('test_case', 'N/A')
    retries = 2

    branch_with_2_builds = None
    builds_for_multi = None
    for branch, builds in branches_dict.items():
        if len(builds) >= 2 and builds[0] != builds[1]:
            branch_with_2_builds = branch
            builds_for_multi = builds
            break

    if not branch_with_2_builds:
        branch_single = list(branches_dict.keys())[0]
        builds_single = branches_dict[branch_single]
        print(f"\n⚠ No hay builds distintos suficientes para ISSU/UPGRADE_DOWNGRADE")
        print(f"  Usando branch {branch_single} para comandos single-build")
    else:
        branch_single = branch_with_2_builds
        builds_single = builds_for_multi
        print(f"\n✓ Usando branch {branch_with_2_builds} con 2 builds para comandos multi-build")
    
    print(f"\nGenerando comandos...\n")
    print(f"{'='*70}")
    
    commands = []
    
    # 1. Normal
    cmd1 = (
        f"ht -t {test_case} "
        f"-i {builds_single[0]} "
        f"-y "
        f"-h {platform_param} "
        f"-r {retries} "
        f"-m {jira_key}#NoKill"
    )
    commands.append(("1. Normal", cmd1))
    
    # 2. ISSU (sin flags) - requiere 2 builds
    if builds_for_multi and len(builds_for_multi) >= 2:
        platform_issu = f"{platform_param}ISSU"
        cmd2 = (
            f"ht -t {test_case} "
            f"-i {builds_for_multi[1]} "
            f"-y "
            f"-h {platform_issu} "
            f"-r {retries} "
            f"-secBuildImage {builds_for_multi[0]} "
            f"-m {jira_key}#NoKill"
        )
        commands.append(("2. ISSU (sin flags)", cmd2))
    else:
        commands.append(("2. ISSU (sin flags)", "❌ Requiere 2 builds distintos - no disponible"))
    
    # 3. ISSU con --issu-upgrade-on-ha - requiere 2 builds
    if builds_for_multi and len(builds_for_multi) >= 2:
        platform_issu = f"{platform_param}ISSU"
        cmd3 = (
            f"ht -t {test_case} "
            f"-i {builds_for_multi[1]} "
            f"-y "
            f"-h {platform_issu} "
            f"-r {retries} "
            f"-secBuildImage {builds_for_multi[0]} "
            f"-passThru --issu-upgrade-on-ha "
            f"-m {jira_key}#NoKill"
        )
        commands.append(("3. ISSU con --issu-upgrade-on-ha", cmd3))
    else:
        commands.append(("3. ISSU con --issu-upgrade-on-ha", "❌ Requiere 2 builds distintos - no disponible"))
    
    # 4. ISSU con --issu-allow-same-version
    platform_issu = f"{platform_param}ISSU"
    cmd4 = (
        f"ht -t {test_case} "
        f"-i {builds_single[0]} "
        f"-y "
        f"-h {platform_issu} "
        f"-r {retries} "
        f"-passThru --issu-allow-same-version "
        f"-m {jira_key}#NoKill"
    )
    commands.append(("4. ISSU con --issu-allow-same-version", cmd4))
    
    # 5. DRY_RUN
    cmd5 = (
        f"ht -t {test_case} "
        f"-i {builds_single[0]} "
        f"-y "
        f"-h {platform_param} "
        f"-r {retries} "
        f"-passThru --dry-run "
        f"-m {jira_key}#NoKill"
    )
    commands.append(("5. DRY_RUN", cmd5))
    
    # 6. CONFIG_RESTORE
    cmd6 = (
        f"ht -t {test_case} "
        f"-i {builds_single[0]} "
        f"-y "
        f"-h {platform_param} "
        f"-r {retries} "
        f"-passThru --config-restore "
        f"-m {jira_key}#NoKill"
    )
    commands.append(("6. CONFIG_RESTORE", cmd6))
    
    # 7. UPGRADE_DOWNGRADE - requiere 2 builds
    if builds_for_multi and len(builds_for_multi) >= 2:
        cmd7 = (
            f"ht -t {test_case} "
            f"-i {builds_for_multi[1]} "
            f"-y "
            f"-h {platform_param} "
            f"-r {retries} "
            f"-passThru --upgrade-downgrade "
            f"-secBuildImage {builds_for_multi[0]} "
            f"-m {jira_key}#NoKill"
        )
        commands.append(("7. UPGRADE_DOWNGRADE", cmd7))
    else:
        commands.append(("7. UPGRADE_DOWNGRADE", "❌ Requiere 2 builds distintos - no disponible"))
    
    # 8. HOTPATCH - requiere selección de patch (simularemos con mensaje)
    commands.append(("8. HOTPATCH", "⚠ Requiere selección interactiva de patch - no implementado en este test"))
    
    # Mostrar todos los comandos
    for idx, (tipo, comando) in enumerate(commands, 1):
        print(f"\n{tipo}")
        print("-" * 70)
        print(comando)
        print()
    
    print(f"{'='*70}")
    print(f"✓ Total comandos generados: {len([c for c in commands if not c[1].startswith('❌') and not c[1].startswith('⚠')])}/8")
    print(f"{'='*70}\n")
    
    # Guardar en archivo
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"test_8_commands_{jira_key}_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(f"# 8 Tipos de Comandos para JIRA: {jira_key}\n")
        f.write(f"# Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*70}\n\n")
        
        for tipo, comando in commands:
            f.write(f"{tipo}\n")
            f.write("-" * 70 + "\n")
            f.write(f"{comando}\n\n")
        
        f.write(f"{'='*70}\n")
    
    print(f"✓ Comandos guardados en: {filename}")


def generate_command_interactive(jira_key, token):
    print(f"\n{'='*70}")
    print(f"DATOS DE JIRA: {jira_key}")
    print(f"{'='*70}\n")
    extractor = JiraExtractor(token=token)
    issue_data = extractor.get_issue_data(jira_key)
    if not issue_data:
        print(f"❌ No se pudo obtener datos del issue {jira_key}")
        return None
    jira_data = extractor.parse_issue_data(issue_data)
    if not jira_data:
        print(f"❌ No se pudo parsear datos del issue {jira_key}")
        return None
    print("\n✓ Datos extraídos:")
    print(f"  Test Case:      {jira_data.get('test_case', 'N/A')}")
    print(f"  Platform:       {jira_data.get('platform', 'N/A')}")
    print(f"  Finding Branch: {jira_data.get('finding_branch', 'N/A')}")
    print(f"  Fix Version/s:  {jira_data.get('fix_versions', 'N/A')}")

    # Menú de modo de generación
    print("\nSeleccione el modo de generación:")
    print("  [1] Generar comando para un build específico")
    print("  [2] Generar comandos para todos los branches")
    print("  [3] Desde el Fix Version hacia arriba")
    modo = input("Ingrese opción [1-3]: ").strip()
    if modo not in {'1', '2', '3'}:
        print("Opción inválida. Usando modo 1 por defecto.")
        modo = '1'

    # Menú de tipo de comando
    print("\nTipos de comando:")
    print("  [1] Normal: Comando estándar de validación")
    print("  [2] ISSU (sin flags): Actualización ISSU sin banderas adicionales")
    print("  [3] ISSU con -passThru --issu-upgrade-on-ha: Actualización ISSU en HA")
    print("  [4] ISSU con -passThru --issu-allow-same-version: Permite misma versión en ISSU")
    print("  [5] DRY_RUN: Simulación sin cambios reales")
    print("  [6] CONFIG_RESTORE: Restauración de configuración")
    print("  [7] UPGRADE_DOWNGRADE: Comando para upgrade/downgrade")
    print("  [8] HOTPATCH: Aplicación de hotpatch")
    tipo = input("Ingrese tipo de comando [1-8]: ").strip()
    if tipo not in {str(i) for i in range(1,9)}:
        print("Tipo inválido. Usando tipo 1 por defecto.")
        tipo = '1'

    # Procesar datos y generar comando según modo y tipo
    platform = jira_data.get('platform', 'N/A')
    platform_num = extract_platform_number(platform)
    if not platform_num:
        print(f"⚠ No se pudo detectar plataforma desde: {platform}")
        platform_num = '6400'
    platform_param = platform_num
    fix_version = jira_data.get('fix_versions', 'N/A')
    branches_to_use = get_branches_from_fix_version(fix_version)
    if modo == '1':
        branches_to_use = branches_to_use[:1]
    elif modo == '3':
        branches_to_use = [b for b in branches_to_use if fix_version.replace('.', '_') in b or b == 'master']
    build_prefix = get_build_prefix(platform_num)
    if not build_prefix:
        print(f"⚠ No se encontró prefijo de build para plataforma: {platform_num}")
        return None
    print(f"✓ Prefijo de build: {build_prefix}")
    all_builds = find_builds_by_branches(branches_to_use, build_prefix)
    if not all_builds:
        print("⚠ No se encontraron builds")
        return None
    test_case = jira_data.get('test_case', 'N/A')
    retries = 2
    comando = None
    if tipo == '1':
        comando = f"ht -t {test_case} -i {all_builds[0]} -y -h {platform_param} -r {retries} -m {jira_key}#NoKill"
    elif tipo == '2':
        comando = f"ht -t {test_case} -i {all_builds[0]} -y -h {platform_param}ISSU -r {retries} -secBuildImage {all_builds[0]} -m {jira_key}#NoKill"
    elif tipo == '3':
        comando = f"ht -t {test_case} -i {all_builds[0]} -y -h {platform_param}ISSU -r {retries} -secBuildImage {all_builds[0]} -passThru --issu-upgrade-on-ha -m {jira_key}#NoKill"
    elif tipo == '4':
        comando = f"ht -t {test_case} -i {all_builds[0]} -y -h {platform_param}ISSU -r {retries} -passThru --issu-allow-same-version -m {jira_key}#NoKill"
    elif tipo == '5':
        comando = f"ht -t {test_case} -i {all_builds[0]} -y -h {platform_param} -r {retries} -passThru --dry-run -m {jira_key}#NoKill"
    elif tipo == '6':
        comando = f"ht -t {test_case} -i {all_builds[0]} -y -h {platform_param} -r {retries} -passThru --config-restore -m {jira_key}#NoKill"
    elif tipo == '7':
        comando = f"ht -t {test_case} -i {all_builds[0]} -y -h {platform_param} -r {retries} -passThru --upgrade-downgrade -secBuildImage {all_builds[0]} -m {jira_key}#NoKill"
    elif tipo == '8':
        comando = f"ht -t {test_case} -i {all_builds[0]} -y -h {platform_param} -r {retries} -p PATCH_ID -m {jira_key}#NoKill"
    print(f"\nComando generado:")
    print("-"*70)
    print(comando)
    print("-"*70)
    return comando

if __name__ == '__main__':
    if len(sys.argv) < 2:
        jira_keys = input("Ingrese las JIRA keys separadas por coma: ").strip().split(',')
    else:
        jira_keys = sys.argv[1].split(',')
    token = None
    try:
        import jira_extractor
        if hasattr(jira_extractor, 'JIRA_TOKEN'):
            token = getattr(jira_extractor, 'JIRA_TOKEN')
    except Exception:
        pass
    if not token:
        if len(sys.argv) < 3:
            token = input("Ingrese el token JIRA: ").strip()
        else:
            token = sys.argv[2]
    print(f"\nToken: {'***' if token else '[NO TOKEN]'}")
    comandos_generados = []
    for key in jira_keys:
        comando = generate_command_interactive(key.strip(), token)
        if comando:
            comandos_generados.append(comando)
    if comandos_generados:
        from datetime import datetime
        filename = f"comandos_jira_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w') as f:
            for c in comandos_generados:
                f.write(c + '\n')
        print(f"\n✓ Comandos guardados en: {filename}")
