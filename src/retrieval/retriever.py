"""
Phase 7: Semantic Retrieval Engine Module
Performs Top-K similarity retrieval against ChromaDB / VectorStore.
Enforces similarity score thresholds (default >= 0.65).
Provides scheme-specific intent filtering and ranking.
Logs runtime retrieval traces to data/retrieval_logs/session_traces.jsonl for auditability.
"""

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.vectordb.store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Retriever")


@dataclass
class RetrievedChunk:
    chunk_id: str
    content: str
    scheme_name: str
    category: str
    section: str
    source_url: str
    similarity_score: float
    cosine_distance: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievalResult:
    query: str
    chunks: List[RetrievedChunk]
    top_url: Optional[str]
    has_sufficient_context: bool
    similarity_threshold: float
    execution_time_ms: float
    context_text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "chunks": [c.to_dict() for c in self.chunks],
            "top_url": self.top_url,
            "has_sufficient_context": self.has_sufficient_context,
            "similarity_threshold": self.similarity_threshold,
            "execution_time_ms": self.execution_time_ms,
            "context_text": self.context_text,
        }


class SemanticRetriever:
    """
    Retrieves the most semantically relevant chunks for a user query.
    Applies score cutoffs, scheme-aware routing, and persists execution traces.
    """

    SCHEME_KEYWORDS = {
        "large cap": "HDFC Large Cap Fund Direct Growth",
        "flexi cap": "HDFC Flexi Cap Direct Plan Growth",
        "equity fund": "HDFC Flexi Cap Direct Plan Growth",
        "elss": "HDFC ELSS Tax Saver Fund Direct Plan Growth",
        "tax saver": "HDFC ELSS Tax Saver Fund Direct Plan Growth",
        "80c": "HDFC ELSS Tax Saver Fund Direct Plan Growth",
        "mid cap": "HDFC Mid Cap Fund Direct Growth",
        "midcap": "HDFC Mid Cap Fund Direct Growth",
        "statement": "HDFC Mutual Fund AMC Overview",
        "capital gains": "HDFC Mutual Fund AMC Overview",
        "amc": "HDFC Mutual Fund AMC Overview",
    }

    def __init__(
        self,
        config_path: str = "config/config.yaml",
        traces_log_path: str = "data/retrieval_logs/session_traces.jsonl",
    ):
        self.config_path = Path(config_path)
        self.traces_log_path = Path(traces_log_path)
        self.traces_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.config = self._load_config()

        self.top_k = self.config.get("vectordb", {}).get("top_k", 3)
        self.similarity_threshold = self.config.get("vectordb", {}).get("similarity_threshold", 0.65)

        self.vector_store = VectorStore(config_path=config_path)

    def _load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                import yaml
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass
        return {}

    def _detect_scheme_target(self, query: str) -> Optional[str]:
        q_lower = query.lower()
        for kw, scheme_name in self.SCHEME_KEYWORDS.items():
            if kw in q_lower:
                return scheme_name
        return None

    def retrieve(self, query: str, top_k: Optional[int] = None) -> RetrievalResult:
        """Retrieves top-K chunks for query, applies thresholding, and returns structured result."""
        start_time = time.perf_counter()
        k = top_k or self.top_k

        # Check for scheme-specific intent
        target_scheme = self._detect_scheme_target(query)
        where_filter = {"scheme_name": target_scheme} if target_scheme else None

        # Execute vector similarity query
        raw_results = self.vector_store.query(query, top_k=k, where=where_filter)

        retrieved_chunks: List[RetrievedChunk] = []
        ids = raw_results.get("ids", [[]])[0]
        docs = raw_results.get("documents", [[]])[0]
        metas = raw_results.get("metadatas", [[]])[0]
        dists = raw_results.get("distances", [[]])[0]
        sims = raw_results.get("similarities", [[]])[0]

        for chunk_id, doc, meta, dist, sim in zip(ids, docs, metas, dists, sims):
            # Check against similarity threshold
            if sim >= self.similarity_threshold:
                retrieved_chunks.append(
                    RetrievedChunk(
                        chunk_id=chunk_id,
                        content=doc,
                        scheme_name=meta.get("scheme_name", ""),
                        category=meta.get("category", ""),
                        section=meta.get("section", ""),
                        source_url=meta.get("source_url", ""),
                        similarity_score=round(sim, 4),
                        cosine_distance=round(dist, 4),
                    )
                )

        # Fallback: If filtered list is empty, relax threshold for top 1 best hit if distance < 0.5
        if not retrieved_chunks and ids:
            top_sim = sims[0]
            if top_sim >= 0.50:
                retrieved_chunks.append(
                    RetrievedChunk(
                        chunk_id=ids[0],
                        content=docs[0],
                        scheme_name=metas[0].get("scheme_name", ""),
                        category=metas[0].get("category", ""),
                        section=metas[0].get("section", ""),
                        source_url=metas[0].get("source_url", ""),
                        similarity_score=round(top_sim, 4),
                        cosine_distance=round(dists[0], 4),
                    )
                )

        has_context = len(retrieved_chunks) > 0
        top_url = retrieved_chunks[0].source_url if has_context else None

        # Assemble clean context string
        context_parts = []
        for i, c in enumerate(retrieved_chunks, 1):
            context_parts.append(f"--- Context Snippet {i} ({c.scheme_name} | {c.section}) ---\n{c.content}\n")
        context_text = "\n".join(context_parts).strip()

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        result = RetrievalResult(
            query=query,
            chunks=retrieved_chunks,
            top_url=top_url,
            has_sufficient_context=has_context,
            similarity_threshold=self.similarity_threshold,
            execution_time_ms=elapsed_ms,
            context_text=context_text,
        )

        # Log trace to disk for transparency and auditability
        self._log_trace(result)
        return result

    def _log_trace(self, result: RetrievalResult):
        """Appends retrieval trace to session_traces.jsonl."""
        try:
            trace_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "query": result.query,
                "hits_count": len(result.chunks),
                "top_score": result.chunks[0].similarity_score if result.chunks else None,
                "top_url": result.top_url,
                "latency_ms": result.execution_time_ms,
                "chunk_ids": [c.chunk_id for c in result.chunks],
            }
            with open(self.traces_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace_entry, ensure_ascii=False) + "\n")
        except PermissionError:
            # File system is read-only in sandbox; trace preserved in memory/result object
            pass
        except Exception as e:
            logger.debug(f"Could not log trace to {self.traces_log_path}: {e}")


if __name__ == "__main__":
    retriever = SemanticRetriever()
    test_queries = [
        "What is the exit load for HDFC Flexi Cap Direct Plan?",
        "What is the lock-in period for HDFC ELSS Tax Saver Fund?",
        "How do I download my mutual fund capital gains statement on Groww?",
        "What is the expense ratio and minimum SIP for HDFC Mid Cap?",
    ]

    for q in test_queries:
        res = retriever.retrieve(q)
        print(f"\n==================================================")
        print(f"QUERY: {res.query}")
        print(f"Sufficient Context: {res.has_sufficient_context} | Latency: {res.execution_time_ms}ms")
        print(f"Top Source URL: {res.top_url}")
        print(f"Retrieved Chunks ({len(res.chunks)}):")
        for chunk in res.chunks:
            print(f" - [{chunk.chunk_id}] (Score: {chunk.similarity_score}) | {chunk.section}")

