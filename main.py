import os
import sys
import time
import glob
import re
import datetime
import schedule
from dotenv import load_dotenv
from tracker import Tracker
from analyzer import Analyzer
from publisher import Publisher

load_dotenv()

# Ensure console supports UTF-8
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

VIDEO_FOLDER = "GYM Boys Motivation Reels"

def natural_sort_key(s):
    """Sort strings containing numbers in human order (e.g. 1, 2, 10 instead of 1, 10, 2)"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def analyze_and_schedule_all(batch_limit=None):
    """
    Scans the video folder, analyzes uncataloged videos with Gemini AI,
    and schedules them in Google Sheets (2 videos per day: 9:00 AM and 11:00 PM IST).
    """
    print("\n=======================================================")
    print("      ANALYZING CONTENT & POPULATING SCHEDULE          ")
    print("=======================================================")
    
    tracker = Tracker()
    analyzer = Analyzer()
    
    # Get list of all mp4 files
    all_files = glob.glob(os.path.join(VIDEO_FOLDER, "*.mp4"))
    all_files.sort(key=natural_sort_key)
    
    # Fetch existing records from Google Sheet
    records = tracker.get_all_records()
    existing_files = set(str(r.get('File Name', '')).strip() for r in records)
    
    print(f"Total videos in folder: {len(all_files)}")
    print(f"Already tracked in Google Sheet: {len(existing_files)}")
    
    unprocessed = [f for f in all_files if os.path.basename(f).strip() not in existing_files]
    print(f"Pending videos to analyze: {len(unprocessed)}")
    
    if not unprocessed:
        print("All videos are already analyzed and scheduled!")
        return

    # Determine starting video number and date
    video_no = len(records)
    today = datetime.date.today()
    
    processed_count = 0
    for file_path in unprocessed:
        if batch_limit and processed_count >= batch_limit:
            print(f"Batch limit reached ({batch_limit}). You can run analysis again anytime.")
            break
            
        file_name = os.path.basename(file_path).strip()
        file_size = os.path.getsize(file_path)
        
        # Check for corrupted or empty video
        if file_size < 10000:
            print(f"Skipping {file_name}: File is corrupted or too small ({file_size} bytes).")
            video_no += 1
            tracker.add_video([
                video_no, file_name, "Corrupted", "N/A", "N/A",
                today.strftime("%Y-%m-%d"), "N/A", "Skipped"
            ])
            continue
            
        video_no += 1
        processed_count += 1
        
        # Calculate schedule: 2 videos per day (9:00 AM and 11:00 PM)
        day_offset = (video_no - 1) // 2
        sched_date = today + datetime.timedelta(days=day_offset)
        sched_time = "09:00 AM" if (video_no % 2 != 0) else "11:00 PM"
        
        print(f"\n[{processed_count}/{len(unprocessed)}] Processing: {file_name} -> Scheduled: {sched_date} at {sched_time}")
        
        # Analyze with Gemini
        analysis = analyzer.analyze_video(file_path)
        
        topic = analysis.get('topic', 'Gym Motivation')
        caption = analysis.get('caption', 'Consistency is key. Push past your limits! 💪')
        hashtags = analysis.get('hashtags', '#gymmotivation #fitness #workout')
        
        # Append row to Google Sheets
        row_data = [
            video_no,
            file_name,
            topic,
            caption,
            hashtags,
            sched_date.strftime("%Y-%m-%d"),
            sched_time,
            "Scheduled"
        ]
        tracker.add_video(row_data)
        time.sleep(1)  # Brief pause between API calls

    print("\nBatch analysis complete! Check your Google Sheet to view the schedule.")

def check_and_publish():
    """
    Checks the Google Sheet for any post scheduled for today and the current time slot,
    and publishes it to Instagram Reels.
    """
    now = datetime.datetime.now()
    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{current_time_str}] Checking schedule for pending Instagram posts...")
    
    tracker = Tracker()
    publisher = Publisher()
    
    records = tracker.get_all_records()
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    current_hour = now.hour
    
    # Determine active slot:
    # 9 AM window (09:00 - 10:00)
    # 11 PM window (23:00 - 00:00)
    target_time = None
    if 9 <= current_hour < 11:
        target_time = "09:00 AM"
    elif 23 <= current_hour <= 23:
        target_time = "11:00 PM"
    
    if not target_time:
        print(f"Current hour is {current_hour}:00. Next posting window is at 09:00 AM or 11:00 PM.")
        return
        
    for record in records:
        if record.get('Scheduled Date') == today_str and record.get('Scheduled Time') == target_time:
            if record.get('Status') == 'Scheduled':
                video_file_name = record.get('File Name')
                video_no = record.get('Video No.')
                
                # Locate video in folder
                file_path = os.path.join(VIDEO_FOLDER, video_file_name)
                if not os.path.exists(file_path):
                    # Also check with possible whitespace
                    matches = glob.glob(os.path.join(VIDEO_FOLDER, f"*{video_file_name}*"))
                    if matches:
                        file_path = matches[0]
                    else:
                        print(f"Error: Video file not found on disk: {video_file_name}")
                        tracker.update_status(video_no, "Failed (File Not Found)")
                        continue
                        
                caption = str(record.get('Caption', ''))
                hashtags = str(record.get('Hashtags', ''))
                full_caption = f"{caption}\n.\n.\n{hashtags}"
                
                print(f"\n=======================================================")
                print(f"Publishing Video No. {video_no}: {video_file_name}")
                print(f"Target slot: {today_str} {target_time}")
                print(f"Caption:\n{full_caption}")
                print(f"=======================================================")
                
                success = publisher.publish_video(file_path, full_caption)
                if success:
                    tracker.update_status(video_no, "Posted")
                    print(f"Video No. {video_no} successfully posted to Instagram!")
                else:
                    tracker.update_status(video_no, "Failed")
                    print(f"Video No. {video_no} failed to post.")
                return

    print(f"No pending posts found for {today_str} {target_time}.")

def run_scheduler():
    """Starts the continuous background scheduler"""
    print("\n=======================================================")
    print("      INSTAGRAM AUTO-POSTER DAEMON ACTIVE              ")
    print("      Schedule: 09:00 AM & 11:00 PM IST Every Day     ")
    print("=======================================================")
    
    # Schedule runs exactly at 9:00 AM and 11:00 PM
    schedule.every().day.at("09:00").do(check_and_publish)
    schedule.every().day.at("23:00").do(check_and_publish)
    
    # Also perform a check at launch in case it's currently 9 AM or 11 PM
    check_and_publish()
    
    print("\nScheduler is actively running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--analyze":
        # Run analysis (optional limit, e.g. python main.py --analyze 10)
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        analyze_and_schedule_all(batch_limit=limit)
    elif len(sys.argv) > 1 and sys.argv[1] == "--post-now":
        # Immediate manual trigger for test post
        check_and_publish()
    else:
        # Default behavior: Prompt or run
        print("Instagram Automation System")
        print("1. Run 'python main.py --analyze' to analyze videos and fill Google Sheet.")
        print("2. Run 'python main.py' to start the automatic 9 AM & 11 PM posting schedule.")
        run_scheduler()
