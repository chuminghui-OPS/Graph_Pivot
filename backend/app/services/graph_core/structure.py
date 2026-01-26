# Python
# 功能：解析 Markdown 结构，生成目录树
# 作者：AI Architect

import os
import re
from typing import List, Dict, Any


# 将章节标记转换为章节切片列表
def _build_chapters_from_markers(markers: List[Dict[str, Any]], content: str) -> List[Dict[str, Any]]:
    parsed = []
    for i, marker in enumerate(markers):
        start_index = int(marker["start"])
        if i + 1 < len(markers):
            end_index = int(markers[i + 1]["start"])
        else:
            end_index = len(content)
        parsed.append(
            {
                "title": marker["title"],
                "level": marker.get("level", 1),
                "start_char": start_index,
                "end_char": end_index,
            }
        )
    return parsed


# 从正文中识别章节标题（适配“第X章/Chapter X”）
def _find_text_chapter_markers(content: str) -> List[Dict[str, Any]]:
    patterns = [
        re.compile(r"^第[\d一二三四五六七八九十百千]+[章节回](\s+.*)?$"),
        re.compile(r"^(CHAPTER|Chapter)\s+\d+[:.\s-].+"),
        re.compile(r"^(CHAPTER|Chapter)\s+\d+\s*$"),
    ]
    markers: List[Dict[str, Any]] = []
    cursor = 0
    for line in content.splitlines(keepends=True):
        stripped = line.strip()
        # 过滤过长的行，避免误判
        if stripped and len(stripped) <= 60:
            if any(p.match(stripped) for p in patterns):
                markers.append({"start": cursor, "title": stripped, "level": 1})
        cursor += len(line)
    return markers


# 从 PDF 书签读取章节标题与页码
def _extract_pdf_bookmarks(pdf_path: str) -> List[Dict[str, Any]]:
    try:
        import fitz
    except Exception as exc:
        raise RuntimeError("PyMuPDF 未安装，无法解析 PDF 书签") from exc

    doc = fitz.open(pdf_path)
    toc = doc.get_toc() or []
    entries = [item for item in toc if len(item) >= 3 and str(item[1]).strip()]
    if not entries:
        return []

    min_level = min(item[0] for item in entries)
    chapters: List[Dict[str, Any]] = []
    for level, title, page in entries:
        if level != min_level:
            continue
        page_index = max(0, int(page) - 1)
        chapters.append({"title": str(title).strip(), "page": page_index})
    return chapters


# 如果读取失败，就尝试读取前几页，从目录页文本中 正则匹配典型目录格式 识别章节标题与页码
def _extract_toc_from_directory(pdf_path: str, max_pages: int = 6) -> List[Dict[str, Any]]:
    try:
        import fitz
    except Exception as exc:
        raise RuntimeError("PyMuPDF 未安装，无法解析 PDF 目录") from exc

    doc = fitz.open(pdf_path)
    results: List[Dict[str, Any]] = []
    for page_index in range(min(max_pages, doc.page_count)):
        text = doc.load_page(page_index).get_text("text")
        if "目录" not in text and "Contents" not in text and "CONTENTS" not in text:
            continue

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines:
            if "目录" in line or "Contents" in line or "CONTENTS" in line:
                continue
            line = re.sub(r"\s+", " ", line)
            match = re.match(r"^(.+?)\.{2,}\s*(\d{1,4})$", line) or re.match(
                r"^(.+?)\s+(\d{1,4})$", line
            )#^(.+?)\.{2,}\s*(\d{1,4})$例如：第一章 绪论........12     2. ^(.+?)\s+(\d{1,4})$例如：第一章 绪论 12
            if not match:
                continue
            title = match.group(1).strip()
            if len(title) < 2 or len(title) > 40:
                continue
            page_index = max(0, int(match.group(2)) - 1)
            results.append({"title": title, "page": page_index})

        if results:
            break
    return results


# 构建逐页 Markdown 文件，并返回每页起始字符偏移
def _build_page_markdown(pdf_path: str, output_path: str) -> Dict[str, Any]:
    try:
        import fitz
    except Exception as exc:
        raise RuntimeError("PyMuPDF 未安装，无法生成分页文本") from exc

    doc = fitz.open(pdf_path)
    offsets: List[int] = []
    cursor = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for page_index in range(doc.page_count):
            offsets.append(cursor)
            text = doc.load_page(page_index).get_text("text")
            f.write(text)
            cursor += len(text)
            if page_index < doc.page_count - 1:
                f.write("\n\n")
                cursor += 2
    return {"offsets": offsets, "total": cursor, "page_count": doc.page_count}


# 解析 Markdown 结构，输出章节列表与范围
def parse_markdown_structure(md_path: str, pdf_path: str | None = None) -> Dict[str, Any]:
    """
    解析 Markdown 文件，生成目录树（支持懒加载索引）
    返回结构：
    {
        "book_title": "...",
        "chapters": [
            {"title": "...", "level": 1, "start_char": 100, "end_char": 5000, "children": []}
        ]
    }
    """
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    structure = {
        "book_title": "Unknown Book",
        "file_path": md_path, # 保存路径用于后续懒加载
        "total_length": len(content),
        "chapters": []
    }

    # 如果提供 PDF 路径，则优先用书签/目录解析真实章节
    if pdf_path:
        chapters = _extract_pdf_bookmarks(pdf_path)
        if chapters:
            unique_pages = len({item["page"] for item in chapters})
            if unique_pages <= 1:
                chapters = []
        if not chapters:
            chapters = _extract_toc_from_directory(pdf_path)
        if not chapters:
            raise ValueError("未检测到有效的 PDF 书签或目录，请使用包含目录/书签的 PDF。")

        page_md_path = os.path.splitext(md_path)[0] + ".pages.md"
        page_meta = _build_page_markdown(pdf_path, page_md_path)
        offsets = page_meta["offsets"]
        total_len = page_meta["total"]
        page_count = page_meta["page_count"]

        # 按页码排序并生成章节范围
        chapters = sorted(chapters, key=lambda item: item["page"])
        parsed_chapters: List[Dict[str, Any]] = []
        for idx, chapter in enumerate(chapters):
            title = str(chapter["title"]).strip()
            if not title:
                continue
            start_page = min(max(int(chapter["page"]), 0), page_count - 1)
            next_page = (
                min(max(int(chapters[idx + 1]["page"]), 0), page_count)
                if idx + 1 < len(chapters)
                else page_count
            )
            end_page = max(start_page, next_page - 1)
            start_char = offsets[start_page]
            end_char = offsets[end_page + 1] if end_page + 1 < len(offsets) else total_len
            parsed_chapters.append(
                {
                    "title": title,
                    "level": 1,
                    "start_char": start_char,
                    "end_char": end_char,
                }
            )

        if not parsed_chapters:
            raise ValueError("目录解析失败，请确认 PDF 书签/目录是否规范。")

        structure["file_path"] = page_md_path
        structure["chapters"] = parsed_chapters
        return structure

    # 优先识别 Markdown 标题（#~####）
    header_pattern = re.compile(r'^\s*(#{1,4})\s+(.+)$', re.MULTILINE)
    matches = list(header_pattern.finditer(content))

    if not matches:
        # 如果没有 Markdown 标题，则尝试识别文本章节标题
        text_markers = _find_text_chapter_markers(content)
        if text_markers:
            structure["chapters"] = _build_chapters_from_markers(text_markers, content)
            return structure
        # 无章节则返回空，交由上层处理
        structure["chapters"] = []
        return structure

    # 尝试将第一个 H1 视为书名，并避免重复作为章节
    start_idx = 0
    if matches[0].group(1) == "#":
        structure["book_title"] = matches[0].group(2).strip()
        if len(matches) > 1:
            start_idx = 1

    parsed_chapters = []
    for i, match in enumerate(matches[start_idx:], start=start_idx):
        level = len(match.group(1)) # 1 or 2 or 3
        title = match.group(2).strip()
        start_index = match.start()

        # 结束索引是下一个标题的开始，或者是文件末尾
        if i + 1 < len(matches):
            end_index = matches[i+1].start()
        else:
            end_index = len(content)

        parsed_chapters.append({
            "title": title,
            "level": level,
            "start_char": start_index,
            "end_char": end_index
        })

    structure["chapters"] = parsed_chapters
    return structure


# 按字符范围读取章节内容
def lazy_load_chapter(md_path: str, start: int, end: int) -> str:
    """
    懒加载：根据字符索引读取特定章节内容
    """
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return content[start:end]
