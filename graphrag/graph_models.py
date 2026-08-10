from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class GraphNode:
    id: str
    value: str
    entity_type: str
    chunk_ids: List[str] = field(default_factory=list)
    source_files: List[str] = field(default_factory=list)


@dataclass
class GraphEdge:
    id: str
    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0
    chunk_ids: List[str] = field(default_factory=list)


@dataclass
class GraphSnapshot:
    nodes: Dict[str, GraphNode]
    edges: Dict[str, GraphEdge]
    metadata: Dict
