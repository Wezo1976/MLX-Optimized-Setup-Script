from __future__ import annotations

from typing import Dict

from .graph_models import GraphNode


def summarize_communities(communities: Dict[int, list], nodes: Dict[str, GraphNode], max_entities: int = 8) -> Dict[int, Dict]:
    summaries = {}
    for cid, member_ids in communities.items():
        members = [nodes[mid] for mid in member_ids if mid in nodes]
        members.sort(key=lambda n: len(n.chunk_ids), reverse=True)
        top = members[:max_entities]
        entity_labels = [f"{n.value} ({n.entity_type})" for n in top]
        summary_text = ", ".join(entity_labels) if entity_labels else "No entities"
        summaries[cid] = {
            "community_id": cid,
            "member_count": len(members),
            "top_entities": entity_labels,
            "summary": f"Community {cid}: {summary_text}",
        }
    return summaries
