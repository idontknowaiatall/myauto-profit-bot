import time
import random
import json
import re
import os
from pathlib import Path
import cloudscraper
import config
import market
import ai_inspector
import damage

SEEN_FILE = Path(__file__).parent / "seen.json"
MAX_PAGES = int(os.getenv("MAX_PAGES", "10"))  # lower it on CPU-limited hosts

def load_seen():
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text()))
        except Exception:
            return set()
    return set()

def save_seen(seen_set):
    # keep file order (oldest first) and append new ids, so trimming drops the
    # oldest ids - list(set) order is arbitrary and could drop recent ones
    old = []
    if SEEN_FILE.exists():
        try:
            old = json.loads(SEEN_FILE.read_text())
        except Exception:
            old = []
    kept = [i for i in old if i in seen_set]
    known = set(kept)
    ordered = kept + [i for i in seen_set if i not in known]
    SEEN_FILE.write_text(json.dumps(ordered[-8000:]))

def make_session():
    # cloudscraper solves the Cloudflare managed challenge on api2.myauto.ge
    s = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "darwin", "desktop": True})
    s.headers.update(config.HEADERS)
    return s

def fetch_page(session, page=1, retries=0):
    params = dict(config.SEARCH_PARAMS)
    params["Page"] = page
    try:
        resp = session.get(config.API_URL, params=params, timeout=config.API_TIMEOUT)
        if resp.status_code == 403:
            # Cloudflare challenge not solved - recreate session once
            if retries == 0:
                session = make_session()
                return fetch_page(session, page, retries + 1)
            print("[ERROR] Still 403 after session renewal")
            return None
        if resp.status_code == 429:
            wait = (2 ** retries) * 60 + random.uniform(0, 30)
            print(f"[WARN] 429 Rate limited. Sleeping {int(wait)}s (retry {retries+1}/{config.MAX_RETRIES})")
            time.sleep(wait)
            if retries < config.MAX_RETRIES:
                return fetch_page(session, page, retries + 1)
            print("[ERROR] Max retries hit after 429")
            return None
        resp.raise_for_status()
        time.sleep(config.REQUEST_DELAY_SEC + random.uniform(0, 1.5))
        return resp.json()
    except Exception as e:
        print(f"[ERROR] Request failed page {page}: {e}")
        if retries < config.MAX_RETRIES:
            time.sleep(5 + random.uniform(0, 5))
            return fetch_page(session, page, retries + 1)
        return None

def _extract_items(data):
    if isinstance(data, dict):
        d = data.get("data")
        if isinstance(d, dict) and isinstance(d.get("items"), list):
            return d["items"]
        if isinstance(d, list):
            return d
        if isinstance(data.get("items"), list):
            return data["items"]
    if isinstance(data, list):
        return data
    return None

def fetch_all_new_cars(seen=None):
    session = make_session()
    all_items = []
    page = 1
    while True:
        print(f"[INFO] Fetching page {page} ...")
        data = fetch_page(session, page)
        if not data:
            break
        items = _extract_items(data)
        if not items:
            print(f"[INFO] No items on page {page}, stopping.")
            break
        print(f"[INFO] Got {len(items)} cars on page {page}")
        all_items.extend(items)
        if seen is not None and all(str(i.get("car_id") or i.get("id")) in seen for i in items):
            print(f"[INFO] Page {page} already seen, stopping.")
            break
        meta = data.get("data", {}).get("meta") if isinstance(data.get("data"), dict) else {}
        if meta and "last_page" in meta and page >= meta["last_page"]:
            break
        if len(items) < 15:
            break
        page += 1
        if page > MAX_PAGES:
            print(f"[INFO] Reached page limit {MAX_PAGES}")
            break
    return all_items

def extract_vin(detail, car):
    # myauto masks VINs publicly (e.g. "5UXTY5***********"); a registered
    # masked VIN still proves the seller filed one. Full VIN from description
    # is preferred when present.
    for src in [detail or {}, car or {}]:
        for k in ["vin", "vin_code", "vinCode", "VIN"]:
            v = src.get(k)
            if v and str(v).strip() and "*" not in str(v):
                v = str(v).strip().upper()
                if re.match(r"^[A-HJ-NPR-Z0-9]{17}$", v):
                    return v
    for src in [detail or {}, car or {}]:
        v = src.get("vin") or src.get("vin_code")
        if v and str(v).strip():
            return str(v).strip().upper()  # masked
        desc = str(src.get("car_desc", "")) + " " + str(src.get("comment", "")) + " " + str(src.get("desc", ""))
        m = re.findall(r"\b[A-HJ-NPR-Z0-9]{17}\b", desc.upper())
        for c in m:
            if re.match(r"^[A-HJ-NPR-Z0-9]{17}$", c):
                return c
    return None

def get_photo_urls(detail, car):
    # New pattern: https://static.tnet.ge/myauto/photos/{photo}/large/{car_id}_{n}.jpg
    urls = []
    for src in [detail or {}, car or {}]:
        car_id = src.get("car_id") or src.get("id")
        path = src.get("photo")
        ver = src.get("photo_ver") or 0
        if not car_id or not path:
            continue
        n = int(src.get("pic_number") or 1) or 1
        for i in range(1, min(n, 8) + 1):
            urls.append(f"{config.PHOTO_BASE}{path}/large/{car_id}_{i}.jpg?v={ver}")
        if not urls:
            urls.append(f"{config.PHOTO_BASE}{path}/large/{car_id}_1.jpg?v={ver}")
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def is_basic_profitable(car, rules=None):
    try:
        price = car.get("price_usd") or car.get("price_value") or car.get("price")
        year = car.get("prod_year")
        mileage = car.get("car_run_km") or car.get("car_run") or 999999
        man = (car.get("man_name") or car.get("man") or "").strip()
        man_norm = man.lower()
        if not price:
            return False, "no price"
        price = int(price)
        year = int(year) if year else 0
        mileage = int(mileage) if mileage else 999999
        r = rules or config.PROFIT_RULES
        ft = car.get("fuel_type_id")
        if ft is not None and str(ft).strip() != "":
            try:
                if int(ft) not in config.ALLOWED_FUEL_TYPES:
                    return False, f"fuel type {config.FUEL_TYPES.get(int(ft), ft)} not allowed"
            except (ValueError, TypeError):
                pass
        if year < r["min_year"]:
            return False, f"year {year} < {r['min_year']}"
        if mileage > r["max_mileage"]:
            return False, f"mileage {mileage} > {r['max_mileage']}"
        if r.get("min_mileage") and mileage < r["min_mileage"]:
            return False, f"mileage {mileage} < {r['min_mileage']}"
        if price > r["max_price"] or price < r["min_price"]:
            return False, f"price {price} out of range"
        if man_norm in config.BANNED_MANS_NORM:
            return False, f"banned American brand {man}"
        for banned in config.BANNED_MANS_NORM:
            if banned in man_norm:
                return False, f"banned brand contains {banned}"
        loc = car.get("location_id")
        try:
            if loc is not None and int(loc) in config.BANNED_LOCATIONS:
                return False, "on the way to Georgia - excluded"
        except (ValueError, TypeError):
            pass
        return True, "basic pass"
    except Exception as e:
        return False, f"error {e}"

def fetch_detail(session, car_id):
    url = config.DETAIL_URL + str(car_id)
    try:
        resp = session.get(url, timeout=config.API_TIMEOUT)
        if resp.status_code == 429:
            print(f"[WARN] 429 on detail {car_id}, sleeping 60s")
            time.sleep(60)
            return None
        resp.raise_for_status()
        time.sleep(1.0 + random.uniform(0, 1))
        j = resp.json()
        if isinstance(j, dict) and isinstance(j.get("data"), dict):
            return j["data"].get("info") or j["data"]
        return j
    except Exception as e:
        print(f"[ERROR] detail fetch {car_id}: {e}")
        return None

def precheck(car, market_data, rules=None):
    """Cheap checks on list data only (VIN + market price), run before the
    detail request so detail calls are spent on real candidates."""
    source = car.get("source", "myauto")
    vin = extract_vin({}, car)
    if source in config.REQUIRE_VIN_SOURCES and (rules or config.PROFIT_RULES).get("require_vin") and not vin:
        return False, "no VIN registered - cannot verify history"
    if vin and vin[0] in config.BANNED_VIN_PREFIXES:
        return False, f"VIN starts with {vin[0]} - excluded"
    ok_price, _, _, reason_price = market.check_price_drop(car, market_data)
    if not ok_price:
        return False, f"market fail: {reason_price}"
    return True, "precheck pass"

def fetch_auction(session, car_id):
    """US auction record for a myauto listing.
    Returns the record dict, {} when myauto has none, None when the lookup failed
    (a failed lookup must never stop the alert)."""
    try:
        resp = session.get(config.AUCTION_URL, params={"carId": car_id}, timeout=config.API_TIMEOUT)
        resp.raise_for_status()
        time.sleep(1.0 + random.uniform(0, 1))
        data = resp.json().get("data")
    except Exception as e:
        print(f"[WARN] auction lookup {car_id}: {e}")
        return None
    if not isinstance(data, dict) or data.get("status") != "success":
        return {}
    # entries can carry stray spaces; video links (.mp4) are not photos
    images = [str(u).strip() for u in (data.get("images") or [])]
    data["images"] = [u for u in images if u and not u.lower().split("?")[0].endswith(".mp4")]
    return data

def check_full_profitable(car, detail, market_data, rules=None):
    source = car.get("source", "myauto")
    vin = extract_vin(detail or {}, car)
    if source in config.REQUIRE_VIN_SOURCES and (rules or config.PROFIT_RULES).get("require_vin") and not vin:
        return False, {"reason": "no VIN registered - cannot verify history", "vin": None}
    if vin and vin[0] in config.BANNED_VIN_PREFIXES:
        return False, {"reason": f"VIN starts with {vin[0]} - excluded", "vin": vin}
    ok_price, avg, discount, reason_price = market.check_price_drop(car, market_data)
    if not ok_price:
        return False, {"reason": f"market fail: {reason_price}", "avg": avg, "discount": discount, "vin": vin}
    photo_urls = car.get("photo_urls") or get_photo_urls(detail or {}, car)
    inspection = ai_inspector.heuristic_inspect(detail or {}, car, market_discount=discount)
    # Caucasus listings can link to their myauto copy, which has the auction record
    auction_id = (detail or {}).get("myauto_id") if source != "myauto" else (car.get("car_id") or car.get("id"))
    auction = fetch_auction(make_session(), auction_id) if auction_id else {}
    chassis = damage.chassis_risk(car, detail or {}, vin=vin, market_discount=discount, has_market=avg is not None, auction=auction)
    airbag = inspection.get("airbag_prob", 50)
    panel = inspection.get("panel_gap_prob", 50)
    if airbag > config.MAX_ALLOWED_AIRBAG_PROB:
        return False, {"reason": f"airbag risk {airbag}% > {config.MAX_ALLOWED_AIRBAG_PROB}%", "vin": vin, "avg": avg, "discount": discount, "inspection": inspection}
    if panel > config.MAX_ALLOWED_PANEL_GAP_PROB:
        return False, {"reason": f"panel gap risk {panel}% > {config.MAX_ALLOWED_PANEL_GAP_PROB}%", "vin": vin, "avg": avg, "discount": discount, "inspection": inspection}
    return True, {"vin": vin, "avg": avg, "discount": discount, "inspection": inspection, "chassis": chassis, "auction": auction, "photo_urls": photo_urls, "reason": reason_price}

def get_car_link(car):
    if car.get("link"):
        return car["link"]
    car_id = car.get("car_id") or car.get("id")
    return f"https://www.myauto.ge/ka/pr/{car_id}"

if __name__ == "__main__":
    import json as _j
    cars = fetch_all_new_cars()
    print(f"Fetched {len(cars)}")
    for c in cars[:3]:
        print(_j.dumps(c, indent=2, ensure_ascii=False)[:800])
        basic, r = is_basic_profitable(c)
        print("basic:", basic, r)
