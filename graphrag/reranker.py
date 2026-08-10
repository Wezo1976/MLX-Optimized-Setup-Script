from __future__ import annotations

from typing import Dict, List


def rerank_results(base_results: Dict, chunk_boosts: Dict[str, float], alpha: float = 0.75) -> Dict:
    docs = base_results.get("documents", [[]])[0]
    metas = base_results.get("metadatas", [[]])[0]
    base_scores = base_results.get("scores")

    if base_scores:
        scores = base_scores[0]
    else:
        distances = base_results.get("distances", [[]])[0]
        scores = [(1 - d) if d is not None else 0.0 for d in distances]

    combined: List[Dict] = []
    for doc, meta, score in zip(docs, metas, scores):
        chunk_id = meta.get("chunk_id")
        graph_boost = chunk_boosts.get(chunk_id, 0.0)
        final_score = (alpha * score) + ((1 - alpha) * graph_boost)
        updated_meta = dict(meta)
        updated_meta["graph_boost"] = graph_boost
        combined.append({"doc": doc, "meta": updated_meta, "score": final_score})

    combined.sort(key=lambda item: item["score"], reverse=True)

    return {
        "documents": [[item["doc"] for item in combined]],
        "metadatas": [[item["meta"] for item in combined]],
        "scores": [[item["score"] for item in combined]],
    }
