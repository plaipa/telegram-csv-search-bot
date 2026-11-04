"""Normalization of Persian/Arabic/Hindi/Chinese text so that searches match regardless of
keyboard layout (ي/ی, ك/ک), digits (۱۲۳/१२३/123) or diacritics."""
import re

_MAP = {
    "ي": "ی", "ى": "ی", "ئ": "ی",
    "ك": "ک",
    "ة": "ه", "ۀ": "ه",
    "أ": "ا", "إ": "ا", "آ": "ا",
    "‌": " ",  # zero-width non-joiner (Persian half-space)
    "‏": "", "‎": "", "﻿": "",
}
for i in range(10):
    _MAP[chr(0x06F0 + i)] = str(i)  # Persian digits
    _MAP[chr(0x0660 + i)] = str(i)  # Arabic digits
    _MAP[chr(0x0966 + i)] = str(i)  # Devanagari digits (Hindi)
# Hindi: drop the nukta (फ़ == फ) and fold the precomposed nukta letters U+0958-095F.
_MAP["\u093c"] = ""
_MAP.update(zip("\u0958\u0959\u095a\u095b\u095c\u095d\u095e\u095f", "कखगजडढफय"))
_TABLE = str.maketrans(_MAP)
_DIACRITICS = re.compile(r"[ً-ٰٟـ]")  # harakat + tatweel
_TOKEN = re.compile(r"\w+")
# Chinese/Japanese have no spaces between words, so every character is its own
# token; a query run of such characters becomes a phrase (see Database.build_query).
CJK = re.compile("[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")


def normalize(text: str) -> str:
    text = _DIACRITICS.sub("", str(text).translate(_TABLE))
    return CJK.sub(lambda m: " " + " ".join(m.group()) + " ", text).lower()


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(normalize(text))
