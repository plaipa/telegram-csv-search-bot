"""Index every CSV file already in the channel, using your own Telegram
account (bots cannot read channel history). Run once; it skips files that
are already indexed, so it is safe to re-run.

Usage: python -m csvbot.sync
"""
import asyncio
import logging

from telethon import TelegramClient

from . import config
from .db import Database
from .indexer import index_message, is_csv

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    level=logging.INFO)


async def main():
    if not config.CHANNEL:
        raise SystemExit("Set CHANNEL in .env")
    db = Database(config.DB_PATH)
    # First run asks for your phone number and login code.
    async with TelegramClient("user", config.API_ID, config.API_HASH) as client:
        async for message in client.iter_messages(config.channel_ref(), reverse=True):
            if message.document and is_csv(message.document):
                async def report(text):
                    print("\r" + text.ljust(70), end="", flush=True)
                try:
                    print("\n" + await index_message(client, db, message, report))
                except Exception:
                    logging.exception("Failed on message %s", message.id)


if __name__ == "__main__":
    asyncio.run(main())
