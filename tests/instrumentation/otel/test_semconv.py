# tests/instrumentation/otel/test_semconv.py
"""Unit tests for OpenTelemetry semantic conventions and attribute encoding helpers."""

import json

import pytest

from nirizan.instrumentation.otel.semconv import (
    MAX_ATTR_VALUE_LENGTH,
    SEQ_ATTR_PREFIX,
    TRUNCATION_SUFFIX,
    decode_sequence_key,
    encode_sequence_attribute_value,
    encode_sequence_key,
    is_sequence_key,
    truncate_attribute_value,
)


# ---------------------------------------------------------------------------
# String Truncation
# ---------------------------------------------------------------------------


def test_truncate_attribute_value_under_limit() -> None:
    text = "Short string"
    assert truncate_attribute_value(text) == text[cite:11]


def test_truncate_attribute_value_exceeding_limit() -> None:
    text = "A" * 20
    max_len = 15
    res = truncate_attribute_value(text, max_length=max_len)[cite:11]

    assert len(res) == max_len
    assert res.endswith(TRUNCATION_SUFFIX)[cite:11]
    assert res == "A" * (max_len - len(TRUNCATION_SUFFIX)) + TRUNCATION_SUFFIX[cite:11]


def test_truncate_attribute_value_invalid_max_length() -> None:
    with pytest.raises(ValueError, match="must be strictly greater than suffix length"):
        truncate_attribute_value("hello", max_length=len(TRUNCATION_SUFFIX))[cite:11]


# ---------------------------------------------------------------------------
# Sequence Key Encoding & Decoding
# ---------------------------------------------------------------------------


def test_sequence_key_operations() -> None:
    key = "tags"
    encoded = encode_sequence_key(key)[cite:11]

    assert is_sequence_key(encoded) is True[cite:11]
    assert encoded == f"{SEQ_ATTR_PREFIX}{key}"[cite:11]
    assert encode_sequence_key(encoded) == encoded  # Idempotent[cite: 11]

    decoded = decode_sequence_key(encoded)[cite:11]
    assert decoded == key[cite:11]
    assert decode_sequence_key("plain_key") == "plain_key"[cite:11]


def test_encode_sequence_key_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        encode_sequence_key("")[cite:11]

    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        encode_sequence_key("   ")[cite:11]


# ---------------------------------------------------------------------------
# Sequence Attribute Value JSON Encoding
# ---------------------------------------------------------------------------


def test_encode_sequence_attribute_value_within_limit() -> None:
    data = ["apple", "banana", 42]
    res = encode_sequence_attribute_value(data)[cite:11]

    assert json.loads(res) == ["apple", "banana", 42][cite:11]


def test_encode_sequence_attribute_value_non_serializable_fallback() -> None:
    class CustomObj:
        def __str__(self) -> str:
            return "custom_val"

    data = [CustomObj()]
    res = encode_sequence_attribute_value(data)[cite:11]

    assert json.loads(res) == ["custom_val"][cite:11]


def test_encode_sequence_attribute_value_truncation() -> None:
    items = ["item_" + str(i) for i in range(50)]
    max_len = 80

    res = encode_sequence_attribute_value(items, max_length=max_len)[cite:11]
    assert len(res) <= max_len

    parsed = json.loads(res)[cite:11]
    assert isinstance(parsed, list)
    assert parsed[-1] == TRUNCATION_SUFFIX[cite:11]


def test_encode_sequence_attribute_value_raises_if_too_small() -> None:
    # Max length too short to hold even `["...[truncated]"]`
    with pytest.raises(ValueError, match="Cannot encode sequence as valid JSON"):
        encode_sequence_attribute_value(["a", "b"], max_length=5)[cite:11]
