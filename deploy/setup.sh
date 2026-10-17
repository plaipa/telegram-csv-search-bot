#!/usr/bin/env bash
# Install the bot on Ubuntu (e.g. Oracle Cloud) and run it as a systemd service.
# Usage: bash deploy/setup.sh   (run again after editing .env or pulling updates)
set -euo pipefail
cd "$(dirname "$0")/.."
APP_DIR=$(pwd)

sudo apt-get update -q
sudo apt-get install -y -q python3-venv python3-pip tmux git
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
# Optional C speed-up for downloads; only use a prebuilt wheel (no compiler needed).
.venv/bin/pip install -q --only-binary=:all: cryptg || echo "cryptg unavailable: downloads will be slower"

if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env
    echo ">>> Fill in .env (nano .env), then run: bash deploy/setup.sh"
    exit 0
fi

sed -e "s|@APP_DIR@|$APP_DIR|g" -e "s|@USER@|$(whoami)|g" deploy/csvbot.service \
    | sudo tee /etc/systemd/system/csvbot.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable csvbot
sudo systemctl restart csvbot
echo ">>> Bot is running. Logs: journalctl -u csvbot -f"
