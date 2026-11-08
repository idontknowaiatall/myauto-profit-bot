"""
Chassis (frame / unibody) damage probability - free, no API.

Evidence is added as log-odds points on top of a base rate, then turned into a
percentage with a sigmoid. A confidence label says how strong the evidence is:
a 70% from an auction damage record means more than a 70% from text alone.

Weights are hand-set from collision-repair logic (see PLAN-fa.md, stage 2).
They are a reasoned score, not a calibrated probability, until inspection
results are collected and the weights are fitted to them.
"""
import math
import re

BASE_PROB = 0.15  # generic used car in Georgia, before any evidence

# auction primary/secondary damage -> log-odds of structural damage
# (rollover / undercarriage / side hit the load-bearing structure; hail does not)
DAMAGE_TYPE_WEIGHTS = [
    (r"frame|rollover|roll over", 2.5),
    (r"undercarriage", 1.8),
    (r"all over|side|t-?bone", 1.5),
    (r"front|rear|top|roof", 1.0),
    (r"burn|fire|flood|water", 0.6),  # rarely bends the frame, but a bad buy
    (r"hail|minor|scratch|vandal|mechanical|normal wear|cosmetic|biohazard", -1.0),
]

# text cues in English, Georgian, Russian
STRUCTURAL_WORDS = ["frame", "chassis", "unibody", "pillar", "rail damage", "structural",
                    "შასი", "ლონჟერონ", "ძარის გეომეტრ", "კარკას",
                    "лонжерон", "геометри", "стапел", "кузов поврежд", "стойк"]
ACCIDENT_WORDS = ["accident", "crash", "collision", "damaged", "salvage", "rebuilt", "total loss",
                  "ავარი", "დაზიანებ", "ნაჯახ", "ნაავარიევ",
                  "битая", "битый", "дтп", "удар", "авари", "поврежд"]
AIRBAG_WORDS = ["airbag deployed", "airbags deployed", "airbag", "srs",
                "აირბეგ", "ეარბეგ", "ბალიშ",
                "подушк"]
CLEAN_PHRASES = ["no accident", "without accident", "accident free", "accident-free", "clean title",
                 "უავარიო", "ავარიის გარეშე", "არ არის ნაავარიევ",
                 "не битая", "не битый", "не бит", "без дтп", "без аварий"]

# VIN 1st char -> region (WMI). NA-built cars in Georgia are mostly US auction imports.
VIN_REGION = {
    **{c: "North America" for c in "12345"},
    "J": "Japan", "K": "Korea", "L": "China", "S": "UK", "T": "Central Europe",
    "V": "France/Spain", "W": "Germany", "Y": "Sweden/Finland", "Z": "Italy",
}


def _logit(p):
    return math.log(p / (1 - p))


def _sigmoid(x):
    return 1 / (1 + math.exp(-x))


def _text(car, detail):
    parts = []
    for src in (detail, car):
        for k in ("car_desc", "comment", "desc", "description", "car_comment", "comment_ka", "comment_en"):
            if src.get(k):
                parts.append(str(src[k]))
    return " ".join(parts).lower()


def _damage_type_weight(label):
    label = str(label or "").lower()
    for pattern, w in DAMAGE_TYPE_WEIGHTS:
        if re.search(pattern, label):
            return w
    return 0.8  # some damage recorded but type unknown


def chassis_risk(car, detail=None, vin=None, market_discount=None, has_market=True, auction=None):
    """Returns {"prob": int %, "confidence": str, "reasons": [str], "region": str|None}."""
    detail = detail or {}
    auction = auction or {}
    x = _logit(BASE_PROB)
    reasons = []
    strong = 0  # evidence from damage records
    weak = 0    # evidence from text / price / origin

    # 1. recorded damage type (Caucasus Auto auction lots; myauto ids > 0)
    for field, factor in (("primaryDamage", 1.0), ("secondaryDamage", 0.5)):
        val = auction.get(field) or detail.get(field) or car.get(field)
        if val and str(val).strip().lower() not in ("unknown", "none", "n/a"):
            w = _damage_type_weight(val) * factor
            x += w
            strong += 1
            reasons.append(f"auction damage: {val}")
    for field, factor in (("primary_damage_type", 1.0), ("secondary_damage_type", 0.5)):
        try:
            if int(detail.get(field) or car.get(field) or 0) > 0:
                x += 0.8 * factor
                strong += 1
                reasons.append(f"myauto damage type recorded ({field})")
        except (ValueError, TypeError):
            pass

    # 2. auction import (insurance auctions sell crashed cars)
    is_auction = bool(auction) or car.get("source") == "caucasus" or str(detail.get("is_auction") or car.get("is_auction") or 0) == "1"
    if is_auction:
        x += 1.0
        weak += 1
        reasons.append("auction import")

    # 3. VIN origin
    region = None
    if vin:
        region = VIN_REGION.get(vin[0].upper())
        if region == "North America" and not is_auction:
            x += 0.5
            weak += 1
            reasons.append("North American VIN (likely US auction import)")

    # 4. description
    text = _text(car, detail)
    claims_clean = any(c in text for c in CLEAN_PHRASES)
    for c in CLEAN_PHRASES:
        text = text.replace(c, " ")
    hit = next((w for w in STRUCTURAL_WORDS if w in text), None)
    if hit:
        x += 2.0
        weak += 1
        reasons.append(f"text mentions structure: '{hit}'")
    hit = next((w for w in AIRBAG_WORDS if w in text), None)
    if hit:
        x += 1.2
        weak += 1
        reasons.append(f"text mentions airbags: '{hit}'")
    hit = next((w for w in ACCIDENT_WORDS if w in text), None)
    if hit:
        x += 1.0
        weak += 1
        reasons.append(f"text mentions accident: '{hit}'")
    if claims_clean:
        x -= 0.6  # sellers say this a lot, so it only counts a little
        reasons.append("seller claims no accident")

    # 5. price far below market
    if has_market and market_discount is not None:
        if market_discount >= 25:
            x += 0.8
            weak += 1
            reasons.append(f"{market_discount}% below market")
        elif market_discount >= 15:
            x += 0.4
            weak += 1
            reasons.append(f"{market_discount}% below market")

    prob = int(round(min(0.97, max(0.03, _sigmoid(x))) * 100))
    if strong:
        confidence = "Likely"
    elif weak >= 2:
        confidence = "Possible"
    else:
        confidence = "Needs inspection"
    return {"prob": prob, "confidence": confidence, "reasons": reasons, "region": region}
