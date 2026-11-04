import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from csvbot import bot, config, i18n
from csvbot.db import Database


class AccessFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = (bot.db, config.ADMIN_IDS, config.ALLOWED_IDS)
        bot.db = Database(os.path.join(self.tmp.name, "i.db"))
        i18n.set_language("en")
        config.ADMIN_IDS, config.ALLOWED_IDS = {1}, {3}
        self.sent = []
        self.ctx = NS(bot=NS(send_message=AsyncMock(side_effect=self.record), get_chat=AsyncMock()),
                      bot_data={}, user_data={})

    def tearDown(self):
        bot.db, config.ADMIN_IDS, config.ALLOWED_IDS = self.old
        i18n.set_language(i18n.DEFAULT)
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
        upd, _, _ = self.callback(1, "accno:9", "📩 Access request\n👤 X")
        asyncio.run(bot.on_access_decision(upd, self.ctx))
        self.assertFalse(bot.can_search(9))
        self.assertIn("rejected", self.sent[-1][1])

    def test_first_start_asks_admin_for_language(self):
        replies = []

        async def reply(text, **kw):
            replies.append((text, kw.get("reply_markup")))

        def start(uid):
            upd = NS(effective_user=NS(id=uid), effective_message=NS(reply_text=reply))
            asyncio.run(bot.on_start(upd, self.ctx))
            return replies[-1]
        # a stranger sees the no-access message (English until an admin chooses)
        self.assertIn("don't have access", start(9)[0])
        # the admin is asked first, with one button per language
        text, markup = start(1)
        self.assertIn("🌐", text)
        self.assertEqual([b.callback_data for b in markup.inline_keyboard[0]],
                         ["lang:en", "lang:fa", "lang:hi", "lang:ru", "lang:zh"])
        # a non-admin cannot choose
        upd, _, _ = self.callback(9, "lang:fa")
        asyncio.run(bot.on_language_chosen(upd, self.ctx))
        self.assertIsNone(bot.db.get_setting("language"))
        # the admin picks Persian: it is saved and used everywhere
        upd, edits, _ = self.callback(1, "lang:fa")
        upd.callback_query.message.reply_text = reply
        asyncio.run(bot.on_language_chosen(upd, self.ctx))
        self.assertEqual(bot.db.get_setting("language"), "fa")
        self.assertIn("فارسی", edits[-1][0])
        self.assertIn("/language", replies[-1][0])
        self.assertIn("دسترسی ندارید", start(9)[0])
        self.assertIn("سلام", start(1)[0])


if __name__ == "__main__":
    unittest.main()
