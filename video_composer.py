import os
import sys
import shutil
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont

def get_ffmpeg_path():
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def get_font(size, bold=False):
    candidates = [
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\calibrib.ttf" if bold else "C:\\Windows\\Fonts\\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()

def create_product_card_image(product, output_image_path):
    """
    Renders an eye-catching 1080x1920 (9:16) vertical motion card for Instagram Reels.
    Uses high-contrast gym typography, verified features, and prominent call to action.
    """
    width, height = 1080, 1920
    im = Image.new("RGB", (width, height), (15, 17, 23))
    draw = ImageDraw.Draw(im)

    # 1. Subtle warm ambient glow in top center
    for r in range(420, 0, -15):
        alpha = int(22 * (1 - r / 420))
        draw.ellipse([width//2 - r, 340 - r, width//2 + r, 340 + r], fill=(22 + alpha//2, 24 + alpha//2, 32))

    # 2. Category / Recommendation Badge (Top)
    badge_text = product.get("badge", "⚡ RECOMMENDED GEAR").upper()
    font_badge = get_font(34, bold=True)
    badge_w = draw.textlength(badge_text, font=font_badge)
    bx0 = (width - badge_w) // 2 - 30
    by0 = 230
    bx1 = bx0 + badge_w + 60
    by1 = by0 + 64
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=32, fill=(255, 107, 0), outline=(255, 160, 50), width=2)
    draw.text((bx0 + 30, by0 + 12), badge_text, fill=(255, 255, 255), font=font_badge)

    # 3. Central Feature Card Container
    cx0, cy0, cx1, cy1 = 80, 340, width - 80, 1500
    draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=40, fill=(26, 30, 42), outline=(45, 52, 72), width=3)

    # Category Subtitle
    font_cat = get_font(30, bold=True)
    category_text = f"★ {product.get('category', 'FITNESS EQUIPMENT').upper()} ★"
    cat_w = draw.textlength(category_text, font=font_cat)
    draw.text(((width - cat_w) // 2, cy0 + 45), category_text, fill=(255, 180, 0), font=font_cat)

    # Product Name (Auto-wrapped nicely)
    font_title = get_font(50, bold=True)
    name = product.get("name", "Featured Fitness Product")
    
    words = name.split()
    lines = []
    curr = []
    for w in words:
        test_line = " ".join(curr + [w])
        if draw.textlength(test_line, font=font_title) < (cx1 - cx0 - 80):
            curr.append(w)
        else:
            if curr:
                lines.append(" ".join(curr))
            curr = [w]
    if curr:
        lines.append(" ".join(curr))

    title_y = cy0 + 110
    for line in lines[:3]:
        lw = draw.textlength(line, font=font_title)
        draw.text(((width - lw) // 2, title_y), line, fill=(255, 255, 255), font=font_title)
        title_y += 66

    # Price / Delivery Pill
    price = product.get("price", "")
    if price:
        price_text = f"Verified Value: {price}  |  Amazon Prime Delivery"
        font_price = get_font(28, bold=False)
        pw = draw.textlength(price_text, font=font_price)
        draw.rounded_rectangle([(width - pw)//2 - 25, title_y + 15, (width + pw)//2 + 25, title_y + 65], radius=15, fill=(38, 44, 62))
        draw.text(((width - pw)//2, title_y + 24), price_text, fill=(200, 215, 240), font=font_price)
        title_y += 75

    # Divider line
    draw.line([cx0 + 50, title_y + 25, cx1 - 50, title_y + 25], fill=(45, 52, 72), width=2)
    features_y = title_y + 60

    # 4. Key Verified Features
    features = product.get("features", [])
    font_feat = get_font(32, bold=False)
    font_feat_title = get_font(34, bold=True)
    
    draw.text((cx0 + 60, features_y), "WHY IT WORKS:", fill=(255, 107, 0), font=font_feat_title)
    features_y += 60

    for feat in features[:3]:
        draw.rounded_rectangle([cx0 + 50, features_y, cx1 - 50, features_y + 88], radius=20, fill=(33, 38, 54), outline=(50, 58, 80), width=1)
        draw.text((cx0 + 75, features_y + 22), "✓", fill=(0, 220, 130), font=font_feat_title)
        draw.text((cx0 + 130, features_y + 24), feat, fill=(240, 244, 250), font=font_feat)
        features_y += 110

    # 5. Call To Action (Bottom Banner)
    cta_y0 = height - 340
    cta_y1 = cta_y0 + 160
    draw.rounded_rectangle([80, cta_y0, width - 80, cta_y1], radius=35, fill=(255, 107, 0), outline=(255, 160, 50), width=3)
    
    font_cta_main = get_font(42, bold=True)
    font_cta_sub = get_font(28, bold=False)
    
    cta_main = "🔗 TAP LINK IN BIO TO GRAB YOURS"
    cta_sub = "Prime Delivery  •  Official Amazon Affiliate Partner"
    
    mw = draw.textlength(cta_main, font=font_cta_main)
    sw = draw.textlength(cta_sub, font=font_cta_sub)
    
    draw.text(((width - mw)//2, cta_y0 + 35), cta_main, fill=(255, 255, 255), font=font_cta_main)
    draw.text(((width - sw)//2, cta_y0 + 95), cta_sub, fill=(255, 235, 210), font=font_cta_sub)

    # 6. Compliance / Affiliate Disclosure Text (Footer)
    font_disc = get_font(22, bold=False)
    disc_text = "As an Amazon Associate, I earn from qualifying purchases at no extra cost to you."
    dw = draw.textlength(disc_text, font=font_disc)
    draw.text(((width - dw)//2, height - 120), disc_text, fill=(130, 140, 160), font=font_disc)

    im.save(output_image_path, "PNG")
    return output_image_path

def create_product_segment_video(card_image_path, output_video_path, duration=5.5):
    """
    Renders the static card into a 1080x1920 30fps vertical video clip with
    smooth entrance/exit fade transitions and silent stereo audio.
    """
    ffmpeg = get_ffmpeg_path()
    fade_in = 0.4
    fade_out_st = max(1.0, duration - 0.4)
    
    vf = f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fade=t=in:st=0:d={fade_in},fade=t=out:st={fade_out_st}:d=0.4"
    
    cmd = [
        ffmpeg, "-y", "-nostdin",
        "-loop", "1", "-i", card_image_path,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2",
        "-t", str(duration), "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "128k",
        "-vf", vf,
        "-shortest",
        output_video_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    return output_video_path

def combine_gym_and_product(gym_video_path, product_segment_path, output_reel_path):
    """
    Standardizes the gym video to 1080x1920 30fps and stitches the product segment seamlessly.
    """
    ffmpeg = get_ffmpeg_path()
    temp_dir = tempfile.mkdtemp()
    
    try:
        standardized_gym = os.path.join(temp_dir, "gym_standard.mp4")
        concat_file = os.path.join(temp_dir, "concat_list.txt")

        # Step 1: Standardize gym video to 1080:1920, 30 fps, 44100Hz stereo AAC
        cmd_standardize = [
            ffmpeg, "-y", "-nostdin",
            "-i", gym_video_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            "-r", "30",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            standardized_gym
        ]
        subprocess.run(cmd_standardize, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)

        # Step 2: Concatenate standardized gym video + product segment
        with open(concat_file, "w") as f:
            f.write(f"file '{standardized_gym}'\n")
            f.write(f"file '{product_segment_path}'\n")

        cmd_concat = [
            ffmpeg, "-y", "-nostdin",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c", "copy",
            output_reel_path
        ]
        subprocess.run(cmd_concat, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        return output_reel_path

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

def prepare_composite_reel(gym_video_path, product, output_dir=None):
    """
    Master function:
    Takes gym video and matched product, builds the product segment, combines them,
    and returns (final_video_path, was_combined).
    If product is None or any step fails, gracefully returns (gym_video_path, False).
    """
    if not product or not os.path.exists(gym_video_path):
        return gym_video_path, False

    if not output_dir:
        output_dir = os.path.join("/tmp" if os.name != 'nt' else ".", "temp_videos")
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(gym_video_path))[0]
    final_output = os.path.join(output_dir, f"{base_name}_with_affiliate.mp4")
    card_img = os.path.join(output_dir, f"{base_name}_card.png")
    segment_video = os.path.join(output_dir, f"{base_name}_segment.mp4")

    try:
        print(f"[VideoComposer] Generating 9:16 product segment for '{product.get('name')}'...")
        create_product_card_image(product, card_img)
        create_product_segment_video(card_img, segment_video, duration=5.5)

        print(f"[VideoComposer] Combining gym video with product segment...")
        combine_gym_and_product(gym_video_path, segment_video, final_output)

        if os.path.exists(final_output) and os.path.getsize(final_output) > 100000:
            print(f"[VideoComposer] Composite Reel ready ({os.path.getsize(final_output)/(1024*1024):.2f} MB)")
            return final_output, True
        else:
            print(f"[VideoComposer] Composite file invalid, falling back to original video.")
            return gym_video_path, False

    except Exception as e:
        print(f"[VideoComposer] Error during video combination: {e}. Falling back to original video.")
        return gym_video_path, False
    finally:
        for temp_f in [card_img, segment_video]:
            if os.path.exists(temp_f):
                try:
                    os.remove(temp_f)
                except Exception:
                    pass
