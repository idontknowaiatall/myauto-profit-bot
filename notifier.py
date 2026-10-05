import telebot
import config

FUEL_TYPES = config.FUEL_TYPES

bot = None
if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_BOT_TOKEN != "1234567890:AAH_example_token_here":
    bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN, parse_mode="HTML")
else:
    print("[WARN] TELEGRAM_BOT_TOKEN not set - notifications disabled. Set it in .env")

def escape_html(text):
    if text is None:
        return ""
    return str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

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
    link = f"https://www.myauto.ge/ka/pr/{car_id}"
    photos = info.get("photo_urls") or []
    photo = photos[0] if photos else ""

    text = f"""🚗 <b>Profitable Car Found!</b>

<b>{man} {model} {year}</b>
💵 Price: <b>${price}</b>
🏁 Mileage: {mileage} km
⛽ Engine: {engine_txt}
🛃 Customs: {customs}
"""
    vin = info.get("vin")
    if vin:
        text += f"🔢 VIN: <code>{escape_html(vin)}</code>\n"
    if info.get("avg"):
        text += f"📊 Market avg: ${info['avg']} ({info.get('discount', 0)}% below)\n"
    inspection = info.get("inspection") or {}
    text += f"🛡 Risk check: airbag {inspection.get('airbag_prob', '?')}% / panel {inspection.get('panel_gap_prob', '?')}%\n"
    text += f"\n🔗 <a href=\"{link}\">{link}</a>\n🆔 ID: {car_id}\n"
    return text, photo, link

def send_car(car, info=None):
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
                bot.send_photo(config.TELEGRAM_CHAT_ID, photo, caption=text)
                print(f"[SENT] Photo + caption for {car.get('car_id')}")
                return True
            except Exception as e:
                print(f"[WARN] Photo send failed {e}, falling back to text")
        bot.send_message(config.TELEGRAM_CHAT_ID, text, disable_web_page_preview=False)
        print(f"[SENT] Text for {car.get('car_id')}")
        return True
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")
        return False

def send_test():
    if not bot:
        print("Bot not configured")
        return
    bot.send_message(config.TELEGRAM_CHAT_ID, "✅ myauto-profit-bot connected successfully!")
