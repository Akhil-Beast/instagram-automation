import gspread
from google.oauth2.service_account import Credentials
import os
import sys

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def create_and_share_sheet():
    print("Authenticating with service_account.json...")
    try:
        credentials = Credentials.from_service_account_file('service_account.json', scopes=SCOPES)
        client = gspread.authorize(credentials)
    except Exception as e:
        print(f"Error authenticating: {e}")
        return

    if len(sys.argv) > 1 and sys.argv[1].strip():
        email = sys.argv[1].strip()
    else:
        email = input("\nEnter your personal Gmail address to share the sheet with you: ")
    
    print("\nCreating new Google Sheet 'Instagram Tracker'...")
    try:
        # Create a new spreadsheet
        spreadsheet = client.create('Instagram Tracker')
        
        # Share it with the user
        spreadsheet.share(email, perm_type='user', role='writer')
        print(f"Shared successfully with {email}!")
        
        # Setup headers
        sheet = spreadsheet.sheet1
        headers = ["Video No.", "File Name", "Topic", "Caption", "Hashtags", "Scheduled Date", "Scheduled Time", "Status"]
        sheet.update(range_name='A1:H1', values=[headers])
        print("Headers created successfully!")
        
        spreadsheet_id = spreadsheet.id
        print(f"\nYour new Spreadsheet ID is: {spreadsheet_id}")
        print(f"Link: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
        
        # Update .env file automatically
        env_file = '.env'
        lines = []
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                lines = f.readlines()
                
        with open(env_file, 'w') as f:
            updated = False
            for line in lines:
                if line.startswith('SPREADSHEET_ID='):
                    f.write(f"SPREADSHEET_ID={spreadsheet_id}\n")
                    updated = True
                else:
                    f.write(line)
            if not updated:
                f.write(f"\nSPREADSHEET_ID={spreadsheet_id}\n")
                
        print("\nSuccessfully updated .env file with the new SPREADSHEET_ID!")
        
    except Exception as e:
        print(f"Error creating sheet: {e}")

if __name__ == '__main__':
    create_and_share_sheet()
