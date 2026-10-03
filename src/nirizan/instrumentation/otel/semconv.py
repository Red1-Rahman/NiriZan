# src/nirizan/instrumentation/otel/semconv.py
"""Semantic conventions and attribute helpers for OpenTelemetry integration.

This module defines standardized OpenTelemetry GenAI semantic conventions,
NiriZan custom attribute keys, OTel metadata attributes, limit constants, and
attribute sanitization / truncation helpers. It contains zero external package dependencies.
"""

import json
from collections.abc import Sequence

__all__ = [
    "GEN_AI_COMPLETION",
    "GEN_AI_OPERATION_NAME",
    "GEN_AI_PROMPT",
    "GEN_AI_PROVIDER_NAME",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_RESPONSE_MODEL",
    "GEN_AI_SYSTEM",
    "GEN_AI_USAGE_COMPLETION_TOKENS",
    "GEN_AI_USAGE_INPUT_TOKENS",
    "GEN_AI_USAGE_OUTPUT_TOKENS",
    "GEN_AI_USAGE_PROMPT_TOKENS",
    "ID_SOURCE_DERIVED",
    "ID_SOURCE_ROUNDTRIP",
    "MAX_ATTR_VALUE_LENGTH",
    "NIRIZAN_INSTRUMENTATION_SCOPE",
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
    "NIRIZAN_TRACE_ID_SOURCE",
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
    "dumps_attribute_json",
    "encode_sequence_attribute_value",
    "encode_sequence_key",
    "is_sequence_key",
    "truncate_attribute_value",
]

# Baseline upstream OpenTelemetry Semantic Conventions version that the
# attribute names below are modeled on (GenAI conventions upstream are
# experimental and keep moving). This is a compatibility baseline, not a
# claim that every constant is current: see the notes on deprecated
# attributes below. Names introduced after this baseline (for example
# GEN_AI_PROVIDER_NAME) are documented where they are defined.
# Provenance: https://github.com/open-telemetry/semantic-conventions/releases/tag/v1.27.0
SEMCONV_VERSION: str = "1.27.0"

# Attribute value limits and formatting defaults
MAX_ATTR_VALUE_LENGTH: int = 1024
TRUNCATION_SUFFIX: str = "...[truncated]"
SEQ_ATTR_PREFIX: str = "nirizan.seq."

# OpenTelemetry instrumentation scope name used by NiriZan's own exporter.
# The OTel -> NiriZan span processor uses it to recognize and skip spans that
# NiriZan itself exported, which prevents an export/ingest feedback loop when
# both bridge directions are attached to the same TracerProvider.
NIRIZAN_INSTRUMENTATION_SCOPE: str = "nirizan"

# Standard OpenTelemetry GenAI Attributes
#
# Upstream status notes (GenAI conventions are still evolving):
#   - gen_ai.system was later deprecated in favor of gen_ai.provider.name
#     (introduced in semantic conventions v1.37.0).
#   - gen_ai.prompt / gen_ai.completion were later deprecated upstream in
#     favor of event / message based content capture.
# NiriZan keeps reading and writing the older names for compatibility with
# existing consumers, and the exporter can emit the newer provider name next
# to the older system name. Remove the deprecated constants together with the
# dual-emit in a future release.
GEN_AI_SYSTEM: str = "gen_ai.system"
GEN_AI_PROVIDER_NAME: str = "gen_ai.provider.name"
GEN_AI_OPERATION_NAME: str = "gen_ai.operation.name"
GEN_AI_REQUEST_MODEL: str = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL: str = "gen_ai.response.model"

# Token usage attributes.
#
# v1.27.0 of the upstream semantic conventions (the version SEMCONV_VERSION
# pins above) renamed these from gen_ai.usage.prompt_tokens /
# gen_ai.usage.completion_tokens to gen_ai.usage.input_tokens /
# gen_ai.usage.output_tokens, "to align terminology between spans and
# metrics". See:
# https://github.com/open-telemetry/semantic-conventions/releases/tag/v1.27.0
#
# GEN_AI_USAGE_INPUT_TOKENS / GEN_AI_USAGE_OUTPUT_TOKENS are the current
# (v1.27.0+) names and are what to_otel.py's exporter treats as canonical.
# GEN_AI_USAGE_PROMPT_TOKENS / GEN_AI_USAGE_COMPLETION_TOKENS are kept as
# the pre-rename names: to_otel.py emits both old and new keys for one
# release so that any existing consumer still reading the old names is not
# silently broken by this change. The old constants and the dual-emit
# should be removed together in a follow-up release once consumers have
# had time to move to the new names.
GEN_AI_USAGE_INPUT_TOKENS: str = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS: str = "gen_ai.usage.output_tokens"
GEN_AI_USAGE_PROMPT_TOKENS: str = "gen_ai.usage.prompt_tokens"
GEN_AI_USAGE_COMPLETION_TOKENS: str = "gen_ai.usage.completion_tokens"

GEN_AI_PROMPT: str = "gen_ai.prompt"
GEN_AI_COMPLETION: str = "gen_ai.completion"

# Custom NiriZan Domain Attributes
NIRIZAN_SPAN_ID: str = "nirizan.span_id"
NIRIZAN_SPAN_ID_SOURCE: str = "nirizan.span_id.source"
NIRIZAN_TRACE_ID: str = "nirizan.trace_id"
NIRIZAN_TRACE_ID_SOURCE: str = "nirizan.trace_id.source"
NIRIZAN_SPAN_KIND: str = "nirizan.span.kind"  # Dot-separated per Plan §3.1
NIRIZAN_SESSION_ID: str = "nirizan.session_id"  # Session identifier span attribute

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

# Span/Trace ID Provenance Identifiers
#
# These two values are reused as the value for both NIRIZAN_SPAN_ID_SOURCE
# and NIRIZAN_TRACE_ID_SOURCE. The two questions they answer -- "was this id
# recovered from a stashed nirizan.* attribute, or freshly derived from the
# OTel id?" -- are identical in kind; only the id being described differs.
# Span-level and trace-level provenance are still tracked as two separate
# *attributes* (NIRIZAN_SPAN_ID_SOURCE vs NIRIZAN_TRACE_ID_SOURCE) because
# they can genuinely disagree: a trace re-ingested from a stashed
# nirizan.trace_id can still contain one child span that arrived from a
# genuinely external system and had no stashed nirizan.span_id, so its
# span_id must be derived even though the trace_id round-tripped.
#
# ID_SOURCE_* are the neutral names, since the values describe either kind
# of id. SPAN_ID_SOURCE_* are kept as aliases so existing imports keep
# working; both names refer to the same string values.
ID_SOURCE_ROUNDTRIP: str = "roundtrip"
ID_SOURCE_DERIVED: str = "derived"
SPAN_ID_SOURCE_ROUNDTRIP: str = ID_SOURCE_ROUNDTRIP
SPAN_ID_SOURCE_DERIVED: str = ID_SOURCE_DERIVED

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
    """Prefix an attribute key to identify it as a JSON-encoded sequence attribute.

    Raises:
        ValueError: If key is empty or whitespace-only.
    """
    if not key or not key.strip():
        raise ValueError("Sequence key cannot be empty or whitespace-only.")
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


def dumps_attribute_json(value: object) -> str:
    """Serialize ``value`` to JSON text for use as a span attribute value.

    This is the single place that decides how NiriZan formats JSON attribute
    values, so the exporter and the sequence encoder stay consistent.

    * Non-ASCII text is kept as-is (``ensure_ascii=False``). With the default
      ASCII escaping, a Bangla or Arabic character costs about six characters
      of the length budget instead of one, so non-English content would be
      truncated far earlier than English content.
    * If the unescaped text cannot be encoded as UTF-8 (for example a lone
      surrogate left behind by a lossy decode), the value is re-serialized
      with ASCII escaping so the result can always be exported.
    * Values that are not natively JSON serializable are rendered with
      ``str`` via ``default=str``.

    Raises:
        TypeError: If the value contains something ``default=str`` cannot
            handle, such as a non-string dict key that is not a basic scalar.
        ValueError: If the value contains a circular reference.
        RecursionError: If the value is nested too deeply to serialize.
    """
    text = json.dumps(value, ensure_ascii=False, default=str)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        text = json.dumps(value, ensure_ascii=True, default=str)
    return text


def _dumps_item(item: object) -> str:
    """Serialize one sequence item, falling back to its ``str`` form if needed."""
    try:
        return dumps_attribute_json(item)
    except (TypeError, ValueError, RecursionError):
        return dumps_attribute_json(str(item))


def encode_sequence_attribute_value(
    sequence: Sequence[object],
    max_length: int = MAX_ATTR_VALUE_LENGTH,
) -> str:
    """Serialize a sequence to a JSON string, strictly preserving valid JSON structure.

    If the full JSON array does not fit within ``max_length``, the longest
    prefix of items that fits is kept and a ``TRUNCATION_SUFFIX`` element is
    appended, so the result is always a valid JSON array.

    The work is a single forward pass that stops serializing as soon as the
    budget is exceeded, so the cost is bounded by ``max_length`` rather than by
    the size of the input sequence. Each item is serialized exactly once; an
    item that cannot be serialized natively is replaced by its ``str`` form
    without affecting the other items.

    Args:
        sequence: A sequence of values (e.g., list, tuple) to encode.
        max_length: Maximum allowed character length for the output JSON string.

    Returns:
        A JSON-formatted string representation of the sequence.

    Raises:
        ValueError: If max_length is too small to fit even a sentinel-only array as valid JSON.

    Note:
        ``TRUNCATION_SUFFIX`` is appended as a list item to mark truncation. If a real
        sequence item equals ``TRUNCATION_SUFFIX`` exactly, consumers should check
        total string length against limits if disambiguation is required.
        Length is measured in characters (code points), not UTF-8 bytes.
    """
    # Output layout for k items is "[" + ", ".join(parts) + "]", which is
    # 2 + sum(len(part)) + 2 * (k - 1) characters for k >= 1 and 2 for k == 0.
    parts: list[str] = []
    total = 0
    exceeded = False
    for item in sequence:
        part = _dumps_item(item)
        parts.append(part)
        total += len(part)
        if 2 + total + 2 * (len(parts) - 1) > max_length:
            # Any longer prefix is longer still, so stop serializing here.
            exceeded = True
            break

    if not exceeded:
        candidate = "[" + ", ".join(parts) + "]"
        if len(candidate) <= max_length:
            return candidate

    # Keep the longest prefix such that prefix + sentinel still fits. For k kept
    # items plus the sentinel there are k separators of two characters each.
    sentinel = dumps_attribute_json(TRUNCATION_SUFFIX)
    kept = 0
    kept_total = 0
    for part in parts:
        if 2 + kept_total + len(part) + len(sentinel) + 2 * (kept + 1) > max_length:
            break
        kept_total += len(part)
        kept += 1

    if kept > 0:
        return "[" + ", ".join([*parts[:kept], sentinel]) + "]"

    sentinel_only = "[" + sentinel + "]"
    if len(sentinel_only) <= max_length:
        return sentinel_only

    raise ValueError(
        f"Cannot encode sequence as valid JSON within max_length={max_length}; "
        f"sentinel-only form requires {len(sentinel_only)} characters."
    )
