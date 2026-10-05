import json
from pathlib import Path
import config

MARKET_FILE = Path(__file__).parent / "market_data.json"

def load_market():
    if MARKET_FILE.exists():
        try:
            return json.loads(MARKET_FILE.read_text())
        except:
            return {}
    return {}

def save_market(data):
    MARKET_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def key_for(car):
    man = (car.get("man_name") or car.get("man") or "").strip().lower()
    model = (car.get("model_name") or car.get("model") or "").strip().lower()
    year = str(car.get("prod_year") or "")
    return f"{man}|{model}|{year}"

def get_avg(car, market):
    k = key_for(car)
    entry = market.get(k)
    if not entry:
        return None
    return entry.get("avg")

def update_with_cars(cars):
    market = load_market()
    for c in cars:
        try:
            price = c.get("price_usd") or c.get("price_value") or c.get("price")
            if not price:
                continue
            price = int(price)
            if price < 1000 or price > 100000:
                continue
            k = key_for(c)
            if "|" not in k or k.endswith("|"):
                continue
            entry = market.get(k)
            if not entry:
                market[k] = {"sum": price, "count": 1, "avg": price}
            else:
                entry["sum"] += price
                entry["count"] += 1
                entry["avg"] = int(entry["sum"] / entry["count"])
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
