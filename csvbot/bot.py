"""Telegram bot that searches every CSV and SQLite file in a folder.

Files placed in DATA_DIR (default: ./data) are indexed automatically; the
folder is re-scanned every SCAN_INTERVAL seconds and on /reload.
"""
import asyncio
import html
import logging
import os
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import InvalidToken, NetworkError
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

from . import config
from .db import Database
from .sources import CSV_EXT, DB_EXT, FolderIndex

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("csvbot")

MAX_VALUE_LEN = 300
MAX_UPLOAD = 20 * 1024 * 1024  # Bot API download limit
db = Database(config.DB_PATH)
folder = FolderIndex(db, config.DATA_DIR)
scan_lock = asyncio.Lock()


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def can_search(user_id: int) -> bool:
    return not config.ALLOWED_IDS or user_id in config.ALLOWED_IDS or is_admin(user_id)


async def notify_admins(bot, text: str):
    for admin in config.ADMIN_IDS:
        try:
            await bot.send_message(admin, text)
        except Exception:
            log.warning("Could not notify admin %s", admin)


async def run_scan(app: Application) -> dict:
    """Index new/changed files in the folder; one scan at a time."""
    loop = asyncio.get_running_loop()

    def on_indexed(name: str, count: int):
        asyncio.run_coroutine_threadsafe(
            notify_admins(app.bot, f"✅ «{name}» با {count:,} ردیف ثبت شد."), loop)

    async with scan_lock:
        return await asyncio.to_thread(folder.sync, on_indexed)


async def scanner(app: Application):
    while True:
        try:
            await run_scan(app)
        except Exception:
            log.exception("Folder scan failed")
        await asyncio.sleep(config.SCAN_INTERVAL)


async def post_init(app: Application):
    log.info("Bot started as @%s, watching folder %s", app.bot.username, config.DATA_DIR)
    app.bot_data["scanner"] = asyncio.get_running_loop().create_task(scanner(app))


async def post_shutdown(app: Application):
    if task := app.bot_data.get("scanner"):
        task.cancel()


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


def pager(total: int, offset: int) -> InlineKeyboardMarkup | None:
    size, buttons = config.PAGE_SIZE, []
    if offset > 0:
        buttons.append(InlineKeyboardButton("« قبلی", callback_data=f"page:{max(offset - size, 0)}"))
    if offset + size < total:
        buttons.append(InlineKeyboardButton("بعدی »", callback_data=f"page:{offset + size}"))
    return InlineKeyboardMarkup([buttons]) if buttons else None


async def run_search(query: str, offset: int):
    total, results = await asyncio.to_thread(db.search, query, config.PAGE_SIZE, offset)
    return format_results(query, total, results, offset), pager(total, offset)


async def on_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not can_search(update.effective_user.id):
        await msg.reply_text("⛔️ شما اجازه استفاده از این ربات را ندارید.")
        return
    query = " ".join(context.args) if context.args is not None else msg.text
    if not query.strip():
        await msg.reply_text("عبارت مورد نظر را بنویسید. مثال: علی رضایی")
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
            "هر کلمه یا عبارتی را بفرستید تا در فایل‌ها جستجو کنم.\n\n"
            "• چند کلمه: ردیف‌هایی که همه کلمات را دارند\n"
            "• عبارت داخل \"گیومه\": جستجوی دقیق همان عبارت\n\n"
            "/files — فهرست فایل‌ها")
    if is_admin(update.effective_user.id):
        text += ("\n\nادمین: فایل‌های CSV و DB را در پوشه‌ی data بگذارید تا خودکار ثبت شوند،"
                 " یا فایل‌های زیر ۲۰ مگابایت را همین‌جا بفرستید.\n/reload — بررسی فوری پوشه")
    await update.effective_message.reply_text(text)


async def on_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not can_search(update.effective_user.id):
        return
    files = db.list_files()
    if not files:
        await update.effective_message.reply_text("هنوز فایلی ثبت نشده است.")
        return
    lines = [f"• {name} — {count:,} ردیف" for _, name, count in files]
    text = "📚 فایل‌های ثبت‌شده:\n" + "\n".join(lines)
    await update.effective_message.reply_text(text[:4000])


async def on_reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not is_admin(update.effective_user.id):
        return
    status = await msg.reply_text("⏳ در حال بررسی پوشه...")
    r = await run_scan(context.application)
    text = f"✅ بررسی شد: {r['added']} مورد جدید، {r['removed']} مورد حذف‌شده."
    if r["pending"]:
        text += f"\n⏳ {r['pending']} فایل در حال کپی است و کمی بعد ثبت می‌شود."
    if r["errors"]:
        text += f"\n❌ {r['errors']} فایل قابل خواندن نبود (جزئیات در لاگ)."
    await status.edit_text(text)


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admins can send small CSV/DB files; they are saved into the folder."""
    msg = update.effective_message
    doc = msg.document
    if not is_admin(update.effective_user.id):
        await msg.reply_text("⛔️ فقط ادمین می‌تواند فایل اضافه کند.")
        return
    name = os.path.basename(doc.file_name or "")
    if not name.lower().endswith(CSV_EXT + DB_EXT):
        await msg.reply_text("فقط فایل‌های CSV و DB پشتیبانی می‌شوند.")
        return
    if doc.file_size and doc.file_size > MAX_UPLOAD:
        await msg.reply_text("⚠️ فایل بزرگ‌تر از ۲۰ مگابایت است؛ آن را مستقیم در پوشه‌ی data کپی کنید.")
        return
    status = await msg.reply_text("⏳ در حال دریافت...")
    target_dir = os.path.join(config.DATA_DIR, "uploads")
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, name)
    tg_file = await context.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(path + ".part")
    os.replace(path + ".part", path)
    past = time.time() - 120  # the file is complete; skip the "still copying" wait
    os.utime(path, (past, past))
    await status.edit_text("⏳ در حال ثبت...")
    r = await run_scan(context.application)
    await status.edit_text(f"✅ ذخیره و ثبت شد ({r['added']} مورد)." if not r["errors"]
                           else "❌ فایل ذخیره شد ولی قابل خواندن نبود.")


def build_app() -> Application:
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is not set in .env (run: python -m csvbot.check)")
    builder = Application.builder().token(config.BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown)
    if config.proxy():
        builder = builder.proxy(config.proxy()).get_updates_proxy(config.proxy())
    app = builder.build()
    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("start", on_start, filters=private))
    app.add_handler(CommandHandler("search", on_search, filters=private))
    app.add_handler(CommandHandler("files", on_files, filters=private))
    app.add_handler(CommandHandler("reload", on_reload, filters=private))
    app.add_handler(MessageHandler(private & filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, on_search))
    app.add_handler(CallbackQueryHandler(on_page, pattern=r"^page:\d+$"))
    return app


def main():
    if not config.ADMIN_IDS:
        log.warning("ADMIN_IDS is empty: nobody gets file notifications or /reload")
    try:
        build_app().run_polling(allowed_updates=Update.ALL_TYPES)
    except InvalidToken:
        raise SystemExit("❌ Telegram rejected BOT_TOKEN; copy it again from @BotFather into .env")
    except NetworkError as e:
        raise SystemExit(f"❌ Cannot reach Telegram ({e}); turn on the VPN and run: python -m csvbot.check")


if __name__ == "__main__":
    main()
