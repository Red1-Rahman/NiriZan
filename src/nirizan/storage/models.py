# src/nirizan/storage/models.py
import json
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nirizan._logging import get_logger
from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.metrics.base import MetricResult as MetricResult

logger = get_logger(__name__)


def _utc_isoformat(value: datetime) -> str:
    """Serialize an aware datetime in canonical UTC ISO-8601 form (write path, strict)."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Persisted datetimes must be timezone-aware.")
    return value.astimezone(UTC).isoformat()


def _parse_utc_datetime(value: str) -> datetime:
    """Parse a persisted datetime and normalize it to UTC (read path, tolerant).

    A value with no offset is a legacy row written before the canonical-UTC
    policy. It is interpreted as UTC (matching SQLite ``julianday()`` semantics
    for offset-less strings), returned as an aware UTC datetime, and logged
    once per process. The stored row is never rewritten on read.

    A value that is not a valid ISO-8601 datetime raises a clear ``ValueError``
    naming the stored text, rather than being silently skipped.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as err:
        raise ValueError(f"Stored timestamp {value!r} is not a valid ISO-8601 datetime.") from err
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _warn_legacy_naive_once(value)
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _warn_legacy_naive_once(stored_value: str) -> None:
    """Emit the legacy-row warning at most once per process."""
    if getattr(_warn_legacy_naive_once, "_warned", False):
        return
    # The latch lives on the function rather than in a module global so that a
    # test can reset it without touching module state other readers share.
    _warn_legacy_naive_once._warned = True  # type: ignore[attr-defined]  # mypy: a function object has no attributes
    logger.warning(
        "Stored timestamp %r has no timezone offset; reading it as UTC "
        "(legacy row, stored value left unchanged).",
        stored_value,
    )


class SpanRecord(BaseModel):
    """Database record representation of a Span."""

    span_id: str
    trace_id: str
    parent_span_id: str | None = None
    kind: str
    name: str
    started_at: str
    ended_at: str
    attributes_json: str = "{}"
    input_payload: str | None = None
    output_payload: str | None = None

    @classmethod
    def from_span(cls, span: Span) -> "SpanRecord":
        return cls(
            span_id=str(span.span_id),
            trace_id=str(span.trace_id),
            parent_span_id=str(span.parent_span_id) if span.parent_span_id else None,
            kind=span.kind.value,
            name=span.name,
            started_at=_utc_isoformat(span.started_at),
            ended_at=_utc_isoformat(span.ended_at),
            attributes_json=json.dumps(span.attributes),
            input_payload=span.input_payload,
            output_payload=span.output_payload,
        )

    def to_span(self) -> Span:
        """Inverse of from_span; keeps this record shape an internal storage detail
        on the read path too."""
        return Span(
            span_id=UUID(self.span_id),
            trace_id=UUID(self.trace_id),
            parent_span_id=UUID(self.parent_span_id) if self.parent_span_id else None,
            kind=SpanKind(self.kind),
            name=self.name,
            started_at=_parse_utc_datetime(self.started_at),
            ended_at=_parse_utc_datetime(self.ended_at),
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
    code_commit: str | None = None
    data_snapshot_id: str | None = None
    session_id: str | None = None

    @classmethod
    def from_trace(cls, trace: Trace) -> "TraceRecord":
        return cls(
            trace_id=str(trace.trace_id),
            application_name=trace.application_name,
            created_at=_utc_isoformat(trace.created_at),
            spans=[SpanRecord.from_span(s) for s in trace.spans],
            code_commit=trace.code_commit,
            data_snapshot_id=trace.data_snapshot_id,
            session_id=str(trace.session_id) if trace.session_id else None,
        )

    def to_trace(self, *, validate: bool = True) -> Trace:
        """Inverse of from_trace.

        Persisted records can predate validators added to ``Trace``. The
        repository uses ``validate=False`` when reading those records so a
        legacy row cannot make an otherwise valid query fail.
        """
        if validate:
            return Trace(
                trace_id=UUID(self.trace_id),
                application_name=self.application_name,
                created_at=_parse_utc_datetime(self.created_at),
                spans=[s.to_span() for s in self.spans],
                code_commit=self.code_commit,
                data_snapshot_id=self.data_snapshot_id,
                session_id=UUID(self.session_id) if self.session_id else None,
            )
        return Trace.model_construct(
            trace_id=UUID(self.trace_id),
            application_name=self.application_name,
            created_at=_parse_utc_datetime(self.created_at),
            spans=[s.to_span() for s in self.spans],
            code_commit=self.code_commit,
            data_snapshot_id=self.data_snapshot_id,
            session_id=UUID(self.session_id) if self.session_id else None,
        )


class Run(BaseModel):
    """A trace plus the MetricResults computed against it, versioned by code
    commit and data snapshot."""

    model_config = ConfigDict(strict=True)

    run_id: UUID
    trace_id: UUID
    code_commit: str = Field(min_length=7, max_length=40)  # git SHA, short or full
    data_snapshot_id: str = Field(min_length=1)
    metric_results: list[MetricResult] = Field(default_factory=list)
    created_at: datetime


class Baseline(BaseModel):
    """A named, queryable set of 'known good' historical runs; references Run
    objects by ID, never embeds them."""

    model_config = ConfigDict(strict=True)

    baseline_id: UUID
    system_type: str
    run_ids: list[UUID] = Field(min_length=1)
    established_at: datetime
    label: str = Field(min_length=1)  # e.g. "pre-v0.3-release", "weekly-2026-08"
