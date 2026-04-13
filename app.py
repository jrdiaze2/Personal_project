#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web Application - Generador de Comandos JIRA
Aplicación web para generar comandos de validación de forma interactiva
"""

from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from datetime import timedelta
import sys
import os
import re

# Disable SSL warnings for faster imports
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Agregar path para importar módulos existentes
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from jira_extractor import JiraExtractor
from command_generator_from_jira import (
    extract_platform_number,
    get_build_prefix,
    find_builds_by_branches,
    get_branches_from_fix_version,
    PLATFORM_MASTER_PREFIX
)
from database import (
    init_db,
    register_user,
    authenticate_user,
    get_all_users,
    log_user_action,
    get_user_stats,
    update_user_workspace,
    save_run_history,
    get_run_history
)
from command_builder import build_command, requires_two_builds, CommandBuildError
from utils import (
    make_response,
    sanitize_flags,
    sanitize_platform_complement,
    sanitize_jira_key,
    encrypt_token,
    decrypt_token
)
from fetch_branches import fetch_branches

# Initialize database on startup
init_db()

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # True en producción con HTTPS
CORS(app)

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    """Autenticación de usuario"""
    data = request.json
    email = data.get('email')
    token = data.get('token')
    
    if not email or not token:
        return make_response(False, error_code='E_PARAMS', message='Email and token are required', status=400)
    
    # Store token directly in session without encryption for now
    # TODO: Implement proper encryption with correct key management
    session.clear()
    session['email'] = email
    session['token'] = token  # Store plain token temporarily
    session.permanent = True

@app.route('/api/branches', methods=['GET'])
def get_branches():
    """Devuelve lista de branches extraídos del dashboard externo"""
    url = request.args.get('url', 'https://prodlabrpt.rose.rdlabs.hpecorp.net/')
    try:
        branches = fetch_branches(url)
        return make_response(True, data={'branches': branches}, message=f'{len(branches)} branches encontrados')
    except Exception as e:
        return make_response(False, error_code='E_BRANCH', message=str(e), status=500)
    session.modified = True
    
    return make_response(True, data={'email': email})

@app.route('/api/set_workspace', methods=['POST'])
def set_workspace():
    """Configurar workspace del usuario"""
    if 'email' not in session or 'token' not in session:
        return make_response(False, error_code='E_SESSION', message='Session expired', status=401)
    
    data = request.json
    username = data.get('username', '').strip()
    
    if not username or not re.match(r'^[a-z0-9_]+$', username):
        return make_response(False, error_code='E_PARAMS', message='Invalid username', status=400)
    
    session['username'] = username
    session['workspace_path'] = f'/ws/{username}/halon/halon-test/tests'
    session.modified = True
    
    return make_response(True, data={'username': username, 'workspace_path': session['workspace_path']})

@app.route('/api/get_jira_keys_by_fix_version', methods=['POST'])
def get_jira_keys_by_fix_version():
    """Obtiene todos los JIRA keys asociados a un Fix Version"""
    if 'token' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    data = request.json
    fix_version = data.get('fix_version', '').strip()
    
    if not fix_version or fix_version == 'N/A':
        return jsonify({'error': 'Fix Version requerido o inválido'}), 400
    
    try:
        extractor = JiraExtractor(token=session['token'])
        
        # Escapar comillas en el Fix Version para JQL
        fix_version_escaped = fix_version.replace('"', '\\"')
        
        # Query JQL para buscar por Fix Version
        jql = f'fixVersion = "{fix_version_escaped}" AND project = AOSCX ORDER BY key ASC'
        
        url = f"{extractor.base_url}/rest/api/2/search"
        params = {
            'jql': jql,
            'fields': 'key,summary,status',
            'maxResults': 100
        }
        
        response = extractor.session.get(url, params=params, verify=False)
        
        if response.status_code != 200:
            return jsonify({'error': f'Error al consultar JIRA: {response.status_code}'}), 400
        
        result = response.json()
        issues = result.get('issues', [])
        
        jira_keys = [{
            'key': issue['key'],
            'summary': issue['fields'].get('summary', 'N/A'),
            'status': issue['fields'].get('status', {}).get('name', 'N/A')
        } for issue in issues]
        
        return jsonify({
            'success': True,
            'jira_keys': jira_keys,
            'total': len(jira_keys)
        })
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/api/get_jira_data', methods=['POST'])
def get_jira_data():
    """Obtener datos de JIRA"""
    if 'token' not in session:
        return make_response(False, error_code='E_AUTH', message='Session expired. Please login again.', status=401)
    
    data = request.json
    jira_key = data.get('jira_key', '')
    
    try:
        jira_key = sanitize_jira_key(jira_key)
    except ValueError as e:
        return make_response(False, error_code='E_PARAMS', message=str(e), status=400)
    
    try:
        # Get token directly from session (no decryption needed)
        token = session.get('token')
        print(f"🔍 DEBUG: Attempting to retrieve JIRA data for {jira_key}")
        print(f"🔐 DEBUG: Token present: {bool(token)}")
        print(f"🔑 DEBUG: Token length: {len(token) if token else 0}")
        
        if not token or len(token) < 10:
            print("⚠️  DEBUG: Token is empty or too short")
            return make_response(False, error_code='E_AUTH', 
                message='Invalid authentication token. Please logout and login again with a valid JIRA API token.', 
                status=401)
        
        extractor = JiraExtractor(token=token)
        issue_data = extractor.get_issue_data(jira_key)
        
        if not issue_data:
            print(f"⚠️  DEBUG: No issue data returned from JIRA for {jira_key}")
            return make_response(False, error_code='E_NOT_FOUND', 
                message=f'Could not retrieve JIRA data for {jira_key}. This could be because: (1) The issue does not exist, (2) Your API token is invalid or expired, (3) You do not have permission to view this issue. Please verify your JIRA API token at https://id.atlassian.com/manage-profile/security/api-tokens', 
                status=404)
        
        jira_data = extractor.parse_issue_data(issue_data)
        platform = jira_data.get('platform', 'N/A')
        platform_num = extract_platform_number(platform)
        
        return make_response(True, data={
            'test_case': jira_data.get('test_case', 'N/A'),
            'platform': platform,
            'platform_num': platform_num,
            'finding_branch': jira_data.get('finding_branch', 'N/A'),
            'fix_versions': jira_data.get('fix_versions', 'N/A'),
            'found_build': jira_data.get('found_build', 'N/A')
        })
    except Exception as e:
        return make_response(False, error_code='E_JIRA', message=str(e), status=500)

@app.route('/api/set_manual_jira_data', methods=['POST'])
def set_manual_jira_data():
    """Guardar datos de JIRA ingresados manualmente"""
    data = request.json
    jira_key = data.get('jira_key')
    test_case = data.get('test_case')
    platform = data.get('platform')
    fix_versions = data.get('fix_versions', 'N/A')
    
    if not all([jira_key, test_case, platform]):
        return jsonify({'error': 'Incomplete data'}), 400
    
    try:
        platform_num = extract_platform_number(platform)
        
        return jsonify({
            'success': True,
            'data': {
                'test_case': test_case,
                'platform': platform,
                'platform_num': platform_num,
                'finding_branch': 'N/A',
                'fix_versions': fix_versions,
                'found_build': 'N/A'
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_builds', methods=['POST'])
def get_builds():
    """Obtener lista de builds disponibles"""
    data = request.json
    platform_num = data.get('platform_num')
    
    if not platform_num:
        return jsonify({'error': 'Platform required'}), 400
    
    try:
        build_prefix = get_build_prefix(platform_num)
        if not build_prefix:
            return jsonify({'error': 'Build prefix not found'}), 404
        
        all_builds = find_builds_by_branches(build_prefix, platform_num)
        
        # Agrupar por branch
        builds_by_branch = {}
        for build_info in all_builds:
            branch = build_info['branch']
            if branch not in builds_by_branch:
                builds_by_branch[branch] = []
            builds_by_branch[branch].append({
                'filename': build_info['filename'],
                'path': build_info['path'],
                'mtime_str': build_info['mtime_str']
            })
        
        return jsonify({
            'success': True,
            'builds': builds_by_branch,
            'prefix': build_prefix
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_latest_builds', methods=['POST'])
def get_latest_builds():
    """Obtener el build más reciente (y segundo si existe) por branch para la plataforma del JIRA"""
    data = request.json
    platform_num = data.get('platform_num')
    if not platform_num:
        return make_response(False, error_code='E_PARAMS', message='Platform required', status=400)
    try:
        build_prefix = get_build_prefix(platform_num)
        if not build_prefix:
            return make_response(False, error_code='E_BUILD', message='Build prefix not found', status=404)
        all_builds = find_builds_by_branches(build_prefix, platform_num)
        # Estructura: branch -> list(sorted newest first, max 2)
        latest_by_branch = {}
        for build_info in all_builds:
            branch = build_info['branch']
            if branch not in latest_by_branch:
                latest_by_branch[branch] = []
            # Limitar a máximo 2 builds por branch
            if len(latest_by_branch[branch]) < 2:
                latest_by_branch[branch].append({
                    'filename': build_info['filename'],
                    'path': build_info['path'],
                    'mtime_str': build_info['mtime_str']
                })
        
        # Cache in session
        session['cached_builds'] = latest_by_branch
        session.modified = True
        
        return make_response(True, data={'branches': latest_by_branch})
    except Exception as e:
        return make_response(False, error_code='E_BUILD', message=str(e), status=500)

@app.route('/api/generate_branch_commands', methods=['POST'])
def generate_branch_commands():
    """Genera un comando por branch usando el/los builds más recientes según tipo"""
    data = request.json
    jira_key = data.get('jira_key')
    test_case = data.get('test_case')
    platform = data.get('platform')
    platform_num = data.get('platform_num')
    command_type = data.get('command_type')
    branches_builds = data.get('branches_builds', {})  # branch -> list of builds (newest first)
    platform_complement = data.get('platform_complement', '')
    additional_flags = data.get('additional_flags', '').strip()
    branch_10_17_override = data.get('branch_10_17_override', '').strip()
    
    # Sanitize inputs
    try:
        jira_key = sanitize_jira_key(jira_key)
        if platform_complement:
            platform_complement = sanitize_platform_complement(platform_complement)
        if additional_flags:
            additional_flags = sanitize_flags(additional_flags)
    except ValueError as e:
        return make_response(False, error_code='E_PARAMS', message=str(e), status=400)
    
    if not all([jira_key, test_case, platform, platform_num, command_type]) or not branches_builds:
        return make_response(False, error_code='E_PARAMS', message='Incomplete parameters', status=400)
    results = []
    platform_param = f"{platform_num}{platform_complement}" if platform_complement else platform_num

    for branch, builds in branches_builds.items():
        if not builds:
            continue
        need_two = requires_two_builds(command_type)
        if need_two and len(builds) < 2:
            results.append({'branch': branch, 'error': f'Requiere 2 builds, solo hay {len(builds)} disponible(s).', 'command': None})
            continue
        primary = builds[0]['path']
        secondary = builds[1]['path'] if len(builds) > 1 else None

        if branch == '10_17' and branch_10_17_override:
            try:
                override_candidate = next((b['path'] for b in builds if b['filename'].startswith(branch_10_17_override)), None)
                if override_candidate:
                    primary = override_candidate
                elif os.path.isfile(branch_10_17_override):
                    primary = branch_10_17_override
            except Exception:
                pass
        try:
            raw_cmd = build_command(
                command_type=command_type,
                test_case=test_case,
                primary_build=primary,
                secondary_build=secondary,
                platform=platform_num,
                platform_complement=platform_complement,
                jira_key=jira_key,
                additional_flags=additional_flags
            )
            # Do NOT prefix with 'cd <workspace> &&' for user-visible command; execution endpoints handle cwd.
            results.append({'branch': branch, 'command': raw_cmd, 'primary': primary, 'secondary': secondary})
        except CommandBuildError as e:
            results.append({'branch': branch, 'error': str(e), 'command': None})
    return make_response(True, data={'commands': results})

@app.route('/api/export_commands', methods=['POST'])
def export_commands():
    """Exportar comandos a archivo de texto"""
    data = request.json
    commands = data.get('commands', [])
    
    if not commands:
        return make_response(False, error_code='E_PARAMS', message='No commands to export', status=400)
    
    try:
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Group commands by JIRA key
        commands_by_jira = {}
        for cmd in commands:
            jira_key = cmd.get('jira_key', 'Unknown')
            if jira_key not in commands_by_jira:
                commands_by_jira[jira_key] = []
            commands_by_jira[jira_key].append(cmd)
        
        # Build export content
        lines = []
        lines.append(f"# Comandos generados - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"# Total comandos: {len(commands)}")
        lines.append("#" + "="*70)
        lines.append("")
        
        for jira_key, jira_cmds in commands_by_jira.items():
            lines.append(f"# JIRA Key: {jira_key}")
            lines.append("#" + "-"*70)
            
            for cmd_info in jira_cmds:
                if cmd_info.get('error'):
                    lines.append(f"# ERROR en branch {cmd_info.get('branch', 'N/A')}: {cmd_info['error']}")
                    continue
                    
                branch = cmd_info.get('branch', 'N/A')
                command = cmd_info.get('command', '')
                
                lines.append(f"# Branch: {branch}")
                lines.append(command)
                lines.append("")
            
            lines.append("")
        
        export_text = "\n".join(lines)
        
        return make_response(True, data={
            'content': export_text,
            'filename': f'comandos_{timestamp}.txt'
        })
    
    except Exception as e:
        return make_response(False, error_code='E_INTERNAL', message=str(e), status=500)

# LEGACY ENDPOINT (DEPRECATED) retained for backward compatibility; will be removed.
@app.route('/api/generate_command', methods=['POST'])
def generate_command():
    return jsonify({'error': 'Endpoint deprecated. Use /api/generate_branch_commands or /api/generate_multiple_commands.'}), 410

@app.route('/api/generate_multiple_commands', methods=['POST'])
def generate_multiple_commands():
    """Genera comandos para múltiples JIRA keys"""
    if 'token' not in session or 'workspace_path' not in session:
        return make_response(False, error_code='E_AUTH', status=401)
    
    data = request.json
    jira_keys = data.get('jira_keys', [])
    command_type = data.get('command_type')
    platform = data.get('platform')
    build1 = data.get('build1')
    build2 = data.get('build2', '')
    
    if not jira_keys or not command_type or not platform:
        return make_response(False, error_code='E_PARAMS', message='Incomplete parameters', status=400)
    
    try:
        token = session.get('token')  # Get token directly from session
        extractor = JiraExtractor(token=token)
        workspace_path = session['workspace_path']
        commands = []
        
        for jira_key in jira_keys:
            try:
                jira_key = sanitize_jira_key(jira_key)
            except ValueError as e:
                commands.append({'jira_key': jira_key, 'error': str(e), 'command': None})
                continue
            
            issue_data = extractor.get_issue_data(jira_key)
            if not issue_data:
                commands.append({'jira_key': jira_key, 'error': 'No se pudo obtener datos del issue', 'command': None})
                continue
            parsed_data = extractor.parse_issue_data(issue_data)
            test_case = parsed_data.get('test_case', 'N/A')
            if test_case == 'N/A':
                commands.append({'jira_key': jira_key, 'summary': parsed_data.get('summary', 'N/A'), 'error': 'No se encontró Test Case', 'command': None})
                continue
            try:
                raw_cmd = build_command(
                    command_type=command_type,
                    test_case=test_case,
                    primary_build=build1,
                    secondary_build=build2 or None,
                    platform=platform,
                    platform_complement="",
                    jira_key=jira_key,
                    additional_flags=""
                )
                command = f"cd {workspace_path} && {raw_cmd}" if not raw_cmd.startswith("cd ") else raw_cmd
                commands.append({'jira_key': jira_key,'summary': parsed_data.get('summary', 'N/A'),'test_case': test_case,'command': command,'error': None})
            except CommandBuildError as e:
                commands.append({'jira_key': jira_key, 'summary': parsed_data.get('summary', 'N/A'), 'error': str(e), 'command': None})
        return make_response(True, data={'commands': commands, 'total': len(commands)})
    except Exception as e:
        return make_response(False, error_code='E_INTERNAL', message=str(e), status=500)

@app.route('/api/execute_commands', methods=['POST'])
@app.route('/api/generate_single_command', methods=['POST'])
def generate_single_command():
    """Genera comando para un solo JIRA key"""
    if 'workspace_path' not in session:
        return make_response(False, error_code='E_SESSION', message='Working directory not configured', status=400)
    
    data = request.json
    jira_key = data.get('jira_key', '')
    command_type = data.get('command_type')
    platform = data.get('platform')
    test_case = data.get('test_case')
    build1 = data.get('build1')
    build2 = data.get('build2', '')
    
    try:
        jira_key = sanitize_jira_key(jira_key)
    except ValueError as e:
        return make_response(False, error_code='E_PARAMS', message=str(e), status=400)
    
    if not all([jira_key, command_type, platform, test_case, build1]):
        return make_response(False, error_code='E_PARAMS', message='Incomplete parameters', status=400)
    
    workspace_path = session['workspace_path']
    
    try:
        raw_cmd = build_command(
            command_type=command_type,
            test_case=test_case,
            primary_build=build1,
            secondary_build=build2 or None,
            platform=platform,
            platform_complement="",
            jira_key=jira_key,
            additional_flags=""
        )
        command = f"cd {workspace_path} && {raw_cmd}" if not raw_cmd.startswith("cd ") else raw_cmd
        return make_response(True, data={'command': command})
    except CommandBuildError as e:
        return make_response(False, error_code='E_COMMAND', message=str(e), status=400)
    except Exception as e:
        return make_response(False, error_code='E_INTERNAL', message=str(e), status=500)

@app.route('/api/execute_command', methods=['POST'])
def execute_command():
    """Ejecuta comando con checkout de branch correspondiente en /ws/username/halon/halon-test/tests/"""
    data = request.json
    command = data.get('command')
    jira_key = data.get('jira_key')
    branch_name = data.get('branch', '')  # Branch del build (ej: 10_17 o 10_17_0001)
    workspace_path = session.get('workspace_path', '/ws/diazcamp/halon/halon-test/tests')
    
    if not command:
        return make_response(False, error_code='E_PARAMS', message='Command required', status=400)
    
    import subprocess
    import re
    
    try:
        print(f"\n{'='*70}")
        print(f"🚀 Executing command for JIRA: {jira_key}")
        print(f"📂 Workspace: {workspace_path}")
        print(f"🔧 Branch provided: {branch_name}")
        print(f"💻 Command: {command[:100]}...")
        print(f"{'='*70}\n")
        
        # Extraer branch del comando si no se pasó explícitamente
        if not branch_name:
            # Buscar patrón de build en el comando (ej: /10_17_0001/ o /10_17/)
            build_match = re.search(r'/(\d+_\d+(?:_\d+)?)', command)
            if build_match:
                branch_name = build_match.group(1)
                print(f"🔍 Branch extracted from command: {branch_name}")
        
        # Convertir nombre de build a branch git
        # Ejemplos: 10_17_0001 -> rel/10_17, 10_17 -> rel/10_17, master -> master
        git_branch = None
        if branch_name:
            if branch_name == 'master':
                git_branch = 'master'
            else:
                # Extraer solo los primeros dos números (10_17_0001 -> 10_17)
                branch_parts = branch_name.split('_')
                if len(branch_parts) >= 2:
                    git_branch = f"rel/{branch_parts[0]}_{branch_parts[1]}"
                    print(f"✓ Git branch determined: {git_branch}")
        
        execution_log = []
        
        # Si tenemos branch, hacer checkout y pull
        if git_branch:
            execution_log.append(f"🔄 Changing to branch: {git_branch}")
            print(f"🔄 Executing: git checkout {git_branch}")
            
            # Git checkout
            checkout_result = subprocess.run(
                ['git', 'checkout', git_branch],
                capture_output=True,
                text=True,
                cwd=workspace_path,
                timeout=60
            )
            
            if checkout_result.returncode != 0:
                error_msg = f'Git checkout failed: {checkout_result.stderr}'
                print(f"❌ {error_msg}")
                return make_response(False, error_code='E_EXEC', message=error_msg, status=500)
            
            execution_log.append(f"✓ Branch changed to {git_branch}")
            print(f"✓ Branch changed successfully")
            
            # Git pull
            execution_log.append("🔄 Executing git pull...")
            print(f"🔄 Executing: git pull")
            pull_result = subprocess.run(
                ['git', 'pull'],
                capture_output=True,
                text=True,
                cwd=workspace_path,
                timeout=120
            )
            
            if pull_result.returncode != 0:
                warning = f"⚠ Warning on git pull: {pull_result.stderr}"
                execution_log.append(warning)
                print(warning)
            else:
                execution_log.append("✓ Git pull completed")
                print("✓ Git pull completed")
        else:
            print("⚠ No branch detected, executing in current branch")
            execution_log.append("⚠ No branch detected, executing in current branch")
        
        # Ejecutar comando
        execution_log.append("🚀 Executing command...")
        print(f"🚀 Executing command...")
        print(f"⏱️  Timeout: 30 minutes")
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            timeout=1800  # 30 minutos timeout para esperar RunID
        )
        
        stdout = result.stdout if result.stdout else ''
        stderr = result.stderr if result.stderr else ''
        combined_output = stdout + '\n' + stderr
        
        # Extraer RunID del output usando los mismos patrones que run_comandos_ejecutar.py
        run_id = None
        run_id_url = None
        
        # Patrón 1: URL completa (más confiable)
        url_pattern = re.compile(r'https?://prodlabrpt\.rose\.rdlabs\.hpecorp\.net/\?runID=U[0-9A-Za-z_-]+')
        url_match = url_pattern.search(combined_output)
        if url_match:
            run_id_url = url_match.group(0)
            # Extraer solo el ID de la URL
            run_id = run_id_url.split('runID=')[1]
            execution_log.append(f"✓ RunID URL detectado: {run_id_url}")
        
        # Patrón 2: runID=UXXXX (formato key=value)
        if not run_id:
            keyval_pattern = re.compile(r'runID=U[0-9A-Za-z_-]+')
            keyval_match = keyval_pattern.search(combined_output)
            if keyval_match:
                run_id = keyval_match.group(0).split('=')[1]
                run_id_url = f"http://prodlabrpt.rose.rdlabs.hpecorp.net/?runID={run_id}"
                execution_log.append(f"✓ RunID detectado (key=value): {run_id}")
        
        # Patrón 3: Identificador solo UXXXX (al menos 6 caracteres)
        if not run_id:
            simple_pattern = re.compile(r'\bU[0-9A-Za-z]{6,}\b')
            simple_match = simple_pattern.search(combined_output)
            if simple_match:
                run_id = simple_match.group(0)
                run_id_url = f"http://prodlabrpt.rose.rdlabs.hpecorp.net/?runID={run_id}"
                execution_log.append(f"✓ RunID inferido: {run_id}")
        
        # Generar mensaje para copiar al JIRA
        jira_message = None
        if run_id:
            jira_message = f"Test executed with RunID: {run_id}\nURL: {run_id_url}\nBranch: {git_branch if git_branch else 'N/A'}"
        else:
            execution_log.append("⚠ RunID no detectado en el output")
        
        # Log execution
        user_email = session.get("email")
        if user_email:
            log_user_action(user_email, "execute_command", jira_key, branch=git_branch)
            # Save run history
            save_run_history(
                user_email=user_email,
                jira_key=jira_key,
                branch=git_branch,
                command=command[:500],  # Truncate long commands
                run_id=run_id,
                status='success' if result.returncode == 0 and run_id else 'failed',
                exit_code=result.returncode
            )
        
        return jsonify({
            'success': True,
            'result': {
                'jira_key': jira_key,
                'branch': git_branch,
                'status': 'success' if result.returncode == 0 else 'failed',
                'returncode': result.returncode,
                'stdout': stdout[-3000:] if stdout else '',
                'stderr': stderr[-1000:] if stderr else '',
                'run_id': run_id,
                'run_id_url': run_id_url,
                'jira_message': jira_message,
                'execution_log': '\n'.join(execution_log),
                'message': f'Command executed (exit code: {result.returncode})'
            }
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': True,
            'result': {
                'jira_key': jira_key,
                'status': 'timeout',
                'message': 'Comando excedió el tiempo límite de 30 minutos esperando RunID'
            }
        })
    except Exception as e:
        return jsonify({
            'success': True,
            'result': {
                'jira_key': jira_key,
                'status': 'error',
                'message': f'Error al ejecutar: {str(e)}'
            }
        })

@app.route('/api/get_run_history', methods=['GET'])
def api_get_run_history():
    """Obtener historial de ejecuciones"""
    if 'email' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    user_email = session.get('email')
    limit = request.args.get('limit', 50, type=int)
    
    try:
        history = get_run_history(user_email=user_email, limit=limit)
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/submit_manual_runid', methods=['POST'])
def submit_manual_runid():
    """Guardar RunID ingresado manualmente"""
    if 'email' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    data = request.json
    jira_key = data.get('jira_key')
    branch = data.get('branch')
    run_id = data.get('run_id')
    command = data.get('command', 'N/A')
    
    if not all([jira_key, run_id]):
        return jsonify({'error': 'JIRA key y RunID requeridos'}), 400
    
    try:
        user_email = session.get('email')
        save_run_history(
            user_email=user_email,
            jira_key=jira_key,
            branch=branch,
            command=command[:500],
            run_id=run_id,
            status='manual',
            exit_code=None
        )
        return jsonify({'success': True, 'message': 'RunID guardado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/open_putty', methods=['POST'])
def open_putty():
    """Abre PuTTY en el sistema"""
    if 'email' not in session:
        return make_response(False, error_code='E_AUTH', message='Not authenticated', status=401)
    
    try:
        import subprocess
        import platform
        
        print(f"\n{'='*70}")
        print(f"🖥️  Opening PuTTY")
        print(f"{'='*70}\n")
        
        # Detect operating system
        system = platform.system()
        
        if system == 'Windows':
            # Try to open PuTTY on Windows - try multiple locations
            putty_paths = [
                'C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\PuTTY (64-bit)\\PuTTY.exe',
                'C:\\Program Files\\PuTTY\\putty.exe',
                'C:\\Program Files (x86)\\PuTTY\\putty.exe',
                'putty.exe'  # Try PATH as last resort
            ]
            
            for putty_path in putty_paths:
                try:
                    if os.path.exists(putty_path) or putty_path == 'putty.exe':
                        subprocess.Popen([putty_path], shell=True)
                        print(f"✓ PuTTY launched from: {putty_path}")
                        return make_response(True, message='PuTTY opened successfully')
                except (FileNotFoundError, OSError):
                    continue
            
            # If none worked
            print("❌ PuTTY not found in any standard location")
            return make_response(False, error_code='E_NOTFOUND', 
                               message='PuTTY not found. Please install PuTTY or verify installation path.', 
                               status=404)
        
        elif system == 'Linux':
            # Try to open terminal on Linux (could be xterm, gnome-terminal, etc.)
            terminals = ['putty', 'gnome-terminal', 'xterm', 'konsole', 'terminator']
            for term in terminals:
                try:
                    subprocess.Popen([term])
                    print(f"✓ Terminal launched: {term}")
                    return make_response(True, message=f'{term} opened successfully')
                except FileNotFoundError:
                    continue
            
            print("⚠ No terminal emulator found")
            return make_response(False, error_code='E_NOTFOUND', 
                               message='No terminal emulator found. Please install putty or a terminal emulator.', 
                               status=404)
        
        elif system == 'Darwin':  # macOS
            # Open Terminal on macOS
            subprocess.Popen(['open', '-a', 'Terminal'])
            print("✓ Terminal launched on macOS")
            return make_response(True, message='Terminal opened successfully')
        
        else:
            print(f"⚠ Unsupported OS: {system}")
            return make_response(False, error_code='E_UNSUPPORTED', 
                               message=f'Unsupported operating system: {system}', 
                               status=400)
    
    except Exception as e:
        error_msg = f'Error opening PuTTY: {str(e)}'
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return make_response(False, error_code='E_EXEC', message=error_msg, status=500)


def _extract_runid(output: str):
    """Extract RunID from command output using multiple patterns."""
    import re
    run_id = None
    run_id_url = None
    # Pattern 1: full URL
    m = re.search(r'https?://prodlabrpt\.rose\.rdlabs\.hpecorp\.net/\?runID=(U[0-9A-Za-z_-]+)', output)
    if m:
        run_id = m.group(1)
        run_id_url = f"http://prodlabrpt.rose.rdlabs.hpecorp.net/?runID={run_id}"
        return run_id, run_id_url
    # Pattern 2: key=value
    m = re.search(r'runID\s*=\s*(U[0-9A-Za-z_-]+)', output)
    if m:
        run_id = m.group(1)
        run_id_url = f"http://prodlabrpt.rose.rdlabs.hpecorp.net/?runID={run_id}"
        return run_id, run_id_url
    # Pattern 3: simple Uxxxxx
    m = re.search(r'\b(U[0-9A-Za-z]{6,})\b', output)
    if m:
        run_id = m.group(1)
        run_id_url = f"http://prodlabrpt.rose.rdlabs.hpecorp.net/?runID={run_id}"
    return run_id, run_id_url


@app.route('/api/execute_batch', methods=['POST'])
def execute_batch():
    """Execute multiple commands grouped by branch (emulates extract_and_format_commands.py)."""
    if 'email' not in session:
        return make_response(False, error_code='E_AUTH', message='Not authenticated', status=401)

    data = request.json or {}
    commands = data.get('commands')  # Expect list of {branch, command, jira_key}
    workspace_path = session.get('workspace_path', '/ws/diazcamp/halon/halon-test/tests')

    if not commands or not isinstance(commands, list):
        return make_response(False, error_code='E_PARAMS', message='commands list required', status=400)

    # Group by branch
    branches = {}
    for item in commands:
        branch = item.get('branch') or 'unknown'
        cmd = item.get('command')
        jira_key = item.get('jira_key')
        if not cmd:
            continue
        branches.setdefault(branch, []).append({'command': cmd, 'jira_key': jira_key})

    import subprocess, re, time
    execution_summary = {
        'workspace': workspace_path,
        'total_branches': len(branches),
        'total_commands': sum(len(v) for v in branches.values())
    }
    per_branch_results = {}
    jira_keys_detected = set()
    runids_by_branch = {}
    log_lines = []

    # Order branches: master first
    ordered = [b for b in branches.keys() if b == 'master'] + [b for b in branches.keys() if b != 'master']

    for branch in ordered:
        cmds = branches[branch]
        branch_result = {
            'branch': branch,
            'commands': [],
            'git_checkout': None,
            'git_pull': None,
            'run_ids': []
        }
        log_lines.append(f"===== BRANCH {branch} =====")

        # Git checkout/pull once
        git_branch = 'master' if branch == 'master' else f"rel/{branch}" if not branch.startswith('rel/') else branch
        try:
            checkout_proc = subprocess.run(['git', 'checkout', git_branch], capture_output=True, text=True, cwd=workspace_path, timeout=90)
            branch_result['git_checkout'] = {'branch': git_branch, 'returncode': checkout_proc.returncode, 'stdout': checkout_proc.stdout[-1000:], 'stderr': checkout_proc.stderr[-500:]}
        except subprocess.TimeoutExpired:
            branch_result['git_checkout'] = {'branch': git_branch, 'timeout': True}
        try:
            pull_proc = subprocess.run(['git', 'pull'], capture_output=True, text=True, cwd=workspace_path, timeout=180)
            branch_result['git_pull'] = {'returncode': pull_proc.returncode, 'stdout': pull_proc.stdout[-1000:], 'stderr': pull_proc.stderr[-500:]}
        except subprocess.TimeoutExpired:
            branch_result['git_pull'] = {'timeout': True}

        # Execute each command
        for idx, entry in enumerate(cmds, 1):
            cmd = entry['command']
            jira_key = entry.get('jira_key')
            if jira_key:
                jira_keys_detected.add(jira_key)
            cmd_record = {
                'index': idx,
                'command': cmd,
                'jira_key': jira_key,
                'returncode': None,
                'run_id': None,
                'run_id_url': None,
                'stdout': None,
                'stderr': None
            }
            try:
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=workspace_path, timeout=1800)
                cmd_record['returncode'] = proc.returncode
                cmd_record['stdout'] = proc.stdout[-2000:]
                cmd_record['stderr'] = proc.stderr[-1000:]
                run_id, run_id_url = _extract_runid(proc.stdout + proc.stderr)
                cmd_record['run_id'] = run_id
                cmd_record['run_id_url'] = run_id_url
                if run_id:
                    branch_result['run_ids'].append(run_id_url)
                    runids_by_branch.setdefault(branch, []).append(run_id_url)
                # Persist history
                try:
                    save_run_history(
                        user_email=session.get('email'),
                        jira_key=jira_key or 'UNKNOWN',
                        branch=branch,
                        command=cmd[:500],
                        run_id=run_id or 'N/A',
                        status='success' if proc.returncode == 0 else 'failed',
                        exit_code=proc.returncode
                    )
                except Exception as db_err:
                    print(f"DB save warning: {db_err}")
            except subprocess.TimeoutExpired:
                cmd_record['timeout'] = True
                cmd_record['stderr'] = 'Timeout (30m)'
            branch_result['commands'].append(cmd_record)
        per_branch_results[branch] = branch_result

    # Build JIRA message similar to script
    jira_message = None
    if runids_by_branch:
        lines = ["Waiting for Results:"]
        for branch in ordered:
            if branch in runids_by_branch:
                lines.append(f"\nBranch: {branch}")
                for rid in runids_by_branch[branch]:
                    lines.append(rid)
        jira_message = "\n".join(lines)

    response_data = {
        'summary': execution_summary,
        'branches': per_branch_results,
        'jira_keys_detected': sorted(jira_keys_detected),
        'jira_message': jira_message
    }
    return make_response(True, data=response_data, message='Batch execution completed')


@app.route('/healthz')
def healthz():
    return jsonify({'status': 'ok'}), 200

@app.route('/api/check_session', methods=['GET'])
def check_session():
    """Verifica si la sesión de usuario está activa."""
    active = 'email' in session and 'token' in session
    return jsonify({'active': active, 'email': session.get('email') if active else None})

if __name__ == '__main__':
    debug_mode = os.environ.get('APP_DEBUG', '0') == '1'
    # Prefer CLI arg then ENV PORT else fallback 5001
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--port', type=int, default=None)
    args, _unknown = parser.parse_known_args()
    port_env = os.environ.get('PORT')
    port = args.port or (int(port_env) if port_env and port_env.isdigit() else 5001)
    print(f"✓ Starting Flask server (debug={debug_mode}) on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=debug_mode, threaded=True)
