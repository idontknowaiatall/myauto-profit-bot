#!/bin/bash
# Run this ON THE SERVER:  sudo bash deploy.sh
# Sets up the bot as a system service that starts on boot and restarts if it crashes.
set -e
cd "$(dirname "$0")"

echo "==> Installing Python..."
apt-get update -y
apt-get install -y python3 python3-venv python3-pip

echo "==> Creating virtualenv and installing dependencies..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "==> Installing systemd service..."
cp myauto-bot.service /etc/systemd/system/myauto-bot.service
# make sure the log file exists and is writable
touch bot.log
chmod 666 bot.log
systemctl daemon-reload
systemctl enable myauto-bot      # start on boot
systemctl restart myauto-bot

echo ""
echo "✅ Bot installed as a 24/7 service."
echo ""
echo "Useful commands:"
echo "  systemctl status myauto-bot    # is it running?"
echo "  tail -f bot.log                # live activity"
echo "  systemctl stop myauto-bot      # stop"
echo "  systemctl start myauto-bot     # start"
echo "  journalctl -u myauto-bot -n 50 # recent errors"
echo ""
systemctl status myauto-bot --no-pager || true
