import os
import sqlite3
import tempfile
import time
import unittest

from csvbot.db import Database
from csvbot.sources import FolderIndex


def age(path, seconds=120):
    t = time.time() - seconds
    os.utime(path, (t, t))


class FolderIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = os.path.join(self.tmp.name, "data")
        os.makedirs(os.path.join(self.data, "sub"))
        # Index lives inside the data folder: it must not index itself.
        self.db = Database(os.path.join(self.data, "index.db"))
        self.folder = FolderIndex(self.db, self.data)

    def tearDown(self):
        self.tmp.cleanup()

    def write_csv(self, rel, text):
        path = os.path.join(self.data, rel)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        age(path)
        return path

    def make_db(self, rel):
        path = os.path.join(self.data, rel)
        con = sqlite3.connect(path)
        con.executescript("""
            CREATE TABLE people (name TEXT, city TEXT, photo BLOB, age INTEGER);
            INSERT INTO people VALUES ('علی', 'تهران', x'00ff', 30), ('سارا', NULL, NULL, 25);
            CREATE TABLE cars (plate TEXT);
            INSERT INTO cars VALUES ('12ب345');
            CREATE VIRTUAL TABLE notes USING fts5(body);
            INSERT INTO notes VALUES ('علی duplicate');
        """)
        con.commit()
        con.close()
        age(path)
        return path

    def test_csv_and_sqlite_tables(self):
        self.write_csv("sub/a.csv", "نام,تلفن\nمریم,0912\n")
        self.make_db("people.db")
        r = self.folder.sync()
        self.assertEqual((r["added"], r["errors"]), (3, 0))
        names = sorted(n for _, n, _ in self.db.list_files())
        self.assertEqual(names, ["people.db › cars", "people.db › people", "sub/a.csv"])
        total, res = self.db.search("علی")
        self.assertEqual(total, 1)  # FTS table "notes" and its shadow tables are skipped
        self.assertEqual(res[0], ("people.db › people", 1, {"name": "علی", "city": "تهران", "age": "30"}))
        self.assertEqual(self.db.search("12ب345")[0], 1)
        self.assertEqual(self.folder.sync()["added"], 0)  # nothing new

    def test_changed_and_deleted_files(self):
        path = self.write_csv("a.csv", "h\nold\n")
        self.folder.sync()
        self.write_csv("a.csv", "h\nnew value\n")
        r = self.folder.sync()
        self.assertEqual((r["added"], r["removed"]), (1, 1))
        self.assertEqual(self.db.search("old")[0], 0)
        self.assertEqual(self.db.search("new")[0], 1)
        os.remove(path)
        self.assertEqual(self.folder.sync()["removed"], 1)
        self.assertEqual(self.db.list_files(), [])

    def test_still_copying_and_invalid_db(self):
        path = os.path.join(self.data, "fresh.csv")
        with open(path, "w") as f:
            f.write("h\nx\n")
        with open(os.path.join(self.data, "fake.db"), "w") as f:
            f.write("not sqlite")
        age(os.path.join(self.data, "fake.db"))
        r = self.folder.sync()
        self.assertEqual((r["added"], r["pending"], r["errors"]), (0, 1, 0))
        age(path)
        self.assertEqual(self.folder.sync()["added"], 1)


if __name__ == "__main__":
    unittest.main()
