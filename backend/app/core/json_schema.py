from __future__ import annotations


# LLM 输出 JSON Schema：约束实体与关系结构
LLM_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["entities", "relations"],
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type", "count"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "count": {"type": "integer", "minimum": 1},
                    "properties": {"type": "object", "additionalProperties": True},
                },
                "additionalProperties": False,
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source", "target", "relation", "evidence"],
                "properties": {
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "relation": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}
