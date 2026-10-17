"""Diagnose setup problems step by step. Usage: python -m csvbot.check"""
import os
import re
import socket
import sqlite3
import subprocess
import sys

OK, FAIL, WARN = "✅", "❌", "⚠️"
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
    from . import config
    report(OK if sys.version_info >= (3, 10) else FAIL, f"Python {sys.version.split()[0]}",
           "" if sys.version_info >= (3, 10) else "Python 3.13 را از python.org نصب کنید")
    v = sqlite3.sqlite_version_info
    report(OK if v >= (3, 43) else FAIL, f"SQLite {sqlite3.sqlite_version}",
           "" if v >= (3, 43) else "Python 3.13 را از python.org نصب کنید")
    env = config.ENV_PATH
    if not os.path.exists(env):
        hint = "فایل .env.example را به .env کپی کنید"
        if os.path.exists(env + ".txt") or os.path.exists(env + ".rtf"):
            hint = "اسم فایل .env.txt یا .env.rtf شده؛ آن را به .env تغییر دهید"
        report(FAIL, f"فایل {env} پیدا نشد", hint)
        return False
    with open(env, "rb") as f:
        if f.read(5) == b"{\\rtf":
            report(FAIL, "فایل .env با فرمت RTF ذخیره شده",
                   "در TextEdit منوی Format → Make Plain Text را بزنید و دوباره ذخیره کنید")
            return False
    report(OK, "فایل .env پیدا شد")
    if not re.fullmatch(r"\d+:[\w-]{30,}", config.BOT_TOKEN):
        report(FAIL, "BOT_TOKEN پر نشده یا اشتباه است", "توکن را از @BotFather کپی کنید")
    admins = os.getenv("ADMIN_IDS", "").replace(",", " ").split()
    if not admins:
        report(WARN, "ADMIN_IDS خالی است: اعلان ثبت فایل و /reload برای کسی کار نمی‌کند",
               "شناسه‌ی عددی خود را از @userinfobot بگیرید")
    elif not all(a.lstrip("-").isdigit() for a in admins):
        report(FAIL, f"ADMIN_IDS باید عدد باشد، نه نام کاربری: {' '.join(admins)}",
               "شناسه‌ی عددی را از @userinfobot بگیرید")
    else:
        report(OK, f"ADMIN_IDS: {' '.join(admins)}")
    check_folder(config.DATA_DIR)
    return not failed


def check_folder(data_dir: str):
    from .sources import CSV_EXT, DB_EXT, is_sqlite
    if not os.path.isdir(data_dir):
        report(WARN, f"پوشه‌ی {data_dir} وجود ندارد؛ موقع اجرای ربات ساخته می‌شود")
        return
    csv_n = db_n = bad = 0
    for root, _, files in os.walk(data_dir):
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext in CSV_EXT:
                csv_n += 1
            elif ext in DB_EXT:
                if is_sqlite(os.path.join(root, name)):
                    db_n += 1
                else:
                    bad += 1
    report(OK if csv_n + db_n else WARN, f"پوشه‌ی {data_dir}: {csv_n} فایل CSV و {db_n} دیتابیس SQLite",
           "" if csv_n + db_n else "فایل‌های CSV یا DB را در این پوشه بگذارید")
    if bad:
        report(WARN, f"{bad} فایل .db دیتابیس SQLite نیست و نادیده گرفته می‌شود")


def parse_scutil(out: str) -> list[str]:
    """Proxy URLs from macOS `scutil --proxy` output (set by most VPN apps)."""
    d = dict(re.findall(r"^\s*(\w+)\s*:\s*(\S+)\s*$", out, re.M))
    urls = []
    for kind, scheme in (("SOCKS", "socks5"), ("HTTPS", "http"), ("HTTP", "http")):
        if d.get(f"{kind}Enable") == "1" and d.get(f"{kind}Proxy") and d.get(f"{kind}Port"):
            urls.append(f"{scheme}://{d[kind + 'Proxy']}:{d[kind + 'Port']}")
    return urls


def proxy_candidates() -> list[str]:
    from urllib.parse import urlparse
    urls = []
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["scutil", "--proxy"], capture_output=True, text=True, timeout=5).stdout
            urls += parse_scutil(out)
        except (OSError, subprocess.SubprocessError):
            pass
    for var in ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy"):
        if os.getenv(var):
            urls.append(os.environ[var])
    urls += [f"{scheme}://127.0.0.1:{port}" for port in COMMON_PORTS for scheme in ("socks5", "http")]
    result = []
    for url in dict.fromkeys(urls):
        p = urlparse(url)
        try:
            socket.create_connection((p.hostname, p.port), timeout=1).close()
            result.append(url)
        except (OSError, TypeError, ValueError):
            continue
    return result


def get_me(proxy_url: str | None):
    """Return (reachable, bot username or None)."""
    import httpx

    from . import config
    try:
        r = httpx.get(f"https://api.telegram.org/bot{config.BOT_TOKEN}/getMe",
                      proxy=proxy_url or None, timeout=15, trust_env=False)
    except Exception:
        return False, None
    if r.status_code == 200:
        return True, r.json()["result"]["username"]
    return r.status_code in (401, 404), None


def save_proxy(url: str):
    from . import config
    with open(config.ENV_PATH, encoding="utf-8") as f:
        lines = [line for line in f.read().splitlines() if not line.startswith("PROXY=")]
    lines.append(f"PROXY={url}")
    with open(config.ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def find_proxy():
    """Telegram is unreachable with the current settings: look for a local
    VPN proxy that works and offer to save it to .env."""
    print("\n🔎 دنبال پروکسی برنامه‌ی VPN روی این کامپیوتر می‌گردم...")
    current = os.getenv("PROXY", "").strip()
    for url in proxy_candidates():
        if url == current:
            continue
        print(f"   امتحان {url} ...")
        reachable, username = get_me(url)
        if reachable:
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
            return True, username
    report(FAIL, "هیچ پروکسی کارآمدی پیدا نشد",
           "VPN را روشن کنید و دوباره اجرا کنید. اگر روشن است، حالت TUN / Enhanced Mode را فعال کنید "
           "یا پورت SOCKS را از تنظیمات برنامه پیدا کرده و در PROXY بنویسید")
    return False, None


def check_telegram():
    from . import config
    try:
        proxy = config.proxy()
    except SystemExit as e:
        report(FAIL, str(e))
        return
    reachable, username = get_me(proxy)
    if reachable:
        report(OK, "اتصال به تلگرام برقرار شد" + (f" (از طریق {proxy})" if proxy else ""))
    else:
        print(f"{WARN} با تنظیمات فعلی به تلگرام وصل نشد")
        reachable, username = find_proxy()
        if not reachable:
            return
    if username:
        report(OK, f"توکن درست است: ربات @{username}")
    else:
        report(FAIL, "تلگرام توکن را قبول نکرد",
               "توکن را دوباره از @BotFather کپی کنید (بعد از /revoke توکن قبلی باطل است)")


def main():
    print("بررسی تنظیمات ربات...\n")
    if check_local():
        check_telegram()
    print("\n" + ("❌ مشکل بالا را برطرف کنید و دوباره اجرا کنید." if failed
                  else "✅ همه چیز درست است. ربات را با python -m csvbot.bot اجرا کنید."))


if __name__ == "__main__":
    main()
