from __future__ import annotations

import os
from typing import Dict, List

from .community_detection import detect_communities
from .community_summarizer import summarize_communities
from .graph_builder import build_graph
from .graph_store import load_graph, save_graph
from .quality_checks import run_quality_checks
from .summary_store import load_summaries, save_summaries


class GraphRAGPipeline:
    def __init__(self, store_path: str):
        self.store_path = store_path
        os.makedirs(self.store_path, exist_ok=True)

    def _assemble_artifacts(self, nodes, edges, metadata, community_by_node=None, community_summaries=None):
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": metadata or {},
            "community_by_node": community_by_node or {},
            "community_summaries": community_summaries or {},
            "chunk_entity_index": (metadata or {}).get("chunk_entity_index", {}),
        }

    def build_from_chunks(self, chunks: List[Dict]) -> Dict:
        nodes, edges, metadata = build_graph(chunks)
        community_by_node, communities = detect_communities(nodes, edges)
        community_summaries = summarize_communities(communities, nodes)

        chunk_to_community = {}
        for node_id, community_id in community_by_node.items():
            node = nodes.get(node_id)
            if not node:
                continue
            for chunk_id in node.chunk_ids:
                chunk_to_community.setdefault(chunk_id, community_id)

        metadata["chunk_to_community"] = chunk_to_community

        save_graph(self.store_path, nodes, edges, metadata)
        save_summaries(self.store_path, community_summaries)

        artifacts = self._assemble_artifacts(nodes, edges, metadata, community_by_node, community_summaries)
        checks = run_quality_checks(chunks, artifacts)

        return {
            "artifacts": artifacts,
            "stats": {
                "nodes": len(nodes),
                "edges": len(edges),
                "communities": len(communities),
                "quality": checks,
            },
        }

    def build_from_collection(self, collection) -> Dict:
        rows = collection.get(include=["documents", "metadatas"])
        documents = rows.get("documents", [])
        metadatas = rows.get("metadatas", [])
        ids = rows.get("ids", [])

        chunks = []
        for doc, meta, cid in zip(documents, metadatas, ids):
            metadata = meta or {}
            chunk_id = metadata.get("chunk_id") or cid
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "source": metadata.get("source", "unknown"),
                    "page": metadata.get("page", 0),
                    "doc_id": metadata.get("doc_id", ""),
                    "section": metadata.get("section", "untitled"),
                    "ingested_at": metadata.get("ingested_at", ""),
                    "chunk_hash": metadata.get("chunk_hash", ""),
                    "text": doc,
                }
            )

        return self.build_from_chunks(chunks)

    def load_artifacts(self) -> Dict:
        nodes, edges, metadata = load_graph(self.store_path)
        summaries = load_summaries(self.store_path)

        community_by_node = {}
        chunk_to_community = metadata.get("chunk_to_community", {}) if metadata else {}
        if nodes and chunk_to_community:
            for node_id, node in nodes.items():
                for chunk_id in node.chunk_ids:
                    if chunk_id in chunk_to_community:
                        community_by_node[node_id] = chunk_to_community[chunk_id]
                        break

        return self._assemble_artifacts(nodes, edges, metadata, community_by_node, summaries)
