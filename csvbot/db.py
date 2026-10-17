"""SQLite full-text index of CSV rows."""
import json
import sqlite3
import time
from contextlib import closing

from .text import normalize, tokens

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    unique_id TEXT UNIQUE,
    name TEXT NOT NULL,
    headers TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    added_at INTEGER NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS rows_fts USING fts5(
    body,
    file_id UNINDEXED,
    row_num UNINDEXED,
    data UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        with closing(self._connect()) as con:
            con.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def has_file(self, unique_id: str) -> bool:
        with closing(self._connect()) as con:
            return con.execute(
                "SELECT 1 FROM files WHERE unique_id = ?", (unique_id,)
            ).fetchone() is not None

    def add_file(self, unique_id: str | None, name: str,
                 headers: list[str], rows: list[list[str]]) -> int:
        with closing(self._connect()) as con, con:
            cur = con.execute(
                "INSERT INTO files (unique_id, name, headers, row_count, added_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (unique_id, name, json.dumps(headers, ensure_ascii=False),
                 len(rows), int(time.time())),
            )
            file_id = cur.lastrowid
            con.executemany(
                "INSERT INTO rows_fts (body, file_id, row_num, data) VALUES (?, ?, ?, ?)",
                ((normalize(" ".join(row)), file_id, i + 2,
                  json.dumps(row, ensure_ascii=False))
                 for i, row in enumerate(rows)),
            )
            return file_id

    def list_files(self) -> list[tuple]:
        with closing(self._connect()) as con:
            return con.execute(
                "SELECT id, name, row_count FROM files ORDER BY id"
            ).fetchall()

    def delete_file(self, file_id: int) -> bool:
        with closing(self._connect()) as con, con:
            con.execute("DELETE FROM rows_fts WHERE file_id = ?", (file_id,))
            return con.execute(
                "DELETE FROM files WHERE id = ?", (file_id,)
            ).rowcount > 0

    @staticmethod
    def build_query(query: str) -> str | None:
        """Every word must appear (as a prefix); "quoted text" means exact phrase."""
        q = query.strip()
        if len(q) > 2 and q[0] in "\"«" and q[-1] in "\"»":
            words = tokens(q[1:-1])
            return '"' + " ".join(words) + '"' if words else None
        words = tokens(q)
        return " ".join(f'"{w}"*' for w in words) if words else None

    def search(self, query: str, limit: int = 5, offset: int = 0):
        """Return (total, [(file_name, row_num, {header: value}), ...])."""
        match = self.build_query(query)
        if not match:
            return 0, []
        with closing(self._connect()) as con:
            total = con.execute(
                "SELECT count(*) FROM rows_fts WHERE rows_fts MATCH ?", (match,)
            ).fetchone()[0]
            found = con.execute(
                "SELECT f.name, f.headers, r.row_num, r.data FROM rows_fts r"
                " JOIN files f ON f.id = r.file_id"
                " WHERE rows_fts MATCH ? ORDER BY rank LIMIT ? OFFSET ?",
                (match, limit, offset),
            ).fetchall()
        results = []
        for name, headers, row_num, data in found:
            headers, values = json.loads(headers), json.loads(data)
            results.append((name, row_num, {
                h: v for h, v in zip(headers, values) if v
            }))
        return total, results
