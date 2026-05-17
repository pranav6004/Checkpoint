import os
import json
import inspect
from dataclasses import dataclass, field, asdict
from typing import List

@dataclass
class GameConfig:
    name: str
    save_path: str
    max_backups: int = 10

@dataclass
class AppConfig:
    games: List[GameConfig] = field(default_factory=list)
    upload_delay_seconds: int = 30
    start_with_windows: bool = True
    notifications: bool = True

class ConfigManager:
    def __init__(self):
        # We use %APPDATA%/Checkpoint for our config
        appdata = os.environ.get('APPDATA')
        if not appdata:
            # Fallback if APPDATA is not defined (e.g. some Unix-like environments under python on windows)
            appdata = os.path.expanduser('~')
            
        self.app_data_dir = os.path.join(appdata, 'Checkpoint')
        self.config_path = os.path.join(self.app_data_dir, 'config.json')
        
        self.ensure_dir_exists()
        self.config = self.load_config()

    def ensure_dir_exists(self):
        os.makedirs(self.app_data_dir, exist_ok=True)

    def load_config(self) -> AppConfig:
        if not os.path.exists(self.config_path):
            config = AppConfig()
            self.save_config(config)
            return config
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Convert list of dicts to list of GameConfig objects
                if 'games' in data:
                    data['games'] = [GameConfig(**g) for g in data['games']]
                
                # Filter data to only include valid AppConfig fields for backwards compatibility
                valid_keys = set(inspect.signature(AppConfig).parameters.keys())
                filtered_data = {k: v for k, v in data.items() if k in valid_keys}
                
                return AppConfig(**filtered_data)
        except Exception as e:
            print(f"Error loading config, using defaults: {e}")
            return AppConfig()

    def save_config(self, config: AppConfig = None):
        if config is None:
            config = self.config
            
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                # Disable ascii conversion so we can handle unicode chars in paths
                json.dump(asdict(config), f, indent=4, ensure_ascii=False)
                
            # Security Audit Fix: Lock down permissions on the config file
            if os.name == 'nt':
                import subprocess
                try:
                    # /inheritance:r removes inherited permissions
                    # /grant "%USERNAME%:F" gives the current user Full Control
                    username = os.environ.get('USERNAME')
                    subprocess.run(
                        ['icacls', self.config_path, '/inheritance:r', '/grant', f'{username}:F'],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                except Exception as perm_err:
                    print(f"Warning: Could not set strict permissions on config file: {perm_err}")

            self.config = config
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def add_game(self, name: str, save_path: str, max_backups: int = 10):
        # Format the path cleanly
        save_path = os.path.normpath(save_path)
        
        # Check for duplicates by name OR by exact path
        for i, game in enumerate(self.config.games):
            if game.name.lower() == name.lower():
                self.config.games[i] = GameConfig(name, save_path, max_backups)
                return self.save_config()
            elif os.path.normcase(game.save_path) == os.path.normcase(save_path):
                print(f"Duplicate path skipped: {save_path} is already being tracked by {game.name}")
                return False
                
        # Append new game
        self.config.games.append(GameConfig(name, save_path, max_backups))
        return self.save_config()
        
    def remove_game(self, name: str):
        original_count = len(self.config.games)
        self.config.games = [g for g in self.config.games if g.name != name]
        if len(self.config.games) < original_count:
            return self.save_config()
        return False

    def add_games_bulk(self, games_list: list) -> list:
        added = []
        changed = False
        
        existing_names = {g.name.lower() for g in self.config.games}
        existing_paths = {os.path.normcase(g.save_path) for g in self.config.games}
        
        for name, save_path in games_list:
            save_path = os.path.normpath(save_path)
            name_lower = name.lower()
            path_case = os.path.normcase(save_path)
            
            if name_lower not in existing_names and path_case not in existing_paths:
                self.config.games.append(GameConfig(name, save_path, 10))
                existing_names.add(name_lower)
                existing_paths.add(path_case)
                added.append((name, save_path))
                changed = True
                
        if changed:
            self.save_config()
            
        return added

# Global instance
config_manager = ConfigManager()
