from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpanKind(str, Enum):
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
        """Ensure all spans in the trace share the trace's trace_id."""
        for span in self.spans:
            if span.trace_id != self.trace_id:
                raise ValueError(
                    f"Span {span.span_id} trace_id ({span.trace_id}) "
                    f"does not match Trace trace_id ({self.trace_id})"
                )
        return self

    def spans_of_kind(self, kind: SpanKind) -> list[Span]:
        """Return all spans matching a specific SpanKind."""
        return [s for s in self.spans if s.kind == kind]
