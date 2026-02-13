from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, Optional

import httpx
from jsonschema import validate, ValidationError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.json_schema import LLM_OUTPUT_SCHEMA
from app.services.prompt_strategy import build_prompt
from app.models import ApiAsset, Book
from app.utils.crypto import decrypt_value


class LLMConfig(BaseModel):
    provider: str = "qwen"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    api_path: str | None = None


# 生成 LLM 提示词（控制输出结构与重要性）
def _build_prompt(text: str, book_type: str | None) -> str:
    return build_prompt(text, book_type)


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


def _extract_error_message(payload: str) -> str:
    try:
        data = json.loads(payload)
    except Exception:
        return payload.strip()[:300]
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or err.get("detail") or err.get("error")
            if msg:
                return str(msg)
        msg = data.get("message") or data.get("detail") or data.get("error")
        if msg:
            return str(msg)
    return payload.strip()[:300]


def _format_llm_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        body = exc.response.text or ""
        message = _extract_error_message(body) if body else str(exc)
        lowered = message.lower()
        if status in (401, 403):
            return "模型密钥无效或权限不足"
        if status == 429 or "rate limit" in lowered or "ratelimit" in lowered:
            return "模型调用被限流，请稍后重试"
        if status == 402 or "insufficient" in lowered or "quota" in lowered or "balance" in lowered:
            return "模型余额不足或调用额度不足"
        return f"模型服务调用失败（{status}）: {message}"
    if isinstance(exc, httpx.HTTPError):
        return "模型服务调用失败，请检查网络或服务状态"
    return str(exc)[:300]


def _get_retry_delay(exc: httpx.HTTPError, attempt: int) -> float:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            retry_after = exc.response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                return min(30.0, float(retry_after))
            return min(30.0, 2.0 * (attempt + 1))
    return 0.0

# 获取当前 LLM 提供方信息（供前端展示）
def get_llm_info(provider_override: str | None = None) -> Dict[str, str]:
    provider = (provider_override or settings.llm_provider).lower()
    if provider == "gemini":
        return {"provider": "Gemini", "model": settings.gemini_model}
    if provider == "custom":
        return {"provider": "自定义", "model": ""}
    return {"provider": "通义千问", "model": settings.llm_model}

# 调用 Gemini API
def _call_gemini(
    text: str,
    model: str | None = None,
    api_key: str | None = None,
    book_type: str | None = None,
) -> Dict[str, Any]:
    if not settings.gemini_api_key:
        return _stub_result(text)

    from google import genai

    client = genai.Client(api_key=api_key or settings.gemini_api_key)
    response = client.models.generate_content(
        model=model or settings.gemini_model,
        contents=_build_prompt(text, book_type),
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
def _call_openai_compatible(text: str, config: LLMConfig, book_type: str | None) -> Dict[str, Any]:
    if not config.api_key:
        return _stub_result(text)
    base_url = config.base_url or settings.llm_base_url
    path = config.api_path or "/chat/completions"
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Authorization": f"Bearer {config.api_key}"}
    payload = {
        "model": config.model or settings.llm_model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": _build_prompt(text, book_type)},
        ],
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(_strip_json_fence(content))


def _call_llm(
    text: str,
    provider_override: str | None = None,
    config_override: LLMConfig | None = None,
    book_type: str | None = None,
) -> Dict[str, Any]:
    provider = (provider_override or settings.llm_provider).lower()
    if provider == "gemini":
        return _call_gemini(text, book_type=book_type)
    if provider == "custom" and config_override:
        if config_override.provider.lower() == "gemini":
            return _call_gemini(
                text, model=config_override.model, api_key=config_override.api_key, book_type=book_type
            )
        return _call_openai_compatible(text, config_override, book_type)

    if not settings.llm_api_key:
        return _stub_result(text)
    default_config = LLMConfig(
        provider=provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )
    return _call_openai_compatible(text, default_config, book_type)


def resolve_asset_config(db: Session, book: Book) -> LLMConfig | None:
    if not book.llm_asset_id:
        return None
    asset = db.get(ApiAsset, book.llm_asset_id)
    if not asset:
        return None
    return LLMConfig(
        provider=asset.provider,
        model=book.llm_model or (asset.models[0] if asset.models else None),
        api_key=decrypt_value(asset.api_key),
        base_url=asset.base_url,
        api_path=asset.api_path,
    )


# 抽取并进行 JSON Schema 校验，失败自动重试
def extract_with_validation(
    text: str,
    max_retries: int = 2,
    provider_override: str | None = None,
    config_override: LLMConfig | None = None,
    book_type: str | None = None,
) -> Dict[str, Any]:
    last_error: str | None = None
    last_error_code: str | None = None
    for attempt in range(max_retries + 1):
        try:
            result = _call_llm(text, provider_override, config_override, book_type)
            # 校验结构合法性
            validate(instance=result, schema=LLM_OUTPUT_SCHEMA)
            # 硬截断实体/关系数量， prompt 控制密度
            result["entities"] = result.get("entities", [])[:1000]
            result["relations"] = result.get("relations", [])[:5000]
            return result
        except httpx.HTTPError as exc:
            # 记录错误并继续重试
            last_error_code = "LLM_HTTP_ERROR"
            last_error = _format_llm_error(exc)
            delay = _get_retry_delay(exc, attempt)
            if delay > 0:
                time.sleep(delay)
            continue
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error_code = "LLM_VALIDATION_FAILED"
            last_error = str(exc)
            continue

    return {
        "error": last_error_code or "LLM_VALIDATION_FAILED",
        "details": last_error or "Unknown error",
        "entities": [],
        "relations": [],
    }
