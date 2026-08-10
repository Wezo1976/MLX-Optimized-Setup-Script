from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Dict, List


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_doc_id(source_path: str) -> str:
    return hashlib.sha256(source_path.encode("utf-8")).hexdigest()


def derive_section(text: str) -> str:
    for line in text.splitlines():
        clean = line.strip()
        if clean:
            return clean[:120]
    return "untitled"


def stable_chunk_id(doc_id: str, page: int, char_position: int, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"{doc_id[:12]}_p{page}_c{char_position}_{digest}"


def enrich_chunks(chunks_with_metadata: List[Dict], source_path: str, chunk_size: int, chunk_overlap: int) -> List[Dict]:
    doc_id = stable_doc_id(source_path)
    stride = max(1, chunk_size - chunk_overlap)
    now = utc_now_iso()
    enriched: List[Dict] = []

    for item in chunks_with_metadata:
        page = int(item.get("page", 0) or 0)
        text = item.get("text", "")
        source = item.get("source", "unknown")
        if not text:
            continue

        for i in range(0, len(text), stride):
            chunk_text = text[i : i + chunk_size]
            if not chunk_text.strip():
                continue
            chunk_id = stable_chunk_id(doc_id, page, i, chunk_text)
            enriched.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "source": source,
                    "page": page,
                    "char_position": i,
                    "section": derive_section(chunk_text),
                    "ingested_at": now,
                    "chunk_hash": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
                    "text": chunk_text,
                }
            )

    return enriched
