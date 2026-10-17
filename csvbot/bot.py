"""Telegram bot that indexes CSV files posted to a channel and searches them.

Uses Telethon (MTProto) instead of the Bot HTTP API so files of several GB
can be downloaded; the Bot API is limited to 20 MB.
"""
import asyncio
import html
import logging

from telethon import Button, TelegramClient, events

from . import config
from .db import Database
from .indexer import index_message, is_csv

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    level=logging.INFO)
log = logging.getLogger("csvbot")

MAX_VALUE_LEN = 300
db = Database(config.DB_PATH)
bot = TelegramClient("bot", config.API_ID, config.API_HASH, proxy=config.proxy())
last_query: dict[int, str] = {}


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def can_search(user_id: int) -> bool:
    return not config.ALLOWED_IDS or user_id in config.ALLOWED_IDS or is_admin(user_id)


async def notify_admins(text: str):
    for admin in config.ADMIN_IDS:
        try:
            await bot.send_message(admin, text)
        except Exception:
            log.warning("Could not notify admin %s", admin)


@bot.on(events.NewMessage(func=lambda e: e.is_channel and not e.is_group))
async def on_channel_post(event):
    if config.CHANNEL:
        ref = config.channel_ref()
        chat = await event.get_chat()
        if ref not in (event.chat_id, getattr(chat, "username", None), "@" + (getattr(chat, "username", "") or "")):
            return
    if not is_csv(event.document):
        return
    try:
        result = await index_message(bot, db, event.message)
    except Exception:
        log.exception("Failed to index channel file")
        result = "❌ خطا در پردازش فایل کانال."
    await notify_admins(result)


@bot.on(events.NewMessage(func=lambda e: e.is_private and e.document is not None))
async def on_private_document(event):
    """Admins forward old CSV files from the channel to index them."""
    if not is_admin(event.sender_id):
        await event.reply("⛔️ فقط ادمین می‌تواند فایل اضافه کند.")
        return
    if not is_csv(event.document):
        await event.reply("فقط فایل‌های CSV پشتیبانی می‌شوند.")
        return
    status = await event.reply("⏳ در صف پردازش...")
    try:
        result = await index_message(bot, db, event.message, report=status.edit)
    except Exception:
        log.exception("Failed to index file")
        result = "❌ خطا در پردازش فایل."
    await status.edit(result)


def format_results(query: str, total: int, results, offset: int) -> str:
    q = html.escape(query)
    if not total:
        return f"🔍 نتیجه‌ای برای «{q}» پیدا نشد."
    shown = f"{total - 1}+" if total > 1000 else str(total)
    parts = [f"🔍 <b>{shown}</b> نتیجه برای «{q}» (نمایش {offset + 1} تا {offset + len(results)})"]
    for i, (name, row_num, fields) in enumerate(results, offset + 1):
        lines = [f"<b>{i}.</b> 📄 <code>{html.escape(name)}</code> — ردیف {row_num:,}"]
        for key, value in fields.items():
            if len(value) > MAX_VALUE_LEN:
                value = value[:MAX_VALUE_LEN] + "…"
            lines.append(f"• <b>{html.escape(key)}:</b> {html.escape(value)}")
        parts.append("\n".join(lines))
    text = "\n\n".join(parts)
    return text if len(text) <= 4000 else text[:3990] + "…"


def pager(total: int, offset: int):
    size, buttons = config.PAGE_SIZE, []
    if offset > 0:
        buttons.append(Button.inline("« قبلی", f"page:{max(offset - size, 0)}".encode()))
    if offset + size < total:
        buttons.append(Button.inline("بعدی »", f"page:{offset + size}".encode()))
    return [buttons] if buttons else None


async def run_search(query: str, offset: int):
    total, results = await asyncio.to_thread(db.search, query, config.PAGE_SIZE, offset)
    return format_results(query, total, results, offset), pager(total, offset)


START_TEXT = ("سلام! 👋\n"
              "هر کلمه یا عبارتی را بفرستید تا در فایل‌های CSV جستجو کنم.\n\n"
              "• چند کلمه: ردیف‌هایی که همه کلمات را دارند\n"
              "• عبارت داخل \"گیومه\": جستجوی دقیق همان عبارت\n\n"
              "دستورات: /files")
ADMIN_TEXT = ("\n\nادمین: فایل‌های CSV جدید کانال خودکار ثبت می‌شوند. فایل‌های قدیمی را"
              " از کانال به همین ربات فوروارد کنید.\n/delete شناسه — حذف یک فایل")


@bot.on(events.NewMessage(func=lambda e: e.is_private and e.document is None and e.raw_text))
async def on_text(event):
    text, uid = event.raw_text.strip(), event.sender_id
    if text.startswith("/start"):
        await event.reply(START_TEXT + (ADMIN_TEXT if is_admin(uid) else ""))
        return
    if not can_search(uid):
        await event.reply("⛔️ شما اجازه استفاده از این ربات را ندارید.")
        return
    if text.startswith("/files"):
        files = db.list_files()
        lines = [f"{fid}. {name} — {count:,} ردیف" for fid, name, count in files]
        await event.reply("📚 فایل‌های ثبت‌شده:\n" + "\n".join(lines) if lines else "هنوز فایلی ثبت نشده است.")
        return
    if text.startswith("/delete"):
        if not is_admin(uid):
            return
        arg = text.split(maxsplit=1)[1:] or [""]
        if not arg[0].isdigit():
            await event.reply("استفاده: /delete شناسه_فایل (شناسه را از /files ببینید)")
            return
        ok = await asyncio.to_thread(db.delete_file, int(arg[0]))
        await event.reply("🗑 حذف شد." if ok else "فایلی با این شناسه پیدا نشد.")
        return
    if text.startswith("/search"):
        text = text[len("/search"):].strip()
    elif text.startswith("/"):
        return
    if not text:
        await event.reply("عبارت مورد نظر را بنویسید. مثال: علی رضایی")
        return
    last_query[uid] = text
    body, buttons = await run_search(text, 0)
    await event.reply(body, parse_mode="html", buttons=buttons)


@bot.on(events.CallbackQuery(pattern=rb"^page:\d+$"))
async def on_page(event):
    query = last_query.get(event.sender_id)
    if not query or not can_search(event.sender_id):
        await event.answer("جستجو منقضی شده، دوباره جستجو کنید.")
        return
    await event.answer()
    body, buttons = await run_search(query, int(event.data.split(b":")[1]))
    await event.edit(body, parse_mode="html", buttons=buttons)


def main():
    if not config.ADMIN_IDS:
        log.warning("ADMIN_IDS is empty: nobody can add files from private chat")
    bot.start(bot_token=config.BOT_TOKEN)
    log.info("Bot started")
    bot.run_until_disconnected()


if __name__ == "__main__":
    main()
