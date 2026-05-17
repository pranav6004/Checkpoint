import os
import requests
import yaml
from pathlib import Path

LUDUSAVI_URL = "https://raw.githubusercontent.com/mtkennerly/ludusavi-manifest/master/data/manifest.yaml"

def resolve_ludusavi_path(path_str):
    """Replaces Ludusavi placeholders with actual Windows paths."""
    user_profile = os.path.expanduser('~')
    
    # Common Ludusavi variables
    replacements = {
        "<USERPROFILE>": user_profile,
        "<DOCUMENTS>": os.path.join(user_profile, "Documents"),
        "<LOCALAPPDATA>": os.path.expandvars("%LOCALAPPDATA%"),
        "<APPDATA>": os.path.expandvars("%APPDATA%"),
        "<SAVEDGAMES>": os.path.join(user_profile, "Saved Games"),
        "<PUBLIC>": os.path.expandvars("%PUBLIC%"),
        "<WINDIR>": os.path.expandvars("%WINDIR%"),
        "<PROGRAMFILES>": os.path.expandvars("%ProgramFiles%"),
        "<PROGRAMFILES64>": os.path.expandvars("%ProgramFiles%"),
        "<PROGRAMFILES86>": os.path.expandvars("%ProgramFiles(x86)%"),
    }
    
    resolved = path_str
    for key, val in replacements.items():
        if key in resolved:
            resolved = resolved.replace(key, val)
            
    # Some paths use forward slashes, normalize for Windows
    return os.path.normpath(resolved)

def scan_for_games():
    """
    Downloads the Ludusavi manifest, parses it, and checks the local drive 
    for matching save directories. Also checks cracked game paths.
    Returns a list of tuples: [(game_name, path), ...]
    """
    found_games = []
    
    # 1. Scan Ludusavi DB
    try:
        response = requests.get(LUDUSAVI_URL, timeout=10)
        response.raise_for_status()
        manifest = yaml.safe_load(response.text)
        
        # Build steam ID to name mapping for emulator detection
        app_id_to_name = {}
        for game_name, game_data in manifest.items():
            if 'steam' in game_data and 'id' in game_data['steam']:
                app_id_to_name[str(game_data['steam']['id'])] = game_name
                
            if 'files' in game_data:
                for path_template, attributes in game_data['files'].items():
                    # Only grab paths marked as save data (not configs if we can avoid it, but Ludusavi generally marks saves with tags)
                    tags = attributes.get('tags', []) if attributes else []
                    if 'save' in tags or not tags:
                        resolved_path = resolve_ludusavi_path(path_template)
                        
                        # Stop at the first valid path found for this game to avoid duplicate folders for the same game
                        if os.path.exists(resolved_path) and os.path.isdir(resolved_path):
                            found_games.append((game_name, resolved_path))
                            break
                            
    except Exception as e:
        print(f"Error fetching/parsing Ludusavi database: {e}")

    # 2. Scan Cracked Game Emulators (CODEX, RUNE, FLT, Goldberg)
    public_steam = os.path.join(os.path.expandvars("%PUBLIC%"), "Documents", "Steam")
    goldberg = os.path.join(os.path.expandvars("%APPDATA%"), "Goldberg SteamEmu Saves")
    
    # Emu groups in Public/Documents/Steam
    emu_groups = ["CODEX", "RUNE", "FLT", "TENOKE"]
    for group in emu_groups:
        group_path = os.path.join(public_steam, group)
        if os.path.exists(group_path):
            # The subdirectories are Steam AppIDs
            for app_id in os.listdir(group_path):
                app_path = os.path.join(group_path, app_id)
                if os.path.isdir(app_path):
                    game_name = app_id_to_name.get(app_id, f"{group} Save {app_id}")
                    found_games.append((game_name, app_path))
                    
    # Goldberg AppData
    if os.path.exists(goldberg):
        for app_id in os.listdir(goldberg):
            # Ignore global settings folder
            if app_id == "settings":
                continue
            app_path = os.path.join(goldberg, app_id)
            if os.path.isdir(app_path):
                game_name = app_id_to_name.get(app_id, f"Goldberg Save {app_id}")
                found_games.append((game_name, app_path))

    return found_games
