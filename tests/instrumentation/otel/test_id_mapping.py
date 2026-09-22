# tests/instrumentation/otel/test_id_mapping.py
"""Unit tests for NiriZan <-> OpenTelemetry identifier mapping utilities.

This module has no state, no I/O, and no external dependencies, so the tests
below focus on invariants, boundary conditions, and regression protection for
the UUID <-> int conversions. Categories that do not apply (state transitions,
side effects, resource cleanup, async behaviour) are intentionally absent.
"""

import subprocess
import sys
from uuid import UUID

import pytest

from nirizan.instrumentation.otel._id_mapping import _MAX_SPAN_ID, _MAX_TRACE_ID
from nirizan.instrumentation.otel._id_mapping import (
    _NIRIZAN_SPAN_ID_NAMESPACE,
    is_valid_otel_span_id,
    is_valid_otel_trace_id,
    otel_span_id_to_uuid,
    otel_trace_id_to_uuid,
    uuid_to_otel_span_id,
    uuid_to_otel_trace_id,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# A UUID whose low 64 bits are non-zero, used across several tests. Defined
# once so a future edit to one test cannot accidentally change another test's
# expected value.
_VALID_UUID = UUID("12345678-1234-5678-1234-567812345678")
_VALID_TRACE_INT = 0x1234567890ABCDEF1234567890ABCDEF
_VALID_SPAN_INT = 0x1122334455667788


# ---------------------------------------------------------------------------
# Module-level invariants (regression protection)
# ---------------------------------------------------------------------------


def test_span_id_namespace_constant_is_frozen() -> None:
    """Regression: changing this UUID invalidates every previously-derived span ID.

    The value is committed in source. If this test fails, either the constant
    was edited (breaking every NiriZan span ID ever derived from an OTel span
    ID) or the namespace was accidentally regenerated at import time.
    """
    assert _NIRIZAN_SPAN_ID_NAMESPACE == UUID("a921d782-2615-4428-b0e6-5c56d78703a1")


def test_max_id_constants_have_correct_bit_widths() -> None:
    """The upper bounds must be exactly 128-bit and 64-bit all-ones masks."""
    assert _MAX_TRACE_ID == (1 << 128) - 1
    assert _MAX_SPAN_ID == (1 << 64) - 1


# ---------------------------------------------------------------------------
# Validation: is_valid_otel_trace_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [1, 2, _VALID_TRACE_INT, _MAX_TRACE_ID],
)
def test_is_valid_otel_trace_id_accepts_valid_values(value: int) -> None:
    """Every positive integer up to and including _MAX_TRACE_ID is valid."""
    assert is_valid_otel_trace_id(value) is True


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        _MAX_TRACE_ID + 1,
        _MAX_TRACE_ID + 100,
    ],
)
def test_is_valid_otel_trace_id_rejects_out_of_range_ints(value: int) -> None:
    """Zero, negatives, and values above the 128-bit ceiling are invalid."""
    assert is_valid_otel_trace_id(value) is False


@pytest.mark.parametrize(
    "value",
    [True, False, "123", 12.34, None, b"\x01", [1]],
)
def test_is_valid_otel_trace_id_rejects_non_int_types(value: object) -> None:
    """The bool subclass of int is rejected, as are other non-int types.

    Excluding bool explicitly matters because ``isinstance(True, int)`` is
    ``True`` in Python, and ``0 < True <= _MAX_TRACE_ID`` would otherwise
    return ``True`` for a value that has no meaningful place in the trace-ID
    domain.
    """
    assert is_valid_otel_trace_id(value) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Validation: is_valid_otel_span_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [1, 2, _VALID_SPAN_INT, _MAX_SPAN_ID],
)
def test_is_valid_otel_span_id_accepts_valid_values(value: int) -> None:
    """Every positive integer up to and including _MAX_SPAN_ID is valid."""
    assert is_valid_otel_span_id(value) is True


@pytest.mark.parametrize(
    "value",
    [0, -1, -5, _MAX_SPAN_ID + 1, 1 << 64],
)
def test_is_valid_otel_span_id_rejects_out_of_range_ints(value: int) -> None:
    """Zero, negatives, and values above the 64-bit ceiling are invalid."""
    assert is_valid_otel_span_id(value) is False


@pytest.mark.parametrize(
    "value",
    [True, False, "123", 12.34, None, b"\x01", [1]],
)
def test_is_valid_otel_span_id_rejects_non_int_types(value: object) -> None:
    """Same strict typing contract as the trace-ID validator."""
    assert is_valid_otel_span_id(value) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Trace ID conversion
# ---------------------------------------------------------------------------


def test_uuid_to_otel_trace_id_returns_uuid_int_value() -> None:
    """The conversion is the UUID's 128-bit integer value, unchanged."""
    result = uuid_to_otel_trace_id(_VALID_UUID)
    assert isinstance(result, int)
    assert result == _VALID_UUID.int


def test_uuid_to_otel_trace_id_rejects_all_zero_uuid() -> None:
    """A UUID of all zeros maps to OTel's "no valid context" sentinel."""
    with pytest.raises(ValueError, match=r"Invalid NiriZan trace_id '.*': maps to all-zeros"):
        uuid_to_otel_trace_id(UUID(int=0))


def test_otel_trace_id_to_uuid_returns_uuid_with_matching_int() -> None:
    """The inverse conversion round-trips the integer value."""
    result = otel_trace_id_to_uuid(_VALID_TRACE_INT)
    assert isinstance(result, UUID)
    assert result.int == _VALID_TRACE_INT


@pytest.mark.parametrize("value", [0, -1, -1000, _MAX_TRACE_ID + 1])
def test_otel_trace_id_to_uuid_rejects_invalid_values(value: int) -> None:
    """Zero and out-of-range values raise ValueError with the input echoed."""
    with pytest.raises(ValueError, match="Invalid OTel trace ID"):
        otel_trace_id_to_uuid(value)


# ---------------------------------------------------------------------------
# Span ID conversion
# ---------------------------------------------------------------------------


def test_uuid_to_otel_span_id_returns_low_64_bits() -> None:
    """The result is the low 8 bytes of the UUID integer, big-endian."""
    result = uuid_to_otel_span_id(_VALID_UUID)
    assert result == _VALID_UUID.int & _MAX_SPAN_ID
    assert 0 < result <= _MAX_SPAN_ID


def test_uuid_to_otel_span_id_rejects_zero_low_bits() -> None:
    """A UUID whose low 64 bits are all zero maps to an invalid OTel span ID."""
    # Upper 64 bits set, lower 64 bits zero.
    with pytest.raises(
        ValueError,
        match=r"low 64 bits yield an invalid all-zeros OTel span ID",
    ):
        uuid_to_otel_span_id(UUID(int=1 << 64))


def test_otel_span_id_to_uuid_is_deterministic() -> None:
    """Repeated calls with the same input produce the same UUID."""
    first = otel_span_id_to_uuid(_VALID_SPAN_INT)
    second = otel_span_id_to_uuid(_VALID_SPAN_INT)
    assert isinstance(first, UUID)
    assert first == second


@pytest.mark.parametrize("value", [0, -1, -5, _MAX_SPAN_ID + 1, 1 << 64])
def test_otel_span_id_to_uuid_rejects_invalid_values(value: int) -> None:
    """Zero and out-of-range values raise ValueError with the input echoed."""
    with pytest.raises(ValueError, match="Invalid OTel span ID"):
        otel_span_id_to_uuid(value)


def test_otel_span_id_to_uuid_uses_big_endian_byte_serialization() -> None:
    """The uuid5 derivation hashes the big-endian 8-byte form of the ID.

    Regression: switching to little-endian byte order would change every
    derived span ID for every OTel span ID ever ingested. This test pins the
    encoding choice to a concrete expected UUID.

    Computed with ``hashlib`` rather than ``uuid.uuid5`` because Python 3.11's
    ``uuid5`` rejects ``bytes`` names while Python 3.12's accepts them; the
    implementation avoids ``uuid.uuid5`` for the same reason, so the test
    mirrors that choice.
    """
    import hashlib

    digest = hashlib.sha1(
        _NIRIZAN_SPAN_ID_NAMESPACE.bytes + _VALID_SPAN_INT.to_bytes(8, "big")
    ).digest()
    expected = UUID(bytes=digest[:16], version=5)
    assert otel_span_id_to_uuid(_VALID_SPAN_INT) == expected


# ---------------------------------------------------------------------------
# Round-trip invariants (the module's core contract)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uuid_value",
    [
        UUID("12345678-1234-5678-1234-567812345678"),
        UUID("00000000-0000-0000-0000-000000000001"),
        UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        UUID(int=1),
        UUID(int=_MAX_TRACE_ID),
    ],
)
def test_trace_id_round_trip_uuid_to_otel_to_uuid(uuid_value: UUID) -> None:
    """NiriZan -> OTel -> NiriZan is exact for every valid trace ID."""
    otel_value = uuid_to_otel_trace_id(uuid_value)
    assert otel_trace_id_to_uuid(otel_value) == uuid_value


@pytest.mark.parametrize(
    "otel_value",
    [
        1,
        _VALID_TRACE_INT,
        _MAX_TRACE_ID,
        _MAX_TRACE_ID - 1,
    ],
)
def test_trace_id_round_trip_otel_to_uuid_to_otel(otel_value: int) -> None:
    """OTel -> NiriZan -> OTel is exact for every valid trace ID."""
    nirizan_value = otel_trace_id_to_uuid(otel_value)
    assert uuid_to_otel_trace_id(nirizan_value) == otel_value


def test_span_id_round_trip_is_intentionally_one_directional() -> None:
    """The documented lossiness of span ID conversion.

    NiriZan -> OTel truncates the UUID to 64 bits. OTel -> NiriZan derives a
    *new* UUID via uuid5. So a full NiriZan -> OTel -> NiriZan round trip does
    NOT recover the original UUID, and the test asserts that explicitly rather
    than assuming a bijection the module never claimed.

    OTel -> NiriZan -> OTel, on the other hand, is exact, because the derived
    UUID's low 64 bits are... let me not assert something false; the derived
    UUID is a fresh uuid5 output, not a value whose low bits equal the input.
    The only exact round trip is the one the module actually guarantees, and
    that is tested at the OTel layer: given an OTel span ID, deriving a
    NiriZan UUID twice yields the same result, and the caller stashes the
    original OTel ID in ``attributes["otel.span_id"]`` for later recovery.
    """
    original = UUID("12345678-1234-5678-1234-567812345678")
    otel_id = uuid_to_otel_span_id(original)
    reconstructed = otel_span_id_to_uuid(otel_id)

    # The reconstruction is a valid UUID but NOT the original.
    assert isinstance(reconstructed, UUID)
    assert reconstructed != original

    # Repeated derivation from the same OTel ID is stable.
    assert otel_span_id_to_uuid(otel_id) == reconstructed


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_uuid_to_otel_trace_id_is_idempotent() -> None:
    """Repeated calls return the same result."""
    assert uuid_to_otel_trace_id(_VALID_UUID) == uuid_to_otel_trace_id(_VALID_UUID)


def test_uuid_to_otel_span_id_is_idempotent() -> None:
    """Repeated calls return the same result."""
    assert uuid_to_otel_span_id(_VALID_UUID) == uuid_to_otel_span_id(_VALID_UUID)


# ---------------------------------------------------------------------------
# Cross-process determinism
# ---------------------------------------------------------------------------


def test_otel_span_id_to_uuid_is_stable_across_processes() -> None:
    """The uuid5 derivation must not depend on process-local state.

    PYTHONHASHSEED and similar environment variables affect the standard
    library's hash randomization, but not uuid5 (which uses SHA-1). This test
    runs the same derivation in two fresh interpreters with different
    PYTHONHASHSEED values and asserts the outputs match.
    """
    script = (
        "from nirizan.instrumentation.otel._id_mapping import otel_span_id_to_uuid;"
        "print(otel_span_id_to_uuid(0x1122334455667788))"
    )

    outputs = []
    for seed in ("0", "1"):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": seed, "PATH": "", **__import__("os").environ},
        )
        outputs.append(proc.stdout.strip())

    assert outputs[0] == outputs[1], f"uuid5 derivation differs across processes: {outputs!r}"

    # And the subprocess result matches the in-process result.
    assert outputs[0] == str(otel_span_id_to_uuid(_VALID_SPAN_INT))


# ---------------------------------------------------------------------------
# Boundary conditions
# ---------------------------------------------------------------------------


def test_smallest_valid_trace_id_boundary() -> None:
    """The smallest valid value is exactly 1 (zero is reserved)."""
    assert is_valid_otel_trace_id(1) is True
    assert is_valid_otel_trace_id(0) is False
    assert otel_trace_id_to_uuid(1) == UUID(int=1)
    assert uuid_to_otel_trace_id(UUID(int=1)) == 1


def test_largest_valid_trace_id_boundary() -> None:
    """The largest valid value is _MAX_TRACE_ID, and one above it is invalid."""
    assert is_valid_otel_trace_id(_MAX_TRACE_ID) is True
    assert is_valid_otel_trace_id(_MAX_TRACE_ID + 1) is False
    assert otel_trace_id_to_uuid(_MAX_TRACE_ID) == UUID(int=_MAX_TRACE_ID)


def test_largest_valid_span_id_boundary() -> None:
    """The largest valid span ID is _MAX_SPAN_ID, and one above it is invalid."""
    assert is_valid_otel_span_id(_MAX_SPAN_ID) is True
    assert is_valid_otel_span_id(_MAX_SPAN_ID + 1) is False
