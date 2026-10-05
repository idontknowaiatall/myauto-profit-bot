# myauto Profit Bot - Ban-Safe & 100% Free

Collects cars from `api2.myauto.ge` and sends profitable ones to Telegram.

**This folder is the PythonAnywhere version** (webhook-based, see
PYTHONANYWHERE.md). The original Mac version with all data lives in
`../myauto-profit-bot-mac/` (start with `start_bot.command`).

**No AI subscriptions, no paid APIs.** All risk checks (VIN check, market
price-drop comparison, airbag/panel-gap keyword heuristics) run locally. The
only external services are the free myauto API and the free Telegram Bot API.
`cloudscraper` (free, open-source) is used to pass myauto's Cloudflare check.

## Anti-Ban Features (IMPORTANT)
- Uses the current official API `https://api2.myauto.ge/ka/products` with `Referer: https://www.myauto.ge/ka/search`
- `cloudscraper` session with real Chrome User-Agent (passes Cloudflare)
- `2.5s + random` delay between pages, `5-10 min` between loops
- `Period=1h` - only scans NEW listings to avoid hammering
- `seen.json` cache prevents re-scraping same car
- Exponential backoff on `429 Too Many Requests`
- Caps at 10 pages per run, max 15 Telegram alerts per run

**Do NOT make it faster.** Faster = banned by Cloudflare.

## Setup (do this FIRST, before running)

1. Install deps:
```bash
pip install -r requirements.txt
```

2. **Set up the Telegram bot now** — you need it to see the results:
   - Open Telegram, talk to **@BotFather** → send `/newbot` → choose a name
     and username → **copy the bot token** (looks like `123456:AAH-xxx`).
   - Send any message to your new bot (press START) — this opens the chat.
   - Get your chat ID: send a message to **@userinfobot**, it replies with
     your numeric ID. (Or use a channel's `@username` as the chat ID.)
   - Create `.env`:
```bash
cp .env.example .env
# edit .env and paste your real TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
```

3. Tune profit rules in `config.py` -> `PROFIT_RULES`:
```python
"min_year": 2021,
"max_mileage": 99999,
"max_price": 50000,
"require_vin": True,
```

4. Test run (once, fetch + print only):
```bash
python scraper.py
```

5. Run the bot forever:
```bash
python main.py
# or in background: nohup python main.py &
```

The first thing `main.py` does is send `✅ myauto-profit-bot connected
successfully!` to your Telegram — if you see that, everything works and you
will receive car alerts there.

## How it works each loop
1. Fetch new listings (last 2h) from myauto API
2. Basic filter: year, mileage, price range, banned American brands
3. Fetch full detail per candidate, extract VIN (required)
4. Compare price vs. learned market average — need 5%+ below average
5. Local risk heuristics: airbag/panel-gap keywords, photo count, too-cheap flag
6. Send survivors to Telegram with photo, VIN, market avg and risk scores
7. Save all listings into `market_data.json` so averages improve over time

## Tuning the profit logic
- `config.py`: `PRICE_DROP_PERCENT`, `MAX_ALLOWED_AIRBAG_PROB`, `MAX_ALLOWED_PANEL_GAP_PROB`, `USE_PRICE_DROP_FILTER`
- `ai_inspector.py`: add/remove keywords for the risk heuristics

## Interactive search (new)
The bot also listens to your Telegram messages. Just type what you want:
```
2021 above benz c class under 30000
toyota prius 2022+ under 40000 km 80000
bmw x5
```
Your year/price/mileage numbers override the defaults for that search, but
every fixed filter still applies (no diesel, no American brands, no "on the
way to Georgia", VIN-prefix ban, risk inspection). `/help` shows usage.

## Safety Checklist Before Running 24/7
- [ ] `.env` has real token and chat id
- [ ] `CHECK_INTERVAL_MIN` >= 500
- [ ] Don't run multiple instances at once
- [ ] Keep `Period` as `1h` or larger, don't use backfill scans often
