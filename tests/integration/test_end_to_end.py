from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from uuid import UUID

import pytest

from nirizan.instrumentation.spans import SpanKind, Trace
from nirizan.instrumentation.tracer import Tracer
from nirizan.orchestrator.collector import CollectorExporter, TraceCollector
from nirizan.orchestrator.dispatcher import MetricDispatcher
from nirizan.orchestrator.scheduler import RunScheduler
from nirizan.metrics.rag_triad import RAGTriadMetric
from nirizan.storage.trace_repository import SQLiteTraceRepository
from nirizan.storage.run_repository import InMemoryRunRepository


# ---------------------------------------------------------------------------
# Fake scorer: deterministic, zero-dependency, satisfies the Scorer protocol
# ---------------------------------------------------------------------------


class FakeScorer:
    """Deterministic scorer for integration tests. Returns a fixed score
    so assertions are stable without ML backend variability."""

    def __init__(self, fixed_score: float = 0.42) -> None:
        self.fixed_score = fixed_score

    def __call__(self, text_a: str, text_b: str) -> float:
        return self.fixed_score


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_scorer() -> FakeScorer:
    return FakeScorer(fixed_score=0.42)


@pytest.fixture
def db_path() -> str:
    """Yield a temporary SQLite file path; clean up after the test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
async def trace_repo(db_path: str) -> SQLiteTraceRepository:
    repo = SQLiteTraceRepository(db_path=db_path)
    yield repo
    repo.close()


@pytest.fixture
async def trace_collector(trace_repo: SQLiteTraceRepository) -> TraceCollector:
    collector = TraceCollector(repository=trace_repo)
    await collector.start()
    yield collector
    await collector.stop()


@pytest.fixture
def run_repo() -> InMemoryRunRepository:
    return InMemoryRunRepository()


@pytest.fixture
def metric_dispatcher(fake_scorer: FakeScorer) -> MetricDispatcher:
    dispatcher = MetricDispatcher()
    rag_metric = RAGTriadMetric(scorer=fake_scorer)
    dispatcher.register(rag_metric, applies_to={"rag_pipeline"})
    return dispatcher


@pytest.fixture
def run_scheduler(
    trace_repo: SQLiteTraceRepository,
    metric_dispatcher: MetricDispatcher,
    run_repo: InMemoryRunRepository,
) -> RunScheduler:
    return RunScheduler(
        trace_source=trace_repo,
        dispatcher=metric_dispatcher,
        run_repository=run_repo,
    )


# ---------------------------------------------------------------------------
# Integration test: Phase 1 + Phase 2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_to_end_rag_pipeline_evaluation(
    trace_collector: TraceCollector,
    trace_repo: SQLiteTraceRepository,
    run_scheduler: RunScheduler,
    run_repo: InMemoryRunRepository,
    fake_scorer: FakeScorer,
) -> None:
    """
    Full pipeline: instrument a RAG call, persist the trace, evaluate it,
    and assert every boundary preserves data integrity.
    """
    app_name = "test-rag-app"
    query = "What is the capital of France?"
    context = "Paris is the capital and most populous city of France."
    answer = "The capital of France is Paris."

    # ------------------------------------------------------------------
    # 1. Instrumentation: simulate a RAG pipeline with three spans
    # ------------------------------------------------------------------
    exporter = CollectorExporter(collector=trace_collector)
    tracer = Tracer(application_name=app_name, exporter=exporter)

    async with tracer.start_span(
        name="plan",
        kind=SpanKind.PLANNING,
        input_payload=query,
    ) as plan_handle:
        # Planning produces the query (no output payload needed for this test)
        plan_handle.output_payload = query

        async with tracer.start_span(
            name="retrieve",
            kind=SpanKind.RETRIEVAL,
            input_payload=query,
        ) as retrieve_handle:
            retrieve_handle.output_payload = context

            async with tracer.start_span(
                name="generate",
                kind=SpanKind.GENERATION,
                input_payload=query,
            ) as generate_handle:
                generate_handle.output_payload = answer

    # The root span closure triggers exporter.export(trace) automatically.
    # Give the collector worker a moment to flush the queue.
    await trace_collector.queue.join()

    # ------------------------------------------------------------------
    # 2. Storage: verify the trace round-tripped through SQLite
    # ------------------------------------------------------------------
    persisted_traces = await trace_repo.list_by_application(app_name)
    assert len(persisted_traces) == 1, "Exactly one trace should be persisted"

    trace = persisted_traces[0]
    assert trace.application_name == app_name
    assert len(trace.spans) == 3

    # Span ordering is preserved (by started_at)
    kinds = [s.kind for s in trace.spans]
    assert kinds == [SpanKind.PLANNING, SpanKind.RETRIEVAL, SpanKind.GENERATION]

    # Payloads survived round-trip
    planning_span = trace.spans_of_kind(SpanKind.PLANNING)[0]
    retrieval_span = trace.spans_of_kind(SpanKind.RETRIEVAL)[0]
    generation_span = trace.spans_of_kind(SpanKind.GENERATION)[0]

    assert planning_span.input_payload == query
    assert planning_span.output_payload == query
    assert retrieval_span.input_payload == query
    assert retrieval_span.output_payload == context
    assert generation_span.input_payload == query
    assert generation_span.output_payload == answer

    # Parent-child hierarchy is preserved
    assert retrieval_span.parent_span_id == planning_span.span_id
    assert generation_span.parent_span_id == retrieval_span.span_id
    assert planning_span.parent_span_id is None

    # Trace ID consistency: all spans share the trace ID
    assert all(s.trace_id == trace.trace_id for s in trace.spans)

    # ------------------------------------------------------------------
    # 3. Orchestrator + Metrics: evaluate the persisted trace
    # ------------------------------------------------------------------
    runs = await run_scheduler.run_on_demand(
        application_name=app_name,
        system_type="rag_pipeline",
    )

    assert len(runs) == 1, "Exactly one Run should be produced"
    run = runs[0]

    # Run links back to the correct trace
    assert run.trace_id == trace.trace_id
    assert isinstance(run.run_id, UUID)
    assert run.created_at <= datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # 4. Metric results: all three RAG triad dimensions scored
    # ------------------------------------------------------------------
    metric_results = run.metric_results
    assert len(metric_results) == 3

    metric_names = {r.metric_name for r in metric_results}
    assert metric_names == {"context_relevance", "groundedness", "answer_relevance"}

    for result in metric_results:
        # Scores are normalized [0.0, 1.0]
        assert 0.0 <= result.score <= 1.0
        # Our fake scorer always returns 0.42
        assert result.score == pytest.approx(0.42)
        # Confidence is optional at Phase 2; here it should be None
        assert result.confidence is None
        # Each result carries the trace_id for audit linkage
        assert result.trace_id == trace.trace_id
        # computed_at is populated
        assert result.computed_at <= datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # 5. Run persistence: verify the Run round-tripped through repository
    # ------------------------------------------------------------------
    fetched_run = await run_repo.get_run(run.run_id)
    assert fetched_run is not None
    assert fetched_run.trace_id == trace.trace_id
    assert len(fetched_run.metric_results) == 3

    # ------------------------------------------------------------------
    # 6. Immutability: the trace was not mutated by metric evaluation
    # ------------------------------------------------------------------
    re_fetched_trace = await trace_repo.get(trace.trace_id)
    assert re_fetched_trace is not None
    assert len(re_fetched_trace.spans) == 3
    assert re_fetched_trace.spans[0].input_payload == query
    assert re_fetched_trace.spans[2].output_payload == answer


# ---------------------------------------------------------------------------
# Integration test: Phase 3 — multi-turn session tracing + collector tagging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_to_end_agent_session_and_versioning_tagging(
    trace_repo: SQLiteTraceRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Multi-turn agent session tracing (Tracer.session()) and collector-side
    commit/snapshot tagging, exercised together through the same real
    pipeline as the Phase 1/2 test above.

    Builds its own TraceCollector locally (rather than using the shared
    trace_collector fixture) because TraceCollector resolves code_commit
    and data_snapshot_id once, at __init__, not per-trace. The shared
    fixture would construct its collector before this test's
    monkeypatch.setenv() calls run, so the mocked env vars would never be
    picked up.
    """
    monkeypatch.setenv("GIT_COMMIT_SHA", "deadbeefcafebabe1234567890abcdef12345678")
    monkeypatch.setenv("NIRIZAN_DATA_SNAPSHOT_ID", "test-snapshot-v1")

    app_name = "test-agent-app"
    collector = TraceCollector(repository=trace_repo)
    await collector.start()

    exporter = CollectorExporter(collector=collector)
    tracer = Tracer(application_name=app_name, exporter=exporter)

    turns = ["search docs", "call calculator", "summarize"]

    async with tracer.session() as session_id:
        for turn in turns:
            async with tracer.start_span(
                name="agent_turn",
                kind=SpanKind.TOOL_USE,
                input_payload=turn,
            ) as handle:
                handle.output_payload = f"result of: {turn}"

    await collector.queue.join()
    await collector.stop()

    persisted_traces = await trace_repo.list_by_application(app_name)
    assert len(persisted_traces) == len(turns), "One trace per turn"

    for trace in persisted_traces:
        # All turns belong to the same session
        assert trace.session_id == session_id

        # Collector tagged every trace with the resolved commit + snapshot,
        # not just the root trace of the session
        assert trace.code_commit == "deadbeefcafebabe1234567890abcdef12345678"
        assert trace.data_snapshot_id == "test-snapshot-v1"


@pytest.mark.asyncio
async def test_end_to_end_trace_outside_session_has_no_session_id(
    trace_collector: TraceCollector,
    trace_repo: SQLiteTraceRepository,
) -> None:
    """
    Backward compatibility: a trace captured outside any Tracer.session()
    block must have session_id=None, not a leaked value from a prior
    session elsewhere in the process (contextvars must reset cleanly on
    exit from the session() block).
    """
    app_name = "test-no-session-app"
    exporter = CollectorExporter(collector=trace_collector)
    tracer = Tracer(application_name=app_name, exporter=exporter)

    async with tracer.start_span(
        name="standalone_call",
        kind=SpanKind.PLANNING,
        input_payload="no session here",
    ) as handle:
        handle.output_payload = "done"

    await trace_collector.queue.join()

    persisted_traces = await trace_repo.list_by_application(app_name)
    assert len(persisted_traces) == 1
    assert persisted_traces[0].session_id is None
