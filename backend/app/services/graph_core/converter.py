# Python
# 功能：PDF转Markdown核心工具
# 作者：AI Architect

import pymupdf4llm
import os
import logging

logger = logging.getLogger(__name__)

# 将 PDF 转换为 Markdown 文件并保存到指定目录
def convert_pdf_to_markdown(pdf_path: str, output_dir: str) -> str:
    """
    将PDF转换为Markdown文件并保存
    :param pdf_path: PDF源文件路径
    :param output_dir: markdown输出目录
    :return: 生成的Markdown文件绝对路径
    """
    try:
        # 1) 提取 Markdown 内容 (包含表格和图片占位符)
        md_text = pymupdf4llm.to_markdown(pdf_path)
        
        # 2) 构建输出路径
        base_name = os.path.basename(pdf_path).replace(".pdf", "")
        output_path = os.path.join(output_dir, f"{base_name}.md")
        
        # 3) 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_text)
            
        logger.info(f"PDF converted to Markdown: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"PDF conversion failed: {str(e)}")
        raise e
