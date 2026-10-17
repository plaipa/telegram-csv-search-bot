"""Diagnose setup problems step by step. Usage: python -m csvbot.check"""
import asyncio
import os
import socket
import sqlite3
import sys

OK, FAIL, WARN = "✅", "❌", "⚠️"
# Same file csvbot.config loads: .env in the project folder.
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
failed = False


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
        report(FAIL, f"به پروکسی {proxy['addr']}:{proxy['port']} وصل نشد",
               "VPN روشن نیست یا شماره پورت SOCKS با تنظیمات برنامه‌ی VPN یکی نیست")
        return False


async def check_telegram():
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    from . import config
    client = TelegramClient(StringSession(), config.API_ID, config.API_HASH,
                            proxy=config.proxy(), connection_retries=1, timeout=15)
    try:
        await asyncio.wait_for(client.connect(), 40)
    except Exception as e:
        report(FAIL, f"اتصال به تلگرام برقرار نشد ({type(e).__name__})",
               "تلگرام فیلتر است: VPN را روشن کنید و PROXY را تنظیم کنید یا VPN را در حالت TUN بگذارید")
        return
    report(OK, "اتصال به سرورهای تلگرام برقرار شد")
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
    print("بررسی تنظیمات ربات...\n")
    if check_local() and not failed and check_proxy():
        asyncio.run(check_telegram())
    print("\n" + ("❌ مشکل بالا را برطرف کنید و دوباره اجرا کنید." if failed
                  else "✅ همه چیز درست است. ربات را با python -m csvbot.bot اجرا کنید."))


if __name__ == "__main__":
    main()
