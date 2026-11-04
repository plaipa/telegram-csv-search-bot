import os
import tempfile
import unittest

from csvbot.db import Database
from csvbot.loader import read_csv


class SearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "t.db"))

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name: str, data: bytes) -> str:
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def add(self, uid, name, data: bytes):
        headers, rows = read_csv(self.write(name, data))
        return headers, self.db.add_file(uid, name, headers, rows)

    def test_utf8_persian(self):
        data = "نام;شهر;تلفن\n\nعلي رضايي;تهران;۰۹۱۲۱۲۳۴۵۶۷\nمریم کاظمی;شیراز;09351112233\n"
        headers, count = self.add("u1", "people.csv", data.encode("utf-8-sig"))
        self.assertEqual((headers, count), (["نام", "شهر", "تلفن"], 2))
        # Arabic ي in data, Persian ی in query; Persian digits in data, Latin in query
        total, res = self.db.search("علی")
        self.assertEqual(total, 1)
        self.assertEqual(res[0], ("people.csv", 1, {"نام": "علي رضايي", "شهر": "تهران", "تلفن": "۰۹۱۲۱۲۳۴۵۶۷"}))
        self.assertEqual(self.db.search("09121234567")[0], 1)
        self.assertEqual(self.db.search("۰۹۳۵")[0], 1)  # prefix match
        self.assertEqual(self.db.search("مریم تهران")[0], 0)  # all words required
        self.assertEqual(self.db.search('"مریم کاظمی"')[1][0][1], 2)

    def test_hindi(self):
        self.add("h", "h.csv", "नाम,शहर,नोट\nराहुल शर्मा,दिल्ली,०९१२३४५६७८९ फ़ोन\n".encode())
        for q in ("राहुल", "शर्मा", "दिल्ली", "09123456789", "०९१२", "फोन", "फ़ोन", '"राहुल शर्मा"'):
            self.assertEqual(self.db.search(q)[0], 1, q)

    def test_chinese_and_russian(self):
        self.add("z", "z.csv", "姓名,备注\n王小明,我在北京工作\n李华,Привет мир Москва\n".encode())
        for q, n in (("北京", 1), ("工作", 1), ("在北京", 1), ("小明", 1), ("北", 1), ("京北", 0),
                     ("王小明 北京", 1), ("привет", 1), ("МОСК", 1), ("мир москва", 1), ('"我在北京"', 1)):
            self.assertEqual(self.db.search(q)[0], n, q)

    def test_legacy_encodings(self):
        cases = [("ru", "имя,город\nИван,Москва\nПётр,Санкт-Петербург\nАнна,Казань\n", "cp1251", "москва"),
                 ("zh", "姓名,城市\n王小明,北京\n李华,上海\n张伟,广州\n", "gbk", "北京"),
                 ("tw", "姓名,城市\n王小明,台北\n李華,高雄\n", "big5", "高雄")]
        for uid, text, enc, word in cases:
            self.add(uid, uid + ".csv", text.encode(enc))
            self.assertEqual(self.db.search(word)[0], 1, enc)

    def test_users(self):
        self.assertTrue(self.db.add_user(5))
        self.assertFalse(self.db.add_user(5))
        self.assertEqual(self.db.users(), [5])
        self.assertTrue(self.db.remove_user(5))
        self.assertFalse(self.db.remove_user(5))
        self.assertEqual(self.db.users(), [])

    def test_delete_row(self):
        self.add("d", "d.csv", b"a,b\nfoo,1\nfoo,2\nbar,3\n")
        _, res = self.db.search("foo", with_ids=True)
        self.assertTrue(self.db.delete_row(res[0][3]))
        self.assertFalse(self.db.delete_row(res[0][3]))
        total, res = self.db.search("foo")
        self.assertEqual((total, res[0][1]), (1, 2))  # row numbers stay stable
        self.assertEqual(self.db.search("bar")[0], 1)
        self.assertEqual(self.db.list_files()[0][2], 2)

    def test_cp1256_and_delete(self):
        _, count = self.add("u2", "old.csv", "name,city\nحسن,اصفهان\n".encode("cp1256"))
        self.assertTrue(self.db.has_file("u2"))
        self.assertEqual(self.db.search("اصفهان")[0], 1)
        fid = self.db.list_files()[0][0]
        self.assertTrue(self.db.delete_file(fid))
        self.assertEqual(self.db.search("اصفهان")[0], 0)
        self.assertEqual(self.db.list_files(), [])

    def test_two_files_reindex_and_paging(self):
        self.add("a", "a.csv", ("a,b\n" + "".join(f"item {i},x\n" for i in range(12))).encode())
        self.add("b", "b.csv", b"c\nitem z\n")
        self.add("a", "a.csv", ("a,b\n" + "".join(f"item {i},x\n" for i in range(12))).encode())
        total, res = self.db.search("item", limit=5, offset=10)
        self.assertEqual((total, len(res)), (13, 3))
        self.assertEqual([(r[0], r[1]) for r in res], [("a.csv", 10), ("a.csv", 11), ("a.csv", 12)])
        self.assertEqual(self.db.search("z")[1], [("b.csv", 1, {"c": "item z"})])
        self.assertEqual(self.db.search('*) OR "')[0], 0)

    def test_interrupted_file_is_cleaned_up(self):
        def broken():
            yield ["x"]
            raise IOError("disk")
        with self.assertRaises(IOError):
            self.db.add_file("c", "c.csv", ["h"], broken())
        Database(self.db.path)  # restart
        self.assertFalse(self.db.has_file("c"))
        self.assertEqual(self.db.search("x")[0], 0)


if __name__ == "__main__":
    unittest.main()
