import os
from urllib.parse import urlparse

from dotenv import load_dotenv

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_DIR, ".env")
load_dotenv(ENV_PATH)


def _ids(name: str) -> set[int]:
    return {int(x) for x in os.getenv(name, "").replace(",", " ").split() if x.lstrip("-").isdigit()}


def _path(name: str, default: str) -> str:
    """Relative paths are relative to the project folder."""
    return os.path.join(PROJECT_DIR, os.path.expanduser(os.getenv(name, "").strip() or default))


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = _ids("ADMIN_IDS")
ALLOWED_IDS = _ids("ALLOWED_USER_IDS")
DATA_DIR = _path("DATA_DIR", "data")
DB_PATH = _path("DB_PATH", "index.db")
# Bot API server; change it to use a mirror/reverse proxy of api.telegram.org
# or a self-hosted telegram-bot-api server.
API_URL = (os.getenv("TELEGRAM_API_URL", "").strip() or "https://api.telegram.org").rstrip("/")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "60"))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "5"))


def _int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    return int(value) if value.lstrip("-").isdigit() else default


# Limits for non-admin users; 0 = unlimited.
SEARCH_LIMIT_HOUR = _int("SEARCH_LIMIT_HOUR", 60)
SEARCH_LIMIT_DAY = _int("SEARCH_LIMIT_DAY", 300)
MAX_RESULTS = _int("MAX_RESULTS", 50)  # results viewable per search
AUDIT_DAYS = _int("AUDIT_DAYS", 180)  # how long the search log is kept


def proxy() -> str | None:
    """PROXY from .env, e.g. socks5://127.0.0.1:10808 (local VPN client port)."""
    return parse_proxy(os.getenv("PROXY", ""))


def parse_proxy(url: str) -> str | None:
    url = url.strip()
    if not url:
        return None
    p = urlparse(url)
    if p.scheme not in ("socks5", "socks5h", "socks4", "http", "https") or not p.hostname or not p.port:
        raise SystemExit(f"Invalid PROXY {url!r}; expected e.g. socks5://127.0.0.1:10808")
    return url
