# Running the bot 24/7 (Mac-independent)

The bot must run on a computer that never sleeps. Best **free** option:
Oracle Cloud "Always Free" VM. Any cheap VPS (Hetzner, DigitalOcean, etc.)
works identically.

## Step 1 — Get a free server (Oracle Cloud Always Free)

1. Go to https://www.oracle.com/cloud/free/ and sign up (needs a card for
   verification, but the Always Free tier never charges).
2. Create an instance:
   - Image: **Ubuntu 22.04** (or newer)
   - Shape: **Ampere A1** (ARM), 2 OCPU / 12 GB — the free tier allows this
   - Download the SSH key when asked.
3. Note the server's public IP address.

## Step 2 — Copy the bot folder to the server

From your Mac:

```bash
cd ~/Downloads
scp -i /path/to/your-ssh-key -r myauto-profit-bot ubuntu@SERVER_IP:~/
scp -i /path/to/your-ssh-key myauto-profit-bot/.env ubuntu@SERVER_IP:~/myauto-profit-bot/
```

(The `.env` holds your Telegram token — don't skip the second command.)

## Step 3 — Install and start

```bash
ssh -i /path/to/your-ssh-key ubuntu@SERVER_IP
cd ~/myauto-profit-bot
sudo bash deploy.sh
```

That's it. The bot is now a system service (`myauto-bot`):
- starts automatically on every server boot
- restarts itself within 60s if it ever crashes
- logs to `bot.log` in the folder

Verify: your Telegram should receive the "✅ connected" message within a
minute, and `systemctl status myauto-bot` should say `active (running)`.

## Useful commands on the server

| What                    | Command                        |
|-------------------------|--------------------------------|
| Status                  | `systemctl status myauto-bot`  |
| Live logs               | `tail -f bot.log`              |
| Restart                 | `sudo systemctl restart myauto-bot` |
| Stop                    | `sudo systemctl stop myauto-bot`    |
| Change filters/config   | edit `config.py`, then restart |

## Important

- **Stop the Mac copy** before the server copy runs, or both will scan
  myauto and you'll get duplicate Telegram messages (double-click
  `stop_bot.command` on the Mac).
- Optionally copy `seen.json` and `market_data.json` to the server too, so
  the bot keeps its memory and market-price history without starting over.
