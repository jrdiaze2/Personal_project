def obtener_url_cit_logs(jira_key):
    """Busca la URL de CIT logs en la descripción o comentarios del JIRA, debajo de la palabra 'Cit Logs'."""
    datos = extraer_datos_jira(jira_key)
    import re
    descripcion = datos.get('description', '')
    url = None
    if descripcion:
        lines = descripcion.splitlines()
        for i, line in enumerate(lines):
            # Buscar en la misma línea que 'CIT Logs:'
            if re.search(r'cit logs', line, re.IGNORECASE):
                # Buscar URL en la misma línea
                url_match = re.search(r'(https?://\S+)', line)
                if url_match:
                    url = url_match.group(1)
                    break
                # Buscar URL en la siguiente línea
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    url_match = re.search(r'(https?://\S+)', next_line)
                    if url_match:
                        url = url_match.group(1)
                        break
        # Si no se encontró, buscar cualquier URL en la descripción
        if not url:
            urls = re.findall(r'(https?://\S+)', descripcion)
            if urls:
                url = urls[0]
            else:
                # Buscar hipervínculo markdown: [texto](url)
                md_links = re.findall(r'\[.*?\]\((https?://[^)]+)\)', descripcion)
                if md_links:
                    url = md_links[0]
    # Si no se encontró, buscar en los comentarios
    if not url and 'comment' in datos and datos['comment']:
        comments = datos['comment']
        if isinstance(comments, dict) and 'comments' in comments:
            for c in comments['comments']:
                body = c.get('body', '')
                # Buscar URLs relacionadas a CIT Logs en los comentarios
                lines = body.splitlines()
                for i, line in enumerate(lines):
                    if re.search(r'cit logs', line, re.IGNORECASE):
                        url_match = re.search(r'(https?://\S+)', line)
                        if url_match:
                            url = url_match.group(1)
                            break
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            url_match = re.search(r'(https?://\S+)', next_line)
                            if url_match:
                                url = url_match.group(1)
                                break
                if url:
                    break
                # Buscar cualquier URL en el comentario
                if not url:
                    urls = re.findall(r'(https?://\S+)', body)
                    if urls:
                        url = urls[0]
                        break
                # Buscar hipervínculo markdown en el comentario
                if not url:
                    md_links = re.findall(r'\[.*?\]\((https?://[^)]+)\)', body)
                    if md_links:
                        url = md_links[0]
                        break
    return url

# Utilidad para mostrar rutas de patch para todos los branches activos

def mostrar_rutas_patch(plataforma):
    branches_activos = [
        'rel/10_18', 'rel/10_17_0001', 'rel/10_17', 'rel/10_16_1020', 'rel/10_16_1010', 'rel/10_16',
        'rel/10_15', 'rel/10_13_1150', 'rel/10_13_1140', 'rel/10_13', 'rel/10_10_1170'
    ]
    plataforma_prefix = {
        "10000L": "NL_", "9300S": "NL_", "5420": "BL_", "6300L": "AL_", "8325H": "HL_", "8320": "TL_", "8400": "XL_",
        "8325P": "GL_", "8325": "GL_", "6300F": "FL_", "6300M": "FL_", "6400": "FL_", "6200F": "ML_", "6200M": "ML_",
        "6000": "PL_", "6100": "PL_", "8100": "LL_", "8360": "LL_", "4100i": "RL_", "10000": "DL_", "9300": "CL_"
    }
    prefijo = plataforma_prefix.get(plataforma, "FL_")
    print(f"\nRutas de patch para todos los branches activos (plataforma: {plataforma}, prefijo: {prefijo}):")
    import glob, os
    for branch in branches_activos:
        branch_num = branch.replace('rel/', '')
        build_glob = f"/aruba/release/rel_{branch_num}/official/{prefijo}{branch_num}*.swi"
        builds = sorted(glob.glob(build_glob), reverse=True)
        if builds:
            build_base = os.path.basename(builds[0]).replace('.swi', '')
            ruta = f"/aruba/release/rel_{branch_num}/official/{build_base}/hot-patches/"
            print(f"Branch: {branch} -> Build: {build_base} -> Ruta: {ruta}")
        else:
            print(f"Branch: {branch} -> No se encontró build con prefijo {prefijo}")

import sys
import os
import re
from pprint import pprint
from jira_config import jira_token

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import jira_api
import jira_config
import glob

def solicitar_modo_generacion():
    print('Seleccione el modo de generación:')
    print('  [1] Generar comando para un build específico (branch y build)')
    print('  [2] Generar comandos para todos los branches (10_13 hasta master)')
    print('  [3] Generar comandos desde el Fix Version extraído del JIRA hasta master')
    opcion = input('> ')
    return opcion.strip()

def solicitar_jira_keys():
    print('Ingrese los JIRA keys separados por coma:')
    keys = input('> ').replace(' ', '').split(',')
    print('Ingrese los JIRA keys separados por coma (máximo 6):')
    if len(keys) > 6:
        print('Solo se permiten hasta 6 JIRA keys. Se tomarán los primeros 6.')
        keys = keys[:6]
    elif len(keys) > 5:
        print('Advertencia: Solo se mostrarán mensajes para los primeros 5 JIRA keys.')
    return keys

def solicitar_tipo_comando(jira_key):
    print(f'JIRA Key: {jira_key}')
    print('Seleccione el tipo de comando:')
    print('  [1] Normal')
    print('  [2] ISSU (sin flags)')
    print('  [3] ISSU con -passThru --issu-upgrade-on-ha')
    print('  [4] ISSU con -passThru --issu-allow-same-version')
    print('  [5] DRY_RUN')
    print('  [6] CONFIG_RESTORE')
    print('  [7] UPGRADE_DOWNGRADE')
    print('  [8] HOTPATCH')
    print('  [9] ST_HOTPATCH')
    print('  [10] PSM')
    opcion = input('> ')
    return opcion.strip()

def extraer_datos_jira(jira_key):
    # Extrae los datos relevantes del ticket JIRA
    filtro = f'key = {jira_key}'
    fields = ['summary', 'description', 'fixVersions', 'customfield_11500', 'customfield_12002', 'customfield_12804', 'customfield_14407', 'customfield_14414', 'components', 'customfield_12810', 'priority', 'comment']
    jira_auth = jira_api.BearerAuth(jira_token)
    jira_url = "https://jira.arubanetworks.com"
    resultado = jira_api.find_issues_content(
        jql=filtro, fields=fields, auth=jira_auth, base_url=jira_url, max_result_size=1
    )
    if resultado:
        datos = resultado.get(jira_key, {})
        return datos
    return {}

def seleccionar_build(builds, param_name):
    print(f"\nSeleccione el build para el parámetro {param_name}:")
    for idx, build in enumerate(builds):
        print(f"  [{idx+1}] {build}")
    opcion = input('> ')
    try:
        idx = int(opcion) - 1
        if 0 <= idx < len(builds):
            return builds[idx]
    except Exception:
        pass
    print("Selección inválida, usando el más actualizado.")
    return builds[0] if builds else ''
    
def solicitar_tipo_build():
    print("\nSeleccione el tipo de build para el parámetro -i:")
    print("  [1] Build de CIT (formato ridley_essw_cit_...)")
    print("  [2] Letter Build (formato FL_10_17_1000.swi)")
    opcion = input('> ').strip()
    if opcion == '2':
        return 'letter'
    return 'cit'

def obtener_builds_actualizados(branch):
    plataforma_prefix = {
        "10000L": ["paws_essw_cit_", "NL_"],
        "9300S": ["paws_essw_cit_", "NL_"],
        "5420": ["lightyear_essw_cit_", "BL_"],
        "6300L": ["aspen_essw_cit_", "AL_"],
        "8325H": ["carlsbad_essw_cit_", "HL_"],
        "vdut": ["genericx86-rosewood_essw_cit_"],
        "8320": ["topflite_essw_cit_", "TL_"],
        "8400": ["ridley_essw_cit_", "XL_"],
        "8325P": ["golfclub_essw_cit_", "GL_"],
        "8325": ["golfclub_essw_cit_", "GL_"],
        "6300F": ["speedway_essw_cit_", "FL_"],
        "6300M": ["speedway_essw_cit_", "FL_"],
        "6400": ["speedway_essw_cit_", "FL_"],
        "6200F": ["tover_essw_cit_", "ML_"],
        "6200M": ["tover_essw_cit_", "ML_"],
        "6000": ["bristol_essw_cit_", "PL_"],
        "6100": ["bristol_essw_cit_", "PL_"],
        "8100": ["lucky_essw_cit_", "LL_"],
        "8360": ["lucky_essw_cit_", "LL_"],
        "4100i": ["lemans_essw_cit_", "RL_"],
        "10000": ["taormina_essw_cit_", "DL_"],
        "9300": ["carmel_essw_cit_", "CL_"],
    }
    def get_prefijos(plataforma):
        return plataforma_prefix.get(plataforma, [])
    # Recibe plataforma como argumento
    import inspect
    frame = inspect.currentframe().f_back
    plataforma = frame.f_locals.get('plataforma', None)
    prefijos = get_prefijos(plataforma)
    build_paths = []
    if branch == 'master':
        build_paths.append('/aruba/pub/*master*.swi')
    elif branch.startswith('rel/10_'):
        branch_clean = branch.replace('rel/', '')
        for pref in prefijos:
            # Buscar builds en /aruba/pub/prefix_branchnum*.swi
            build_paths.append(f'/aruba/pub/{pref}{branch_clean}*.swi')
    else:
        for pref in prefijos:
            build_paths.append(f'/aruba/pub/{pref}*.swi')
    builds = []
    for path in build_paths:
        builds.extend(glob.glob(path))
    builds = sorted(list(set(builds)), reverse=True)
    return builds

def obtener_patch(build):
    # Buscar el patch en la ruta correspondiente a HOTPATCH
    build_base = os.path.basename(build).replace('.swi', '')
    # Ejemplo build: FL_10_17_0001BF
    match = re.match(r'([A-Z]+)_(\d+_\d+)(?:_\d+)?[A-Z]*', build_base)
    if match:
        branch_num = match.group(2)   # 10_17
        patch_dir = f"/aruba/release/rel_{branch_num}/official/{build_base}/hot-patches/"
    else:
        patch_dir = os.path.dirname(build) + '/hot-patches/'

    print(f"\n[DEBUG] Directorio de patches para HOTPATCH: {patch_dir}")
    patch_path = os.path.join(patch_dir, '*.patch')
    # Buscar y mostrar solo los 5 patches más recientes para el branch/build seleccionados
    patches = sorted(glob.glob(patch_path), key=lambda x: os.path.getmtime(x), reverse=True)
    patches = patches[:5] if len(patches) > 5 else patches
    if patches:
        print(f"Parches más recientes disponibles para este branch/build:")
        for idx, patch in enumerate(patches):
            print(f"  [{idx+1}] {os.path.basename(patch)}")
        opcion = input('Seleccione el número de patch a usar: ').strip()
        try:
            idx = int(opcion) - 1
            if 0 <= idx < len(patches):
                selected_patch = patches[idx]
            else:
                selected_patch = patches[0]
        except Exception:
            selected_patch = patches[0]
        print(f"Patch seleccionado: {selected_patch}")
        return selected_patch
    else:
        print("No se encontraron parches en la ruta para este branch/build.")
        return ''

def extraer_branch_plataforma(datos):
    # Buscar branch y plataforma en los campos relevantes del ticket
    branch = 'master'
    # Lista estándar de plataformas
    plataformas_std = [
        "10000L", "9300S", "5420", "6300L", "8325H", "vdut", "8320", "8400", "8325P", "8325", "6300F", "6300M", "6400", "6200F", "6200M", "6000", "6100", "8100", "8360", "4100i", "10000", "9300"
    ]
    plataforma = None
    # Buscar branch en fixVersions
    if 'fixVersions' in datos and datos['fixVersions']:
        fix = datos['fixVersions'][0] if isinstance(datos['fixVersions'], list) else datos['fixVersions']
        # Si es formato rel_ lo usamos directo
        if 'rel_' in fix:
            branch = fix
        # Si es formato CPExx.xxxx lo convertimos a rel/10_xx_xxxx
        elif isinstance(fix, dict) and 'name' in fix:
            fix_name = fix['name']
            match = re.match(r'CPE(\d+)\.(\d+)', fix_name)
            if match:
                branch = f"rel/10_{match.group(1)}_{match.group(2)}"
        elif isinstance(fix, str):
            match_cpe = re.match(r'CPE(\d+)\.(\d+)', fix)
            if match_cpe:
                branch = f"rel/10_{match_cpe.group(1)}_{match_cpe.group(2)}"
            else:
                match_halon = re.match(r'Halon(\d+)\.(\d+)', fix)
                if match_halon:
                    branch = f"rel/10_{match_halon.group(1)}"
    # Buscar plataforma en 'Affected Platforms' dentro de la descripción
    if 'description' in datos and datos['description']:
        match = re.search(r'Affected Platforms:\s*([\w, ]+)', datos['description'])
        if match:
            # Tomar la primera plataforma listada
            plataformas_encontradas = [p.strip() for p in match.group(1).split(',') if p.strip() in plataformas_std]
            if plataformas_encontradas:
                plataforma = plataformas_encontradas[0]
    # Si no se encontró, buscar en components
    if not plataforma and 'components' in datos and datos['components']:
        comp = datos['components'][0] if isinstance(datos['components'], list) else datos['components']
        if isinstance(comp, dict) and 'name' in comp:
            if comp['name'] in plataformas_std:
                plataforma = comp['name']
        elif isinstance(comp, str) and comp in plataformas_std:
            plataforma = comp
    # Si no se pudo extraer, usar un valor por defecto
    if not plataforma:
        plataforma = "6400"
    return branch, plataforma

def generar_comando(key, tipo, branch, plataforma, build_i=None, r_value='2'):
    comando = ''
    # r_value is now always passed explicitly and used directly
    if build_i is None:
        # Si la plataforma contiene varias, probar todos los prefijos posibles
        plataformas_lista = [plataforma] if isinstance(plataforma, str) else plataforma
        prefijos_plataforma = {
            "10000L": ["NL_", "paws_essw_cit_"], "9300S": ["NL_", "paws_essw_cit_"], "5420": ["BL_", "lightyear_essw_cit_"],
            "6300L": ["AL_", "aspen_essw_cit_"], "8325H": ["HL_", "carlsbad_essw_cit_"], "vdut": ["genericx86-rosewood_essw_cit_"],
            "8320": ["TL_", "topflite_essw_cit_"], "8400": ["XL_", "ridley_essw_cit_"], "8325P": ["GL_", "golfclub_essw_cit_"],
            "8325": ["GL_", "golfclub_essw_cit_"], "6300F": ["FL_", "speedway_essw_cit_"], "6300M": ["FL_", "speedway_essw_cit_"],
            "6400": ["FL_", "speedway_essw_cit_"], "6200F": ["ML_", "tover_essw_cit_"], "6200M": ["ML_", "tover_essw_cit_"],
            "6000": ["PL_", "bristol_essw_cit_"], "6100": ["PL_", "bristol_essw_cit_"], "8100": ["LL_", "lucky_essw_cit_"],
            "8360": ["LL_", "lucky_essw_cit_"], "4100i": ["RL_", "lemans_essw_cit_"], "10000": ["DL_", "taormina_essw_cit_"],
            "9300": ["CL_", "carmel_essw_cit_"]
        }
        build_i = None
        build_sec = ''
        builds = []
        # Si la plataforma es una lista (ej: "8360, 8325PWS")
        if isinstance(plataforma, str) and ',' in plataforma:
            plataformas_lista = [p.strip() for p in plataforma.split(',')]
        for plat in plataformas_lista:
            prefijos = prefijos_plataforma.get(plat, [])
            branch_clean = branch.replace('rel/', '')
            for prefijo in prefijos:
                path = f'/aruba/pub/{prefijo}{branch_clean}*.swi'
                builds_encontrados = sorted(glob.glob(path), reverse=True)
                if builds_encontrados:
                    builds = builds_encontrados
                    break
            if builds:
                break
        if not builds:
            print(f"[ADVERTENCIA] No se encontró build para el branch {branch} y plataformas {plataformas_lista}. Comando omitido.")
            return ''
        # Para master, usar cit; para otros, forzar letter build
        if branch == 'master':
            builds_cit = [b for b in builds if 'essw_cit_' in os.path.basename(b)]
            builds_cit = sorted(builds_cit, reverse=True)
            build_i = builds_cit[0] if len(builds_cit) > 0 else builds[0]
            build_sec = builds_cit[1] if len(builds_cit) > 1 else ''
        else:
            builds_letter = [b for b in builds if re.match(r'[A-Z]+_\d+_\d+_\d+[A-Z]?\.swi$', os.path.basename(b))]
            builds_letter = sorted(builds_letter, reverse=True)
            build_i = builds_letter[0] if len(builds_letter) > 0 else builds[0]
            build_sec = builds_letter[1] if len(builds_letter) > 1 else ''
        patch = ''
        if tipo == '8':
            build_base = os.path.basename(build_i).replace('.swi', '')
            branch_num = branch.replace('rel/', '')
            patch_dir = f"/aruba/release/rel_{branch_num}/official/{build_base}/hot-patches/"
            patch_files = sorted(glob.glob(os.path.join(patch_dir, '*.patch')), key=lambda x: os.path.getmtime(x), reverse=True)
            if patch_files:
                patch = patch_files[0]
                print(f"[INFO] Patch seleccionado para branch {branch}: {patch}")
            else:
                print(f"[ADVERTENCIA] No se encontró patch para HOTPATCH en {patch_dir}.")
                patch = ''
        # Mejor extracción de test case
        if hasattr(generar_comando, "test_case"):
            test_case = generar_comando.test_case
        else:
            # Buscar varios patrones, incluyendo se_
            test_case = None
            patrones = [r'ft_[\w_]+', r'test_[\w-]+', r'TC_[\w-]+', r'se_[\w-]+']
            for pat in patrones:
                for campo in ['summary', 'description']:
                    if campo in locals() and locals()[campo]:
                        match = re.search(pat, locals()[campo])
                        if match:
                            test_case = match.group(0)
                            break
                if test_case:
                    break
            if not test_case:
                print(f"[ADVERTENCIA] No se encontró test case en el JIRA para {key}. Usando test_{key}.")
                test_case = f"test_{key}"
        base = f'ht -t {test_case} -i {build_i}'
        if tipo == '2':  # ISSU
            comando = f'{base} -y -h {plataforma}ISSU -r {r_value} -secBuildImage {build_sec} -m CR_{key}#NoKill'
        elif tipo == '3':  # ISSU con -passThru --issu-upgrade-on-ha
            comando = f'{base} -y -h {plataforma}ISSU -r {r_value} -secBuildImage {build_sec} -passThru --issu-upgrade-on-ha -m CR_{key}#NoKill'
        elif tipo == '4':  # ISSU con -passThru --issu-allow-same-version
            comando = f'{base} -y -h {plataforma}ISSU -r {r_value} -passThru --issu-allow-same-version -m CR_{key}#NoKill'
        elif tipo == '5':  # DRY_RUN
            comando = f'{base} -y -h {plataforma} -r {r_value} -passThru --dry-run -m CR_{key}#NoKill'
        elif tipo == '6':  # CONFIG_RESTORE
            comando = f'{base} -y -h {plataforma} -r {r_value} -passThru --config-restore -m CR_{key}#NoKill'
        elif tipo == '7':  # UPGRADE_DOWNGRADE
            comando = f'{base} -y -h {plataforma} -r {r_value} -passThru --upgrade-downgrade -secBuildImage {build_sec} -m CR_{key}#NoKill'
        elif tipo == '8':  # HOTPATCH
            if branch == 'master':
                print("HOTPATCH no se puede generar para el branch master.")
                return ''
            builds = obtener_builds_actualizados(branch)
            builds_letter = [b for b in builds if re.match(r'[A-Z]+_\d+_\d+_\d+[A-Z]?\.swi$', os.path.basename(b))]
            if not builds_letter:
                print("No hay builds Letter disponibles para HOTPATCH.")
                return ''
            build_i = builds_letter[0]
            build_base = os.path.basename(build_i).replace('.swi', '')
            branch_num = branch.replace('rel/', '')
            patch_dir = f"/aruba/release/rel_{branch_num}/official/{build_base}/hot-patches/"
            patch_files = sorted(glob.glob(os.path.join(patch_dir, '*.patch')), key=lambda x: os.path.getmtime(x), reverse=True)
            patch_files = patch_files[:5] if len(patch_files) > 5 else patch_files
            if not patch_files:
                print(f"ERROR: El parámetro -p es obligatorio para HOTPATCH. No se encontró patch en {patch_dir}.")
                return ''
            print(f"\nParches más recientes disponibles para este branch/build:")
            for idx, patch in enumerate(patch_files):
                print(f"  [{idx+1}] {os.path.basename(patch)}")
            opcion = input('Seleccione el número de patch a usar: ').strip()
            try:
                idx = int(opcion) - 1
                if 0 <= idx < len(patch_files):
                    patch_path = patch_files[idx]
                else:
                    patch_path = patch_files[0]
            except Exception:
                patch_path = patch_files[0]
            print(f"Patch seleccionado: {patch_path}")
            comando = f'ht -t {test_case} -y -i {build_i} -passThru --hot-patch-on-setup -h {plataforma} -r {r_value} -m CR_{key}#NoKill -p {patch_path}'
        elif tipo == '9':  # ST_HOTPATCH
            if branch == 'master':
                print("ST_HOTPATCH no se puede generar para el branch master.")
                return ''
            builds = obtener_builds_actualizados(branch)
            builds_letter = [b for b in builds if re.match(r'[A-Z]+_\d+_\d+_\d+[A-Z]?\.swi$', os.path.basename(b))]
            if not builds_letter:
                print("No hay builds Letter disponibles para ST_HOTPATCH.")
                return ''
            build_i = builds_letter[0]
            build_base = os.path.basename(build_i).replace('.swi', '')
            branch_num = branch.replace('rel/', '')
            patch_dir = f"/aruba/release/rel_{branch_num}/official/{build_base}/hot-patches/"
            patch_files = sorted(glob.glob(os.path.join(patch_dir, '*.patch')), key=lambda x: os.path.getmtime(x), reverse=True)
            patch_files = patch_files[:5] if len(patch_files) > 5 else patch_files
            if not patch_files:
                print(f"ERROR: El parámetro -p es obligatorio para ST_HOTPATCH. No se encontró patch en {patch_dir}.")
                return ''
            print(f"\nParches más recientes disponibles para este branch/build:")
            for idx, patch in enumerate(patch_files):
                print(f"  [{idx+1}] {os.path.basename(patch)}")
            opcion = input('Seleccione el número de patch a usar: ').strip()
            try:
                idx = int(opcion) - 1
                if 0 <= idx < len(patch_files):
                    patch_path = patch_files[idx]
                else:
                    patch_path = patch_files[0]
            except Exception:
                patch_path = patch_files[0]
            print(f"Patch seleccionado: {patch_path}")
            comando = f'ht -t {test_case} -y -i {build_i} -h {plataforma} -r {r_value} -m CR_{key}#NoKill -p {patch_path}'
        elif tipo == '10':  # PSM
            comando = f'{base} -y -h {plataforma} -r {r_value} -supportDevFamily 6300F,6300M,6405,6410,6200,6100,6000 -isPSMOvaTest 1'
        else:  # Normal
            comando = f'{base} -y -h {plataforma} -r {r_value} -m CR_{key}#NoKill'
    return comando

def main():

    # Utilidad para mostrar rutas de patch para todos los branches activos
    def mostrar_rutas_patch(build_base):
        branches_activos = [
            'rel/10_18', 'rel/10_17_0001', 'rel/10_17', 'rel/10_16_1020', 'rel/10_16_1010', 'rel/10_16',
            'rel/10_15', 'rel/10_13_1150', 'rel/10_13_1140', 'rel/10_13', 'rel/10_10_1170'
        ]
        print("\nRutas de patch para todos los branches activos:")
        for branch in branches_activos:
            branch_num = branch.replace('rel/', '')
            ruta = f"/aruba/release/rel_{branch_num}/official/{build_base}/hot-patches/"
            print(f"Branch: {branch} -> {ruta}")


    modo = solicitar_modo_generacion()
    # JQL para obtener los issues con status 'Verification in Progress'
    jql = (
        'project in (AOSCX, TAORMINA, AOSANSI) '
        'AND issuetype in ("HW CR", "Infra CR", "SW CR") '
        'AND status = "Verification in Progress" '
        'AND assignee in ('
        '"franz.vargas-acuna@hpe.com", "noel.perez-caceres@hpe.com", "cynthia.taylor@hpe.com", "j.guerrero@hpe.com", '
        '"oldemar.ramirez-rodriguez@hpe.com", "alan.martinez-bolanos@hpe.com", "jesus.diaz-campos@hpe.com", "manual.sanabria@hpe.com", '
        '"jose.ardila@hpe.com", "walter.rojas-cubero@hpe.com", "ruth.campos-artavia@hpe.com", "diego.rodriguez-garnier@hpe.com", '
        '"yermi.arias-alfaro@hpe.com", "carlos.camacho-morales@hpe.com", "william.omodeo-venegas@hpe.com", "alonso.jimenez-mendez@hpe.com", '
        '"marco.romero-diaz@hpe.com", "jotan-jesus.sanchez-mesen@hpe.com", "maureen.elizondo-meja-as@hpe.com", "carlos.rodriguez-machado@hpe.com", '
        '"luis-antonio.solis-garcia@hpe.com", "alvaro.sossa-rojas-ext@hpe.com", "jeisson.gonzalez-ledezma@hpe.com", "manuel.mora@hpe.com"'
        ') '
        'ORDER BY assignee ASC, cf[14200] ASC, resolved ASC, updated DESC'
    )
    fields = [
        'key', 'summary', 'description', 'fixVersions', 'customfield_11500', 'customfield_12002', 'customfield_12804',
        'customfield_14407', 'customfield_14414', 'components', 'customfield_12810', 'priority', 'comment'
    ]
    jira_auth = jira_api.BearerAuth(jira_token)
    jira_url = "https://jira.arubanetworks.com"
    # Obtener todos los issues
    issues_dict = jira_api.find_issues_content(
        jql=jql, fields=fields, auth=jira_auth, base_url=jira_url, max_result_size=50
    )
    jira_keys = list(issues_dict.keys())
    comandos_por_branch = {}
    print(f"\nSe encontraron {len(jira_keys)} JIRA keys con status 'Verification in Progress'.")
    print("\nResumen extraído de los JIRA keys:")
    for key in jira_keys[:5]:
        datos = issues_dict[key]
        tc = None
        if 'summary' in datos and datos['summary']:
            match = re.search(r'ft_[\w_]+', datos['summary'])
            if match:
                tc = match.group(0)
        if not tc and 'description' in datos and datos['description']:
            match = re.search(r'ft_[\w_]+', datos['description'])
            if match:
                tc = match.group(0)
        plataformas = None
        if 'description' in datos and datos['description']:
            match = re.search(r'Affected Platforms:\s*([\w, ]+)', datos['description'])
            if match:
                plataformas = match.group(1)
        fix_version = None
        if 'fixVersions' in datos and datos['fixVersions']:
            fix = datos['fixVersions'][0] if isinstance(datos['fixVersions'], list) else datos['fixVersions']
            if isinstance(fix, dict) and 'name' in fix:
                fix_version = fix['name']
            elif isinstance(fix, str):
                fix_version = fix
        reproducibility = None
        if 'description' in datos and datos['description']:
            match = re.search(r'Reproducibility\s*:\s*([\w\- ]+)', datos['description'], re.IGNORECASE)
            if match:
                reproducibility = match.group(1).strip().lower().replace('-', '').replace('_', '').replace(' ', '')
        print(f"\nJira Key: {key}")
        print(f"TCs: {tc if tc else '-'}")
        print(f"Platform: {plataformas if plataformas else '-'}")
        print(f"Fix Version: {fix_version if fix_version else '-'}")
        print(f"Reproducibility: {reproducibility if reproducibility else '-'}")

    for key in jira_keys:
        if jira_keys.index(key) == 5:
            print('\nSolo se mostrarán mensajes para los primeros 5 JIRA keys.')
        datos = issues_dict[key]
        branch, plataforma = extraer_branch_plataforma(datos)
        print(f"[DEBUG] Procesando branch: {branch}, plataforma: {plataforma}")
        if branch in ["rel/10_17", "rel/10_17_0001"]:
            print("[DEBUG] Forzando plataforma a '4100i' para branch de prueba 10_17/10_17_0001")
            plataforma = "4100i"
        test_case = None
        patrones = [r'ft_[\w_]+', r'se_[\w-]+', r'test_[\w-]+', r'TC_[\w-]+']
        for pat in patrones:
            if 'summary' in datos and datos['summary']:
                match = re.search(pat, datos['summary'])
                if match:
                    test_case = match.group(0)
                    break
            if not test_case and 'description' in datos and datos['description']:
                match = re.search(pat, datos['description'])
                if match:
                    test_case = match.group(0)
                    break
        if not test_case:
            print(f"[ADVERTENCIA] No se encontró test case en el JIRA para {key}. Usando test_{key}.")
            test_case = f"test_{key}"

        generar_comando.test_case = test_case
        reproducibility = None
        if 'description' in datos and datos['description']:
            match = re.search(r'Reproducibility\s*:\s*([\w\- ]+)', datos['description'], re.IGNORECASE)
            if match:
                reproducibility = match.group(1).strip().lower().replace('-', '').replace('_', '').replace(' ', '')
        reproducibility_map = {
            'always': '1',
            'intermittent': '2',
            'once': '3',
        }
        r_value = reproducibility_map.get(reproducibility, '2')
        print(f"[DEBUG reproducibility] JIRA {key}: '{reproducibility}' (mapped to -r {r_value})")
        tipo = solicitar_tipo_comando(key)
        if modo == '1':
            branches_disponibles = [
                'master',
                'rel/10_18',
                'rel/10_17_0001',
                'rel/10_17',
                'rel/10_16_1020',
                'rel/10_16_1010',
                'rel/10_16',
                'rel/10_15',
                'rel/10_13_1150',
                'rel/10_13_1140',
                'rel/10_13',
                'rel/10_10_1170'
            ]
            print("\nSeleccione el branch específico:")
            for idx, b in enumerate(branches_disponibles, 1):
                print(f"  [{idx}] {b}")
            opcion_branch = input('> ').strip()
            try:
                idx = int(opcion_branch) - 1
                branch_elegido = branches_disponibles[idx]
            except Exception:
                branch_elegido = branches_disponibles[0]
            comando = generar_comando(key, tipo, branch_elegido, plataforma, r_value=r_value)
            if comando:
                comandos_por_branch[branch_elegido] = [comando]
        if modo == '3':
            extra_branches = []
            for extra in ["rel/10_17", "rel/10_17_0001"]:
                plataformas_lista = [plataforma] if isinstance(plataforma, str) else plataforma
                found = False
                for plat in plataformas_lista:
                    prefijos = {
                        "10000L": ["NL_", "paws_essw_cit_"], "9300S": ["NL_", "paws_essw_cit_"], "5420": ["BL_", "lightyear_essw_cit_"],
                        "6300L": ["AL_", "aspen_essw_cit_"], "8325H": ["HL_", "carlsbad_essw_cit_"], "vdut": ["genericx86-rosewood_essw_cit_"],
                        "8320": ["TL_", "topflite_essw_cit_"], "8400": ["XL_", "ridley_essw_cit_"], "8325P": ["GL_", "golfclub_essw_cit_"],
                        "8325": ["GL_", "golfclub_essw_cit_"], "6300F": ["FL_", "speedway_essw_cit_"], "6300M": ["FL_", "speedway_essw_cit_"],
                        "6400": ["FL_", "speedway_essw_cit_"], "6200F": ["ML_", "tover_essw_cit_"], "6200M": ["tover_essw_cit_"],
                        "6000": ["PL_", "bristol_essw_cit_"], "6100": ["PL_", "bristol_essw_cit_"], "8100": ["LL_", "lucky_essw_cit_"],
                        "8360": ["LL_", "lucky_essw_cit_"], "4100i": ["RL_", "lemans_essw_cit_"], "10000": ["DL_", "taormina_essw_cit_"],
                        "9300": ["CL_", "carmel_essw_cit_"]
                    }.get(plat, [])
                    branch_clean = extra.replace('rel/', '')
                    for prefijo in prefijos:
                        import glob
                        path = f'/aruba/pub/{prefijo}{branch_clean}*.swi'
                        builds_encontrados = sorted(glob.glob(path), reverse=True)
                        if builds_encontrados:
                            found = True
                            break
                    if found:
                        break
                if found:
                    extra_branches.append(extra)
            if branch != 'master':
                branches_activos = [branch] + extra_branches + ['master']
            else:
                branches_activos = ['master']
            for b in branches_activos:
                comando = generar_comando(key, tipo, b, plataforma, r_value=r_value)
                if comando:
                    if b not in comandos_por_branch:
                        comandos_por_branch[b] = []
                    comandos_por_branch[b].append(f"{key}_{b}: {comando}")
    # Guardar los comandos en un archivo txt en el mismo directorio que el script
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    txt_path = os.path.join(script_dir, 'Comandos_generados_por_tool.txt')
    with open(txt_path, 'w') as f:
        if comandos_por_branch:
            for branch, cmds in comandos_por_branch.items():
                f.write(f"git checkout {branch}\n")
                f.write("git pull\n")
                for cmd in cmds:
                    if ': ' in cmd:
                        f.write(cmd.split(': ', 1)[1] + '\n')
                    else:
                        f.write(cmd + '\n')
        else:
            f.write('No se generó ningún comando. Verifique que existan builds y patches válidos para los branches seleccionados.\n')
    print(f"\n✓ Comandos guardados en {txt_path}")

if __name__ == '__main__':
    main()
