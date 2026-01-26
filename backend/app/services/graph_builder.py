from __future__ import annotations

from typing import Any, Dict, List


# 将多个 chunk 的抽取结果合并为章节级图谱
def build_chapter_graph(chapter_id: str, chunk_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    entity_map: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    # 确保实体唯一，并为其生成节点 ID
    def ensure_entity(name: str, entity_type: str | None = None) -> None:
        if not name:
            return
        if name not in entity_map:
            entity_map[name] = {
                "id": f"n{len(entity_map) + 1}",
                "name": name,
                "type": entity_type or "Concept",
            }

    for result in chunk_results:
        # 合并实体
        for entity in result.get("entities", []):
            ensure_entity(entity.get("name", "").strip(), entity.get("type", "Concept"))

        # 合并关系，并补全对应实体
        for relation in result.get("relations", []):
            source = relation.get("source", "").strip()
            target = relation.get("target", "").strip()
            ensure_entity(source)
            ensure_entity(target)
            edge = {
                "source": source,
                "target": target,
                "relation": relation.get("relation", "").strip(),
                "evidence": relation.get("evidence", "").strip(),
                "confidence": float(relation.get("confidence", 0.5)) if relation.get("confidence") else 0.5,
            }
            edges.append(edge)

    return {
        "chapter_id": chapter_id,
        "nodes": list(entity_map.values()),
        "edges": edges,
    }
