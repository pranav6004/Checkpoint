# Checkpoint

A lightweight Windows background utility that watches save game folders for changes and automatically backs them up to Google Drive. It securely lives in your system tray and silently protects your saves every time you play.

## Features
- **Zero-CPU Watching:** Uses OS-native file system events (`watchdog`) to monitor folders without constant polling.
- **Smart Debouncing:** Waits for you to finish saving before uploading, handling bursty or sequential file writes smoothly.
- **Google Drive Integration:** Uploads zipped, timestamped backups directly into a clean `Checkpoint/` folder on your Drive and automatically prunes old backups.
- **Privacy First:** Uses the `drive.file` OAuth scope, meaning the app can only see and manage files *it* creates. It has no access to the rest of your Drive.
- **Set and Forget:** Runs silently in the background alongside your games.

## Usage for End Users

1. Download the latest `Checkpoint.exe` from the Releases page.
2. Run it. On first launch, it will open your browser to log into Google securely.
3. Right click the blue tray icon in your Windows taskbar -> **Add Game**.
4. Select your save directory, give it a name (like `Elden Ring`), and you're good to go!

*Note: Configuration is stored locally in `%APPDATA%\Checkpoint\config.json`. You can edit this directly if you want to tweak things like the `upload_delay_seconds` or max backups kept.*

## Building from Source

To build Checkpoint yourself, you need Python and your own Google Cloud credentials.

1. Clone the repository.
2. Install requirements:
   ```cmd
   pip install -r requirements.txt
   ```
3. [Create a Google Cloud Project](https://developers.google.com/workspace/guides/create-project) and enable the **Google Drive API**.
4. Set up an **OAuth consent screen** (test/unverified status is fine for personal use).
5. Create an **OAuth 2.0 Client ID** (Application Type: Desktop App) and download the JSON.
6. Rename that file to `credentials.json` and place it in the same directory as `main.py` (refer to `credentials.example.json` for structure).
7. Run the application locally:
   ```cmd
   python main.py
   ```

### Creating the `.exe` Release

You can build a standalone executable using `PyInstaller`:

```cmd
pyinstaller --noconfirm --onefile --windowed --add-data "credentials.json;." main.py
```

The resulting `.exe` will be built into the `dist/` folder. It bundles your `credentials.json` internally so end users do not need to deal with the Google API developer setup.

## Privacy Policy
Checkpoint asks for the **"See, edit, create, and delete only the specific Google Drive files you use with this app"** permission (`https://www.googleapis.com/auth/drive.file`).

It does NOT collect analytics, telemetry, or sync any data other than the folders you explicitly configure it to watch via the tray UI. All authentication tokens are stored safely & locally on your machine in `%APPDATA%\Checkpoint\token.json`.

## Frequently Asked Questions (FAQ)

**Do I need to install Python to run Checkpoint?**
No! If you download the `Checkpoint.exe` from the GitHub Releases page, you don't need to know anything about Python or coding. It is a completely self-contained application. Just double-click and run it.

**Is the "Localhost" pop-up during login safe?**
Yes. When you first run Checkpoint, it opens a page in your web browser asking you to log into Google. This is the official Google secure login. Because Checkpoint is an independent open-source tool, Google will show a warning saying "Google hasn't verified this app." Simply click **Advanced -> Go to Checkpoint (unsafe)** to safely proceed.

**Is using the Google Drive API free?**
100% free! Google gives extremely generous free quotas (up to 1,000,000 requests per day) that you will never hit just by backing up game saves.

**Do I have to add my game folders every single time I restart my computer?**
No! You only have to add a game once. Checkpoint remembers your folders in a hidden configuration file and will automatically resume watching them whenever your computer reboots or the app is restarted.
