"""Tests for text processing and normalization conforming to Methodology Section 2.1."""

from trace_eval.text_norm import (
    normalize_for_matching,
    normalize_number_tokens,
    normalize_unicode_and_newlines,
    strip_citation_markers,
    tokenize,
)


def test_unicode_and_newline_normalization():
    # Combining characters NFD -> NFC
    nfd = "cafe\u0301"
    assert normalize_unicode_and_newlines(nfd) == "caf\u00e9"

    # Newline canonicalization (\r\n and \r -> \n)
    mixed_newlines = "line1\r\nline2\rline3\nline4"
    assert normalize_unicode_and_newlines(mixed_newlines) == "line1\nline2\nline3\nline4"


def test_strip_citation_markers():
    text = "Refunds take 30 days.[p01] Cancellations apply.[p02, p03] Notes here.[1; 2]"
    stripped = strip_citation_markers(text)
    assert "[p01]" not in stripped
    assert "[p02, p03]" not in stripped
    assert "[1; 2]" not in stripped
    assert "Refunds take 30 days. Cancellations apply. Notes here." == stripped


def test_normalize_number_tokens():
    # Thousands separators removed
    assert normalize_number_tokens("1,000") == "1000"
    assert normalize_number_tokens("Cost is $1,250,000 dollars.") == "Cost is $1250000 dollars."

    # Trailing .0 dropped
    assert normalize_number_tokens("10.0") == "10"
    assert normalize_number_tokens("Rate is 42.0% and 3.14.") == "Rate is 42% and 3.14."


def test_normalize_for_matching():
    # Punctuation stripped except inside numbers (e.g. 3.14)
    raw = "Refunds take up to 1,000 days (or 30.0 days)! See: 3.14."
    norm = normalize_for_matching(raw)
    assert norm == "refunds take up to 1000 days or 30 days see 3.14"


def test_tokenize():
    raw = "Refunds take 30 days.[p01]"
    tokens = tokenize(raw)
    assert tokens == ["refunds", "take", "30", "days"]
