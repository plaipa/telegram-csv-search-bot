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
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "60"))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "5"))


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
