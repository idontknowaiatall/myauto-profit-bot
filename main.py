"""
Main loop for myauto.ge profit bot
Run: python main.py
"""
import time
import random
import threading
import traceback
import scraper
import notifier
import config
import commands
import webserver

MAX_ALERTS_PER_RUN = 15  # avoid telegram flood limits

def run_once():
    seen = scraper.load_seen()
    market_data = scraper.market.load_market()
    cars = scraper.fetch_all_new_cars()
    print(f"[LOOP] Fetched {len(cars)} cars, seen cache {len(seen)}")
    new_profitable = 0
    alerts_sent = 0
    for car in cars:
        car_id = str(car.get("car_id") or car.get("id"))
        if not car_id or car_id in seen:
            continue
        seen.add(car_id)

        ok_basic, reason = scraper.is_basic_profitable(car)
        if not ok_basic:
            continue

        session = scraper.make_session()
        detail = scraper.fetch_detail(session, car_id)
        ok_full, info = scraper.check_full_profitable(car, detail, market_data)
        if not ok_full:
            print(f"[SKIP] {car_id}: {info.get('reason')}")
            continue

        print(f"[HIT] {car_id} {car.get('man_name')} {car.get('model_name')} ${car.get('price_usd')} -> {info.get('reason')}")
        if alerts_sent < MAX_ALERTS_PER_RUN:
            if notifier.send_car(car, info):
                scraper.save_seen(seen)  # save immediately - a crash must never re-send
                time.sleep(1.5)  # don't spam telegram
                alerts_sent += 1
        new_profitable += 1

    scraper.save_seen(seen)
    # Build market averages from tonight's listings for future price-drop checks
    scraper.market.update_with_cars(cars)
    print(f"[LOOP] Done. New profitable: {new_profitable}, alerts sent: {alerts_sent}")
    return len(cars), new_profitable

def scan_loop():
    first = True
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[ERROR] Loop crash: {e}")
            traceback.print_exc()

        sleep_s = random.randint(config.CHECK_INTERVAL_MIN, config.CHECK_INTERVAL_MAX)
        if first:
            sleep_s = 30  # first quick confirmation cycle, then settle into rhythm
            first = False
        print(f"[SLEEP] {sleep_s//60}m {sleep_s%60}s until next check...")
        time.sleep(sleep_s)

def main(health=True):
    print("=== myauto Profit Bot Started ===")
    if health:
        webserver.start_health_server()  # needed for HF Docker Spaces; harmless at home
    print(f"Search params: {config.SEARCH_PARAMS}")
    print(f"Profit rules: {config.PROFIT_RULES}")
    print(f"Check interval: {config.CHECK_INTERVAL_MIN}-{config.CHECK_INTERVAL_MAX}s")
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        print("[WARN] Telegram not configured - fill .env to receive alerts")
        scan_loop()
        return

    try:
        notifier.send_test()
    except Exception as e:
        print(f"[WARN] Telegram test failed: {e}")

    # scanner runs in the background; the main thread listens for your messages
    t = threading.Thread(target=scan_loop, daemon=True)
    t.start()

    commands.register_handlers(notifier.bot)
    print("[BOT] Listening for your Telegram messages - try: 2021 above benz c class under 30000")
    notifier.bot.infinity_polling(skip_pending=True, timeout=20)

if __name__ == "__main__":
    main()
