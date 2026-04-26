import os
import math
import json
from typing import List
 
# Pillow مدمجة في معظم بيئات Flask — لو مو موجودة: pip install pillow
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
 
 
# ── مساعدات الصورة ────────────────────────────────────────────────────────────
 
def _load_image(path: str, size=(16, 16)):
    if not PIL_AVAILABLE or not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert('RGB')
        img = img.resize(size, Image.LANCZOS)
        return img
    except Exception:
        return None
 
 
def _color_histogram(img, bins=8) -> List[float]:
    """histogram للألوان R,G,B — vector بطول bins*3."""
    if img is None:
        return []
    pixels = list(img.getdata())
    hist   = [0.0] * (bins * 3)
    step   = 256 // bins
    for r, g, b in pixels:
        hist[r // step]            += 1
        hist[bins + g // step]     += 1
        hist[bins * 2 + b // step] += 1
    total = len(pixels) * 3
    return [v / total for v in hist]
 
 
def _average_hash(img, hash_size=8) -> str:
    """Average Hash — بصمة الصورة، صور متشابهة = hash قريب."""
    if img is None:
        return ''
    small  = img.resize((hash_size, hash_size), Image.LANCZOS).convert('L')
    pixels = list(small.getdata())
    avg    = sum(pixels) / len(pixels)
    return ''.join('1' if p > avg else '0' for p in pixels)
 
 
def _hamming_distance(h1: str, h2: str) -> float:
    """مسافة هامينج بين hashين — 0 متطابق، 1 مختلف كلياً."""
    if not h1 or not h2 or len(h1) != len(h2):
        return 1.0
    return sum(c1 != c2 for c1, c2 in zip(h1, h2)) / len(h1)
 
 
def _dominant_colors(img, top=3) -> List[str]:
    """أبرز الألوان في الصورة كأسماء تقريبية."""
    if img is None:
        return []
    small      = img.resize((50, 50))
    pixels     = list(small.getdata())
    color_map  = {}
    for r, g, b in pixels:
        key = ((r // 64) * 64, (g // 64) * 64, (b // 64) * 64)
        color_map[key] = color_map.get(key, 0) + 1
 
    sorted_colors = sorted(color_map.items(), key=lambda x: x[1], reverse=True)
    names = []
    for (r, g, b), _ in sorted_colors[:top]:
        if r > 150 and g < 80  and b < 80:   names.append('red')
        elif r < 80  and g > 150 and b < 80:  names.append('green')
        elif r < 80  and g < 80  and b > 150: names.append('blue')
        elif r > 150 and g > 150 and b < 80:  names.append('yellow')
        elif r > 150 and g > 80  and b < 80:  names.append('orange')
        elif r > 80  and g < 80  and b > 150: names.append('purple')
        elif r > 150 and g > 150 and b > 150: names.append('white')
        elif r < 80  and g < 80  and b < 80:  names.append('black')
        else:                                  names.append('gray')
    return list(dict.fromkeys(names))
 
 
def _cosine_vec(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2:
        return 0.0
    length = min(len(v1), len(v2))
    dot    = sum(v1[i] * v2[i] for i in range(length))
    mag1   = math.sqrt(sum(x ** 2 for x in v1[:length]))
    mag2   = math.sqrt(sum(x ** 2 for x in v2[:length]))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)
 
 
def _analyze_image(path: str) -> dict:
    """تحليل كامل للصورة — hash + histogram + ألوان."""
    img = _load_image(path)
    return {
        'avg_hash':        _average_hash(img),
        'color_hist':      _color_histogram(img),
        'dominant_colors': _dominant_colors(img),
    }
 
 
def _compare_analyses(a1: dict, a2: dict) -> float:
    """
    يقارن تحليلين:
      Hash similarity   → 50%
      Color histogram   → 35%
      Dominant colors   → 15%
    """
    if not a1 or not a2:
        return 0.0
 
    hash_sim  = 1.0 - _hamming_distance(a1.get('avg_hash', ''), a2.get('avg_hash', ''))
    hist_sim  = _cosine_vec(a1.get('color_hist', []), a2.get('color_hist', []))
 
    c1, c2    = set(a1.get('dominant_colors', [])), set(a2.get('dominant_colors', []))
    color_sim = len(c1 & c2) / len(c1 | c2) if (c1 and c2) else 0.0
 
    return (hash_sim * 0.50) + (hist_sim * 0.35) + (color_sim * 0.15)
 
 
# ── الكلاس الرئيسي ────────────────────────────────────────────────────────────
 
class AIMatching:
 
    model_version: str = "2.0.0"
    threshold: float   = 0.40
 
    @staticmethod
    def _tokenize(text: str) -> dict:
        if not text:
            return {}
        freq: dict = {}
        for w in text.lower().split():
            freq[w] = freq.get(w, 0) + 1
        return freq
 
    @staticmethod
    def _cosine_text(v1: dict, v2: dict) -> float:
        all_keys = set(v1) | set(v2)
        dot  = sum(v1.get(k, 0) * v2.get(k, 0) for k in all_keys)
        mag1 = math.sqrt(sum(x ** 2 for x in v1.values()))
        mag2 = math.sqrt(sum(x ** 2 for x in v2.values()))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)
 
    # ── image API ─────────────────────────────────────────────────────────
 
    def request_img_details(self, image_path: str) -> dict:
        if not image_path or not os.path.exists(image_path):
            return {}
        return _analyze_image(image_path)
 
    def get_or_create_image_analysis(self, item) -> dict:
        """يجلب التحليل المحفوظ في DB أو يُنشئه ويحفظه."""
        if item.image_analysis:
            try:
                return json.loads(item.image_analysis)
            except Exception:
                pass
 
        if not item.image_path:
            return {}
 
        from flask import current_app
        full_path = os.path.join(current_app.root_path, 'static', item.image_path)
        analysis  = _analyze_image(full_path)
 
        if analysis:
            from extensions import db
            item.image_analysis = json.dumps(analysis, ensure_ascii=False)
            db.session.commit()
 
        return analysis
 
    def compare_similarity(self, a1, a2) -> float:
        if isinstance(a1, dict) and isinstance(a2, dict):
            return _compare_analyses(a1, a2)
        return _cosine_vec(a1, a2) if (a1 and a2) else 0.0
 
    # ── matching ──────────────────────────────────────────────────────────
 
    def compare_matches(self, target_item, item_list: list) -> list:
        results     = []
        target_text = f"{target_item.item_name} {target_item.description or ''} {target_item.location or ''}"
        target_vec  = self._tokenize(target_text)
        target_img  = self.get_or_create_image_analysis(target_item)
 
        for item in item_list:
            if item.id == target_item.id:
                continue
 
            item_text  = f"{item.item_name} {item.description or ''} {item.location or ''}"
            text_score = self._cosine_text(target_vec, self._tokenize(item_text))
 
            img_score = 0.0
            if target_img:
                img_score = _compare_analyses(target_img, self.get_or_create_image_analysis(item))
 
            category_bonus = 0.20 if target_item.category == item.category else 0.0
            final_score    = (img_score * 0.50) + (text_score * 0.30) + category_bonus
 
            if final_score >= self.threshold:
                results.append({'item': item, 'score': round(final_score, 4)})
 
        results.sort(key=lambda x: x['score'], reverse=True)
        return results
 
    def run_matching_for_item(self, lost_item) -> list:
        from models.item import Item, ItemType, ItemStatus, Match
        from extensions import db
 
        self.get_or_create_image_analysis(lost_item)
        found_items = Item.query.filter_by(
            item_type=ItemType.FOUND, status=ItemStatus.NOT_FOUND
        ).all()
        matches = self.compare_matches(lost_item, found_items)
 
        Match.query.filter_by(source_item_id=lost_item.id).delete()
        for m in matches[:10]:
            db.session.add(Match(
                source_item_id=lost_item.id,
                matched_item_id=m['item'].id,
                similarity_score=m['score'],
            ))
        db.session.commit()
        return matches
 
    def search_by_image(self, image_path: str, item_list: list) -> list:
        """يبحث بصورة مؤقتة في قائمة الأغراض."""
        search_analysis = _analyze_image(image_path)
        if not search_analysis:
            return []
 
        results = []
        for item in item_list:
            if not item.image_path:
                continue
            item_analysis = self.get_or_create_image_analysis(item)
            score         = _compare_analyses(search_analysis, item_analysis)
            if score >= self.threshold:
                results.append({
                    'item':            item,
                    'score':           round(score * 100, 1),
                    'dominant_colors': search_analysis.get('dominant_colors', []),
                })
 
        results.sort(key=lambda x: x['score'], reverse=True)
        return results
 
 
# Singleton
ai_matcher = AIMatching()
 