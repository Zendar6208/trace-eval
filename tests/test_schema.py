"""Tests for TRACE AI versioned data contracts and schema validations."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from trace_eval.schema.comparison import ComparisonResult
from trace_eval.schema.dataset import Dataset, DatasetItem, Passage, RequiredFact
from trace_eval.schema.labels import LabelsDocument
from trace_eval.schema.run import RunResult
from trace_eval.schema.submission import Submission

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> dict:
    path = FIXTURES_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


# --- 1. Valid Model Loading ---


def test_valid_dataset():
    data = load_fixture("golden_dataset.json")
    model = Dataset.model_validate(data)
    assert model.schema_version == "trace.dataset/1.0"
    assert model.dataset_id == "sample-finance-benchmark"
    assert len(model.items) == 2
    assert len(model.corpus) == 2


def test_valid_submission():
    data = load_fixture("golden_submission.json")
    model = Submission.model_validate(data)
    assert model.schema_version == "trace.submission/1.0"
    assert model.system.name == "ProductionRAG"
    assert len(model.outputs) == 2


def test_valid_labels():
    data = load_fixture("golden_labels.json")
    model = LabelsDocument.model_validate(data)
    assert model.schema_version == "trace.labels/1.0"
    assert len(model.items) == 2


def test_valid_run():
    data = load_fixture("golden_run.json")
    model = RunResult.model_validate(data)
    assert model.schema_version == "trace.run/1.0"
    assert model.methodology_version == "1.0.0"
    assert model.runtime_status == "loaded"


def test_valid_comparison():
    data = load_fixture("golden_comparison.json")
    model = ComparisonResult.model_validate(data)
    assert model.schema_version == "trace.comparison/1.0"
    assert model.comparison_id == "comp-baseline-vs-candidate"
    assert len(model.item_comparisons) == 2


# --- 2. Schema Version Rejection ---


@pytest.mark.parametrize(
    ("model_cls", "fixture_name"),
    [
        (Dataset, "golden_dataset.json"),
        (Submission, "golden_submission.json"),
        (LabelsDocument, "golden_labels.json"),
        (RunResult, "golden_run.json"),
        (ComparisonResult, "golden_comparison.json"),
    ],
)
def test_unsupported_schema_version_rejected(model_cls, fixture_name):
    data = load_fixture(fixture_name)
    data["schema_version"] = "trace.unsupported/99.0"
    with pytest.raises(ValidationError, match="Unsupported schema version"):
        model_cls.model_validate(data)


# --- 3. Missing Required Fields ---


def test_missing_required_fields():
    # Missing dataset_id
    data = load_fixture("golden_dataset.json")
    del data["dataset_id"]
    with pytest.raises(ValidationError):
        Dataset.model_validate(data)

    # Missing question in item
    data2 = load_fixture("golden_dataset.json")
    del data2["items"][0]["question"]
    with pytest.raises(ValidationError):
        Dataset.model_validate(data2)


# --- 4. Duplicate IDs Validation ---


def test_duplicate_passage_id_rejected():
    data = load_fixture("golden_dataset.json")
    # Duplicate passage ID 'p01'
    data["corpus"].append({"id": "p01", "text": "Duplicate passage body"})
    with pytest.raises(ValidationError, match="Duplicate passage ID 'p01'"):
        Dataset.model_validate(data)


def test_duplicate_item_id_rejected():
    data = load_fixture("golden_dataset.json")
    dup_item = copy.deepcopy(data["items"][0])
    data["items"].append(dup_item)
    with pytest.raises(ValidationError, match="Duplicate item ID"):
        Dataset.model_validate(data)


def test_duplicate_fact_id_rejected():
    with pytest.raises(ValidationError, match="Duplicate fact_id"):
        DatasetItem(
            id="item-test",
            group_id="grp",
            split="dev",
            question="Q?",
            required_facts=[
                RequiredFact(fact_id="f1", text="fact one"),
                RequiredFact(fact_id="f1", text="fact one duplicate"),
            ],
        )


def test_gold_passage_not_in_corpus_rejected():
    data = load_fixture("golden_dataset.json")
    data["items"][0]["gold_passage_ids"] = ["nonexistent_passage_999"]
    with pytest.raises(
        ValidationError,
        match="references gold passage ID 'nonexistent_passage_999' not found in corpus",
    ):
        Dataset.model_validate(data)


# --- 5. Provenance Constraints ---


def test_synthetic_fixture_requires_note():
    data = load_fixture("golden_submission.json")
    # synthetic_fixture with empty or None fixture_note
    data["outputs"][1]["fixture_note"] = None
    with pytest.raises(ValidationError, match="missing mandatory 'fixture_note'"):
        Submission.model_validate(data)

    data["outputs"][1]["fixture_note"] = "   "
    with pytest.raises(ValidationError, match="missing mandatory 'fixture_note'"):
        Submission.model_validate(data)


def test_recorded_system_requires_provenance():
    data = load_fixture("golden_submission.json")
    # Remove provenance while outputs contain recorded_system items
    data["system"]["provenance"] = None
    with pytest.raises(
        ValidationError,
        match="Submission contains 'recorded_system' outputs, but 'system.provenance' is missing",
    ):
        Submission.model_validate(data)


# --- 6. Split Constraints ---


def test_invalid_split_rejected():
    data = load_fixture("golden_dataset.json")
    data["items"][0]["split"] = "train"  # only 'dev' or 'test' allowed
    with pytest.raises(ValidationError):
        Dataset.model_validate(data)


# --- 7. Passage ID Regex ---


def test_invalid_passage_id_format():
    with pytest.raises(ValidationError, match="does not match required format"):
        Passage(id="invalid id with spaces!", text="some text")


# --- 8. Labels Contract Validations ---


def test_duplicate_sentence_index_in_labels_rejected():
    data = load_fixture("golden_labels.json")
    dup_sentence = copy.deepcopy(data["items"][0]["sentences"][0])
    data["items"][0]["sentences"].append(dup_sentence)
    with pytest.raises(ValidationError, match="Duplicate sentence_index"):
        LabelsDocument.model_validate(data)


def test_duplicate_item_in_labels_rejected():
    data = load_fixture("golden_labels.json")
    dup_item = copy.deepcopy(data["items"][0])
    data["items"].append(dup_item)
    with pytest.raises(ValidationError, match="Duplicate item_id"):
        LabelsDocument.model_validate(data)


# --- 9. Round-Trip Validation ---


def test_round_trip_serialization():
    """Ensure all schemas can serialize to dict and validate back without information loss."""
    for fixture in [
        "golden_dataset.json",
        "golden_submission.json",
        "golden_labels.json",
        "golden_run.json",
        "golden_comparison.json",
    ]:
        raw_json = load_fixture(fixture)
        if "dataset" in fixture:
            m = Dataset.model_validate(raw_json)
            assert Dataset.model_validate(m.model_dump(mode="json")) == m
        elif "submission" in fixture:
            m = Submission.model_validate(raw_json)
            assert Submission.model_validate(m.model_dump(mode="json")) == m
        elif "labels" in fixture:
            m = LabelsDocument.model_validate(raw_json)
            assert LabelsDocument.model_validate(m.model_dump(mode="json")) == m
        elif "run" in fixture:
            m = RunResult.model_validate(raw_json)
            assert RunResult.model_validate(m.model_dump(mode="json")) == m
        elif "comparison" in fixture:
            m = ComparisonResult.model_validate(raw_json)
            assert ComparisonResult.model_validate(m.model_dump(mode="json")) == m
