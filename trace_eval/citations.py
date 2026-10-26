"""Citation marker parsing, attachment, and validity checking conforming to Methodology Section 2.2 and 2.4.

Methodology requirements:
- Section 2.2:
  - citation_style: 'id' (default) -> [ID (SEP ID)*] with ID matching [A-Za-z0-9_.:-]+, SEP , or ;
  - citation_style: 'index' -> [N (SEP N)*] with N integer (1-based position in retrieved)
  - Adjacent groups separated only by whitespace ([p1][p2], [p1] [p2]) form one citation set.
  - phantom_mode: 'bracket' (default) -> any matching bracket is citation, unknown IDs are phantoms.
  - phantom_mode: 'known_only' -> only IDs present in retrieved or corpus count as citations.
- Section 2.4 (CA-1 to CA-8):
  - CA-1: Mask marker spans, segment, then reattach.
  - CA-2: Marker inside a sentence attaches to that sentence.
  - CA-3: Marker after sentence-final punctuation and before next sentence attaches to preceding sentence.
  - CA-4: Marker before any sentence text is an orphan (sentence_index = None).
  - CA-5: Per sentence, cited IDs are deduplicated in first-appearance order.
  - CA-6: Units evaluated against cited passage only. Sentence is supported if >= 1 unit supports it.
  - CA-7: Unit validity: 'ok', 'not_retrieved', 'unknown_id', 'index_out_of_range'.
  - CA-8: Marker text stripped before NLI and correctness matching.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from trace_eval.claims import RawSentence, identify_sentences
from trace_eval.schema.run import CitationUnitEvidence

CitationValidity = Literal["ok", "not_retrieved", "unknown_id", "index_out_of_range"]

ID_MARKER_PATTERN = re.compile(r"\[([A-Za-z0-9_.:-]+(?:\s*[,;]\s*[A-Za-z0-9_.:-]+)*)\]")
INDEX_MARKER_PATTERN = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")


@dataclass(frozen=True)
class CitationMarkerSpan:
    """An individual citation marker span in the text."""

    raw_text: str
    start: int
    end: int
    raw_tokens: list[str]


@dataclass
class ParsedCitationUnit:
    """A citation unit after attachment and deduplication."""

    sentence_index: int | None
    passage_id: str
    validity: CitationValidity
    duplicate_count: int = 0
    supports: bool = False
    entail_prob: float | None = None
    best_window: str | None = None

    def to_evidence(self) -> CitationUnitEvidence:
        """Convert to validated CitationUnitEvidence Pydantic model."""
        return CitationUnitEvidence(
            sentence_index=self.sentence_index,
            passage_id=self.passage_id,
            validity=self.validity,
            supports=self.supports,
            entail_prob=self.entail_prob,
            best_window=self.best_window,
        )


@dataclass
class CitationParsingResult:
    """Complete citation parsing and sentence attachment result."""

    sentences: list[RawSentence]
    units: list[ParsedCitationUnit]
    marker_spans: list[CitationMarkerSpan]
    duplicate_units_count: int = 0


def find_marker_spans(
    text: str,
    citation_style: Literal["id", "index"] = "id",
    phantom_mode: Literal["bracket", "known_only"] = "bracket",
    retrieved_ids: Sequence[str] | None = None,
    corpus_ids: set[str] | None = None,
) -> list[CitationMarkerSpan]:
    """Find all citation marker spans matching the configured citation style and phantom mode."""
    if not text:
        return []

    pattern = INDEX_MARKER_PATTERN if citation_style == "index" else ID_MARKER_PATTERN
    spans: list[CitationMarkerSpan] = []

    retrieved_set = set(retrieved_ids) if retrieved_ids else set()
    corpus_set = corpus_ids or set()
    known_ids = retrieved_set | corpus_set

    for match in pattern.finditer(text):
        inner_content = match.group(1)
        tokens = [t.strip() for t in re.split(r"[,;]", inner_content) if t.strip()]

        if phantom_mode == "known_only":
            if citation_style == "index":
                # Only keep indices that point to known retrieved positions
                valid_tokens = [
                    t for t in tokens if t.isdigit() and 1 <= int(t) <= len(retrieved_set)
                ]
            else:
                valid_tokens = [t for t in tokens if t in known_ids]

            if not valid_tokens:
                continue
            tokens = valid_tokens

        spans.append(
            CitationMarkerSpan(
                raw_text=match.group(0),
                start=match.start(),
                end=match.end(),
                raw_tokens=tokens,
            )
        )

    return spans


def strip_citation_markers(
    text: str,
    citation_style: Literal["id", "index"] = "id",
    phantom_mode: Literal["bracket", "known_only"] = "bracket",
    retrieved_ids: Sequence[str] | None = None,
    corpus_ids: set[str] | None = None,
) -> str:
    """Remove citation markers and collapse whitespace per CA-8."""
    spans = find_marker_spans(
        text,
        citation_style=citation_style,
        phantom_mode=phantom_mode,
        retrieved_ids=retrieved_ids,
        corpus_ids=corpus_ids,
    )
    if not spans:
        cleaned = re.sub(r"[ \t]+", " ", text).strip()
        return re.sub(r"\s+([.,;:!?])", r"\1", cleaned)

    chars = list(text)
    for span in spans:
        for i in range(span.start, span.end):
            chars[i] = " "
    stripped = "".join(chars)
    collapsed = re.sub(r"[ \t]+", " ", stripped).strip()
    return re.sub(r"\s+([.,;:!?])", r"\1", collapsed)


def parse_and_attach_citations(
    text: str,
    retrieved_ids: Sequence[str],
    corpus_ids: set[str] | None = None,
    citation_style: Literal["id", "index"] = "id",
    phantom_mode: Literal["bracket", "known_only"] = "bracket",
    custom_refusal_patterns: list[str] | None = None,
    custom_non_claim_patterns: list[str] | None = None,
) -> CitationParsingResult:
    """Parse citations, segment sentences, attach per CA-1 to CA-7, and deduplicate."""
    retrieved_list = list(retrieved_ids)
    retrieved_set = set(retrieved_list)
    corpus_set = corpus_ids or set()

    # Step 1: Find all marker spans
    marker_spans = find_marker_spans(
        text,
        citation_style=citation_style,
        phantom_mode=phantom_mode,
        retrieved_ids=retrieved_list,
        corpus_ids=corpus_set,
    )

    # Step 2: CA-1 - Mask marker spans and segment sentences
    char_spans = [(m.start, m.end) for m in marker_spans]

    def _cleaner(s: str) -> str:
        return strip_citation_markers(
            s,
            citation_style=citation_style,
            phantom_mode=phantom_mode,
            retrieved_ids=retrieved_list,
            corpus_ids=corpus_set,
        )

    sentences = identify_sentences(
        text,
        mask_char_spans=char_spans,
        clean_marker_fn=_cleaner,
        custom_refusal_patterns=custom_refusal_patterns,
        custom_non_claim_patterns=custom_non_claim_patterns,
    )

    # Step 3: Attach markers to sentences (CA-2, CA-3, CA-4)
    # Mapping from sentence_index (or None for orphan) to list of tokens in appearance order
    attached_tokens: dict[int | None, list[str]] = {s.index: [] for s in sentences}
    attached_tokens[None] = []

    first_sentence_start = sentences[0].start_char if sentences else None

    for m in marker_spans:
        # CA-4: Marker at very start before any sentence text is orphan
        if first_sentence_start is None or m.end <= first_sentence_start:
            target_idx = None
        else:
            # Find the sentence this marker attaches to:
            # Latest sentence S_i such that S_i.start_char <= m.start
            target_s = None
            for s in sentences:
                if s.start_char <= m.start:
                    target_s = s
                else:
                    break
            target_idx = target_s.index if target_s is not None else None

        attached_tokens[target_idx].extend(m.raw_tokens)

    # Step 4: CA-5 - Deduplicate cited IDs per sentence in appearance order
    # Step 5: CA-7 - Assign validity
    units: list[ParsedCitationUnit] = []
    total_duplicates = 0

    # Process sentences in order, followed by orphan citations (None)
    ordered_keys: list[int | None] = [s.index for s in sentences]
    ordered_keys.append(None)

    for s_idx in ordered_keys:
        tokens = attached_tokens.get(s_idx, [])
        if not tokens:
            continue

        seen_in_sentence: dict[str, int] = {}
        for token in tokens:
            # Resolve passage_id and validity per CA-7
            if citation_style == "index":
                try:
                    idx_val = int(token)
                    if 1 <= idx_val <= len(retrieved_list):
                        passage_id = retrieved_list[idx_val - 1]
                        validity: CitationValidity = "ok"
                    else:
                        passage_id = token
                        validity = "index_out_of_range"
                except ValueError:
                    passage_id = token
                    validity = "index_out_of_range"
            else:
                passage_id = token
                if passage_id in retrieved_set:
                    validity = "ok"
                elif passage_id in corpus_set:
                    validity = "not_retrieved"
                else:
                    validity = "unknown_id"

            if passage_id in seen_in_sentence:
                seen_in_sentence[passage_id] += 1
                total_duplicates += 1
            else:
                seen_in_sentence[passage_id] = 1
                units.append(
                    ParsedCitationUnit(
                        sentence_index=s_idx,
                        passage_id=passage_id,
                        validity=validity,
                        duplicate_count=0,
                        supports=False,
                    )
                )

        # Update duplicate counts on the units
        for u in units:
            if u.sentence_index == s_idx and u.passage_id in seen_in_sentence:
                u.duplicate_count = seen_in_sentence[u.passage_id] - 1

    return CitationParsingResult(
        sentences=sentences,
        units=units,
        marker_spans=marker_spans,
        duplicate_units_count=total_duplicates,
    )
