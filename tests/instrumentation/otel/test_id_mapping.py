# tests/instrumentation/otel/test_id_mapping.py
"""Unit tests for NiriZan <-> OpenTelemetry identifier mapping utilities.

This module has no state, no I/O, and no external dependencies, so the tests
below focus on invariants, boundary conditions, and regression protection for
the UUID <-> int conversions. Categories that do not apply (state transitions,
side effects, resource cleanup, async behaviour) are intentionally absent.
"""

import hashlib
import os
import random
import subprocess
import sys
from uuid import UUID

import pytest

from nirizan.instrumentation.otel._id_mapping import (
    _MAX_SPAN_ID,
    _MAX_TRACE_ID,
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

# Known answers for the span ID derivation, computed once and committed. They
# are also what the standard library's ``uuid.uuid5`` returns on Python 3.12+
# when given the same namespace and the 8-byte big-endian name, which is how
# the values were cross-checked. If any of these fail, every span ID that was
# ever derived from an OTel span ID has silently changed.
_DERIVED_SPAN_ID_GOLDEN: dict[int, UUID] = {
    0x1122334455667788: UUID("423a37ba-78b3-520e-b257-9cecf2d06ae3"),
    1: UUID("7f606d49-dcda-5d16-bd23-81bc87414121"),
    _MAX_SPAN_ID: UUID("917f31d2-65ce-5fbe-ab8a-99bea247d331"),
}


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
    digest = hashlib.sha1(
        _NIRIZAN_SPAN_ID_NAMESPACE.bytes + _VALID_SPAN_INT.to_bytes(8, "big")
    ).digest()
    expected = UUID(bytes=digest[:16], version=5)
    assert otel_span_id_to_uuid(_VALID_SPAN_INT) == expected


@pytest.mark.parametrize(("otel_id", "expected"), list(_DERIVED_SPAN_ID_GOLDEN.items()))
def test_otel_span_id_to_uuid_matches_known_answers(otel_id: int, expected: UUID) -> None:
    """Pin concrete outputs, not just the recipe.

    The recipe test above recomputes the expected value with the same steps as
    the implementation, so a change to the namespace or byte order that is
    applied to both would go unnoticed. Committed literals do not move.
    """
    assert otel_span_id_to_uuid(otel_id) == expected


def test_otel_span_id_to_uuid_yields_rfc4122_version_5_uuids() -> None:
    """Derived IDs are well-formed name-based (version 5) UUIDs."""
    derived = otel_span_id_to_uuid(_VALID_SPAN_INT)
    assert derived.version == 5
    assert derived.variant == "specified in RFC 4122"


def test_otel_span_id_to_uuid_has_no_collisions_in_a_large_sample() -> None:
    """Distinct OTel span IDs map to distinct UUIDs (sampled, not exhaustive)."""
    rng = random.Random(20260402)
    ids = {rng.randrange(1, _MAX_SPAN_ID + 1) for _ in range(5_000)}
    derived = {otel_span_id_to_uuid(i) for i in ids}
    assert len(derived) == len(ids)


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


def test_span_id_conversion_is_lossy_in_both_directions() -> None:
    """Span ID conversion is lossy both ways, and derivation is stable.

    NiriZan -> OTel keeps only the low 64 bits of the UUID. OTel -> NiriZan
    derives a new UUID from a hash of the OTel span ID, so the derived UUID
    does not carry the input value in its low bits. As a result, neither
    NiriZan -> OTel -> NiriZan nor OTel -> NiriZan -> OTel recovers the
    original value, and the bridge preserves the original ID by stashing it
    in a span attribute instead (``nirizan.span_id`` and ``otel.span_id``).

    Deriving a NiriZan UUID from the same OTel span ID always gives the same
    result, which is what makes the derived value usable as an identifier.
    """
    # NiriZan -> OTel -> NiriZan does not recover the original UUID.
    otel_id = uuid_to_otel_span_id(_VALID_UUID)
    reconstructed = otel_span_id_to_uuid(otel_id)
    assert isinstance(reconstructed, UUID)
    assert reconstructed != _VALID_UUID

    # OTel -> NiriZan -> OTel does not recover the original span ID.
    assert uuid_to_otel_span_id(otel_span_id_to_uuid(_VALID_SPAN_INT)) != _VALID_SPAN_INT

    # Derivation from the same OTel span ID is stable.
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


def _run_derivation_in_fresh_interpreter(hash_seed: str) -> str:
    """Derive a span ID UUID in a new interpreter with a given PYTHONHASHSEED.

    The child environment is the parent environment with ``PYTHONHASHSEED``
    set last, so an ambient value (for example one set by CI or a pytest
    plugin) cannot override the seed under test. ``PYTHONPATH`` is rebuilt
    from the parent's ``sys.path`` so the child can import the package even
    when the tests rely on pytest's ``pythonpath`` setting rather than an
    installed distribution.
    """
    script = (
        "from nirizan.instrumentation.otel._id_mapping import otel_span_id_to_uuid;"
        f"print(otel_span_id_to_uuid({_VALID_SPAN_INT:#x}))"
    )
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(p for p in sys.path if p),
        "PYTHONHASHSEED": hash_seed,
    }
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return proc.stdout.strip()


def test_otel_span_id_to_uuid_is_stable_across_processes() -> None:
    """The uuid5 derivation must not depend on process-local state.

    PYTHONHASHSEED randomizes ``str`` and ``bytes`` hashing, but not SHA-1, so
    the derivation is expected to be independent of it. This runs the same
    derivation in two fresh interpreters with different seeds and checks that
    both agree with each other, with the in-process result, and with the
    committed known answer.
    """
    outputs = [_run_derivation_in_fresh_interpreter(seed) for seed in ("0", "1")]

    assert outputs[0] == outputs[1], f"uuid5 derivation differs across processes: {outputs!r}"
    assert outputs[0] == str(otel_span_id_to_uuid(_VALID_SPAN_INT))
    assert outputs[0] == str(_DERIVED_SPAN_ID_GOLDEN[_VALID_SPAN_INT])


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
