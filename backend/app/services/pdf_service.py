from __future__ import annotations

import os
from app.services.graph_core.converter import convert_pdf_to_markdown


# 将 PDF 转为 Markdown 文件
def pdf_to_markdown(pdf_path: str, output_dir: str) -> str:
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    return convert_pdf_to_markdown(pdf_path, output_dir)
