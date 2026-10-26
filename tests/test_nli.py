"""Unit tests for NLI evidence verification, sanity checks, and numeric guard conforming to Methodology Section 3 & 4."""

import pytest

from trace_eval.nli import (
    NLIEvaluator,
    check_numeric_guard,
    extract_numbers_and_dates,
    extract_premise_windows,
)


def test_extract_premise_windows():
    passage = "Sentence one. Sentence two. Sentence three. Sentence four."
    windows = extract_premise_windows(passage, window_sentences=2)
    # Windows of length 1 and 2
    assert "Sentence one." in windows
    assert "Sentence two." in windows
    assert "Sentence one. Sentence two." in windows
    assert "Sentence two. Sentence three." in windows
    assert "Sentence three. Sentence four." in windows
    # Window of length 3 should not be present when window_sentences=2
    assert "Sentence one. Sentence two. Sentence three." not in windows


def test_numeric_guard_grounded_numbers():
    claim = "The refund takes 30 days."
    retrieved = ["All refunds take 30 days to process."]
    assert check_numeric_guard(claim, retrieved) is False


def test_numeric_guard_ungrounded_number():
    claim = "The refund takes 45 days."
    retrieved = ["All refunds take 30 days to process."]
    # "45" is missing from retrieved text, so numeric guard MUST trigger!
    assert check_numeric_guard(claim, retrieved) is True


def test_numeric_guard_thousands_separator_normalization():
    claim = "The company serves 1,000 clients."
    retrieved = ["We proudly serve 1000 clients nationwide."]
    # 1,000 normalizes to 1000, so it matches!
    assert check_numeric_guard(claim, retrieved) is False


def test_numeric_guard_date_extraction():
    claim = "The policy was signed on October 15, 2023."
    retrieved = ["The agreement was finalized on October 15, 2023 in London."]
    assert check_numeric_guard(claim, retrieved) is False

    claim_ungrounded = "The policy was signed on October 15, 2025."
    assert check_numeric_guard(claim_ungrounded, retrieved) is True


def test_extract_numbers_and_dates():
    text = "In 2024, our revenue was $1,500.00 across 42 stores on 05/12/2023."
    extracted = extract_numbers_and_dates(text)
    assert "2024" in extracted
    assert "1500" in extracted
    assert "42" in extracted


def test_nli_sanity_checks_real_model():
    """Verify that the real pinned local model loads and passes all 3 mandatory sanity checks."""
    evaluator = NLIEvaluator(
        model_name="cross-encoder/nli-distilroberta-base",
        revision="b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
        device="cpu",
        local_files_only=True,
    )
    assert evaluator.get_id2label_dict() == {
        "0": "contradiction",
        "1": "entailment",
        "2": "neutral",
    }

    # Test inference output and precision
    pairs = [
        ("The dog is running in the park.", "An animal is outside."),
        ("The door is firmly closed.", "The door is open."),
    ]
    preds = evaluator.predict(pairs)
    assert len(preds) == 2
    assert preds[0].argmax_label == "entailment"
    assert preds[0].entailment >= 0.95
    # Verify probabilities rounded to 4 decimals per Section 4
    assert round(preds[0].entailment, 4) == preds[0].entailment

    assert preds[1].argmax_label == "contradiction"
    assert preds[1].contradiction >= 0.95


def test_nli_invalid_id2label_fails():
    """Model load must fail if id2label does not have contradiction, entailment, neutral."""
    with pytest.raises(ValueError, match="id2label"):
        NLIEvaluator(
            model_name="cross-encoder/nli-distilroberta-base",
            id2label_override={"0": "label_0", "1": "label_1", "2": "label_2"},
            local_files_only=True,
        )
