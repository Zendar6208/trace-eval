"""Tests for JSON Schema generation, export, and drift detection."""

import json
from pathlib import Path

from trace_eval.schema.export import SCHEMA_MODELS, check_schema_drift, generate_json_schemas

SCHEMA_DIR = Path(__file__).parent.parent / "schema"


def test_schema_drift_check():
    """Verify that committed /schema/*.json files match currently generated schemas exactly."""
    assert SCHEMA_DIR.exists(), f"Schema directory does not exist: {SCHEMA_DIR}"
    in_sync, diffs = check_schema_drift(SCHEMA_DIR)
    assert in_sync, "Schema drift detected:\n" + "\n".join(diffs)


def test_generated_json_schemas_are_valid_json():
    """Verify that each exported schema is valid JSON containing standard JSON schema fields."""
    schemas = generate_json_schemas()
    assert len(schemas) == len(SCHEMA_MODELS)

    for filename, content in schemas.items():
        parsed = json.loads(content)
        assert "$defs" in parsed or "properties" in parsed or "title" in parsed
        assert (SCHEMA_DIR / filename).exists(), f"Missing schema file on disk: {filename}"


def test_detects_drift_when_tampered(tmp_path):
    """Ensure check_schema_drift flags discrepancies if disk files are modified."""
    # Write empty file
    tampered_file = tmp_path / "trace_dataset_v1.json"
    tampered_file.write_text("{}", encoding="utf-8")

    in_sync, diffs = check_schema_drift(tmp_path)
    assert not in_sync
    assert any("Schema drift detected" in d for d in diffs)
