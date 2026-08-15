from __future__ import annotations

from collections import deque
from typing import Dict, List, Set, Tuple

from .graph_models import GraphEdge, GraphNode


def seed_nodes_from_query(query: str, nodes: Dict[str, GraphNode]) -> List[str]:
    q = (query or "").lower()
    seeds = [nid for nid, node in nodes.items() if node.value.lower() in q or q in node.value.lower()]
    if seeds:
        return seeds[:10]
    query_tokens = [t for t in q.split() if len(t) > 2]
    for token in query_tokens:
        for nid, node in nodes.items():
            if token in node.value.lower():
                seeds.append(nid)
    seen = set()
    unique = []
    for seed in seeds:
        if seed not in seen:
            seen.add(seed)
            unique.append(seed)
    return unique[:10]


def build_adjacency(edges: Dict[str, GraphEdge]) -> Dict[str, Set[Tuple[str, str]]]:
    adjacency: Dict[str, Set[Tuple[str, str]]] = {}
    for edge_id, edge in edges.items():
        adjacency.setdefault(edge.source_id, set()).add((edge.target_id, edge_id))
        adjacency.setdefault(edge.target_id, set()).add((edge.source_id, edge_id))
    return adjacency


def retrieve_multihop(seeds: List[str], edges: Dict[str, GraphEdge], max_hops: int = 2, max_nodes: int = 80) -> Dict:
    adjacency = build_adjacency(edges)
    visited_nodes = set(seeds)
    visited_edges = set()
    queue = deque((seed, 0) for seed in seeds)

    while queue and len(visited_nodes) < max_nodes:
        node_id, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for neighbor, edge_id in adjacency.get(node_id, set()):
            visited_edges.add(edge_id)
            if neighbor not in visited_nodes:
                visited_nodes.add(neighbor)
                queue.append((neighbor, depth + 1))

    return {
        "node_ids": list(visited_nodes),
        "edge_ids": list(visited_edges),
        "hops": max_hops,
    }
