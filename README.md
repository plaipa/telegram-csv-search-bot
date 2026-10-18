<div align="center">

**English** · **[فارسی](README.fa.md)** · **[हिन्दी](README.hi.md)**

</div>

# Telegram CSV & SQLite Search Bot

> A free, open-source **Telegram bot that searches inside CSV, TSV and SQLite (`.db`) files**. Drop your files in a folder and search them from Telegram, even multi-gigabyte files. Full-text search with **Persian, Arabic, Hindi and English** text support. Runs on macOS, Windows, Linux and Docker.

Keywords: telegram bot, csv search, sqlite search, search csv in telegram, full-text search, FTS5, large csv files, python-telegram-bot, Persian / Farsi / Hindi / Arabic search.

## Features
- **Folder watching:** put `.csv`, `.tsv`, `.db`, `.sqlite`, `.sqlite3` files in `data/`. New files are indexed automatically, changed files are re-indexed, deleted files disappear from results.
- **Huge files:** CSV is streamed, so memory stays around 250 MB even for 3 GB+ files. A 6-million-row CSV indexes in about 2.5 minutes; most searches answer in under 200 ms (SQLite FTS5).
- **SQLite databases:** every table of every `.db` file is searchable (opened read-only).
- **Multilingual text:** Persian/Arabic letters (ي/ی, ك/ک), Persian/Arabic/Hindi (Devanagari) digits, Arabic diacritics and the Hindi nukta (फ़ = फ) are normalized, so `०९१२`, `۰۹۱۲` and `0912` all match. Encoding (UTF-8, Windows-1256, UTF-16) and delimiter (`, ; | tab`) are auto-detected.
- **Search syntax:** several words (all must match), word prefixes (3+ characters), `"exact phrase"`, paging buttons.
- **Access control:** closed by default; admins add or remove users from the chat (`/adduser`, `/deluser`).
- **Safety:** per-user search and result limits, an audit log of every search (`/audit`).
- **Admin tools:** upload small files in chat, `/reload`, delete a row from the index or from the original file.
- **Only a bot token is needed** (no `API_ID` / `API_HASH`). Proxy and custom Bot API server supported for regions where Telegram is blocked.

## Quick start

### 1. Create the bot
1. Message [@BotFather](https://t.me/BotFather), send `/newbot`, copy the **token**.
2. Get your numeric Telegram id from [@userinfobot](https://t.me/userinfobot); it becomes `ADMIN_IDS`.

### 2. Install

**Docker** (any OS)
```bash
git clone https://github.com/plaipa/DB.git telegram-csv-search-bot
cd telegram-csv-search-bot
cp .env.example .env        # set BOT_TOKEN and ADMIN_IDS
docker compose up -d --build
```

**Python 3.10+** (macOS / Linux)
```bash
cp .env.example .env        # set BOT_TOKEN and ADMIN_IDS
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m csvbot.check   # verifies settings and Telegram access
.venv/bin/python -m csvbot.bot
```
On Windows use `py -m venv .venv`, `.venv\Scripts\pip` and `.venv\Scripts\python`. Linux servers: `bash deploy/setup.sh` installs a systemd service; macOS: `bash deploy/mac.sh`. SQLite 3.43 or newer is required (check with `python -m csvbot.check`; Docker already has it).

### 3. Add files and search
Copy CSV / SQLite files into `data/` (a fictional `sample.csv` is included). Within a minute the admin gets a "file indexed" message. Then send any word to the bot.

## Configuration (`.env`)
| Setting | Description | Default |
|---|---|---|
| `BOT_TOKEN` | Token from @BotFather (required) | — |
| `ADMIN_IDS` | Numeric ids of admins, comma separated | — |
| `ALLOWED_USER_IDS` | Extra allowed users (besides admins and `/adduser`) | — |
| `DATA_DIR` | Folder with your files (relative or absolute) | `data` |
| `DB_PATH` | Search index file (created automatically) | `index.db` |
| `SCAN_INTERVAL` | Seconds between folder scans | `60` |
| `PAGE_SIZE` | Results per page | `5` |
| `SEARCH_LIMIT_HOUR` / `SEARCH_LIMIT_DAY` | Searches per regular user (`0` = unlimited) | `60` / `300` |
| `MAX_RESULTS` | Results a regular user can page through per search (`0` = unlimited) | `50` |
| `AUDIT_DAYS` | Days to keep the search log (`0` = forever) | `180` |
| `PROXY` | e.g. `socks5://127.0.0.1:10808` | — |
| `TELEGRAM_API_URL` | Custom Bot API server | `https://api.telegram.org` |

Run `python -m csvbot.check` after any change; it never prints secrets.

## Bot commands
| Command | Action | Who |
|---|---|---|
| any text, `/search text` | Search | admins and allowed users |
| `/start` | Help; users without access see how to contact the admin | everyone |
| `/files` | List indexed files | admin |
| `/reload` | Scan the folder now | admin |
| `/adduser ID`, `/deluser ID`, `/users` | Manage allowed users | admin |
| `/audit [ID]` | Recent searches (who, when, what) | admin |
| 🗑 button under results | Delete the row from the index, or from the source file too (irreversible) | admin |
| send a file | Add a CSV/DB under 20 MB | admin |

## Change the bot token or the Telegram API server
- **Token:** in BotFather send `/revoke` (same bot) or `/newbot`, put the new value in `BOT_TOKEN` in `.env`, run `python -m csvbot.check`, restart. Run only one instance per token.
- **API server:** set `TELEGRAM_API_URL=https://your-mirror.example.com` (a reverse proxy, a Cloudflare Worker or your own [telegram-bot-api](https://github.com/tdlib/telegram-bot-api) server; the latter also lifts the 20 MB upload limit). The bot token passes through that server, so only use one you control.
- **Proxy / VPN:** `PROXY=socks5://127.0.0.1:10808`. `python -m csvbot.check` can detect a local proxy automatically.

## Documentation
- Full guide in Persian: [README.fa.md](README.fa.md) · Hindi: [README.hi.md](README.hi.md)
- Run on your own computer: [docs/local.md](docs/local.md) · Free Oracle Cloud server: [docs/oracle-cloud.md](docs/oracle-cloud.md)
- GitHub repo settings (name, topics, description): [docs/github-seo.md](docs/github-seo.md)
- Tests: `python -m unittest discover -s tests -v`

## Responsible use, license and disclaimer
The bot is a general-purpose file search tool. It ships with no data, sends no data anywhere and collects nothing; every installation is independent and reads only the files **you** put in `data/`. You are responsible for your data and for complying with local laws (including personal-data protection laws) and Telegram's terms. Do not use it to search personal data that was collected or leaked without people's consent. Keep `.env` and `data/` out of git.

Released under the [MIT License](LICENSE), provided "as is" without warranty.
