import os
import sqlite3
import unittest

from csvbot.purge import PurgeError, delete_source_row
from test_sources import FolderIndexTest as Base


class PurgeTest(Base):
    def row_id(self, word):
        return self.db.search(word, with_ids=True)[1][0][3]

    def test_csv_rows_are_removed_from_file_and_index(self):
        path = self.write_csv("a.csv", 'name,note\r\nali,"two\r\nlines"\r\n\r\nreza,x\r\nsara,y\r\n')
        self.folder.sync()
        mtime = os.stat(path).st_mtime
        delete_source_row(self.db, self.data, self.row_id("reza"))
        delete_source_row(self.db, self.data, self.row_id("sara"))  # position shifted by the first delete
        with open(path, newline="") as f:
            self.assertEqual(f.read(), 'name,note\r\nali,"two\r\nlines"\r\n\r\n')
        self.assertEqual(os.stat(path).st_mtime, mtime)
        self.assertEqual(self.db.search("reza")[0] + self.db.search("sara")[0], 0)
        self.assertEqual(self.folder.sync()["added"], 0)  # re-keyed: no re-index
        self.assertEqual(self.db.search("ali")[0], 1)
        delete_source_row(self.db, self.data, self.row_id("ali"))
        with open(path, newline="") as f:
            self.assertEqual(f.read(), "name,note\r\n\r\n")

    def test_index_only_delete_does_not_confuse_positions(self):
        path = self.write_csv("a.csv", "n\none\ntwo\nthree\n")
        self.folder.sync()
        self.db.delete_row(self.row_id("one"))
        delete_source_row(self.db, self.data, self.row_id("three"))
        with open(path) as f:
            self.assertEqual(f.read(), "n\none\ntwo\n")

    def test_mismatch_leaves_file_alone(self):
        path = self.write_csv("a.csv", "n\none\ntwo\n")
        self.folder.sync()
        rid = self.row_id("two")
        st = os.stat(path)
        with open(path, "w") as f:
            f.write("n\ntwo\none\n")
        os.utime(path, (st.st_atime, st.st_mtime))
        with self.assertRaises(PurgeError):  # same size, but the row at that position changed
            delete_source_row(self.db, self.data, rid)
        with open(path) as f:
            self.assertEqual(f.read(), "n\ntwo\none\n")

    def test_sqlite_row(self):
        path = self.make_db("p.db")
        self.folder.sync()
        delete_source_row(self.db, self.data, self.row_id("علی"))
        con = sqlite3.connect(path)
        self.assertEqual(con.execute("SELECT name FROM people").fetchall(), [("سارا",)])
        con.close()
        self.assertEqual(self.folder.sync()["added"], 0)
        self.assertEqual(self.db.search("12ب345")[0], 1)
        self.assertEqual(self.db.search("سارا")[0], 1)


if __name__ == "__main__":
    unittest.main()
