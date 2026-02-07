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
    "textbook": PromptStrategy("重视知识模块、概念、公式/定理/定律与推导关系。"),
    "handbook": PromptStrategy("重视工具/标准、流程步骤、参数指标与问题-方案关系。"),
    "humanities": PromptStrategy("重视理论观点、学派流派、人物动机与因果链条。"),
    "exam": PromptStrategy("重视考点、题型、答题技巧与知识点映射关系。"),
    "popular_science": PromptStrategy("重视科学概念、现象规律、实验/发现与解释关系。"),
    "business": PromptStrategy("重视模型方法论、流程步骤、案例与应用关系。"),
    "history_geo": PromptStrategy("重视历史人物、事件、时间线与地理关联关系。"),
    "literature": PromptStrategy("重视人物、情节、主题意象、叙事关系与修辞线索。"),
    "lifestyle": PromptStrategy("重视核心对象、工具、步骤流程与适用场景关系。"),
    "general": PromptStrategy("重视章节主题的核心概念与关键因果关系。"),
}


def build_prompt(text: str, book_type: str | None) -> str:
    normalized = normalize_book_type(book_type)
    strategy = STRATEGIES.get(normalized, STRATEGIES["general"])
    return strategy.build(text)
