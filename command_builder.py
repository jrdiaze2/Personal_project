#!/usr/bin/env python3
# Centralized command builder for JIRA test executions

from typing import Optional

DEFAULT_RETRIES = 2

class CommandBuildError(Exception):
    pass

def build_command(
    command_type: str,
    test_case: str,
    primary_build: str,
    secondary_build: Optional[str],
    platform: str,
    platform_complement: str,
    jira_key: str,
    additional_flags: str = "",
    patch_path: Optional[str] = None
) -> str:
    """Construye el comando final según el tipo solicitado.

    Nuevas reglas (según requerimiento del usuario):
    - Todos los tipos usan herramienta `ht` (incl. DRY_RUN, UPGRADE_DOWNGRADE, HOTPATCH, CONFIG_RESTORE).
    - Orden base (Normal): ht -t <tc> -i <build> -y -h <platform> -r <retries> [flags] -m <jira>#NoKill
    - ISSU / UPGRADE_DOWNGRADE requieren dos builds: el más reciente (primary_build) y el segundo (secondary_build).
        * Para ISSU/UPGRADE_DOWNGRADE: -i usa el segundo más reciente (secondary_build) y -secBuildImage el más reciente (primary_build).
        * Variante ISSU_ALLOW_SAME_VERSION (command_type == 'ISSU_ALLOW_SAME_VERSION'): solo un build; -i es el más reciente y NO se incluye -secBuildImage.
        * Variante ISSU_UPGRADE_ON_HA agrega flag: -passThru --issu-upgrade-on-ha.
    - DRY_RUN agrega: -passThru --dry-run.
    - CONFIG_RESTORE agrega: -passThru --config-restore.
    - HOTPATCH: ht -t <tc> -y -i <build> -passThru --hot-patch-on-setup -h <platform> -r <retries> -m <jira>#NoKill -p <patch>.
        * Usa solo primary_build en -i.
        * patch_path obligatorio.
    - additional_flags (si vienen) se inyectan justo antes de #NoKill dentro de -m <jira> ... #NoKill.
    - platform_complement se concatena a la plataforma (ej: 6400ISSU para ISSU al construir -h).
    - Para ISSU se añade 'ISSU' al parámetro -h, ya que ejemplo: -h 6400ISSU.
    """
    if not all([command_type, test_case, primary_build, jira_key, platform]):
        raise CommandBuildError("Missing required parameters for command construction")

    retries = DEFAULT_RETRIES
    platform_param = f"{platform}{platform_complement}" if platform_complement else platform
    cmd: Optional[str] = None

    # Normal
    if command_type == 'Normal':
        cmd = f"ht -t {test_case} -i {primary_build} -y -h {platform_param} -r {retries} -m {jira_key}#NoKill"

    # ISSU base / upgrade_on_ha / allow_same_version
    elif command_type in ['ISSU', 'ISSU_BASE', 'ISSU_NO_FLAGS', 'ISSU_UPGRADE_ON_HA', 'ISSU_ALLOW_SAME_VERSION']:
        # Allow same version uses only the most recent build (primary)
        if command_type == 'ISSU_ALLOW_SAME_VERSION':
            cmd = (
                f"ht -t {test_case} -i {primary_build} -y -h {platform_param}ISSU -r {retries} "
                f"-passThru --issu-allow-same-version -m {jira_key}#NoKill"
            )
        else:
            if not secondary_build:
                raise CommandBuildError("ISSU requiere dos builds (primario y secundario).")
            # -i segundo más reciente (secondary_build), -secBuildImage más reciente (primary_build)
            base = (
                f"ht -t {test_case} -i {secondary_build} -y -h {platform_param}ISSU -r {retries} "
                f"-secBuildImage {primary_build}"
            )
            if command_type == 'ISSU_UPGRADE_ON_HA':
                base += " -passThru --issu-upgrade-on-ha"
            cmd = base + f" -m {jira_key}#NoKill"

    # UPGRADE_DOWNGRADE
    elif command_type == 'UPGRADE_DOWNGRADE':
        if not secondary_build:
            raise CommandBuildError("UPGRADE_DOWNGRADE requiere dos builds.")
        cmd = (
            f"ht -t {test_case} -i {secondary_build} -y -h {platform_param} -r {retries} "
            f"-passThru --upgrade-downgrade -secBuildImage {primary_build} -m {jira_key}#NoKill"
        )

    # DRY_RUN
    elif command_type == 'DRY_RUN':
        cmd = f"ht -t {test_case} -i {primary_build} -y -h {platform_param} -r {retries} -passThru --dry-run -m {jira_key}#NoKill"

    # CONFIG_RESTORE
    elif command_type == 'CONFIG_RESTORE':
        cmd = f"ht -t {test_case} -i {primary_build} -y -h {platform_param} -r {retries} -passThru --config-restore -m {jira_key}#NoKill"

    # HOTPATCH
    elif command_type == 'HOTPATCH':
        if not patch_path:
            raise CommandBuildError("HOTPATCH requiere patch_path (-p).")
        cmd = (
            f"ht -t {test_case} -y -i {primary_build} -passThru --hot-patch-on-setup "
            f"-h {platform_param} -r {retries} -m {jira_key}#NoKill -p {patch_path}"
        )
    else:
        raise CommandBuildError(f"Unsupported command type: {command_type}")

    if additional_flags:
        cmd = cmd.replace(f"-m {jira_key}#NoKill", f"-m {jira_key} {additional_flags}#NoKill")
    return cmd

def requires_two_builds(command_type: str) -> bool:
    """Indica si el tipo necesita dos builds (más reciente y segundo)."""
    if command_type in ['ISSU_ALLOW_SAME_VERSION', 'HOTPATCH', 'Normal', 'DRY_RUN', 'CONFIG_RESTORE']:
        return False
    if command_type.startswith('ISSU'):
        return True
    if command_type == 'UPGRADE_DOWNGRADE':
        return True
    return False
