"""Normalization of Persian/Arabic text so that searches match regardless of
keyboard layout (ي/ی, ك/ک), digits (۱۲۳/123) or diacritics."""
import re

_MAP = {
    "ي": "ی", "ى": "ی", "ئ": "ی",
    "ك": "ک",
    "ة": "ه", "ۀ": "ه",
    "أ": "ا", "إ": "ا", "آ": "ا",
    "‌": " ",  # zero-width non-joiner (نیم‌فاصله)
    "‏": "", "‎": "", "﻿": "",
}
for i in range(10):
    _MAP[chr(0x06F0 + i)] = str(i)  # Persian digits
    _MAP[chr(0x0660 + i)] = str(i)  # Arabic digits
_TABLE = str.maketrans(_MAP)
_DIACRITICS = re.compile(r"[ً-ٰٟـ]")  # harakat + tatweel
_TOKEN = re.compile(r"\w+")


def normalize(text: str) -> str:
    text = _DIACRITICS.sub("", str(text).translate(_TABLE))
    return text.lower()


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(normalize(text))
