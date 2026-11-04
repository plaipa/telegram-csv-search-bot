"""Keep the search index in sync with the CSV and SQLite files in a folder.

Each CSV file, and each table of each SQLite database, is indexed as one
"file". Its unique id contains the path, size and mtime, so a changed file
is re-indexed and a deleted one is removed from the index.
"""
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Callable, Iterator

from .db import Database
from .loader import read_csv

log = logging.getLogger("csvbot.sources")

CSV_EXT = (".csv", ".tsv")
DB_EXT = (".db", ".sqlite", ".sqlite3")
PREFIX = "local:"
# Files modified more recently than this may still be copying; index them later.
SETTLE_SECONDS = 30

_warned: set[str] = set()

Loader = Callable[[], tuple[list[str], Iterator[list[str]]]]


def is_sqlite(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def _open_readonly(path: str) -> sqlite3.Connection:
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def sqlite_tables(path: str) -> list[str]:
    """Ordinary tables, excluding virtual tables (e.g. FTS) and their shadow tables."""
    con = _open_readonly(path)
    try:
        rows = con.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    finally:
        con.close()
    virtual = [name for name, sql in rows if (sql or "").upper().startswith("CREATE VIRTUAL TABLE")]
    return [name for name, _ in rows
            if name not in virtual and not any(name.startswith(v + "_") for v in virtual)]


def _cell(value) -> str:
    if value is None or isinstance(value, (bytes, memoryview)):
        return ""
    return str(value).strip()


def sqlite_rows(path: str, table: str) -> tuple[list[str], Iterator[list[str]]]:
    con = _open_readonly(path)
    cur = con.execute('SELECT * FROM "{}"'.format(table.replace('"', '""')))
    headers = [d[0] for d in cur.description]

    def rows():
        try:
            for row in cur:
                cells = [_cell(v) for v in row]
                if any(cells):
                    yield cells
        finally:
            con.close()

    return headers, rows()


def scan(data_dir: str, skip: set[str] = frozenset()) -> tuple[dict[str, tuple[str, Loader]], int]:
    """Return ({unique_id: (display name, loader)}, number of files still settling)."""
    found: dict[str, tuple[str, Loader]] = {}
    pending = 0
    now = time.time()
    for root, dirs, files in os.walk(data_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if name.startswith(".") or ext not in CSV_EXT + DB_EXT:
                continue
            if os.path.realpath(path) in skip:
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            if now - st.st_mtime < SETTLE_SECONDS:
                pending += 1
                continue
            rel = os.path.relpath(path, data_dir).replace(os.sep, "/")
            key = f"{PREFIX}{rel}|{st.st_size}|{int(st.st_mtime)}"
            if ext in CSV_EXT:
                found[key] = (rel, lambda p=path: read_csv(p))
            elif is_sqlite(path):
                try:
                    tables = sqlite_tables(path)
                except sqlite3.Error as e:
                    log.warning("Cannot read %s: %s", rel, e)
                    continue
                for table in tables:
                    found[f"{key}|{table}"] = (f"{rel} › {table}",
                                               lambda p=path, t=table: sqlite_rows(p, t))
            elif key not in _warned:
                _warned.add(key)
                log.warning("Skipping %s: not a SQLite database", rel)
    return found, pending


class FolderIndex:
    def __init__(self, db: Database, data_dir: str):
        self.db = db
        self.data_dir = data_dir
        # Never index the search index itself if it lives inside data_dir.
        self.skip = {os.path.realpath(db.path + suffix) for suffix in ("", "-wal", "-shm", "-journal")}
        self.failed: set[str] = set()  # don't retry a broken file until it changes

    def sync(self, on_indexed: Callable[[str, int], None] | None = None,
             progress: Callable[[str, int], None] | None = None) -> dict:
        os.makedirs(self.data_dir, exist_ok=True)
        found, pending = scan(self.data_dir, self.skip)
        existing = {u for u in self.db.unique_ids() if u.startswith(PREFIX)}
        removed = 0
        for uid in existing - found.keys():
            self.db.delete_unique_id(uid)
            removed += 1
        added = errors = 0
        for uid in sorted(found.keys() - existing - self.failed):
            name, loader = found[uid]
            try:
                headers, rows = loader()
                count = self.db.add_file(uid, name, headers, rows,
                                         (lambda n, name=name: progress(name, n)) if progress else None)
            except Exception:
                log.exception("Failed to index %s", name)
                self.failed.add(uid)
                errors += 1
                continue
            log.info("Indexed %s (%d rows)", name, count)
            added += 1
            if on_indexed:
                on_indexed(name, count)
        return {"added": added, "removed": removed, "pending": pending, "errors": errors}
