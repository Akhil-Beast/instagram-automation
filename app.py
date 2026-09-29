import os
import sys
import threading
import time
import datetime
import json
from flask import Flask, jsonify, request, render_template, send_from_directory
from dotenv import load_dotenv
import schedule
from tracker import Tracker
from publisher import Publisher
from drive_downloader import download_video_from_drive
from affiliate_manager import AffiliateManager
from video_composer import prepare_composite_reel

load_dotenv()

# Ensure UTF-8 output
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
VIDEO_FOLDER = "GYM Boys Motivation Reels"

def check_and_publish_post(force=False, target_video_no=None):
    """
    Finds the scheduled video for the active time window (or specific video_no / next pending if force=True),
    matches an Amazon affiliate product, composes a product card Reel, and publishes to Instagram.
    """
    # Explicitly calculate India Standard Time (IST = UTC + 5:30)
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now = utc_now.astimezone(ist_tz)
    today_str = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    
    target_time = None
    if 8 <= current_hour < 12:
        target_time = "09:00 AM"
    elif 21 <= current_hour <= 23 or current_hour == 0:
        target_time = "11:00 PM"
        
    print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S IST')}] Triggering schedule check... Target slot: {target_time} (Force: {force}, Target Video: {target_video_no})")
    
    tracker = Tracker()
    publisher = Publisher()
    records = tracker.get_all_records()
    
    target_record = None
    
    def is_pending(rec):
        s = str(rec.get('Status', '')).strip().lower()
        return s not in ('posted', 'published')

    # 1. Target specific video number if explicitly passed
    if target_video_no is not None:
        for record in records:
            if str(record.get('Video No.')).strip() == str(target_video_no).strip():
                target_record = record
                print(f"Explicitly targeting Video No. {target_video_no}")
                break
                
    # 2. Force post next pending scheduled video
    elif force:
        for record in records:
            if is_pending(record):
                target_record = record
                print(f"Force mode: selecting first unposted Video No. {record.get('Video No.')}")
                break
                
    # 3. Regular scheduled run
    else:
        # First priority: Look for post specifically scheduled for this slot (today + target_time)
        if target_time:
            for record in records:
                if is_pending(record) and record.get('Scheduled Date') == today_str and record.get('Scheduled Time') == target_time:
                    target_record = record
                    print(f"Found scheduled post for current slot ({today_str} {target_time}): Video No. {record.get('Video No.')}")
                    break
        
        # Second priority: If no exact slot match, check if there is an overdue scheduled post (Scheduled Date + Time <= now)
        if not target_record:
            for record in records:
                if is_pending(record):
                    rec_date = str(record.get('Scheduled Date', '')).strip()
                    rec_time = str(record.get('Scheduled Time', '')).strip()
                    try:
                        rec_dt_str = f"{rec_date} {rec_time}"
                        rec_dt = datetime.datetime.strptime(rec_dt_str, "%Y-%m-%d %I:%M %p").replace(tzinfo=ist_tz)
                        if rec_dt <= now:
                            target_record = record
                            print(f"Recovering overdue scheduled post: Video No. {record.get('Video No.')} ({rec_dt_str})")
                            break
                    except Exception:
                        pass
                 
    if not target_record:
        msg = f"No pending scheduled posts found to publish at this time."
        print(msg)
        return {"success": False, "message": msg}
        
    video_no = target_record.get('Video No.')
    file_name = str(target_record.get('File Name', '')).strip()
    caption = str(target_record.get('Caption', ''))
    hashtags = str(target_record.get('Hashtags', ''))
    topic = str(target_record.get('Topic', ''))
    
    print(f"Processing Video No. {video_no}: {file_name} (Topic: '{topic}')")
    
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
            tracker.update_row_fields(video_no, {"Status": "Failed (Video Not Found)", "Error": "Drive download failed"})
            return {"success": False, "message": f"Video '{file_name}' not found locally or on Google Drive."}
        temp_downloaded = True

    # 3. Intelligent Amazon Affiliate Product Selection & Video Composition
    affiliate_mgr = AffiliateManager()
    
    # Check if a product is already designated in the Google Sheet
    sheet_asin = str(target_record.get('Product ASIN', '')).strip()
    matched_product = None
    if sheet_asin:
        for p in affiliate_mgr.products:
            if p.get('asin') == sheet_asin:
                matched_product = dict(p)
                matched_product['affiliate_url'] = affiliate_mgr.get_affiliate_url(matched_product)
                print(f"Using pre-assigned product from Google Sheet: {matched_product.get('name')} (ASIN: {sheet_asin})")
                break
                
    if not matched_product:
        recent_products = tracker.get_recent_promoted_products(limit=5)
        matched_product = affiliate_mgr.select_product(
            topic=topic,
            caption=caption,
            recent_product_ids=recent_products
        )

    publish_path = local_path
    final_caption = f"{caption}\n.\n.\n{hashtags}"
    composite_video_path = None

    if matched_product:
        print(f"Matched product: {matched_product.get('name')} (ASIN: {matched_product.get('asin')})")
        tracker.update_row_fields(video_no, {
            "Status": "Product Selected",
            "Product Name": matched_product.get("name", ""),
            "Product ASIN": matched_product.get("asin", ""),
            "Product Category": matched_product.get("category", ""),
            "Product Price": matched_product.get("price", ""),
            "Amazon URL": matched_product.get("amazon_url", ""),
            "Affiliate URL": matched_product.get("affiliate_url", "")
        })

        print("Generating composite Reel with product motion card...")
        temp_out_dir = os.path.dirname(local_path)
        comp_path, was_combined = prepare_composite_reel(local_path, matched_product, output_dir=temp_out_dir)
        
        if was_combined:
            composite_video_path = comp_path
            publish_path = comp_path
            tracker.update_status(video_no, "Video Combined")
            final_caption = affiliate_mgr.generate_affiliate_caption(caption, matched_product, hashtags)
            print("Successfully combined gym video with affiliate product card!")
        else:
            print("Video combination skipped or timed out. Falling back cleanly to original gym video.")
            final_caption = affiliate_mgr.generate_affiliate_caption(caption, matched_product, hashtags)
    else:
        print("No high-relevance affiliate product found for this video. Publishing original gym video.")

    # 4. Direct Upload & Publication to Instagram Reels
    try:
        print(f"Publishing Video No. {video_no} to Instagram...")
        result = publisher.publish_video(publish_path, final_caption)
        if result.get("success"):
            post_id = result.get("post_id", "")
            permalink = result.get("permalink", "")
            tracker.update_row_fields(video_no, {
                "Status": "Published",
                "Instagram Reel ID": post_id,
                "Instagram URL": permalink,
                "Error": ""
            })

            # Dynamically sync newly published Reel to the website storefront catalog
            if matched_product and permalink:
                try:
                    catalog_path = os.path.join(os.path.dirname(__file__), 'affiliate_products.json')
                    if os.path.exists(catalog_path):
                        with open(catalog_path, 'r', encoding='utf-8') as f:
                            all_prods = json.load(f)
                        updated_cat = False
                        for p in all_prods:
                            if p.get('asin') == matched_product.get('asin'):
                                if 'featured_reels' not in p:
                                    p['featured_reels'] = []
                                if not any(r.get('url') == permalink or r.get('reel_no') == video_no for r in p['featured_reels']):
                                    p['featured_reels'].insert(0, {
                                        'reel_no': video_no,
                                        'title': topic or f"Reel #{video_no}",
                                        'url': permalink
                                    })
                                    updated_cat = True
                                break
                        if updated_cat:
                            with open(catalog_path, 'w', encoding='utf-8') as f:
                                json.dump(all_prods, f, indent=2, ensure_ascii=False)
                            print(f"Dynamically added Reel #{video_no} to {matched_product.get('name')} on the storefront website!")

                            # Re-render static site files and push to GitHub/Vercel
                            def sync_website_async():
                                try:
                                    from jinja2 import Environment, FileSystemLoader
                                    import subprocess
                                    env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')))
                                    tmpl = env.get_template('store.html')
                                    rendered = tmpl.render(products=all_prods)
                                    for fname in ['index.html', 'store.html', 'shop.html']:
                                        fpath = os.path.join(os.path.dirname(__file__), fname)
                                        with open(fpath, 'w', encoding='utf-8') as sf:
                                            sf.write(rendered)
                                    print("Re-rendered static HTML files with latest Reel links.")
                                    subprocess.run(['git', 'add', 'affiliate_products.json', 'index.html', 'store.html', 'shop.html'], cwd=os.path.dirname(__file__), capture_output=True)
                                    subprocess.run(['git', 'commit', '-m', f"Auto-sync Reel #{video_no} to storefront website"], cwd=os.path.dirname(__file__), capture_output=True)
                                    subprocess.run(['git', 'push', 'origin', 'main'], cwd=os.path.dirname(__file__), capture_output=True)
                                    print("Pushed updated website to GitHub/Vercel.")
                                except Exception as err:
                                    print(f"Website auto-sync notice: {err}")
                            threading.Thread(target=sync_website_async, daemon=True).start()
                except Exception as sync_err:
                    print(f"Storefront sync error: {sync_err}")

            return {
                "success": True,
                "message": f"Successfully published Video No. {video_no} ({file_name}) to Instagram!",
                "permalink": permalink,
                "product": matched_product.get("name") if matched_product else "None"
            }
        else:
            err = result.get("error", "Publish failed")
            tracker.update_row_fields(video_no, {
                "Status": "Failed",
                "Error": err
            })
            return {"success": False, "message": f"Publishing failed for Video No. {video_no}: {err}"}
    finally:
        # Clean up temporary downloaded file to save disk space
        if temp_downloaded and os.path.exists(local_path):
            try:
                os.remove(local_path)
                print(f"Cleaned up temporary downloaded video: {local_path}")
            except Exception:
                pass
        # Clean up composite video file if created
        if composite_video_path and os.path.exists(composite_video_path):
            try:
                os.remove(composite_video_path)
                print(f"Cleaned up temporary composite video: {composite_video_path}")
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
    # If accessed by a browser, serve the storefront directly for the Instagram bio link
    if request.accept_mimetypes.accept_html and not request.accept_mimetypes.accept_json:
        return store()

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    ist_now = utc_now.astimezone(ist_tz)
    return jsonify({
        "status": "online",
        "service": "Instagram Automation Bot (Amazon Affiliate Integrated)",
        "account": "@gym147boy",
        "ist_time": ist_now.strftime("%Y-%m-%d %H:%M:%S IST"),
        "endpoints": {
            "/": "Official Storefront (Browser) or Health Status (API)",
            "/store": "Official Amazon Affiliate Storefront",
            "/shop": "Official Amazon Affiliate Storefront (Alias)",
            "/ping": "Lightweight 2-byte keep-alive ping (prevents Render from sleeping)",
            "/trigger-post": "Check schedule and post current or overdue slot",
            "/trigger-post?video_no=X": "Post specific video number immediately",
            "/trigger-post?force=true": "Force post the next scheduled video immediately"
        }
    })

@app.route('/store', methods=['GET'])
@app.route('/shop', methods=['GET'])
def store():
    """Serves the responsive official Amazon Affiliate storefront for @gym147boy bio"""
    try:
        catalog_path = os.path.join(os.path.dirname(__file__), 'affiliate_products.json')
        if os.path.exists(catalog_path):
            with open(catalog_path, 'r', encoding='utf-8') as f:
                products = json.load(f)
        else:
            products = []
        return render_template('store.html', products=products)
    except Exception as e:
        return f"Error loading storefront: {e}", 500

@app.route('/api/products', methods=['GET'])
def api_products():
    """Live JSON API returning all affiliate products, prices, and featured reels"""
    try:
        catalog_path = os.path.join(os.path.dirname(__file__), 'affiliate_products.json')
        if os.path.exists(catalog_path):
            with open(catalog_path, 'r', encoding='utf-8') as f:
                products = json.load(f)
        else:
            products = []
        resp = jsonify(products)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/favicon.ico')
@app.route('/favicon.svg')
@app.route('/apple-touch-icon.png')
@app.route('/icon-192.png')
@app.route('/icon-512.png')
@app.route('/icon.png')
def serve_brand_icons():
    filename = request.path.lstrip('/')
    return send_from_directory(os.path.dirname(__file__), filename)

@app.route('/ping', methods=['GET'])
def ping():
    """Ultra-lightweight keep-alive ping for cron-job.org to keep Render active 24/7"""
    return "OK", 200, {'Content-Type': 'text/plain'}

@app.route('/trigger-post', methods=['GET', 'POST'])
def trigger_post():
    try:
        force = request.args.get('force', 'false').lower() == 'true'
        video_no = request.args.get('video_no')
        
        # Run publishing in a background thread so the HTTP response returns immediately (<20ms)
        worker = threading.Thread(
            target=check_and_publish_post,
            kwargs={'force': force, 'target_video_no': video_no},
            daemon=True
        )
        worker.start()
        
        # Return tiny plain text "OK" so cron-job.org NEVER hits "Failed (output too large)"
        return "OK", 200, {'Content-Type': 'text/plain'}
    except Exception as e:
        return f"Error: {e}", 500, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
