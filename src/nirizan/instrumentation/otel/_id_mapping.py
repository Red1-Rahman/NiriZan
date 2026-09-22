# src/nirizan/instrumentation/otel/_id_mapping.py
"""Identifier mapping utilities between NiriZan UUIDs and OpenTelemetry IDs.

This module provides stdlib-only, pure-Python conversion functions between
NiriZan 128-bit UUID identifiers and OpenTelemetry 128-bit Trace IDs / 64-bit Span IDs.
It contains zero external package dependencies.
"""

import hashlib
from uuid import UUID

__all__ = [
    "is_valid_otel_span_id",
    "is_valid_otel_trace_id",
    "otel_span_id_to_uuid",
    "otel_trace_id_to_uuid",
    "uuid_to_otel_span_id",
    "uuid_to_otel_trace_id",
]

# Private module constants; not part of the bridge's public API.
# Fixed UUID namespace for deterministic derivation of 128-bit UUIDs
# from 64-bit OTel Span IDs when the 'nirizan.span_id' attribute is absent.
_NIRIZAN_SPAN_ID_NAMESPACE: UUID = UUID("a921d782-2615-4428-b0e6-5c56d78703a1")

_MAX_TRACE_ID: int = (1 << 128) - 1
_MAX_SPAN_ID: int = (1 << 64) - 1


def is_valid_otel_trace_id(otel_trace_id: int) -> bool:
    """Check if an OTel trace ID is a valid, non-zero 128-bit integer.

    Note:
        Accepts standard Python `int` instances. Strictly excludes `bool`
        (a subclass of `int` in Python) and non-standard integer types
        such as NumPy integers.
    """
    if not isinstance(otel_trace_id, int) or isinstance(otel_trace_id, bool):
        return False
    return 0 < otel_trace_id <= _MAX_TRACE_ID


def is_valid_otel_span_id(otel_span_id: int) -> bool:
    """Check if an OTel span ID is a valid, non-zero 64-bit integer.

    Note:
        Accepts standard Python `int` instances. Strictly excludes `bool`
        (a subclass of `int` in Python) and non-standard integer types
        such as NumPy integers.
    """
    if not isinstance(otel_span_id, int) or isinstance(otel_span_id, bool):
        return False
    return 0 < otel_span_id <= _MAX_SPAN_ID


def uuid_to_otel_trace_id(trace_id: UUID) -> int:
    """Convert a 128-bit NiriZan UUID trace ID to a 128-bit integer OTel trace ID.

    Raises:
        ValueError: If trace_id resolves to an invalid (all-zeros) trace ID.
    """
    otel_trace_id = trace_id.int
    if not is_valid_otel_trace_id(otel_trace_id):
        raise ValueError(f"Invalid NiriZan trace_id '{trace_id}': maps to all-zeros OTel trace ID.")
    return otel_trace_id


def otel_trace_id_to_uuid(otel_trace_id: int) -> UUID:
    """Convert a 128-bit integer OTel trace ID to a 128-bit NiriZan UUID trace ID.

    Raises:
        ValueError: If otel_trace_id is not a valid non-zero 128-bit integer.
    """
    if not is_valid_otel_trace_id(otel_trace_id):
        raise ValueError(
            f"Invalid OTel trace ID: {otel_trace_id}. Must be a non-zero 128-bit integer."
        )
    return UUID(int=otel_trace_id)


def uuid_to_otel_span_id(span_id: UUID) -> int:
    """Convert a 128-bit NiriZan UUID span ID to a 64-bit integer OTel span ID.

    Takes the lower 64 bits (low 8 bytes in big-endian order) of the UUID integer
    representation via bitwise AND with `_MAX_SPAN_ID`.

    Raises:
        ValueError: If the resulting low 64 bits yield zero (an invalid OTel span ID).
            Downstream callers must catch this exception and handle it gracefully
            according to exporter contract rules (e.g., skip + warning log).
    """
    otel_span_id = span_id.int & _MAX_SPAN_ID
    if not is_valid_otel_span_id(otel_span_id):
        raise ValueError(
            f"Invalid NiriZan span_id '{span_id}': low 64 bits yield an invalid all-zeros OTel span ID."
        )
    return otel_span_id


def otel_span_id_to_uuid(otel_span_id: int) -> UUID:
    """Derive a deterministic 128-bit NiriZan UUID span ID from a 64-bit OTel span ID.

    Computes a UUIDv5 using ``_NIRIZAN_SPAN_ID_NAMESPACE`` as the namespace and
    the big-endian 8-byte representation of the 64-bit span ID as the name.

    The derivation is done with ``hashlib.sha1`` directly rather than via
    ``uuid.uuid5`` because Python 3.11's ``uuid5`` rejects ``bytes`` names
    (it calls ``bytes(name, "utf-8")`` internally), while Python 3.12's
    accepts them. Computing the digest here produces the same UUID on both
    versions, which matters because NiriZan's ``requires-python`` floor is
    3.11.

    Raises:
        ValueError: If otel_span_id is not a valid non-zero 64-bit integer.
    """
    if not is_valid_otel_span_id(otel_span_id):
        raise ValueError(
            f"Invalid OTel span ID: {otel_span_id}. Must be a non-zero 64-bit integer."
        )
    # Standardized on big-endian 8-byte serialization for cross-platform/cross-process determinism.
    span_bytes = otel_span_id.to_bytes(8, byteorder="big")
    # Reproduce uuid.uuid5's hashing without going through uuid.uuid5, whose
    # handling of `bytes` names differs between Python 3.11 and 3.12.
    digest = hashlib.sha1(_NIRIZAN_SPAN_ID_NAMESPACE.bytes + span_bytes).digest()
    return UUID(bytes=digest[:16], version=5)
