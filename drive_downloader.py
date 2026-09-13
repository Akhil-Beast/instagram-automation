import os
import json
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from dotenv import load_dotenv

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    service_account_env = os.getenv('SERVICE_ACCOUNT_JSON')
    if service_account_env:
        creds_info = json.loads(service_account_env)
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    elif os.path.exists('service_account.json'):
        creds = Credentials.from_service_account_file('service_account.json', scopes=SCOPES)
    else:
        print("No service account found for Google Drive.")
        return None
    return build('drive', 'v3', credentials=creds)

def download_video_from_drive(file_name, output_path):
    """
    Finds a video by filename in Google Drive and downloads it to output_path.
    """
    service = get_drive_service()
    if not service:
        return False
        
    print(f"Searching Google Drive for: '{file_name}'...")
    clean_name = os.path.basename(file_name).strip()
    
    # Exact match query
    query = f"name = '{clean_name}' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name, size)").execute()
    files = results.get('files', [])
    
    # Fallback to contains query if exact match not found
    if not files:
        query = f"name contains '{clean_name}' and trashed = false"
        results = service.files().list(q=query, fields="files(id, name, size)").execute()
        files = results.get('files', [])
        
    if not files:
        print(f"File '{clean_name}' not found in Google Drive.")
        return False
        
    file_id = files[0]['id']
    file_title = files[0]['name']
    print(f"Found on Drive: '{file_title}' (ID: {file_id}). Downloading...")
    
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    request = service.files().get_media(fileId=file_id)
    with open(output_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Downloading: {int(status.progress() * 100)}%")
                
    print(f"Successfully downloaded to: {output_path}")
    return True
