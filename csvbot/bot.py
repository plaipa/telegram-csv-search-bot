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

from . import config, i18n
from .db import Database
from .i18n import LANGS, t
from .purge import PurgeError, delete_source_row
from .sources import CSV_EXT, DB_EXT, FolderIndex

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("csvbot")

MAX_VALUE_LEN = 300
MAX_UPLOAD = 20 * 1024 * 1024  # Bot API download limit
db = Database(config.DB_PATH)
i18n.set_language(db.get_setting("language") or i18n.DEFAULT)
folder = FolderIndex(db, config.DATA_DIR)
scan_lock = asyncio.Lock()


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def can_search(user_id: int) -> bool:
    """Closed by default: only admins and users added in .env or with /adduser."""
    return is_admin(user_id) or user_id in config.ALLOWED_IDS or user_id in db.users()


def rate_limit_message(user_id: int) -> str | None:
    """None if the user may search now; admins are exempt."""
    if is_admin(user_id):
        return None
    now = int(time.time())
    for limit, seconds, key in ((config.SEARCH_LIMIT_HOUR, 3600, "rate_hour"),
                                (config.SEARCH_LIMIT_DAY, 86400, "rate_day")):
        if limit and db.count_searches(user_id, now - seconds) >= limit:
            return t(key, limit=limit)
    return None


async def admin_contacts(bot, cache_store: dict) -> str:
    """@usernames of the admins (looked up once); falls back to a profile link."""
    usernames = cache_store.get("admin_usernames")
    if usernames is None:
        usernames = {}
        for admin in sorted(config.ADMIN_IDS):
            try:
                usernames[admin] = (await bot.get_chat(admin)).username
            except Exception:
                usernames[admin] = None
        cache_store["admin_usernames"] = usernames
    return ", ".join(f"@{name}" if name else f'<a href="tg://user?id={admin}">{t("admin_link")}</a>'
                     for admin, name in usernames.items())


async def deny(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contacts = await admin_contacts(context.bot, context.bot_data) if config.ADMIN_IDS else ""
    text = t("no_access")
    markup = None
    if contacts:
        text += t("no_access_contact", contacts=contacts)
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_request"), callback_data="acc:req")]])
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


REQUEST_COOLDOWN = 3600  # seconds between access requests from the same user


async def on_access_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A user without access presses the button; every admin gets approve/reject buttons."""
    cq, user = update.callback_query, update.callback_query.from_user
    if can_search(user.id):
        await cq.answer(t("already_access"), show_alert=True)
        return
    sent = context.bot_data.setdefault("access_requests", {})
    if time.time() - sent.get(user.id, 0) < REQUEST_COOLDOWN:
        await cq.answer(t("request_already"), show_alert=True)
        return
    sent[user.id] = time.time()
    handle = f"@{user.username}" if user.username else "—"
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton(t("btn_approve"), callback_data=f"accok:{user.id}"),
        InlineKeyboardButton(t("btn_reject"), callback_data=f"accno:{user.id}")]])
    text = t("request_text", name=html.escape(user.full_name), handle=handle, id=user.id)
    for admin in config.ADMIN_IDS:
        try:
            await context.bot.send_message(admin, text, parse_mode=ParseMode.HTML, reply_markup=markup)
        except Exception:
            log.warning("Could not send access request to admin %s", admin)
    await cq.answer(t("request_sent"), show_alert=True)


async def on_access_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin presses ✅/❌ under an access request."""
    cq = update.callback_query
    if not is_admin(cq.from_user.id):
        await cq.answer(t("admins_only"), show_alert=True)
        return
    action, uid = cq.data.split(":")
    uid = int(uid)
    base = cq.message.text_html if cq.message else ""
    if action == "accok":
        await asyncio.to_thread(db.add_user, uid, _name_from_request(cq.message.text))
        verdict, note = t("verdict_ok"), t("note_ok")
    else:
        verdict, note = t("verdict_no"), t("note_no")
    await cq.answer(verdict)
    await cq.edit_message_text(f"{base}\n\n{verdict} ({html.escape(cq.from_user.full_name)})",
                               parse_mode=ParseMode.HTML)
    try:
        await context.bot.send_message(uid, note)
    except Exception:
        log.warning("Could not notify user %s", uid)


def _name_from_request(text: str) -> str:
    for line in (text or "").splitlines():
        if line.startswith("👤 "):  # the name line of the request message
            return line[2:].strip()
    return ""


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
            notify_admins(app.bot, t("indexed", name=name, count=count)), loop)

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
    await asyncio.to_thread(db.purge_audit, config.AUDIT_DAYS)
    log.info("Bot started as @%s, watching folder %s", app.bot.username, config.DATA_DIR)
    if not await asyncio.to_thread(db.get_setting, "language"):
        for admin in config.ADMIN_IDS:  # first run: ask which language the bot should use
            try:
                await app.bot.send_message(admin, t("lang_prompt"), reply_markup=language_markup())
            except Exception:
                log.info("Could not ask admin %s for the language yet; they will be asked on /start", admin)
    app.bot_data["scanner"] = asyncio.get_running_loop().create_task(scanner(app))


async def post_shutdown(app: Application):
    if task := app.bot_data.get("scanner"):
        task.cancel()


def format_results(query: str, total: int, results, offset: int, cap: int = 0) -> str:
    results = [r[:3] for r in results]
    q = html.escape(query)
    if not total:
        return t("no_results", q=q)
    shown = f"{total - 1}+" if total > 1000 else str(total)
    parts = [t("results_header", shown=shown, q=q, a=offset + 1, b=offset + len(results))]
    for i, (name, row_num, fields) in enumerate(results, offset + 1):
        lines = [t("result_line", i=i, name=html.escape(name), row=row_num)]
        for key, value in fields.items():
            if len(value) > MAX_VALUE_LEN:
                value = value[:MAX_VALUE_LEN] + "…"
            lines.append(f"• <b>{html.escape(key)}:</b> {html.escape(value)}")
        parts.append("\n".join(lines))
    if cap and total > cap:
        parts.append(t("cap_note", cap=cap))
    text = "\n\n".join(parts)
    return text if len(text) <= 4000 else text[:3990] + "…"


def pager(total: int, offset: int, results=(), admin: bool = False) -> InlineKeyboardMarkup | None:
    size, buttons = config.PAGE_SIZE, []
    rows = []
    if admin and results:
        rows.append([InlineKeyboardButton(f"🗑 {i}", callback_data=f"del:{r[3]}")
                     for i, r in enumerate(results, offset + 1)])
    if offset > 0:
        buttons.append(InlineKeyboardButton(t("btn_prev"), callback_data=f"page:{max(offset - size, 0)}"))
    if offset + size < total:
        buttons.append(InlineKeyboardButton(t("btn_next"), callback_data=f"page:{offset + size}"))
    if buttons:
        rows.append(buttons)
    return InlineKeyboardMarkup(rows) if rows else None


async def run_search(query: str, offset: int, admin: bool = False):
    """Returns (text, markup, total). Non-admins can view at most MAX_RESULTS results."""
    cap = 0 if admin else config.MAX_RESULTS
    limit = min(config.PAGE_SIZE, cap - offset) if cap else config.PAGE_SIZE
    total, results = await asyncio.to_thread(db.search, query, max(limit, 0), offset, admin)
    shown_total = min(total, cap) if cap else total
    return (format_results(query, total, results, offset, cap),
            pager(shown_total, offset, results, admin), total)


async def on_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not can_search(update.effective_user.id):
        await deny(update, context)
        return
    query = " ".join(context.args) if context.args is not None else msg.text
    if not query.strip():
        await msg.reply_text(t("enter_query"))
        return
    user = update.effective_user
    if blocked := await asyncio.to_thread(rate_limit_message, user.id):
        await msg.reply_text(blocked)
        return
    context.user_data["query"] = query
    context.user_data["offset"] = 0
    text, markup, total = await run_search(query, 0, is_admin(user.id))
    await asyncio.to_thread(db.log_search, user.id, user.full_name, query, total)
    await msg.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


async def on_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    query = context.user_data.get("query")
    if not query or not can_search(cq.from_user.id):
        await cq.answer(t("search_expired"))
        return
    await cq.answer()
    offset = context.user_data["offset"] = int(cq.data.split(":")[1])
    text, markup, _ = await run_search(query, offset, is_admin(cq.from_user.id))
    await cq.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


async def on_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: remove one result row from the index (asks to confirm first)."""
    cq = update.callback_query
    if not is_admin(cq.from_user.id):
        await cq.answer(t("admins_only"), show_alert=True)
        return
    action, row_id = cq.data.split(":")
    query = context.user_data.get("query")
    offset = context.user_data.get("offset", 0)
    if action == "del":
        await cq.answer()
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_del_index"), callback_data=f"delok:{row_id}")],
            [InlineKeyboardButton(t("btn_del_source"), callback_data=f"delsrc:{row_id}")],
            [InlineKeyboardButton(t("btn_cancel"), callback_data="delno:0")]])
        await cq.edit_message_reply_markup(markup)
        return
    if action == "delsrc":
        await cq.answer(t("deleting_source"))
        try:
            async with scan_lock:  # no folder scan while the file is rewritten
                name = await asyncio.to_thread(delete_source_row, db, config.DATA_DIR, int(row_id))
            log.info("Admin %s deleted row %s from source file %s", cq.from_user.id, row_id, name)
        except PurgeError as e:
            await cq.message.reply_text(f"❌ {e}")
        except Exception:
            log.exception("Deleting row %s from source failed", row_id)
            await cq.message.reply_text(t("delete_failed"))
    elif action == "delok":
        ok = await asyncio.to_thread(db.delete_row, int(row_id))
        log.info("Admin %s deleted row %s (%s)", cq.from_user.id, row_id, "ok" if ok else "missing")
        await cq.answer(t("deleted") if ok else t("already_deleted"))
    else:
        await cq.answer()
    if not query:
        await cq.edit_message_reply_markup(None)
        return
    text, markup, _ = await run_search(query, offset, True)
    await cq.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


def language_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(name, callback_data=f"lang:{code}")
                                  for code, name in LANGS.items()]])


def start_text(admin: bool) -> str:
    return t("start") + (t("start_admin") if admin else "")


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_admin(user_id) and not db.get_setting("language"):
        # first run: the admin chooses the language of the bot
        await update.effective_message.reply_text(t("lang_prompt"), reply_markup=language_markup())
        return
    if not can_search(user_id):
        await deny(update, context)
        return
    await update.effective_message.reply_text(start_text(is_admin(user_id)))


async def on_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/language: an admin changes the language of the whole bot."""
    if is_admin(update.effective_user.id):
        await update.effective_message.reply_text(t("lang_prompt"), reply_markup=language_markup())


async def on_language_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    if not is_admin(cq.from_user.id):
        await cq.answer(t("admins_only"), show_alert=True)
        return
    code = cq.data.split(":")[1]
    await asyncio.to_thread(db.set_setting, "language", code)
    i18n.set_language(code)
    await cq.answer()
    await cq.edit_message_text(t("lang_saved"))
    await cq.message.reply_text(start_text(True))


async def on_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    files = db.list_files()
    if not files:
        await update.effective_message.reply_text(t("no_files"))
        return
    lines = [t("file_line", name=name, count=count) for _, name, count in files]
    text = t("files_header") + "\n" + "\n".join(lines)
    await update.effective_message.reply_text(text[:4000])


def _user_id_arg(context) -> int | None:
    arg = context.args[0] if context.args else ""
    return int(arg) if arg.isdigit() else None


async def on_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not is_admin(update.effective_user.id):
        return
    uid = _user_id_arg(context)
    if uid is None:
        await msg.reply_text(t("adduser_usage"))
        return
    if await asyncio.to_thread(db.add_user, uid):
        text = t("user_added", uid=uid)
    else:
        text = t("user_exists", uid=uid)
    await msg.reply_text(text)


async def on_deluser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not is_admin(update.effective_user.id):
        return
    uid = _user_id_arg(context)
    if uid is None:
        await msg.reply_text(t("deluser_usage"))
        return
    if await asyncio.to_thread(db.remove_user, uid):
        text = t("user_removed", uid=uid)
        if uid in config.ALLOWED_IDS:
            text += t("user_still_env")
    elif uid in config.ALLOWED_IDS:
        text = t("user_in_env", uid=uid)
    else:
        text = t("user_missing", uid=uid)
    await msg.reply_text(text)


async def on_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text, markup = await asyncio.to_thread(users_panel)
    await update.effective_message.reply_text(text, reply_markup=markup)


def users_panel() -> tuple[str, InlineKeyboardMarkup | None]:
    """The /users message: one ❌ button per removable user."""
    added = db.users_named()
    ids = {u for u, _ in added}
    lines = [f"• {u} {name}".rstrip() for u, name in added]
    lines += [f"• {u} {t('from_env')}" for u in sorted(config.ALLOWED_IDS) if u not in ids]
    admins = ", ".join(map(str, sorted(config.ADMIN_IDS))) or "—"
    text = (t("users_title") + "\n" + "\n".join(lines)) if lines else t("users_empty")
    text += t("users_footer", admins=admins)
    buttons = [[InlineKeyboardButton(f"❌ {name or u}"[:40], callback_data=f"rm:{u}")] for u, name in added]
    return text[:4000], InlineKeyboardMarkup(buttons) if buttons else None


async def on_remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    if not is_admin(cq.from_user.id):
        await cq.answer(t("admins_only"), show_alert=True)
        return
    removed = await asyncio.to_thread(db.remove_user, int(cq.data.split(":")[1]))
    await cq.answer(t("removed_ok") if removed else t("removed_already"))
    text, markup = await asyncio.to_thread(users_panel)
    await cq.edit_message_text(text, reply_markup=markup)


async def on_audit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/audit [user id] [count] — newest searches first."""
    if not is_admin(update.effective_user.id):
        return
    nums = [int(a) for a in context.args if a.isdigit()]
    uid = nums[0] if nums and nums[0] > 1000 else None
    limit = min(next((n for n in nums if n <= 1000), 20), 50)
    rows = await asyncio.to_thread(db.audit, limit, uid)
    if not rows:
        await update.effective_message.reply_text(t("audit_empty"))
        return
    lines = [f"{time.strftime('%m-%d %H:%M', time.localtime(ts))} | {user_id} {html.escape(name or '')}"
             f" | «{html.escape(query)}» → {total}" for ts, user_id, name, query, total in rows]
    await update.effective_message.reply_text(
        t("audit_title") + "\n" + "\n".join(lines)[:3900], parse_mode=ParseMode.HTML)


async def on_reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not is_admin(update.effective_user.id):
        return
    status = await msg.reply_text(t("reload_checking"))
    r = await run_scan(context.application)
    text = t("reload_done", added=r["added"], removed=r["removed"])
    if r["pending"]:
        text += t("reload_pending", n=r["pending"])
    if r["errors"]:
        text += t("reload_errors", n=r["errors"])
    await status.edit_text(text)


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admins can send small CSV/DB files; they are saved into the folder."""
    msg = update.effective_message
    doc = msg.document
    if not is_admin(update.effective_user.id):
        await msg.reply_text(t("upload_admin_only"))
        return
    name = os.path.basename(doc.file_name or "")
    if not name.lower().endswith(CSV_EXT + DB_EXT):
        await msg.reply_text(t("upload_type"))
        return
    if doc.file_size and doc.file_size > MAX_UPLOAD:
        await msg.reply_text(t("upload_big"))
        return
    status = await msg.reply_text(t("receiving"))
    target_dir = os.path.join(config.DATA_DIR, "uploads")
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, name)
    tg_file = await context.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(path + ".part")
    os.replace(path + ".part", path)
    past = time.time() - 120  # the file is complete; skip the "still copying" wait
    os.utime(path, (past, past))
    await status.edit_text(t("indexing"))
    r = await run_scan(context.application)
    await status.edit_text(t("saved", n=r["added"]) if not r["errors"] else t("unreadable"))


def build_app() -> Application:
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is not set in .env (run: python -m csvbot.check)")
    builder = (Application.builder().token(config.BOT_TOKEN)
               .base_url(f"{config.API_URL}/bot").base_file_url(f"{config.API_URL}/file/bot")
               .post_init(post_init).post_shutdown(post_shutdown))
    if config.proxy():
        builder = builder.proxy(config.proxy()).get_updates_proxy(config.proxy())
    app = builder.build()
    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("start", on_start, filters=private))
    app.add_handler(CommandHandler("search", on_search, filters=private))
    app.add_handler(CommandHandler("files", on_files, filters=private))
    app.add_handler(CommandHandler("reload", on_reload, filters=private))
    app.add_handler(CommandHandler("adduser", on_adduser, filters=private))
    app.add_handler(CommandHandler("deluser", on_deluser, filters=private))
    app.add_handler(CommandHandler("users", on_users, filters=private))
    app.add_handler(CommandHandler("audit", on_audit, filters=private))
    app.add_handler(CommandHandler("language", on_language, filters=private))
    app.add_handler(MessageHandler(private & filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, on_search))
    app.add_handler(CallbackQueryHandler(on_language_chosen, pattern=r"^lang:[a-z]{2}$"))
    app.add_handler(CallbackQueryHandler(on_access_request, pattern=r"^acc:req$"))
    app.add_handler(CallbackQueryHandler(on_access_decision, pattern=r"^acc(ok|no):\d+$"))
    app.add_handler(CallbackQueryHandler(on_remove_user, pattern=r"^rm:\d+$"))
    app.add_handler(CallbackQueryHandler(on_page, pattern=r"^page:\d+$"))
    app.add_handler(CallbackQueryHandler(on_delete, pattern=r"^(del|delok|delsrc|delno):\d+$"))
    return app


def main():
    if not config.ADMIN_IDS:
        log.warning("ADMIN_IDS is empty: nobody can manage users, add files or use /reload")
    try:
        build_app().run_polling(allowed_updates=Update.ALL_TYPES)
    except InvalidToken:
        raise SystemExit("❌ Telegram rejected BOT_TOKEN; copy it again from @BotFather into .env")
    except NetworkError as e:
        raise SystemExit(f"❌ Cannot reach Telegram ({e}); turn on the VPN and run: python -m csvbot.check")


if __name__ == "__main__":
    main()
