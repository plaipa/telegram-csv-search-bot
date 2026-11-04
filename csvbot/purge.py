"""Remove a single row from the original CSV / SQLite file, not just the index.

The row is found by its position in the source and compared with the text
stored in the index; if they differ (file edited by hand, odd formatting) the
file is left untouched. The file's mtime is kept and its index entries are
re-keyed to the new size, so deleting never triggers a re-index.
"""
import csv
import os
import re
import shutil
import sqlite3

from .db import SEP, Database, writer_lock
from .loader import csv_format
from .sources import CSV_EXT, PREFIX, _cell

_UID = re.compile(r"^(?P<rel>.+)\|(?P<size>\d+)\|(?P<mtime>\d+)(?:\|(?P<table>.*))?$", re.S)


class PurgeError(Exception):
    pass


class _Tee:
    """Line iterator that remembers the raw lines of the record being parsed."""
    def __init__(self, f):
        self.f, self.buf = f, []

    def __iter__(self):
        return self

    def __next__(self):
        line = next(self.f)
        self.buf.append(line)
        return line


def _rewrite_csv(path: str, position: int, expected: str):
    encoding, dialect = csv_format(path)
    with open(path, "rb") as f:
        if encoding == "utf-8-sig" and f.read(3) != b"\xef\xbb\xbf":
            encoding = "utf-8"  # don't add a BOM the file never had
    tmp = path + ".purge.tmp"
    removed = False
    try:
        with open(path, encoding=encoding, errors="surrogateescape", newline="") as src, \
                open(tmp, "w", encoding=encoding, errors="surrogateescape", newline="") as out:
            tee = _Tee(src)
            seen_header, n = False, 0
            for row in csv.reader(tee, dialect):
                keep = True
                if any(c.strip() for c in row):
                    if not seen_header:
                        seen_header = True
                    else:
                        n += 1
                        if n == position:
                            if SEP.join(c.strip() for c in row) != expected:
                                raise PurgeError("محتوای ردیف در فایل با ایندکس نمی‌خواند؛ فایل تغییر نکرد.")
                            keep, removed = False, True
                if keep:
                    out.writelines(tee.buf)
                tee.buf.clear()
        if not removed:
            raise PurgeError("ردیف در فایل پیدا نشد؛ فایل تغییر نکرد.")
        shutil.copymode(path, tmp)
        st = os.stat(path)
        os.utime(tmp, ns=(st.st_atime_ns, st.st_mtime_ns))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _delete_sqlite(path: str, table: str, position: int, expected: str):
    st = os.stat(path)
    con = sqlite3.connect(path, timeout=30)
    try:
        try:
            cur = con.execute('SELECT rowid, * FROM "{}"'.format(table.replace('"', '""')))
        except sqlite3.Error:
            raise PurgeError("این جدول rowid ندارد و حذف از آن پشتیبانی نمی‌شود.")
        n, target = 0, None
        for rid, *cells in cur:
            cells = [_cell(v) for v in cells]
            if any(cells):
                n += 1
                if n == position:
                    target = (rid, cells)
                    break
        cur.close()
        if not target or SEP.join(target[1]) != expected:
            raise PurgeError("محتوای ردیف در فایل با ایندکس نمی‌خواند؛ فایل تغییر نکرد.")
        with con:
            con.execute('DELETE FROM "{}" WHERE rowid = ?'.format(table.replace('"', '""')),
                        (target[0],))
    finally:
        con.close()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))


def delete_source_row(db: Database, data_dir: str, row_id: int) -> str:
    """Delete the row from its source file and the index. Returns the file name."""
    with writer_lock(db.path):
        loc = db.locate(row_id)
        if not loc:
            raise PurgeError("این ردیف دیگر در ایندکس نیست.")
        file_id, uid, position, data = loc
        m = _UID.match(uid[len(PREFIX):]) if uid and uid.startswith(PREFIX) else None
        if not m:
            raise PurgeError("این ردیف از فایل پوشه‌ی data نیست.")
        root = os.path.realpath(data_dir)
        path = os.path.realpath(os.path.join(root, m["rel"]))
        if os.path.commonpath([root, path]) != root or not os.path.isfile(path):
            raise PurgeError("فایل اصلی پیدا نشد.")
        st = os.stat(path)
        if st.st_size != int(m["size"]) or int(st.st_mtime) != int(m["mtime"]):
            raise PurgeError("فایل بعد از ثبت تغییر کرده؛ ابتدا /reload بزنید.")
        if os.path.splitext(path)[1].lower() in CSV_EXT:
            _rewrite_csv(path, position, data)
        else:
            _delete_sqlite(path, m["table"] or "", position, data)
        old = f"{PREFIX}{m['rel']}|{m['size']}|{m['mtime']}"
        new = f"{PREFIX}{m['rel']}|{os.stat(path).st_size}|{m['mtime']}"
        db.mark_purged(file_id, row_id, old, new)
        db.delete_row(row_id)
        return m["rel"] + (f" › {m['table']}" if m["table"] else "")
