"""Index local CSV files directly (useful for files larger than 20 MB).

Usage: python import_csv.py file1.csv [file2.csv ...]
"""
import os
import sys

from dotenv import load_dotenv

from csvbot.db import Database
from csvbot.loader import parse_csv

load_dotenv()

if len(sys.argv) < 2:
    sys.exit(__doc__)
db = Database(os.getenv("DB_PATH", "data.db"))
for path in sys.argv[1:]:
    with open(path, "rb") as f:
        headers, rows = parse_csv(f.read())
    if not headers:
        print(f"skip (empty): {path}")
        continue
    db.add_file(None, os.path.basename(path), headers, rows)
    print(f"indexed {path}: {len(rows)} rows")
