#!/bin/bash
# Double-click this file to STOP the myauto profit bot
if pkill -f "main.py"; then
    echo "🛑 Bot stopped."
else
    echo "Bot was not running."
fi
read -p "Press Enter to close this window..."
