# tests/instrumentation/otel/test_semconv.py
"""Unit tests for OpenTelemetry semantic conventions and attribute encoding helpers.

``semconv.py`` is a pure, stateless module of constants and small pure
functions. Tests below focus on invariants, boundary conditions, and
regression protection for the encode/decode helpers and the truncation logic.
Categories that do not apply (state transitions, side effects, resource
cleanup, async behaviour, external dependencies) are intentionally absent.
"""

import json

import pytest

from nirizan.instrumentation.otel.semconv import (
    MAX_ATTR_VALUE_LENGTH,
    SEMCONV_VERSION,
    SEQ_ATTR_PREFIX,
    TRUNCATION_SUFFIX,
    decode_sequence_key,
    encode_sequence_attribute_value,
    encode_sequence_key,
    is_sequence_key,
    truncate_attribute_value,
)


# ---------------------------------------------------------------------------
# Constant invariants (regression protection)
# ---------------------------------------------------------------------------


def test_prefix_and_suffix_constants_are_frozen() -> None:
    """These strings appear in persisted span attributes.

    Changing either breaks round-trip decoding for every previously-recorded
    sequence attribute or truncated value.
    """
    assert SEQ_ATTR_PREFIX == "nirizan.seq."
    assert TRUNCATION_SUFFIX == "...[truncated]"


def test_max_attr_value_length_default_is_1024() -> None:
    """The default limit is part of the module's public contract."""
    assert MAX_ATTR_VALUE_LENGTH == 1024


def test_semconv_version_is_pinned() -> None:
    """The tracked upstream version is documented and versioned deliberately."""
    assert SEMCONV_VERSION == "1.27.0"


# ---------------------------------------------------------------------------
# String truncation
# ---------------------------------------------------------------------------


def test_truncate_attribute_value_under_limit_returns_input_unchanged() -> None:
    text = "Short string"
    assert truncate_attribute_value(text) == text


def test_truncate_attribute_value_exactly_at_limit_returns_input_unchanged() -> None:
    """A value exactly max_length characters long must not be modified."""
    text = "A" * 100
    assert truncate_attribute_value(text, max_length=100) == text


def test_truncate_attribute_value_one_over_limit_truncates() -> None:
    """The first length that triggers truncation is max_length + 1."""
    max_len = 30
    text = "A" * (max_len + 1)
    result = truncate_attribute_value(text, max_length=max_len)

    assert len(result) == max_len
    assert result.endswith(TRUNCATION_SUFFIX)
    assert result == "A" * (max_len - len(TRUNCATION_SUFFIX)) + TRUNCATION_SUFFIX


def test_truncate_attribute_value_preserves_unicode_code_points() -> None:
    """Truncation counts characters, not bytes, per the documented note."""
    # Emoji are multi-byte in UTF-8 but single code points in Python.
    text = "\U0001f680" * 50  # 50 rocket emoji
    result = truncate_attribute_value(text, max_length=20)

    assert len(result) == 20
    assert result.endswith(TRUNCATION_SUFFIX)


def test_truncate_attribute_value_rejects_max_length_at_or_below_suffix() -> None:
    """max_length must leave room for the suffix plus at least one character."""
    suffix_len = len(TRUNCATION_SUFFIX)
    with pytest.raises(ValueError, match="must be strictly greater than suffix length"):
        truncate_attribute_value("hello", max_length=suffix_len)

    with pytest.raises(ValueError, match="must be strictly greater than suffix length"):
        truncate_attribute_value("hello", max_length=suffix_len - 1)

    with pytest.raises(ValueError, match="must be strictly greater than suffix length"):
        truncate_attribute_value("hello", max_length=0)


# ---------------------------------------------------------------------------
# Sequence key encode/decode round trip
# ---------------------------------------------------------------------------


def test_encode_sequence_key_adds_prefix() -> None:
    assert encode_sequence_key("tags") == f"{SEQ_ATTR_PREFIX}tags"


def test_encode_sequence_key_is_idempotent() -> None:
    """Encoding an already-encoded key returns it unchanged."""
    once = encode_sequence_key("tags")
    assert encode_sequence_key(once) == once


def test_decode_sequence_key_strips_prefix() -> None:
    assert decode_sequence_key(f"{SEQ_ATTR_PREFIX}tags") == "tags"


def test_decode_sequence_key_passthrough_for_unprefixed_key() -> None:
    """A key that never had the prefix is returned unchanged."""
    assert decode_sequence_key("plain_key") == "plain_key"


def test_sequence_key_round_trip() -> None:
    """encode(decode(x)) == x for prefixed keys, decode(encode(y)) == y for bodies."""
    body = "retrieved_doc_ids"
    assert decode_sequence_key(encode_sequence_key(body)) == body
    prefixed = f"{SEQ_ATTR_PREFIX}{body}"
    assert encode_sequence_key(decode_sequence_key(prefixed)) == prefixed


def test_is_sequence_key_discriminates() -> None:
    assert is_sequence_key(f"{SEQ_ATTR_PREFIX}tags") is True
    assert is_sequence_key("tags") is False
    assert is_sequence_key("") is False


def test_decode_sequence_key_prefix_only_returns_empty_string() -> None:
    """Documented asymmetry: ``encode_sequence_key("")`` raises, but decoding a
    prefix-only key yields the empty string rather than raising.

    This test pins the behaviour so a future change is a deliberate decision,
    not an accident.
    """
    assert decode_sequence_key(SEQ_ATTR_PREFIX) == ""


@pytest.mark.parametrize("bad_key", ["", "   ", "\t", "\n"])
def test_encode_sequence_key_rejects_blank_bodies(bad_key: str) -> None:
    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        encode_sequence_key(bad_key)


# ---------------------------------------------------------------------------
# Sequence attribute value encoding
# ---------------------------------------------------------------------------


def test_encode_sequence_attribute_value_within_limit_is_valid_json() -> None:
    data = ["apple", "banana", 42]
    result = encode_sequence_attribute_value(data)

    assert isinstance(result, str)
    assert json.loads(result) == ["apple", "banana", 42]


def test_encode_sequence_attribute_value_empty_sequence() -> None:
    """An empty sequence serializes to a valid empty JSON array."""
    assert encode_sequence_attribute_value([]) == "[]"


def test_encode_sequence_attribute_value_single_item() -> None:
    assert json.loads(encode_sequence_attribute_value(["x"])) == ["x"]


def test_encode_sequence_attribute_value_tuple_input() -> None:
    """Tuples are valid Sequence inputs and serialize identically to lists."""
    assert json.loads(encode_sequence_attribute_value(("a", "b"))) == ["a", "b"]


def test_encode_sequence_attribute_value_non_serializable_items_use_str() -> None:
    class CustomObj:
        def __str__(self) -> str:
            return "custom_val"

    result = encode_sequence_attribute_value([CustomObj()])
    assert json.loads(result) == ["custom_val"]


def test_encode_sequence_attribute_value_truncates_with_sentinel() -> None:
    """When the full JSON would exceed max_length, tail items are dropped and
    a sentinel is appended, producing output that is still valid JSON.
    """
    items = [f"item_{i}" for i in range(50)]
    max_len = 80

    result = encode_sequence_attribute_value(items, max_length=max_len)
    assert len(result) <= max_len

    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert parsed[-1] == TRUNCATION_SUFFIX


def test_encode_sequence_attribute_value_truncation_preserves_prefix_items() -> None:
    """Truncation removes tail items; items that fit are kept in order."""
    items = ["alpha", "beta", "gamma", "delta", "epsilon"]
    # Pick a limit that keeps exactly "alpha" and "beta" plus the sentinel.
    max_len = len(json.dumps(["alpha", "beta", TRUNCATION_SUFFIX]))
    result = encode_sequence_attribute_value(items, max_length=max_len)

    parsed = json.loads(result)
    assert parsed[:2] == ["alpha", "beta"]
    assert parsed[-1] == TRUNCATION_SUFFIX


def test_encode_sequence_attribute_value_sentinel_only_when_needed() -> None:
    """When no items fit but the sentinel does, the result is sentinel-only."""
    # The sentinel-only form is ``["...[truncated]"]``; compute its length
    # from the constants rather than hard-coding 19.
    sentinel_only_len = len(json.dumps([TRUNCATION_SUFFIX]))
    result = encode_sequence_attribute_value(["a"], max_length=sentinel_only_len)

    assert json.loads(result) == [TRUNCATION_SUFFIX]


def test_encode_sequence_attribute_value_exactly_at_limit_does_not_truncate() -> None:
    """A sequence whose JSON is exactly max_length long is returned as-is."""
    items = ["a", "b", "c"]
    exact_len = len(json.dumps(items))
    result = encode_sequence_attribute_value(items, max_length=exact_len)
    assert result == json.dumps(items)


def test_encode_sequence_attribute_value_raises_when_even_sentinel_does_not_fit() -> None:
    with pytest.raises(ValueError, match="Cannot encode sequence as valid JSON"):
        encode_sequence_attribute_value(["a", "b"], max_length=5)


def test_encode_sequence_attribute_value_output_is_always_parseable() -> None:
    """Property: whatever the input, the output parses as a JSON array.

    This is the module's central contract for this function -- the earlier
    version returned invalid JSON when the input was too long to fit. The
    test cases below cover the three branches: fits-as-is, fits-after-trim,
    and sentinel-only.
    """
    test_cases = [
        (["short"], 1024),  # fits as-is
        ([f"item_{i}" for i in range(100)], 50),  # fits after trim
        (["x" * 200], 100),  # fits after trim (one item dropped)
        ([], 10),  # empty
        ([1, 2, 3], 20),  # mixed types, fits
        ([{"a": 1}], 100),  # dict item, uses default=str
    ]
    for items, max_len in test_cases:
        result = encode_sequence_attribute_value(items, max_length=max_len)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
