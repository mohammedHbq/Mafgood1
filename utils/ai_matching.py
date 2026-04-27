"""
AIMatching — الوحدة المسؤولة عن مطابقة الأغراض المفقودة بالموجودة
تعكس الـ Class Diagram: AIMatching
"""
import os
import math
from typing import List, Optional


class AIMatching:
    """
    محرك المطابقة الذكي.
    يحسب التشابه النصي بين الأغراض ويُعيد قائمة بأفضل التطابقات.
    """

    model_version: str = "1.0.0"
    threshold: float = 0.40   # الحد الأدنى لنسبة التشابه

    # ── helpers ───────────────────────────────────────────────────────────
    @staticmethod
    def _tokenize(text: str) -> dict:
        """يحوّل النص إلى مجموعة كلمات مع أوزانها (TF بسيط)."""
        if not text:
            return {}
        words = text.lower().split()
        freq: dict = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        return freq

    @staticmethod
    def _cosine(v1: dict, v2: dict) -> float:
        """Cosine similarity بين متجهين (dicts)."""
        all_keys = set(v1) | set(v2)
        dot = sum(v1.get(k, 0) * v2.get(k, 0) for k in all_keys)
        mag1 = math.sqrt(sum(x ** 2 for x in v1.values()))
        mag2 = math.sqrt(sum(x ** 2 for x in v2.values()))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)

    # ── public API (matches the class diagram) ────────────────────────────
    def request_img_details(self, image_path: str) -> List[float]:
        """
        يُعيد 'vector' بسيط للصورة بناءً على اسم الملف.
        في الإنتاج استبدل هذا بنموذج CNN / CLIP حقيقي.
        """
        if not image_path or not os.path.exists(image_path):
            return []
        # Placeholder: vector من hash اسم الملف
        h = hash(os.path.basename(image_path))
        return [(h >> i & 0xFF) / 255.0 for i in range(8)]

    def compare_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        """Cosine similarity بين متجهي صور."""
        if not vector1 or not vector2:
            return 0.0
        length = min(len(vector1), len(vector2))
        dot  = sum(vector1[i] * vector2[i] for i in range(length))
        mag1 = math.sqrt(sum(x ** 2 for x in vector1[:length]))
        mag2 = math.sqrt(sum(x ** 2 for x in vector2[:length]))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)

    def compare_matches(self, target_item, item_list: list) -> list:
        """
        يُقارن غرضاً مفقوداً بقائمة من الأغراض الموجودة
        ويُعيد أفضل التطابقات مرتبةً تنازلياً.
        """
        results = []

        target_text = f"{target_item.item_name} {target_item.description or ''} {target_item.location or ''}"
        target_vec  = self._tokenize(target_text)

        for item in item_list:
            # تجاهل الغرض نفسه
            if item.id == target_item.id:
                continue

            # ── نص ──────────────────────────────────────────────────────
            item_text = f"{item.item_name} {item.description or ''} {item.location or ''}"
            item_vec  = self._tokenize(item_text)
            text_score = self._cosine(target_vec, item_vec)

            # ── صورة ─────────────────────────────────────────────────────
            img_score = 0.0
            if target_item.image_path and item.image_path:
                v1 = self.request_img_details(target_item.image_path)
                v2 = self.request_img_details(item.image_path)
                img_score = self.compare_similarity(v1, v2)

            # ── فئة ──────────────────────────────────────────────────────
            category_bonus = 0.2 if target_item.category == item.category else 0.0

            # ── الدرجة الكلية ─────────────────────────────────────────────
            final_score = (text_score * 0.6) + (img_score * 0.2) + category_bonus

            if final_score >= self.threshold:
                results.append({'item': item, 'score': round(final_score, 4)})

        results.sort(key=lambda x: x['score'], reverse=True)
        return results

    def run_matching_for_item(self, lost_item) -> list:
        """
        يبحث في قاعدة البيانات عن أفضل تطابق لغرض مفقود.
        يُخزّن النتائج في جدول Match.
        """
        from models.item import Item, ItemType, ItemStatus, Match
        from extensions import db

        found_items = Item.query.filter_by(item_type=ItemType.FOUND, status=ItemStatus.NOT_FOUND).all()
        matches = self.compare_matches(lost_item, found_items)

        saved = []
        for m in matches:
            match_record = Match(
                source_item_id=lost_item.id,
                matched_item_id=m['item'].id,
                similarity_score=m['score'],
            )
            db.session.add(match_record)
            saved.append(match_record)

        db.session.commit()
        return saved


# Singleton للاستخدام عبر التطبيق
ai_matcher = AIMatching()
