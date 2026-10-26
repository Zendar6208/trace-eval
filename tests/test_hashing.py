"""Tests for cryptographic content and result hashing conforming to Sections 8.2 & 8.3."""

import copy
import json
from pathlib import Path

from trace_eval.hashing import (
    compute_run_hashes,
    extract_run_core,
    hash_dataset,
    hash_labels,
    hash_submission,
    verify_run_hashes,
)
from trace_eval.schema.dataset import Dataset
from trace_eval.schema.run import RunResult

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> dict:
    path = FIXTURES_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def test_golden_hashes_match_committed_values():
    """Verify that committed golden fixtures produce exact committed SHA-256 digests."""
    golden_hashes = load_fixture("golden_hashes.json")

    dataset_data = load_fixture("golden_dataset.json")
    assert hash_dataset(dataset_data) == golden_hashes["dataset_content_sha256"]

    submission_data = load_fixture("golden_submission.json")
    assert hash_submission(submission_data) == golden_hashes["submission_content_sha256"]

    labels_data = load_fixture("golden_labels.json")
    assert hash_labels(labels_data) == golden_hashes["labels_content_sha256"]

    run_data = load_fixture("golden_run.json")
    result_hash, run_id = compute_run_hashes(run_data)
    assert result_hash == golden_hashes["run_result_hash"]
    assert run_id == golden_hashes["run_id"]
    assert run_id == result_hash[:16]
    assert verify_run_hashes(run_data)


def test_corrected_m0_golden_hashes():
    """Verify that versioned corrected fixtures with calibration and graded relevance match expected digests."""
    corrected_hashes = load_fixture("golden_hashes_m0_corrected.json")

    dataset_data = load_fixture("golden_dataset_m0_corrected.json")
    dataset_model = Dataset.model_validate(dataset_data)
    assert hash_dataset(dataset_model) == corrected_hashes["dataset_content_sha256"]

    run_data = load_fixture("golden_run_m0_corrected.json")
    run_model = RunResult.model_validate(run_data)
    result_hash, run_id = compute_run_hashes(run_model)
    assert result_hash == corrected_hashes["run_result_hash"]
    assert run_id == corrected_hashes["run_id"]
    assert verify_run_hashes(run_model)


def test_dataset_hashing_field_exclusion_and_sensitivity():
    """Dataset hash includes {schema_version, dataset_id, language, corpus, items}; excludes name, description, license."""
    base_data = load_fixture("golden_dataset.json")
    base_hash = hash_dataset(base_data)

    # Modifying excluded fields MUST NOT change hash
    data_mod_excluded = copy.deepcopy(base_data)
    data_mod_excluded["name"] = "Completely Altered Dataset Name"
    data_mod_excluded["description"] = "New description that should not affect content hash"
    data_mod_excluded["license"] = "MIT"
    assert hash_dataset(data_mod_excluded) == base_hash

    # Modifying included fields MUST change hash
    data_mod_item = copy.deepcopy(base_data)
    data_mod_item["items"][0]["question"] = "Different question text?"
    assert hash_dataset(data_mod_item) != base_hash

    data_mod_corpus = copy.deepcopy(base_data)
    data_mod_corpus["corpus"][0]["text"] = "Different corpus text"
    assert hash_dataset(data_mod_corpus) != base_hash


def test_submission_hashing_field_exclusion_and_sensitivity():
    """Submission hash includes {schema_version, dataset_id, outputs}; excludes system."""
    base_data = load_fixture("golden_submission.json")
    base_hash = hash_submission(base_data)

    # Modifying system metadata MUST NOT change hash
    data_mod_system = copy.deepcopy(base_data)
    data_mod_system["system"]["name"] = "DifferentPipelineName"
    data_mod_system["system"]["version"] = "v999.0"
    data_mod_system["system"]["provenance"]["model_name"] = "different-model"
    assert hash_submission(data_mod_system) == base_hash

    # Modifying outputs MUST change hash
    data_mod_output = copy.deepcopy(base_data)
    data_mod_output["outputs"][0]["answer"] = "Different answer text."
    assert hash_submission(data_mod_output) != base_hash

    data_mod_retrieved = copy.deepcopy(base_data)
    data_mod_retrieved["outputs"][0]["retrieved"] = []
    assert hash_submission(data_mod_retrieved) != base_hash


def test_labels_hashing_field_exclusion_and_sensitivity():
    """Labels hash includes entire document except annotator_notes."""
    base_data = load_fixture("golden_labels.json")
    base_hash = hash_labels(base_data)

    # Modifying annotator_notes MUST NOT change hash
    data_mod_notes = copy.deepcopy(base_data)
    data_mod_notes["annotator_notes"] = "These notes should be excluded from content hash."
    assert hash_labels(data_mod_notes) == base_hash

    # Modifying sentence labels MUST change hash
    data_mod_label = copy.deepcopy(base_data)
    data_mod_label["items"][0]["sentences"][0]["grounding_label"] = "unsupported"
    assert hash_labels(data_mod_label) != base_hash


def test_run_result_hashing_non_deterministic_exclusion():
    """Run result hash strictly excludes run_id, result_hash, runtime_status, environment, system, input_origin_summary."""
    base_data = load_fixture("golden_run.json")
    base_result_hash, base_run_id = compute_run_hashes(base_data)

    # Modifying excluded runtime/environment metadata MUST NOT change result hash
    data_mod_env = copy.deepcopy(base_data)
    data_mod_env["runtime_status"] = "live"
    data_mod_env["run_id"] = "modified_run_id_00"
    data_mod_env["result_hash"] = "modified_result_hash_value"
    data_mod_env["environment"]["timestamp"] = "2099-01-01T00:00:00Z"
    data_mod_env["environment"]["hostname"] = "different-cluster-node"
    data_mod_env["environment"]["duration_seconds"] = 999.99
    data_mod_env["input_origin_summary"]["total_count"] = 9999

    new_result_hash, new_run_id = compute_run_hashes(data_mod_env)
    assert new_result_hash == base_result_hash
    assert new_run_id == base_run_id

    # Modifying semantic core fields MUST change result hash
    data_mod_summary = copy.deepcopy(base_data)
    data_mod_summary["summary"]["combined"]["mean_token_f1"] = 0.999999
    mod_result_hash, _ = compute_run_hashes(data_mod_summary)
    assert mod_result_hash != base_result_hash

    data_mod_config = copy.deepcopy(base_data)
    data_mod_config["config"]["thresholds"]["entail"] = 0.85
    config_result_hash, _ = compute_run_hashes(data_mod_config)
    assert config_result_hash != base_result_hash


def test_mutation_safety():
    """Hashing functions must never modify their input arguments."""
    base_data = load_fixture("golden_run.json")
    snapshot = copy.deepcopy(base_data)

    _ = compute_run_hashes(base_data)
    _ = extract_run_core(base_data)

    assert base_data == snapshot, "Input data was mutated by hashing functions!"
