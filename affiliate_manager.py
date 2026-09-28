import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "affiliate_products.json")

class AffiliateManager:
    def __init__(self, catalog_path=CATALOG_PATH):
        self.associate_tag = os.getenv("AMAZON_ASSOCIATE_TAG", "gym147boy-21")
        self.catalog_path = catalog_path
        self.products = self._load_catalog()

    def _load_catalog(self):
        if not os.path.exists(self.catalog_path):
            print(f"Warning: Affiliate catalog not found at {self.catalog_path}")
            return []
        try:
            with open(self.catalog_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading affiliate catalog: {e}")
            return []

    def get_affiliate_url(self, product):
        """Generates compliant Amazon Associates tracking link"""
        base_url = product.get("amazon_url", "").strip()
        if not base_url:
            return ""
        sep = "&" if "?" in base_url else "?"
        return f"{base_url}{sep}tag={self.associate_tag}"

    def select_product(self, topic="", caption="", recent_product_ids=None):
        """
        Intelligently matches a relevant fitness product based on topic and caption keywords.
        Penalizes recently promoted products to maintain rotation diversity.
        Returns None if no relevant match is found.
        """
        if not self.products:
            return None

        if recent_product_ids is None:
            recent_product_ids = []

        combined_text = f"{topic} {caption}".lower()
        # Clean non-alphanumeric
        tokens = set(re.findall(r'\b[a-z]{3,}\b', combined_text))

        best_product = None
        best_score = 0.0

        for product in self.products:
            prod_id = product.get("id")
            score = 0.0

            # Match against keywords (whole word or phrase)
            keywords = product.get("keywords", [])
            for kw in keywords:
                kw_lower = kw.lower()
                if " " in kw_lower:
                    if kw_lower in combined_text:
                        score += 3.0
                elif kw_lower in tokens:
                    score += 3.0

            # Match against product name terms
            name_tokens = set(re.findall(r'\b[a-z]{3,}\b', product.get("name", "").lower()))
            overlap = tokens.intersection(name_tokens)
            score += len(overlap) * 1.5

            # Apply rotation penalty if recently used
            if prod_id in recent_product_ids:
                recency_index = recent_product_ids.index(prod_id)
                # Stronger penalty if promoted very recently (e.g. within last 3 posts)
                penalty = max(1.0, 6.0 - recency_index)
                score -= penalty

            if score > best_score:
                best_score = score
                best_product = product

        # Minimum relevance threshold: avoid forcing irrelevant products
        # If score is too low, we return None (publish pure gym video without product)
        if best_score < 2.5:
            print(f"No sufficiently relevant product found for topic '{topic}' (score: {best_score:.1f}). Skipping product insertion.")
            return None

        # Return deep copy with generated affiliate link
        selected = dict(best_product)
        selected["affiliate_url"] = self.get_affiliate_url(selected)
        print(f"Selected relevant product: '{selected['name']}' (Score: {best_score:.1f})")
        return selected

    def generate_affiliate_caption(self, original_caption, product, hashtags=""):
        """
        Generates an authentic, high-converting caption combining the workout advice,
        a natural product recommendation, call to action, and mandatory affiliate disclosure.
        """
        if not product:
            return f"{original_caption}\n.\n.\n{hashtags}".strip()

        prod_name = product.get("name", "")
        cta = product.get("cta", "Link in bio to check it out! 🔗")
        category = product.get("category", "Workout Gear")
        features = product.get("features", [])
        
        feature_str = f" ({features[0]})" if features else ""

        affiliate_section = (
            f"\n\n⚡ Level Up Your Training:\n"
            f"Equip yourself with the {prod_name}{feature_str}. {cta}\n\n"
            f"📌 Disclosure: Some links may be affiliate links. As an Amazon Associate, I earn from qualifying purchases at no extra cost to you."
        )

        full_caption = f"{original_caption}{affiliate_section}\n.\n.\n{hashtags}".strip()
        return full_caption
