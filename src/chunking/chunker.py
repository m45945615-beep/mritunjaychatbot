"""
Phase 4: Domain-Aware Document Chunking Module
Implements section-aware Markdown chunking.
Preserves financial tabular facts and metric integrity.
Injects canonical scheme context into every chunk for high-precision retrieval.
Persists intermediate chunks to data/chunks/chunks.json.
"""

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Chunker")


@dataclass
class TextChunk:
    """Represents a discrete semantic chunk with rich metadata and injected context."""
    chunk_id: str
    scheme_name: str
    category: str
    section: str
    source_url: str
    last_scraped_at: str
    content: str
    token_estimate: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextChunk":
        return cls(**data)


class SectionAwareChunker:
    """
    Splits loaded documents along section boundaries, keeping related financial facts together.
    Injects [SCHEME: ... | CATEGORY: ... | SECTION: ... | SOURCE: ...] header into every chunk.
    """

    def __init__(
        self,
        loaded_docs_path: str = "data/loaded_docs/loaded_documents.json",
        output_chunks_path: str = "data/chunks/chunks.json",
        target_tokens: int = 350,
        overlap_tokens: int = 50,
    ):
        self.loaded_docs_path = Path(loaded_docs_path)
        self.output_chunks_path = Path(output_chunks_path)
        self.output_chunks_path.parent.mkdir(parents=True, exist_ok=True)
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens

    def estimate_tokens(self, text: str) -> int:
        """Rough token count estimation (~4 characters per token for English)."""
        return max(1, len(text.split()))

    def chunk_document(self, doc_data: Dict[str, Any]) -> List[TextChunk]:
        """Splits a single document into section-aware chunks with injected context."""
        doc_id = doc_data.get("doc_id", "scheme")
        scheme_name = doc_data.get("scheme_name", "Mutual Fund")
        category = doc_data.get("category", "Mutual Funds")
        source_url = doc_data.get("source_url", "")
        last_scraped_at = doc_data.get("last_scraped_at", "2026-11-01")
        clean_text = doc_data.get("clean_text", "")

        chunks: List[TextChunk] = []

        # Split along markdown section headers (## )
        raw_sections = re.split(r"\n(?=##\s+)", clean_text)
        section_idx = 1

        for raw_sec in raw_sections:
            sec_text = raw_sec.strip()
            if not sec_text:
                continue

            # Extract section title if present
            header_match = re.match(r"^##\s+(.+)$", sec_text, re.MULTILINE)
            if header_match:
                section_title = header_match.group(1).strip()
            elif sec_text.startswith("# "):
                section_title = "Overview & Introduction"
            else:
                section_title = f"Section {section_idx}"

            # Create clean slug for chunk_id
            clean_sec_slug = re.sub(r"[^a-zA-Z0-9]+", "_", section_title.lower()).strip("_")
            chunk_id = f"{doc_id}_{clean_sec_slug}_{section_idx:02d}"

            # Context Header Injection
            context_header = (
                f"[SCHEME: {scheme_name} | CATEGORY: {category} | "
                f"SECTION: {section_title} | SOURCE: {source_url}]"
            )

            # Combine header with section content
            full_chunk_text = f"{context_header}\n{sec_text}"
            token_count = self.estimate_tokens(full_chunk_text)

            chunk = TextChunk(
                chunk_id=chunk_id,
                scheme_name=scheme_name,
                category=category,
                section=section_title,
                source_url=source_url,
                last_scraped_at=last_scraped_at,
                content=full_chunk_text,
                token_estimate=token_count,
            )
            chunks.append(chunk)
            section_idx += 1

        return chunks

    def process_all(self) -> List[TextChunk]:
        """Loads all documents and produces the full chunk list, persisting to chunks.json."""
        if not self.loaded_docs_path.exists():
            raise FileNotFoundError(f"Loaded documents not found at {self.loaded_docs_path}")

        with open(self.loaded_docs_path, "r", encoding="utf-8") as f:
            docs = json.load(f)

        logger.info(f"Chunking {len(docs)} documents from {self.loaded_docs_path}...")
        all_chunks: List[TextChunk] = []

        for doc in docs:
            doc_chunks = self.chunk_document(doc)
            all_chunks.extend(doc_chunks)
            logger.info(f"Generated {len(doc_chunks)} chunks for: {doc.get('scheme_name')}")

        # Persist chunks to JSON for stage inspection
        serialized = [c.to_dict() for c in all_chunks]
        with open(self.output_chunks_path, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Successfully saved {len(all_chunks)} chunks to {self.output_chunks_path}"
        )
        return all_chunks


if __name__ == "__main__":
    chunker = SectionAwareChunker()
    chunks = chunker.process_all()
    print(f"\n--- SectionAwareChunker Summary ---")
    print(f"Total chunks created: {len(chunks)}")
    for c in chunks:
        print(f" - [{c.chunk_id}] {c.section} (~{c.token_estimate} tokens)")

