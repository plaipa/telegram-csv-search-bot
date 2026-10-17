"""Telegram bot that indexes CSV files posted to a channel and searches them."""
import asyncio
import html
import logging
import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

from .db import Database
from .loader import parse_csv

load_dotenv()
logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    level=logging.INFO)
log = logging.getLogger("csvbot")

TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()  # e.g. -1001234567890
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(",", " ").split()}
ALLOWED_IDS = {int(x) for x in os.getenv("ALLOWED_USER_IDS", "").replace(",", " ").split()}
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "5"))
MAX_VALUE_LEN = 300

db = Database(os.getenv("DB_PATH", "data.db"))


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def can_search(user_id: int) -> bool:
    return not ALLOWED_IDS or user_id in ALLOWED_IDS or is_admin(user_id)


def is_csv(doc) -> bool:
    name = (doc.file_name or "").lower()
    return name.endswith((".csv", ".tsv")) or doc.mime_type in ("text/csv", "text/tab-separated-values")


async def index_document(context: ContextTypes.DEFAULT_TYPE, doc) -> str:
    """Download a CSV document and add it to the index. Returns a status message."""
    name = doc.file_name or "file.csv"
    if db.has_file(doc.file_unique_id):
        return f"ℹ️ فایل «{name}» قبلاً ثبت شده است."
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        return (f"⚠️ فایل «{name}» بزرگ‌تر از ۲۰ مگابایت است و ربات نمی‌تواند آن را دانلود کند."
                " از اسکریپت import_csv.py استفاده کنید.")
    tg_file = await context.bot.get_file(doc.file_id)
    data = bytes(await tg_file.download_as_bytearray())
    headers, rows = await asyncio.to_thread(parse_csv, data)
    if not headers:
        return f"⚠️ فایل «{name}» خالی است یا قابل خواندن نیست."
    await asyncio.to_thread(db.add_file, doc.file_unique_id, name, headers, rows)
    log.info("Indexed %s (%d rows)", name, len(rows))
    return f"✅ فایل «{name}» با {len(rows)} ردیف ثبت شد."


async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post
    if CHANNEL_ID and str(post.chat.id) != CHANNEL_ID and post.chat.username != CHANNEL_ID.lstrip("@"):
        return
    if not is_csv(post.document):
        return
    try:
        result = await index_document(context, post.document)
    except Exception:
        log.exception("Failed to index channel file")
        result = f"❌ خطا در پردازش فایل «{post.document.file_name}»"
    for admin in ADMIN_IDS:
        try:
            await context.bot.send_message(admin, result)
        except Exception:
            log.warning("Could not notify admin %s", admin)


async def on_private_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admins can forward old CSV files from the channel to index them."""
    msg = update.effective_message
    if not is_admin(update.effective_user.id):
        await msg.reply_text("⛔️ فقط ادمین می‌تواند فایل اضافه کند.")
        return
    if not is_csv(msg.document):
        await msg.reply_text("فقط فایل‌های CSV پشتیبانی می‌شوند.")
        return
    status = await msg.reply_text("⏳ در حال پردازش...")
    try:
        result = await index_document(context, msg.document)
    except Exception:
        log.exception("Failed to index file")
        result = "❌ خطا در پردازش فایل."
    await status.edit_text(result)


def format_results(query: str, total: int, results, offset: int) -> str:
    if not total:
        return f"🔍 نتیجه‌ای برای «{html.escape(query)}» پیدا نشد."
    end = offset + len(results)
    parts = [f"🔍 <b>{total}</b> نتیجه برای «{html.escape(query)}» (نمایش {offset + 1} تا {end})"]
    for i, (file_name, row_num, fields) in enumerate(results, offset + 1):
        lines = [f"<b>{i}.</b> 📄 <code>{html.escape(file_name)}</code> — ردیف {row_num}"]
        for key, value in fields.items():
            if len(value) > MAX_VALUE_LEN:
                value = value[:MAX_VALUE_LEN] + "…"
            lines.append(f"• <b>{html.escape(key)}:</b> {html.escape(value)}")
        parts.append("\n".join(lines))
    text = "\n\n".join(parts)
    return text if len(text) <= 4000 else text[:3990] + "…"


def pager(total: int, offset: int) -> InlineKeyboardMarkup | None:
    buttons = []
    if offset > 0:
        buttons.append(InlineKeyboardButton("« قبلی", callback_data=f"page:{max(offset - PAGE_SIZE, 0)}"))
    if offset + PAGE_SIZE < total:
        buttons.append(InlineKeyboardButton("بعدی »", callback_data=f"page:{offset + PAGE_SIZE}"))
    return InlineKeyboardMarkup([buttons]) if buttons else None


async def run_search(query: str, offset: int):
    total, results = await asyncio.to_thread(db.search, query, PAGE_SIZE, offset)
    return format_results(query, total, results, offset), pager(total, offset)


async def on_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not can_search(update.effective_user.id):
        await msg.reply_text("⛔️ شما اجازه استفاده از این ربات را ندارید.")
        return
    query = " ".join(context.args) if context.args is not None else msg.text
    if not query.strip():
        await msg.reply_text("عبارت مورد نظر را بنویسید. مثال: /search علی رضایی")
        return
    context.user_data["query"] = query
    text, markup = await run_search(query, 0)
    await msg.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


async def on_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    query = context.user_data.get("query")
    if not query or not can_search(cq.from_user.id):
        await cq.answer("جستجو منقضی شده، دوباره جستجو کنید.")
        return
    await cq.answer()
    text, markup = await run_search(query, int(cq.data.split(":")[1]))
    await cq.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ("سلام! 👋\n"
            "هر کلمه یا عبارتی را بفرستید تا در فایل‌های CSV جستجو کنم.\n\n"
            "• چند کلمه: ردیف‌هایی که همه کلمات را دارند\n"
            "• عبارت داخل \"گیومه\": جستجوی دقیق همان عبارت\n\n"
            "دستورات: /search /files")
    if is_admin(update.effective_user.id):
        text += ("\n\nادمین: فایل‌های CSV جدید کانال خودکار ثبت می‌شوند. فایل‌های قدیمی را"
                 " از کانال به همین ربات فوروارد کنید.\n/delete شناسه — حذف یک فایل")
    await update.effective_message.reply_text(text)


async def on_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not can_search(update.effective_user.id):
        return
    files = db.list_files()
    if not files:
        await update.effective_message.reply_text("هنوز فایلی ثبت نشده است.")
        return
    lines = [f"{fid}. {name} — {count} ردیف" for fid, name, count in files]
    await update.effective_message.reply_text("📚 فایل‌های ثبت‌شده:\n" + "\n".join(lines))


async def on_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not is_admin(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await msg.reply_text("استفاده: /delete شناسه_فایل (شناسه را از /files ببینید)")
        return
    ok = await asyncio.to_thread(db.delete_file, int(context.args[0]))
    await msg.reply_text("🗑 حذف شد." if ok else "فایلی با این شناسه پیدا نشد.")


def main():
    if not ADMIN_IDS:
        log.warning("ADMIN_IDS is empty: nobody can add files from private chat")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST & filters.Document.ALL, on_channel_post))
    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("start", on_start, filters=private))
    app.add_handler(CommandHandler("search", on_search, filters=private))
    app.add_handler(CommandHandler("files", on_files, filters=private))
    app.add_handler(CommandHandler("delete", on_delete, filters=private))
    app.add_handler(MessageHandler(private & filters.Document.ALL, on_private_document))
    app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, on_search))
    app.add_handler(CallbackQueryHandler(on_page, pattern=r"^page:\d+$"))
    log.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
