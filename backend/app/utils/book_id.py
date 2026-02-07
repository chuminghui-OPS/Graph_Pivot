from __future__ import annotations

import random
from datetime import datetime

from app.core.book_types import get_type_code


def _word_count_bucket(word_count: int) -> str:
    if word_count <= 10_000:
        return "1"
    if word_count <= 100_000:
        return "2"
    if word_count <= 500_000:
        return "3"
    if word_count <= 1_000_000:
        return "4"
    if word_count <= 5_000_000:
        return "5"
    return "6"


def _time_code(now: datetime) -> str:
    # YYMMDDHH -> 十进制 -> 16 进制（6 位）
    stamp = f"{now.year % 100:02d}{now.month:02d}{now.day:02d}{now.hour:02d}"
    value = int(stamp)
    hex_value = hex(value)[2:].upper()
    return hex_value[-6:].rjust(6, "0")


def _checksum_numeric(base: str) -> str:
    total = sum(ord(ch) for ch in base)
    return str(total % 10)


def _checksum_alpha(base: str) -> str:
    total = sum(ord(ch) for ch in base)
    return chr(ord("A") + (total % 26))


def generate_book_id(book_type: str, word_count: int, now: datetime | None = None) -> str:
    current = now or datetime.utcnow()
    type_code = f"{get_type_code(book_type)}{_word_count_bucket(word_count)}"
    time_code = _time_code(current)
    rand_code = f"{random.randint(0, 999):03d}"
    base = f"{type_code}{time_code}{rand_code}"
    num_check = _checksum_numeric(base)
    alpha_check = _checksum_alpha(base)
    return f"{type_code}-{time_code}-{rand_code}-{num_check}-{alpha_check}"
