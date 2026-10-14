import json
import shutil
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(base_dir, 'scratch', 'curated_152_catalog.json')
dst1 = os.path.join(base_dir, 'affiliate_products.json')
dst2 = os.path.join(base_dir, 'products.json')

with open(src, 'r', encoding='utf-8') as f:
    products = json.load(f)

print(f"Catalog has {len(products)} products.")

# Write dst1 and dst2 with pretty formatting
with open(dst1, 'w', encoding='utf-8') as f:
    json.dump(products, f, indent=2, ensure_ascii=False)
print("Updated affiliate_products.json")

with open(dst2, 'w', encoding='utf-8') as f:
    json.dump(products, f, indent=2, ensure_ascii=False)
print("Updated products.json")
