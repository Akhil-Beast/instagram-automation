import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

class Publisher:
    def __init__(self):
        self.access_token = os.getenv("ACCESS_TOKEN")
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        self.graph_url = 'https://graph.facebook.com/v22.0'
        
    def publish_video(self, file_path, caption):
        """
        Publishes a local video file directly to Instagram Reels using Meta's resumable upload API.
        No public URL or external web server is needed.
        """
        if not self.access_token or not self.instagram_account_id:
            print("Missing Instagram API credentials.")
            return False
            
        if not os.path.exists(file_path):
            print(f"Error: Video file not found at {file_path}")
            return False

        file_size = os.path.getsize(file_path)
        print(f"Starting direct upload for: {file_path} ({file_size / (1024*1024):.2f} MB)")
        
        # 1. Initialize Resumable Media Container
        container_url = f"{self.graph_url}/{self.instagram_account_id}/media"
        init_payload = {
            'upload_type': 'resumable',
            'media_type': 'REELS',
            'caption': caption,
            'access_token': self.access_token
        }
        
        try:
            r = requests.post(container_url, data=init_payload)
            init_res = r.json()
            
            if 'id' not in init_res or 'uri' not in init_res:
                print(f"Error initializing upload session: {init_res}")
                return False
                
            creation_id = init_res['id']
            upload_uri = init_res['uri']
            print(f"Upload session initialized. Container ID: {creation_id}")
            
            # 2. Upload video binary data directly to Meta
            print("Uploading video bytes to Instagram...")
            headers = {
                'Authorization': f'OAuth {self.access_token}',
                'offset': '0',
                'file_size': str(file_size),
                'Content-Type': 'application/octet-stream'
            }
            
            with open(file_path, 'rb') as f:
                upload_res = requests.post(upload_uri, headers=headers, data=f, timeout=(30, 600))
                
            if upload_res.status_code not in (200, 201):
                print(f"Error uploading video data: {upload_res.status_code} - {upload_res.text}")
                return False
                
            print("Video data successfully uploaded. Waiting for Meta to finish processing...")
            
            # 3. Poll Status until Finished
            status_url = f"{self.graph_url}/{creation_id}?fields=status_code&access_token={self.access_token}"
            max_attempts = 30
            for attempt in range(max_attempts):
                time.sleep(10)
                status_res = requests.get(status_url).json()
                status_code = status_res.get('status_code')
                print(f"Processing status [{attempt + 1}/{max_attempts}]: {status_code}")
                
                if status_code == 'FINISHED':
                    break
                elif status_code == 'ERROR':
                    print(f"Processing failed on Meta servers: {status_res}")
                    return False
            else:
                print("Timed out waiting for video processing.")
                return False
                
            # 4. Publish the Reel
            publish_url = f"{self.graph_url}/{self.instagram_account_id}/media_publish"
            publish_payload = {
                'creation_id': creation_id,
                'access_token': self.access_token
            }
            
            pub_r = requests.post(publish_url, data=publish_payload)
            pub_result = pub_r.json()
            
            if 'id' in pub_result:
                print(f"Successfully published Reel! Post ID: {pub_result['id']}")
                return True
            else:
                print(f"Error publishing media: {pub_result}")
                return False
                
        except Exception as e:
            print(f"Exception during publishing: {e}")
            return False
