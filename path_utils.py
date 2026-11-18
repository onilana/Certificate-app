import os
import sys

def get_base_dir() -> str:
    """
    Returns the root directory where the app is installed/running.
    Used for user-writable persistent files (config.json, certificates.db, Output_Certificates/, custom_positions.json).
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_asset_path(*parts: str) -> str:
    """
    Returns the path to a bundled asset (templates, fonts, icons),
    resolving correctly across Python source execution and PyInstaller (onedir & onefile).
    """
    # 1. PyInstaller single-file temp extraction dir (_MEIPASS)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        p = os.path.join(sys._MEIPASS, *parts)
        if os.path.exists(p):
            return p

    # 2. PyInstaller directory mode (next to .exe)
    if getattr(sys, 'frozen', False):
        p = os.path.join(os.path.dirname(sys.executable), *parts)
        if os.path.exists(p):
            return p

    # 3. Source directory
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)
