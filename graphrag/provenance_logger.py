from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict


def log_provenance(log_path: str, query: str, graph_context: Dict):
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "seed_nodes": graph_context.get("seed_nodes", []),
        "node_ids": graph_context.get("node_ids", []),
        "edge_ids": graph_context.get("edge_ids", []),
        "chunk_ids": list(graph_context.get("chunk_boosts", {}).keys()),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")
