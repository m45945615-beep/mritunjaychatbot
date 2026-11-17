# Groww Mutual Fund FAQ RAG Assistant

> A fully-offline-capable Retrieval-Augmented Generation (RAG) system that answers factual questions about HDFC AMC mutual funds from official Groww product pages.

---

## Project Layout

```
c:\builder\
├── config/
│   ├── config.yaml          # Chunk size, model, retrieval thresholds
│   └── sources.json         # Exactly 5 official URLs to scrape
├── data/
│   ├── raw_scraped/         # Phase 2 output — one JSON per URL
│   ├── loaded_docs/         # Phase 3 output — normalised Document objects
│   ├── chunks/              # Phase 4 output — 29 text chunks
│   ├── embeddings/          # Phase 5 output — embedding summaries
│   ├── chroma_db/           # Phase 6 output — vector store (JSON-backed mock)
│   └── retrieval_logs/      # Phase 7 output — session traces (JSONL)
├── src/
│   ├── ingestion/           # scraper.py, loader.py
│   ├── chunking/            # chunker.py (SectionAwareChunker)
│   ├── embeddings/          # embedder.py (MiniLM / deterministic fallback)
│   ├── vectordb/            # store.py (ChromaDB / JSON mock)
│   ├── retrieval/           # retriever.py (SemanticRetriever, cosine sim)
│   ├── llm/                 # groq_client.py, factory.py, prompts.py
│   ├── guardrails/          # pii_sanitizer.py, advisory_filter.py, validator.py
│   └── pipeline.py          # RAGPipeline — orchestrates all stages
├── ui/
│   ├── app.py               # Streamlit UI (requires `pip install streamlit`)
│   └── server.py            # Zero-dependency stdlib HTTP server (recommended)
├── tests/
│   ├── test_retrieval.py
│   └── test_guardrails.py
├── run_pipeline.py          # CLI entry-point
├── .env                     # Your API keys (never commit this)
├── .env.example             # Template — copy to .env
├── requirements.txt
└── Docs/
    ├── PRD.md
    ├── architecture.md
    ├── implementation.md
    └── sample_qa.md
```

---

## Quick Start

### 1 — Set your Groq API key

Open `.env` and replace the placeholder:

```env
GROQ_API_KEY=gsk_your_actual_key_here
```

Get a free key at <https://console.groq.com/keys>.

### 2 — Install dependencies (optional — has offline fallbacks)

```powershell
pip install httpx beautifulsoup4 pyyaml sentence-transformers chromadb groq streamlit pytest python-dotenv
```

The system works without any of these — it uses deterministic embeddings and an in-memory JSON store.

### 3 — Run the pipeline

```powershell
# Full end-to-end (skips UI)
python run_pipeline.py --stage all

# Individual stages
python run_pipeline.py --stage ingest    # re-scrape the 5 source URLs
python run_pipeline.py --stage load      # normalise scraped JSON → Documents
python run_pipeline.py --stage chunk     # split into ~29 chunks
python run_pipeline.py --stage index     # embed + upsert into vector DB
python run_pipeline.py --stage retrieve  # interactive retrieval REPL

# One-shot query
python run_pipeline.py --query "What is the expense ratio of HDFC ELSS fund?"

# Start the web UI
python run_pipeline.py --stage ui
# Then open http://localhost:8080 in your browser
```

---

## Guardrails

| Guardrail | Trigger | Action |
|---|---|---|
| PII Sanitizer | PAN / Aadhaar / Phone / Email in query | Redact before sending to LLM |
| Advisory Filter | "Should I invest…", "expected returns…" | Refuse + standard disclaimer |
| Output Validator | Response > 3 sentences | Truncate to 3 sentences |
| Output Validator | No source URL in response | Flag as invalid |
| Output Validator | Missing disclaimer | Append disclaimer |

---

## Sources

Only the following **5 official URLs** are scraped — no internal link crawling:

| # | Source |
|---|---|
| 1 | `https://groww.in/mutual-funds/hdfc-amc-mutual-fund` |
| 2 | `https://groww.in/mutual-funds/hdfc-top-100-fund-direct-plan-growth-option` |
| 3 | `https://groww.in/mutual-funds/hdfc-flexi-cap-fund-direct-growth` |
| 4 | `https://groww.in/mutual-funds/hdfc-elss-tax-saver-direct-growth` |
| 5 | `https://groww.in/mutual-funds/hdfc-mid-cap-opportunities-fund-direct-growth` |

---

## Constraints & Limitations

- **No investment advice** — the system strictly refuses advisory / predictive queries.
- **Facts only** — answers are limited to ≤ 3 sentences with a source URL.
- **No PII storage** — all PII is redacted before processing.
- **Offline fallback** — works without network or Groq API key (extractive synthesis).
- **Static corpus** — re-run `--stage ingest` to refresh data from source pages.
- **5 sources only** — no third-party blogs, no crawled internal links.

---

## Running Tests

```powershell
# Retrieval tests
python tests/test_retrieval.py

# Guardrails tests (TC-01 → TC-09)
python tests/test_guardrails.py

# With pytest (if installed)
python -m pytest tests/ -v
```

---

## Architecture

See [`Docs/architecture.md`](Docs/architecture.md) for the full system diagram.

```
User Query
   │
   ▼
[Guardrails: PII + Advisory]
   │
   ▼
[SemanticRetriever] ──► [VectorStore (ChromaDB / JSON mock)]
   │                          │
   │                   [SentenceTransformer / deterministic]
   ▼
[RAGPipeline]
   │
   ▼
[LLM: Groq / extractive fallback]
   │
   ▼
[OutputValidator: ≤3 sentences + disclaimer]
   │
   ▼
UI (Streamlit / stdlib HTTP server)
```

---

## Disclaimer

> This tool provides factual information extracted from official Groww product pages.
> It does **not** constitute investment advice. Past performance is not indicative of future results.
> Please consult a SEBI-registered financial advisor before making any investment decisions.

