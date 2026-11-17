"""
RAG Pipeline Coordinator.
Unites Semantic Retrieval, Prompt Assembly, LLM Generation, and Traceability.
"""

import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from src.llm.factory import LLMFactory
from src.llm.prompts import format_qa_prompt
from src.retrieval.retriever import SemanticRetriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RAGPipeline")


@dataclass
class FAQResponse:
    query: str
    answer: str
    source_url: Optional[str]
    last_updated: str
    is_refusal: bool
    refusal_reason: Optional[str]
    retrieved_chunks_count: int
    execution_time_ms: float
    disclaimer: str = "Facts-only. No investment advice."

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RAGPipeline:
    """End-to-end RAG orchestrator for Mutual Fund scheme facts."""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.retriever = SemanticRetriever(config_path=config_path)
        self.llm = LLMFactory.get_client()

    def run(self, query: str) -> FAQResponse:
        start_time = time.perf_counter()

        logger.info(f"Running RAG pipeline for query: '{query}'")

        # 1. Semantic Retrieval
        retrieval = self.retriever.retrieve(query)

        if not retrieval.has_sufficient_context:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return FAQResponse(
                query=query,
                answer=(
                    "I do not have verified official facts for this specific inquiry within the ingested mutual fund schemes. "
                    "Please refer to the official Groww knowledge portal for further details."
                ),
                source_url="https://groww.in/mutual-funds",
                last_updated="2026-11-01",
                is_refusal=False,
                refusal_reason="insufficient_context",
                retrieved_chunks_count=0,
                execution_time_ms=elapsed_ms,
            )

        # 2. Prompt Formatting
        prompt = format_qa_prompt(query=query, context_text=retrieval.context_text)

        # 3. LLM Generation
        raw_completion = self.llm.generate(prompt)

        # 4. Clean up and format response
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return FAQResponse(
            query=query,
            answer=raw_completion,
            source_url=retrieval.top_url,
            last_updated="2026-11-01",
            is_refusal=False,
            refusal_reason=None,
            retrieved_chunks_count=len(retrieval.chunks),
            execution_time_ms=elapsed_ms,
        )


if __name__ == "__main__":
    pipeline = RAGPipeline()
    sample_queries = [
        "What is the exit load for HDFC Flexi Cap Direct Growth?",
        "What is the lock-in period for HDFC ELSS Tax Saver Fund?",
        "How can I download my capital-gains statement?",
        "What is the expense ratio and riskometer of HDFC Large Cap Fund?",
    ]

    for q in sample_queries:
        print("\n" + "=" * 60)
        print(f"USER: {q}")
        resp = pipeline.run(q)
        print("-" * 60)
        print(f"ASSISTANT:\n{resp.answer}")
        print(f"\n[Latency: {resp.execution_time_ms}ms | Retrieved Chunks: {resp.retrieved_chunks_count} | Source: {resp.source_url}]")

