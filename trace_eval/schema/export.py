"""JSON Schema export and drift detection for TRACE AI data contracts.

This module generates canonical JSON Schemas from Pydantic v2 models directly into
the /schema/ directory, ensuring schemas remain synchronized with code without
manual duplication.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from trace_eval.schema.comparison import ComparisonResult
from trace_eval.schema.dataset import Dataset
from trace_eval.schema.labels import LabelsDocument
from trace_eval.schema.run import RunResult
from trace_eval.schema.submission import Submission

if TYPE_CHECKING:
    from pydantic import BaseModel

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "trace_dataset_v1.json": Dataset,
    "trace_submission_v1.json": Submission,
    "trace_labels_v1.json": LabelsDocument,
    "trace_run_v1.json": RunResult,
    "trace_comparison_v1.json": ComparisonResult,
}


def generate_json_schemas() -> dict[str, str]:
    """Generate deterministic formatted JSON Schema strings for all models."""
    schemas: dict[str, str] = {}
    for filename, model in SCHEMA_MODELS.items():
        schema_dict = model.model_json_schema()
        # Clean formatted JSON with 2-space indentation and newline
        formatted = json.dumps(schema_dict, indent=2, sort_keys=True) + "\n"
        schemas[filename] = formatted
    return schemas


def export_schemas(output_dir: Path | str) -> dict[str, Path]:
    """Write generated JSON Schemas to disk."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    generated = generate_json_schemas()
    written: dict[str, Path] = {}

    for filename, content in generated.items():
        file_path = out_path / filename
        file_path.write_text(content, encoding="utf-8")
        written[filename] = file_path

    return written


def check_schema_drift(schema_dir: Path | str) -> tuple[bool, list[str]]:
    """Check if committed schema files differ from freshly generated schemas.

    Returns:
        (is_in_sync: bool, diff_messages: list[str])
    """
    s_path = Path(schema_dir)
    generated = generate_json_schemas()
    diffs: list[str] = []

    for filename, expected_content in generated.items():
        file_path = s_path / filename
        if not file_path.exists():
            diffs.append(f"Schema file missing on disk: {file_path}")
            continue

        disk_content = file_path.read_text(encoding="utf-8")
        if disk_content != expected_content:
            diffs.append(
                f"Schema drift detected in {file_path}. Run 'python -m trace_eval.schema.export' to regenerate."
            )

    return len(diffs) == 0, diffs


def main() -> int:
    """CLI entrypoint for exporting or verifying schemas."""
    parser = argparse.ArgumentParser(description="Export or verify TRACE JSON Schemas")
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="schema",
        help="Directory to write or check schema files (default: 'schema')",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for schema drift without overwriting files; exits with 1 on drift",
    )

    args = parser.parse_args()
    target_dir = Path(args.output_dir)

    if args.check:
        in_sync, diffs = check_schema_drift(target_dir)
        if in_sync:
            print(f"All schemas in '{target_dir}' are in sync with Pydantic models.")
            return 0
        else:
            print("SCHEMA DRIFT DETECTED:")
            for d in diffs:
                print(f"  - {d}")
            return 1
    else:
        written = export_schemas(target_dir)
        print(f"Exported {len(written)} schemas to '{target_dir}':")
        for name, p in written.items():
            print(f"  - {name} -> {p}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
