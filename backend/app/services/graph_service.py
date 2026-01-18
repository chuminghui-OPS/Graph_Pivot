# Python
# 功能：服务层整合
# 操作指令：此文件用于路由层直接调用

from app.services.graph_core.converter import convert_pdf_to_markdown
from app.services.graph_core.structure import parse_markdown_structure, lazy_load_chapter
from app.services.graph_core.extractor import extract_graph_from_text
import os

# 1. 处理上传并生成目录
def process_uploaded_pdf_to_structure(pdf_path: str, temp_dir: str):
    # 转换
    md_path = convert_pdf_to_markdown(pdf_path, temp_dir)
    # 解析结构
    structure = parse_markdown_structure(md_path)
    # 这里建议将 structure 存入数据库或缓存 (Redis)，key为 task_id
    # structure['md_path'] = md_path # 确保保留路径以便后续读取
    return structure

# 2. 懒加载并分析章节
async def analyze_chapter(md_path: str, start: int, end: int, api_key: str):
    # 懒加载读取
    text_content = lazy_load_chapter(md_path, start, end)
    
    # AI 分析
    graph_data = await extract_graph_from_text(text_content, api_key)
    
    return graph_data