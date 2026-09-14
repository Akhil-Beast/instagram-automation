import os
import sys
import threading
import time
import datetime
from flask import Flask, jsonify, request
from dotenv import load_dotenv
import schedule
from tracker import Tracker
from publisher import Publisher
from drive_downloader import download_video_from_drive

load_dotenv()

# Ensure UTF-8 output
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
VIDEO_FOLDER = "GYM Boys Motivation Reels"

def check_and_publish_post(force=False):
    """
    Finds the scheduled video for the active time window (or next pending if force=True)
    and publishes it to Instagram.
    """
    # Explicitly calculate India Standard Time (IST = UTC + 5:30)
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now = utc_now.astimezone(ist_tz)
    today_str = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    
    target_time = None
    if 9 <= current_hour < 12:
        target_time = "09:00 AM"
    elif 22 <= current_hour <= 23 or current_hour == 0:
        target_time = "11:00 PM"
        
    print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] Triggering schedule check... Active slot: {target_time} (Force: {force})")
    
    tracker = Tracker()
    publisher = Publisher()
    records = tracker.get_all_records()
    
    target_record = None
    for record in records:
        if record.get('Status') == 'Scheduled':
            if force:
                target_record = record
                break
            if record.get('Scheduled Date') == today_str and record.get('Scheduled Time') == target_time:
                target_record = record
                break
                
    if not target_record:
        msg = f"No pending scheduled posts found for slot: {today_str} {target_time}"
        print(msg)
        return {"success": False, "message": msg}
        
    video_no = target_record.get('Video No.')
    file_name = str(target_record.get('File Name', '')).strip()
    caption = str(target_record.get('Caption', ''))
    hashtags = str(target_record.get('Hashtags', ''))
    full_caption = f"{caption}\n.\n.\n{hashtags}"
    
    print(f"Targeting Video No. {video_no}: {file_name}")
    
    # 1. Look for video locally
    local_path = os.path.join(VIDEO_FOLDER, file_name)
    temp_downloaded = False
    
    if not os.path.exists(local_path):
        # 2. Download from Google Drive if running in cloud
        cloud_temp_dir = os.path.join("/tmp" if os.name != 'nt' else ".", "temp_videos")
        os.makedirs(cloud_temp_dir, exist_ok=True)
        local_path = os.path.join(cloud_temp_dir, file_name)
        
        print(f"Local file not found. Attempting download from Google Drive...")
        downloaded = download_video_from_drive(file_name, local_path)
        if not downloaded:
            tracker.update_status(video_no, "Failed (Video Not Found)")
            return {"success": False, "message": f"Video '{file_name}' not found locally or on Google Drive."}
        temp_downloaded = True

    try:
        print(f"Publishing Video No. {video_no} to Instagram...")
        success = publisher.publish_video(local_path, full_caption)
        if success:
            tracker.update_status(video_no, "Posted")
            return {"success": True, "message": f"Successfully posted Video No. {video_no} ({file_name}) to Instagram!"}
        else:
            tracker.update_status(video_no, "Failed")
            return {"success": False, "message": f"Publishing failed for Video No. {video_no}."}
    finally:
        # Clean up temporary downloaded file to save disk space
        if temp_downloaded and os.path.exists(local_path):
            try:
                os.remove(local_path)
                print("Cleaned up temporary video file.")
            except Exception:
                pass

def background_scheduler_worker():
    """Background thread running schedule loop"""
    schedule.every().day.at("09:00").do(check_and_publish_post)
    schedule.every().day.at("23:00").do(check_and_publish_post)
    
    print("Background scheduler thread started. Listening for 09:00 AM and 11:00 PM IST.")
    while True:
        schedule.run_pending()
        time.sleep(30)

# Start background thread on launch
scheduler_thread = threading.Thread(target=background_scheduler_worker, daemon=True)
scheduler_thread.start()

@app.route('/', methods=['GET'])
def index():
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    ist_now = utc_now.astimezone(ist_tz)
    return jsonify({
        "status": "online",
        "service": "Instagram Automation Bot",
        "account": "@gym147boy",
        "ist_time": ist_now.strftime("%Y-%m-%d %H:%M:%S IST"),
        "endpoints": {
            "/": "Health check and status",
            "/trigger-post": "Check schedule and post current slot",
            "/trigger-post?force=true": "Force post the next scheduled video immediately"
        }
    })

@app.route('/trigger-post', methods=['GET', 'POST'])
def trigger_post():
    try:
        force = request.args.get('force', 'false').lower() == 'true'
        result = check_and_publish_post(force=force)
        return jsonify(result)
    except Exception as e:
        import traceback
        err_msg = str(e)
        tb = traceback.format_exc()
        print(f"Error in trigger_post: {err_msg}\n{tb}")
        return jsonify({
            "success": False,
            "error": err_msg,
            "traceback": tb
        }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
