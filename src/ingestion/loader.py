"""
Phase 3: Data Loading & Normalization Module
Loads persisted raw documents from data/raw_scraped/, cleans and normalizes content,
validates mandatory metadata, and produces standardized Document objects.
Persists normalized output to data/loaded_docs/loaded_documents.json for inspection.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DocumentLoader")


@dataclass
class Document:
    """Standardized document representation across the RAG pipeline."""
    doc_id: str
    scheme_name: str
    category: str
    source_url: str
    last_scraped_at: str
    clean_text: str
    key_metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        return cls(
            doc_id=data["doc_id"],
            scheme_name=data["scheme_name"],
            category=data["category"],
            source_url=data["source_url"],
            last_scraped_at=data.get("last_scraped_at", "2026-11-01"),
            clean_text=data["clean_text"],
            key_metrics=data.get("key_metrics", {}),
            metadata=data.get("metadata", {}),
        )


class DocumentLoader:
    """Loads and normalizes raw scraped JSON files into structured Document objects."""

    def __init__(
        self,
        raw_dir: str = "data/raw_scraped",
        output_path: str = "data/loaded_docs/loaded_documents.json",
    ):
        self.raw_dir = Path(raw_dir)
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def normalize_document_text(self, raw_data: Dict[str, Any]) -> str:
        """Transforms raw sections and key metrics into clean, structured Markdown."""
        scheme_name = raw_data.get("scheme_name", "Mutual Fund Scheme")
        category = raw_data.get("category", "Equity")
        source_url = raw_data.get("source_url", "")
        key_metrics = raw_data.get("key_metrics", {})
        parsed_sections = raw_data.get("parsed_sections", {})

        blocks = []
        # Title & Category Header
        blocks.append(f"# {scheme_name}")
        blocks.append(f"**Category:** {category} | **Source:** {source_url}\n")

        # Key Facts Table / Metric Section
        if key_metrics:
            blocks.append("## Key Scheme Facts & Metrics")
            for metric, val in key_metrics.items():
                metric_title = metric.replace("_", " ").title()
                blocks.append(f"- **{metric_title}:** {val}")
            blocks.append("")

        # Narrative Sections with standard Markdown headings
        for section_title, section_content in parsed_sections.items():
            blocks.append(f"## {section_title}")
            blocks.append(f"{section_content}\n")

        # Official Source Verification Footer
        blocks.append(f"Official Source Link: {source_url}")

        return "\n".join(blocks).strip()

    def load(self) -> List[Document]:
        """Loads all JSON files in raw_dir, validates metadata, and persists normalized documents."""
        if not self.raw_dir.exists():
            raise FileNotFoundError(f"Raw data directory does not exist: {self.raw_dir}")

        json_files = sorted(list(self.raw_dir.glob("*.json")))
        if not json_files:
            logger.warning(f"No JSON files found in {self.raw_dir}")
            return []

        documents: List[Document] = []
        logger.info(f"Loading {len(json_files)} raw files from {self.raw_dir}...")

        for file_path in json_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Validation of mandatory fields
                doc_id = data.get("slug") or file_path.stem
                scheme_name = data.get("scheme_name")
                source_url = data.get("source_url")

                if not scheme_name or not source_url:
                    logger.warning(f"Skipping {file_path.name}: missing scheme_name or source_url")
                    continue

                clean_text = self.normalize_document_text(data)

                doc = Document(
                    doc_id=doc_id,
                    scheme_name=scheme_name,
                    category=data.get("category", "Mutual Funds"),
                    source_url=source_url,
                    last_scraped_at=data.get("scraped_at", "2026-11-01"),
                    clean_text=clean_text,
                    key_metrics=data.get("key_metrics", {}),
                    metadata={
                        "slug": doc_id,
                        "raw_file": file_path.name,
                        "section_count": len(data.get("parsed_sections", {})),
                    },
                )
                documents.append(doc)
                logger.info(f"Loaded document: {doc_id} ({scheme_name})")

            except Exception as e:
                logger.error(f"Error loading {file_path.name}: {e}")

        # Persist loaded documents for intermediate inspection
        serialized = [doc.to_dict() for doc in documents]
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Successfully normalized and saved {len(documents)} documents to {self.output_path}"
        )
        return documents


if __name__ == "__main__":
    loader = DocumentLoader()
    docs = loader.load()
    print(f"\n--- DocumentLoader Summary ---")
    print(f"Total documents loaded: {len(docs)}")
    for d in docs:
        print(f" - [{d.doc_id}] {d.scheme_name} (Length: {len(d.clean_text)} chars)")

