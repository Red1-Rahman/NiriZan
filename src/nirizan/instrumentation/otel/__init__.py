# src/nirizan/instrumentation/otel/__init__.py
"""OpenTelemetry integration adapters and semantic convention helpers for NiriZan.

This package provides bridging between OpenTelemetry traces/spans and NiriZan
data structures.

Submodules:
    - _id_mapping: Zero-dependency conversion utilities for 128-bit / 64-bit IDs.
    - semconv: Standardized attribute keys, limit constants, and sequence helpers.
      (See ``semconv.__all__`` for the complete list of exported constants).
    - to_otel: Exporter converting NiriZan traces into OpenTelemetry spans
      (requires ``opentelemetry-api``).
    - from_otel: SpanProcessor converting OpenTelemetry spans into NiriZan traces
      (requires ``opentelemetry-sdk``).

Import Hygiene:
    To prevent missing-dependency errors when ``opentelemetry-api`` or
    ``opentelemetry-sdk`` is not installed in the target environment, this
    ``__init__.py`` re-exports only ``_id_mapping`` and ``semconv``. Modules
    requiring OpenTelemetry packages (``to_otel`` and ``from_otel``) must be
    explicitly imported by callers.
"""

from nirizan.instrumentation.otel import _id_mapping, semconv

__all__ = [
    "_id_mapping",
    "semconv",
]
