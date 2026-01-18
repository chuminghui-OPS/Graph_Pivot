# Python
# 功能：LLM 图谱提取逻辑 (适配 LangChain v0.2+ 与 Pydantic v2)
# 作者：AI Architect

import tiktoken
import json
from typing import Dict, Any, List, Optional

# 核心修正：使用 langchain_core 替代 langchain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI 
from pydantic import BaseModel, Field

# 1. 定义输出的数据结构
# 确保使用 Pydantic v2 语法
class Entity(BaseModel):
    name: str = Field(..., description="实体的名称")
    type: str = Field(..., description="实体类型，例如：Person, Location, Technology, Concept, Organization")
    description: str = Field(..., description="关于该实体在文本中的简短描述")

class Relationship(BaseModel):
    source: str = Field(..., description="源实体名称")
    target: str = Field(..., description="目标实体名称")
    relation: str = Field(..., description="关系描述，例如：author_of, located_in, uses")
    description: str = Field(..., description="关系的上下文证明")

class GraphOutput(BaseModel):
    entities: List[Entity] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    summary: str = Field(..., description="本章节的简短摘要")

# 2. Token 检查器
def check_token_safety(text: str, model: str = "qwen-plus", limit: int = 30000) -> bool:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    
    num_tokens = len(encoding.encode(text))
    return num_tokens <= limit

# 3. 核心提取函数
async def extract_graph_from_text(text: str, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
    # 安全检查
    if not check_token_safety(text):
        return {
            "error": "Token limit exceeded",
            "message": f"当前章节长度超过限制，请缩减范围。"
        }

    # 初始化 LLM (确保 api_key 正确传入)
    llm = ChatOpenAI(
        model="qwen-plus", 
        temperature=0.1,
        api_key=api_key,
        base_url=base_url # 如果使用代理请配置此项
    )

    # 设计 Prompt
    system_prompt = """
    你是一位专业的科研图谱分析专家。
    请根据文本内容提取关键实体及其关系。
    如果是技术文档，请专注于概念依赖；如果是人物传记，请专注于人物关系。
    输出必须是合法的 JSON 格式。
    """

    parser = JsonOutputParser(pydantic_object=GraphOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "请分析以下文本并提取图谱：\n\n{text}\n\n{format_instructions}")
    ])

    # 声明链式调用
    chain = prompt | llm | parser

    try:
        # 执行异步调用
        result = await chain.ainvoke({
            "text": text,
            "format_instructions": parser.get_format_instructions()
        })
        return result
    except Exception as e:
        # 详尽的错误捕获
        return {
            "error": "LLM_ERROR",
            "details": str(e)
        }