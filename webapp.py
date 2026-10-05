"""
PythonAnywhere web app (Flask). Built for the FREE tier:
- Telegram messages arrive via WEBHOOK (no polling -> near-zero idle CPU)
- /scan  runs one scanner cycle (ping with cron-job.org every 30-60 min)
- /setup sets the Telegram webhook (run once, after the Mac copy is stopped)
"""
import os
import sys
import threading

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)

from flask import Flask, request
import telebot
import config
import notifier
import commands
import main as botmain

app = Flask(__name__)

if notifier.bot:
    commands.register_handlers(notifier.bot)
else:
    print("[WARN] no bot token - set .env on the server")

def _scan_safe():
    try:
        botmain.run_once()
        print("[SCAN] cycle done")
    except Exception as e:
        print(f"[SCAN] error: {e}")

@app.route("/")
def index():
    return "myauto profit bot web app is running", 200

@app.route("/scan")
def scan():
    threading.Thread(target=_scan_safe, daemon=True).start()
    return "scan started", 200

@app.route("/setup")
def setup():
    key = request.args.get("key", "")
    if key != config.WEBHOOK_SECRET:
        return "bad key", 403
    if not notifier.bot:
        return "no bot token in .env", 500
    if not config.SITE_URL:
        return "SITE_URL not set in .env", 500
    url = f"https://{config.SITE_URL}/webhook/{config.WEBHOOK_SECRET}"
    try:
        notifier.bot.delete_webhook(drop_pending_updates=False)
        notifier.bot.set_webhook(url, allowed_updates=["message", "callback_query"])
        return f"✅ webhook set: {url}", 200
    except Exception as e:
        return f"error: {e}", 500

@app.route(f"/webhook/{config.WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    if not notifier.bot:
        return "no bot token", 500
    update = request.get_json(force=True, silent=True)
    if not update:
        return "ok", 200
    # answer Telegram fast (it retries slow webhooks); process in background
    threading.Thread(
        target=notifier.bot.process_new_updates,
        args=([telebot.types.Update.de_json(update)],),
        daemon=True,
    ).start()
    return "ok", 200
