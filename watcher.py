import os
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config import config_manager
from uploader import DriveUploader

class SaveHandler(FileSystemEventHandler):
    def __init__(self, watcher):
        super().__init__()
        self.watcher = watcher

    def on_modified(self, event):
        self._handle_event(event)
        
    def on_created(self, event):
        self._handle_event(event)

    def _handle_event(self, event):
        # Ignore directory changes, we care when files change
        if event.is_directory:
            return
            
        file_path = event.src_path
        game_name = self.watcher.get_game_for_path(file_path)
        if game_name:
            self.watcher.trigger_game_change(game_name)

class Watcher:
    def __init__(self, uploader):
        self.uploader = uploader
        self.observer = Observer()
        self.handler = SaveHandler(self)
        self.watches = {}
        
        # Debounce state management
        self.pending_uploads = {} # game_name -> timestamp to upload
        self.debounce_timer = None
        self.is_running = False
        self.lock = threading.Lock()
        
    def set_notification_callback(self, callback):
        self.notification_callback = callback

    def start(self):
        self.is_running = True
        self._update_watches_from_config()
        self.observer.start()
        
        # Start a background thread to handle debounce timers
        self.debounce_timer = threading.Thread(target=self._debounce_loop, daemon=True)
        self.debounce_timer.start()

    def get_game_for_path(self, path):
        path = os.path.abspath(path)
        for game in config_manager.config.games:
            game_path = os.path.abspath(game.save_path)
            # Check if modified path is under the game save folder
            if path.startswith(game_path):
                return game.name
        return None

    def trigger_game_change(self, game_name):
        with self.lock:
            delay = config_manager.config.upload_delay_seconds
            self.pending_uploads[game_name] = time.time() + delay
            print(f"[{game_name}] Save changed. Upload queued in {delay} seconds.")

    def _debounce_loop(self):
        while self.is_running:
            time.sleep(1)
            now = time.time()
            to_upload = []
            
            with self.lock:
                for game_name, upload_time in list(self.pending_uploads.items()):
                    if now >= upload_time:
                        to_upload.append(game_name)
                        del self.pending_uploads[game_name]
            
            # Perform uploads outside the lock so we don't block other save events
            for game_name in to_upload:
                self._do_upload(game_name)

    def _do_upload(self, game_name):
        game_config = next((g for g in config_manager.config.games if g.name == game_name), None)
        if game_config:
            print(f"[{game_name}] Debounce period ended. Zipping and uploading...")
            success = self.uploader.upload_save(game_config)
            
            if success and config_manager.config.notifications:
                self._notify(f"{game_name} backed up ✓", "Save synced to Google Drive")
                
    def _notify(self, title, message):
        if hasattr(self, 'notification_callback') and self.notification_callback:
            self.notification_callback(title, message)
        else:
            print(f"NOTIFICATION: {title} - {message}")

    def refresh_watches(self):
        """Called when settings or games change in the UI"""
        self._update_watches_from_config()

    def _update_watches_from_config(self):
        # Clear all existing watches to avoid stale references if paths change
        self.observer.unschedule_all()
        self.watches.clear()
        
        for game in config_manager.config.games:
            if os.path.exists(game.save_path):
                watch = self.observer.schedule(self.handler, game.save_path, recursive=True)
                self.watches[game.name] = watch
                print(f"Started watching: {game.name} at {game.save_path}")
            else:
                print(f"Warning: Path for {game.name} does not exist: {game.save_path}")

    def stop(self):
        self.is_running = False
        self.observer.stop()
        self.observer.join()
