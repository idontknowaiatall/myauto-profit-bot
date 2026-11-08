"""
Caucasus Auto (caucasusauto.com) source.

Uses the site's own public JSON API (no Cloudflare challenge, no login) and
converts each listing to the myauto-style dict the rest of the bot expects,
with source="caucasus". Listings have no VIN, mileage is in miles, and most
cars are not customs-cleared (an estimate in GEL comes with each listing).
"""
import time
import random
import requests
import config

HEADERS = {
    "User-Agent": config.HEADERS["User-Agent"],
    "Accept": "application/json",
    "Origin": "https://caucasusauto.com",
    "Referer": "https://caucasusauto.com/",
}
MILES_TO_KM = 1.609344
# canonical myauto fuel ids (config.FUEL_TYPES)
FUEL_IDS = {"Petrol": 2, "Diesel": 3, "Hybrid": 6, "Electric": 7, "PluginHybrid": 10}


def _get(url, params=None):
    for attempt in range(config.MAX_RETRIES):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=config.API_TIMEOUT)
            if r.status_code == 429:
                time.sleep(60 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[CAUCASUS] request failed ({attempt + 1}): {e}")
            time.sleep(5 + random.uniform(0, 5))
    return None


def normalize(item):
    price = float(item.get("priceUsd") or (item.get("price") or {}).get("amount") or 0)
    customs_usd = 0
    est = item.get("customsEstimate") or {}
    national = item.get("priceNational") or {}
    cleared = item.get("customsClearanceStatus") == "Cleared"
    if not cleared and est.get("amount") and national.get("amount") and price:
        gel_per_usd = float(national["amount"]) / price
        customs_usd = int(float(est["amount"]) / gel_per_usd)
    mileage = item.get("mileage") or {}
    km = mileage.get("value")
    if km is not None and str(mileage.get("unit", "")).lower().startswith("mile"):
        km = int(km * MILES_TO_KM)
    photos = item.get("photoGalleryUrls") or item.get("previewPhotoUrls") or []
    # w8192 originals are huge; Telegram needs <=10MB, the w1280 size is enough
    photos = [u.replace(".w8192.", ".w1280.") for u in photos]
    engine = item.get("engineVolume")
    return {
        "source": "caucasus",
        "car_id": "ca-" + str(item["publicId"]),
        "public_id": item["publicId"],
        "man_name": item.get("makeName") or "",
        "model_name": item.get("modelName") or "",
        "prod_year": item.get("releaseYear"),
        "price_usd": int(price + (customs_usd if config.CAUCASUS_ADD_CUSTOMS else 0)),
        "list_price_usd": int(price),
        "customs_usd": customs_usd,
        "car_run_km": km,
        "fuel_type_id": FUEL_IDS.get(item.get("fuelType")),
        "engine_volume": int(float(engine) * 1000) if engine else "",
        "customs_passed": cleared,
        "vin": item.get("vin") or item.get("maskedVin") or "",
        "photo_urls": photos,
        "pic_number": len(photos),
        "link": f"https://caucasusauto.com/ka-ge/car-catalogue/{item.get('slug')}?market=GE",
        "car_desc": item.get("additionalPublicDescription") or "",
        "primaryDamage": item.get("primaryDamage"),
        "secondaryDamage": item.get("secondaryDamage"),
    }


def fetch_new_cars(seen=None):
    """Newest listings first; stops at a page that is fully seen."""
    if not config.CAUCASUS_ENABLED:
        return []
    cars = []
    for page in range(1, config.CAUCASUS_MAX_PAGES + 1):
        data = _get(config.CAUCASUS_API, {"currency": "USD", "sort": "CreatedDesc",
                                          "page": page, "pageSize": config.CAUCASUS_PAGE_SIZE})
        items = (data or {}).get("items") or []
        if not items:
            break
        batch = []
        for it in items:
            try:
                batch.append(normalize(it))
            except Exception as e:
                print(f"[CAUCASUS] skip bad item: {e}")
        print(f"[CAUCASUS] Got {len(batch)} cars on page {page}")
        cars.extend(batch)
        if seen is not None and all(c["car_id"] in seen for c in batch):
            break
        time.sleep(config.REQUEST_DELAY_SEC + random.uniform(0, 1.5))
    return cars


def fetch_detail(car):
    """Full listing (description, damage fields if any)."""
    d = _get(config.CAUCASUS_API + "/" + str(car["public_id"]))
    time.sleep(1.0 + random.uniform(0, 1))
    if not d:
        return {}
    return {
        "car_desc": d.get("additionalPublicDescription") or "",
        "primaryDamage": d.get("primaryDamage"),
        "secondaryDamage": d.get("secondaryDamage"),
        "damageDescription": d.get("damageDescription"),
        "vin": d.get("vin") or d.get("maskedVin") or "",
        "auctionLotNumber": d.get("auctionLotNumber"),
        "myauto_id": next((l.get("externalId") for l in d.get("externalLinks") or []
                           if l.get("source") == "myauto.ge"), None),
    }
