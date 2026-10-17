"""Decode and parse CSV files of unknown encoding and delimiter."""
import csv
import io

ENCODINGS = ("utf-8-sig", "cp1256")  # cp1256 = Windows Arabic/Persian (old Excel)


def decode(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    for enc in ENCODINGS:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def parse_csv(data: bytes) -> tuple[list[str], list[list[str]]]:
    """Return (headers, rows). Blank rows are skipped."""
    text = decode(data)
    try:
        dialect = csv.Sniffer().sniff(text[:20000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    headers: list[str] | None = None
    rows: list[list[str]] = []
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        if headers is None:
            headers = [h.strip() or f"ستون {i + 1}" for i, h in enumerate(row)]
            continue
        rows.append([cell.strip() for cell in row])
    if headers is None:
        return [], []
    width = max([len(headers)] + [len(r) for r in rows])
    headers += [f"ستون {i + 1}" for i in range(len(headers), width)]
    return headers, rows
