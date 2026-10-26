"""Unit tests for sentence segmentation and claim identification conforming to Methodology Section 2.3 and 2.5."""

from trace_eval.claims import identify_sentences, split_sentences_raw


def test_sentence_segmentation_soft_boundaries():
    text = "First sentence. Second sentence! Third sentence? Fourth sentence."
    sentences = split_sentences_raw(text)
    assert len(sentences) == 4
    texts = [s[2] for s in sentences]
    assert texts == [
        "First sentence.",
        "Second sentence!",
        "Third sentence?",
        "Fourth sentence.",
    ]


def test_sentence_segmentation_protected_abbreviations():
    # Protected: dr, mr, prof, e.g, i.e, approx, st, fig
    text = "Dr. Smith met with Prof. Jones at 10 a.m. approx. yesterday. They discussed e.g. the new policy."
    sentences = split_sentences_raw(text)
    assert len(sentences) == 2
    assert "Dr. Smith met with Prof. Jones" in sentences[0][2]
    assert "They discussed e.g. the new policy." in sentences[1][2]


def test_sentence_segmentation_decimals_and_numbers():
    text = "The price increased from $10.50 to $12.75 in v1.0.0 today. This is expected."
    sentences = split_sentences_raw(text)
    assert len(sentences) == 2
    assert "$10.50 to $12.75 in v1.0.0" in sentences[0][2]


def test_sentence_segmentation_hard_boundaries():
    text = "Introductory paragraph.\n\nList items:\n- First item.\n- Second item."
    sentences = split_sentences_raw(text)
    assert len(sentences) == 4
    assert sentences[0][2] == "Introductory paragraph."
    assert sentences[1][2] == "List items:"
    assert "First item." in sentences[2][2]
    assert "Second item." in sentences[3][2]


def test_single_newline_becomes_space():
    text = "This is a single sentence\nthat spans across two lines."
    claims = identify_sentences(text)
    assert len(claims) == 1
    assert claims[0].clean_text == "This is a single sentence that spans across two lines."


def test_claim_classification_refusal():
    text = "I do not have enough information to answer this question from the context."
    claims = identify_sentences(text)
    assert len(claims) == 1
    assert claims[0].is_refusal is True
    # Refusals are not claims per Section 2.5(a)
    assert claims[0].is_claim is False
    assert claims[0].is_assessable is False


def test_claim_classification_non_claim():
    text = "Sure. Here is the answer: Refunds take 30 days."
    claims = identify_sentences(text)
    # "Sure." matches non_claim_patterns per Section 2.5(c)
    assert claims[0].is_non_claim is True
    assert claims[0].is_claim is False


def test_claim_classification_unassessable():
    text = "Yes. Refunds take 30 days."
    claims = identify_sentences(text)
    assert len(claims) == 2
    # "Yes." has 1 word token (< 3), so not_assessable per Section 2.5
    assert claims[0].token_count < 3
    assert claims[0].is_assessable is False

    # Second sentence has >= 3 tokens, so assessable
    assert claims[1].token_count >= 3
    assert claims[1].is_assessable is True


def test_claim_classification_no_alnum():
    text = "... !!! Refunds take 30 days."
    claims = identify_sentences(text)
    # The first segment has no alphanumeric content, so not a claim per Section 2.5(b)
    for c in claims:
        if not any(ch.isalnum() for ch in c.clean_text):
            assert c.is_claim is False
