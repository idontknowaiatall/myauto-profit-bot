"""
Config for myauto.ge profit bot - 100% free, no AI subscriptions:
- Market price-drop check (needs 5%+ below learned average)
- No American cars (Chevrolet etc.)
- Min year 2021, mileage < 100000 km
- VIN must be registered on the listing (myauto masks VINs publicly)
- Local keyword-based airbag/panel-gap risk heuristics (no AI API)
"""
from pathlib import Path
from dotenv import load_dotenv
import os
# absolute path so it works on PythonAnywhere too (different working dir)
load_dotenv(Path(__file__).resolve().parent / ".env")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", "500"))
CHECK_INTERVAL_MAX = int(os.getenv("CHECK_INTERVAL_MAX", "700"))
# PythonAnywhere web app settings
SITE_URL = os.getenv("SITE_URL", "")               # e.g. yourname.pythonanywhere.com
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "myauto-secret-1")
REQUEST_DELAY_SEC = 2.5
API_TIMEOUT = 30
MAX_RETRIES = 3
# New 2025+ myauto API (locale-prefixed). cloudscraper passes the Cloudflare check.
API_URL = "https://api2.myauto.ge/ka/products"
DETAIL_URL = "https://api2.myauto.ge/ka/products/"
PHOTO_BASE = "https://static.tnet.ge/myauto/photos/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.myauto.ge/ka/search",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,ka;q=0.8",
}
# TypeID=0 cars, ForRent=0 sell only, Period: newest listings (1h/3h/6h/12h/24h),
# SortOrder=1 newest first, FuelTypes: 2=petrol 6/10/11=hybrid 7=electric (3=diesel excluded)
SEARCH_PARAMS = {
    "TypeID": "0",
    "ForRent": "0",
    "Period": "1h",
    "CurrencyID": "1",
    "SortOrder": "1",
    "FuelTypes": "2,6,7,10,11",
}
PROFIT_RULES = {
    "min_year": 2021,
    "max_mileage": 99999,
    "max_price": 50000,
    "min_price": 3000,
    "customs_passed": None,
    "allowed_engines": None,
    "target_mans": [],
    "require_vin": True,  # listing must have a VIN registered (masked is ok)
}
BANNED_MANS = ["CHEVROLET","FORD","DODGE","CHRYSLER","GMC","CADILLAC","LINCOLN","JEEP","BUICK","TESLA","HUMMER","PONTIAC","SATURN","RAM"]
BANNED_MANS_NORM = {m.strip().lower() for m in BANNED_MANS}
# myauto location_id 23 = "on the way to Georgia" (გზაში საქ.-სკენ)
BANNED_LOCATIONS = {23}
# VIN first char = country code. Exclude 2 (Canada), 3 (Mexico), 5 (USA)
BANNED_VIN_PREFIXES = {"2", "3", "5"}
USE_PRICE_DROP_FILTER = True
PRICE_DROP_PERCENT = 5
STRICT_MARKET_FILTER = False
MAX_ALLOWED_AIRBAG_PROB = 60
MAX_ALLOWED_PANEL_GAP_PROB = 60
# fuel_type_id -> label (canonical IDs from myauto appdata)
FUEL_TYPES = {2: "Petrol", 3: "Diesel", 5: "Gas/Petrol", 6: "Hybrid", 7: "Electric", 8: "Gas/Petrol", 9: "Gas/Petrol", 10: "Plug-in Hybrid", 11: "Hybrid", 12: "Hydrogen"}
# Only these are alerted: petrol, hybrid, plug-in hybrid, electric (3=diesel, 5/8/9=gas excluded)
ALLOWED_FUEL_TYPES = {2, 6, 7, 10, 11}
