import re
import config

AIRBAG_KEYWORDS = ["airbag", "air bag", "airbags", "srs", "deployed", "opened", "replaced", "shot", "fired"]
PANEL_KEYWORDS = ["repaint", "re-paint", "painted", "respray", "panel", "gap", "uneven", "repaired", "restored", "damage", "accident", "collision", "crash", "dent", "filler", "putty"]
REPAIR_KEYWORDS = ["repaired", "restored", "after accident", "needs repair"]

def _contains_any(text, keywords):
    t = text.lower()
    for k in keywords:
        if k.lower() in t:
            return k
    return None

def heuristic_inspect(detail, car, market_discount=None):
    desc = ""
    for k in ["car_desc", "comment", "desc", "description", "car_comment", "comment_ka", "comment_en"]:
        if detail.get(k):
            desc += " " + str(detail.get(k))
    for k in ["comment", "desc"]:
        if car.get(k):
            desc += " " + str(car.get(k))
    desc_lower = desc.lower()
    photos = detail.get("photos") or detail.get("pics") or detail.get("photo_urls") or car.get("photos") or []
    if isinstance(photos, str):
        photos = [photos]
    photo_count = len(photos) if isinstance(photos, list) else 0

    airbag_prob = 10
    panel_prob = 15
    reasons = []

    hit = _contains_any(desc_lower, AIRBAG_KEYWORDS)
    if hit:
        airbag_prob += 40
        reasons.append(f"description mentions '{hit}'")
    hit2 = _contains_any(desc_lower, REPAIR_KEYWORDS)
    if hit2:
        airbag_prob += 15
        panel_prob += 20
        reasons.append(f"repair keyword '{hit2}'")
    hit3 = _contains_any(desc_lower, PANEL_KEYWORDS)
    if hit3:
        panel_prob += 30
        reasons.append(f"panel/paint keyword '{hit3}'")
    if photo_count > 0 and photo_count < 4:
        airbag_prob += 15
        panel_prob += 15
        reasons.append(f"few photos ({photo_count}) - seller hiding")
    if photo_count == 0:
        airbag_prob += 10
        panel_prob += 10
        reasons.append("no photos")
    if market_discount is not None and market_discount > 10:
        airbag_prob += 10
        panel_prob += 10
        reasons.append(f"very cheap {market_discount}% below market")
    try:
        price = int(car.get("price_usd") or detail.get("price_usd") or 0)
        year = int(car.get("prod_year") or detail.get("prod_year") or 0)
        if year >= 2021 and price > 0 and price < 5000:
            airbag_prob += 15
            reasons.append(f"suspiciously cheap ${price} for {year}")
    except:
        pass

    airbag_prob = min(95, max(5, airbag_prob))
    panel_prob = min(95, max(5, panel_prob))

    if "no accident" in desc_lower or "without accident" in desc_lower or "clean" in desc_lower:
        airbag_prob = max(5, airbag_prob - 20)
        panel_prob = max(5, panel_prob - 15)
        reasons.append("claims 'no accident/clean'")

    return {"airbag_prob": airbag_prob, "panel_gap_prob": panel_prob, "reasons": reasons, "photo_count": photo_count, "desc_snippet": desc[:200].strip()}
