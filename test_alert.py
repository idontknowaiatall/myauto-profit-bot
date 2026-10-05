"""Send a test alert through the real Telegram code path (pipeline check)."""
import notifier
import config

def main():
    print("token configured:", bool(config.TELEGRAM_BOT_TOKEN))
    print("chat id:", config.TELEGRAM_CHAT_ID)
    notifier.send_test()

    # a clearly-marked fake car, sent through the SAME format function the
    # real alerts use - verifies photo/caption path and full card layout
    car = {
        "car_id": 123456789,
        "man_name": "TEST",
        "model_name": "Pipeline Check (not a real car)",
        "prod_year": 2022,
        "price_usd": 15000,
        "car_run_km": 60000,
        "engine_volume": 1600,
        "fuel_type_id": 2,
        "customs_passed": True,
    }
    info = {
        "vin": "TESTVINCHECK12345",
        "avg": 16500,
        "discount": 9.1,
        "inspection": {"airbag_prob": 15, "panel_gap_prob": 20},
    }
    ok = notifier.send_car(car, info)
    print("test alert sent:", ok)

if __name__ == "__main__":
    main()
