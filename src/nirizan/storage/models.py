import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.metrics.base import MetricResult as MetricResult


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
        """Inverse of from_span; keeps this record shape an internal storage detail on the read path too."""
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
    code_commit: Optional[str] = None
    data_snapshot_id: Optional[str] = None
    session_id: Optional[str] = None

    @classmethod
    def from_trace(cls, trace: Trace) -> "TraceRecord":
        return cls(
            trace_id=str(trace.trace_id),
            application_name=trace.application_name,
            created_at=trace.created_at.isoformat(),
            spans=[SpanRecord.from_span(s) for s in trace.spans],
            code_commit=trace.code_commit,
            data_snapshot_id=trace.data_snapshot_id,
            session_id=str(trace.session_id) if trace.session_id else None,
        )

    def to_trace(self) -> Trace:
        """Inverse of from_trace."""
        return Trace(
            trace_id=UUID(self.trace_id),
            application_name=self.application_name,
            created_at=datetime.fromisoformat(self.created_at),
            spans=[s.to_span() for s in self.spans],
            code_commit=self.code_commit,
            data_snapshot_id=self.data_snapshot_id,
            session_id=UUID(self.session_id) if self.session_id else None,
        )


class Run(BaseModel):
    """A trace plus the MetricResults computed against it, versioned by code commit and data snapshot."""

    model_config = ConfigDict(strict=True)

    run_id: UUID
    trace_id: UUID
    code_commit: str = Field(min_length=7, max_length=40)  # git SHA, short or full
    data_snapshot_id: str = Field(min_length=1)
    metric_results: list[MetricResult] = Field(default_factory=list)
    created_at: datetime


class Baseline(BaseModel):
    """A named, queryable set of 'known good' historical runs; references Run objects by ID, never embeds them."""

    model_config = ConfigDict(strict=True)

    baseline_id: UUID
    system_type: str
    run_ids: list[UUID] = Field(min_length=1)
    established_at: datetime
    label: str = Field(min_length=1)  # e.g. "pre-v0.3-release", "weekly-2026-08"
