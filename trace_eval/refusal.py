"""Rule-based refusal detection conforming to Methodology Sections 2.5 & 3.

For unanswerable items:
The verdict is 'correct' if and only if the answer is a refusal.
"""

from __future__ import annotations

import re

from trace_eval.text_norm import normalize_for_matching

DEFAULT_REFUSAL_PATTERNS = [
    r"\bi (?:cannot|can't|am unable to) answer\b",
    r"\b(?:not|no) (?:information|mention|evidence|context|details) (?:is|are)?\s*(?:provided|found|available|given)\b",
    r"\b(?:the\s+)?(?:provided|given)?\s*(?:text|context|document|passage|documents)?\s*(?:does not|do not|doesn't|don't) (?:contain|mention|state|provide|say)\b",
    r"\bdoes not (?:mention|state|contain|provide|specify)\b",
    r"\bthere is no (?:information|mention|record|evidence)\b",
    r"\bcannot be answered from the (?:provided|given) (?:text|context|documents)\b",
    r"\bi do not have (?:enough|sufficient) information\b",
    r"\bnot mentioned in the (?:provided|given) (?:text|context|passages)\b",
    r"\bunable to determine from the (?:provided|given) (?:text|context)\b",
    r"\bnot specified in the (?:provided|given) (?:text|context)\b",
    r"\bi don't know\b",
    r"\bi do not know\b",
]

COMPILED_REFUSAL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DEFAULT_REFUSAL_PATTERNS]


def is_refusal(text: str, custom_patterns: list[str] | None = None) -> bool:
    """Determine whether an answer constitutes a refusal to answer.

    Args:
        text: The raw answer text.
        custom_patterns: Optional list of additional regex patterns.

    Returns:
        True if the text matches any standard or custom refusal pattern.
    """
    if not text or not text.strip():
        return False

    norm = normalize_for_matching(text)

    # Check compiled defaults
    for pat in COMPILED_REFUSAL_PATTERNS:
        if pat.search(norm):
            return True

    # Check custom patterns
    if custom_patterns:
        for p in custom_patterns:
            if re.search(p, norm, re.IGNORECASE):
                return True

    return False
