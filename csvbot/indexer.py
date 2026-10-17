"""Download a CSV document from Telegram (any size, via MTProto) and index it."""
import asyncio
import logging
import os
import time

from telethon.tl.types import DocumentAttributeFilename

from . import config
from .db import Database
from .loader import read_csv

log = logging.getLogger("csvbot.indexer")
CSV_MIME = ("text/csv", "text/tab-separated-values", "text/comma-separated-values")

# Index one file at a time: SQLite has a single writer and files are huge.
_lock = asyncio.Lock()


def file_name(doc) -> str:
    for attr in doc.attributes:
        if isinstance(attr, DocumentAttributeFilename):
            return attr.file_name
    return f"{doc.id}.csv"


def is_csv(doc) -> bool:
    return bool(doc) and (file_name(doc).lower().endswith((".csv", ".tsv"))
                          or doc.mime_type in CSV_MIME)


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


async def index_message(client, db: Database, message, report=None) -> str:
    """Index the CSV document attached to `message`. `report(text)` is an
    optional coroutine called with throttled progress updates."""
    doc = message.document
    name, unique_id = file_name(doc), f"tg:{doc.id}"
    if db.has_file(unique_id):
        return f"ℹ️ فایل «{name}» قبلاً ثبت شده است."

    last = 0.0

    async def throttled(text: str):
        nonlocal last
        if report and time.monotonic() - last > 5:
            last = time.monotonic()
            try:
                await report(text)
            except Exception:  # e.g. "message not modified"
                pass

    async with _lock:
        os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
        path = os.path.join(config.DOWNLOAD_DIR, f"{doc.id}.part")
        try:
            log.info("Downloading %s (%s)", name, human_size(doc.size))
            await client.download_media(
                message, file=path,
                progress_callback=lambda done, total: asyncio.ensure_future(throttled(
                    f"⬇️ دانلود «{name}»: {done * 100 // max(total, 1)}٪ از {human_size(total)}")),
            )
            headers, rows = read_csv(path)
            if not headers:
                return f"⚠️ فایل «{name}» خالی است یا قابل خواندن نیست."

            loop = asyncio.get_running_loop()

            def progress(n: int):
                asyncio.run_coroutine_threadsafe(
                    throttled(f"🗂 ثبت «{name}»: {n:,} ردیف..."), loop)

            count = await asyncio.to_thread(db.add_file, unique_id, name, headers, rows, progress)
        finally:
            if os.path.exists(path):
                os.remove(path)
    log.info("Indexed %s (%d rows)", name, count)
    return f"✅ فایل «{name}» با {count:,} ردیف ثبت شد."
