#!/usr/bin/env python3
"""
MLX-Optimized RAG Chat V1.11 - Streamlit UI with Court-Ready Features
- Chat UI for PDF RAG queries with page-level citations
- Auto-load PDFs from folder + persistent Chroma DB
- Sidebar wipe/re-ingest checkbox
- Hybrid semantic + BM25 keyword search
- Audit trail logging for compliance
- Hallucination detection & grounding validation
- Primary: MLX streaming generation (fast on M4)
- Fallback: Ollama chat
- Run: streamlit run mlx_optimized_v1_11.py
"""

import os
import glob
import psutil
import streamlit as st
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
import fitz  # PyMuPDF
from mlx_lm import load, stream_generate
from typing import List, Dict, Tuple
import json
from datetime import datetime
import hashlib
import re
import numpy as np
from rank_bm25 import BM25Okapi

# ────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────
DEFAULT_PDF_FOLDER = os.path.expanduser("~/Documents/PDFs")
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "pdf_rag_collection"
EMBED_MODEL = "nomic-embed-text:v1.5"
GEN_MODEL_MLX = "mlx-community/Qwen2.5-14B-Instruct-4bit-MLX"
FALLBACK_GEN_OLLAMA = "qwen2.5:14b"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MAX_TOKENS_NORMAL = 4096
MAX_TOKENS_LOW = 2048
TEMP_NORMAL = 0.6
TEMP_LOW = 0.35
HYBRID_ALPHA = 0.7  # 70% semantic, 30% keyword

AUDIT_LOG_PATH = "./rag_audit_log.jsonl"

os.environ["MLX_NUM_THREADS"] = "0"

# ────────────────────────────────────────────────
# Resource Check
# ────────────────────────────────────────────────
def check_resources():
    """Monitor M4 system resources"""
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.5)
    high = mem.percent > 80 or cpu > 85
    status = f"CPU: {cpu:.1f}% | Mem: {mem.percent:.1f}% ({mem.used/1e9:.1f}/{mem.total/1e9:.1f} GB)"
    return high, status

# ────────────────────────────────────────────────
# PDF Processing with Page Tracking
# ────────────────────────────────────────────────
def extract_text_with_pages(pdf_path: str) -> List[Dict]:
    """Extract text WITH page numbers - critical for court docs"""
    try:
        doc = fitz.open(pdf_path)
        chunks_with_metadata = []
        
        for page_num, page in enumerate(doc, 1):
            text = page.get_text('text')
            paragraphs = text.split('\n\n')
            
            for para in paragraphs:
                if para.strip():
                    chunks_with_metadata.append({
                        "text": para,
                        "page": page_num,
                        "source": os.path.basename(pdf_path),
                    })
        
        doc.close()
        return chunks_with_metadata
    except Exception as e:
        st.warning(f"Failed to extract: {e}")
        return []

def chunk_with_page_metadata(chunks_with_metadata: List[Dict], chunk_size=800) -> List[Dict]:
    """Chunk while preserving page numbers"""
    result = []
    for item in chunks_with_metadata:
        text = item["text"]
        for i in range(0, len(text), chunk_size - 150):
            result.append({
                "text": text[i:i+chunk_size],
                "page": item["page"],
                "source": item["source"],
                "char_position": i
            })
    return result

def auto_load_pdfs(folder_path: str) -> List[str]:
    """Auto-discover PDFs in folder"""
    if not os.path.isdir(folder_path):
        st.error(f"Invalid folder path: {folder_path}")
        return []
    return glob.glob(os.path.join(folder_path, "*.pdf"))

# ────────────────────────────────────────────────
# Audit Trail
# ────────────────────────────────────────────────
class AuditTrail:
    """Court-ready audit logging"""
    def __init__(self, log_path=AUDIT_LOG_PATH):
        self.log_path = log_path
    
    def log_query(self, query: str, results: Dict, response: str, model_used: str, user_id: str = "system") -> Dict:
        """Log every query for court review"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user": user_id,
            "query_hash": hashlib.sha256(query.encode()).hexdigest(),
            "query": query,
            "model": model_used,
            "sources_used": len(results.get("documents", [[]])[0]) if results.get("documents") else 0,
            "source_files": [m.get("source", "unknown") for m in results.get("metadatas", [[]])[0]] if results.get("metadatas") else [],
            "response_length": len(response),
            "response_hash": hashlib.sha256(response.encode()).hexdigest()
        }
        
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        
        return entry

auditor = AuditTrail()

# ────────────────────────────────────────────────
# Hybrid Search (Semantic + BM25)
# ────────────────────────────────────────────────
def hybrid_retrieval(collection, query: str, n_results: int = 5, alpha: float = HYBRID_ALPHA) -> Dict:
    """
    Hybrid search: alpha * semantic + (1-alpha) * keyword
    For legal docs, catches both nuance AND exact terminology
    """
    # Semantic search via Chroma
    semantic_results = collection.query(query_texts=[query], n_results=n_results*2)
    
    # Keyword search (BM25)
    all_docs_result = collection.get(include=["documents"])
    all_docs = all_docs_result.get("documents", [])
    
    if not all_docs:
        return semantic_results
    
    corpus = [doc.split() for doc in all_docs]
    bm25 = BM25Okapi(corpus)
    
    query_tokens = query.split()
    bm25_scores = bm25.get_scores(query_tokens)
    top_bm25_indices = np.argsort(bm25_scores)[-n_results:][::-1]
    
    # Combine results
    combined = {}
    
    # Add semantic results
    for i, (doc, meta, dist) in enumerate(zip(
        semantic_results.get("documents", [[]])[0],
        semantic_results.get("metadatas", [[]])[0],
        semantic_results.get("distances", [[]])[0]
    )):
        doc_id = f"{meta.get('source', 'unknown')}_{meta.get('chunk_id', i)}"
        combined[doc_id] = {
            "doc": doc, 
            "meta": meta, 
            "score": (1 - dist) * alpha if dist is not None else 0.5 * alpha
        }
    
    # Add/boost keyword results
    for idx in top_bm25_indices:
        if idx < len(all_docs):
            doc = all_docs[idx]
            doc_id = f"bm25_{idx}"
            score = bm25_scores[idx] * (1 - alpha)
            if doc_id not in combined:
                combined[doc_id] = {"doc": doc, "meta": {"source": "keyword_match"}, "score": score}
            else:
                combined[doc_id]["score"] += score
    
    # Sort by combined score
    sorted_results = sorted(combined.items(), key=lambda x: x[1]["score"], reverse=True)[:n_results]
    
    return {
        "documents": [[item[1]["doc"] for item in sorted_results]],
        "metadatas": [[item[1]["meta"] for item in sorted_results]],
        "scores": [[item[1]["score"] for item in sorted_results]]
    }

# ────────────────────────────────────────────────
# Response Validation
# ────────────────────────────────────────────────
def validate_response(response: str, context: str, query: str) -> Dict:
    """
    Court-ready validation:
    - Check if response is grounded in context
    - Flag potential hallucinations
    - Verify confidence
    """
    validation = {
        "grounded": True,
        "confidence": 0.0,
        "issues": [],
    }
    
    # Check: Is response grounded in context?
    context_words = set(context.lower().split())
    response_key_words = set(w for w in response.lower().split() if len(w) > 3)
    
    overlap = len(response_key_words & context_words) / (len(response_key_words) + 1)
    validation["confidence"] = overlap
    
    if overlap < 0.3:
        validation["grounded"] = False
        validation["issues"].append("⚠️ Low overlap with source material - potential hallucination risk")
    
    # Check: Response length relative to query
    if len(response) > len(context) * 2:
        validation["issues"].append("⚠️ Response significantly longer than sources - verify accuracy")
    
    # Check: Numbers consistency
    response_numbers = set(re.findall(r'\d+', response))
    context_numbers = set(re.findall(r'\d+', context))
    
    suspicious_numbers = response_numbers - context_numbers
    if suspicious_numbers and len(suspicious_numbers) > 1:
        validation["grounded"] = False
        validation["issues"].append(f"⚠️ Numbers not found in sources: {suspicious_numbers}")
    
    return validation

# ────────────────────────────────────────────────
# Chroma Collection Management
# ────────────────────────────────────────────────
@st.cache_resource(show_spinner="Ingesting PDFs...")
def get_or_create_collection(folder_path: str, force_reingest: bool):
    """Get or create Chroma collection with PDF data"""
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    ef = OllamaEmbeddingFunction(model_name=EMBED_MODEL, url="http://localhost:11434")

    try:
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"}
        )
    except Exception as e:
        st.error(f"Failed to create collection: {e}")
        return None

    if force_reingest:
        try:
            client.delete_collection(COLLECTION_NAME)
            collection = client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"}
            )
        except:
            pass

    if collection.count() == 0 or force_reingest:
        pdf_paths = auto_load_pdfs(folder_path)
        if not pdf_paths:
            st.error(f"No PDFs found in {folder_path}")
            return None

        st.info(f"Found {len(pdf_paths)} PDFs. Ingesting...")
        all_chunks, all_metadatas, all_ids = [], [], []

        for pdf_idx, path in enumerate(pdf_paths):
            chunks_with_meta = extract_text_with_pages(path)
            chunks_data = chunk_with_page_metadata(chunks_with_meta, CHUNK_SIZE)
            
            for chunk_idx, chunk_data in enumerate(chunks_data):
                all_chunks.append(chunk_data["text"])
                all_metadatas.append({
                    "source": chunk_data["source"],
                    "page": chunk_data["page"],
                    "chunk_id": chunk_idx
                })
                all_ids.append(f"doc_{pdf_idx}_chunk_{chunk_idx}")

        if all_chunks:
            collection.add(documents=all_chunks, metadatas=all_metadatas, ids=all_ids)
            st.success(f"✅ Ingested {collection.count()} chunks from {len(pdf_paths)} PDFs!")
        else:
            st.warning("No valid text extracted from PDFs.")
    else:
        st.info(f"✅ Using existing collection ({collection.count()} chunks)")

    return collection

# ────────────────────────────────────────────────
# Generation
# ────────────────────────────────────────────────
def generate_response(prompt: str, model, tokenizer, high_load: bool):
    """Generate response with MLX, fallback to Ollama"""
    kwargs = {
        "max_tokens": MAX_TOKENS_LOW if high_load else MAX_TOKENS_NORMAL,
        "temp": TEMP_LOW if high_load else TEMP_NORMAL,
        "verbose": False,
    }

    try:
        for chunk in stream_generate(model, tokenizer, prompt=prompt, **kwargs):
            yield chunk
    except Exception as e:
        st.warning(f"MLX issue: {e} → falling back to Ollama")
        try:
            import ollama
            resp = ollama.chat(
                model=FALLBACK_GEN_OLLAMA,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": kwargs["temp"], "num_predict": kwargs["max_tokens"]}
            )
            yield resp['message']['content']
        except Exception as e2:
            yield f"❌ Generation failed: {e2}"

# ────────────────────────────────────────────────
# Streamlit App
# ────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="MLX RAG Chat V1.11", layout="wide")
    st.title("🔥 MLX-Optimized RAG Chat V1.11")
    st.markdown("**Court-Ready PDF Analysis** | Local M4 RAG with Hybrid Search & Audit Trails")

    # ──── Sidebar ────
    with st.sidebar:
        st.header("⚙️ Settings")
        pdf_folder = st.text_input("PDF Folder Path", value=DEFAULT_PDF_FOLDER)
        wipe_checkbox = st.checkbox("🗑️ Wipe & Re-ingest", value=False,
                                    help="Delete current DB and re-process all PDFs")
        st.session_state["wipe"] = wipe_checkbox

        high_load, resource_str = check_resources()
        st.markdown(f"**M4 Status** \n{resource_str}")
        if high_load:
            st.warning("⚠️ Low-resource mode active (>80% memory)")
        else:
            st.success("✅ Optimal resources")

    # ──── Load Models ────
    @st.cache_resource
    def load_mlx_model():
        st.info("🤖 Loading MLX model... (first run ~1 min)")
        try:
            return load(GEN_MODEL_MLX)
        except Exception as e:
            st.error(f"❌ MLX load failed: {e}")
            st.info("Ensure: `pip install mlx-lm` and Apple Silicon")
            return None, None

    gen_model, tokenizer = load_mlx_model()
    if gen_model is None:
        st.stop()

    # ──── Get Collection ────
    collection = get_or_create_collection(pdf_folder, force_reingest=st.session_state.get("wipe", False))
    if collection is None:
        st.stop()

    # ──── Chat History ────
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ──── Chat Input ────
    if prompt := st.chat_input("Ask about your PDFs..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""

            # Retrieve using hybrid search
            results = hybrid_retrieval(collection, prompt, n_results=5, alpha=HYBRID_ALPHA)
            
            if not results.get("documents") or not results["documents"][0]:
                full_response = "❌ No relevant chunks found in your PDFs."
                message_placeholder.markdown(full_response)
            else:
                # Build context
                context_pieces = []
                for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
                    page_info = f"Page {meta.get('page', '?')}" if meta.get('page') else "page unknown"
                    context_pieces.append(f"[Source {i+1}: {meta.get('source', 'unknown')} - {page_info}]\n{doc}")

                context = "\n\n".join(context_pieces)

                rag_prompt = f"""Use ONLY this context from the PDFs to answer accurately:

{context}

Question: {prompt}

Answer:"""

                # Show retrieved chunks
                with st.expander("📖 Retrieved Chunks (top 5)"):
                    preview = context[:2000] + "..." if len(context) > 2000 else context
                    st.markdown(preview)

                # Generate response
                try:
                    for chunk in generate_response(rag_prompt, gen_model, tokenizer, high_load):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    message_placeholder.markdown(full_response)
                except Exception as e:
                    st.error(f"Generation failed: {e}")
                    full_response = "❌ Generation error"
                    message_placeholder.markdown(full_response)

                # Validate response
                validation = validate_response(full_response, context, prompt)
                audit_entry = auditor.log_query(prompt, results, full_response,
                                               model_used=GEN_MODEL_MLX if gen_model else FALLBACK_GEN_OLLAMA)

                # Quality dashboard
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    color = "🟢" if validation["grounded"] else "🟡"
                    st.metric("Grounded", color, delta=f"{validation['confidence']:.0%}")
                with col2:
                    st.metric("Sources Used", len(results["documents"][0]))
                with col3:
                    st.metric("Response Length", len(full_response))
                with col4:
                    st.metric("Audit ID", audit_entry["query_hash"][:8])

                # Show citations
                st.markdown("---")
                st.markdown("**📋 Citations:**")
                for i, meta in enumerate(results["metadatas"][0], 1):
                    page = meta.get('page', '?')
                    source = meta.get('source', 'unknown')
                    st.markdown(f"{i}. **{source}** (Page {page})")

                # Validation warnings
                if validation["issues"]:
                    st.warning("⚠️ **Validation Notes:**")
                    for issue in validation["issues"]:
                        st.write(issue)

        st.session_state.messages.append({"role": "assistant", "content": full_response})

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"❌ App crashed: {e}")
        st.info("Troubleshooting: Check ollama serve is running + models pulled")