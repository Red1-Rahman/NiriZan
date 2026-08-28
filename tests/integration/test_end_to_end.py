# tests/integration/test_end_to_end.py
from __future__ import annotations

import io
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
import pytest

from nirizan.gate.ci import (
    format_gate_summary,
    gate_exit_code,
    write_github_summary,
)
from nirizan.gate.verdict import GateVerdict, evaluate_gate
from nirizan.instrumentation.spans import SpanKind, Trace
from nirizan.instrumentation.tracer import Tracer
from nirizan.metrics.rag_triad import RAGTriadMetric
from nirizan.orchestrator.collector import CollectorExporter, TraceCollector
from nirizan.orchestrator.dispatcher import MetricDispatcher
from nirizan.orchestrator.scheduler import RunScheduler
from nirizan.regression.comparator import (
    BaselineComparator,
    RegressionSeverity,
)
from nirizan.reporting.dashboard import assemble_dashboard_snapshot
from nirizan.reporting.judge_reliability import (
    JudgeReliabilityStatus,
    compute_judge_reliability,
)
from nirizan.storage.baselines import SQLiteBaselineRepository
from nirizan.storage.experiment_store import SQLiteExperimentStore
from nirizan.storage.models import Baseline, Run
from nirizan.storage.run_repository import InMemoryRunRepository
from nirizan.storage.trace_repository import SQLiteTraceRepository
from nirizan.trust.attribution import AttributionEngine, DriftAttribution


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
# Integration test: Phase 1 + Phase 2 (With log stream verification)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_to_end_rag_pipeline_evaluation(
    trace_collector: TraceCollector,
    trace_repo: SQLiteTraceRepository,
    run_scheduler: RunScheduler,
    run_repo: InMemoryRunRepository,
    fake_scorer: FakeScorer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Full pipeline: instrument a RAG call, persist the trace, evaluate it,
    and assert every boundary preserves data integrity while writing logs.
    """
    app_name = "test-rag-app"
    query = "What is the capital of France?"
    context = "Paris is the capital and most populous city of France."
    answer = "The capital of France is Paris."

    with caplog.at_level(logging.INFO):
        # 1. Instrumentation: simulate a RAG pipeline with three spans
        exporter = CollectorExporter(collector=trace_collector)
        tracer = Tracer(application_name=app_name, exporter=exporter)

        async with tracer.start_span(
            name="plan",
            kind=SpanKind.PLANNING,
            input_payload=query,
        ) as plan_handle:
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

        await trace_collector.queue.join()

        # 2. Storage: verify the trace round-tripped through SQLite
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

        assert all(s.trace_id == trace.trace_id for s in trace.spans)

        # 3. Orchestrator + Metrics: evaluate the persisted trace
        runs = await run_scheduler.run_on_demand(
            application_name=app_name,
            system_type="rag_pipeline",
        )

    assert len(runs) == 1, "Exactly one Run should be produced"
    run = runs[0]

    assert run.trace_id == trace.trace_id
    assert isinstance(run.run_id, UUID)
    assert run.created_at <= datetime.now(timezone.utc)

    # 4. Metric results: all three RAG triad dimensions scored
    metric_results = run.metric_results
    assert len(metric_results) == 3

    metric_names = {r.metric_name for r in metric_results}
    assert metric_names == {"context_relevance", "groundedness", "answer_relevance"}

    for result in metric_results:
        assert 0.0 <= result.score <= 1.0
        assert result.score == pytest.approx(0.42)
        assert result.confidence is None
        assert result.trace_id == trace.trace_id
        assert result.computed_at <= datetime.now(timezone.utc)

    # 5. Run persistence: verify the Run round-tripped through repository
    fetched_run = await run_repo.get_run(run.run_id)
    assert fetched_run is not None
    assert fetched_run.trace_id == trace.trace_id
    assert len(fetched_run.metric_results) == 3

    # 6. Verify logging streams were captured during evaluation
    assert f"Evaluating RAGTriadMetric for trace_id={trace.trace_id}" in caplog.text
    assert f"completed for trace_id={trace.trace_id}: computed 3 metrics" in caplog.text


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
    commit/snapshot tagging.
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
        assert trace.session_id == session_id
        assert trace.code_commit == "deadbeefcafebabe1234567890abcdef12345678"
        assert trace.data_snapshot_id == "test-snapshot-v1"


@pytest.mark.asyncio
async def test_end_to_end_trace_outside_session_has_no_session_id(
    trace_collector: TraceCollector,
    trace_repo: SQLiteTraceRepository,
) -> None:
    """
    Backward compatibility: a trace captured outside any Tracer.session()
    block must have session_id=None.
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


# ---------------------------------------------------------------------------
# Integration test: Phase 3 + Phase 4 Statistical Gating & CI Workflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_to_end_phase4_statistical_gating_and_ci_summary(
    trace_repo: SQLiteTraceRepository,
    metric_dispatcher: MetricDispatcher,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Full Phase 3 & 4 E2E Pipeline:
    1. Instrument multi-turn session traces under Baseline (Commit A) and Candidate (Commit B).
    2. Collect and verify version tags on persisted traces.
    3. Record baseline and candidate runs in SQLiteExperimentStore.
    4. Save a Baseline referencing Commit A's run in SQLiteBaselineRepository.
    5. Perform BaselineComparator analysis with Mann-Whitney U test & Holm-Bonferroni correction.
    6. Evaluate gate verdict with bootstrap confidence interval.
    7. Generate GitHub CI markdown summary & assert process exit code.
    8. Validate log stream outputs across all stages.
    """
    app_name = "test-phase4-rag-agent"
    sys_type = "rag_pipeline"

    exp_db = str(tmp_path / "experiments.db")
    base_db = str(tmp_path / "baselines.db")

    experiment_store = SQLiteExperimentStore(db_path=exp_db)
    baseline_repo = SQLiteBaselineRepository(db_path=base_db)

    # ------------------------------------------------------------------
    # 1. Baseline (Commit A) execution & trace capture
    # ------------------------------------------------------------------
    monkeypatch.setenv("GIT_COMMIT_SHA", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    monkeypatch.setenv("NIRIZAN_DATA_SNAPSHOT_ID", "snapshot-v1.0")

    collector_a = TraceCollector(repository=trace_repo)
    await collector_a.start()
    exporter_a = CollectorExporter(collector=collector_a)
    tracer_a = Tracer(application_name=app_name, exporter=exporter_a)

    async with tracer_a.session() as session_a_id:
        async with tracer_a.start_span(
            name="plan", kind=SpanKind.PLANNING, input_payload="Query A"
        ) as plan:
            plan.output_payload = "Query A"
            async with tracer_a.start_span(
                name="retrieve", kind=SpanKind.RETRIEVAL, input_payload="Query A"
            ) as ret:
                ret.output_payload = "Context A"
                async with tracer_a.start_span(
                    name="generate", kind=SpanKind.GENERATION, input_payload="Query A"
                ) as gen:
                    gen.output_payload = "Answer A"

    await collector_a.queue.join()
    await collector_a.stop()

    traces_a = await trace_repo.list_by_application(app_name)
    assert len(traces_a) == 1
    trace_a = traces_a[0]
    assert trace_a.code_commit == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert trace_a.session_id == session_a_id

    metric_results_a = await metric_dispatcher.dispatch(trace_a, sys_type)
    run_a = Run(
        run_id=UUID("11111111-1111-1111-1111-111111111111"),
        trace_id=trace_a.trace_id,
        code_commit=trace_a.code_commit,
        data_snapshot_id=trace_a.data_snapshot_id or "snapshot-v1.0",
        metric_results=metric_results_a,
        created_at=datetime.now(timezone.utc),
    )
    await experiment_store.record_run(run_a)

    baseline_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    baseline = Baseline(
        baseline_id=baseline_id,
        system_type=sys_type,
        run_ids=[run_a.run_id],
        established_at=datetime.now(timezone.utc),
        label="v1.0-gold-baseline",
    )
    await baseline_repo.save_baseline(baseline)

    # ------------------------------------------------------------------
    # 2. Candidate (Commit B - Degraded) execution & trace capture
    # ------------------------------------------------------------------
    monkeypatch.setenv("GIT_COMMIT_SHA", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    monkeypatch.setenv("NIRIZAN_DATA_SNAPSHOT_ID", "snapshot-v1.0")

    collector_b = TraceCollector(repository=trace_repo)
    await collector_b.start()
    exporter_b = CollectorExporter(collector=collector_b)
    tracer_b = Tracer(application_name=app_name, exporter=exporter_b)

    async with tracer_b.session():
        async with tracer_b.start_span(
            name="plan", kind=SpanKind.PLANNING, input_payload="Query B"
        ) as plan:
            plan.output_payload = "Query B"
            async with tracer_b.start_span(
                name="retrieve", kind=SpanKind.RETRIEVAL, input_payload="Query B"
            ) as ret:
                ret.output_payload = "Context B"
                async with tracer_b.start_span(
                    name="generate", kind=SpanKind.GENERATION, input_payload="Query B"
                ) as gen:
                    gen.output_payload = "Answer B"

    await collector_b.queue.join()
    await collector_b.stop()

    all_traces = await trace_repo.list_by_application(app_name)
    trace_b = [
        t for t in all_traces if t.code_commit == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    ][0]

    metric_results_b = await metric_dispatcher.dispatch(trace_b, sys_type)
    run_b = Run(
        run_id=UUID("22222222-2222-2222-2222-222222222222"),
        trace_id=trace_b.trace_id,
        code_commit=trace_b.code_commit,
        data_snapshot_id=trace_b.data_snapshot_id or "snapshot-v1.0",
        metric_results=metric_results_b,
        created_at=datetime.now(timezone.utc),
    )
    await experiment_store.record_run(run_b)

    # ------------------------------------------------------------------
    # 3. Statistical Gating & Baseline Comparison (Phase 4)
    # ------------------------------------------------------------------
    rng = np.random.default_rng(42)

    baseline_scores = {
        "context_relevance": rng.normal(loc=0.90, scale=0.02, size=30).clip(0.0, 1.0),
        "groundedness": rng.normal(loc=0.88, scale=0.02, size=30).clip(0.0, 1.0),
        "answer_relevance": rng.normal(loc=0.92, scale=0.02, size=30).clip(0.0, 1.0),
    }

    candidate_pass_scores = {
        "context_relevance": rng.normal(loc=0.91, scale=0.02, size=30).clip(0.0, 1.0),
        "groundedness": rng.normal(loc=0.89, scale=0.02, size=30).clip(0.0, 1.0),
        "answer_relevance": rng.normal(loc=0.93, scale=0.02, size=30).clip(0.0, 1.0),
    }

    candidate_block_scores = {
        "context_relevance": rng.normal(loc=0.30, scale=0.05, size=30).clip(0.0, 1.0),
        "groundedness": rng.normal(loc=0.35, scale=0.05, size=30).clip(0.0, 1.0),
        "answer_relevance": rng.normal(loc=0.40, scale=0.05, size=30).clip(0.0, 1.0),
    }

    comparator = BaselineComparator(
        alpha=0.05,
        warning_effect=-0.20,
        blocking_effect=-0.50,
    )

    with caplog.at_level(logging.INFO):
        # --- Evaluate Candidate PASS ---
        pass_verdicts = comparator.compare(
            candidate_scores=candidate_pass_scores,
            baseline_scores=baseline_scores,
            baseline_id=baseline_id,
            run_id=run_a.run_id,
        )

        pass_scores_by_metric = {
            m: (candidate_pass_scores[m], baseline_scores[m]) for m in candidate_pass_scores
        }
        pass_gate_verdict = evaluate_gate(
            verdicts=pass_verdicts,
            scores_by_metric=pass_scores_by_metric,
        )

        assert pass_gate_verdict.passed is True
        assert gate_exit_code(pass_gate_verdict) == 0

        # --- Evaluate Candidate BLOCK ---
        block_verdicts = comparator.compare(
            candidate_scores=candidate_block_scores,
            baseline_scores=baseline_scores,
            baseline_id=baseline_id,
            run_id=run_b.run_id,
        )

        block_scores_by_metric = {
            m: (candidate_block_scores[m], baseline_scores[m]) for m in candidate_block_scores
        }
        block_gate_verdict = evaluate_gate(
            verdicts=block_verdicts,
            scores_by_metric=block_scores_by_metric,
        )

        assert block_gate_verdict.passed is False
        assert any(v.severity == RegressionSeverity.BLOCKING for v in block_verdicts)
        assert gate_exit_code(block_gate_verdict) == 1

        # ------------------------------------------------------------------
        # 4. CI Summary Generation
        # ------------------------------------------------------------------
        summary_buf = io.StringIO()
        write_github_summary(block_gate_verdict, output=summary_buf)
        summary_text = summary_buf.getvalue()

        assert "| Metric | Severity | P-Value | Effect Size |" in summary_text
        assert "**Gate:** BLOCK" in summary_text
        assert "**95% bootstrap CI:**" in summary_text

    # ------------------------------------------------------------------
    # 5. Log Stream Validation
    # ------------------------------------------------------------------
    assert "Comparing 3 metric(s) between candidate run_id=" in caplog.text
    assert "Gate evaluation result: PASSED" in caplog.text
    assert "Gate evaluation result: BLOCKED" in caplog.text
    assert "Writing GitHub CI summary" in caplog.text
    assert "CI Gate BLOCKED" in caplog.text

    experiment_store.close()
    baseline_repo.close()


# ---------------------------------------------------------------------------
# Integration test: Phase 5 — Trust, Attribution & Dashboard Reporting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_to_end_trust_attribution_and_dashboard_reporting(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Full Phase 5 E2E Pipeline:
    1. Run AttributionEngine across standard, joint drift, and inconclusive score scenarios.
    2. Aggregate multi-outcome verdict windows with compute_judge_reliability().
    3. Verify judge reliability status flags UNSTABLE when judge drift + joint drift rate exceeds threshold.
    4. Assemble full DashboardSnapshots and assert system health score penalties for JOINT_DRIFT and INCONCLUSIVE.
    5. Verify log stream output for dashboard assembly.
    """
    engine = AttributionEngine(significance_threshold=0.05)
    anchor_id = "anchor-set-v1.0"

    ref_scores = [0.90, 0.90, 0.90, 0.90]
    rescored_stable = [0.90, 0.90, 0.90, 0.90]
    rescored_drift = [0.70, 0.70, 0.70, 0.70]

    baseline_scores = [0.90, 0.90, 0.90, 0.90]
    candidate_stable = [0.90, 0.90, 0.90, 0.90]
    candidate_drift = [0.65, 0.65, 0.65, 0.65]

    # 1. Evaluate attribution across 5 outcomes
    v_none = engine.analyze(
        anchor_id, ref_scores, rescored_stable, baseline_scores, candidate_stable
    )
    v_sys = engine.analyze(anchor_id, ref_scores, rescored_stable, baseline_scores, candidate_drift)
    v_judge = engine.analyze(
        anchor_id, ref_scores, rescored_drift, baseline_scores, candidate_stable
    )
    v_joint = engine.analyze(
        anchor_id, ref_scores, rescored_drift, baseline_scores, candidate_drift
    )
    v_inc = engine.analyze(anchor_id, [], rescored_stable, baseline_scores, candidate_stable)

    assert v_none.attribution == DriftAttribution.NONE
    assert v_sys.attribution == DriftAttribution.SYSTEM_DRIFT
    assert v_judge.attribution == DriftAttribution.JUDGE_DRIFT
    assert v_joint.attribution == DriftAttribution.JOINT_DRIFT
    assert v_inc.attribution == DriftAttribution.INCONCLUSIVE

    verdicts = [v_none, v_sys, v_judge, v_joint, v_inc]

    # 2. Aggregated Judge Reliability Metrics
    metrics = compute_judge_reliability(verdicts, drift_rate_warning=0.10)
    assert metrics.verdict_count == 5
    assert metrics.judge_drift_rate == pytest.approx(2 / 5)
    assert metrics.system_drift_rate == pytest.approx(2 / 5)
    assert metrics.joint_drift_rate == pytest.approx(1 / 5)
    assert metrics.inconclusive_rate == pytest.approx(1 / 5)
    assert metrics.none_rate == pytest.approx(1 / 5)
    assert metrics.status == JudgeReliabilityStatus.UNSTABLE

    # 3. Dashboard Snapshot Assembly with JOINT_DRIFT & INCONCLUSIVE
    with caplog.at_level(logging.INFO):
        snapshot_joint = assemble_dashboard_snapshot(
            system_type="rag_pipeline",
            quality_score=0.90,
            confidence=0.95,
            attribution_verdicts=[v_joint],
        )

        expected_joint_health = round(0.90 * 0.95 * 100.0 * 0.70, 1)
        assert snapshot_joint.health_score == expected_joint_health
        assert snapshot_joint.latest_attribution is not None
        assert snapshot_joint.latest_attribution.attribution == DriftAttribution.JOINT_DRIFT

        snapshot_inc = assemble_dashboard_snapshot(
            system_type="rag_pipeline",
            quality_score=0.90,
            confidence=0.95,
            attribution_verdicts=[v_inc],
        )

        expected_inc_health = round(0.90 * 0.95 * 100.0 * 0.85, 1)
        assert snapshot_inc.health_score == expected_inc_health
        assert snapshot_inc.latest_attribution is not None
        assert snapshot_inc.latest_attribution.attribution == DriftAttribution.INCONCLUSIVE

    assert "Assembled dashboard snapshot for system_type=rag_pipeline" in caplog.text
