import logging
import os

import pymupdf4llm

logger = logging.getLogger(__name__)


def convert_pdf_to_markdown(pdf_path: str, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    md_text = pymupdf4llm.to_markdown(pdf_path)
    base_name = os.path.basename(pdf_path).replace(".pdf", "")
    output_path = os.path.join(output_dir, f"{base_name}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_text)
    logger.info("PDF converted to Markdown: %s", output_path)
    return output_path
