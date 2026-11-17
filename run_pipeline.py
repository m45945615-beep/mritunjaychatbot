#!/usr/bin/env python3
"""
run_pipeline.py — CLI entry-point for the Groww Mutual Fund FAQ RAG pipeline.

Usage
-----
  python run_pipeline.py --stage all          # run full pipeline end-to-end
  python run_pipeline.py --stage ingest       # scrape sources
  python run_pipeline.py --stage load         # load scraped JSON → Document objects
  python run_pipeline.py --stage chunk        # chunk documents
  python run_pipeline.py --stage index        # embed + upsert into vector DB
  python run_pipeline.py --stage retrieve     # interactive retrieval REPL
  python run_pipeline.py --stage ui           # start standalone HTTP UI server
  python run_pipeline.py --query "..."        # one-shot query (no --stage needed)
"""

import argparse
import json
import os
import sys

# ── ensure src/ is on the path regardless of cwd ────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


# ── helpers ──────────────────────────────────────────────────────────────────

def _banner(stage: str) -> None:
    print(f"\n{'='*60}")
    print(f"  Stage: {stage.upper()}")
    print(f"{'='*60}")


def stage_ingest() -> None:
    _banner("ingest (scrape)")
    from src.ingestion.scraper import MutualFundScraper
    config_path = os.path.join(ROOT, "config", "sources.json")
    out_dir = os.path.join(ROOT, "data", "raw_scraped")
    scraper = MutualFundScraper(config_path=config_path, output_dir=out_dir)
    results = scraper.scrape_all()
    print(f"  Scraped {len(results)} sources → {out_dir}")


def stage_load() -> None:
    _banner("load")
    from src.ingestion.loader import DocumentLoader
    raw_dir = os.path.join(ROOT, "data", "raw_scraped")
    out_path = os.path.join(ROOT, "data", "loaded_docs", "loaded_documents.json")
    loader = DocumentLoader(raw_dir=raw_dir, output_path=out_path)
    docs = loader.load_all()
    print(f"  Loaded {len(docs)} documents → {out_path}")


def stage_chunk() -> None:
    _banner("chunk")
    from src.chunking.chunker import SectionAwareChunker
    docs_path = os.path.join(ROOT, "data", "loaded_docs", "loaded_documents.json")
    out_path = os.path.join(ROOT, "data", "chunks", "chunks.json")
    with open(docs_path, encoding="utf-8") as f:
        docs = json.load(f)
    chunker = SectionAwareChunker()
    chunks = chunker.chunk_documents(docs)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        print(f"  Created {len(chunks)} chunks → {out_path}")
    except PermissionError:
        print(f"  [WARN] Cannot write to {out_path} (permission denied) — {len(chunks)} chunks in memory only.")


def stage_index() -> None:
    _banner("index (embed + upsert)")
    from src.vectordb.store import VectorStore
    store = VectorStore()
    store.load_and_index()
    stats = store.stats()
    print(f"  Vector DB stats: {stats}")


def stage_retrieve() -> None:
    _banner("retrieve (interactive REPL)")
    from src.retrieval.retriever import SemanticRetriever
    retriever = SemanticRetriever()
    print("  Type a query (or 'quit' to exit):")
    while True:
        try:
            query = input("\n  Query> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if query.lower() in ("quit", "exit", "q"):
            break
        if not query:
            continue
        results = retriever.retrieve(query)
        if not results:
            print("  No results found.")
        for i, r in enumerate(results, 1):
            print(f"\n  [{i}] score={r.get('score', 0):.3f}  source={r.get('metadata', {}).get('source_url', 'N/A')}")
            print(f"      {r.get('text', '')[:200]}...")


def stage_ui() -> None:
    _banner("UI server")
    ui_path = os.path.join(ROOT, "ui", "server.py")
    print(f"  Starting server from {ui_path}")
    import subprocess
    subprocess.run([sys.executable, ui_path], check=True)


def one_shot_query(query: str) -> None:
    _banner(f"query: {query[:60]}")
    from src.guardrails.advisory_filter import AdvisoryFilter
    from src.guardrails.pii_sanitizer import PIISanitizer
    from src.pipeline import RAGPipeline

    pii = PIISanitizer()
    adv = AdvisoryFilter()

    had_pii, clean_query, pii_types = pii.check_and_redact(query)
    if had_pii:
        print(f"  [GUARDRAIL] PII detected & redacted: {pii_types}")

    blocked, msg = adv.check(clean_query)
    if blocked:
        print(f"  [GUARDRAIL] Advisory query blocked.\n  {msg}")
        return

    pipeline = RAGPipeline()
    response = pipeline.run(clean_query)
    print(f"\n  Answer : {response.answer}")
    print(f"  Sources: {response.sources}")
    print(f"  Stage  : {response.retrieval_stage}")


# ── main ─────────────────────────────────────────────────────────────────────

STAGES = {
    "ingest": stage_ingest,
    "load": stage_load,
    "chunk": stage_chunk,
    "index": stage_index,
    "retrieve": stage_retrieve,
    "ui": stage_ui,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Groww Mutual Fund FAQ RAG — pipeline runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--stage",
        choices=list(STAGES.keys()) + ["all"],
        help="Pipeline stage to run",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Run a one-shot query against the full pipeline",
    )
    args = parser.parse_args()

    if args.query:
        one_shot_query(args.query)
        return

    if not args.stage:
        parser.print_help()
        return

    if args.stage == "all":
        for name, fn in STAGES.items():
            if name == "ui":
                continue  # don't auto-start UI in 'all' mode
            fn()
        print("\n  Pipeline complete. Run --stage ui to start the server.")
    else:
        STAGES[args.stage]()


if __name__ == "__main__":
    main()

