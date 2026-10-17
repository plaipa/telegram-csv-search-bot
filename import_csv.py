"""Index local CSV files directly, without Telegram.

Usage: python import_csv.py file1.csv [file2.csv ...]
"""
import os
import sys

from dotenv import load_dotenv

from csvbot.db import Database
from csvbot.loader import read_csv

load_dotenv()

if len(sys.argv) < 2:
    sys.exit(__doc__)
db = Database(os.getenv("DB_PATH", "data.db"))
for path in sys.argv[1:]:
    headers, rows = read_csv(path)
    if not headers:
        print(f"skip (empty): {path}")
        continue
    name = os.path.basename(path)
    count = db.add_file(f"local:{os.path.abspath(path)}", name, headers, rows,
                        progress=lambda n: print(f"\r{name}: {n:,} rows", end="", flush=True))
    print(f"\r{name}: {count:,} rows indexed")
db.optimize()
