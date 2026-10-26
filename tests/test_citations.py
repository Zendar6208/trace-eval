"""Unit tests for citation parsing, attachment, and validity conforming to Methodology Section 2.2 and 2.4."""

import pytest

from trace_eval.citations import (
    find_marker_spans,
    parse_and_attach_citations,
    strip_citation_markers,
)
from trace_eval.schema.run import CitationUnitEvidence


def test_find_marker_spans_id_style():
    text = "First fact [p01]. Second fact [doc_2, doc:3; p-4]. Final remark."
    spans = find_marker_spans(text, citation_style="id", phantom_mode="bracket")
    assert len(spans) == 2
    assert spans[0].raw_tokens == ["p01"]
    assert spans[1].raw_tokens == ["doc_2", "doc:3", "p-4"]


def test_find_marker_spans_index_style():
    text = "First fact [1]. Second fact [2, 3; 5]."
    spans = find_marker_spans(text, citation_style="index", phantom_mode="bracket")
    assert len(spans) == 2
    assert spans[0].raw_tokens == ["1"]
    assert spans[1].raw_tokens == ["2", "3", "5"]


def test_adjacent_marker_groups():
    text = "Here is the claim [p01][p02] and another [p03] [p04]."
    spans = find_marker_spans(text, citation_style="id")
    assert len(spans) == 4
    assert spans[0].raw_tokens == ["p01"]
    assert spans[1].raw_tokens == ["p02"]
    assert spans[2].raw_tokens == ["p03"]
    assert spans[3].raw_tokens == ["p04"]


def test_phantom_mode_known_only():
    text = "Valid [p01] and phantom [sic] and unknown [p999]."
    retrieved = ["p01"]
    corpus = {"p01", "p02"}

    # bracket mode: all bracketed tokens matching syntax count as markers
    bracket_spans = find_marker_spans(
        text,
        citation_style="id",
        phantom_mode="bracket",
        retrieved_ids=retrieved,
        corpus_ids=corpus,
    )
    assert len(bracket_spans) == 3

    # known_only mode: only known IDs count
    known_spans = find_marker_spans(
        text,
        citation_style="id",
        phantom_mode="known_only",
        retrieved_ids=retrieved,
        corpus_ids=corpus,
    )
    assert len(known_spans) == 1
    assert known_spans[0].raw_tokens == ["p01"]


def test_strip_citation_markers():
    text = "Refunds take 30 days.[p01] Fees apply [doc_2, doc_3]."
    stripped = strip_citation_markers(text)
    assert stripped == "Refunds take 30 days. Fees apply."


def test_ca2_in_sentence_attachment():
    text = "Refunds [p01] take 30 days. Fees apply."
    res = parse_and_attach_citations(text, retrieved_ids=["p01"])
    assert len(res.sentences) == 2
    assert len(res.units) == 1
    assert res.units[0].sentence_index == 0
    assert res.units[0].passage_id == "p01"
    assert res.units[0].validity == "ok"


def test_ca3_trailing_marker_attachment():
    text = "Refunds take 30 days.[p03] Fees apply."
    res = parse_and_attach_citations(text, retrieved_ids=["p03"])
    assert len(res.sentences) == 2
    assert len(res.units) == 1
    # Attaches to preceding sentence 0
    assert res.units[0].sentence_index == 0
    assert res.units[0].passage_id == "p03"
    assert res.units[0].validity == "ok"


def test_ca4_orphan_marker_at_start():
    text = "[p01] Refunds take 30 days."
    res = parse_and_attach_citations(text, retrieved_ids=["p01"])
    assert len(res.sentences) == 1
    assert len(res.units) == 1
    # Orphan marker before any sentence text has sentence_index = None
    assert res.units[0].sentence_index is None
    assert res.units[0].passage_id == "p01"
    assert res.units[0].validity == "ok"

    # Verify Pydantic schema validation for orphan
    ev = res.units[0].to_evidence()
    assert ev.sentence_index is None
    assert ev.supports is False


def test_ca5_deduplication_per_sentence():
    text = "Refunds take 30 days [p01] according to policy [p01].[p01] Fees apply."
    res = parse_and_attach_citations(text, retrieved_ids=["p01"])
    assert len(res.sentences) == 2
    # Only 1 unique citation unit for sentence 0
    assert len(res.units) == 1
    assert res.units[0].sentence_index == 0
    assert res.units[0].passage_id == "p01"
    assert res.units[0].duplicate_count == 2
    assert res.duplicate_units_count == 2


def test_ca7_validity_classes_id_style():
    text = "Claim A [p_ret]. Claim B [p_corp]. Claim C [p_phantom]."
    retrieved = ["p_ret"]
    corpus = {"p_ret", "p_corp"}

    res = parse_and_attach_citations(
        text,
        retrieved_ids=retrieved,
        corpus_ids=corpus,
        citation_style="id",
        phantom_mode="bracket",
    )
    units_by_id = {u.passage_id: u for u in res.units}
    assert units_by_id["p_ret"].validity == "ok"
    assert units_by_id["p_corp"].validity == "not_retrieved"
    assert units_by_id["p_phantom"].validity == "unknown_id"


def test_ca7_validity_classes_index_style():
    text = "Claim 1 [1]. Claim 2 [2]. Claim out of range [5]."
    retrieved = ["doc_first", "doc_second"]

    res = parse_and_attach_citations(
        text,
        retrieved_ids=retrieved,
        citation_style="index",
    )
    assert len(res.units) == 3
    assert res.units[0].passage_id == "doc_first"
    assert res.units[0].validity == "ok"
    assert res.units[1].passage_id == "doc_second"
    assert res.units[1].validity == "ok"
    assert res.units[2].passage_id == "5"
    assert res.units[2].validity == "index_out_of_range"


def test_orphan_validation_integrity():
    # Attempting to mark an orphan citation as supporting must raise ValueError
    with pytest.raises(ValueError, match="cannot be supporting per CA-4"):
        CitationUnitEvidence(
            sentence_index=None,
            passage_id="p01",
            validity="ok",
            supports=True,
        )


def test_invalid_validity_support_integrity():
    # Attempting to mark non-ok citation as supporting must raise ValueError
    for v in ["not_retrieved", "unknown_id", "index_out_of_range"]:
        with pytest.raises(ValueError, match="cannot be supporting per CA-7"):
            CitationUnitEvidence(
                sentence_index=0,
                passage_id="p01",
                validity=v,
                supports=True,
            )
