# tests/instrumentation/otel/test_id_mapping.py
"""Unit tests for NiriZan <-> OpenTelemetry identifier mapping utilities."""

from uuid import UUID

import pytest

from nirizan.instrumentation.otel._id_mapping import (
    _MAX_SPAN_ID,
    _MAX_TRACE_ID,
    is_valid_otel_span_id,
    is_valid_otel_trace_id,
    otel_span_id_to_uuid,
    otel_trace_id_to_uuid,
    uuid_to_otel_span_id,
    uuid_to_otel_trace_id,
)


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------


def test_is_valid_otel_trace_id_valid_and_boundary_values() -> None:
    assert is_valid_otel_trace_id(1) is True[cite:10]
    assert is_valid_otel_trace_id(_MAX_TRACE_ID) is True[cite:10]
    assert is_valid_otel_trace_id(0x1234567890ABCDEF1234567890ABCDEF) is True[cite:10]


def test_is_valid_otel_trace_id_invalid_inputs() -> None:
    assert is_valid_otel_trace_id(0) is False[cite:10]
    assert is_valid_otel_trace_id(-1) is False[cite:10]
    assert is_valid_otel_trace_id(_MAX_TRACE_ID + 1) is False[cite:10]

    # Strictly excludes bools and non-int types[cite: 10]
    assert is_valid_otel_trace_id(True) is False[cite:10]
    assert is_valid_otel_trace_id(False) is False[cite:10]
    assert is_valid_otel_trace_id("123") is False[cite:10]  # type: ignore[arg-type]
    assert is_valid_otel_trace_id(12.34) is False[cite:10]  # type: ignore[arg-type]
    assert is_valid_otel_trace_id(None) is False[cite:10]  # type: ignore[arg-type]


def test_is_valid_otel_span_id_valid_and_boundary_values() -> None:
    assert is_valid_otel_span_id(1) is True[cite:10]
    assert is_valid_otel_span_id(_MAX_SPAN_ID) is True[cite:10]
    assert is_valid_otel_span_id(0x1234567890ABCDEF) is True[cite:10]


def test_is_valid_otel_span_id_invalid_inputs() -> None:
    assert is_valid_otel_span_id(0) is False[cite:10]
    assert is_valid_otel_span_id(-1) is False[cite:10]
    assert is_valid_otel_span_id(_MAX_SPAN_ID + 1) is False[cite:10]

    # Strictly excludes bools and non-int types[cite: 10]
    assert is_valid_otel_span_id(True) is False[cite:10]
    assert is_valid_otel_span_id(False) is False[cite:10]
    assert is_valid_otel_span_id("123") is False[cite:10]  # type: ignore[arg-type]
    assert is_valid_otel_span_id(None) is False[cite:10]  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Trace ID Conversions
# ---------------------------------------------------------------------------


def test_uuid_to_otel_trace_id_success() -> None:
    uuid_val = UUID("12345678-1234-5678-1234-567812345678")
    expected_int = uuid_val.int[cite:10]
    assert uuid_to_otel_trace_id(uuid_val) == expected_int[cite:10]


def test_uuid_to_otel_trace_id_raises_on_zero() -> None:
    zero_uuid = UUID(int=0)
    with pytest.raises(ValueError, match="Invalid NiriZan trace_id"):
        uuid_to_otel_trace_id(zero_uuid)[cite:10]


def test_otel_trace_id_to_uuid_success() -> None:
    trace_int = 0x1234567890ABCDEF1234567890ABCDEF
    res_uuid = otel_trace_id_to_uuid(trace_int)[cite:10]
    assert isinstance(res_uuid, UUID)
    assert res_uuid.int == trace_int[cite:10]


def test_otel_trace_id_to_uuid_raises_on_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid OTel trace ID: 0"):
        otel_trace_id_to_uuid(0)[cite:10]

    with pytest.raises(ValueError, match="Invalid OTel trace ID: -1"):
        otel_trace_id_to_uuid(-1)[cite:10]


# ---------------------------------------------------------------------------
# Span ID Conversions
# ---------------------------------------------------------------------------


def test_uuid_to_otel_span_id_success() -> None:
    # UUID with non-zero lower 64 bits[cite: 10]
    uuid_val = UUID("12345678-1234-5678-1234-567812345678")
    expected_span_id = uuid_val.int & _MAX_SPAN_ID[cite:10]

    assert uuid_to_otel_span_id(uuid_val) == expected_span_id[cite:10]


def test_uuid_to_otel_span_id_raises_when_low_64_bits_are_zero() -> None:
    # Upper bits non-zero, low 64 bits all zeros[cite: 10]
    zero_low_bits_uuid = UUID(int=1 << 64)
    with pytest.raises(ValueError, match="low 64 bits yield an invalid all-zeros OTel span ID"):
        uuid_to_otel_span_id(zero_low_bits_uuid)[cite:10]


def test_otel_span_id_to_uuid_determinism_and_conversion() -> None:
    span_id_int = 0x1122334455667788
    uuid1 = otel_span_id_to_uuid(span_id_int)[cite:10]
    uuid2 = otel_span_id_to_uuid(span_id_int)[cite:10]

    assert isinstance(uuid1, UUID)
    assert uuid1 == uuid2  # Assert determinism[cite: 10]


def test_otel_span_id_to_uuid_raises_on_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid OTel span ID: 0"):
        otel_span_id_to_uuid(0)[cite:10]

    with pytest.raises(ValueError, match="Invalid OTel span ID: -5"):
        otel_span_id_to_uuid(-5)[cite:10]
