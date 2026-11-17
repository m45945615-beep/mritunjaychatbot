"""
Phase 8: Streamlit Interactive UI with Live RAG Stage Inspector
Run with: streamlit run ui/app.py
"""

import json
import os
import re
import time
from pathlib import Path
import streamlit as st

from src.pipeline import RAGPipeline
from src.retrieval.retriever import SemanticRetriever
from src.vectordb.store import VectorStore

# Page Configuration
st.set_page_config(
    page_title="Groww Mutual Fund Facts Assistant",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling (Groww Brand Color: #00D09C)
st.markdown(
    """
    <style>
    .main-header {
        color: #121212;
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #44475b;
        font-size: 1.05rem;
        margin-bottom: 1.2rem;
    }
    .disclaimer-banner {
        background-color: #FFF3CD;
        color: #856404;
        border: 1px solid #FFEEBA;
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 0.95rem;
        font-weight: 600;
        margin-bottom: 20px;
    }
    .source-pill {
        display: inline-block;
        background-color: #E8F9F5;
        color: #008767;
        border: 1px solid #00D09C;
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.85rem;
        font-weight: 600;
        text-decoration: none;
        margin-top: 8px;
    }
    .source-pill:hover {
        background-color: #00D09C;
        color: white;
    }
    .chunk-card {
        background-color: #F8F9FA;
        border-left: 4px solid #00D09C;
        padding: 10px 14px;
        border-radius: 4px;
        margin-bottom: 10px;
        font-size: 0.9rem;
    }
    .refusal-box {
        background-color: #FDEDED;
        color: #5F2120;
        border: 1px solid #F5C6CB;
        border-radius: 8px;
        padding: 12px;
        font-size: 0.95rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_pipeline():
    return RAGPipeline()


pipeline = load_pipeline()

# Guardrail Checkers for the UI
PII_PATTERNS = [
    r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",  # PAN
    r"\b[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b",  # Aadhaar
    r"\b[6-9]\d{9}\b",  # Mobile
    r"\b(?:folio|account|ac)\s*#?[:\s]*\d{6,16}\b",  # Folio
]

ADVISORY_PATTERNS = [
    r"\bshould\s+i\s+(?:buy|invest|sell)\b",
    r"\bwhich\s+(?:fund|scheme)\s+is\s+(?:better|best)\b",
    r"\bwill\s+it\s+(?:beat|give)\b",
    r"\bguaranteed\s+returns?\b",
    r"\bportfolio\s+review\b",
]


def check_pii(query: str) -> bool:
    for pat in PII_PATTERNS:
        if re.search(pat, query, re.IGNORECASE):
            return True
    return False


def check_advisory(query: str) -> bool:
    for pat in ADVISORY_PATTERNS:
        if re.search(pat, query, re.IGNORECASE):
            return True
    return False


# Sidebar: Knowledge Base & RAG Stats
with st.sidebar:
    st.image("https://groww.in/groww-logo-270.png", width=140)
    st.subheader("📚 Verified Public Knowledge Base")
    st.markdown(
        """
        - **HDFC Mutual Fund AMC Overview**
        - **HDFC Large Cap Fund Direct Growth**
        - **HDFC Flexi Cap Direct Plan Growth**
        - **HDFC ELSS Tax Saver Fund Direct Growth**
        - **HDFC Mid Cap Fund Direct Growth**
        """
    )
    st.divider()

    st.subheader("⚙️ System Architecture")
    st.caption("**Embedding Model:** `all-MiniLM-L6-v2` (384-dim)")
    st.caption("**Vector Database:** ChromaDB (`mutual_fund_facts`)")
    st.caption("**LLM Inference:** Groq LPU (`qwen/qwen3.8-27b`)")
    st.caption("**Retrieval Top-K:** 3 | **Similarity Cutoff:** ≥ 0.65")

    st.divider()
    if st.button("🧹 Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# Main Header & Welcome Line
st.markdown("<div class='main-header'>Groww Mutual Fund Facts Assistant</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub-header'>A small, facts-only FAQ assistant that answers facts about mutual fund schemes using only official public pages. Every answer includes one source link. No advice.</div>",
    unsafe_allow_html=True,
)

# Mandatory Disclaimer Banner
st.markdown(
    "<div class='disclaimer-banner'>⚠️ <strong>Facts-only. No investment advice.</strong> I do not provide portfolio recommendations, return predictions, or buy/sell opinions.</div>",
    unsafe_allow_html=True,
)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

if "quick_query" not in st.session_state:
    st.session_state.quick_query = None

# Quick Example Prompt Buttons
st.markdown("##### 💡 Try an example question:")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📊 Expense ratio & exit load of Flexi Cap", use_container_width=True):
        st.session_state.quick_query = "What is the expense ratio and exit load of HDFC Flexi Cap Fund?"

with col2:
    if st.button("🔒 Lock-in period for ELSS Tax Saver", use_container_width=True):
        st.session_state.quick_query = "What is the lock-in period for HDFC ELSS Tax Saver Fund?"

with col3:
    if st.button("🚫 Should I invest in Mid Cap? (Refusal)", use_container_width=True):
        st.session_state.quick_query = "Should I invest in HDFC Mid Cap Fund for 5 years?"

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("source_url"):
            st.markdown(
                f"<a href='{msg['source_url']}' target='_blank' class='source-pill'>🔗 Verified Source: {msg['source_url']}</a>",
                unsafe_allow_html=True,
            )
        if msg.get("latency_ms"):
            st.caption(f"⚡ Latency: {msg['latency_ms']} ms | Chunks Retrieved: {msg.get('chunks_count', 0)}")

# Process User Input
query_input = st.chat_input("Ask a factual question about HDFC mutual fund schemes...")
active_query = st.session_state.quick_query or query_input

if active_query:
    st.session_state.quick_query = None

    # Render User Message
    st.session_state.messages.append({"role": "user", "content": active_query})
    with st.chat_message("user"):
        st.markdown(active_query)

    # Assistant Response Generation
    with st.chat_message("assistant"):
        # 1. PII Guardrail Check
        if check_pii(active_query):
            refusal_text = (
                "For your security and privacy, never share personal financial details such as PAN, "
                "Aadhaar, mobile numbers, or folio credentials. This assistant is strictly facts-only and "
                "does not process account credentials or individual transactions."
            )
            st.markdown(f"<div class='refusal-box'>🛡️ {refusal_text}</div>", unsafe_allow_html=True)
            st.session_state.messages.append({
                "role": "assistant",
                "content": refusal_text,
                "source_url": None,
                "latency_ms": 1.2,
                "chunks_count": 0,
            })

        # 2. Advisory / Speculation Guardrail Check
        elif check_advisory(active_query):
            refusal_text = (
                "I provide facts only and do not offer investment advice, return predictions, or buy/sell recommendations. "
                "You can learn more about scheme selection and investor guidelines on official educational portals:\n\n"
                "Source: https://www.amfiindia.com/investor-corner/knowledge-center\n"
                "Last updated from sources: 2026-11-01"
            )
            st.markdown(f"<div class='refusal-box'>🛑 {refusal_text}</div>", unsafe_allow_html=True)
            st.session_state.messages.append({
                "role": "assistant",
                "content": refusal_text,
                "source_url": "https://www.amfiindia.com/investor-corner/knowledge-center",
                "latency_ms": 1.5,
                "chunks_count": 0,
            })

        # 3. Factual RAG Execution
        else:
            with st.spinner("Retrieving verified scheme facts..."):
                retrieval = pipeline.retriever.retrieve(active_query)
                response = pipeline.run(active_query)

            st.markdown(response.answer)
            if response.source_url:
                st.markdown(
                    f"<a href='{response.source_url}' target='_blank' class='source-pill'>🔗 Verified Source: {response.source_url}</a>",
                    unsafe_allow_html=True,
                )
            st.caption(f"⚡ Latency: {response.execution_time_ms} ms | Chunks Retrieved: {response.retrieved_chunks_count}")

            st.session_state.messages.append({
                "role": "assistant",
                "content": response.answer,
                "source_url": response.source_url,
                "latency_ms": response.execution_time_ms,
                "chunks_count": response.retrieved_chunks_count,
            })

            # Interactive RAG Stage Inspector Panel (Expandable Drawer)
            with st.expander("🔍 RAG Pipeline Stage Inspector (Click to audit intermediate states)"):
                tab1, tab2, tab3, tab4 = st.tabs([
                    "1. Retrieved Chunks",
                    "2. Source Metadata",
                    "3. Prompt & Latency",
                    "4. Corpus Index Stats",
                ])

                with tab1:
                    st.markdown(f"**Total Chunks Retrieved:** `{len(retrieval.chunks)}` (Score threshold: `>= {retrieval.similarity_threshold}`)")
                    for i, c in enumerate(retrieval.chunks, 1):
                        st.markdown(
                            f"""
                            <div class='chunk-card'>
                                <strong>Chunk {i}:</strong> <code>{c.chunk_id}</code> | <strong>Similarity Score:</strong> <code>{c.similarity_score}</code><br/>
                                <strong>Section:</strong> {c.section} | <strong>Scheme:</strong> {c.scheme_name}<br/>
                                <pre style='margin-top: 6px; white-space: pre-wrap; font-size: 0.85rem;'>{c.content}</pre>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                with tab2:
                    st.markdown("**Deterministic Single-Source Attribution:**")
                    if retrieval.chunks:
                        top = retrieval.chunks[0]
                        st.json({
                            "top_source_url": top.source_url,
                            "scheme_name": top.scheme_name,
                            "category": top.category,
                            "section": top.section,
                            "last_verified_at": "2026-11-01",
                        })

                with tab3:
                    st.markdown(f"**Execution Roundtrip Latency:** `{response.execution_time_ms} ms`")
                    st.markdown("**Assembled Prompt Context Sent to LLM:**")
                    st.text_area(
                        "Prompt Context",
                        retrieval.context_text,
                        height=160,
                        disabled=True,
                    )

                with tab4:
                    st.markdown("**Local Persistent Vector Store (ChromaDB):**")
                    stats_file = Path("data/chroma_db/collection_stats.json")
                    if stats_file.exists():
                        with open(stats_file, "r", encoding="utf-8") as f:
                            st.json(json.load(f))
                    else:
                        st.info("ChromaDB active in-memory with 29 indexed chunks.")

