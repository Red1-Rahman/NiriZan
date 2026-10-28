"""Regression coverage for trace identity and producer ownership boundaries."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from nirizan.instrumentation.otel._id_mapping import otel_span_id_to_uuid
from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.storage.trace_repository import SQLiteTraceRepository


def _trace(trace_id: UUID, span_id: UUID, app: str = "producer") -> Trace:
    now = datetime.now(UTC)
    span = Span(span_id=span_id, trace_id=trace_id, kind=SpanKind.GENERATION,
                name="root", started_at=now, ended_at=now)
    return Trace(trace_id=trace_id, application_name=app, spans=[span], created_at=now)


@pytest.mark.asyncio
async def test_otel_span_id_collision_across_traces_is_rejected_atomically(tmp_path):
    # OTel span IDs map directly to NiriZan UUIDs; trace IDs are separate.
    repo = SQLiteTraceRepository(str(tmp_path / "traces.db"))
    span_id = otel_span_id_to_uuid(0x123456789ABCDEF)
    a, b = uuid4(), uuid4()
    await repo.save(_trace(a, span_id))
    with pytest.raises(ValueError):
        await repo.save(_trace(b, span_id))
    assert await repo.get(b) is None
    assert (await repo.get(a)).spans[0].span_id == span_id
    repo.close()


@pytest.mark.xfail(strict=True, reason="tracked: NZ-SEC-002")
def test_otel_service_name_is_bound_to_a_producer_identity():
    # Finding NZ-SEC-002: service.name is producer-controlled and has no identity binding.
    from pathlib import Path
    source = (Path(__file__).parents[2] / "src/nirizan/instrumentation/otel/from_otel.py").read_text()
    assert "application_name = allowlist[producer_identity]" in source


@pytest.mark.xfail(strict=True, reason="tracked: NZ-SEC-003")
@pytest.mark.asyncio
async def test_trace_upsert_rejects_application_name_takeover(tmp_path):
    # Finding NZ-SEC-003: same trace_id can replace application_name and prune spans.
    repo = SQLiteTraceRepository(str(tmp_path / "traces.db"))
    trace_id = uuid4()
    first, second = uuid4(), uuid4()
    await repo.save(_trace(trace_id, first, "owner-a"))
    await repo.save(_trace(trace_id, second, "owner-b"))
    stored = await repo.get(trace_id)
    assert stored.application_name == "owner-a"
    assert {s.span_id for s in stored.spans} == {first}
    repo.close()
