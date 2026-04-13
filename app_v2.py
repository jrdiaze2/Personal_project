#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web Application V2 - Generador de Comandos JIRA
Versión mejorada con todas las funcionalidades integradas
"""

from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from datetime import timedelta
import sys
import os
import re
import traceback

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Agregar path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from command_service import CommandService
from database import (
    init_db,
    register_user,
    authenticate_user,
    log_user_action,
    save_run_history,
    get_run_history
)
from utils import make_response, sanitize_jira_key
from command_generator_from_jira import get_branches_from_fix_version

# Initialize database
init_db()

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
CORS(app)

# ============================================================================
# ROUTES - Authentication
# ============================================================================

@app.route('/')
def index():
    """Página principal"""
    return render_template('index_v2.html')

@app.route('/api/login', methods=['POST'])
def login():
    """Autenticación de usuario"""
    data = request.json
    email = data.get('email', '').strip()
    token = data.get('token', '').strip()
    
    if not email or not token:
        return make_response(False, error_code='E_PARAMS', 
                           message='Email y token requeridos', status=400)
    
    # Validar token haciendo una request simple
    try:
        service = CommandService(token)
        # Test JIRA connection
        test_data = service.extractor.session.get(
            f"{service.extractor.base_url}/rest/api/2/myself",
            verify=False
        )
        if test_data.status_code != 200:
            return make_response(False, error_code='E_AUTH',
                               message='Token inválido o expirado', status=401)
    except Exception as e:
        return make_response(False, error_code='E_AUTH',
                           message=f'Error validando token: {str(e)}', status=401)
    
    # Guardar en sesión
    session.clear()
    session['email'] = email
    session['token'] = token
    session.permanent = True
    
    # Registrar usuario si no existe
    try:
        register_user(email, email.split('@')[0])
        log_user_action(email, 'login', {'ip': request.remote_addr})
    except:
        pass
    
    return make_response(True, data={'email': email}, 
                        message='Login exitoso')

@app.route('/api/logout', methods=['POST'])
def logout():
    """Cerrar sesión"""
    email = session.get('email')
    if email:
        log_user_action(email, 'logout', {})
    session.clear()
    return make_response(True, message='Sesión cerrada')

@app.route('/api/session', methods=['GET'])
def check_session():
    """Verificar sesión activa"""
    if 'email' not in session or 'token' not in session:
        return make_response(False, error_code='E_SESSION', 
                           message='Sesión expirada', status=401)
    return make_response(True, data={'email': session['email']})

# ============================================================================
# ROUTES - JIRA Data
# ============================================================================

@app.route('/api/jira/data', methods=['POST'])
def get_jira_data():
    """Obtener datos completos de un JIRA key"""
    if 'token' not in session:
        return make_response(False, error_code='E_SESSION', 
                           message='Sesión expirada', status=401)
    
    data = request.json
    jira_key = data.get('jira_key', '').strip().upper()
    
    # Validar formato
    try:
        jira_key = sanitize_jira_key(jira_key)
    except ValueError as e:
        return make_response(False, error_code='E_PARAMS', 
                           message=str(e), status=400)
    
    try:
        service = CommandService(session['token'])
        jira_data = service.get_jira_data(jira_key)
        
        if not jira_data:
            return make_response(False, error_code='E_NOT_FOUND',
                               message=f'JIRA {jira_key} no encontrado', status=404)
        
        # Log action
        log_user_action(session['email'], 'get_jira_data', 
                       {'jira_key': jira_key})
        
        return make_response(True, data=jira_data, 
                           message=f'Datos de {jira_key} obtenidos')
        
    except Exception as e:
        return make_response(False, error_code='E_JIRA',
                           message=f'Error obteniendo datos: {str(e)}', status=500)

# ============================================================================
# ROUTES - Builds
# ============================================================================

@app.route('/api/builds/search', methods=['POST'])
def search_builds():
    """Buscar builds disponibles"""
    if 'token' not in session:
        return make_response(False, error_code='E_SESSION', 
                           message='Sesión expirada', status=401)
    
    data = request.json
    platform_num = data.get('platform_num')
    branches = data.get('branches')  # opcional
    
    if not platform_num:
        return make_response(False, error_code='E_PARAMS',
                           message='platform_num requerido', status=400)
    
    try:
        service = CommandService(session['token'])
        branches_dict = service.find_available_builds(platform_num, branches)
        
        # Convertir a formato serializable
        result = {}
        for branch, builds in branches_dict.items():
            result[branch] = [{
                'path': b['path'],
                'filename': os.path.basename(b['path']),
                'mtime_str': b['mtime_str'],
                'branch': b['branch']
            } for b in builds]
        
        return make_response(True, data={'branches': result},
                           message=f'{len(result)} branches encontrados')
        
    except Exception as e:
        return make_response(False, error_code='E_BUILD',
                           message=f'Error buscando builds: {str(e)}', status=500)

@app.route('/api/builds/from_fix_version', methods=['POST'])
def builds_from_fix_version():
    """Obtener branches y builds desde Fix Version"""
    if 'token' not in session:
        return make_response(False, error_code='E_SESSION',
                           message='Sesión expirada', status=401)
    
    data = request.json
    fix_version = data.get('fix_version', '').strip()
    finding_branch = data.get('finding_branch', '').strip()
    platform_num = data.get('platform_num')
    
    if not fix_version or not platform_num:
        return make_response(False, error_code='E_PARAMS',
                           message='fix_version y platform_num requeridos', status=400)
    
    try:
        # Obtener branches desde Fix Version
        branches = get_branches_from_fix_version(fix_version, finding_branch)
        
        if not branches:
            return make_response(False, error_code='E_BRANCH',
                               message=f'No se pudo mapear Fix Version: {fix_version}', 
                               status=400)
        
        # Buscar builds para esos branches
        service = CommandService(session['token'])
        branches_dict = service.find_available_builds(platform_num, branches)
        
        # Convertir a formato serializable
        result = {}
        for branch, builds in branches_dict.items():
            result[branch] = [{
                'path': b['path'],
                'filename': os.path.basename(b['path']),
                'mtime_str': b['mtime_str'],
                'branch': b['branch']
            } for b in builds]
        
        return make_response(True, data={
            'branches': result,
            'branch_list': branches
        }, message=f'{len(result)} branches desde {fix_version}')
        
    except Exception as e:
        return make_response(False, error_code='E_BUILD',
                           message=f'Error: {str(e)}', status=500)

# ============================================================================
# ROUTES - Patches
# ============================================================================

@app.route('/api/patches/search', methods=['POST'])
def search_patches():
    """Buscar patches para un build"""
    if 'token' not in session:
        return make_response(False, error_code='E_SESSION',
                           message='Sesión expirada', status=401)
    
    data = request.json
    build_path = data.get('build_path', '').strip()
    
    if not build_path:
        return make_response(False, error_code='E_PARAMS',
                           message='build_path requerido', status=400)
    
    try:
        service = CommandService(session['token'])
        patches = service.find_patches_for_build(build_path)
        
        return make_response(True, data={'patches': patches},
                           message=f'{len(patches)} patches encontrados')
        
    except Exception as e:
        return make_response(False, error_code='E_PATCH',
                           message=f'Error buscando patches: {str(e)}', status=500)

# ============================================================================
# ROUTES - Command Generation
# ============================================================================

@app.route('/api/generate/single', methods=['POST'])
def generate_single_command():
    """Generar un comando individual (Modo 1)"""
    if 'token' not in session:
        return make_response(False, error_code='E_SESSION',
                           message='Sesión expirada', status=401)
    
    data = request.json
    jira_key = data.get('jira_key', '').strip().upper()
    command_type = data.get('command_type', '1')
    platform_param = data.get('platform_param', '').strip()
    retries = data.get('retries', 3)
    builds = data.get('builds', [])  # [path1, path2]
    patch_path = data.get('patch_path')
    additional_flags = (data.get('additional_flags') or '').strip()
    
    # Validaciones
    if not jira_key or not command_type or not platform_param or not builds:
        return make_response(False, error_code='E_PARAMS',
                           message='Parámetros incompletos', status=400)
    
    try:
        service = CommandService(session['token'])
        
        # Obtener datos de JIRA
        jira_data = service.get_jira_data(jira_key)
        if not jira_data:
            return make_response(False, error_code='E_NOT_FOUND',
                               message=f'JIRA {jira_key} no encontrado', status=404)
        
        # Convertir builds de paths a formato esperado
        builds_list = []
        for build_path in builds:
            builds_list.append({
                'path': build_path,
                'branch': '',  # No importa para single command
                'mtime_str': ''
            })
        
        # Generar comando
        result = service.generate_command(
            jira_data, jira_key, command_type, platform_param,
            retries, builds_list, patch_path, additional_flags
        )
        
        # Guardar en historial
        save_run_history(
            session['email'],
            jira_key,
            None,  # branch
            result['command'],
            None,  # run_id
            'generated',
            None  # exit_code
        )
        
        # Log action
        log_user_action(session['email'], 'generate_command', {
            'jira_key': jira_key,
            'type': result['type']
        })
        
        return make_response(True, data=result,
                           message='Comando generado exitosamente')
        
    except ValueError as e:
        return make_response(False, error_code='E_VALIDATION',
                           message=str(e), status=400)
    except Exception as e:
        traceback.print_exc()
        return make_response(False, error_code='E_GENERATE',
                           message=f'Error generando comando: {str(e)}', status=500)

@app.route('/api/generate/multiple', methods=['POST'])
def generate_multiple_commands():
    """Generar comandos para múltiples branches (Modo 2/3)"""
    if 'token' not in session:
        return make_response(False, error_code='E_SESSION',
                           message='Sesión expirada', status=401)
    
    data = request.json
    jira_key = data.get('jira_key', '').strip().upper()
    command_type = data.get('command_type', '1')
    platform_param = data.get('platform_param', '').strip()
    retries = data.get('retries', 3)
    branches_dict = data.get('branches_dict', {})  # {branch: [path1, path2]}
    patch_selections = data.get('patch_selections', {})  # {branch: patch_path}
    additional_flags = (data.get('additional_flags') or '').strip()
    
    # Validaciones
    if not jira_key or not command_type or not platform_param or not branches_dict:
        return make_response(False, error_code='E_PARAMS',
                           message='Parámetros incompletos', status=400)
    
    try:
        service = CommandService(session['token'])
        
        # Obtener datos de JIRA
        jira_data = service.get_jira_data(jira_key)
        if not jira_data:
            return make_response(False, error_code='E_NOT_FOUND',
                               message=f'JIRA {jira_key} no encontrado', status=404)
        
        # Convertir branches_dict a formato esperado
        converted_branches = {}
        for branch, builds_paths in branches_dict.items():
            converted_branches[branch] = [{
                'path': path,
                'branch': branch,
                'mtime_str': ''
            } for path in builds_paths]
        
        # Generar comandos
        commands = service.generate_commands_for_branches(
            jira_data, jira_key, command_type, platform_param,
            retries, converted_branches, patch_selections, additional_flags
        )
        
        # Guardar cada comando en historial
        for cmd in commands:
            save_run_history(
                session['email'],
                jira_key,
                cmd.get('branch'),
                cmd['command'],
                None,  # run_id
                'generated',
                None  # exit_code
            )
        
        # Log action
        log_user_action(session['email'], 'generate_multiple_commands', {
            'jira_key': jira_key,
            'type': command_type,
            'branches': len(commands)
        })
        
        return make_response(True, data={'commands': commands},
                           message=f'{len(commands)} comandos generados')
        
    except Exception as e:
        traceback.print_exc()
        return make_response(False, error_code='E_GENERATE',
                           message=f'Error generando comandos: {str(e)}', status=500)

# ============================================================================
# ROUTES - History
# ============================================================================

@app.route('/api/history', methods=['GET'])
def get_history():
    """Obtener historial de comandos del usuario"""
    if 'email' not in session:
        return make_response(False, error_code='E_SESSION',
                           message='Sesión expirada', status=401)
    
    limit = request.args.get('limit', 50, type=int)
    
    try:
        history = get_run_history(session['email'], limit)
        return make_response(True, data={'history': history},
                           message=f'{len(history)} registros encontrados')
    except Exception as e:
        return make_response(False, error_code='E_DB',
                           message=f'Error obteniendo historial: {str(e)}', status=500)

# ============================================================================
# ROUTES - Utilities
# ============================================================================

@app.route('/api/command_types', methods=['GET'])
def get_command_types():
    """Obtener lista de tipos de comandos disponibles"""
    return make_response(True, data={
        'command_types': CommandService.COMMAND_TYPES
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return make_response(True, data={
        'status': 'healthy',
        'version': '2.0'
    })

# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return make_response(False, error_code='E_NOT_FOUND',
                        message='Endpoint no encontrado', status=404)

@app.errorhandler(500)
def internal_error(error):
    return make_response(False, error_code='E_SERVER',
                        message='Error interno del servidor', status=500)

# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Iniciando Web Application V2")
    print("=" * 60)
    print("📍 URL: http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
