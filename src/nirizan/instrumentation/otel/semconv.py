# src\nirizan\instrumentation\otel\semconv.py
"""Semantic conventions and attribute helpers for OpenTelemetry integration.

This module defines standardized OpenTelemetry GenAI semantic conventions,
NiriZan custom attribute keys, limit constants, and attribute sanitization
/ truncation helpers. It contains zero external package dependencies.
"""

import json
from typing import Any, Sequence

__all__ = [
    "GEN_AI_COMPLETION",
    "GEN_AI_PROMPT",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_RESPONSE_MODEL",
    "GEN_AI_SYSTEM",
    "GEN_AI_USAGE_COMPLETION_TOKENS",
    "GEN_AI_USAGE_PROMPT_TOKENS",
    "MAX_ATTR_VALUE_LENGTH",
    "NIRIZAN_RETRIEVAL_DOCUMENTS",
    "NIRIZAN_RETRIEVAL_QUERY",
    "NIRIZAN_RETRIEVAL_TOP_K",
    "NIRIZAN_SESSION_ID",
    "NIRIZAN_SPAN_ID",
    "NIRIZAN_SPAN_ID_SOURCE",
    "NIRIZAN_SPAN_KIND",
    "NIRIZAN_TOOL_ARGS",
    "NIRIZAN_TOOL_NAME",
    "NIRIZAN_TOOL_RESULT",
    "NIRIZAN_TRACE_ID",
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

# Upstream OpenTelemetry Semantic Conventions version standard
SEMCONV_VERSION: str = "1.27.0"

# Attribute value limits and formatting defaults
MAX_ATTR_VALUE_LENGTH: int = 1024
TRUNCATION_SUFFIX: str = "...[truncated]"
SEQ_ATTR_PREFIX: str = "nirizan.seq."

# Standard OpenTelemetry GenAI Attributes
GEN_AI_SYSTEM: str = "gen_ai.system"
GEN_AI_REQUEST_MODEL: str = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL: str = "gen_ai.response.model"
GEN_AI_USAGE_PROMPT_TOKENS: str = "gen_ai.usage.prompt_tokens"
GEN_AI_USAGE_COMPLETION_TOKENS: str = "gen_ai.usage.completion_tokens"
GEN_AI_PROMPT: str = "gen_ai.prompt"
GEN_AI_COMPLETION: str = "gen_ai.completion"

# Custom NiriZan Attributes
NIRIZAN_SPAN_ID: str = "nirizan.span_id"
NIRIZAN_SPAN_ID_SOURCE: str = "nirizan.span_id.source"
NIRIZAN_TRACE_ID: str = "nirizan.trace_id"
NIRIZAN_SESSION_ID: str = "nirizan.session_id"
NIRIZAN_SPAN_KIND: str = "nirizan.span_kind"

# Retrieval Span Attributes
NIRIZAN_RETRIEVAL_QUERY: str = "nirizan.retrieval.query"
NIRIZAN_RETRIEVAL_DOCUMENTS: str = "nirizan.retrieval.documents"
NIRIZAN_RETRIEVAL_TOP_K: str = "nirizan.retrieval.top_k"

# Tool Use Span Attributes
NIRIZAN_TOOL_NAME: str = "nirizan.tool.name"
NIRIZAN_TOOL_ARGS: str = "nirizan.tool.args"
NIRIZAN_TOOL_RESULT: str = "nirizan.tool.result"

# Span ID Provenance Identifiers
SPAN_ID_SOURCE_ROUNDTRIP: str = "roundtrip"
SPAN_ID_SOURCE_DERIVED: str = "derived"


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
    """
    if len(value) <= max_length:
        return value

    suffix_len = len(TRUNCATION_SUFFIX)
    if max_length <= suffix_len:
        return TRUNCATION_SUFFIX[:max_length]

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
    sequence: Sequence[Any],
    max_length: int = MAX_ATTR_VALUE_LENGTH,
) -> str:
    """Serialize a sequence to a JSON string and apply length truncation.

    Args:
        sequence: A sequence of values (e.g. list, tuple) to encode.
        max_length: Maximum allowed character length for the output JSON string.

    Returns:
        A JSON-formatted string representation of the sequence, truncated if needed.
    """
    try:
        raw_json = json.dumps(list(sequence), default=str)
    except Exception:
        raw_json = json.dumps([str(item) for item in sequence])

    return truncate_attribute_value(raw_json, max_length=max_length)
