import os
import zipfile
import tempfile
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from auth import authenticate
from config import GameConfig

ROOT_FOLDER_NAME = "Checkpoint"

class DriveUploader:
    def __init__(self):
        # Authenticate and setup service
        # NOTE: This will trigger the browser if token is missing/expired!
        self.creds = authenticate()
        self.service = build('drive', 'v3', credentials=self.creds)
        self.root_folder_id = self._get_or_create_folder(ROOT_FOLDER_NAME)
        
    def _get_or_create_folder(self, folder_name, parent_id=None):
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
            
        results = self.service.files().list(
            q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        
        if files:
            return files[0]['id']
            
        # Folder doesn't exist, create it
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]
            
        folder = self.service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

    def _zip_folder(self, folder_path, game_name):
        # Create timestamped zip filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        zip_filename = f"save_{timestamp}.zip"
        
        # We put the temporary zip in the system's temp directory
        zip_path = os.path.join(tempfile.gettempdir(), f"{game_name}_{zip_filename}")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.isfile(folder_path):
                # User provided a single file instead of a folder
                zipf.write(folder_path, os.path.basename(folder_path))
            else:
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Archive name is the relative path
                        arcname = os.path.relpath(file_path, folder_path)
                        zipf.write(file_path, arcname)
                    
        return zip_path, zip_filename

    def upload_save(self, game_config: GameConfig):
        # Make sure the target folder exists
        if not os.path.exists(game_config.save_path):
            print(f"Error: Path {game_config.save_path} does not exist.")
            return False
            
        print(f"Uploading {game_config.name} saves from {game_config.save_path}...")
        
        zip_path = None
        try:
            game_folder_id = self._get_or_create_folder(game_config.name, self.root_folder_id)
            zip_path, zip_filename = self._zip_folder(game_config.save_path, game_config.name)
            
            file_metadata = {
                'name': zip_filename,
                'parents': [game_folder_id]
            }
            media = MediaFileUpload(zip_path, mimetype='application/zip', resumable=True)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            print(f"Successfully uploaded {zip_filename} to Drive (ID: {file.get('id')})")
            
            # Rotate out old backups
            self._cleanup_old_backups(game_folder_id, game_config.max_backups)
            return True
            
        except Exception as e:
            # Broad exception catch to prevent mass uploads from crashing the thread
            print(f"Error uploading {game_config.name} to Drive: {e}")
            return False
        finally:
            # Clean up local temporary zip file
            if zip_path and os.path.exists(zip_path):
                # The googleapiclient MediaFileUpload maintains an open file handle
                # We need to wait a tiny bit for it to be released on Windows.
                import time
                import gc
                
                # Delete the media object to encourage closing the file
                if 'media' in locals():
                    del media
                gc.collect()
                
                # Try a few times to delete the file
                for _ in range(3):
                    try:
                        os.remove(zip_path)
                        break
                    except Exception as cleanup_err:
                        time.sleep(1)
                else:
                    print(f"Warning: Could not remove temp file {zip_path} after 3 attempts.")

    def _cleanup_old_backups(self, folder_id, max_backups):
        # Order by creation time descending (newest first)
        query = f"'{folder_id}' in parents and mimeType='application/zip' and trashed=false"
        results = self.service.files().list(
            q=query, spaces='drive', 
            orderBy='createdTime desc',
            fields='files(id, name, createdTime)').execute()
            
        files = results.get('files', [])
        
        if len(files) > max_backups:
            # We have more backups than allowed, delete the oldest ones
            files_to_delete = files[max_backups:]
            for f in files_to_delete:
                try:
                    self.service.files().delete(fileId=f['id']).execute()
                    print(f"Deleted old backup: {f['name']}")
                except Exception as e:
                    print(f"Error deleting old backup {f['name']}: {e}")
