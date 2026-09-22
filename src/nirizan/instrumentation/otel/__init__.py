# src\nirizan\instrumentation\otel\__init__.py
"""OpenTelemetry integration adapters and semantic convention helpers for NiriZan.

This package provides bridging between OpenTelemetry traces/spans and NiriZan
data structures.

Submodules:
    - id_mapping: Zero-dependency conversion utilities for 128-bit / 64-bit IDs.
    - semconv: Standardized attribute keys, limit constants, and sequence helpers[cite: 11].
      (See `semconv.__all__` for the complete list of exported constants).
    - to_otel: Exporter converting NiriZan traces into OpenTelemetry spans
      (requires `opentelemetry-api`)[cite: 11].
    - from_otel: SpanProcessor converting OpenTelemetry spans into NiriZan traces
      (requires `opentelemetry-sdk`)[cite: 11].

Import Hygiene:
    To prevent missing-dependency errors when `opentelemetry-api` or `opentelemetry-sdk`
    is not installed in the target environment, this `__init__.py` re-exports only
    `id_mapping` and `semconv`[cite: 11]. Modules requiring OpenTelemetry packages (`to_otel`
    and `from_otel`) must be explicitly imported by callers[cite: 11].
"""

from nirizan.instrumentation.otel import id_mapping, semconv

__all__ = [
    "id_mapping",
    "semconv",
]
