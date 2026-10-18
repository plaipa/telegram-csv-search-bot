"""SQLite full-text index of CSV rows, designed for tens of millions of rows.

Raw rows are stored once in `rows`; `rows_fts` is a contentless FTS5 index
over the normalized text, sharing rowids with `rows`. Each file occupies a
contiguous rowid range [first_id, last_id].
"""
import sqlite3
import time
from contextlib import closing, contextmanager
from typing import Callable, Iterable

from .text import CJK, normalize, tokens

SEP = "\x1f"
BATCH = 20_000
COUNT_CAP = 1000

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None


@contextmanager
def writer_lock(db_path: str, wait: bool = True):
    """Only one process (bot or sync script) may index at a time, because row
    ids are allocated as contiguous ranges per file. Yields False if
    wait=False and another process holds the lock."""
    if fcntl is None:
        yield True
        return
    with open(db_path + ".lock", "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    unique_id TEXT UNIQUE,
    name TEXT NOT NULL,
    headers TEXT NOT NULL,
    first_id INTEGER,
    last_id INTEGER,
    row_count INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    added_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, added_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY, ts INTEGER NOT NULL, user_id INTEGER NOT NULL,
    name TEXT, query TEXT NOT NULL, total INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_user_ts ON audit (user_id, ts);
CREATE TABLE IF NOT EXISTS purged (
    file_id INTEGER, row_id INTEGER, PRIMARY KEY (file_id, row_id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS rows (id INTEGER PRIMARY KEY, data TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS rows_fts USING fts5(
    body, content='', contentless_delete=1,
    tokenize='unicode61 remove_diacritics 2'
);
"""


class Database:
    def __init__(self, path: str):
        if sqlite3.sqlite_version_info < (3, 43):
            raise RuntimeError(f"SQLite >= 3.43 is required (found {sqlite3.sqlite_version})")
        self.path = path
        with closing(self._connect()) as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(SCHEMA)
        with writer_lock(path, wait=False) as locked:
            if locked:  # otherwise another process is indexing right now
                self._cleanup_incomplete()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=60)
        con.execute("PRAGMA cache_size=-200000")  # ~200 MB
        return con

    def _cleanup_incomplete(self):
        """Remove files whose indexing was interrupted (e.g. by a crash).
        Must be called while holding the writer lock."""
        with closing(self._connect()) as con:
            ids = [r[0] for r in con.execute("SELECT id FROM files WHERE done = 0")]
        for file_id in ids:
            self.delete_file(file_id)

    def has_file(self, unique_id: str) -> bool:
        with closing(self._connect()) as con:
            return con.execute(
                "SELECT 1 FROM files WHERE unique_id = ? AND done = 1", (unique_id,)
            ).fetchone() is not None

    def add_file(self, unique_id: str | None, name: str, headers: list[str],
                 rows: Iterable[list[str]],
                 progress: Callable[[int], None] | None = None) -> int:
        """Index rows in batches; returns the number of rows indexed."""
        with writer_lock(self.path):
            self._cleanup_incomplete()
            return self._add_file(unique_id, name, headers, rows, progress)

    def _add_file(self, unique_id, name, headers, rows, progress) -> int:
        with closing(self._connect()) as con:
            old = con.execute("SELECT id FROM files WHERE unique_id = ?", (unique_id,)).fetchone()
        if old:
            self.delete_file(old[0])
        con = self._connect()
        try:
            con.execute("PRAGMA synchronous=OFF")
            with con:
                file_id = con.execute(
                    "INSERT INTO files (unique_id, name, headers, added_at) VALUES (?, ?, ?, ?)",
                    (unique_id, name, SEP.join(headers), int(time.time())),
                ).lastrowid
            next_id = (con.execute("SELECT max(id) FROM rows").fetchone()[0] or 0) + 1
            first_id, count, batch = next_id, 0, []

            def flush():
                with con:
                    con.executemany("INSERT INTO rows (id, data) VALUES (?, ?)",
                                    ((i, SEP.join(r)) for i, r in batch))
                    con.executemany("INSERT INTO rows_fts (rowid, body) VALUES (?, ?)",
                                    ((i, normalize(" ".join(r))) for i, r in batch))
                    con.execute("UPDATE files SET first_id = ?, last_id = ? WHERE id = ?",
                                (first_id, batch[-1][0], file_id))
                batch.clear()
                if progress:
                    progress(count)

            for row in rows:
                batch.append((next_id, row))
                next_id += 1
                count += 1
                if len(batch) >= BATCH:
                    flush()
            if batch:
                flush()
            with con:
                con.execute("UPDATE files SET row_count = ?, done = 1 WHERE id = ?",
                            (count, file_id))
            return count
        finally:
            con.close()

    def unique_ids(self) -> set[str]:
        with closing(self._connect()) as con:
            return {r[0] for r in con.execute(
                "SELECT unique_id FROM files WHERE done = 1 AND unique_id IS NOT NULL")}

    def delete_unique_id(self, unique_id: str) -> bool:
        with closing(self._connect()) as con:
            found = con.execute("SELECT id FROM files WHERE unique_id = ?", (unique_id,)).fetchone()
        return self.delete_file(found[0]) if found else False

    def list_files(self) -> list[tuple]:
        with closing(self._connect()) as con:
            return con.execute(
                "SELECT id, name, row_count FROM files WHERE done = 1 ORDER BY id"
            ).fetchall()

    def delete_file(self, file_id: int) -> bool:
        with closing(self._connect()) as con, con:
            found = con.execute(
                "SELECT first_id, last_id FROM files WHERE id = ?", (file_id,)
            ).fetchone()
            if not found:
                return False
            first, last = found
            if first is not None:
                con.execute("DELETE FROM rows_fts WHERE rowid BETWEEN ? AND ?", (first, last))
                con.execute("DELETE FROM rows WHERE id BETWEEN ? AND ?", (first, last))
            con.execute("DELETE FROM files WHERE id = ?", (file_id,))
            con.execute("DELETE FROM purged WHERE file_id = ?", (file_id,))
            return True

    def add_user(self, user_id: int) -> bool:
        with closing(self._connect()) as con, con:
            return con.execute("INSERT OR IGNORE INTO users VALUES (?, ?)",
                               (user_id, int(time.time()))).rowcount > 0

    def remove_user(self, user_id: int) -> bool:
        with closing(self._connect()) as con, con:
            return con.execute("DELETE FROM users WHERE user_id = ?", (user_id,)).rowcount > 0

    def users(self) -> list[int]:
        with closing(self._connect()) as con:
            return [r[0] for r in con.execute("SELECT user_id FROM users ORDER BY added_at")]

    def log_search(self, user_id: int, name: str, query: str, total: int):
        with closing(self._connect()) as con, con:
            con.execute("INSERT INTO audit (ts, user_id, name, query, total) VALUES (?, ?, ?, ?, ?)",
                        (int(time.time()), user_id, name, query[:200], total))

    def count_searches(self, user_id: int, since: int) -> int:
        with closing(self._connect()) as con:
            return con.execute("SELECT count(*) FROM audit WHERE user_id = ? AND ts >= ?",
                               (user_id, since)).fetchone()[0]

    def audit(self, limit: int = 20, user_id: int | None = None) -> list[tuple]:
        """Newest first: (ts, user_id, name, query, total)."""
        sql = "SELECT ts, user_id, name, query, total FROM audit"
        args: tuple = ()
        if user_id is not None:
            sql, args = sql + " WHERE user_id = ?", (user_id,)
        with closing(self._connect()) as con:
            return con.execute(sql + " ORDER BY id DESC LIMIT ?", args + (limit,)).fetchall()

    def purge_audit(self, days: int):
        if days > 0:
            with closing(self._connect()) as con, con:
                con.execute("DELETE FROM audit WHERE ts < ?", (int(time.time()) - days * 86400,))

    def locate(self, row_id: int):
        """Where an indexed row lives in its source file: (file_id, unique_id,
        position, stored_data). position counts the non-blank data rows of the
        source, excluding rows already removed from it (see mark_purged)."""
        with closing(self._connect()) as con:
            found = con.execute(
                "SELECT f.id, f.unique_id, r.id - f.first_id + 1, r.data FROM rows r"
                " JOIN files f ON r.id BETWEEN f.first_id AND f.last_id"
                " WHERE r.id = ? AND f.done = 1", (row_id,)).fetchone()
            if not found:
                return None
            file_id, uid, pos, data = found
            gone = con.execute("SELECT count(*) FROM purged WHERE file_id = ? AND row_id < ?",
                               (file_id, row_id)).fetchone()[0]
        return file_id, uid, pos - gone, data

    def mark_purged(self, file_id: int, row_id: int, old_prefix: str, new_prefix: str):
        """Record that a row was removed from its source file, and re-key the
        file(s) of that source so the changed size doesn't trigger a re-index."""
        with closing(self._connect()) as con, con:
            con.execute("INSERT OR IGNORE INTO purged VALUES (?, ?)", (file_id, row_id))
            con.execute(
                "UPDATE files SET unique_id = ? || substr(unique_id, ?)"
                " WHERE unique_id = ? OR substr(unique_id, 1, ?) = ? || '|'",
                (new_prefix, len(old_prefix) + 1, old_prefix, len(old_prefix) + 1, old_prefix))

    def optimize(self):
        with closing(self._connect()) as con, con:
            con.execute("INSERT INTO rows_fts (rows_fts) VALUES ('optimize')")

    @staticmethod
    def build_query(query: str) -> str | None:
        """Every word must appear (as a prefix if 3+ chars); "quoted text" means exact phrase."""
        q = query.strip()
        if len(q) > 2 and q[0] in "\"«" and q[-1] in "\"»":
            words = tokens(q[1:-1])
            return '"' + " ".join(words) + '"' if words else None
        terms, pos = [], 0
        for m in CJK.finditer(q):  # a run of Chinese/Japanese characters is matched as a phrase
            terms += [(w, False) for w in tokens(q[pos:m.start()])]
            terms.append((" ".join(tokens(m.group())), True))
            pos = m.end()
        terms += [(w, False) for w in tokens(q[pos:])]
        # Prefix-matching very short words expands to huge term lists; match them exactly.
        return " ".join(f'"{w}"' if phrase or len(w) < 3 else f'"{w}"*'
                        for w, phrase in terms) if terms else None

    def delete_row(self, row_id: int) -> bool:
        """Remove one row from the index (the source file is left untouched)."""
        with closing(self._connect()) as con, con:
            cur = con.execute("DELETE FROM rows WHERE id = ?", (row_id,))
            if not cur.rowcount:
                return False
            con.execute("DELETE FROM rows_fts WHERE rowid = ?", (row_id,))
            con.execute("UPDATE files SET row_count = row_count - 1"
                        " WHERE ? BETWEEN first_id AND last_id", (row_id,))
            return True

    def search(self, query: str, limit: int = 5, offset: int = 0, with_ids: bool = False):
        """Return (total, [(file_name, row_num, {header: value}), ...]).
        With with_ids each tuple gets the row id appended (for delete_row).
        total is capped at COUNT_CAP + 1 to stay fast on huge indexes."""
        match = self.build_query(query)
        if not match:
            return 0, []
        with closing(self._connect()) as con:
            total = con.execute(
                "SELECT count(*) FROM (SELECT 1 FROM rows_fts WHERE rows_fts MATCH ? LIMIT ?)",
                (match, COUNT_CAP + 1),
            ).fetchone()[0]
            found = con.execute(
                "SELECT f.name, f.headers, r.id - f.first_id + 1, r.data, r.id"
                " FROM (SELECT rowid FROM rows_fts WHERE rows_fts MATCH ?"
                "       ORDER BY rowid LIMIT ? OFFSET ?) m"
                " JOIN rows r ON r.id = m.rowid"
                " JOIN files f ON r.id BETWEEN f.first_id AND f.last_id",
                (match, limit, offset),
            ).fetchall()
        results = []
        for name, headers, row_num, data, row_id in found:
            fields = {h: v for h, v in zip(headers.split(SEP), data.split(SEP)) if v}
            results.append((name, row_num, fields, row_id) if with_ids else (name, row_num, fields))
        return total, results
