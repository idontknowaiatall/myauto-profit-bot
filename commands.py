"""
Interactive Telegram commands. The bot listens for text messages like:
    2021 above benz c class under 30000
    toyota prius 2022+ under 40000 mileage under 80000
    bmw x5 under 35000
The search overrides year/price/mileage with YOUR numbers, but still applies
every fixed program filter: fuel (no diesel), banned American brands,
"on the way to Georgia" exclusion, VIN-prefix ban, and risk heuristics.
"""
import re
import threading
import telebot
import config
import scraper
import market
import notifier

SEARCH_PAGES = 2          # ~60 listings scanned per search
MAX_RESULTS_SHOWN = 10
MAX_DETAILS_CHECKED = 30  # politeness cap on detail requests per search

HELP_TEXT = """🤖 <b>myauto Profit Bot</b>

I scan myauto.ge every 8-12 min and send you underpriced cars automatically.

<b>You can also search step by step with buttons:</b> send <code>/search</code>
and I'll ask you: manufacturer → model → year → mileage → price.

<b>Or just type what you want:</b> just type what you want, e.g.
<code>2021 above benz c class under 30000</code>
<code>toyota prius 2022+ under 40000 km 80000</code>
<code>bmw x5</code>

I understand:
• year: <code>2021</code> or <code>2021+</code> (from that year)
• price: <code>under 30000</code> / <code>below $30000</code>
• mileage: <code>km 80000</code> / <code>under 80000 km</code>
• the rest of the words are used as search keywords

Every result still passes the fixed checks: no diesel ⛽, no American brands,
no "on the way to Georgia" 🚚, VIN registered 🔢, risk inspection 🛡.

/search - step-by-step search with buttons
/help - show this message
"""

_STOPWORDS = {"under", "over", "above", "below", "less", "than", "more", "max",
              "minimum", "min", "for", "from", "with", "and", "the", "a", "an",
              "newer", "older", "cheaper", "price", "year", "mileage", "km",
              "class", "up", "to", "dollars", "usd", "$"}

def parse_query(text):
    """Parse a natural language query into API filters."""
    q = text.lower().replace(",", "")
    year = None
    price = None
    mileage = None

    # 1) mileage: "<N> km" (extract first so it isn't confused with price)
    m = re.search(r"(\d{2,6})\s*k?\s*km\b", q)
    if m:
        mileage = int(m.group(1))
        q = q.replace(m.group(0), " ")

    # 2) year: 1900-2029, optional trailing +
    m = re.search(r"\b(19\d{2}|20[0-2]\d)\b\s*\+?", q)
    if m:
        year = int(m.group(1))
        q = q.replace(m.group(0), " ")

    # 3) price: "under/below/less than N" or a bare 4-6 digit number
    m = re.search(r"(?:under|below|less than|cheaper than|max)\s*\$?\s*(\d{3,6})", q)
    if m:
        price = int(m.group(1))
        q = q.replace(m.group(0), " ")
    else:
        m2 = re.search(r"\$?(\d{4,6})\b", q)
        if m2 and not (1900 <= int(m2.group(1)) <= 2030):
            price = int(m2.group(1))
            q = q.replace(m2.group(0), " ")

    words = [w.strip("+$") for w in q.split()]
    words = [w for w in words if w and w not in _STOPWORDS and not re.fullmatch(r"\d{1,2}", w)]
    keyword = " ".join(words).strip()
    return {"year": year, "price": price, "mileage": mileage, "keyword": keyword}

def _describe(p):
    parts = []
    if p["keyword"]:
        parts.append(f"🔎 {p['keyword']}")
    if p["year"]:
        parts.append(f"📅 {p['year']}+")
    if p["price"]:
        parts.append(f"💵 up to ${p['price']:,}")
    if p["mileage"]:
        parts.append(f"🏁 up to {p['mileage']:,} km")
    return "  ".join(parts) if parts else "all new listings"

def search_cars(p, client=None, pages=SEARCH_PAGES):
    """Run the search against myauto + local filters.
    p: year/price/price_min/mileage/mileage_min/keyword
    client: optional extra predicate applied to each car (e.g. exact man/model).
    Returns list of (car, info)."""
    params = {"TypeID": config.SEARCH_PARAMS["TypeID"], "ForRent": "0", "CurrencyID": "1"}
    if p.get("year"):
        params["ProdYearFrom"] = str(p["year"])
    if p.get("price"):
        params["PriceTo"] = str(p["price"])
    if p.get("price_min"):
        params["PriceFrom"] = str(p["price_min"])
    if p.get("mileage"):
        params["MileageTo"] = str(p["mileage"])
    if p.get("mileage_min"):
        params["MileageFrom"] = str(p["mileage_min"])
    if p.get("keyword"):
        params["Keyword"] = p["keyword"]

    session = scraper.make_session()
    cars = []
    for page in range(1, pages + 1):
        req = dict(params)
        req["Page"] = page
        try:
            resp = session.get(config.API_URL, params=req, timeout=config.API_TIMEOUT)
            resp.raise_for_status()
            items = scraper._extract_items(resp.json()) or []
        except Exception as e:
            print(f"[SEARCH] page {page} failed: {e}")
            break
        if not items:
            break
        cars.extend(items)
        if page < pages:
            import time as _t
            _t.sleep(config.REQUEST_DELAY_SEC + 1)

    # interactive search: YOUR year/price override the defaults; everything
    # else (fuel, brands, location, VIN) stays fixed
    rules = dict(config.PROFIT_RULES)
    if p.get("year"):
        rules["min_year"] = p["year"]
    if p.get("price"):
        rules["max_price"] = p["price"]
    if p.get("price_min"):
        rules["min_price"] = max(p["price_min"], 0)
    if p.get("mileage"):
        rules["max_mileage"] = p["mileage"]
    if p.get("mileage_min"):
        rules["min_mileage"] = p["mileage_min"]

    market_data = market.load_market()
    results = []
    details_checked = 0
    for car in cars:
        ok, _ = scraper.is_basic_profitable(car, rules)
        if not ok:
            continue
        if client and not client(car):
            continue
        if details_checked >= MAX_DETAILS_CHECKED:
            break
        details_checked += 1
        detail = scraper.fetch_detail(session, str(car.get("car_id")))
        okf, info = scraper.check_full_profitable(car, detail, market_data)
        if okf:
            results.append((car, info))
        if len(results) >= MAX_RESULTS_SHOWN:
            break
    return results

def handle_query(bot, chat_id, text):
    try:
        p = parse_query(text)
        if not (p["keyword"] or p["year"] or p["price"] or p["mileage"]):
            bot.send_message(chat_id, HELP_TEXT)
            return
        bot.send_message(chat_id, f"🔍 Searching myauto for: {_describe(p)} ...\n(this takes up to a minute)")
        results = search_cars(p)
        if not results:
            bot.send_message(chat_id, f"Nothing passed all checks for: {_describe(p)}\nTry loosening the year or price.")
            return
        bot.send_message(chat_id, f"✅ {len(results)} car(s) passed all checks:")
        for car, info in results:
            notifier.send_car(car, info)
    except Exception as e:
        print(f"[SEARCH] error: {e}")
        try:
            bot.send_message(chat_id, f"⚠️ Search failed: {e}")
        except Exception:
            pass

def register_handlers(bot: telebot.TeleBot):
    @bot.message_handler(commands=["start", "help"])
    def _help(m):
        bot.send_message(m.chat.id, HELP_TEXT)

    @bot.message_handler(commands=["search"])
    def _search(m):
        wizard_start(bot, m.chat.id)

    @bot.message_handler(func=lambda m: True)
    def _any(m):
        text = (m.text or "").strip()
        if text.startswith("/"):
            bot.send_message(m.chat.id, "Unknown command. " + HELP_TEXT)
            return
        if text.lower() in ("status", "ping"):
            bot.send_message(m.chat.id, "🟢 I'm running and scanning every 8-12 min.")
            return
        # wizard free-text step (custom mileage/price range)?
        w = WIZARDS.get(m.chat.id)
        if w and w.get("expect"):
            wizard_handle_text(bot, m.chat.id, text)
            return
        # run the search in the background so polling keeps working
        threading.Thread(target=handle_query, args=(bot, m.chat.id, text), daemon=True).start()

    @bot.callback_query_handler(func=lambda c: True)
    def _callback(c):
        try:
            wizard_callback(bot, c)
        except Exception as e:
            print(f"[WIZARD] error: {e}")
            try:
                bot.answer_callback_query(c.id, "Error, try again")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Button wizard: manufacturer -> model -> year -> mileage -> price -> search
# ---------------------------------------------------------------------------
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

WIZARDS = {}          # chat_id -> wizard state
PAGE_SIZE = 20        # buttons per page for man/model lists
WIZARD_PAGES = 5      # pages of listings scanned for a wizard search

_appdata_cache = None

def _appdata():
    """Load manufacturer list from myauto appdata (cached)."""
    global _appdata_cache
    if _appdata_cache is None:
        import cloudscraper
        s = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "darwin", "desktop": True})
        s.headers.update({"Referer": "https://www.myauto.ge/", "Accept": "application/json"})
        d = s.get("https://api2.myauto.ge/appdata/other_light_ka.json", timeout=30).json()
        mans = sorted([m for m in d["CatMans"] if m.get("is_car")], key=lambda m: m["man_name"])
        _appdata_cache = mans
    return _appdata_cache

def harvest_models(man_name, pages=3):
    """Discover real (model_id, model_name) pairs for a brand from live
    listings - the appdata catalog uses different ID spaces than the search API.
    Returns (listing_man_id, [(model_id, model_name), ...])."""
    session = scraper.make_session()
    man_id, models = None, {}
    for page in range(1, pages + 1):
        try:
            resp = session.get(config.API_URL, timeout=config.API_TIMEOUT,
                               params={"TypeID": "0", "ForRent": "0", "CurrencyID": "1",
                                       "Page": page, "Keyword": man_name})
            resp.raise_for_status()
            items = scraper._extract_items(resp.json()) or []
        except Exception as e:
            print(f"[WIZARD] harvest page {page} failed: {e}")
            break
        if not items:
            break
        for it in items:
            if (it.get("man_name") or "").strip().lower() == man_name.strip().lower():
                man_id = it.get("man_id")
                if it.get("model_id"):
                    models[it["model_id"]] = it.get("model_name") or "?"
        if page < pages:
            import time as _t
            _t.sleep(config.REQUEST_DELAY_SEC + 1)
    return man_id, sorted(models.items(), key=lambda kv: str(kv[1]))

def _kb(rows):
    kb = InlineKeyboardMarkup()
    for row in rows:
        kb.row(*row)
    return kb

def _pager(items, page):
    n = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(1, page), n)
    return items[(page - 1) * PAGE_SIZE: page * PAGE_SIZE], page, n

def _nav_row(prefix, page, n):
    row = []
    if page > 1:
        row.append(InlineKeyboardButton("◀️", callback_data=f"{prefix}:{page-1}"))
    row.append(InlineKeyboardButton(f"{page}/{n}", callback_data="w:noop"))
    if page < n:
        row.append(InlineKeyboardButton("▶️", callback_data=f"{prefix}:{page+1}"))
    return row

def _send_step(bot, chat_id, text, kb, edit_msg=None):
    if edit_msg:
        try:
            bot.edit_message_text(text, chat_id, edit_msg.message_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)

def _cancel_row():
    return [InlineKeyboardButton("❌ Cancel", callback_data="w:cancel")]

def wizard_start(bot, chat_id, edit_msg=None):
    mans = _appdata()
    WIZARDS[chat_id] = {"step": "man"}
    page_items, page, n = _pager(mans, 1)
    rows = [[InlineKeyboardButton(m["man_name"], callback_data=f"w:man:{m['man_name']}")
             for m in page_items[i:i+2]] for i in range(0, len(page_items), 2)]
    kb = _kb([r for r in rows if r])
    kb.row(*_nav_row("w:mpage", page, n))
    kb.row(*_cancel_row())
    _send_step(bot, chat_id, "🔍 <b>Step 1/5 — Manufacturer</b>\nChoose the brand:", kb, edit_msg=edit_msg)

def _wizard_man_kb(page):
    mans = _appdata()
    page_items, page, n = _pager(mans, page)
    rows = [[InlineKeyboardButton(m["man_name"], callback_data=f"w:man:{m['man_name']}")
             for m in page_items[i:i+2]] for i in range(0, len(page_items), 2)]
    kb = _kb([r for r in rows if r])
    kb.row(*_nav_row("w:mpage", page, n))
    kb.row(*_cancel_row())
    return kb

def _wizard_model_kb(w, page):
    models = w.get("models") or []
    page_items, page, n = _pager(models, page)
    rows = [[InlineKeyboardButton(name, callback_data=f"w:mod:{mid}")
             for mid, name in page_items[i:i+2]] for i in range(0, len(page_items), 2)]
    kb = _kb([r for r in rows if r])
    if models:
        kb.row(*_nav_row("w:dpage", page, n))
    kb.row(InlineKeyboardButton("🌐 Any model", callback_data="w:mod:0"),
           InlineKeyboardButton("◀️ Change brand", callback_data="w:backman"))
    kb.row(*_cancel_row())
    return kb

def _wizard_year_kb():
    kb = _kb([[InlineKeyboardButton(t, callback_data=f"w:year:{v}")] for t, v in
              [("Any year", 0), ("2023+", 2023), ("2022+", 2022), ("2021+", 2021),
               ("2020+", 2020), ("2019+", 2019), ("2018+", 2018), ("2015+", 2015)]])
    kb.row(*_cancel_row())
    return kb

def _range_kb(prefix):
    kb = _kb([
        [InlineKeyboardButton("Any", callback_data=f"{prefix}:0-0"),
         InlineKeyboardButton("0 - 30,000", callback_data=f"{prefix}:0-30000")],
        [InlineKeyboardButton("0 - 50,000", callback_data=f"{prefix}:0-50000"),
         InlineKeyboardButton("0 - 80,000", callback_data=f"{prefix}:0-80000")],
        [InlineKeyboardButton("30,000 - 80,000", callback_data=f"{prefix}:30000-80000"),
         InlineKeyboardButton("50,000 - 150,000", callback_data=f"{prefix}:50000-150000")],
        [InlineKeyboardButton("80,000 - 150,000", callback_data=f"{prefix}:80000-150000"),
         InlineKeyboardButton("150,000+", callback_data=f"{prefix}:150000-0")],
    ])
    kb.row(InlineKeyboardButton("✍️ Type custom (e.g. 5000-25000)", callback_data=f"{prefix}:custom"))
    kb.row(*_cancel_row())
    return kb

def _range_label(lo, hi):
    lo = int(lo or 0); hi = int(hi or 0)
    if not lo and not hi: return "any"
    if not hi: return f"{lo:,}+"
    return f"{lo:,} - {hi:,}"

def _wizard_summary_kb():
    kb = _kb([[InlineKeyboardButton("🔎 Search now", callback_data="w:go"),
               InlineKeyboardButton("🔄 Start over", callback_data="w:restart")]])
    kb.row(*_cancel_row())
    return kb

def _summary_text(w):
    return (f"📋 <b>Your search:</b>\n"
            f"🏭 {w.get('man_name', 'any brand')} — {w.get('model_name') or 'any model'}\n"
            f"📅 Year: {str(w['year']) + '+' if w.get('year') else 'any'}\n"
            f"🏁 Mileage: {_range_label(w.get('mile_lo'), w.get('mile_hi'))} km\n"
            f"💵 Price: {_range_label(w.get('price_lo'), w.get('price_hi'))} $\n\n"
            f"All fixed checks still apply (VIN, location, fuel, risk).")

def _load_models_async(bot, chat_id, man_name, edit_msg):
    """Fetch real model list from live listings in the background."""
    w = WIZARDS.get(chat_id)
    man_id, models = harvest_models(man_name)
    if w is None or w.get("step") != "models_loading":
        return  # user cancelled or restarted meanwhile
    w["man_id"] = man_id
    w["models"] = models
    w["step"] = "model"
    bot.send_message(chat_id, f"🔍 <b>Step 2/5 — Model</b>", reply_markup=_wizard_model_kb(w, 1))

def wizard_callback(bot, c):
    data = c.data or ""
    chat_id = c.message.chat.id
    if data == "w:noop":
        bot.answer_callback_query(c.id)
        return

    if data == "w:cancel":
        WIZARDS.pop(chat_id, None)
        bot.answer_callback_query(c.id, "Cancelled")
        bot.send_message(chat_id, "❌ Search cancelled. Send /search to start again or just type a query.")
        return
    if data == "w:restart":
        bot.answer_callback_query(c.id)
        wizard_start(bot, chat_id, edit_msg=c.message)
        return

    w = WIZARDS.get(chat_id)
    if w is None:
        bot.answer_callback_query(c.id, "Press /search to start")
        return

    if data == "w:backman":
        w["step"] = "man"
        bot.answer_callback_query(c.id)
        _send_step(bot, chat_id, "🔍 <b>Step 1/5 — Manufacturer</b>", _wizard_man_kb(1), edit_msg=c.message)
        return

    if data.startswith("w:mpage:"):
        bot.answer_callback_query(c.id)
        _send_step(bot, chat_id, "🔍 <b>Step 1/5 — Manufacturer</b>", _wizard_man_kb(int(data.split(":")[2])), edit_msg=c.message)
        return

    if data.startswith("w:man:"):
        man_name = data.split(":", 2)[2]
        w.clear()
        w["step"] = "models_loading"
        w["man_name"] = man_name
        bot.answer_callback_query(c.id)
        try:
            bot.edit_message_text(f"⏳ Loading {man_name} models from live listings...",
                                  chat_id, c.message.message_id)
        except Exception:
            pass
        threading.Thread(target=_load_models_async, args=(bot, chat_id, man_name, c.message), daemon=True).start()
        return

    if data.startswith("w:dpage:"):
        bot.answer_callback_query(c.id)
        _send_step(bot, chat_id, "🔍 <b>Step 2/5 — Model</b>", _wizard_model_kb(w, int(data.split(":")[2])), edit_msg=c.message)
        return

    if data.startswith("w:mod:"):
        mid = int(data.split(":")[2])
        w["model_id"] = mid or None
        w["model_name"] = next((name for mid2, name in (w.get("models") or []) if mid2 == mid), None)
        w["step"] = "year"
        bot.answer_callback_query(c.id)
        _send_step(bot, chat_id, "🔍 <b>Step 3/5 — Year</b>", _wizard_year_kb(), edit_msg=c.message)
        return

    if data.startswith("w:year:"):
        v = int(data.split(":")[2])
        w["year"] = v or None
        w["step"] = "mileage"
        bot.answer_callback_query(c.id)
        _send_step(bot, chat_id, "🔍 <b>Step 4/5 — Mileage (km)</b>", _range_kb("w:mile"), edit_msg=c.message)
        return

    if data.startswith("w:mile:"):
        arg = data.split(":", 2)[2]
        if arg == "custom":
            w["expect"] = "mileage"
            bot.answer_callback_query(c.id)
            _send_step(bot, chat_id, "✍️ Send the mileage range as: <code>min-max</code>\nExample: <code>20000-80000</code>", None)
            return
        lo, hi = (arg.split("-") + ["0"])[:2]
        w["mile_lo"], w["mile_hi"] = int(lo or 0), int(hi or 0)
        w["step"] = "price"
        bot.answer_callback_query(c.id)
        _send_step(bot, chat_id, "🔍 <b>Step 5/5 — Price ($)</b>", _range_kb("w:price"), edit_msg=c.message)
        return

    if data.startswith("w:price:"):
        arg = data.split(":", 2)[2]
        if arg == "custom":
            w["expect"] = "price"
            bot.answer_callback_query(c.id)
            _send_step(bot, chat_id, "✍️ Send the price range as: <code>min-max</code>\nExample: <code>5000-25000</code>", None)
            return
        lo, hi = (arg.split("-") + ["0"])[:2]
        w["price_lo"], w["price_hi"] = int(lo or 0), int(hi or 0)
        w["step"] = "ready"
        bot.answer_callback_query(c.id)
        _send_step(bot, chat_id, _summary_text(w), _wizard_summary_kb(), edit_msg=c.message)
        return

    if data == "w:go":
        bot.answer_callback_query(c.id, "Searching...")
        _send_step(bot, chat_id, "🔎 Searching... this takes up to a minute.")
        WIZARDS.pop(chat_id, None)
        threading.Thread(target=wizard_run, args=(bot, chat_id, w), daemon=True).start()
        return

    bot.answer_callback_query(c.id)

def wizard_handle_text(bot, chat_id, text):
    w = WIZARDS.get(chat_id)
    expect = w.get("expect")
    m = re.match(r"^\s*(\d+)\s*[-–]\s*(\d+)\s*$", text)
    if not m:
        bot.send_message(chat_id, "Please send the range as <code>min-max</code>, e.g. <code>5000-25000</code>")
        return
    lo, hi = int(m.group(1)), int(m.group(2))
    w.pop("expect", None)
    if expect == "mileage":
        w["mile_lo"], w["mile_hi"] = lo, hi
        bot.send_message(chat_id, "🔍 <b>Step 5/5 — Price ($)</b>", reply_markup=_range_kb("w:price"))
    else:
        w["price_lo"], w["price_hi"] = lo, hi
        bot.send_message(chat_id, _summary_text(w), reply_markup=_wizard_summary_kb())

def wizard_run(bot, chat_id, w):
    try:
        p = {"keyword": w.get("man_name") or "", "year": w.get("year"),
             "price": w.get("price_hi") or None, "price_min": w.get("price_lo") or None,
             "mileage": w.get("mile_hi") or None, "mileage_min": w.get("mile_lo") or None}
        man_name = (w.get("man_name") or "").lower()
        model_id = w.get("model_id")

        def client(car):
            if (car.get("man_name") or "").strip().lower() != man_name:
                return False
            if model_id and str(car.get("model_id")) != str(model_id):
                return False
            return True

        results = search_cars(p, client=client, pages=WIZARD_PAGES)
        if not results:
            bot.send_message(chat_id, f"Nothing passed all checks for:\n{_summary_text(w)}\n\nTry a wider year or price range.")
            return
        bot.send_message(chat_id, f"✅ {len(results)} car(s) passed all checks:")
        for car, info in results:
            notifier.send_car(car, info)
    except Exception as e:
        print(f"[WIZARD] search error: {e}")
        try:
            bot.send_message(chat_id, f"⚠️ Search failed: {e}")
        except Exception:
            pass
