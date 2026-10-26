"""Deterministic text processing and normalization conforming to Methodology Section 2.1.

Requirements:
- All text is Unicode NFC. \\r\\n and \\r become \\n.
- Matching normalization (for fact matching and token F1):
  - Lowercase.
  - Strip punctuation except inside numbers (e.g. 3.14).
  - Collapse whitespace.
  - Normalize numbers (remove thousands separators e.g. 1,000 -> 1000; drop trailing .0 e.g. 10.0 -> 10).
  - Number words are not converted in v1.
- Citation marker stripping per CA-8 (marker groups [p01], [1, 2] removed before matching).
"""

from __future__ import annotations

import re
import unicodedata

# Matches citation markers like [p01], [p1, p2], [1; 2], [doc-1]
CITATION_MARKER_REGEX = re.compile(r"\[(?:\s*[A-Za-z0-9_.:-]+\s*[,;]?\s*)+\]")


def normalize_unicode_and_newlines(text: str) -> str:
    """Normalize text to Unicode NFC and canonicalize newlines to \\n."""
    if not text:
        return ""
    nfc_text = unicodedata.normalize("NFC", text)
    return nfc_text.replace("\r\n", "\n").replace("\r", "\n")


normalize_text = normalize_unicode_and_newlines


def strip_citation_markers(text: str) -> str:
    """Remove citation markers from answer text per Methodology CA-8."""
    if not text:
        return ""
    stripped = CITATION_MARKER_REGEX.sub(" ", text)
    return re.sub(r"[ \t]+", " ", stripped).strip()


def normalize_number_tokens(text: str) -> str:
    """Normalize numbers: remove thousands separators (1,000 -> 1000) and drop trailing .0."""
    # 1. Remove thousands separators between digits: 1,000 or 10,000,000
    cleaned = re.sub(r"(?<=\d),(?=\d{3}(?:\b|\D))", "", text)
    # 2. Drop trailing .0 on whole-number decimals: 10.0 -> 10, 42.0 -> 42
    cleaned = re.sub(r"\b(\d+)\.0\b", r"\1", cleaned)
    return cleaned


def normalize_for_matching(text: str, strip_markers: bool = True) -> str:
    """Complete matching normalization for token F1 and fact matching per Section 2.1.

    Steps:
    1. Unicode NFC & newline normalization.
    2. Optional removal of citation markers (CA-8).
    3. Lowercase.
    4. Normalize numbers (thousands separators removed, trailing .0 stripped).
    5. Strip punctuation except inside numbers (like decimals in 3.14).
    6. Collapse whitespace.
    """
    if not text:
        return ""

    norm = normalize_unicode_and_newlines(text)
    if strip_markers:
        norm = strip_citation_markers(norm)

    norm = norm.lower()
    norm = normalize_number_tokens(norm)

    # Strip punctuation except inside numbers.
    # Preserve: alphanumeric, spaces, and periods/hyphens flanked strictly by digits.
    # Replace any punctuation character that is not a decimal point or hyphen inside a number with a space.
    cleaned_chars: list[str] = []
    n = len(norm)
    for i, ch in enumerate(norm):
        if ch.isalnum() or ch.isspace():
            cleaned_chars.append(ch)
        elif ch in ".-" and 0 < i < n - 1 and norm[i - 1].isdigit() and norm[i + 1].isdigit():
            # decimal point or range between digits (e.g. 3.14 or 1-2)
            cleaned_chars.append(ch)
        else:
            cleaned_chars.append(" ")

    result = "".join(cleaned_chars)
    return re.sub(r"\s+", " ", result).strip()


def tokenize(text: str) -> list[str]:
    """Tokenize normalized text into word tokens by whitespace."""
    norm = normalize_for_matching(text)
    if not norm:
        return []
    return norm.split()
