# Python
# 功能：验证 PDF 解析、结构提取与 LLM 提取逻辑
# 作者：AI Architect
import os
import asyncio
import json
from app.services.graph_core.converter import convert_pdf_to_markdown
from app.services.graph_core.structure import parse_markdown_structure, lazy_load_chapter
from app.services.graph_core.extractor import extract_graph_from_text

# ================= 配置区 =================
TEST_PDF_PATH = "ecomic.pdf"  # 请确保根目录有一个 test.pdf
TEMP_DIR = "temp_test"
API_KEY = os.getenv("LLM_API_KEY", "")  # set via env
BASE_URL = os.getenv("LLM_BASE_URL", "")  # optional proxy base url
# ==========================================

async def run_validation():
    print("--- 🛰️ 开始功能验证 ---")
    
    # 1. 创建临时目录
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    # 2. 验证 PDF 转 Markdown
    print("\n[Step 1] 正在转换 PDF 为 Markdown...")
    if not os.path.exists(TEST_PDF_PATH):
        print(f"❌ 错误：找不到测试文件 {TEST_PDF_PATH}，请先放置一个 PDF 文件。")
        return
    
    md_path = convert_pdf_to_markdown(TEST_PDF_PATH, TEMP_DIR)
    print(f"✅ 转换成功: {md_path}")

    # 3. 验证结构解析
    print("\n[Step 2] 正在解析书籍结构树...")
    structure = parse_markdown_structure(md_path)
    print(f"✅ 书名: {structure.get('book_title')}")
    print(f"✅ 检测到章节数: {len(structure.get('chapters', []))}")
    
    if structure['chapters']:
        first_chapter = structure['chapters'][0]
        print(f"   -> 第一章示例: {first_chapter['title']} (字符范围: {first_chapter['start_char']}-{first_chapter['end_char']})")

    # 4. 验证懒加载切片
    print("\n[Step 3] 验证切片懒加载...")
    if structure['chapters']:
        sample_text = lazy_load_chapter(md_path, first_chapter['start_char'], first_chapter['end_char'])
        print(f"✅ 成功读取内容快照 (前50字): {sample_text[:50]}...")

    # 5. 验证 LLM 提取 (核心环节)
    print("\n[Step 4] 联调 LLM 提取实体关系 (使用第一章内容)...")
    
    # 截取前 2000 字进行快速测试，节省 Token
    test_text = sample_text[:30000]
    if not API_KEY:
        print("❌ 请先设置环境变量 LLM_API_KEY")
        return

    result = await extract_graph_from_text(test_text, API_KEY, BASE_URL or None)
        
    if "error" in result:
        print(f"❌ LLM 报错: {result['error']}")
        print(f"📝 详情: {result.get('details')}")
    else:
        print("✅ LLM 提取成功！")
        print(f"📊 提取到实体数: {len(result.get('entities', []))}")
        print(f"📊 提取到关系数: {len(result.get('relationships', []))}")
        print("\n--- 预览 JSON 数据 ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\n--- ✨ 验证任务完成 ---")

if __name__ == "__main__":
    asyncio.run(run_validation())
