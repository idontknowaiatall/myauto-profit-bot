import requests
import telebot
import config

FUEL_TYPES = config.FUEL_TYPES
MILES_TO_KM = 1.609344

bot = None
if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_BOT_TOKEN != "1234567890:AAH_example_token_here":
    bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN, parse_mode="HTML")
else:
    print("[WARN] TELEGRAM_BOT_TOKEN not set - notifications disabled. Set it in .env")

def escape_html(text):
    if text is None:
        return ""
    return str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def _auction_lines(car, info):
    auction = info.get("auction")
    if auction is None:
        return ""  # lookup failed: say nothing rather than claim there is no record
    if not auction:
        return "⚠️ سابقه حراجی پیدا نشد (به معنی سالم بودن نیست)\n"
    damage = " + ".join(escape_html(d) for d in (auction.get("primaryDamage"), auction.get("secondaryDamage"))
                        if d and str(d).strip().lower() not in ("unknown", "none", "n/a"))
    text = f"💥 <b>Auction damage: {damage or 'not stated'}</b>\n"
    sale = f"🔨 {escape_html(str(auction.get('auctionName') or 'auction').capitalize())}"
    if auction.get("salePrice"):
        sale += f" ${int(auction['salePrice']):,}"
    if auction.get("saleDate"):
        sale += f" ({escape_html(str(auction['saleDate'])[:10])})"
    text += sale + "\n"
    if auction.get("startCode"):
        text += f"🔑 {escape_html(auction['startCode'])}\n"
    try:
        auction_km = int(float(auction.get("mileage") or 0) * MILES_TO_KM)
        listing_km = int(car.get("car_run_km") or 0)
        if auction_km:
            text += f"🏁 Auction odometer: {auction_km:,} km\n"
            if listing_km and listing_km < auction_km * config.MILEAGE_WARN_RATIO:
                text += f"⚠️ Listing shows less: {listing_km:,} km\n"
                # e.g. 79,522 mi at auction listed as 79,800 km
                if abs(listing_km - float(auction["mileage"])) <= float(auction["mileage"]) * 0.03:
                    text += "   (same number as the auction miles - check the real km)\n"
    except (ValueError, TypeError):
        pass
    if auction.get("lotId"):
        text += f"🔎 <a href=\"https://finalbid.vin/en/search?q={auction['lotId']}\">Full record (title, repair cost)</a>\n"
    return text

def format_car_message(car, info=None):
    info = info or {}
    car_id = car.get("car_id") or car.get("id")
    man = escape_html(car.get("man_name") or car.get("man") or "")
    model = escape_html(car.get("model_name") or car.get("model") or "")
    year = car.get("prod_year") or ""
    price = car.get("price_usd") or car.get("price_value") or car.get("price") or "?"
    try:
        price = f"{int(float(price)):,}"
    except (ValueError, TypeError):
        pass
    mileage = car.get("car_run_km") or car.get("car_run") or "?"
    customs = "✅" if car.get("customs_passed") in (1, True, "1") else "❌"
    fuel = FUEL_TYPES.get(car.get("fuel_type_id"), "")
    engine = car.get("engine_volume") or ""
    engine_txt = f"{engine}cc {fuel}".strip()
    link = car.get("link") or f"https://www.myauto.ge/ka/pr/{car_id}"
    source = "Caucasus Auto" if car.get("source") == "caucasus" else "myauto.ge"
    photos = info.get("photo_urls") or []
    photo = photos[0] if photos else ""

    text = f"""🚗 <b>Profitable Car Found!</b> ({source})

<b>{man} {model} {year}</b>
💵 Price: <b>${price}</b>
"""
    if car.get("customs_usd"):
        text += f"   (listed ${int(car.get('list_price_usd') or 0):,} + est. customs ${int(car['customs_usd']):,})\n"
    text += f"""🏁 Mileage: {mileage} km
⛽ Engine: {engine_txt}
🛃 Customs: {customs}
"""
    vin = info.get("vin")
    if vin:
        text += f"🔢 VIN: <code>{escape_html(vin)}</code>\n"
    if info.get("avg"):
        text += f"📊 Market avg: ${info['avg']} ({info.get('discount', 0)}% below)\n"
    else:
        text += "📊 Market avg: unknown (no price history yet)\n"
    inspection = info.get("inspection") or {}
    text += f"🛡 Risk check: airbag {inspection.get('airbag_prob', '?')}% / panel {inspection.get('panel_gap_prob', '?')}%\n"
    text += _auction_lines(car, info)
    chassis = info.get("chassis")
    if chassis:
        text += f"🧱 Chassis damage: <b>{chassis['prob']}%</b> ({chassis['confidence']})\n"
        if chassis.get("reasons"):
            text += "   " + escape_html("; ".join(chassis["reasons"][:3])) + "\n"
    text += f"\n🔗 <a href=\"{link}\">{link}</a>\n🆔 ID: {car_id}\n"
    return text, photo, link

def _send_auction_photos(car, info, reply_to=None):
    """Crash photos as an album under the alert. Never fails the alert itself."""
    urls = ((info or {}).get("auction") or {}).get("images") or []
    urls = urls[:config.MAX_AUCTION_PHOTOS]
    if len(urls) < 2:
        return  # Telegram albums need 2+; the record link still covers the car
    try:
        bot.send_media_group(config.TELEGRAM_CHAT_ID, [telebot.types.InputMediaPhoto(u) for u in urls],
                             reply_to_message_id=reply_to)
        return
    except Exception as e:
        print(f"[WARN] album by URL failed for {car.get('car_id')}: {e}")
    try:
        # auction hosts can refuse Telegram's servers; download and upload instead
        files = []
        for u in urls:
            r = requests.get(u, headers={"User-Agent": config.HEADERS["User-Agent"]}, timeout=config.API_TIMEOUT)
            r.raise_for_status()
            files.append(telebot.types.InputMediaPhoto(r.content))
        bot.send_media_group(config.TELEGRAM_CHAT_ID, files, reply_to_message_id=reply_to)
    except Exception as e:
        print(f"[WARN] album upload failed for {car.get('car_id')}: {e}")

def send_car(car, info=None):
    if config.DRY_RUN:
        text, photo, link = format_car_message(car, info)
        print("[DRY RUN] would send:\n" + text + f"photo: {photo}\n")
        print("[DRY RUN] auction photos:", ((info or {}).get("auction") or {}).get("images", [])[:config.MAX_AUCTION_PHOTOS])
        print("[DRY RUN] caption length:", len(text))
        return True
    if not bot:
        print("[SKIP] No bot token - would send:", car.get("car_id"))
        return False
    if not config.TELEGRAM_CHAT_ID:
        print("[ERROR] TELEGRAM_CHAT_ID not set in .env")
        return False
    text, photo, link = format_car_message(car, info)
    try:
        if len(text) > 1000:
            text = text[:997] + "..."
        if photo.startswith("http"):
            try:
                msg = bot.send_photo(config.TELEGRAM_CHAT_ID, photo, caption=text)
                print(f"[SENT] Photo + caption for {car.get('car_id')}")
                _send_auction_photos(car, info, reply_to=msg.message_id)
                return True
            except Exception as e:
                print(f"[WARN] Photo send failed {e}, falling back to text")
        msg = bot.send_message(config.TELEGRAM_CHAT_ID, text, disable_web_page_preview=False)
        print(f"[SENT] Text for {car.get('car_id')}")
        _send_auction_photos(car, info, reply_to=msg.message_id)
        return True
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")
        return False

def send_test():
    if not bot:
        print("Bot not configured")
        return
    bot.send_message(config.TELEGRAM_CHAT_ID, "✅ myauto-profit-bot connected successfully!")
