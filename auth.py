import os
import sys
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from config import config_manager

# Scope for Drive API (only files created by this app)
# Using drive.file scope builds trust as we can't access user's other files
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_credentials_path():
    """Locate credentials.json in user AppData, bundled resource, or current dir."""
    appdata_path = os.path.join(config_manager.app_data_dir, 'credentials.json')
    if os.path.exists(appdata_path):
        return appdata_path
    resource_path = get_resource_path('credentials.json')
    if os.path.exists(resource_path):
        return resource_path
    local_path = os.path.abspath('credentials.json')
    if os.path.exists(local_path):
        return local_path
    return appdata_path

def authenticate():
    """ Authenticates the user and returns the credentials. """
    creds = None
    token_path = os.path.join(config_manager.app_data_dir, 'token.json')
    credentials_path = get_credentials_path()
    
    # Read active client_id from credentials.json to detect credential rotation
    active_client_id = None
    if os.path.exists(credentials_path):
        try:
            with open(credentials_path, 'r', encoding='utf-8') as f:
                cred_data = json.load(f)
                active_client_id = cred_data.get('installed', {}).get('client_id')
        except Exception:
            pass
    
    # Check if we already have a valid token
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            # Invalidate cached token if the user configured a different client_id
            if active_client_id and getattr(creds, 'client_id', None) != active_client_id:
                print("OAuth Client ID changed in credentials.json. Re-authenticating with new client...")
                creds = None
        except Exception as e:
            print(f"Error loading token: {e}")
            creds = None

    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as ref_err:
                print(f"Token expired or revoked ({ref_err}). Re-authenticating...")
                creds = None
            except Exception as e:
                print(f"Warning: Could not refresh token (possible offline state): {e}")
                # Return current creds so the app can start without network connection
                return creds
                
        if not creds:
            # We need to authenticate from scratch
            credentials_path = get_credentials_path()
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"Missing credentials file. Place your Google Cloud OAuth client secrets at: {credentials_path}"
                )
                
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES)
            
            # This will pop open the browser on an ephemeral port
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run (atomically)
        temp_token_path = token_path + ".tmp"
        with open(temp_token_path, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())
        os.replace(temp_token_path, token_path)
            
        # Security Audit Fix: Lock down permissions on the token file
        if os.name == 'nt':
            import subprocess
            try:
                username = os.environ.get('USERNAME')
                if username:
                    subprocess.run(
                        ['icacls', token_path, '/inheritance:r', '/grant', f'{username}:F'],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
            except Exception as perm_err:
                print(f"Warning: Could not set strict permissions on token file: {perm_err}")

    return creds

if __name__ == '__main__':
    # Test authentication directly
    authenticate()
    print("Authentication successful!")
