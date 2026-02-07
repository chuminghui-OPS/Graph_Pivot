from __future__ import annotations

from dataclasses import dataclass

from app.core.book_types import BOOK_CATEGORIES, normalize_book_type


BASE_RULES = (
    "你是资深知识图谱抽取专家。\n"
    "目标：只抽取真正关键、可复用的实体与关系，过滤噪声和无关细节。\n"
    "规则：\n"
    "1) 实体必须是“概念/人物/组织/地点/技术/事件”等核心名词，避免长句或碎片。\n"
    "2) 实体需去重，名称尽量短；只保留能代表章节主题的实体。\n"
    "3) 关系必须有明确证据句（来自原文），不要凭空推断。\n"
    "4) 实体和关系按重要性排序，最多实体 10 个、关系 12 条。\n"
    "5) 返回严格 JSON，只能包含 keys: entities, relations；不要代码块、不要解释。\n"
    "6) count 表示实体在文本中出现的次数（可用粗略计数，最少为 1）。\n"
)

OUTPUT_FORMAT = (
    "输出格式（必须严格一致）：\n"
    "{\n"
    "  \"entities\": [\n"
    "    {\"name\": \"实体名\", \"type\": \"类型\", \"count\": 3}\n"
    "  ],\n"
    "  \"relations\": [\n"
    "    {\"source\": \"实体A\", \"target\": \"实体B\", \"relation\": \"关系\", \"evidence\": \"原文短句\"}\n"
    "  ]\n"
    "}\n"
    "禁止输出额外字段。\n"
)


@dataclass(frozen=True)
class PromptStrategy:
    focus: str

    def build(self, text: str) -> str:
        return (
            f"{BASE_RULES}"
            f"领域侧重点：{self.focus}\n"
            f"{OUTPUT_FORMAT}\n\n"
            f"文本：\n{text}\n"
        )


STRATEGIES = {
    "literature": PromptStrategy("重视人物、情节、主题意象、叙事关系与修辞线索。"),
    "technology": PromptStrategy("重视技术概念、方法、算法、系统组件与依赖关系。"),
    "history": PromptStrategy("重视事件、人物、时间线、因果关系与历史背景。"),
    "philosophy": PromptStrategy("重视概念、观点、论证结构与思想流派关系。"),
    "economics": PromptStrategy("重视模型、指标、市场主体、政策工具与因果链。"),
    "art": PromptStrategy("重视流派、作品、技法、风格特征与影响关系。"),
    "education": PromptStrategy("重视教学目标、知识点、方法策略与学习路径关系。"),
    "biography": PromptStrategy("重视人物经历、阶段事件、成就与影响关系。"),
    "other": PromptStrategy("重视章节主题的核心概念与关键因果关系。"),
}


def build_prompt(text: str, book_type: str | None) -> str:
    normalized = normalize_book_type(book_type)
    strategy = STRATEGIES.get(normalized, STRATEGIES["other"])
    return strategy.build(text)
