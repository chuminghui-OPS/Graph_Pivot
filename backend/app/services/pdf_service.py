from __future__ import annotations

import os
from app.services.graph_core.converter import convert_pdf_to_markdown
from app.services.chunk_service import count_text_units
import pymupdf4llm


# 将 PDF 转为 Markdown 文件
def pdf_to_markdown(pdf_path: str, output_dir: str) -> str:
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    return convert_pdf_to_markdown(pdf_path, output_dir)


# 估算 PDF 字数（用于 book_id 生成）
def estimate_pdf_units(pdf_path: str) -> int:
    try:
        text = pymupdf4llm.to_markdown(pdf_path)
        return count_text_units(text)
    except Exception:
        return 0
