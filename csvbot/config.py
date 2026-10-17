import os
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


def _ids(name: str) -> set[int]:
    return {int(x) for x in os.getenv(name, "").replace(",", " ").split()}


API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL = os.getenv("CHANNEL", "").strip()  # -100... id or @username
ADMIN_IDS = _ids("ADMIN_IDS")
ALLOWED_IDS = _ids("ALLOWED_USER_IDS")
DB_PATH = os.getenv("DB_PATH", "data.db")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "5"))


def channel_ref():
    """CHANNEL as Telethon accepts it: an int id or a username."""
    return int(CHANNEL) if CHANNEL.lstrip("-").isdigit() else CHANNEL


def proxy() -> dict | None:
    """PROXY from .env, e.g. socks5://127.0.0.1:10808 (local VPN client port)."""
    url = os.getenv("PROXY", "").strip()
    if not url:
        return None
    p = urlparse(url)
    if p.scheme not in ("socks5", "socks4", "http") or not p.hostname or not p.port:
        raise SystemExit(f"Invalid PROXY {url!r}; expected e.g. socks5://127.0.0.1:10808")
    return {"proxy_type": p.scheme, "addr": p.hostname, "port": p.port,
            "username": p.username, "password": p.password, "rdns": True}
