from __future__ import annotations

from typing import Dict, List

from .multihop_retriever import retrieve_multihop, seed_nodes_from_query
from .reranker import rerank_results


class QueryEngine:
    def __init__(self, graph_artifacts: Dict):
        self.nodes = graph_artifacts.get("nodes", {})
        self.edges = graph_artifacts.get("edges", {})
        self.community_by_node = graph_artifacts.get("community_by_node", {})
        self.community_summaries = graph_artifacts.get("community_summaries", {})
        self.chunk_entity_index = graph_artifacts.get("chunk_entity_index", {})

    def _chunk_boosts(self, node_ids: List[str], edge_ids: List[str]) -> Dict[str, float]:
        boosts: Dict[str, float] = {}

        for node_id in node_ids:
            node = self.nodes.get(node_id)
            if not node:
                continue
            for chunk_id in node.chunk_ids:
                boosts[chunk_id] = boosts.get(chunk_id, 0.0) + 1.0

        for edge_id in edge_ids:
            edge = self.edges.get(edge_id)
            if not edge:
                continue
            for chunk_id in edge.chunk_ids:
                boosts[chunk_id] = boosts.get(chunk_id, 0.0) + edge.weight

        return boosts

    def retrieve(self, query: str, base_results: Dict) -> Dict:
        seeds = seed_nodes_from_query(query, self.nodes)
        graph_walk = retrieve_multihop(seeds, self.edges, max_hops=2) if seeds else {"node_ids": [], "edge_ids": [], "hops": 0}

        chunk_boosts = self._chunk_boosts(graph_walk["node_ids"], graph_walk["edge_ids"])
        reranked = rerank_results(base_results, chunk_boosts)

        communities = sorted({self.community_by_node.get(node_id) for node_id in graph_walk["node_ids"] if node_id in self.community_by_node})
        community_evidence = [self.community_summaries.get(cid, {}) for cid in communities]

        return {
            "results": reranked,
            "graph_context": {
                "seed_nodes": seeds,
                "node_ids": graph_walk["node_ids"],
                "edge_ids": graph_walk["edge_ids"],
                "communities": community_evidence,
                "chunk_boosts": chunk_boosts,
            },
        }
