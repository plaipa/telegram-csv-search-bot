import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from csvbot import bot, config
from csvbot.db import Database


class AccessFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = (bot.db, config.ADMIN_IDS, config.ALLOWED_IDS)
        bot.db = Database(os.path.join(self.tmp.name, "i.db"))
        config.ADMIN_IDS, config.ALLOWED_IDS = {1}, {3}
        self.sent = []
        self.ctx = NS(bot=NS(send_message=AsyncMock(side_effect=self.record), get_chat=AsyncMock()),
                      bot_data={}, user_data={})

    def tearDown(self):
        bot.db, config.ADMIN_IDS, config.ALLOWED_IDS = self.old
        self.tmp.cleanup()

    async def record(self, chat, text, **kw):
        self.sent.append((chat, text, kw.get("reply_markup")))

    def callback(self, user_id, data, text="", name="U"):
        edits, answers = [], []

        async def edit(t, **k):
            edits.append((t, k.get("reply_markup")))

        async def answer(t=None, **k):
            answers.append(t)
        msg = NS(text=text, text_html=text, edit_text=edit)
        cq = NS(from_user=NS(id=user_id, full_name=name, username="u"), data=data, message=msg,
                answer=answer, edit_message_text=edit)
        return NS(callback_query=cq), edits, answers

    def test_request_approve_and_remove(self):
        # a stranger asks for access: the admin gets approve/reject buttons
        upd, _, answers = self.callback(9, "acc:req", name="Ali Test")
        asyncio.run(bot.on_access_request(upd, self.ctx))
        chat, text, markup = self.sent[-1]
        self.assertEqual(chat, 1)
        self.assertIn("Ali Test", text)
        self.assertEqual([b.callback_data for b in markup.inline_keyboard[0]], ["accok:9", "accno:9"])
        # asking again right away is ignored
        n = len(self.sent)
        asyncio.run(bot.on_access_request(upd, self.ctx))
        self.assertEqual(len(self.sent), n)
        # non-admins cannot approve
        upd, _, answers = self.callback(9, "accok:9", text)
        asyncio.run(bot.on_access_decision(upd, self.ctx))
        self.assertFalse(bot.can_search(9))
        # admin approves: user is added with their name and gets notified
        upd, edits, _ = self.callback(1, "accok:9", text)
        asyncio.run(bot.on_access_decision(upd, self.ctx))
        self.assertTrue(bot.can_search(9))
        self.assertEqual(bot.db.users_named(), [(9, "Ali Test")])
        self.assertEqual(self.sent[-1][0], 9)
        # /users shows a remove button; pressing it removes the user
        text, markup = bot.users_panel()
        self.assertIn("9 Ali Test", text)
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "rm:9")
        upd, edits, _ = self.callback(1, "rm:9")
        asyncio.run(bot.on_remove_user(upd, self.ctx))
        self.assertFalse(bot.can_search(9))

    def test_reject(self):
        upd, _, _ = self.callback(1, "accno:9", "نام: X")
        asyncio.run(bot.on_access_decision(upd, self.ctx))
        self.assertFalse(bot.can_search(9))
        self.assertIn("رد", self.sent[-1][1])


if __name__ == "__main__":
    unittest.main()
