import sys

def check_dependencies():
    """Ensure all required third-party packages are installed"""
    try:
        import googleapiclient
        import google_auth_oauthlib
        import pystray
        import PIL
        import watchdog
    except ImportError as e:
        print("ERROR: Missing dependencies.")
        print(f"Missing: {e.name}")
        print("\nPlease install the required packages using:")
        print("pip install google-api-python-client google-auth-oauthlib pystray Pillow watchdog psutil")
        sys.exit(1)

def main():
    check_dependencies()
    
    # Imports are done lazily after dependency check to give a cleaner error message
    print("Initializing Checkpoint...")
    from uploader import DriveUploader
    from watcher import Watcher
    from tray import TrayMenu
    from config import config_manager
    from startup_manager import enable_startup, disable_startup

    # Sync startup registry setting with config file preference
    if config_manager.config.start_with_windows:
        enable_startup()
    else:
        disable_startup()

    # 1. Initialize Uploader (handles Google Drive OAuth)
    # Note: On first run, this pops open the browser for authentication
    try:
        uploader = DriveUploader()
    except Exception as e:
        print(f"Failed to initialize Google Drive connection: {e}")
        input("Press Enter to exit...")
        sys.exit(1)
        
    # 2. Initialize the file watcher
    watcher = Watcher(uploader)
    
    # 3. Initialize and run the System Tray Interface
    # This blocks until the user quits via the tray menu
    tray = TrayMenu(watcher, uploader)
    tray.run()
    
    print("Checkpoint stopped.")

if __name__ == '__main__':
    main()
