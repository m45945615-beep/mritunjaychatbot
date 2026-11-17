"""
PII Sanitizer — detects and redacts Personally Identifiable Information
before any text is sent to the LLM or stored in logs.

Patterns covered
----------------
- PAN card        : AAAAA9999A (10 chars, format LLLLLDDDDDL)
- Aadhaar number  : 12-digit number (with/without spaces or hyphens)
- Indian phone    : +91 / 0 prefix + 10 digits
- Folio number    : alphanumeric sequences of 8–16 chars labelled "folio"
- Email addresses : standard email pattern
"""

import re
from typing import Tuple

# ── Pattern definitions ──────────────────────────────────────────────────────
_PATTERNS: dict[str, str] = {
    "PAN": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    "AADHAAR": r"\b[2-9]\d{3}[\s\-]?\d{4}[\s\-]?\d{4}\b",
    "PHONE": r"(?<!\d)(\+91[\s\-]?|0)[6-9]\d{9}(?!\d)",
    "FOLIO": r"\bfolio[\s\-]?(?:no\.?|number)?[\s:]*([A-Z0-9]{8,16})\b",
    "EMAIL": r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
}

_COMPILED: dict[str, re.Pattern] = {
    name: re.compile(pat, re.IGNORECASE) for name, pat in _PATTERNS.items()
}


class PIISanitizer:
    """Detects and redacts PII from user input and LLM output."""

    def contains_pii(self, text: str) -> Tuple[bool, list[str]]:
        """
        Check *text* for PII.

        Returns
        -------
        (found, types)
            found : True if any PII was detected
            types : list of PII type names detected (e.g. ["PAN", "PHONE"])
        """
        found_types: list[str] = []
        for name, pattern in _COMPILED.items():
            if pattern.search(text):
                found_types.append(name)
        return bool(found_types), found_types

    def redact(self, text: str) -> str:
        """
        Return *text* with all PII replaced by <REDACTED_TYPE> placeholders.
        """
        result = text
        for name, pattern in _COMPILED.items():
            result = pattern.sub(f"<REDACTED_{name}>", result)
        return result

    def check_and_redact(self, text: str) -> Tuple[bool, str, list[str]]:
        """
        Convenience method combining detection and redaction.

        Returns
        -------
        (had_pii, redacted_text, pii_types)
        """
        had_pii, types = self.contains_pii(text)
        redacted = self.redact(text) if had_pii else text
        return had_pii, redacted, types

