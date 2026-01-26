from __future__ import annotations

import math
import re
from typing import List, Dict


# 统计文本字数：中文按字符数，英文按单词数
def count_text_units(text: str) -> int:
    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text))
    return chinese_count + english_words


# 将文本平均切分为指定数量的 chunk
def split_evenly(text: str, chunk_count: int) -> List[Dict[str, int | str]]:
    chunks: List[Dict[str, int | str]] = []
    if chunk_count <= 0:
        return chunks
    length = len(text)
    if length == 0:
        return chunks

    size = max(1, math.ceil(length / chunk_count))
    for idx in range(chunk_count):
        start = idx * size
        if start >= length:
            break
        end = min(length, start + size)
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({"start": start, "end": end, "text": chunk_text})
    return chunks


# 将文本按固定长度切分为块，并保留重叠窗口
def split_text(text: str, chunk_size: int, overlap: int) -> List[Dict[str, int | str]]:
    chunks: List[Dict[str, int | str]] = []
    if chunk_size <= 0:
        return chunks

    start = 0
    length = len(text)

    while start < length:
        # 计算当前块的切片范围
        end = min(length, start + chunk_size)
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                {
                    "start": start,
                    "end": end,
                    "text": chunk_text,
                }
            )
        # 处理重叠窗口，避免信息断裂
        if end >= length:
            break
        start = max(0, end - overlap)

    return chunks
