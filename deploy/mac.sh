#!/usr/bin/env bash
# One-step install and start on macOS. Run from the project folder:
#   bash deploy/mac.sh
# Reuses BOT_TOKEN/ADMIN_IDS/ALLOWED_USER_IDS/PROXY from an older copy's .env
# in ~/Downloads (DB-old, DB-prev, DB-master...), installs dependencies,
# checks the setup and starts the bot in the background.
set -euo pipefail
cd "$(dirname "$0")/.."
APP_DIR=$(pwd)

if [ ! -f .env ]; then
    cp .env.example .env
    for old in ~/Downloads/DB-old/.env ~/Downloads/DB-prev/.env ~/Downloads/DB-master*/.env; do
        [ -f "$old" ] && [ "$old" != "$APP_DIR/.env" ] || continue
        echo ">>> Copying settings from $old"
        for key in BOT_TOKEN ADMIN_IDS ALLOWED_USER_IDS PROXY; do
            line=$(grep -E "^$key=" "$old" | tail -1 || true)
            [ -n "$line" ] || continue
            grep -v -E "^$key=" .env > .env.tmp && mv .env.tmp .env
            printf '%s\n' "$line" >> .env
        done
        break
    done
    chmod 600 .env
fi

if ! grep -qE '^BOT_TOKEN=[0-9]+:' .env; then
    echo ">>> BOT_TOKEN is missing. Opening .env; paste the token from @BotFather, save, then run this script again."
    open -e .env
    exit 1
fi

echo ">>> Installing dependencies..."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo ">>> Checking setup..."
.venv/bin/python -m csvbot.check || true

# Bracket patterns so the match never hits a shell whose command line merely mentions the bot.
if pgrep -f "[.]venv/bin/python -m csvbot[.]bot" >/dev/null; then
    echo ">>> Stopping the bot that is already running"
    pkill -f "[.]venv/bin/python -m csvbot[.]bot" || true
    sleep 2
fi

echo ">>> Starting the bot in the background (log: $APP_DIR/bot.log)"
nohup caffeinate -i .venv/bin/python -m csvbot.bot > bot.log 2>&1 &
BOT_PID=$!
sleep 10
tail -n 20 bot.log
echo
if ! kill -0 "$BOT_PID" 2>/dev/null; then
    echo ">>> The bot stopped; see the error above (and the check output)."
    exit 1
fi
echo ">>> Done. Send /start to your bot and search for: علی"
echo ">>> Put your CSV/DB files in: $APP_DIR/data"
echo ">>> Stop the bot: pkill -f '[.]venv/bin/python -m csvbot[.]bot'"
