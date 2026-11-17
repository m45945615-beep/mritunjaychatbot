"""
Guardrails test suite — TC-01 through TC-09 from implementation.md
Run with: python -m pytest tests/test_guardrails.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.guardrails.pii_sanitizer import PIISanitizer
from src.guardrails.advisory_filter import AdvisoryFilter
from src.guardrails.validator import OutputValidator


# ── Fixtures ─────────────────────────────────────────────────────────────────
pii = PIISanitizer()
adv = AdvisoryFilter()
val = OutputValidator(max_sentences=3, require_source_url=True, append_disclaimer=True)


# ══════════════════════════════════════════════════════════════════════════════
# TC-01  PAN card detection
# ══════════════════════════════════════════════════════════════════════════════
def test_tc01_pan_detected():
    text = "My PAN is ABCDE1234F and I want to invest."
    found, types = pii.contains_pii(text)
    assert found, "PAN should be detected"
    assert "PAN" in types


def test_tc01_pan_redacted():
    text = "My PAN is ABCDE1234F."
    _, redacted, _ = pii.check_and_redact(text)
    assert "ABCDE1234F" not in redacted
    assert "<REDACTED_PAN>" in redacted


# ══════════════════════════════════════════════════════════════════════════════
# TC-02  Aadhaar detection
# ══════════════════════════════════════════════════════════════════════════════
def test_tc02_aadhaar_detected():
    text = "My Aadhaar is 9876 5432 1098."
    found, types = pii.contains_pii(text)
    assert found, "Aadhaar should be detected"
    assert "AADHAAR" in types


# ══════════════════════════════════════════════════════════════════════════════
# TC-03  Phone number detection
# ══════════════════════════════════════════════════════════════════════════════
def test_tc03_phone_detected():
    text = "Call me at +91 9876543210 for more info."
    found, types = pii.contains_pii(text)
    assert found, "Phone should be detected"
    assert "PHONE" in types


# ══════════════════════════════════════════════════════════════════════════════
# TC-04  No false positive on normal text
# ══════════════════════════════════════════════════════════════════════════════
def test_tc04_no_false_positive():
    text = "What is the expense ratio of HDFC Large Cap Fund?"
    found, types = pii.contains_pii(text)
    assert not found, f"No PII expected; got: {types}"


# ══════════════════════════════════════════════════════════════════════════════
# TC-05  Advisory filter — investment advice query blocked
# ══════════════════════════════════════════════════════════════════════════════
def test_tc05_advice_blocked():
    query = "Should I invest in HDFC ELSS fund right now?"
    blocked, msg = adv.check(query)
    assert blocked, "Advisory query should be blocked"
    assert len(msg) > 0


# ══════════════════════════════════════════════════════════════════════════════
# TC-06  Advisory filter — return prediction blocked
# ══════════════════════════════════════════════════════════════════════════════
def test_tc06_prediction_blocked():
    query = "What will be the expected returns of HDFC Flexi Cap in 2025?"
    blocked, _ = adv.check(query)
    assert blocked, "Return prediction should be blocked"


# ══════════════════════════════════════════════════════════════════════════════
# TC-07  Advisory filter — factual query NOT blocked
# ══════════════════════════════════════════════════════════════════════════════
def test_tc07_factual_not_blocked():
    query = "What is the expense ratio of HDFC ELSS Tax Saver Fund?"
    blocked, _ = adv.check(query)
    assert not blocked, "Factual query must NOT be blocked"


# ══════════════════════════════════════════════════════════════════════════════
# TC-08  Output validator — long response truncated
# ══════════════════════════════════════════════════════════════════════════════
def test_tc08_long_response_truncated():
    long_text = (
        "The fund has a 3-year lock-in. "
        "It invests in equity. "
        "The NAV is updated daily. "
        "You can redeem after lock-in. "
        "Source: https://example.com"
    )
    _, processed, issues = val.validate(long_text, sources=["https://example.com"])
    sentences = processed.split(". ")
    # Disclaimer may add more text but the main body should be ≤3 sentences
    assert any("truncated" in i.lower() for i in issues), f"Expected truncation; issues={issues}"


# ══════════════════════════════════════════════════════════════════════════════
# TC-09  Output validator — disclaimer appended when absent
# ══════════════════════════════════════════════════════════════════════════════
def test_tc09_disclaimer_appended():
    text = "The expense ratio is 1.05%. Source: https://example.com"
    _, processed, issues = val.validate(text, sources=["https://example.com"])
    assert "not investment advice" in processed.lower(), "Disclaimer should be appended"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {passed + failed} tests.")

