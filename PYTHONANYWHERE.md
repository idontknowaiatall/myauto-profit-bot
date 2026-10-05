# Running the bot FREE on PythonAnywhere (no credit card)

PythonAnywhere's free tier hosts a small web app forever. To fit its limits
(100 CPU-seconds/day, no background processes), this version works differently:

- Your Telegram messages arrive via **webhook** (Telegram pushes them to the
  web app) — near-zero idle CPU, interactive search and wizard still work.
- The scanner is triggered by a **free cron-job.org ping** every 30-60 min
  hitting `/scan`.
- Scans use fewer pages by default (`MAX_PAGES=3` in `.env`) to stay within
  the CPU allowance. Raise it if your usage stays low.

## Step 1 — Whitelist myauto (CRITICAL, do this first)

Free PythonAnywhere accounts can only reach a whitelist of websites, and
`api2.myauto.ge` is not on it by default.

1. Log in at pythonanywhere.com
2. Go to **Consoles** tab → click **"Add new site to whitelist"**
   (or open: https://www.pythonanywhere.com/user/YOUR-USERNAME/sites_whitelist_request/ )
3. Request: `api2.myauto.ge`
4. Wait for approval (usually fast). If they refuse it, the bot cannot fetch
   data on PythonAnywhere — tell me and we switch to the Mac version only.

## Step 2 — Sign up and upload the files

1. Create a free account (email only, no card).
2. Zip the `myauto-profit-bot` folder on your Mac, then on PythonAnywhere:
   **Files → Upload a file** (upload the zip into `/home/USERNAME/`)
3. Open a **Bash console** and run:
   ```bash
   cd ~
   unzip myauto-profit-bot.zip
   pip3.10 install --user -r ~/myauto-profit-bot/requirements.txt
   ```

## Step 3 — Configure .env

Edit `~/myauto-profit-bot/.env` (Files tab → click the file) and add these
two lines, replacing YOUR-USERNAME:

```
SITE_URL=YOUR-USERNAME.pythonanywhere.com
WEBHOOK_SECRET=pick-a-random-word-here
MAX_PAGES=3
```

(Keep TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as they are.)

## Step 4 — Create the web app

1. **Web** tab → **Add a new web app** → (free domain) →
   **Manual configuration** → **Python 3.10**
2. On the Web tab, set **Source code** to `/home/USERNAME/myauto-profit-bot`
3. Click the WSGI configuration file link (top of Web tab). Delete everything
   in it and replace with:
   ```python
   import sys
   sys.path.insert(0, "/home/USERNAME/myauto-profit-bot")
   from webapp import app as application
   ```
4. **Reload** the web app (green button).
5. Visit `https://YOUR-USERNAME.pythonanywhere.com/` — you should see
   "myauto profit bot web app is running".

## Step 5 — Connect Telegram (one-time)

**First stop the Mac copy** (double-click `stop_bot.command`) — Telegram
allows only one connection mode at a time.

Then visit (replace SECRET with your WEBHOOK_SECRET):

```
https://YOUR-USERNAME.pythonanywhere.com/setup?key=SECRET
```

You should see "✅ webhook set". Send your bot a message — it answers.
Send `/help` to see everything.

## Step 6 — Automatic scanning

1. Sign up at https://cron-job.org (free, no card)
2. Create a cron job: URL = `https://YOUR-USERNAME.pythonanywhere.com/scan`,
   every 30 minutes.
3. Done — profitable cars arrive automatically, and the wizard works on demand.

## Notes

- **100 CPU-seconds/day limit**: with MAX_PAGES=3 and hourly pings you use
  roughly half of it. If PythonAnywhere emails you about CPU, increase the
  ping interval to every 60 minutes.
- The web app keeps running 24/7; scheduled pings run the scans.
- Code changes: upload the changed file(s), then **Reload** on the Web tab.
