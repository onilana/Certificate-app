# -*- coding: utf-8 -*-
"""
Updater module for Mount Everest Certificate Printing Studio.
Supports:
1. Online update checking via Web URL / GitHub Releases (version.json).
2. Local Network / Shared Folder checking (LAN / Wi-Fi shared folder).
3. Offline manual update via Update ZIP package (USB / Local disk).
4. Administrator packaging tool to easily bundle updates for distribution.
"""

import os
import sys
import json
import shutil
import zipfile
import threading
import urllib.request
import urllib.error
import subprocess
from packaging import version as pkg_version
from version import APP_VERSION
from path_utils import get_base_dir

# List of sensitive user-specific data files that should NEVER be overwritten by an update
PRESERVED_USER_FILES = [
    'certificates.db',
    'config.json',
    'custom_positions.json'
]
PRESERVED_USER_DIRS = [
    'Output_Certificates'
]


def compare_versions(current_v: str, remote_v: str) -> bool:
    """Returns True if remote_v is strictly newer than current_v."""
    try:
        cur = current_v.lstrip('vV').strip()
        rem = remote_v.lstrip('vV').strip()
        return pkg_version.parse(rem) > pkg_version.parse(cur)
    except Exception:
        # Fallback numeric tuple split
        try:
            c_parts = [int(p) for p in cur.split('.') if p.isdigit()]
            r_parts = [int(p) for p in rem.split('.') if p.isdigit()]
            return r_parts > c_parts
        except Exception:
            return rem != cur


def fetch_remote_manifest(url: str, timeout: int = 5) -> dict:
    """Fetches and parses remote version.json manifest over HTTP/HTTPS."""
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'MountEverest-CertStudio-Updater'}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        content = response.read().decode('utf-8')
        return json.loads(content)


def fetch_network_manifest(folder_path: str) -> dict:
    """Reads version.json manifest from a local network shared folder."""
    manifest_path = os.path.join(folder_path, 'version.json')
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"version.json not found in {folder_path}")
    with open(manifest_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_for_updates(config: dict) -> dict:
    """
    Checks for updates according to user configuration:
    - First checks local network folder if configured.
    - Otherwise checks update URL if configured.
    Returns:
        dict with keys: 'has_update', 'current_version', 'new_version', 'notes', 'date', 'download_url', 'source'
    """
    res = {
        'has_update': False,
        'current_version': APP_VERSION,
        'new_version': APP_VERSION,
        'notes': '',
        'date': '',
        'download_url': '',
        'source': 'none',
        'error': None
    }

    net_folder = config.get('update_network_folder', '').strip()
    update_url = config.get('update_url', '').strip()

    manifest = None
    source_type = None

    # 1. Try local network folder if specified and accessible
    if net_folder and os.path.isdir(net_folder):
        try:
            manifest = fetch_network_manifest(net_folder)
            source_type = 'network'
        except Exception as e:
            res['error'] = f"Network folder check failed: {e}"

    # 2. Try URL if no network manifest found
    if not manifest and update_url and update_url.startswith(('http://', 'https://')):
        try:
            manifest = fetch_remote_manifest(update_url)
            source_type = 'url'
        except Exception as e:
            res['error'] = f"URL check failed: {e}"

    if manifest and isinstance(manifest, dict):
        new_v = str(manifest.get('version', '')).strip()
        if new_v and compare_versions(APP_VERSION, new_v):
            res['has_update'] = True
            res['new_version'] = new_v
            res['notes'] = manifest.get('changelog', manifest.get('notes', 'Bug fixes and performance improvements.'))
            res['date'] = manifest.get('release_date', manifest.get('date', ''))
            res['source'] = source_type
            
            # Resolve download URL:
            # If network folder, download_url can be relative filename inside that folder
            dl_url = manifest.get('download_url', '')
            if source_type == 'network' and dl_url and not os.path.isabs(dl_url):
                res['download_url'] = os.path.join(net_folder, dl_url)
            else:
                res['download_url'] = dl_url

    return res


def download_file(url_or_path: str, dest_path: str, progress_callback=None):
    """Downloads or copies update file with optional progress callback(percent)."""
    # If it's a local or network file path
    if os.path.isfile(url_or_path):
        total_size = os.path.getsize(url_or_path)
        chunk_size = 64 * 1024
        copied = 0
        with open(url_or_path, 'rb') as fsrc, open(dest_path, 'wb') as fdst:
            while True:
                chunk = fsrc.read(chunk_size)
                if not chunk:
                    break
                fdst.write(chunk)
                copied += len(chunk)
                if progress_callback and total_size > 0:
                    pct = min(100, int((copied / total_size) * 100))
                    progress_callback(pct)
        if progress_callback:
            progress_callback(100)
        return

    # HTTP / HTTPS download
    req = urllib.request.Request(
        url_or_path,
        headers={'User-Agent': 'MountEverest-CertStudio-Updater'}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        total_size = resp.headers.get('content-length')
        total_size = int(total_size) if total_size and total_size.isdigit() else 0
        chunk_size = 64 * 1024
        downloaded = 0
        with open(dest_path, 'wb') as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total_size > 0:
                    pct = min(100, int((downloaded / total_size) * 100))
                    progress_callback(pct)
        if progress_callback:
            progress_callback(100)


def apply_update_from_zip(zip_path: str, is_frozen: bool, base_dir: str):
    """
    Extracts update zip into a temporary staging folder, creates a self-executing
    helper batch script, launches it in a separate process, and exits the application
    so files are safely overwritten without Windows lock conflicts.
    """
    stage_dir = os.path.join(base_dir, "_update_staged")
    if os.path.exists(stage_dir):
        shutil.rmtree(stage_dir, ignore_errors=True)
    os.makedirs(stage_dir, exist_ok=True)

    # Extract update zip into staging folder
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(stage_dir)

    # If the zip extracted into a single root folder (e.g. CertificateStudio/...)
    subitems = os.listdir(stage_dir)
    if len(subitems) == 1 and os.path.isdir(os.path.join(stage_dir, subitems[0])):
        nested_dir = os.path.join(stage_dir, subitems[0])
        # Move all contents of nested_dir up to stage_dir
        for item in os.listdir(nested_dir):
            shutil.move(os.path.join(nested_dir, item), os.path.join(stage_dir, item))
        os.rmdir(nested_dir)

    # Protect user data in stage_dir: Remove any file from stage_dir that would overwrite user's DB / config
    for pf in PRESERVED_USER_FILES:
        candidate = os.path.join(stage_dir, pf)
        # If the user already has this file in base_dir, don't overwrite it with the package's default
        if os.path.exists(os.path.join(base_dir, pf)) and os.path.exists(candidate):
            try:
                os.remove(candidate)
            except Exception:
                pass

    for pd in PRESERVED_USER_DIRS:
        candidate_dir = os.path.join(stage_dir, pd)
        if os.path.exists(candidate_dir):
            try:
                shutil.rmtree(candidate_dir, ignore_errors=True)
            except Exception:
                pass

    # Create apply_update.bat helper
    bat_path = os.path.join(base_dir, "apply_update.bat")
    exe_path = sys.executable if is_frozen else os.path.join(base_dir, "CertificateStudio.exe")
    is_exe_present = is_frozen or os.path.exists(exe_path)

    relaunch_cmd = f'start "" "{exe_path}"' if is_exe_present else f'start "" "{sys.executable}" "app.py"'

    bat_content = f"""@echo off
title Updating Mount Everest Certificate Printing Studio...
echo ================================================================
echo Applying software updates... Please wait a moment.
echo ================================================================

:: Wait 2 seconds for main application process to fully release file locks
timeout /t 2 /nobreak > nul

:: Copy all staged update files over the app directory
xcopy "{stage_dir}\\*" "{base_dir}" /s /y /e /h > nul

:: Clean up staging directory and downloaded zip
if exist "{stage_dir}" rmdir /s /q "{stage_dir}"
if exist "{zip_path}" del /f /q "{zip_path}" 2>nul

echo Update applied successfully! Relaunching...
{relaunch_cmd}

:: Clean up this batch file
(goto) 2>nul & del "%~f0"
exit
"""
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(bat_content)

    # Launch helper batch script detached from this process
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(
        ['cmd.exe', '/c', bat_path],
        creationflags=CREATE_NO_WINDOW,
        close_fds=True
    )

    # Terminate current app cleanly
    sys.exit(0)


def create_update_package(new_version: str, changelog: str, target_output_dir: str) -> tuple[str, str]:
    """
    Administrator tool: Packages current application files into an update ZIP and generates version.json.
    Excludes user DB, user output certificates, build caches, git, and local temp files.
    Returns: (zip_path, json_path)
    """
    base_dir = get_base_dir()
    os.makedirs(target_output_dir, exist_ok=True)

    zip_filename = f"CertificateStudio_Update_v{new_version}.zip"
    zip_path = os.path.join(target_output_dir, zip_filename)
    json_path = os.path.join(target_output_dir, "version.json")

    # Files & directories to exclude
    EXCLUDE_NAMES = {
        'certificates.db',
        'Output_Certificates',
        '.git',
        '__pycache__',
        'build',
        'dist',
        'previews',
        '.pytest_cache',
        'update_package.zip',
        '_update_staged',
        'apply_update.bat'
    }

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(base_dir):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_NAMES and not d.startswith('.')]
            for f in files:
                if f in EXCLUDE_NAMES or f.endswith(('.pyc', '.tmp', '.log')):
                    continue
                # Also do not include current update files being generated
                if f == zip_filename or f == "version.json":
                    continue
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, base_dir)
                zf.write(full_path, rel_path)

    # Write version.json manifest
    manifest_data = {
        "version": new_version,
        "release_date": import_today_date(),
        "changelog": changelog.strip() or "Standard feature updates and bug fixes.",
        "download_url": zip_filename,  # relative filename for shared folder or replace with Web URL
        "mandatory": False
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(manifest_data, f, indent=4)

    return zip_path, json_path


def import_today_date():
    import datetime
    return datetime.date.today().strftime("%Y-%m-%d")
