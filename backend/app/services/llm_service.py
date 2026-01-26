from __future__ import annotations

import json
import re
from typing import Any, Dict

import httpx
from jsonschema import validate, ValidationError

from app.core.config import settings
from app.core.json_schema import LLM_OUTPUT_SCHEMA


# 生成 LLM 提示词（控制输出结构与重要性）
def _build_prompt(text: str) -> str:
    return (
        "你是资深知识图谱抽取专家。\n"
        "目标：只抽取真正关键、可复用的实体与关系，过滤噪声和无关细节。\n"
        "规则：\n"
        "1) 实体必须是“概念/人物/组织/地点/技术/事件”等核心名词，避免长句或碎片。\n"
        "2) 实体需去重，名称尽量短；只保留能代表章节主题的实体。\n"
        "3) 关系必须有明确证据句（来自原文），不要凭空推断。\n"
        "4) 实体和关系按重要性排序，最多实体 10 个、关系 12 条。\n"
        "5) 返回严格 JSON，只能包含 keys: entities, relations；不要代码块、不要解释。\n"
        "6) count 表示实体在文本中出现的次数（可用粗略计数，最少为 1）。\n"
        "输出格式（必须严格一致）：\n"
        "{\n"
        "  \"entities\": [\n"
        "    {\"name\": \"实体名\", \"type\": \"类型\", \"count\": 3}\n"
        "  ],\n"
        "  \"relations\": [\n"
        "    {\"source\": \"实体A\", \"target\": \"实体B\", \"relation\": \"关系\", \"evidence\": \"原文短句\"}\n"
        "  ]\n"
        "}\n"
        "禁止输出额外字段。\n\n"
        f"文本：\n{text}\n"
    )


# 当没有配置 LLM_KEY 时返回最小可运行结果
def _stub_result(text: str) -> Dict[str, Any]:
    seed = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", text)
    if not seed:
        return {"entities": [], "relations": []}
    name = seed[0][:40]
    return {
        "entities": [{"name": name, "type": "Concept", "count": 1}],
        "relations": [],
    }

def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text

# 获取当前 LLM 提供方信息（供前端展示）
def get_llm_info(provider_override: str | None = None) -> Dict[str, str]:
    provider = (provider_override or settings.llm_provider).lower()
    if provider == "gemini":
        return {"provider": "Gemini", "model": settings.gemini_model}
    return {"provider": "通义千问", "model": settings.llm_model}

# 调用 Gemini API
def _call_gemini(text: str) -> Dict[str, Any]:
    if not settings.gemini_api_key:
        return _stub_result(text)

    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=_build_prompt(text),
    )
    content = response.text or ""
    return json.loads(_strip_json_fence(content))

# 估算文本 token 数量（优先使用 tiktoken）
def estimate_tokens(text: str) -> int:
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # 兜底：中文场景下约等于字符数
        return len(text)


# 调用 LLM 服务并解析为 JSON
def _call_llm(text: str, provider_override: str | None = None) -> Dict[str, Any]:
    provider = (provider_override or settings.llm_provider).lower()
    if provider == "gemini":
        return _call_gemini(text)
    if not settings.llm_api_key:
        return _stub_result(text)

    # 组装 OpenAI 兼容请求
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    payload = {
        "model": settings.llm_model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": _build_prompt(text)},
        ],
        "response_format": {"type": "json_object"},
    }

    # 发起同步 HTTP 请求
    with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(_strip_json_fence(content))


# 抽取并进行 JSON Schema 校验，失败自动重试
def extract_with_validation(
    text: str, max_retries: int = 2, provider_override: str | None = None
) -> Dict[str, Any]:
    last_error: str | None = None
    for _ in range(max_retries + 1):
        try:
            result = _call_llm(text, provider_override)
            # 校验结构合法性
            validate(instance=result, schema=LLM_OUTPUT_SCHEMA)
            # 控制输出规模，防止过大
            result["entities"] = result.get("entities", [])[:10]
            result["relations"] = result.get("relations", [])[:12]
            return result
        except (json.JSONDecodeError, ValidationError, httpx.HTTPError) as exc:
            # 记录错误并继续重试
            last_error = str(exc)
            continue

    return {
        "error": "LLM_VALIDATION_FAILED",
        "details": last_error or "Unknown error",
        "entities": [],
        "relations": [],
    }
