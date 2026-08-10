from __future__ import annotations

import hashlib
from typing import Dict, List, Tuple

from .entity_extractor import extract_entities
from .graph_models import GraphEdge, GraphNode
from .relation_extractor import extract_relations


def _node_id(entity_value: str, entity_type: str) -> str:
    key = f"{entity_type}:{entity_value.lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _edge_id(source_id: str, target_id: str, relation_type: str) -> str:
    ordered = tuple(sorted([source_id, target_id]))
    key = f"{ordered[0]}|{ordered[1]}|{relation_type}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def build_graph(chunks: List[Dict]) -> Tuple[Dict[str, GraphNode], Dict[str, GraphEdge], Dict]:
    nodes: Dict[str, GraphNode] = {}
    edges: Dict[str, GraphEdge] = {}
    chunk_entity_index: Dict[str, List[str]] = {}

    for chunk in chunks:
        text = chunk.get("text", "")
        chunk_id = chunk.get("chunk_id")
        source = chunk.get("source", "unknown")
        if not text or not chunk_id:
            continue

        entities = extract_entities(text)
        values = []

        for entity in entities:
            nid = _node_id(entity.value, entity.entity_type)
            values.append(entity.value)
            if nid not in nodes:
                nodes[nid] = GraphNode(
                    id=nid,
                    value=entity.value,
                    entity_type=entity.entity_type,
                    chunk_ids=[chunk_id],
                    source_files=[source],
                )
            else:
                if chunk_id not in nodes[nid].chunk_ids:
                    nodes[nid].chunk_ids.append(chunk_id)
                if source not in nodes[nid].source_files:
                    nodes[nid].source_files.append(source)

            chunk_entity_index.setdefault(chunk_id, []).append(nid)

        relations = extract_relations(text, values)
        node_map = {(n.value, n.entity_type): n.id for n in nodes.values()}
        value_to_id = {}
        for entity in entities:
            nid = _node_id(entity.value, entity.entity_type)
            value_to_id[entity.value] = nid

        for relation in relations:
            source_id = value_to_id.get(relation.source)
            target_id = value_to_id.get(relation.target)
            if not source_id or not target_id or source_id == target_id:
                continue

            eid = _edge_id(source_id, target_id, relation.relation_type)
            if eid not in edges:
                edges[eid] = GraphEdge(
                    id=eid,
                    source_id=source_id,
                    target_id=target_id,
                    relation_type=relation.relation_type,
                    weight=1.0,
                    chunk_ids=[chunk_id],
                )
            else:
                edges[eid].weight += 1.0
                if chunk_id not in edges[eid].chunk_ids:
                    edges[eid].chunk_ids.append(chunk_id)

    metadata = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "chunk_entity_index": chunk_entity_index,
    }
    return nodes, edges, metadata
