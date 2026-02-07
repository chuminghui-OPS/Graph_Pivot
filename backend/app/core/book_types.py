from __future__ import annotations

from typing import Dict, Tuple


# 9 大类书籍（可按需调整）
# key: 用于 API 的稳定标识
# code: 书籍类型码字母（B、C、D...）
# label: 中文展示名
BOOK_CATEGORIES: Dict[str, Dict[str, str]] = {
    "literature": {"code": "B", "label": "文学"},
    "technology": {"code": "C", "label": "科技"},
    "history": {"code": "D", "label": "历史"},
    "philosophy": {"code": "E", "label": "哲学"},
    "economics": {"code": "F", "label": "经济"},
    "art": {"code": "G", "label": "艺术"},
    "education": {"code": "H", "label": "教育"},
    "biography": {"code": "I", "label": "传记"},
    "other": {"code": "J", "label": "其他"},
}


def normalize_book_type(value: str | None) -> str:
    if not value:
        return "other"
    candidate = value.strip().lower()
    if candidate in BOOK_CATEGORIES:
        return candidate
    # 允许传中文 label
    for key, meta in BOOK_CATEGORIES.items():
        if meta["label"] == value.strip():
            return key
    # 允许传类型码字母
    for key, meta in BOOK_CATEGORIES.items():
        if meta["code"].lower() == candidate:
            return key
    return "other"


def get_type_code(book_type: str) -> str:
    return BOOK_CATEGORIES.get(book_type, BOOK_CATEGORIES["other"])["code"]


def list_book_types() -> Tuple[dict[str, str], ...]:
    return tuple({"key": key, **meta} for key, meta in BOOK_CATEGORIES.items())
