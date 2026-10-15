# tests/storage/test_models.py
import logging
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.metrics.base import MetricResult
from nirizan.storage.models import (
    Baseline,
    Run,
    SpanRecord,
    TraceRecord,
    _parse_utc_datetime,
    _utc_isoformat,
)


def test_span_record_round_trip() -> None:
    now = datetime.now(UTC)
    span = Span(
        span_id=uuid4(),
        trace_id=uuid4(),
        parent_span_id=uuid4(),
        kind=SpanKind.GENERATION,
        name="test_llm_call",
        started_at=now,
        ended_at=now,
        attributes={"model": "gpt-4o", "temperature": 0.2},
        input_payload="User query",
        output_payload="Agent response",
    )

    record = SpanRecord.from_span(span)
    reconstructed = record.to_span()

    assert reconstructed.span_id == span.span_id
    assert reconstructed.trace_id == span.trace_id
    assert reconstructed.parent_span_id == span.parent_span_id
    assert reconstructed.kind == span.kind
    assert reconstructed.name == span.name
    assert reconstructed.started_at == span.started_at
    assert reconstructed.ended_at == span.ended_at
    assert reconstructed.attributes == span.attributes
    assert reconstructed.input_payload == span.input_payload
    assert reconstructed.output_payload == span.output_payload


def test_trace_record_round_trip() -> None:
    now = datetime.now(UTC)
    session_id = uuid4()
    trace = Trace(
        trace_id=uuid4(),
        application_name="nirizan_test_app",
        created_at=now,
        spans=[],
        code_commit="a1b2c3d4e5f67890",
        data_snapshot_id="snapshot_2026_08_07",
        session_id=session_id,
    )

    record = TraceRecord.from_trace(trace)
    reconstructed = record.to_trace()

    assert reconstructed.trace_id == trace.trace_id
    assert reconstructed.application_name == trace.application_name
    assert reconstructed.created_at == trace.created_at
    assert reconstructed.code_commit == "a1b2c3d4e5f67890"
    assert reconstructed.data_snapshot_id == "snapshot_2026_08_07"
    assert reconstructed.session_id == session_id


def test_run_validation() -> None:
    now = datetime.now(UTC)
    trace_id = uuid4()
    valid_run = Run(
        run_id=uuid4(),
        trace_id=trace_id,
        code_commit="1234567",  # minimum 7 characters
        data_snapshot_id="snap_1",
        metric_results=[
            MetricResult(
                metric_name="accuracy",
                trace_id=trace_id,
                score=0.95,
                computed_at=now,
            )
        ],
        created_at=now,
    )
    assert valid_run.code_commit == "1234567"

    # Commit too short (<7 chars)
    with pytest.raises(ValidationError):
        Run(
            run_id=uuid4(),
            trace_id=trace_id,
            code_commit="123456",
            data_snapshot_id="snap_1",
            created_at=now,
        )

    # Empty data snapshot ID (<1 char)
    with pytest.raises(ValidationError):
        Run(
            run_id=uuid4(),
            trace_id=trace_id,
            code_commit="1234567",
            data_snapshot_id="",
            created_at=now,
        )


def test_baseline_validation() -> None:
    now = datetime.now(UTC)
    valid_baseline = Baseline(
        baseline_id=uuid4(),
        system_type="rag_agent",
        run_ids=[uuid4()],
        established_at=now,
        label="v1.0-release",
    )
    assert valid_baseline.label == "v1.0-release"

    # Empty run_ids list (requires min 1)
    with pytest.raises(ValidationError):
        Baseline(
            baseline_id=uuid4(),
            system_type="rag_agent",
            run_ids=[],
            established_at=now,
            label="empty_baseline",
        )

    # Empty label
    with pytest.raises(ValidationError):
        Baseline(
            baseline_id=uuid4(),
            system_type="rag_agent",
            run_ids=[uuid4()],
            established_at=now,
            label="",
        )


# ---------------------------------------------------------------------------
# Timestamp serialization helpers (write strict / read tolerant)
# ---------------------------------------------------------------------------


def test_utc_isoformat_normalizes_offsets_to_utc() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))

    result = _utc_isoformat(datetime(2026, 1, 1, 5, 30, tzinfo=ist))

    assert result == "2026-01-01T00:00:00+00:00"


def test_utc_isoformat_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _utc_isoformat(datetime(2026, 1, 1))


def test_parse_utc_datetime_normalizes_offset_to_utc() -> None:
    parsed = _parse_utc_datetime("2026-01-01T05:30:00+05:30")

    assert parsed == datetime(2026, 1, 1, tzinfo=UTC)
    assert parsed.utcoffset() == timedelta(0)


def test_parse_utc_datetime_accepts_z_suffix() -> None:
    parsed = _parse_utc_datetime("2026-01-01T00:00:00Z")

    assert parsed == datetime(2026, 1, 1, tzinfo=UTC)


def test_parse_utc_datetime_reads_naive_as_utc(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("nirizan.storage.models._LEGACY_NAIVE_WARNED", False)

    with caplog.at_level(logging.WARNING):
        parsed = _parse_utc_datetime("2025-06-01T12:00:00")

    assert parsed == datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    assert parsed.utcoffset() == timedelta(0)
    warnings = [
        record
        for record in caplog.records
        if record.name == "nirizan.storage.models" and record.levelno >= logging.WARNING
    ]
    assert len(warnings) == 1
    assert "2025-06-01T12:00:00" in warnings[0].getMessage()


def test_parse_utc_datetime_warns_once_per_process(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("nirizan.storage.models._LEGACY_NAIVE_WARNED", False)

    with caplog.at_level(logging.WARNING):
        _parse_utc_datetime("2025-06-01T12:00:00")
        _parse_utc_datetime("2025-06-02T12:00:00")
        _parse_utc_datetime("2025-06-03T12:00:00")

    warnings = [
        record
        for record in caplog.records
        if record.name == "nirizan.storage.models" and record.levelno >= logging.WARNING
    ]
    assert len(warnings) == 1
    # Only the first offending value is named in the warning.
    assert "2025-06-01T12:00:00" in warnings[0].getMessage()


def test_parse_utc_datetime_malformed_raises_clear_value_error() -> None:
    with pytest.raises(ValueError, match="'not-a-timestamp'"):
        _parse_utc_datetime("not-a-timestamp")


def test_span_record_round_trip_normalizes_to_utc() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    started = datetime(2026, 1, 1, 5, 30, tzinfo=ist)
    span = Span(
        span_id=uuid4(),
        trace_id=uuid4(),
        kind=SpanKind.GENERATION,
        name="offset-span",
        started_at=started,
        ended_at=started + timedelta(seconds=1),
        attributes={},
    )

    record = SpanRecord.from_span(span)
    reconstructed = record.to_span()

    assert record.started_at == "2026-01-01T00:00:00+00:00"
    assert reconstructed.started_at == started.astimezone(UTC)
    assert reconstructed.ended_at == (started + timedelta(seconds=1)).astimezone(UTC)
