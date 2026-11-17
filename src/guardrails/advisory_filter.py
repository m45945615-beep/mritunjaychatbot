"""
Advisory Filter — detects queries that solicit investment advice or predictions.

Any query matching the ADVISORY_PATTERNS list is refused with a standard
disclaimer; the RAG pipeline is never invoked for such queries.
"""

import re
from typing import Tuple

# Phrases that indicate the user is asking for financial advice / predictions.
ADVISORY_PATTERNS: list[str] = [
    r"\bshould i (invest|buy|sell|redeem|switch)\b",
    r"\bis .+ (a )?(good|bad|safe|risky) (investment|fund|option)\b",
    r"\bwill .+(give|return|generate|earn|make).+(return|profit|gain|interest)\b",
    r"\bexpected returns?\b",
    r"\bpredict(ed)? (return|nav|performance)\b",
    r"\bguaranteed returns?\b",
    r"\bwhere should i (put|invest|park)\b",
    r"\bbest fund(s)? (for|to)\b",
    r"\brecommend(ation)?\b",
    r"\badvice\b",
    r"\bwhich fund (should|would|is best)\b",
    r"\bportfolio (advice|recommendation|suggest)\b",
]

REFUSAL_MESSAGE = (
    "I'm sorry, I can't provide personalised investment advice or return predictions. "
    "Please consult a SEBI-registered financial advisor. "
    "I can answer factual questions about fund details, NAV, expense ratios, and lock-in periods."
)


class AdvisoryFilter:
    """Detects advisory / predictive queries and returns a standard refusal."""

    def __init__(self) -> None:
        self._compiled = [re.compile(p, re.IGNORECASE) for p in ADVISORY_PATTERNS]

    def is_advisory(self, text: str) -> bool:
        """Return True if *text* is seeking investment advice or predictions."""
        for pattern in self._compiled:
            if pattern.search(text):
                return True
        return False

    def check(self, query: str) -> Tuple[bool, str]:
        """
        Returns (is_blocked, message).
        If is_blocked is True, message contains the refusal string.
        """
        if self.is_advisory(query):
            return True, REFUSAL_MESSAGE
        return False, ""

