import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from nirizan.instrumentation.spans import Span, SpanKind, Trace


class SpanRecord(BaseModel):
    """Database record representation of a Span."""

    span_id: str
    trace_id: str
    parent_span_id: Optional[str] = None
    kind: str
    name: str
    started_at: str
    ended_at: str
    attributes_json: str = "{}"
    input_payload: Optional[str] = None
    output_payload: Optional[str] = None

    @classmethod
    def from_span(cls, span: Span) -> "SpanRecord":
        """Convert an in-memory Span model into a persistent SpanRecord."""
        return cls(
            span_id=str(span.span_id),
            trace_id=str(span.trace_id),
            parent_span_id=str(span.parent_span_id) if span.parent_span_id else None,
            kind=span.kind.value,
            name=span.name,
            started_at=span.started_at.isoformat(),
            ended_at=span.ended_at.isoformat(),
            attributes_json=json.dumps(span.attributes),
            input_payload=span.input_payload,
            output_payload=span.output_payload,
        )

    def to_span(self) -> Span:
        """Convert a persistent SpanRecord back into an in-memory Span model."""
        return Span(
            span_id=UUID(self.span_id),
            trace_id=UUID(self.trace_id),
            parent_span_id=UUID(self.parent_span_id) if self.parent_span_id else None,
            kind=SpanKind(self.kind),
            name=self.name,
            started_at=datetime.fromisoformat(self.started_at),
            ended_at=datetime.fromisoformat(self.ended_at),
            attributes=json.loads(self.attributes_json),
            input_payload=self.input_payload,
            output_payload=self.output_payload,
        )


class TraceRecord(BaseModel):
    """Database record representation of a complete Trace."""

    trace_id: str
    application_name: str
    created_at: str
    spans: list[SpanRecord] = Field(default_factory=list)

    @classmethod
    def from_trace(cls, trace: Trace) -> "TraceRecord":
        """Convert an in-memory Trace model into a persistent TraceRecord."""
        return cls(
            trace_id=str(trace.trace_id),
            application_name=trace.application_name,
            created_at=trace.created_at.isoformat(),
            spans=[SpanRecord.from_span(s) for s in trace.spans],
        )

    def to_trace(self) -> Trace:
        """Convert a persistent TraceRecord back into an in-memory Trace model.
        Inverse of from_trace. See SpanRecord.to_span for why this exists.
        """
        return Trace(
            trace_id=UUID(self.trace_id),
            application_name=self.application_name,
            created_at=datetime.fromisoformat(self.created_at),
            spans=[s.to_span() for s in self.spans],
        )
