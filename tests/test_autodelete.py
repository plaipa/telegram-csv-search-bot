import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from csvbot import bot, config, i18n
from csvbot.db import Database
from csvbot.loader import read_csv


class AutoDeleteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = (bot.db, config.ADMIN_IDS, config.AUTO_DELETE_SECONDS)
        bot.db = Database(os.path.join(self.tmp.name, "i.db"))
        path = os.path.join(self.tmp.name, "a.csv")
        with open(path, "w") as f:
            f.write("n\nhello world\n")
        bot.db.add_file("a", "a.csv", *read_csv(path))
        config.ADMIN_IDS, config.AUTO_DELETE_SECONDS = {1}, 0.05
        i18n.set_language("en")

    def tearDown(self):
        bot.db, config.ADMIN_IDS, config.AUTO_DELETE_SECONDS = self.old
        i18n.set_language(i18n.DEFAULT)
        self.tmp.cleanup()

    def test_result_and_question_are_deleted_and_page_turn_restarts_the_timer(self):
        deleted = []

        async def run():
            async def reply(text, **kw):
                self.text = text
                return NS(message_id=11)
            ctx = NS(args=None, user_data={}, bot_data={},
                     bot=NS(delete_message=AsyncMock(side_effect=lambda c, m: deleted.append((c, m)))))
            msg = NS(text="hello", message_id=10, chat_id=5, reply_text=reply)
            await bot.on_search(NS(effective_user=NS(id=1, full_name="A"), effective_message=msg), ctx)
            self.assertIn("will be deleted in 0.05 seconds", self.text)
            await asyncio.sleep(0.03)
            self.assertEqual(deleted, [])
            bot.schedule_delete(ctx, 5, 11, 10)  # a page turn restarts the countdown
            await asyncio.sleep(0.03)
            self.assertEqual(deleted, [])
            await asyncio.sleep(0.1)
            self.assertEqual(deleted, [(5, 11), (5, 10)])
            self.assertEqual(ctx.bot_data["delete_tasks"], {})
        asyncio.run(run())

    def test_zero_keeps_messages(self):
        config.AUTO_DELETE_SECONDS = 0
        ctx = NS(bot_data={}, bot=NS())
        asyncio.run(asyncio.sleep(0))
        bot.schedule_delete(ctx, 5, 11)
        self.assertEqual(ctx.bot_data, {})

    def test_admin_toggles_auto_delete_in_settings(self):
        config.AUTO_DELETE_SECONDS = 60

        def press(user_id, data):
            edits, answers = [], []

            async def edit(text, **kw):
                edits.append((text, kw.get("reply_markup")))

            async def answer(text=None, **kw):
                answers.append(text)
            cq = NS(from_user=NS(id=user_id), data=data, answer=answer, edit_message_text=edit)
            asyncio.run(bot.on_setting_chosen(NS(callback_query=cq), NS()))
            return edits, answers
        self.assertEqual(bot.delete_delay(), 60)  # the .env default until an admin decides
        press(5, "ad:toggle")  # a non-admin cannot change it
        self.assertEqual(bot.delete_delay(), 60)
        edits, _ = press(1, "ad:toggle")
        self.assertEqual(bot.delete_delay(), 0)
        self.assertIn("OFF", edits[-1][0])
        edits, _ = press(1, "ad:300")
        self.assertEqual(bot.delete_delay(), 300)
        self.assertIn("300", edits[-1][0])
        press(1, "ad:toggle")
        press(1, "ad:toggle")  # on again: back to the last chosen time
        self.assertEqual(bot.delete_delay(), 300)
        text, markup = bot.settings_panel()
        self.assertEqual([b.callback_data for b in markup.inline_keyboard[1]], ["ad:30", "ad:60", "ad:300"])


if __name__ == "__main__":
    unittest.main()
