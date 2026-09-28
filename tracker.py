import gspread
from google.oauth2.service_account import Credentials
import os
import json
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

TRACKER_COLUMNS = [
    'Video No.',
    'File Name',
    'Topic',
    'Caption',
    'Hashtags',
    'Scheduled Date',
    'Scheduled Time',
    'Status',
    'Product Name',
    'Product ASIN',
    'Product Category',
    'Product Price',
    'Amazon URL',
    'Affiliate URL',
    'Instagram Reel ID',
    'Instagram URL',
    'Error'
]

class Tracker:
    def __init__(self):
        self.credentials_file = 'service_account.json'
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        self.client = None
        self.sheet = None
        self.header_indices = {}
        
        self.authenticate()
        if self.sheet:
            self._ensure_and_map_headers()

    def authenticate(self):
        try:
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

    def _ensure_and_map_headers(self):
        """Ensures all necessary affiliate and status tracking headers exist and builds column index map."""
        try:
            current_headers = self.sheet.row_values(1)
            updated = False
            for col in TRACKER_COLUMNS:
                if col not in current_headers:
                    current_headers.append(col)
                    updated = True
            
            if updated:
                # Update row 1 with expanded headers
                end_col_a1 = gspread.utils.rowcol_to_a1(1, len(current_headers))
                self.sheet.update(range_name=f"A1:{end_col_a1}", values=[current_headers])
                print(f"[Tracker] Headers updated to include affiliate columns: {current_headers}")
            
            self.header_indices = {name: idx + 1 for idx, name in enumerate(current_headers)}
        except Exception as e:
            print(f"[Tracker] Error initializing headers: {e}")

    def get_all_records(self):
        if not self.sheet:
            return []
        try:
            return self.sheet.get_all_records()
        except Exception as e:
            print(f"[Tracker] Error getting records: {e}")
            return []

    def update_row_fields(self, video_no, fields_dict):
        """
        Updates multiple columns for a given Video No. in a single API call.
        fields_dict: e.g. {'Status': 'Published', 'Product Name': '...', 'Instagram Reel ID': '...'}
        """
        if not self.sheet:
            return False
            
        try:
            if not self.header_indices:
                current_headers = self.sheet.row_values(1)
                self.header_indices = {name: idx + 1 for idx, name in enumerate(current_headers)}
                
            records = self.get_all_records()
            for i, record in enumerate(records):
                if str(record.get('Video No.')).strip() == str(video_no).strip():
                    row_index = i + 2  # row 1 is header, 1-indexed
                    cells_to_update = []
                    for field_name, value in fields_dict.items():
                        col_index = self.header_indices.get(field_name)
                        if col_index:
                            val_str = "" if value is None else str(value)
                            cells_to_update.append(gspread.Cell(row=row_index, col=col_index, value=val_str))
                    
                    if cells_to_update:
                        self.sheet.update_cells(cells_to_update)
                        print(f"[Tracker] Updated Video No. {video_no}: {list(fields_dict.keys())}")
                    return True
                    
            print(f"[Tracker] Video No. {video_no} not found.")
            return False
        except Exception as e:
            print(f"[Tracker] Error updating row for Video No. {video_no}: {e}")
            return False

    def update_status(self, video_no, new_status):
        return self.update_row_fields(video_no, {'Status': new_status})

    def get_recent_promoted_products(self, limit=5):
        """
        Returns list of product IDs / ASINs that were recently promoted
        so the affiliate manager can avoid repetitive recommendations.
        """
        if not self.sheet:
            return []
        try:
            records = self.get_all_records()
            recent_ids = []
            for r in reversed(records):
                status = str(r.get('Status', '')).strip().lower()
                asin = str(r.get('Product ASIN', '')).strip()
                p_name = str(r.get('Product Name', '')).strip()
                if status in ('posted', 'published') and (asin or p_name):
                    target_id = asin if asin else p_name
                    if target_id not in recent_ids:
                        recent_ids.append(target_id)
                if len(recent_ids) >= limit:
                    break
            return recent_ids
        except Exception as e:
            print(f"[Tracker] Error getting recent promoted products: {e}")
            return []

    def add_video(self, video_data):
        if not self.sheet:
            return
        self.sheet.append_row(video_data)
        print(f"Added {video_data[1]} to tracker.")

