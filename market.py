import json
import re
import statistics
from pathlib import Path
import config

MARKET_FILE = Path(__file__).parent / "market_data.json"

MAX_PRICES_PER_KEY = 300
MIN_SAMPLES_FOR_MEDIAN = 5

def _norm(s):
    # "5-Series" (caucasus) and "5 Series" (myauto) must share one key
    return re.sub(r"[^0-9a-z]+", "", str(s or "").lower())

def load_market():
    if MARKET_FILE.exists():
        try:
            data = json.loads(MARKET_FILE.read_text())
        except:
            return {}
        # migrate old raw keys to normalized ones (keep the bigger entry on clash)
        out = {}
        for k, v in data.items():
            parts = k.split("|")
            nk = "|".join([_norm(parts[0]), _norm(parts[1]), parts[2]]) if len(parts) == 3 else k
            size = lambda e: max(e.get("count", 0), len(e.get("prices", {})))
            if nk not in out or size(v) > size(out[nk]):
                out[nk] = v
        return out
    return {}

def save_market(data):
    MARKET_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def key_for(car):
    man = _norm(car.get("man_name") or car.get("man") or "")
    model = _norm(car.get("model_name") or car.get("model") or "")
    year = str(car.get("prod_year") or "")
    return f"{man}|{model}|{year}"

def get_avg(car, market):
    k = key_for(car)
    entry = market.get(k)
    if not entry:
        return None
    return entry.get("avg")

def update_with_cars(cars):
    """Median price per make|model|year. Each listing is stored once by id, so a
    car seen in many runs no longer counts many times (old sum/count did)."""
    market = load_market()
    for c in cars:
        try:
            if c.get("source", "myauto") != "myauto":
                continue  # other sources are uncleared auction cars - different market
            price = c.get("price_usd") or c.get("price_value") or c.get("price")
            if not price:
                continue
            price = int(price)
            if price < 1000 or price > 100000:
                continue
            k = key_for(c)
            if "|" not in k or k.endswith("|"):
                continue
            car_id = str(c.get("car_id") or c.get("id") or "")
            entry = market.setdefault(k, {})
            prices = entry.setdefault("prices", {})
            prices.pop(car_id, None)  # re-insert so newest stays last
            prices[car_id] = price
            while len(prices) > MAX_PRICES_PER_KEY:
                prices.pop(next(iter(prices)))
            if len(prices) >= MIN_SAMPLES_FOR_MEDIAN or not entry.get("avg"):
                entry["avg"] = int(statistics.median(prices.values()))
        except:
            continue
    save_market(market)
    return market

def check_price_drop(car, market):
    if not config.USE_PRICE_DROP_FILTER:
        return True, None, 0, "filter disabled"
    price = car.get("price_usd") or car.get("price_value") or car.get("price")
    if not price:
        return False, None, 0, "no price"
    price = int(price)
    avg = get_avg(car, market)
    if avg is None:
        if config.STRICT_MARKET_FILTER:
            return False, None, 0, "no market history (strict)"
        else:
            return True, None, 0, "no market history (lenient pass)"
    if avg <= 0:
        return True, avg, 0, "avg 0"
    discount = (avg - price) / avg * 100
    needed = config.PRICE_DROP_PERCENT
    if discount >= needed:
        return True, avg, round(discount,1), f"{discount:.1f}% below avg ${avg}"
    else:
        return False, avg, round(discount,1), f"only {discount:.1f}% below, need {needed}% (avg ${avg})"
