#!/bin/bash
# Double-click this file to START the myauto profit bot
cd "$(dirname "$0")"

if pgrep -f "main.py" > /dev/null; then
    echo "⚠️  Bot is ALREADY running - no need to start it again."
    echo "   To stop it first, double-click stop_bot.command"
    echo ""
    read -p "Press Enter to close this window..."
    exit 0
fi

nohup python3 -u main.py >> bot.log 2>&1 &
BOT_PID=$!
echo "✅ Bot started (process $BOT_PID)"
echo "   It checks myauto every 8-12 minutes and sends profitable cars to your Telegram."
echo "   You can close this window - the bot keeps running in the background."
echo ""
sleep 3
echo "──────── Last activity from bot.log ────────"
tail -6 bot.log
echo "─────────────────────────────────────────────"
echo ""
echo "To STOP the bot: double-click stop_bot.command"
read -p "Press Enter to close this window..."
