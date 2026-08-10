from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Tuple

from .graph_models import GraphEdge, GraphNode


def detect_communities(nodes: Dict[str, GraphNode], edges: Dict[str, GraphEdge]) -> Tuple[Dict[str, int], Dict[int, List[str]]]:
    adjacency = defaultdict(set)
    for edge in edges.values():
        adjacency[edge.source_id].add(edge.target_id)
        adjacency[edge.target_id].add(edge.source_id)

    community_by_node: Dict[str, int] = {}
    communities: Dict[int, List[str]] = {}
    community_id = 0

    for node_id in nodes.keys():
        if node_id in community_by_node:
            continue
        queue = deque([node_id])
        members = []
        while queue:
            cur = queue.popleft()
            if cur in community_by_node:
                continue
            community_by_node[cur] = community_id
            members.append(cur)
            for nxt in adjacency.get(cur, set()):
                if nxt not in community_by_node:
                    queue.append(nxt)
        communities[community_id] = members
        community_id += 1

    return community_by_node, communities
