import gspread
from google.oauth2.service_account import Credentials
import os
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

class Tracker:
    def __init__(self):
        # We assume the service account key is saved as service_account.json
        self.credentials_file = 'service_account.json'
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        self.client = None
        self.sheet = None
        
        self.authenticate()

    def authenticate(self):
        try:
            import json
            service_account_env = os.getenv('SERVICE_ACCOUNT_JSON')
            if service_account_env:
                creds_info = json.loads(service_account_env)
                credentials = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
            else:
                credentials = Credentials.from_service_account_file(
                    self.credentials_file, scopes=SCOPES
                )
            self.client = gspread.authorize(credentials)
            self.sheet = self.client.open_by_key(self.spreadsheet_id).sheet1
        except Exception as e:
            print(f"Error authenticating with Google Sheets: {e}")

    def get_all_records(self):
        if not self.sheet:
            return []
        return self.sheet.get_all_records()

    def update_status(self, video_no, new_status):
        if not self.sheet:
            return
        
        records = self.get_all_records()
        for i, record in enumerate(records):
            if str(record.get('Video No.')) == str(video_no):
                # +2 because gspread is 1-indexed and we have a header row
                row_index = i + 2
                self.sheet.update_cell(row_index, 8, new_status) # Assuming Status is column 8 (H)
                print(f"Updated Video No. {video_no} to {new_status}")
                return
        print(f"Video No. {video_no} not found.")

    def add_video(self, video_data):
        if not self.sheet:
            return
        
        # video_data should be a list matching the columns:
        # [Video No., File Name, Topic, Caption, Hashtags, Scheduled Date, Scheduled Time, Status]
        self.sheet.append_row(video_data)
        print(f"Added {video_data[1]} to tracker.")
