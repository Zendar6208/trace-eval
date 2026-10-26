"""Tests for canonical JSON serialization conforming to Methodology Section 8.1."""

import hashlib
import json
import math
from pathlib import Path

import pytest
from pydantic import BaseModel

from trace_eval.canonical import canonical_json

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class SampleModel(BaseModel):
    name: str
    score: float | None = None
    count: int = 0
    active: bool = True


def test_golden_canonical_fixtures():
    """Verify canonical serialization against committed golden fixtures."""
    golden_file = FIXTURES_DIR / "golden_canonical.json"
    assert golden_file.exists(), f"Missing golden fixture file: {golden_file}"

    cases = json.loads(golden_file.read_text(encoding="utf-8"))
    for case in cases:
        raw_input = case["input"]
        expected_hex = case["expected_canonical_bytes_hex"]
        expected_sha256 = case["expected_sha256"]

        serialized = canonical_json(raw_input)
        assert serialized.hex() == expected_hex, f"Mismatch in bytes for case: {case['name']}"

        digest = hashlib.sha256(serialized).hexdigest()
        assert digest == expected_sha256, f"Mismatch in SHA-256 for case: {case['name']}"


def test_dict_key_ordering():
    """Ensure dictionary keys are strictly sorted by Unicode code point."""
    obj1 = {"c": 3, "a": 1, "b": 2}
    obj2 = {"b": 2, "c": 3, "a": 1}
    assert canonical_json(obj1) == b'{"a":1,"b":2,"c":3}'
    assert canonical_json(obj1) == canonical_json(obj2)


def test_unicode_nfc_normalization():
    """Ensure strings and keys in NFD are normalized to NFC."""
    # 'e' + combining acute accent (NFD)
    nfd_key = "cafe\u0301"
    nfc_key = "caf\u00e9"
    nfd_val = "re\u0301sume\u0301"
    nfc_val = "r\u00e9sum\u00e9"

    serialized = canonical_json({nfd_key: nfd_val})
    expected = canonical_json({nfc_key: nfc_val})
    assert serialized == expected
    assert nfc_key.encode("utf-8") in serialized
    assert nfc_val.encode("utf-8") in serialized


def test_unicode_key_collision_after_nfc():
    """If two distinct NFD/NFC keys normalize to identical NFC, raise ValueError."""
    collision_dict = {"caf\u00e9": 1, "cafe\u0301": 2}
    with pytest.raises(ValueError, match="Duplicate dictionary key"):
        canonical_json(collision_dict)


def test_whitespace_handling():
    """Ensure zero insignificant whitespace is present in JSON output."""
    obj = {"key": [1, 2, 3], "nested": {"a": "value with spaces"}}
    raw_bytes = canonical_json(obj)
    # Inside strings, spaces are preserved; outside strings, no spaces after ',' or ':'
    assert b'{"key":[1,2,3],"nested":{"a":"value with spaces"}}' == raw_bytes


def test_integer_vs_float_distinction():
    """Integers and whole-number floats must stay strictly distinct (1 vs 1.0)."""
    assert canonical_json(1) == b"1"
    assert canonical_json(1.0) == b"1.0"
    assert canonical_json({"a": 1}) == b'{"a":1}'
    assert canonical_json({"a": 1.0}) == b'{"a":1.0}'
    assert canonical_json({"a": 1}) != canonical_json({"a": 1.0})


def test_float_rounding():
    """Floats must be rounded to exactly 6 decimal places."""
    assert canonical_json({"f": 1.2345678}) == b'{"f":1.234568}'
    assert canonical_json({"f": 1.2345674}) == b'{"f":1.234567}'
    assert canonical_json({"f": 0.123456}) == b'{"f":0.123456}'


def test_negative_zero_normalization():
    """Negative zero (-0.0) must normalize to positive zero (0.0)."""
    neg_zero = -0.0
    assert math.copysign(1.0, neg_zero) == -1.0  # confirms IEEE negative zero
    serialized = canonical_json({"zero": neg_zero})
    assert serialized == b'{"zero":0.0}'
    assert serialized == canonical_json({"zero": 0.0})


def test_null_inclusion():
    """Null fields must be serialized as JSON null and never omitted."""
    assert canonical_json(None) == b"null"
    assert (
        canonical_json({"missing": None, "present": "yes"}) == b'{"missing":null,"present":"yes"}'
    )


def test_pydantic_model_serialization_with_nulls():
    """Pydantic model dumping includes null fields explicitly."""
    model = SampleModel(name="test", score=None, count=5, active=False)
    serialized = canonical_json(model)
    assert serialized == b'{"active":false,"count":5,"name":"test","score":null}'


def test_nan_and_infinity_rejection():
    """NaN, +Inf, -Inf must be rejected with ValueError."""
    with pytest.raises(ValueError, match="Non-finite float value"):
        canonical_json(float("nan"))
    with pytest.raises(ValueError, match="Non-finite float value"):
        canonical_json(float("inf"))
    with pytest.raises(ValueError, match="Non-finite float value"):
        canonical_json(float("-inf"))
    with pytest.raises(ValueError, match="Non-finite float value"):
        canonical_json({"val": float("nan")})


def test_unsupported_types():
    """Tuples, sets, and non-string dictionary keys must raise TypeError."""
    with pytest.raises(TypeError, match="Unsupported type"):
        canonical_json((1, 2, 3))
    with pytest.raises(TypeError, match="Unsupported type"):
        canonical_json({1, 2, 3})
    with pytest.raises(TypeError, match="Dictionary keys must be strings"):
        canonical_json({1: "val"})


def test_repeatability():
    """Multiple serialization runs on complex objects must be bit-for-bit identical."""
    complex_obj = {
        "dataset": "benchmark_v1",
        "nested": [{"id": i, "score": i / 3.0, "text": f"text_{i}"} for i in range(10)],
        "active": True,
        "notes": None,
    }
    first_run = canonical_json(complex_obj)
    for _ in range(50):
        assert canonical_json(complex_obj) == first_run
