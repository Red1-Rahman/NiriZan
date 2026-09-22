# src\nirizan\instrumentation\otel\_id_mapping.py
"""Identifier mapping utilities between NiriZan UUIDs and OpenTelemetry IDs.

This module provides pure-Python, zero-dependency conversion functions between
NiriZan 128-bit UUID identifiers and OpenTelemetry 128-bit Trace IDs / 64-bit Span IDs[cite: 11].
"""

from uuid import UUID, uuid5

# Fixed UUID namespace for deterministic derivation of 128-bit UUIDs
# from 64-bit OTel Span IDs when the 'nirizan.span_id' attribute is absent[cite: 11].
_NIRIZAN_SPAN_ID_NAMESPACE: UUID = UUID("a921d782-2615-4428-b0e6-5c56d78703a1")

_MAX_TRACE_ID: int = (1 << 128) - 1
_MAX_SPAN_ID: int = (1 << 64) - 1


def is_valid_otel_trace_id(otel_trace_id: int) -> bool:
    """Check if an OTel trace ID is a valid, non-zero 128-bit integer[cite: 11]."""
    if not isinstance(otel_trace_id, int) or isinstance(otel_trace_id, bool):
        return False
    return 0 < otel_trace_id <= _MAX_TRACE_ID


def is_valid_otel_span_id(otel_span_id: int) -> bool:
    """Check if an OTel span ID is a valid, non-zero 64-bit integer[cite: 11]."""
    if not isinstance(otel_span_id, int) or isinstance(otel_span_id, bool):
        return False
    return 0 < otel_span_id <= _MAX_SPAN_ID


def uuid_to_otel_trace_id(trace_id: UUID) -> int:
    """Convert a 128-bit NiriZan UUID trace ID to a 128-bit integer OTel trace ID[cite: 11].

    Raises:
        ValueError: If trace_id resolves to an invalid (all-zeros) trace ID[cite: 11].
    """
    otel_trace_id = trace_id.int
    if not is_valid_otel_trace_id(otel_trace_id):
        raise ValueError(f"Invalid NiriZan trace_id '{trace_id}': maps to all-zeros OTel trace ID.")
    return otel_trace_id


def otel_trace_id_to_uuid(otel_trace_id: int) -> UUID:
    """Convert a 128-bit integer OTel trace ID to a 128-bit NiriZan UUID trace ID[cite: 11].

    Raises:
        ValueError: If otel_trace_id is not a valid non-zero 128-bit integer[cite: 11].
    """
    if not is_valid_otel_trace_id(otel_trace_id):
        raise ValueError(
            f"Invalid OTel trace ID: {otel_trace_id}. Must be a non-zero 128-bit integer."
        )
    return UUID(int=otel_trace_id)


def uuid_to_otel_span_id(span_id: UUID) -> int:
    """Convert a 128-bit NiriZan UUID span ID to a 64-bit integer OTel span ID[cite: 11].

    Takes the low 8 bytes (64 bits) of the UUID integer representation[cite: 11].

    Raises:
        ValueError: If the resulting 64-bit integer is zero[cite: 11].
    """
    otel_span_id = span_id.int & _MAX_SPAN_ID
    if not is_valid_otel_span_id(otel_span_id):
        raise ValueError(
            f"Invalid NiriZan span_id '{span_id}': low 64 bits yield an invalid all-zeros OTel span ID."
        )
    return otel_span_id


def otel_span_id_to_uuid(otel_span_id: int) -> UUID:
    """Derive a deterministic 128-bit NiriZan UUID span ID from a 64-bit integer OTel span ID[cite: 11].

    Uses uuid5 with the fixed _NIRIZAN_SPAN_ID_NAMESPACE[cite: 11].

    Raises:
        ValueError: If otel_span_id is not a valid non-zero 64-bit integer[cite: 11].
    """
    if not is_valid_otel_span_id(otel_span_id):
        raise ValueError(
            f"Invalid OTel span ID: {otel_span_id}. Must be a non-zero 64-bit integer."
        )
    span_bytes = otel_span_id.to_bytes(8, byteorder="big")
    return uuid5(_NIRIZAN_SPAN_ID_NAMESPACE, span_bytes)
