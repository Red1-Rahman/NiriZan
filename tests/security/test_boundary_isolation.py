# tests/security/test_boundary_isolation.py
"""Regression coverage for trace identity and producer ownership boundaries."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from nirizan.instrumentation.otel._id_mapping import otel_span_id_to_uuid
from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.storage.trace_repository import SQLiteTraceRepository


def _trace(trace_id: UUID, span_id: UUID, app: str = "producer") -> Trace:
    now = datetime.now(UTC)
    span = Span(
        span_id=span_id,
        trace_id=trace_id,
        kind=SpanKind.GENERATION,
        name="root",
        started_at=now,
        ended_at=now,
    )
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
def test_otel_service_name_is_not_trusted_as_the_sole_application_identity():
    # Finding NZ-SEC-002: service.name is producer-controlled with no identity
    # binding, so any producer can claim another application's namespace.
    #
    # This asserts BEHAVIOR, not source text: two producers claim the same
    # service.name via the span resource, but are otherwise distinguishable
    # (different OTel resource attributes / connection context depending on
    # how the eventual fix exposes producer identity). The resulting
    # application_name must differ, OR the processor must reject/flag the
    # mismatch -- a string-literal match on the fix's source code is NOT
    # an acceptable replacement for this assertion; see NZ-SEC-002 for the
    # binding mechanism once implemented.
    #
    # TODO before un-skipping the strict xfail: confirm the parameter/config
    # surface NiriZanSpanProcessor exposes for producer identity once
    # NZ-SEC-002 lands (e.g. trusted_service_names allowlist keyed on some
    # non-spoofable connection-level identity), then replace this body with
    # a real two-producer ingest + assertion on the stored application_name.
    pytest.fail(
        "NZ-SEC-002 not yet implemented: no producer-identity binding exists "
        "to test against. Replace this body once the binding mechanism is "
        "decided (see comment above)."
    )


@pytest.mark.xfail(strict=True, reason="tracked: NZ-SEC-003")
@pytest.mark.asyncio
async def test_trace_upsert_rejects_application_name_takeover(tmp_path):
    # Finding NZ-SEC-003: same trace_id can currently replace application_name
    # and prune the original owner's spans on upsert.
    #
    # Accept EITHER acceptable fix shape, not just one: the repository may
    # either (a) silently no-op the conflicting write (original owner/spans
    # untouched), or (b) explicitly reject it (raise ValueError, matching the
    # existing span-id-collision contract in this same file). Only assert
    # that owner-a's data survives; do not require one specific mechanism,
    # or a correct rejection-based fix will falsely remain XFAIL forever.
    repo = SQLiteTraceRepository(str(tmp_path / "traces.db"))
    trace_id = uuid4()
    first, second = uuid4(), uuid4()
    await repo.save(_trace(trace_id, first, "owner-a"))

    try:
        await repo.save(_trace(trace_id, second, "owner-b"))
    except ValueError:
        pass  # explicit rejection is an acceptable fix shape

    stored = await repo.get(trace_id)
    assert stored is not None
    assert stored.application_name == "owner-a"
    assert {s.span_id for s in stored.spans} == {first}
    repo.close()
