# src\nirizan\instrumentation\otel\semconv.py
"""Semantic conventions and attribute helpers for OpenTelemetry integration.

This module defines standardized OpenTelemetry GenAI semantic conventions,
NiriZan custom attribute keys, OTel metadata attributes, limit constants, and
attribute sanitization / truncation helpers. It contains zero external package dependencies.
"""

import json
from typing import Sequence

__all__ = [
    "GEN_AI_COMPLETION",
    "GEN_AI_OPERATION_NAME",
    "GEN_AI_PROMPT",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_RESPONSE_MODEL",
    "GEN_AI_SYSTEM",
    "GEN_AI_USAGE_COMPLETION_TOKENS",
    "GEN_AI_USAGE_PROMPT_TOKENS",
    "MAX_ATTR_VALUE_LENGTH",
    "NIRIZAN_PLANNING_CONTEXT",
    "NIRIZAN_PLANNING_OUTPUT",
    "NIRIZAN_RETRIEVAL_QUERY",
    "NIRIZAN_RETRIEVAL_RESULTS",
    "NIRIZAN_RETRIEVAL_TOP_K",
    "NIRIZAN_SESSION_ID",
    "NIRIZAN_SPAN_ID",
    "NIRIZAN_SPAN_ID_SOURCE",
    "NIRIZAN_SPAN_KIND",
    "NIRIZAN_TOOL_ARGUMENTS",
    "NIRIZAN_TOOL_NAME",
    "NIRIZAN_TOOL_RESULT",
    "NIRIZAN_TRACE_ID",
    "OTEL_SAMPLED",
    "OTEL_SPAN_ID",
    "OTEL_STATUS_CODE",
    "OTEL_STATUS_DESCRIPTION",
    "OTEL_TRACE_STATE",
    "SEMCONV_VERSION",
    "SEQ_ATTR_PREFIX",
    "SPAN_ID_SOURCE_DERIVED",
    "SPAN_ID_SOURCE_ROUNDTRIP",
    "TRUNCATION_SUFFIX",
    "decode_sequence_key",
    "encode_sequence_attribute_value",
    "encode_sequence_key",
    "is_sequence_key",
    "truncate_attribute_value",
]

# Upstream OpenTelemetry Semantic Conventions version standard.
# Refers to OpenTelemetry Semantic Conventions v1.27.0 which stabilized initial GenAI conventions.
SEMCONV_VERSION: str = "1.27.0"

# Attribute value limits and formatting defaults
MAX_ATTR_VALUE_LENGTH: int = 1024
TRUNCATION_SUFFIX: str = "...[truncated]"
SEQ_ATTR_PREFIX: str = "nirizan.seq."

# Standard OpenTelemetry GenAI Attributes
GEN_AI_SYSTEM: str = "gen_ai.system"
GEN_AI_OPERATION_NAME: str = "gen_ai.operation.name"
GEN_AI_REQUEST_MODEL: str = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL: str = "gen_ai.response.model"
GEN_AI_USAGE_PROMPT_TOKENS: str = "gen_ai.usage.prompt_tokens"
GEN_AI_USAGE_COMPLETION_TOKENS: str = "gen_ai.usage.completion_tokens"
GEN_AI_PROMPT: str = "gen_ai.prompt"
GEN_AI_COMPLETION: str = "gen_ai.completion"

# Custom NiriZan Domain Attributes (aligned with Plan §3.1)
NIRIZAN_SPAN_ID: str = "nirizan.span_id"
NIRIZAN_SPAN_ID_SOURCE: str = "nirizan.span_id.source"
NIRIZAN_TRACE_ID: str = "nirizan.trace_id"
NIRIZAN_SESSION_ID: str = "nirizan.session_id"  # Used as Baggage key or span attribute
NIRIZAN_SPAN_KIND: str = "nirizan.span.kind"  # Dot-separated per Plan §3.1

# Planning Span Attributes
NIRIZAN_PLANNING_CONTEXT: str = "nirizan.planning.context"
NIRIZAN_PLANNING_OUTPUT: str = "nirizan.planning.output"

# Retrieval Span Attributes
NIRIZAN_RETRIEVAL_QUERY: str = "nirizan.retrieval.query"
NIRIZAN_RETRIEVAL_RESULTS: str = "nirizan.retrieval.results"
NIRIZAN_RETRIEVAL_TOP_K: str = "nirizan.retrieval.top_k"

# Tool Use Span Attributes
NIRIZAN_TOOL_NAME: str = "nirizan.tool.name"
NIRIZAN_TOOL_ARGUMENTS: str = "nirizan.tool.arguments"
NIRIZAN_TOOL_RESULT: str = "nirizan.tool.result"

# Span ID Provenance Identifiers
SPAN_ID_SOURCE_ROUNDTRIP: str = "roundtrip"
SPAN_ID_SOURCE_DERIVED: str = "derived"

# Captured OTel Metadata Attributes (written during OTel -> NiriZan ingestion)
OTEL_SPAN_ID: str = "otel.span_id"
OTEL_SAMPLED: str = "otel.sampled"
OTEL_TRACE_STATE: str = "otel.trace_state"
OTEL_STATUS_CODE: str = "otel.status_code"
OTEL_STATUS_DESCRIPTION: str = "otel.status_description"


def truncate_attribute_value(
    value: str,
    max_length: int = MAX_ATTR_VALUE_LENGTH,
) -> str:
    """Truncate string attribute values exceeding max_length while appending a suffix.

    Args:
        value: The string attribute value to truncate.
        max_length: Maximum allowed character length including the suffix.

    Returns:
        The original string if within limit, or a truncated string ending in
        TRUNCATION_SUFFIX.

    Raises:
        ValueError: If max_length is less than or equal to the length of TRUNCATION_SUFFIX.

    Note:
        Length measurement is performed on Unicode code points (characters),
        not UTF-8 byte length.
    """
    suffix_len = len(TRUNCATION_SUFFIX)
    if max_length <= suffix_len:
        raise ValueError(
            f"max_length ({max_length}) must be strictly greater than suffix length ({suffix_len})."
        )

    if len(value) <= max_length:
        return value

    content_len = max_length - suffix_len
    return f"{value[:content_len]}{TRUNCATION_SUFFIX}"


def encode_sequence_key(key: str) -> str:
    """Prefix an attribute key to identify it as a JSON-encoded sequence attribute."""
    if is_sequence_key(key):
        return key
    return f"{SEQ_ATTR_PREFIX}{key}"


def decode_sequence_key(key: str) -> str:
    """Strip the sequence attribute prefix from a key, returning the original key name."""
    if is_sequence_key(key):
        return key[len(SEQ_ATTR_PREFIX) :]
    return key


def is_sequence_key(key: str) -> bool:
    """Check if an attribute key carries the reserved sequence prefix."""
    return key.startswith(SEQ_ATTR_PREFIX)


def encode_sequence_attribute_value(
    sequence: Sequence[object],
    max_length: int = MAX_ATTR_VALUE_LENGTH,
) -> str:
    """Serialize a sequence to a JSON string, keeping valid JSON structure if truncated.

    Attempts to trim tail items from the list before serializing to ensure the
    resulting string remains valid JSON ending with a truncation marker element.

    Args:
        sequence: A sequence of values (e.g., list, tuple) to encode.
        max_length: Maximum allowed character length for the output JSON string.

    Returns:
        A JSON-formatted string representation of the sequence.
    """
    items = list(sequence)
    try:
        raw_json = json.dumps(items, default=str)
    except Exception:
        items = [str(item) for item in items]
        raw_json = json.dumps(items)

    if len(raw_json) <= max_length:
        return raw_json

    # Iteratively remove tail items and insert sentinel to preserve valid JSON
    trimmed = items.copy()
    while trimmed:
        candidate_list = trimmed + [TRUNCATION_SUFFIX]
        candidate_json = json.dumps(candidate_list, default=str)
        if len(candidate_json) <= max_length:
            return candidate_json
        trimmed.pop()

    # Fallback if even a single item + sentinel cannot fit into max_length
    return truncate_attribute_value(raw_json, max_length=max_length)
