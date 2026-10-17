"""Diagnose setup problems step by step. Usage: python -m csvbot.check"""
import asyncio
import logging
import os
import re
import socket
import sqlite3
import subprocess
import sys

OK, FAIL, WARN = "✅", "❌", "⚠️"
# Same file csvbot.config loads: .env in the project folder.
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
failed = False
# Default local proxy ports of common VPN clients (v2rayN, V2RayU, sing-box,
# Clash, Clash Verge, Hiddify, ...), tried when Telegram is unreachable.
COMMON_PORTS = (10808, 10809, 1080, 1087, 2080, 7890, 7897, 12334, 8889)


def report(status: str, text: str, hint: str = ""):
    global failed
    failed |= status == FAIL
    print(f"{status} {text}")
    if hint:
        print(f"   ← {hint}")


def check_local() -> bool:
    report(OK if sys.version_info >= (3, 10) else FAIL,
           f"Python {sys.version.split()[0]}", "Python 3.13 را از python.org نصب کنید" if sys.version_info < (3, 10) else "")
    v = sqlite3.sqlite_version_info
    report(OK if v >= (3, 43) else FAIL, f"SQLite {sqlite3.sqlite_version}",
           "" if v >= (3, 43) else "Python 3.13 را از python.org نصب کنید")
    if not os.path.exists(ENV_PATH):
        hint = "فایل .env.example را به .env کپی کنید"
        if os.path.exists(ENV_PATH + ".txt") or os.path.exists(ENV_PATH + ".rtf"):
            hint = "اسم فایل .env.txt یا .env.rtf شده؛ آن را به .env تغییر دهید"
        report(FAIL, f"فایل {ENV_PATH} پیدا نشد", hint)
        return False
    with open(ENV_PATH, "rb") as f:
        if f.read(5) == b"{\\rtf":
            report(FAIL, "فایل .env با فرمت RTF ذخیره شده",
                   "در TextEdit منوی Format → Make Plain Text را بزنید و دوباره ذخیره کنید")
            return False
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)
    report(OK, "فایل .env پیدا شد")
    ok = True
    for name, why in [("API_ID", "از my.telegram.org"), ("API_HASH", "از my.telegram.org"),
                      ("BOT_TOKEN", "از @BotFather")]:
        value = os.getenv(name, "").strip()
        if not value or value.startswith(("123456", "0123456789abcdef")):
            report(FAIL, f"{name} پر نشده", why)
            ok = False
    if os.getenv("API_ID", "").strip() and not os.getenv("API_ID", "").strip().isdigit():
        report(FAIL, "API_ID باید فقط عدد باشد")
        ok = False
    if ok:
        report(OK, "API_ID و API_HASH و BOT_TOKEN پر شده‌اند")
    admins = os.getenv("ADMIN_IDS", "").replace(",", " ").split()
    if not admins:
        report(WARN, "ADMIN_IDS خالی است: هیچ‌کس نمی‌تواند فایل اضافه کند", "شناسه‌ی عددی خود را از @userinfobot بگیرید")
    elif not all(a.lstrip("-").isdigit() for a in admins):
        report(FAIL, f"ADMIN_IDS باید عدد باشد، نه نام کاربری: {' '.join(admins)}", "شناسه‌ی عددی را از @userinfobot بگیرید")
    else:
        report(OK, f"ADMIN_IDS: {' '.join(admins)}")
    return ok


def check_proxy() -> bool:
    from . import config
    try:
        proxy = config.proxy()
    except SystemExit as e:
        report(FAIL, str(e))
        return False
    if not proxy:
        report(OK, "PROXY خالی است (اتصال مستقیم یا VPN در حالت TUN)")
        return True
    try:
        socket.create_connection((proxy["addr"], proxy["port"]), timeout=5).close()
        report(OK, f"پروکسی {proxy['addr']}:{proxy['port']} در دسترس است")
        return True
    except OSError:
        report(WARN, f"به پروکسی {proxy['addr']}:{proxy['port']} وصل نشد",
               "VPN روشن نیست یا شماره پورت SOCKS با تنظیمات برنامه‌ی VPN یکی نیست")
        return True  # check_telegram will look for a working proxy


def parse_scutil(out: str) -> list[str]:
    """Proxy URLs from macOS `scutil --proxy` output (set by most VPN apps)."""
    d = dict(re.findall(r"^\s*(\w+)\s*:\s*(\S+)\s*$", out, re.M))
    urls = []
    for kind, scheme in (("SOCKS", "socks5"), ("HTTPS", "http"), ("HTTP", "http")):
        if d.get(f"{kind}Enable") == "1" and d.get(f"{kind}Proxy") and d.get(f"{kind}Port"):
            urls.append(f"{scheme}://{d[kind + 'Proxy']}:{d[kind + 'Port']}")
    return urls


def proxy_candidates() -> list[str]:
    urls = []
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["scutil", "--proxy"], capture_output=True, text=True, timeout=5).stdout
            urls += parse_scutil(out)
        except (OSError, subprocess.SubprocessError):
            pass
    for var in ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy"):
        if os.getenv(var):
            urls.append(os.environ[var].replace("socks5h://", "socks5://"))
    urls += [f"{scheme}://127.0.0.1:{port}" for port in COMMON_PORTS for scheme in ("socks5", "http")]
    result = []
    for url in dict.fromkeys(urls):
        from .config import parse_proxy
        try:
            p = parse_proxy(url)
            socket.create_connection((p["addr"], p["port"]), timeout=1).close()
            result.append(url)
        except (SystemExit, OSError, TypeError):
            continue
    return result


async def connect(proxy_url: str | None):
    """Return a connected client, or None."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    from . import config
    client = TelegramClient(StringSession(), config.API_ID, config.API_HASH,
                            proxy=config.parse_proxy(proxy_url or ""),
                            connection_retries=1, timeout=10)
    try:
        await asyncio.wait_for(client.connect(), 30)
        return client
    except Exception:
        try:
            await client.disconnect()
        except Exception:
            pass
        return None


def save_proxy(url: str):
    with open(ENV_PATH, encoding="utf-8") as f:
        lines = [line for line in f.read().splitlines() if not line.startswith("PROXY=")]
    lines.append(f"PROXY={url}")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


async def find_proxy():
    """Telegram is unreachable with the current settings: look for a local
    VPN proxy that works and offer to save it to .env."""
    print("\n🔎 دنبال پروکسی برنامه‌ی VPN روی این کامپیوتر می‌گردم...")
    current = os.getenv("PROXY", "").strip()
    for url in proxy_candidates():
        if url == current:
            continue
        print(f"   امتحان {url} ...")
        client = await connect(url)
        if client:
            report(OK, f"از طریق {url} به تلگرام وصل شد")
            answer = "y"
            if sys.stdin.isatty():
                answer = input(f"   این را در .env ذخیره کنم؟ (PROXY={url}) [Y/n] ").strip().lower() or "y"
            if answer.startswith("y"):
                save_proxy(url)
                os.environ["PROXY"] = url
                print("   ذخیره شد.")
            else:
                print(f"   خودتان این خط را در .env بنویسید: PROXY={url}")
            return client
    report(FAIL, "هیچ پروکسی کارآمدی پیدا نشد",
           "VPN را روشن کنید و دوباره اجرا کنید. اگر روشن است، حالت TUN / Enhanced Mode را فعال کنید "
           "یا پورت SOCKS را از تنظیمات برنامه پیدا کرده و در PROXY بنویسید")
    return None


async def check_telegram():
    from . import config
    client = await connect(os.getenv("PROXY", ""))
    if client:
        report(OK, "اتصال به سرورهای تلگرام برقرار شد")
    else:
        print(f"{WARN} با تنظیمات فعلی به تلگرام وصل نشد")
        client = await find_proxy()
        if not client:
            return
    try:
        try:
            await client.sign_in(bot_token=config.BOT_TOKEN)
        except Exception as e:
            report(FAIL, f"توکن ربات قبول نشد ({type(e).__name__})",
                   "توکن را دوباره از @BotFather کپی کنید (بعد از /revoke توکن قبلی باطل است)")
            return
        me = await client.get_me()
        report(OK, f"ربات @{me.username} وارد شد")
        if not config.CHANNEL:
            report(WARN, "CHANNEL خالی است: فایل‌های همه‌ی کانال‌هایی که ربات ادمین آن‌هاست ثبت می‌شوند")
            return
        if config.CHANNEL.lstrip("@").lower() == (me.username or "").lower():
            report(FAIL, "CHANNEL نام کاربری خود ربات است، نه کانال", "آدرس کانال را بنویسید، مثلاً @mychannel")
            return
        try:
            channel = await client.get_entity(config.channel_ref())
            perms = await client.get_permissions(channel, "me")
            if perms.is_admin:
                report(OK, f"ربات در کانال «{channel.title}» ادمین است")
            else:
                report(FAIL, f"ربات در کانال «{channel.title}» ادمین نیست", "ربات را در تنظیمات کانال ادمین کنید")
        except Exception as e:
            report(FAIL, f"کانال {config.CHANNEL} پیدا نشد یا ربات عضو آن نیست ({type(e).__name__})",
                   "ربات را در کانال ادمین کنید؛ برای کانال خصوصی شناسه‌ی عددی -100... را بنویسید")
    finally:
        await client.disconnect()


def main():
    logging.getLogger("telethon").setLevel(logging.CRITICAL)
    print("بررسی تنظیمات ربات...\n")
    if check_local() and not failed and check_proxy():
        asyncio.run(check_telegram())
    print("\n" + ("❌ مشکل بالا را برطرف کنید و دوباره اجرا کنید." if failed
                  else "✅ همه چیز درست است. ربات را با python -m csvbot.bot اجرا کنید."))


if __name__ == "__main__":
    main()
