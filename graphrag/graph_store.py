from __future__ import annotations

import json
import os
from typing import Dict, Tuple

from .graph_models import GraphEdge, GraphNode


GRAPH_FILE = "graph_snapshot.json"


def save_graph(path: str, nodes: Dict[str, GraphNode], edges: Dict[str, GraphEdge], metadata: Dict) -> str:
    os.makedirs(path, exist_ok=True)
    payload = {
        "nodes": {k: vars(v) for k, v in nodes.items()},
        "edges": {k: vars(v) for k, v in edges.items()},
        "metadata": metadata,
    }
    file_path = os.path.join(path, GRAPH_FILE)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return file_path


def load_graph(path: str) -> Tuple[Dict[str, GraphNode], Dict[str, GraphEdge], Dict]:
    file_path = os.path.join(path, GRAPH_FILE)
    if not os.path.exists(file_path):
        return {}, {}, {}

    with open(file_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    nodes = {k: GraphNode(**v) for k, v in payload.get("nodes", {}).items()}
    edges = {k: GraphEdge(**v) for k, v in payload.get("edges", {}).items()}
    metadata = payload.get("metadata", {})
    return nodes, edges, metadata
