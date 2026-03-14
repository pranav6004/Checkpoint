import sys
import os
import winreg

APP_NAME = "Checkpoint"
REGISTRY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

def get_executable_path():
    """Returns the absolute path to the running executable"""
    # If built with PyInstaller
    if getattr(sys, 'frozen', False):
        return os.path.abspath(sys.executable)
    # If running normally (for dev testing)
    # Be careful, this will register the python.exe path if not built, so it's a dev-only curiosity
    return os.path.abspath(sys.argv[0])

def enable_startup():
    try:
        # Wrap path in quotes to handle spaces
        exe_path = f'"{get_executable_path()}"'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        return True
    except Exception as e:
        print(f"Failed to enable startup: {e}")
        return False

def disable_startup():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
        return True
    except FileNotFoundError:
        # Already disabled
        return True
    except Exception as e:
        print(f"Failed to disable startup: {e}")
        return False

def is_startup_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return value == f'"{get_executable_path()}"'
    except Exception:
        return False
