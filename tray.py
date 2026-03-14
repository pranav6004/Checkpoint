import pystray
from PIL import Image, ImageDraw
import threading
import os
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog, simpledialog

from config import config_manager
from startup_manager import enable_startup, disable_startup

class TrayMenu:
    def __init__(self, watcher, uploader):
        self.watcher = watcher
        self.uploader = uploader
        self.icon = None
        self.watcher.set_notification_callback(self.notify)

    def create_image(self):
        # Generate a simple icon programmatically
        # Blue circle with a white upload cloud/arrow
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(image)
        # Blue circle
        d.ellipse((4, 4, 60, 60), fill=(66, 133, 244))
        # White up arrow
        d.polygon([(32, 16), (16, 36), (26, 36), (26, 48), (38, 48), (38, 36), (48, 36)], fill=(255, 255, 255))
        return image

    def run(self):
        self.icon = pystray.Icon(
            "Checkpoint", 
            self.create_image(), 
            "Checkpoint", 
            self._create_menu()
        )
        
        # We start the watcher right before blocking on the tray icon
        self.watcher.start()
        print("Checkpoint is ready and watching in the system tray.")
        
        # This blocks forever until icon.stop() is called
        self.icon.run()

    def _create_menu(self):
        game_count = len(config_manager.config.games)
        return pystray.Menu(
            pystray.MenuItem(f"● Watching {game_count} games", lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Backup Now", self.action_backup_now),
            pystray.MenuItem("Add Game", self.action_add_game),
            pystray.MenuItem("Open Config File", self.action_open_settings),
            pystray.MenuItem(
                "Run on Startup", 
                self.action_toggle_startup, 
                checked=lambda item: config_manager.config.start_with_windows
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.action_quit)
        )

    def _update_menu(self):
        if self.icon:
            self.icon.menu = self._create_menu()

    def action_backup_now(self, icon, item):
        # Run in thread to not block the tray UI
        def backup_job():
            if not config_manager.config.games:
                self.notify("No Games", "Add a game first before backing up.")
                return
                
            self.notify("Starting Backup", "Zipping and uploading all games...")
            success_count = 0
            for game in config_manager.config.games:
                if self.uploader.upload_save(game):
                    success_count += 1
                    
            if success_count > 0:
                self.notify("Backup Complete", f"Successfully backed up {success_count} games.")
                
        threading.Thread(target=backup_job, daemon=True).start()

    def action_add_game(self, icon, item):
        def add_game_job():
            # Create a hidden root window for tkinter dialogs
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            # Step 1: Pick folder
            folder_path = filedialog.askdirectory(title="Select Save Folder")
            if not folder_path:
                root.destroy()
                return
                
            # Step 2: Name it
            game_name = simpledialog.askstring("Game Name", "Enter the name of the game (e.g., 'Elden Ring'):", parent=root)
            if not game_name or not game_name.strip():
                root.destroy()
                return
                
            # Add to config
            game_name = game_name.strip()
            config_manager.add_game(game_name, folder_path)
            
            # Tell watcher to pick up the new folder
            self.watcher.refresh_watches()
            
            # Update tray menu count
            self._update_menu()
            
            root.destroy()
            self.notify("Game Added", f"Now watching {game_name}.")
            
        threading.Thread(target=add_game_job).start()

    def action_open_settings(self, icon, item):
        # Open the config file in the default OS text editor
        config_path = config_manager.config_path
        try:
            if os.name == 'nt': # Windows
                os.startfile(config_path)
            elif sys.platform == 'darwin': # macOS
                subprocess.call(('open', config_path))
            else: # Linux
                subprocess.call(('xdg-open', config_path))
        except Exception as e:
            print(f"Failed to open config file: {e}")

    def action_quit(self, icon, item):
        print("Shutting down Checkpoint...")
        self.watcher.stop()
        self.icon.stop()

    def notify(self, title, message):
        if self.icon:
            try:
                self.icon.notify(message, title)
            except Exception as e:
                print(f"Failed to show toast notification: {e}")
                print(f"NOTIFICATION: {title} - {message}")
        else:
            print(f"NOTIFICATION: {title} - {message}")

    def action_toggle_startup(self, icon, item):
        new_state = not config_manager.config.start_with_windows
        
        if new_state:
            success = enable_startup()
        else:
            success = disable_startup()
            
        if success:
            config_manager.config.start_with_windows = new_state
            config_manager.save_config()
            self.notify("Startup Setting", f"Run on Startup is now {'Enabled' if new_state else 'Disabled'}")
        else:
            self.notify("Error", "Failed to change startup setting.")
