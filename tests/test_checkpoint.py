import os
import sys
import tempfile
import unittest
import shutil

# Ensure Checkpoint directory is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import ConfigManager, GameConfig, AppConfig
from scanner import resolve_ludusavi_path
from watcher import Watcher


class TestLudusaviPathResolution(unittest.TestCase):
    def test_replaces_placeholders(self):
        user_home = os.path.expanduser('~')
        resolved = resolve_ludusavi_path("<winDocuments>/My Games/TestGame")
        expected = os.path.normpath(os.path.join(user_home, "Documents", "My Games", "TestGame"))
        self.assertEqual(resolved, expected)

    def test_replaces_appdata(self):
        appdata = os.path.expandvars("%APPDATA%")
        resolved = resolve_ludusavi_path("<winAppData>/TestGame/saves")
        expected = os.path.normpath(os.path.join(appdata, "TestGame", "saves"))
        self.assertEqual(resolved, expected)


class TestWatcherPathMatching(unittest.TestCase):
    def setUp(self):
        # Create a dummy uploader
        self.watcher = Watcher(uploader=None)
        self.temp_dir = tempfile.mkdtemp()
        
        # Setup games with overlapping prefix names
        self.doom_path = os.path.join(self.temp_dir, "Doom")
        self.doom_eternal_path = os.path.join(self.temp_dir, "Doom Eternal")
        os.makedirs(self.doom_path, exist_ok=True)
        os.makedirs(self.doom_eternal_path, exist_ok=True)

        from config import config_manager
        self.orig_games = config_manager.config.games
        config_manager.config.games = [
            GameConfig(name="Doom", save_path=self.doom_path),
            GameConfig(name="Doom Eternal", save_path=self.doom_eternal_path)
        ]

    def tearDown(self):
        from config import config_manager
        config_manager.config.games = self.orig_games
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_exact_path_match(self):
        self.assertEqual(self.watcher.get_game_for_path(self.doom_path), "Doom")
        self.assertEqual(self.watcher.get_game_for_path(self.doom_eternal_path), "Doom Eternal")

    def test_subpath_match(self):
        doom_save = os.path.join(self.doom_path, "slot1", "save.dat")
        self.assertEqual(self.watcher.get_game_for_path(doom_save), "Doom")

        eternal_save = os.path.join(self.doom_eternal_path, "slot1", "save.dat")
        self.assertEqual(self.watcher.get_game_for_path(eternal_save), "Doom Eternal")

    def test_prefix_isolation(self):
        # Crucial test: Ensure "Doom Eternal" is NOT mistakenly matched as "Doom"
        eternal_save = os.path.join(self.doom_eternal_path, "save.dat")
        matched = self.watcher.get_game_for_path(eternal_save)
        self.assertEqual(matched, "Doom Eternal")
        self.assertNotEqual(matched, "Doom")

    def test_case_insensitivity_on_windows(self):
        doom_save_upper = os.path.join(self.doom_path.upper(), "SAVE.DAT")
        self.assertEqual(self.watcher.get_game_for_path(doom_save_upper), "Doom")


class TestGoogleDriveQueryEscaping(unittest.TestCase):
    def test_query_escaping(self):
        # Test backslash and quote escaping
        name = r"Baldur's Gate \ Enhanced"
        safe_name = name.replace('\\', '\\\\').replace("'", "\\'")
        expected = r"Baldur\'s Gate \\ Enhanced"
        self.assertEqual(safe_name, expected)

    def test_trailing_backslash(self):
        name = "Game\\"
        safe_name = name.replace('\\', '\\\\').replace("'", "\\'")
        expected = "Game\\\\"
        self.assertEqual(safe_name, expected)


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = ConfigManager()
        self.config_manager.app_data_dir = self.temp_dir
        self.config_manager.config_path = os.path.join(self.temp_dir, "config.json")
        self.config_manager.config = AppConfig()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_atomic_save_and_load(self):
        self.config_manager.config.upload_delay_seconds = 45
        self.assertTrue(self.config_manager.save_config())

        # Verify file exists on disk
        self.assertTrue(os.path.exists(self.config_manager.config_path))
        
        # Verify tmp file was removed by atomic replace
        self.assertFalse(os.path.exists(self.config_manager.config_path + ".tmp"))

        # Re-read
        loaded = self.config_manager.load_config()
        self.assertEqual(loaded.upload_delay_seconds, 45)

    def test_duplicate_path_rejected(self):
        save_p = os.path.join(self.temp_dir, "saves")
        res1 = self.config_manager.add_game("Game1", save_p)
        self.assertTrue(res1)
        self.assertEqual(len(self.config_manager.config.games), 1)

        # Attempt to add same path under different name
        res2 = self.config_manager.add_game("Game2", save_p)
        self.assertFalse(res2)
        self.assertEqual(len(self.config_manager.config.games), 1)

    def test_same_name_updates_existing(self):
        save_p1 = os.path.join(self.temp_dir, "saves1")
        save_p2 = os.path.join(self.temp_dir, "saves2")
        self.config_manager.add_game("Witcher", save_p1, max_backups=5)
        self.assertEqual(self.config_manager.config.games[0].max_backups, 5)

        # Update Witcher with new path and backup count
        self.config_manager.add_game("Witcher", save_p2, max_backups=15)
        self.assertEqual(len(self.config_manager.config.games), 1)
        self.assertEqual(self.config_manager.config.games[0].save_path, os.path.normpath(save_p2))
        self.assertEqual(self.config_manager.config.games[0].max_backups, 15)


class TestCredentialsResolution(unittest.TestCase):
    def test_finds_credentials_file(self):
        from auth import get_credentials_path
        cred_path = get_credentials_path()
        self.assertTrue(os.path.exists(cred_path), f"Credentials file should exist, checked: {cred_path}")


if __name__ == '__main__':
    unittest.main()
