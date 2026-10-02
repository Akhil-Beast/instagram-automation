import os
import json
from jinja2 import Environment, FileSystemLoader

base_dir = os.path.dirname(os.path.abspath(__file__))
catalog_path = os.path.join(base_dir, 'affiliate_products.json')

with open(catalog_path, 'r', encoding='utf-8') as f:
    products = json.load(f)

print(f"Loaded {len(products)} products with updated images.")

env = Environment(loader=FileSystemLoader(os.path.join(base_dir, 'templates')))
tmpl = env.get_template('store.html')
rendered = tmpl.render(products=products)

for fname in ['index.html', 'store.html', 'shop.html']:
    target_path = os.path.join(base_dir, fname)
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(rendered)
    print(f"Rendered {fname} ({len(rendered)} bytes).")

print("All static storefront files successfully re-rendered!")
