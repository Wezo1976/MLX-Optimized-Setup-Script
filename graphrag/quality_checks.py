from __future__ import annotations

from typing import Dict, List


def run_quality_checks(chunks: List[Dict], graph_artifacts: Dict) -> Dict:
    chunk_ids = {c.get("chunk_id") for c in chunks if c.get("chunk_id")}
    linked_chunk_ids = set()

    for node in graph_artifacts.get("nodes", {}).values():
        linked_chunk_ids.update(node.chunk_ids)

    coverage = (len(chunk_ids & linked_chunk_ids) / len(chunk_ids)) if chunk_ids else 0.0
    duplicate_chunk_ids = len(chunk_ids) != len([c.get("chunk_id") for c in chunks if c.get("chunk_id")])

    return {
        "chunk_count": len(chunk_ids),
        "linked_chunk_count": len(chunk_ids & linked_chunk_ids),
        "coverage": coverage,
        "duplicate_chunk_ids": duplicate_chunk_ids,
        "ok": coverage >= 0.25 and not duplicate_chunk_ids,
    }
