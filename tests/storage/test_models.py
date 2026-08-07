# tests/storage/test_models.py
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.metrics.base import MetricResult
from nirizan.storage.models import Baseline, Run, SpanRecord, TraceRecord


def test_span_record_round_trip() -> None:
    now = datetime.now(timezone.utc)
    span = Span(
        span_id=uuid4(),
        trace_id=uuid4(),
        parent_span_id=uuid4(),
        kind=SpanKind.LLM,
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
    now = datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
    valid_run = Run(
        run_id=uuid4(),
        trace_id=uuid4(),
        code_commit="1234567",  # minimum 7 characters
        data_snapshot_id="snap_1",
        metric_results=[MetricResult(metric_name="accuracy", score=0.95)],
        created_at=now,
    )
    assert valid_run.code_commit == "1234567"

    # Commit too short (<7 chars)
    with pytest.raises(ValidationError):
        Run(
            run_id=uuid4(),
            trace_id=uuid4(),
            code_commit="123456",
            data_snapshot_id="snap_1",
            created_at=now,
        )

    # Empty data snapshot ID (<1 char)
    with pytest.raises(ValidationError):
        Run(
            run_id=uuid4(),
            trace_id=uuid4(),
            code_commit="1234567",
            data_snapshot_id="",
            created_at=now,
        )


def test_baseline_validation() -> None:
    now = datetime.now(timezone.utc)
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
