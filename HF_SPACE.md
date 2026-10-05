# Running the bot FREE on Hugging Face Spaces (Gradio SDK, no card)

Hugging Face Spaces hosts apps free on the **Gradio** SDK — no card, no
Docker needed. The bot runs 24/7 there with full functionality (auto alerts
+ the interactive search wizard), behind a small status page.

## Step 1 — Create the account and Space

1. Sign up at https://huggingface.co (email only, no card).
2. Click **New → Space**.
   - Space name: `myauto-bot` (anything works)
   - SDK: **Gradio**  ← the FREE one (do NOT pick Docker)
   - Visibility: **Public** is fine — your Telegram token goes into a
     secret (step 2), never into the code.

## Step 2 — Add your secrets

In the Space: **Settings → Variables and secrets → New secret**

| Name                | Value                        |
|---------------------|------------------------------|
| TELEGRAM_BOT_TOKEN  | your bot token               |
| TELEGRAM_CHAT_ID    | your chat id (105258480)     |

## Step 3 — Upload the files

In the Space: **Files → Add file → Upload files**. Upload ALL of these
from this folder:

```
app.py  main.py  scraper.py  market.py  ai_inspector.py  notifier.py
config.py  commands.py  webserver.py
requirements.txt
```

Do NOT upload: `Dockerfile`, `.dockerignore`, `.env`, `seen.json`,
`bot.log`, the `.command` files, `HF_SPACE.md`.

The Space builds itself (~2 min). Then check your Telegram for the
"✅ connected" message. Visiting the Space URL shows a status page —
that's normal, the real work happens in Telegram.

## Step 4 — Keep it awake (important)

Free Spaces sleep after **48 hours without web visitors**. Wake it up with a
free uptime monitor:

1. Sign up at https://cron-job.org (free, no card).
2. Create a cron job that pings your Space URL every 15 minutes:
   `https://YOUR-USERNAME-myauto-bot.hf.space`
3. Done — it will never sleep.

## Notes & limits

- **Stop the Mac copy first** (double-click `stop_bot.command`) — two bots
  polling Telegram at once cause conflicts and duplicate alerts.
- Space restarts wipe `seen.json`/`market_data.json` — the bot rebuilds
  its memory and market averages over the next hours. Nothing else is lost.
- If the bot ever crashes inside the Space, `app.py` restarts it
  automatically after 60 seconds.
- If you change code later, re-upload the changed file(s) — the Space
  rebuilds automatically.
- To change the Telegram token later: edit the Space secrets, then
  "Factory rebuild" the Space.
