import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "affiliate_products.json")

class AffiliateManager:
    def __init__(self, catalog_path=CATALOG_PATH):
        self.associate_tag = os.getenv("AMAZON_ASSOCIATE_TAG", "akhilfinds01-21")
        self.marketplace = os.getenv("AMAZON_MARKETPLACE", "amazon.in")
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
        """Generates compliant Amazon Associates tracking link for the active marketplace"""
        base_url = product.get("amazon_url", "").strip()
        if not base_url:
            asin = product.get("asin", "")
            if asin:
                base_url = f"https://www.{self.marketplace}/dp/{asin}"
            else:
                return ""
        # Ensure marketplace consistency if configured
        if self.marketplace and "amazon." in base_url:
            base_url = re.sub(r'https?://(?:www\.)?amazon\.[a-z.]+', f'https://www.{self.marketplace}', base_url)
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

            # Priority boost for Gym Whey Protein & Organic Moringa Powder
            if product.get("priority"):
                score += product.get("priority_bonus", 8.0)

            # Apply rotation penalty if recently used
            if prod_id in recent_product_ids:
                recency_index = recent_product_ids.index(prod_id)
                # Stronger penalty if promoted very recently (e.g. within last 3 posts)
                penalty = max(2.0, 7.0 - recency_index)
                score -= penalty

            if score > best_score:
                best_score = score
                best_product = product

        # If score is low or generic topic, rotate prioritized health/gym powders first
        if best_score < 5.0 or not best_product:
            priority_prods = [p for p in self.products if p.get("priority")]
            for p in priority_prods:
                if p.get("id") not in recent_product_ids:
                    best_product = p
                    break
            if not best_product:
                for fallback_prod in self.products:
                    if fallback_prod.get("id") not in recent_product_ids:
                        best_product = fallback_prod
                        break
            if not best_product:
                best_product = self.products[0]
            print(f"Using prioritized gym/moringa powder staple for topic '{topic}': '{best_product['name']}'")

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
        # Clean existing affiliate section if caption already contains one
        clean_caption = original_caption.split("⚡ Level Up Your Training:")[0].strip()
        clean_caption = clean_caption.split("📌 Disclosure:")[0].strip()
        if hashtags and hashtags.strip() in clean_caption:
            clean_caption = clean_caption.replace(hashtags.strip(), "").strip()
        clean_caption = re.sub(r'(\n\s*\.\s*)+\n*$', '', clean_caption).strip()

        if not product:
            return f"{clean_caption}\n.\n.\n{hashtags}".strip()

        prod_name = product.get("name", "")
        cta = product.get("cta", "Tap the link in bio to upgrade your gym setup! 🔗")
        category = product.get("category", "Workout Gear")
        features = product.get("features", [])
        store_url = os.getenv("STORE_URL", "https://gym147boy-store.vercel.app")
        
        feature_str = f" ({features[0]})" if features else ""

        affiliate_section = (
            f"\n\n⚡ Level Up Your Training:\n"
            f"Equip yourself with the {prod_name}{feature_str}.\n"
            f"{cta}\n"
            f"👉 Official Store in Bio: {store_url}\n\n"
            f"📌 Disclosure: As an Amazon Associate, I earn from qualifying purchases at no extra cost to you."
        )

        full_caption = f"{clean_caption}{affiliate_section}\n.\n.\n{hashtags}".strip()
        return full_caption
