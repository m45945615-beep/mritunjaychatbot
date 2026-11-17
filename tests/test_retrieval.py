"""
Automated Unit Tests for Vector DB Indexing and Semantic Retrieval.
"""

import sys
import os

# Ensure repo root is on sys.path and is the working directory
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
os.chdir(ROOT)  # data/ paths are relative to repo root

import json
from pathlib import Path
from src.vectordb.store import VectorStore
from src.retrieval.retriever import SemanticRetriever


def test_all_chunks_present_in_vector_db():
    chunks_path = Path("data/chunks/chunks.json")
    assert chunks_path.exists(), "chunks.json must exist"

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    vdb = VectorStore()
    assert vdb.count() == len(chunks), f"Expected {len(chunks)} chunks in Vector DB, found {vdb.count()}"

    for c in chunks:
        cid = c["chunk_id"]
        assert cid in vdb.collection._records, f"Chunk {cid} missing from Vector DB"


def test_elss_lock_in_retrieval():
    retriever = SemanticRetriever()
    res = retriever.retrieve("What is the lock-in period for HDFC ELSS Tax Saver Fund?")
    assert res.has_sufficient_context is True
    assert len(res.chunks) >= 1
    top_hit = res.chunks[0]
    assert "elss" in top_hit.scheme_name.lower()
    assert "lock" in top_hit.section.lower()
    assert "hdfc-elss-tax-saver" in top_hit.source_url


def test_statement_download_retrieval():
    retriever = SemanticRetriever()
    res = retriever.retrieve("How do I download my mutual fund capital gains statement?")
    assert res.has_sufficient_context is True
    assert len(res.chunks) >= 1
    top_hit = res.chunks[0]
    assert "statement" in top_hit.section.lower()
    assert "hdfc-mutual-funds" in top_hit.source_url


def test_flexi_cap_exit_load_retrieval():
    retriever = SemanticRetriever()
    res = retriever.retrieve("What is the exit load for HDFC Flexi Cap Direct Growth?")
    assert res.has_sufficient_context is True
    top_hit = res.chunks[0]
    assert "flexi cap" in top_hit.scheme_name.lower()
    assert "exit load" in top_hit.section.lower()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {passed + failed} tests.")

