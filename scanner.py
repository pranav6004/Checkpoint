import os
import requests
import yaml
from pathlib import Path

import time
import json
import glob

LUDUSAVI_URL = "https://raw.githubusercontent.com/mtkennerly/ludusavi-manifest/master/data/manifest.yaml"
MANIFEST_CACHE_FILE = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'Checkpoint', 'manifest_cache.json')

def get_manifest():
    """Fetches the manifest from cache if fresh, otherwise downloads and caches as JSON for instant loading."""
    try:
        if os.path.exists(MANIFEST_CACHE_FILE):
            # Check if file is less than 7 days old (604800 seconds)
            if time.time() - os.path.getmtime(MANIFEST_CACHE_FILE) < 604800:
                with open(MANIFEST_CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
    except Exception as e:
        print(f"Failed to read cache: {e}")
        
    print("Downloading fresh manifest...")
    response = requests.get(LUDUSAVI_URL, timeout=10)
    response.raise_for_status()
    manifest = yaml.safe_load(response.text)
    
    try:
        os.makedirs(os.path.dirname(MANIFEST_CACHE_FILE), exist_ok=True)
        with open(MANIFEST_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
    except Exception as e:
        print(f"Failed to write cache: {e}")
        
    return manifest

def resolve_ludusavi_path(path_str):
    """Replaces Ludusavi placeholders with actual Windows paths."""
    user_profile = os.path.expanduser('~')
    
    # Common Ludusavi variables
    replacements = {
        "<winUserProfile>": user_profile,
        "<winDocuments>": os.path.join(user_profile, "Documents"),
        "<winLocalAppData>": os.path.expandvars("%LOCALAPPDATA%"),
        "<winAppData>": os.path.expandvars("%APPDATA%"),
        "<winSavedGames>": os.path.join(user_profile, "Saved Games"),
        "<winPublic>": os.path.expandvars("%PUBLIC%"),
        "<winDir>": os.path.expandvars("%WINDIR%"),
        "<winProgramFiles>": os.path.expandvars("%ProgramFiles%"),
        "<winProgramFiles86>": os.path.expandvars("%ProgramFiles(x86)%"),
        "<winProgramData>": os.path.expandvars("%ProgramData%"),
        "<storeUserId>": "*",
        "<osUserName>": os.environ.get("USERNAME"),
        "<root>": "C:\\Program Files (x86)\\Steam",
    }
    
    resolved = path_str
    for key, val in replacements.items():
        if key in resolved:
            resolved = resolved.replace(key, val)
            
    # Some paths use forward slashes, normalize for Windows
    resolved = os.path.normpath(resolved)
        
    return resolved

def scan_for_games():
    """
    Downloads the Ludusavi manifest, parses it, and checks the local drive 
    for matching save directories. Also checks cracked game paths.
    Returns a list of tuples: [(game_name, path), ...]
    """
    found_games = []
    
    # 1. Scan Ludusavi DB
    try:
        manifest = get_manifest()
        
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
                        
                        matches = glob.glob(resolved_path, recursive=True)
                        found = False
                        for match in matches:
                            save_dir = os.path.dirname(match) if os.path.isfile(match) else match
                            if os.path.exists(save_dir) and os.path.isdir(save_dir):
                                found_games.append((game_name, save_dir))
                                found = True
                                break
                        if found:
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
                    game_name = app_id_to_name.get(app_id)
                    final_name = f"{game_name} ({group})" if game_name else f"{group} Save {app_id}"
                    found_games.append((final_name, app_path))
                    
    # Goldberg AppData
    if os.path.exists(goldberg):
        for app_id in os.listdir(goldberg):
            # Ignore global settings folder
            if app_id == "settings":
                continue
            app_path = os.path.join(goldberg, app_id)
            if os.path.isdir(app_path):
                game_name = app_id_to_name.get(app_id)
                final_name = f"{game_name} (Goldberg)" if game_name else f"Goldberg Save {app_id}"
                found_games.append((final_name, app_path))
                
    # GSE Saves AppData
    gse_saves = os.path.join(os.path.expandvars("%APPDATA%"), "GSE Saves")
    if os.path.exists(gse_saves):
        for app_id in os.listdir(gse_saves):
            if app_id == "settings":
                continue
            app_path = os.path.join(gse_saves, app_id)
            if os.path.isdir(app_path):
                game_name = app_id_to_name.get(app_id)
                final_name = f"{game_name} (GSE)" if game_name else f"GSE Save {app_id}"
                found_games.append((final_name, app_path))

    return found_games
