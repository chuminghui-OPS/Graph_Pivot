from __future__ import annotations

from typing import Any, Dict

from app.services.graph_core.structure import parse_markdown_structure, lazy_load_chapter


# 解析 Markdown 并返回结构化目录
def parse_structure(md_path: str, pdf_path: str | None = None) -> Dict[str, Any]:
    return parse_markdown_structure(md_path, pdf_path)


# 根据字符范围加载章节内容
def load_chapter_text(md_path: str, start: int, end: int) -> str:
    return lazy_load_chapter(md_path, start, end)
