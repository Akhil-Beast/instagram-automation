import os
import sys
import json
import re
from collections import Counter, defaultdict

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

from tracker import Tracker
from affiliate_manager import AffiliateManager

def detect_strong_gear_match(topic, caption):
    combined = f"{topic} {caption}".lower()
    
    # Specific gear cues
    if any(k in combined for k in ["forearm", "wrist roller", "plate pinch", "grip strength", "crush grip", "zottman"]):
        return "hand_grip_strengthener", 15.0
        
    if any(k in combined for k in ["preacher bench", "preacher curl", "spider curl", "arm blaster", "strict curl", "bicep peak"]):
        return "arm_blaster_bicep_isolator", 15.0
        
    if any(k in combined for k in ["deadlift", "rack pull", "heavy shrug", "pendlay", "barbell row", "rdl"]):
        return "lifting_straps_heavy_duty", 14.0
        
    if any(k in combined for k in ["heavy squat", "back squat", "hack squat", "front squat"]):
        return "knee_sleeves_7mm", 14.0
        
    if any(k in combined for k in ["bench press", "incline barbell", "overhead press", "military press", "heavy lockout"]):
        return "wrist_wraps_heavy_duty", 13.0
        
    if any(k in combined for k in ["rotator cuff", "warmup", "resistance band", "banded", "mobility"]):
        return "resistance_bands_loop_set", 13.0

    return None, 0.0

def score_video_for_gear(product, topic, caption):
    combined = f"{topic} {caption}".lower()
    tokens = set(re.findall(r'\b[a-z]{3,}\b', combined))
    score = 0.0
    
    for kw in product.get("keywords", []):
        kw_lower = kw.lower()
        if " " in kw_lower:
            if kw_lower in combined:
                score += 4.0
        elif kw_lower in tokens:
            score += 3.0
            
    name_tokens = set(re.findall(r'\b[a-z]{3,}\b', product.get("name", "").lower()))
    overlap = tokens.intersection(name_tokens)
    score += len(overlap) * 1.5
    
    return score

def main():
    print("=================================================================")
    print("  UPDATING GOOGLE SHEET SCHEDULE WITH PRIORITY GYM & MORINGA POWDER")
    print("=================================================================")
    
    t = Tracker()
    am = AffiliateManager()
    
    prod_map = {p['id']: p for p in am.products}
    gear_prods = [p for p in am.products if not p.get('priority')]
    
    all_values = t.sheet.get_all_values()
    headers = all_values[0]
    print(f"Total rows in sheet (including header): {len(all_values)}")
    print(f"Headers: {headers}")
    
    h_map = {h: idx for idx, h in enumerate(headers)}
    
    # Rows 39 to 198 correspond to Video 38 to 197 (0-indexed lines 38 to 197)
    future_row_indices = list(range(38, len(all_values)))
    print(f"Number of future rows to update: {len(future_row_indices)} (Row 39 to Row {len(all_values)})")
    
    # Group by Scheduled Date
    by_date = defaultdict(list)
    for row_idx in future_row_indices:
        row_vals = all_values[row_idx]
        v_no = row_vals[h_map['Video No.']]
        d = row_vals[h_map['Scheduled Date']]
        by_date[d].append((row_idx, v_no, row_vals))
        
    print(f"Unique scheduled days: {len(by_date)}")
    
    assignments = {} # row_idx -> matched_product
    recent_gear_ids = []
    
    # Priority rotation: alternate Gym Whey Protein and Organic Moringa Powder across days
    priority_rotation = ['gym_whey_protein_powder', 'organic_moringa_powder']
    
    for day_idx, (d, items) in enumerate(by_date.items()):
        daily_priority_prod_id = priority_rotation[day_idx % 2]
        other_priority_prod_id = priority_rotation[(day_idx + 1) % 2]
        
        if len(items) == 1:
            row_idx, v_no, r = items[0]
            # Tonight: Video 38
            assignments[row_idx] = prod_map[daily_priority_prod_id]
            continue
            
        (r1_idx, v1_no, r1), (r2_idx, v2_no, r2) = items[0], items[1]
        
        t1, c1 = r1[h_map['Topic']], r1[h_map['Caption']]
        t2, c2 = r2[h_map['Topic']], r2[h_map['Caption']]
        
        gear1_id, strong1 = detect_strong_gear_match(t1, c1)
        gear2_id, strong2 = detect_strong_gear_match(t2, c2)
        
        if strong1 > 0 and strong2 == 0:
            assignments[r1_idx] = prod_map[gear1_id]
            assignments[r2_idx] = prod_map[daily_priority_prod_id]
            recent_gear_ids.insert(0, gear1_id)
        elif strong2 > 0 and strong1 == 0:
            assignments[r1_idx] = prod_map[daily_priority_prod_id]
            assignments[r2_idx] = prod_map[gear2_id]
            recent_gear_ids.insert(0, gear2_id)
        elif strong1 > 0 and strong2 > 0:
            if strong1 >= strong2:
                assignments[r1_idx] = prod_map[gear1_id]
                assignments[r2_idx] = prod_map[daily_priority_prod_id]
                recent_gear_ids.insert(0, gear1_id)
            else:
                assignments[r1_idx] = prod_map[daily_priority_prod_id]
                assignments[r2_idx] = prod_map[gear2_id]
                recent_gear_ids.insert(0, gear2_id)
        else:
            def get_best_gear(top, cap):
                best_p = None
                best_s = -1.0
                for gp in gear_prods:
                    s = score_video_for_gear(gp, top, cap)
                    if gp['id'] in recent_gear_ids:
                        rec_idx = recent_gear_ids.index(gp['id'])
                        s -= max(2.0, 6.0 - rec_idx)
                    if s > best_s:
                        best_s = s
                        best_p = gp
                return best_p, best_s

            p_gear1, s_gear1 = get_best_gear(t1, c1)
            p_gear2, s_gear2 = get_best_gear(t2, c2)
            
            if s_gear1 >= s_gear2:
                assignments[r1_idx] = p_gear1
                assignments[r2_idx] = prod_map[daily_priority_prod_id]
                recent_gear_ids.insert(0, p_gear1['id'])
            else:
                assignments[r1_idx] = prod_map[daily_priority_prod_id]
                assignments[r2_idx] = p_gear2
                recent_gear_ids.insert(0, p_gear2['id'])

        recent_gear_ids = recent_gear_ids[:6]

    # Prepare updated rows for batch writing
    updated_rows = []
    for row_idx in future_row_indices:
        row_vals = list(all_values[row_idx])
        prod = assignments[row_idx]
        
        # Ensure affiliate URL is populated
        aff_url = am.get_affiliate_url(prod)
        
        # Generate new clean caption
        orig_caption = row_vals[h_map['Caption']]
        hashtags = row_vals[h_map['Hashtags']]
        new_caption = am.generate_affiliate_caption(orig_caption, prod, hashtags)
        
        # Update columns
        row_vals[h_map['Product Name']] = prod.get('name', '')
        row_vals[h_map['Product ASIN']] = prod.get('asin', '')
        row_vals[h_map['Product Category']] = prod.get('category', '')
        row_vals[h_map['Product Price']] = prod.get('price', '')
        row_vals[h_map['Amazon URL']] = prod.get('amazon_url', '')
        row_vals[h_map['Affiliate URL']] = aff_url
        row_vals[h_map['Caption']] = new_caption
        
        updated_rows.append(row_vals)
        
    start_row = 39 # 1-indexed sheet row for Video 38
    end_row = 38 + len(updated_rows) # 198
    range_name = f"A{start_row}:Q{end_row}"
    
    print(f"\nBatch updating Google Sheet range: {range_name} ({len(updated_rows)} rows)...")
    success = t.batch_update_range(range_name, updated_rows)
    
    if success:
        print("Successfully updated Google Sheet in a single batch operation!")
    else:
        print("Error during batch update. Please verify credentials and connectivity.")
        return

    # Print summary statistics
    assigned_names = [assignments[r]['name'] for r in future_row_indices]
    counts = Counter(assigned_names)
    print("\n--- Final Product Distribution across Scheduled Posts ---")
    for name, cnt in counts.most_common():
        print(f"  {cnt:3d} posts -> {name}")
        
    print("\n--- Verification: First 5 Updated Videos ---")
    for r_idx in future_row_indices[:5]:
        v_no = all_values[r_idx][h_map['Video No.']]
        d = all_values[r_idx][h_map['Scheduled Date']]
        tm = all_values[r_idx][h_map['Scheduled Time']]
        top = all_values[r_idx][h_map['Topic']]
        p = assignments[r_idx]
        print(f"Video {v_no} ({d} {tm}) [{top}]:\n  -> {p['name']} ({p['price']}, ASIN: {p['asin']})")

if __name__ == '__main__':
    main()
