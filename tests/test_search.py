import os
import tempfile
import unittest

from csvbot.db import Database
from csvbot.loader import parse_csv


class SearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "t.db"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_utf8_persian(self):
        data = "نام;شهر;تلفن\nعلي رضايي;تهران;۰۹۱۲۱۲۳۴۵۶۷\nمریم کاظمی;شیراز;09351112233\n".encode("utf-8-sig")
        headers, rows = parse_csv(data)
        self.assertEqual(headers, ["نام", "شهر", "تلفن"])
        self.db.add_file("u1", "people.csv", headers, rows)
        # Arabic ي in data, Persian ی in query; Persian digits in data, Latin in query
        total, res = self.db.search("علی")
        self.assertEqual(total, 1)
        self.assertEqual(res[0][2]["شهر"], "تهران")
        self.assertEqual(self.db.search("09121234567")[0], 1)
        self.assertEqual(self.db.search("۰۹۳۵")[0], 1)  # prefix match
        self.assertEqual(self.db.search("مریم تهران")[0], 0)  # all words required
        self.assertEqual(self.db.search('"مریم کاظمی"')[0], 1)

    def test_cp1256_and_delete(self):
        data = "name,city\nحسن,اصفهان\n".encode("cp1256")
        headers, rows = parse_csv(data)
        fid = self.db.add_file("u2", "old.csv", headers, rows)
        self.assertTrue(self.db.has_file("u2"))
        self.assertEqual(self.db.search("اصفهان")[0], 1)
        self.assertTrue(self.db.delete_file(fid))
        self.assertEqual(self.db.search("اصفهان")[0], 0)

    def test_paging_and_garbage_query(self):
        rows = [[f"item {i}", "x"] for i in range(12)]
        self.db.add_file(None, "a.csv", ["a", "b"], rows)
        total, res = self.db.search("item", limit=5, offset=10)
        self.assertEqual((total, len(res)), (12, 2))
        self.assertEqual(self.db.search('*) OR "')[0], 0)


if __name__ == "__main__":
    unittest.main()
