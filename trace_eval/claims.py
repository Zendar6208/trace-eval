"""Rule-based sentence segmentation and claim identification conforming to Methodology Section 2.3 and 2.5.

Methodology requirements:
- Section 2.3:
  1. Blank line, or newline followed by list marker (-, *, •, \\d+[.)]), is a hard boundary.
  2. Within a unit, a soft boundary is [.!?], then optional closing quote or bracket characters,
     then whitespace, then an uppercase letter, digit, or opening quote or bracket.
  3. No split after a protected abbreviation (e.g, i.e, vs, mr, mrs, ms, dr, prof, inc, ltd,
     co, no, fig, approx, st; case-insensitive).
     No split on a period between digits not followed by whitespace (decimals, versions).
  4. A single newline inside a unit becomes a space.
  5. Segmentation is pinned by golden tests.
- Section 2.5:
  - Claim sentence is any sentence except:
    (a) matches refusal_patterns
    (b) no alphanumeric content after marker removal
    (c) matches non_claim_patterns (e.g. "Sure.", "Here is the answer:")
  - Claim sentence with fewer than 3 word tokens is not_assessable (e.g. "Yes.").
    Excluded from claim rates, counted, and reported.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from trace_eval.refusal import is_refusal
from trace_eval.text_norm import normalize_text

PROTECTED_ABBREVIATIONS = {
    "e.g",
    "i.e",
    "vs",
    "mr",
    "mrs",
    "ms",
    "dr",
    "prof",
    "inc",
    "ltd",
    "co",
    "no",
    "fig",
    "approx",
    "st",
}

DEFAULT_NON_CLAIM_PATTERNS = [
    r"^(?:sure|certainly|of course)[.:!]?$",
    r"^(?:here is the answer|here's the answer|here is what i found|here are the details|here is the information)[.:!]?$",
    r"^(?:based on the (?:provided|given) (?:text|context|documents))[.:!]?$",
    r"^(?:as requested|in summary)[.:!]?$",
]

COMPILED_NON_CLAIM_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DEFAULT_NON_CLAIM_PATTERNS]


@dataclass(frozen=True)
class RawSentence:
    """A segmented sentence before and after marker cleaning."""

    index: int
    raw_text: str
    clean_text: str
    start_char: int
    end_char: int
    is_claim: bool
    is_refusal: bool
    is_non_claim: bool
    is_assessable: bool
    token_count: int


def is_non_claim_sentence(text: str, custom_patterns: Sequence[str] | None = None) -> bool:
    """Check if a sentence matches non-claim patterns (e.g. pleasantries, preamble)."""
    stripped = text.strip()
    if not stripped:
        return True
    for pat in COMPILED_NON_CLAIM_PATTERNS:
        if pat.match(stripped):
            return True
    if custom_patterns:
        for p in custom_patterns:
            if re.match(p, stripped, re.IGNORECASE):
                return True
    return False


def _has_alphanumeric(text: str) -> bool:
    """Check if string contains any alphanumeric character."""
    return any(c.isalnum() for c in text)


def _count_word_tokens(text: str) -> int:
    """Count word tokens in sentence per Section 2.5."""
    return len(re.findall(r"\b\w+\b", text))


def mask_spans(text: str, spans: Sequence[tuple[int, int]]) -> str:
    """Replace character spans with spaces of identical length."""
    chars = list(text)
    for start, end in spans:
        s = max(0, start)
        e = min(len(chars), end)
        for i in range(s, e):
            chars[i] = " "
    return "".join(chars)


def split_sentences_raw(
    text: str,
    mask_char_spans: Sequence[tuple[int, int]] | None = None,
) -> list[tuple[int, int, str]]:
    """Perform rule-based sentence segmentation conforming strictly to Section 2.3.

    Returns:
        List of tuples: (start_char, end_char, raw_segment_text)
    """
    normalized = normalize_text(text)
    if not normalized:
        return []

    # Mask marker spans with spaces so periods inside IDs never trigger splits
    masked = mask_spans(normalized, mask_char_spans) if mask_char_spans else normalized

    # Step 1: Identify hard boundaries
    # Hard boundary 1: Blank line (\n\s*\n)
    # Hard boundary 2: Newline followed by list marker (\n\s*(?:[-*•]|\d+[.)])\s+)
    hard_split_pattern = re.compile(r"(\n[ \t]*\n|\n[ \t]*(?:[-*•]|\d+[.)])[ \t]+)")

    hard_chunks: list[tuple[int, int]] = []
    last_idx = 0
    for match in hard_split_pattern.finditer(masked):
        m_start, m_end = match.span()
        if m_start > last_idx:
            hard_chunks.append((last_idx, m_start))
        # If it's a list marker, the list marker itself belongs to the next chunk!
        # Notice: match group includes \n[ \t]*...
        # The split point is before the list marker or between lines
        last_idx = m_end
    if last_idx < len(masked):
        hard_chunks.append((last_idx, len(masked)))

    # Step 2: Within each hard unit, apply soft boundaries
    # Soft boundary: [.!?], then optional closing quote/bracket, then whitespace, then [A-Z0-9"'\(\[\{«“‘]
    # Guard 3: Protected abbreviations and decimals
    soft_boundary_pattern = re.compile(r"([.!?])(['\"\)\]\}»”’]*)([\s]+)(?=[A-Z0-9'\"‘“\(\[\{«])")

    sentences: list[tuple[int, int, str]] = []

    for chunk_start, chunk_end in hard_chunks:
        chunk_masked = masked[chunk_start:chunk_end]
        if not chunk_masked.strip():
            continue

        local_start = 0
        for m in soft_boundary_pattern.finditer(chunk_masked):
            punct = m.group(1)
            closing = m.group(2)
            punct_pos_in_chunk = m.start(1)

            # Check if this period is protected
            if punct == ".":
                # Check for decimal/version between digits: digit . digit
                if punct_pos_in_chunk > 0 and punct_pos_in_chunk + 1 < len(chunk_masked):
                    before_c = chunk_masked[punct_pos_in_chunk - 1]
                    after_c = chunk_masked[punct_pos_in_chunk + 1]
                    if before_c.isdigit() and after_c.isdigit():
                        continue

                # Check for protected abbreviation before this period
                # Look back up to 10 chars for word
                prefix = chunk_masked[:punct_pos_in_chunk]
                word_match = re.search(r"([A-Za-z]+)$", prefix)
                if word_match:
                    abbr = word_match.group(1).lower()
                    if abbr in PROTECTED_ABBREVIATIONS:
                        continue
                    # Check e.g / i.e with previous period
                    # E.g. "e.g" preceded by "e." -> check "e.g" or "i.e"
                    if abbr in {"g", "e"} and prefix.endswith(f"{abbr[0]}.{abbr}"):
                        continue

            # Found valid soft split
            split_end_in_chunk = punct_pos_in_chunk + len(punct) + len(closing)
            span_start = chunk_start + local_start
            span_end = chunk_start + split_end_in_chunk

            masked_seg = chunk_masked[local_start:split_end_in_chunk]
            if masked_seg.strip():
                # Strip leading and trailing whitespace from the masked segment
                leading_spaces = len(masked_seg) - len(masked_seg.lstrip())
                trailing_spaces = len(masked_seg) - len(masked_seg.rstrip())
                actual_start = span_start + leading_spaces
                actual_end = span_end - trailing_spaces
                if actual_end > actual_start:
                    sentences.append(
                        (actual_start, actual_end, normalized[actual_start:actual_end])
                    )

            # Advance local_start to after the whitespace
            local_start = m.end()

        # Remainder of chunk
        if local_start < len(chunk_masked):
            span_start = chunk_start + local_start
            span_end = chunk_end
            masked_seg = chunk_masked[local_start:]
            if masked_seg.strip():
                leading_spaces = len(masked_seg) - len(masked_seg.lstrip())
                trailing_spaces = len(masked_seg) - len(masked_seg.rstrip())
                actual_start = span_start + leading_spaces
                actual_end = span_end - trailing_spaces
                if actual_end > actual_start:
                    sentences.append(
                        (actual_start, actual_end, normalized[actual_start:actual_end])
                    )

    return sentences


def identify_sentences(
    text: str,
    mask_char_spans: Sequence[tuple[int, int]] | None = None,
    clean_marker_fn: callable = None,
    custom_refusal_patterns: list[str] | None = None,
    custom_non_claim_patterns: list[str] | None = None,
) -> list[RawSentence]:
    """Segment text into sentences and classify each per Section 2.3 & 2.5."""
    raw_spans = split_sentences_raw(text, mask_char_spans=mask_char_spans)
    results: list[RawSentence] = []

    for idx, (start_char, end_char, raw_sentence) in enumerate(raw_spans):
        # Rule 4: A single newline inside a unit becomes a space
        unit_text = re.sub(r"\r?\n", " ", raw_sentence)

        # Remove marker text if cleaner provided
        cleaned_text = clean_marker_fn(unit_text) if clean_marker_fn else unit_text
        # Collapse whitespace
        cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text).strip()

        # Classify
        refusal = is_refusal(cleaned_text, custom_patterns=custom_refusal_patterns)
        has_alnum = _has_alphanumeric(cleaned_text)
        non_claim = is_non_claim_sentence(cleaned_text, custom_patterns=custom_non_claim_patterns)

        # Section 2.5: A claim sentence is any sentence except:
        # (a) matches refusal_patterns
        # (b) no alphanumeric content
        # (c) matches non_claim_patterns
        is_claim = has_alnum and (not refusal) and (not non_claim)

        tokens = _count_word_tokens(cleaned_text)
        # Fewer than 3 word tokens is not_assessable for grounding
        assessable = is_claim and (tokens >= 3)

        results.append(
            RawSentence(
                index=idx,
                raw_text=raw_sentence,
                clean_text=cleaned_text,
                start_char=start_char,
                end_char=end_char,
                is_claim=is_claim,
                is_refusal=refusal,
                is_non_claim=non_claim,
                is_assessable=assessable,
                token_count=tokens,
            )
        )

    return results
