from __future__ import annotations

import os
from uuid import uuid4

from app.core.config import settings


# 确保书籍目录存在并返回路径
def ensure_book_dir(book_id: str) -> str:
    base_dir = os.path.join(settings.data_dir, "books", book_id)
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


# 生成书籍唯一 ID
def new_book_id() -> str:
    return f"b_{uuid4().hex}"


# 生成章节 ID
def new_chapter_id(index: int) -> str:
    return f"c{index:02d}"


# 生成 chunk ID（含章节与序号）
def new_chunk_id(chapter_id: str, index: int) -> str:
    return f"{chapter_id}_k{index:03d}_{uuid4().hex[:6]}"
