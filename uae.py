"""
UAE sources: carsooq.com and sooq-cars.com.

Both sites allow these pages in robots.txt and serve them to plain requests.
Dubizzle and DubiCars block automated requests (Incapsula / 403, and DubiCars'
robots.txt disallows /search), so they are not scanned.

Rules here are separate from myauto's: years, AED price range and makes come
from config.UAE_RULES; there is no VIN, market average or auction check.
"""
import json
import random
import re
import time
import requests
import config

HEADERS = {
    "User-Agent": config.HEADERS["User-Agent"],
    "Accept-Language": "en-US,en;q=0.9",
}
AED_PER_USD = 3.6725  # the dirham is pegged to the dollar


def _get(url, params=None):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=config.API_TIMEOUT)
        r.raise_for_status()
        time.sleep(config.REQUEST_DELAY_SEC + random.uniform(0, 1.5))
        return r.text
    except Exception as e:
        print(f"[UAE] request failed {url}: {e}")
        return None


def _make(title):
    """First wanted make named in the title ("Used 2021 Toyota ..." -> toyota)."""
    words = re.findall(r"[a-z]+", title.lower())
    for w in words:
        if w in config.UAE_RULES["makes"]:
            return w
    return next((w for w in words if w != "used"), "")


def _price(value):
    digits = re.sub(r"[^\d]", "", str(value or ""))
    return int(digits) if digits else None


def matches(car):
    r = config.UAE_RULES
    if car.get("make", "").lower() not in r["makes"]:
        return False, f"make {car.get('make')}"
    year = car.get("year") or 0
    if not (r["min_year"] <= year <= r["max_year"]):
        return False, f"year {year}"
    price = car.get("price_aed")
    if not price or not (r["min_price_aed"] <= price <= r["max_price_aed"]):
        return False, f"price {price}"
    return True, "match"


# --- carsooq.com -----------------------------------------------------------
# /search filters condition, make and year server-side; price is checked here.

def _carsooq_cards(html):
    cards = []
    for m in re.finditer(r"vehicleQuickView\(JSON\.parse\('(.*?)'\)\)", html):
        try:
            cards.append(json.loads(m.group(1).encode().decode("unicode_escape")))
        except Exception:
            continue
    return cards


def fetch_carsooq(seen=None):
    r = config.UAE_RULES
    params = [("condition", "used")] + [("make[]", m) for m in r["makes"]] + [
        ("year_min", r["min_year"]), ("year_max", r["max_year"]), ("sort", "newest")]
    cars = []
    for page in range(1, config.UAE_MAX_PAGES + 1):
        html = _get("https://www.carsooq.com/search", params + [("page", page)])
        cards = _carsooq_cards(html or "")
        if not cards:
            break
        batch = []
        for c in cards:
            title = str(c.get("title") or "").replace("\\/", "/")
            batch.append({
                "source": "carsooq",
                "car_id": f"cs-{c.get('id')}",
                "title": title,
                "make": _make(title),
                "year": int(c.get("year") or 0),
                "price_aed": _price(c.get("price")),
                "mileage": c.get("mileage") or "",
                "city": c.get("city") or "",
                "link": str(c.get("permalink") or "").replace("\\/", "/"),
                "photo": "",
            })
        cars.extend(batch)
        if seen is not None and all(c["car_id"] in seen for c in batch):
            break
    print(f"[UAE] carsooq: {len(cars)} listings")
    return cars


# --- sooq-cars.com ---------------------------------------------------------
# Newest-first list; robots.txt allows only ?page= on it, so filters run here.

def _sooq_records(html):
    payload = "".join(
        json.loads('"' + chunk + '"')
        for chunk in re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S))
    records = {}
    for m in re.finditer(r'\{"id":(\d+),"isHomePage":[^{}]*?"currency":"[A-Z]+"', payload):
        try:
            rec = json.loads(m.group(0) + "}")
        except Exception:
            continue
        records[rec["id"]] = rec
    return list(records.values())


def fetch_sooqcars(seen=None):
    cars = []
    for page in range(1, config.UAE_MAX_PAGES + 1):
        params = {"page": page} if page > 1 else None
        html = _get("https://sooq-cars.com/ae/en/ready/cars", params)
        records = _sooq_records(html or "")
        if not records:
            break
        batch = []
        for rec in records:
            title = str(rec.get("nameEn") or rec.get("title") or "")
            years = re.findall(r"\b(19\d{2}|20\d{2})\b", title)
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            batch.append({
                "source": "sooqcars",
                "car_id": f"sq-{rec['id']}",
                "title": title,
                "make": _make(title),
                "year": int(years[-1]) if years else 0,
                "price_aed": rec.get("price") if rec.get("currency") == "AED" else None,
                "mileage": "",
                "city": "",
                "link": f"https://sooq-cars.com/ae/en/ready/cars/{rec['id']}-{slug}",
                "photo": rec.get("imageSrc") or "",
                "posted": rec.get("timestamp") or "",
            })
        cars.extend(batch)
        if seen is not None and all(c["car_id"] in seen for c in batch):
            break
    print(f"[UAE] sooq-cars: {len(cars)} listings")
    return cars


def fetch_all(seen=None):
    cars = []
    for fetch in (fetch_carsooq, fetch_sooqcars):
        try:
            cars += fetch(seen)
        except Exception as e:
            print(f"[UAE] {fetch.__name__} failed: {e}")
    return cars
