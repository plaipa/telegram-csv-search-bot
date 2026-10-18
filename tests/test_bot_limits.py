import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from csvbot import bot, config
from csvbot.db import Database


class LimitsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = (bot.db, config.ADMIN_IDS, config.ALLOWED_IDS, config.SEARCH_LIMIT_HOUR,
                    config.SEARCH_LIMIT_DAY, config.MAX_RESULTS)
        bot.db = Database(os.path.join(self.tmp.name, "i.db"))
        config.ADMIN_IDS, config.ALLOWED_IDS = {1}, set()
        config.SEARCH_LIMIT_HOUR, config.SEARCH_LIMIT_DAY, config.MAX_RESULTS = 3, 0, 4
        path = os.path.join(self.tmp.name, "a.csv")
        with open(path, "w") as f:
            f.write("n\n" + "".join(f"item {i}\n" for i in range(10)))
        bot.db.add_file("a", "a.csv", *__import__("csvbot.loader", fromlist=["x"]).read_csv(path))

    def tearDown(self):
        (bot.db, config.ADMIN_IDS, config.ALLOWED_IDS, config.SEARCH_LIMIT_HOUR,
         config.SEARCH_LIMIT_DAY, config.MAX_RESULTS) = self.old
        self.tmp.cleanup()

    def search(self, uid, text="item"):
        sent = []

        async def reply(t, **k):
            sent.append((t, k.get("reply_markup")))
        upd = NS(effective_user=NS(id=uid, full_name="U"), effective_message=NS(text=text, reply_text=reply))
        ctx = NS(args=None, user_data={}, bot=NS(get_chat=AsyncMock()), bot_data={})
        asyncio.run(bot.on_search(upd, ctx))
        return sent[-1]

    def test_closed_by_default(self):
        self.assertIn("دسترسی ندارید", self.search(9)[0])
        bot.db.add_user(9)
        self.assertIn("نتیجه", self.search(9)[0])

    def test_rate_limit_and_result_cap_and_audit(self):
        bot.db.add_user(9)
        text, markup = self.search(9)
        self.assertIn("فقط 4 نتیجه", text)
        self.assertEqual(text.count("📄"), 4)
        self.search(9), self.search(9)
        self.assertIn("سقف 3 جستجو", self.search(9)[0])
        self.assertEqual(len(bot.db.audit(10, 9)), 3)  # blocked attempt not counted
        for _ in range(5):  # admins are exempt but logged
            self.assertNotIn("سقف", self.search(1)[0])
        self.assertEqual(len(bot.db.audit(50, 1)), 5)


if __name__ == "__main__":
    unittest.main()
