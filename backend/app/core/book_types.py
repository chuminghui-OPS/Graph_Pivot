from __future__ import annotations

from typing import Dict, Tuple


# 10 大类书籍（与 prompt.txt 保持一致）
# key: 用于 API 的稳定标识（对应 prompt id）
# code: 书籍类型码字母（B、C、D...）
# label: 中文展示名
BOOK_CATEGORIES: Dict[str, Dict[str, str]] = {
    "textbook": {"code": "B", "label": "专业教材/大学教科书"},
    "handbook": {"code": "C", "label": "专业工具书/行业手册"},
    "humanities": {"code": "D", "label": "人文社科研究著作"},
    "exam": {"code": "E", "label": "职业考试备考"},
    "popular_science": {"code": "F", "label": "科普类书籍"},
    "business": {"code": "G", "label": "商业/管理/职场"},
    "history_geo": {"code": "H", "label": "历史/地理叙述类"},
    "literature": {"code": "I", "label": "纯文学"},
    "lifestyle": {"code": "J", "label": "生活/休闲"},
    "general": {"code": "K", "label": "通用规则"},
}

# 兼容旧类型 key
LEGACY_TYPE_MAP: Dict[str, str] = {
    "technology": "textbook",
    "history": "history_geo",
    "philosophy": "humanities",
    "economics": "business",
    "art": "literature",
    "education": "textbook",
    "biography": "humanities",
    "other": "general",
}


def normalize_book_type(value: str | None) -> str:
    if not value:
        return "general"
    candidate = value.strip().lower()
    if candidate in BOOK_CATEGORIES:
        return candidate
    if candidate in LEGACY_TYPE_MAP:
        return LEGACY_TYPE_MAP[candidate]
    # 允许传中文 label
    for key, meta in BOOK_CATEGORIES.items():
        if meta["label"] == value.strip():
            return key
    # 允许传类型码字母
    for key, meta in BOOK_CATEGORIES.items():
        if meta["code"].lower() == candidate:
            return key
    return "general"


def get_type_code(book_type: str) -> str:
    return BOOK_CATEGORIES.get(book_type, BOOK_CATEGORIES["other"])["code"]


def list_book_types() -> Tuple[dict[str, str], ...]:
    return tuple({"key": key, **meta} for key, meta in BOOK_CATEGORIES.items())
