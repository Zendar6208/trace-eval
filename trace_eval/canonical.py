"""TRACE-specific canonical JSON serialization conforming to Methodology Section 8.1.

This implementation guarantees:
- Unicode NFC normalization on all strings and dictionary keys.
- Sorted dictionary keys by Unicode code point.
- Rejection of non-string dictionary keys.
- Finite floating-point values only (strict rejection of NaN and infinity).
- Six-decimal rounding for all floating-point values.
- Normalization of negative zero (-0.0 -> 0.0).
- Preservation of integer versus floating-point types (e.g. 1 vs 1.0).
- Zero insignificant whitespace (separators=(',', ':')).
- UTF-8 encoding with no ASCII escaping.
- Pydantic v2 model compatibility (model_dump(mode='json') with nulls included).

Note: This is a TRACE-specific canonical form and does NOT claim RFC 8785 (JCS) compliance.
"""

from __future__ import annotations

import json
import math
import unicodedata
from typing import Any


def _normalize_and_validate(obj: Any) -> Any:
    """Recursively validate types and prepare object for canonical JSON serialization."""
    # Check for Pydantic models
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        obj = obj.model_dump(mode="json")

    # In Python, bool is a subclass of int. Check bool first!
    if isinstance(obj, bool):
        return obj

    if isinstance(obj, int):
        return obj

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"Non-finite float value ({obj}) is not allowed in canonical JSON")
        # Round to 6 decimal places per Section 8.1
        rounded = round(obj, 6)
        # Normalize negative zero to positive zero
        if rounded == 0.0:
            rounded = 0.0
        return rounded

    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)

    if obj is None:
        return None

    if isinstance(obj, list):
        return [_normalize_and_validate(item) for item in obj]

    if isinstance(obj, dict):
        normalized_dict: dict[str, Any] = {}
        # Keys must be strings and NFC-normalized
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(f"Dictionary keys must be strings, got {type(k).__name__}: {k!r}")
            norm_k = unicodedata.normalize("NFC", k)
            if norm_k in normalized_dict:
                raise ValueError(
                    f"Duplicate dictionary key after Unicode NFC normalization: {norm_k!r}"
                )
            normalized_dict[norm_k] = _normalize_and_validate(v)
        return normalized_dict

    raise TypeError(
        f"Unsupported type for canonical JSON serialization: {type(obj).__name__} ({obj!r})"
    )


def canonical_json(obj: Any) -> bytes:
    """Serialize an object into canonical JSON bytes per TRACE Methodology v1.0.0 Section 8.1.

    Args:
        obj: The object to serialize (dict, list, str, int, bool, None, float, or Pydantic model).

    Returns:
        Canonical UTF-8 encoded bytes.

    Raises:
        TypeError: If an unsupported type or non-string dictionary key is encountered.
        ValueError: If non-finite float (NaN or inf) or NFC key collision occurs.
    """
    prepared = _normalize_and_validate(obj)
    # separators=(',', ':') removes whitespace after commas and colons.
    # sort_keys=True ensures keys are sorted by Unicode code point.
    # ensure_ascii=False ensures UTF-8 output without \uXXXX escaping.
    # allow_nan=False ensures strict rejection of any non-finite floats.
    json_str = json.dumps(
        prepared,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return json_str.encode("utf-8")
