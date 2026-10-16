# src\nirizan\instrumentation\spans.py
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Set on a Span's ``attributes`` when an ingest adapter intentionally preserves
# a missing local parent as a synthetic dangling link. In OTel ingestion this
# means ``orphan_policy="emit"`` for a missing local OTel parent; children of
# dropped spans are re-attached to surviving ancestors without this marker,
# and remote parents produce roots. ``Trace.validate_span_trace_ids`` allows a
# dangling parent only when this attribute is set to ``True``, so an unmarked
# dangling parent is a real data-integrity bug.
#
# This constant lives in the core layer (``instrumentation/spans.py``) rather
# than in the OTel adapter, so the adapter imports it from core and core never
# imports the adapter; any future adapter that needs to emit synthetic
# parents can depend on this same constant without depending on OTel.
SYNTHETIC_PARENT_ATTRIBUTE: str = "nirizan.parent.synthetic"


class SpanKind(StrEnum):
    """The functional role of an execution span."""

    PLANNING = "planning"
    RETRIEVAL = "retrieval"
    TOOL_USE = "tool_use"
    GENERATION = "generation"


class Span(BaseModel):
    """The atomic unit of instrumentation: one step in an AI execution graph."""

    model_config = ConfigDict(frozen=True, strict=True)

    span_id: UUID
    trace_id: UUID
    parent_span_id: UUID | None = None
    kind: SpanKind
    name: str = Field(min_length=1, max_length=200)
    started_at: datetime
    ended_at: datetime
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)
    input_payload: str | None = None
    output_payload: str | None = None


class Trace(BaseModel):
    """An ordered collection of spans belonging to a single invocation."""

    model_config = ConfigDict(strict=True)

    trace_id: UUID
    application_name: str = Field(min_length=1)
    spans: list[Span] = Field(default_factory=list)
    created_at: datetime
    code_commit: str | None = None  # Phase 3: stamped by collector.py at ingest
    data_snapshot_id: str | None = None  # Phase 3: stamped by collector.py at ingest
    session_id: UUID | None = None  # Phase 3: set when captured inside Tracer.session(...)

    @model_validator(mode="after")
    def validate_span_trace_ids(self) -> Trace:
        """Ensure all spans share the trace's trace_id, and that every parent
        link either points at another span in this trace or is explicitly
        marked synthetic.

        A span whose ``parent_span_id`` is not in ``self.spans`` and is not
        marked with ``SYNTHETIC_PARENT_ATTRIBUTE`` is a dangling parent link:
        something that cannot be distinguished, by a consumer walking the
        trace, from data corruption. Ingest paths that intentionally
        re-parent an orphan onto a synthetic ancestor (one that was dropped
        rather than converted) must mark the result, or validation rejects it.
        """
        known_span_ids = {span.span_id for span in self.spans}
        for span in self.spans:
            if span.trace_id != self.trace_id:
                raise ValueError(
                    f"Span {span.span_id} trace_id ({span.trace_id}) "
                    f"does not match Trace trace_id ({self.trace_id})"
                )
            if span.parent_span_id is not None and span.parent_span_id not in known_span_ids:
                if span.attributes.get(SYNTHETIC_PARENT_ATTRIBUTE) is not True:
                    raise ValueError(
                        f"Span {span.span_id} has parent_span_id "
                        f"{span.parent_span_id} that is not in the trace and "
                        f"is not marked with {SYNTHETIC_PARENT_ATTRIBUTE!r}."
                    )
        return self

    def spans_of_kind(self, kind: SpanKind) -> list[Span]:
        """Return all spans matching a specific SpanKind."""
        return [s for s in self.spans if s.kind == kind]
