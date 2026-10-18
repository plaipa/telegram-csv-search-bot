"""Stream rows out of CSV files of unknown encoding and delimiter without
loading the whole file into memory (files can be several GB)."""
import codecs
import csv
from typing import Iterator

from charset_normalizer import from_bytes

SAMPLE_SIZE = 1 << 20  # 1 MB
csv.field_size_limit(1 << 24)


# Legacy code pages we accept from charset detection: Persian/Arabic, Cyrillic, Chinese.
_LEGACY = {"cp1256": "cp1256", "cp1251": "cp1251", "gb18030": "gb18030", "gbk": "gb18030",
           "gb2312": "gb18030", "big5": "big5", "big5hkscs": "big5"}


def detect_encoding(sample: bytes) -> str:
    if sample[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    try:
        # A multi-byte character may be cut at the end of the sample.
        codecs.getincrementaldecoder("utf-8-sig")().decode(sample, final=False)
        return "utf-8-sig"
    except UnicodeDecodeError:
        pass
    best = from_bytes(sample[:-4] if len(sample) > 4096 else sample).best()  # a cut-off tail skews detection
    if best and best.encoding.lower().replace("-", "_") in _LEGACY:
        return _LEGACY[best.encoding.lower().replace("-", "_")]
    return "cp1256"  # Windows Arabic/Persian (old Excel exports)


def detect_dialect(text: str):
    try:
        return csv.Sniffer().sniff(text, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def csv_format(path: str):
    """Return (encoding, dialect) detected from the start of the file."""
    with open(path, "rb") as f:
        sample = f.read(SAMPLE_SIZE)
    encoding = detect_encoding(sample)
    text_sample = sample.decode(encoding, errors="ignore")
    # Sniff on whole lines only
    return encoding, detect_dialect(text_sample[: text_sample.rfind("\n") + 1] or text_sample)


def read_csv(path: str) -> tuple[list[str], Iterator[list[str]]]:
    """Return (headers, row iterator). Blank rows are skipped; short rows are
    kept as-is and long rows get extra "ستون N" headers only if seen first."""
    encoding, dialect = csv_format(path)
    f = open(path, encoding=encoding, errors="replace", newline="")
    reader = csv.reader(f, dialect)
    headers: list[str] = []
    for row in reader:
        if any(cell.strip() for cell in row):
            headers = [h.strip() or f"ستون {i + 1}" for i, h in enumerate(row)]
            break

    def rows():
        with f:
            for row in reader:
                if any(cell.strip() for cell in row):
                    yield [cell.strip() for cell in row]

    if not headers:
        f.close()
        return [], iter(())
    return headers, rows()
