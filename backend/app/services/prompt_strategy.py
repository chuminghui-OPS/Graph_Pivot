from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.core.book_types import normalize_book_type


@dataclass(frozen=True)
class PromptCatalog:
    default: str
    prompts: Dict[str, str]


_CATALOG_CACHE: Tuple[PromptCatalog, float] | None = None


def _catalog_path() -> Path:
    app_dir = Path(__file__).resolve().parents[1]
    return app_dir / "prompt.txt"


def _parse_prompt_catalog(raw: str) -> PromptCatalog:
    default = "general"
    prompts: Dict[str, str] = {}
    current_id: Optional[str] = None
    collecting = False
    buffer: list[str] = []

    lines = raw.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("default:"):
            default = stripped.split(":", 1)[1].strip() or default
            continue
        if stripped.startswith("- id:"):
            if current_id and buffer:
                prompts[current_id] = "\n".join(buffer).rstrip()
            current_id = stripped.split(":", 1)[1].strip()
            collecting = False
            buffer = []
            continue
        if current_id and stripped.startswith("prompt:"):
            collecting = True
            buffer = []
            continue
        if collecting:
            # Prompt body lines are indented in catalog; keep original spacing.
            if line.startswith("      "):
                buffer.append(line[6:])
            elif line.startswith("    "):
                buffer.append(line[4:])
            else:
                # Non-indented line means prompt block ended.
                collecting = False
            continue

    if current_id and buffer:
        prompts[current_id] = "\n".join(buffer).rstrip()

    return PromptCatalog(default=default, prompts=prompts)


def _load_catalog() -> PromptCatalog:
    global _CATALOG_CACHE
    path = _catalog_path()
    try:
        stat = path.stat()
    except FileNotFoundError:
        return PromptCatalog(default="general", prompts={})
    mtime = stat.st_mtime
    if _CATALOG_CACHE and _CATALOG_CACHE[1] == mtime:
        return _CATALOG_CACHE[0]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    catalog = _parse_prompt_catalog(raw)
    _CATALOG_CACHE = (catalog, mtime)
    return catalog


def build_prompt(text: str, book_type: str | None) -> str:
    normalized = normalize_book_type(book_type)
    catalog = _load_catalog()
    prompt = catalog.prompts.get(normalized) or catalog.prompts.get(catalog.default)
    if not prompt:
        # Hard fallback to avoid crash if catalog missing.
        return f"你是资深知识图谱抽取专家。\\n文本：\\n{text}\\n"
    return prompt.replace("{text}", text)
