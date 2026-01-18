# Python
# 功能：解析Markdown结构，生成目录树
# 作者：AI Architect

import re
from typing import List, Dict, Any

def parse_markdown_structure(md_path: str) -> Dict[str, Any]:
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

    # 简单的正则匹配 # 和 ## (根据实际md风格调整，pymupdf4llm通常生成标准的ATX headers)
    # 匹配行首的 # 标题
    header_pattern = re.compile(r'^(#{1,2})\s+(.+)$', re.MULTILINE)
    
    matches = list(header_pattern.finditer(content))
    
    structure = {
        "book_title": "Unknown Book",
        "file_path": md_path, # 保存路径用于后续懒加载
        "total_length": len(content),
        "chapters": []
    }

    if not matches:
        # 如果没有检测到标题，将全文作为一个章节
        structure["chapters"].append({
            "title": "Full Content",
            "level": 1,
            "start_char": 0,
            "end_char": len(content)
        })
        return structure

    # 尝试将第一个 H1 视为书名
    if matches[0].group(1) == "#":
        structure["book_title"] = matches[0].group(2).strip()

    # 构建层级树
    # 这里的逻辑是将平铺的 matches 转换为嵌套结构，或者为了简单起见，
    # 我们先生成扁平列表，前端负责渲染缩进，后端负责切片。
    # 为了懒加载方便，我们计算每个章节的 start 和 end
    
    parsed_chapters = []
    
    for i, match in enumerate(matches):
        level = len(match.group(1)) # 1 or 2
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

def lazy_load_chapter(md_path: str, start: int, end: int) -> str:
    """
    懒加载：根据字符索引读取特定章节内容
    """
    with open(md_path, 'r', encoding='utf-8') as f:
        f.seek(start)
        # 读取指定长度
        length = end - start
        return f.read(length)