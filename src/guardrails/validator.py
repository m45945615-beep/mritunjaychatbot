"""
Output Validator — enforces response quality constraints:

1. Sentence count  : answers must be ≤ MAX_SENTENCES (default 3)
2. Source citation : answers must contain at least one URL
3. Disclaimer      : appends a standard advisory disclaimer if missing
"""

import re
from typing import Tuple

MAX_SENTENCES = 3

DISCLAIMER = (
    "\n\n⚠️ *This is factual information only — not investment advice. "
    "Consult a SEBI-registered financial advisor before investing.*"
)

_URL_PATTERN = re.compile(
    r"https?://[^\s\"'>]+"
)

_SENTENCE_SPLITTER = re.compile(r"(?<=[.!?])\s+")


class OutputValidator:
    """Validates and post-processes LLM / synthesiser responses."""

    def __init__(
        self,
        max_sentences: int = MAX_SENTENCES,
        require_source_url: bool = True,
        append_disclaimer: bool = True,
    ) -> None:
        self.max_sentences = max_sentences
        self.require_source_url = require_source_url
        self.append_disclaimer = append_disclaimer

    # ── public API ───────────────────────────────────────────────────────────

    def validate(self, response: str, sources: list[str] | None = None) -> Tuple[bool, str, list[str]]:
        """
        Validate *response* and return (is_valid, processed_response, issues).

        Parameters
        ----------
        response : str
            The answer text from the LLM / synthesiser.
        sources : list[str] | None
            Source URLs already attached to the response (may be empty).

        Returns
        -------
        is_valid : bool
            False only when the response has no source URL at all.
        processed_response : str
            Possibly truncated and disclaimer-appended version of *response*.
        issues : list[str]
            Human-readable list of warnings/fixes applied.
        """
        issues: list[str] = []
        text = response

        # 1. Sentence-count guard
        sentences = _SENTENCE_SPLITTER.split(text.strip())
        if len(sentences) > self.max_sentences:
            text = " ".join(sentences[: self.max_sentences]).rstrip()
            if not text.endswith((".", "!", "?")):
                text += "."
            issues.append(
                f"Response truncated from {len(sentences)} to {self.max_sentences} sentences."
            )

        # 2. Source URL check
        urls_in_body = _URL_PATTERN.findall(text)
        all_urls = urls_in_body + (sources or [])
        if self.require_source_url and not all_urls:
            issues.append("No source URL found in response.")
            is_valid = False
        else:
            is_valid = True

        # 3. Append disclaimer if absent
        if self.append_disclaimer and "not investment advice" not in text.lower():
            text += DISCLAIMER
            issues.append("Disclaimer appended.")

        return is_valid, text, issues

    def sentence_count(self, text: str) -> int:
        """Return the number of sentences in *text*."""
        return len(_SENTENCE_SPLITTER.split(text.strip()))

