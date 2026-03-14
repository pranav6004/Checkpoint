import os
import sys
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
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

def authenticate():
    """ Authenticates the user and returns the credentials. """
    creds = None
    token_path = os.path.join(config_manager.app_data_dir, 'token.json')
    
    # Check if we already have a valid token
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            print(f"Error loading token: {e}")
            creds = None

    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                creds = None
                
        if not creds:
            # We need to authenticate from scratch
            credentials_path = get_resource_path('credentials.json')
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Missing {credentials_path}. You need to configure Google Cloud OAuth client secrets.")
                
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES)
            
            # This will pop open the browser on an ephemeral port
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            
        # Security Audit Fix: Lock down permissions on the token file
        if os.name == 'nt':
            import subprocess
            try:
                username = os.environ.get('USERNAME')
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
