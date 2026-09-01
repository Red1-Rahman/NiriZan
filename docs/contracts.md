# Contracts

This document is the single source of truth for the shapes NiriZan's components agree on: pydantic models, plugin interfaces, and return-value contracts between components. `docs/architecture.md` says what each component does and how they connect. This document says exactly what each component promises the components around it, in enough detail that two people (or one person and their future self) could implement either side of a boundary independently and have them fit together.

Every model here is a `pydantic.BaseModel` (pydantic v2). Strict typing means every field has a real type, not `Any`, and every model validates at construction, not just at the edges. If a field's type is genuinely unknown at design time, that is a sign the contract isn't ready to be written down yet, not a reason to reach for `Any`.

Contracts are added here in the phase they're introduced and never edited to change meaning in a later phase, only extended. If a later phase needs to change what an earlier contract means, that is a breaking change and must be called out explicitly as one, with a version bump, not folded in silently.

---

## Phase 1 Contracts: Instrumentation & Trace Storage

### `Span` (`instrumentation/spans.py`)

The atomic unit of instrumentation. One span per planning, retrieval, tool-use, or generation step.

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SpanKind(str, Enum):
    PLANNING = "planning"
    RETRIEVAL = "retrieval"
    TOOL_USE = "tool_use"
    GENERATION = "generation"


class Span(BaseModel):
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
```

**Contract guarantees:**

* `span_id` is unique per span, `trace_id` groups all spans from a single application invocation.
* `Span` is frozen (immutable) once constructed. Nothing downstream mutates a span; corrections happen by emitting a new span, not editing history.
* `attributes` values are restricted to primitive types on purpose. If a metric needs to attach a structured object to a span, that belongs in a separate linked record, not jammed into `attributes` as a serialized blob.

### `Trace` (`instrumentation/spans.py`)

A trace is the ordered collection of spans belonging to one application invocation.

```python
class Trace(BaseModel):
    model_config = ConfigDict(strict=True)

    trace_id: UUID
    application_name: str = Field(min_length=1)
    spans: list[Span] = Field(default_factory=list)
    created_at: datetime
    code_commit: str | None = None  # Phase 3: stamped by collector.py at ingest
    data_snapshot_id: str | None = None  # Phase 3: stamped by collector.py at ingest
    session_id: UUID | None = None  # Phase 3: set when captured inside Tracer.session(...)

    def spans_of_kind(self, kind: SpanKind) -> list[Span]:
        return [s for s in self.spans if s.kind == kind]
```

**Contract guarantees:**

* Every `Span` in `spans` must share the same `trace_id` as the `Trace` itself. Enforce this with a `model_validator`, do not rely on callers to get it right.
* `Trace` is the only object the Instrumentation Layer hands to the Orchestrator. Nothing calls `Span` in isolation across that boundary.
* `code_commit`, `data_snapshot_id`, and `session_id` are additive Phase 3 fields, all optional with a `None` default, per this document's Versioning Rule. `None` means the value genuinely wasn't available at ingest (e.g. traces captured outside a git checkout, or outside a `Tracer.session(...)` block); callers must not treat `None` as a placeholder to be filled in later, only as "not applicable to this trace."

### `TraceExporter` protocol (`instrumentation/exporters.py`)

```python
from typing import Protocol


class TraceExporter(Protocol):
    async def export(self, trace: Trace) -> None:
        """Send a completed trace to the orchestrator's Trace Collector.

        Must not raise on transient failure; implementations are
        responsible for their own retry/backoff. Must not block the
        instrumented application's request/response path (Design Principle
        2 in docs/architecture.md): callers await this from a background task,
        never inline in the request handler.
        """
        ...
```

**Contract guarantees:**

* This is the seam between Instrumentation and Orchestrator. Anything on the application side depends only on this `Protocol`, never on a concrete Trace Collector implementation. That is what keeps instrumentation swappable per framework without touching the orchestrator.

### `TraceRepository` interface (`storage/trace_repository.py`)

```python
class TraceRepository(Protocol):
    async def save(self, trace: Trace) -> None: ...
    async def get(self, trace_id: UUID) -> Trace | None: ...
    async def list_by_application(self, application_name: str, limit: int = 100) -> list[Trace]: ...
```

**Contract guarantees:**

* `get` returns `None` for a missing trace, it does not raise. Callers that need "trace must exist" semantics wrap this themselves; the repository stays a dumb, honest store.
* No method here accepts or returns anything from `metrics/`, `regression/`, or `reporting/`. This is Phase 1's boundary and it stays that narrow.

---

## Phase 2 Contracts: RAG Triad Metrics

### `Metric` plugin interface (`metrics/base.py`)

This is the interface every metric module implements, from Phase 2's `RAGTriadMetric` through Phase 5's `BehavioralAnchorMetric`. Nothing about this interface changes after Phase 2; new metrics conform to it, it does not bend to them.

```python
class MetricResult(BaseModel):
    model_config = ConfigDict(strict=True)

    metric_name: str
    trace_id: UUID
    score: float = Field(ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    details: dict[str, str | int | float | bool] = Field(default_factory=dict)
    computed_at: datetime


class Metric(Protocol):
    name: str

    async def evaluate(self, trace: Trace) -> list[MetricResult]:
        """Compute one or more scores for a trace.

        A single metric module may return multiple MetricResults (e.g. the
        RAG Triad returns three: context relevance, groundedness, answer
        relevance), each with its own metric_name.

        Must not mutate the trace. Must not perform its own persistence;
        the Metric Dispatcher is responsible for writing results to
        storage, never the metric itself.
        """
        ...
```

**Contract guarantees:**

* `score` is always normalized to `[0.0, 1.0]`. A metric that produces a different native range (a raw log-likelihood, a distance, a percentage) converts before returning `MetricResult`. This is what lets the System Health Score in Phase 5 aggregate scores from wildly different metric implementations without special-casing each one.
* `confidence` is optional in Phase 2 (the RAG Triad may not produce one) and becomes load-bearing in Phase 4 once Statistical Gating exists. The field is defined now so Phase 4 doesn't need a breaking migration to add it.
* A `Metric` never talks to `regression/`, `gate/`, or `reporting/` directly. It returns `MetricResult` objects and nothing else; everything downstream is the Metric Dispatcher's job.

### `MetricDispatcher` contract (`orchestrator/dispatcher.py`)

```python
class MetricDispatcher(Protocol):
    def register(self, metric: Metric, applies_to: set[str]) -> None:
        """Register a metric for one or more application/system types
        (e.g. {"rag_pipeline"}, {"agent"}). Registration is explicit;
        there is no implicit auto-discovery of metrics on import, since
        implicit registration is exactly the kind of thing that produces
        circular imports between metrics/ and orchestrator/.
        """
        ...

    async def dispatch(self, trace: Trace, system_type: str) -> list[MetricResult]: ...
```

**Contract guarantees:**

* `register` is called explicitly at application startup (in the CLI entry point or a setup module), never via import-time side effects in `metrics/*.py`. This is the specific mechanism that keeps `metrics/` from depending on `orchestrator/` and `orchestrator/` from needing to import every metric module by name. See the Import Direction rule below.

### `RunRepository` interface (`storage/run_repository.py`)

A minimal, additive interface for persisting a `Run` (a trace's `MetricResult`s, per Phase 2's `Run` model in `storage/models.py`) ahead of Phase 3's fuller `ExperimentStore`. This exists because the Phase 2 architecture diagram already draws metric results flowing into storage (`METRICS --> S1`); `RunRepository` is the honest, narrow version of that edge for this phase, not a workaround.

```python
class RunRepository(Protocol):
    async def save_run(self, run: Run) -> None: ...
    async def get_run(self, run_id: UUID) -> Run | None: ...
```

**Contract guarantees:**

* `get_run` returns `None` for a missing run, it does not raise. Same "dumb, honest store" guarantee as `TraceRepository.get` in Phase 1.
* `RunRepository` is deliberately narrower than Phase 3's `ExperimentStore`: no `diff`, no baseline comparison, no versioning-aware queries. Those arrive in Phase 3 as an extension, not a redefinition, of what a `Run` can do once persisted. `ExperimentStore` in Phase 3 is expected to satisfy `RunRepository`'s shape as a subset of its own interface, so nothing built against `RunRepository` in Phase 2 needs to change when Phase 3 lands.
* Lives in `storage/`, same as `TraceRepository`; `RunRepository` does not replace or extend `TraceRepository`, they are separate interfaces persisting separate things (`Trace` vs. `Run`).

---

## Phase 3 Contracts: Experiment Tracking & Baselines

### `Run` (`storage/models.py`)

```python
class Run(BaseModel):
    model_config = ConfigDict(strict=True)

    run_id: UUID
    trace_id: UUID
    code_commit: str = Field(min_length=7, max_length=40)  # git SHA, short or full
    data_snapshot_id: str = Field(min_length=1)
    metric_results: list[MetricResult] = Field(default_factory=list)
    created_at: datetime
```

**Contract guarantees:**

* `code_commit` and `data_snapshot_id` are both required, not optional. A `Run` with no versioning information is not a valid `Run`; this is the field pairing that makes two runs comparable at all. Do not make these optional later to "make testing easier." Use a fixed test fixture value instead.

### `Baseline` (`storage/models.py`)

```python
class Baseline(BaseModel):
    model_config = ConfigDict(strict=True)

    baseline_id: UUID
    system_type: str
    run_ids: list[UUID] = Field(min_length=1)
    established_at: datetime
    label: str = Field(min_length=1)  # e.g. "pre-v0.3-release", "weekly-2026-08"
```

**Contract guarantees:**

* A `Baseline` references `Run` objects by ID, it does not embed them. This keeps the Experiment Store as the single owner of `Run` data; `Baseline` is a named pointer, not a copy.

### `BaselineRepository` interface (`storage/baselines.py`)

Validated in `experiments/03_experiment_tracking_baselines.ipynb` before being made official.

```python
class BaselineRepository(Protocol):
    async def save_baseline(self, baseline: Baseline) -> None: ...
    async def get_baseline(self, baseline_id: UUID) -> Baseline | None: ...
    async def list_baselines(self, system_type: str) -> list[Baseline]: ...
```

**Contract guarantees:**

* `get_baseline` returns `None` for a missing baseline, it does not raise. Same "dumb, honest store" guarantee as `TraceRepository.get`, `RunRepository.get_run`, and `SessionRepository.get_session`.
* `list_baselines` is filtered by `system_type`, satisfying the roadmap's "baseline management and *querying*" deliverable; it is the one method here with query semantics beyond single-record lookup.
* `BaselineRepository` does not implement selection logic (i.e. it does not decide which runs *should* become a baseline). It only persists and retrieves `Baseline` objects a caller has already constructed. Any future automatic baseline-selection heuristic belongs in a different component, not here.

### `ExperimentStore` interface (`storage/experiment_store.py`)

```python
class ExperimentStore(Protocol):
    async def record_run(self, run: Run) -> None: ...
    async def get_run(self, run_id: UUID) -> Run | None: ...
    async def diff(self, run_a: UUID, run_b: UUID) -> "RunDiff": ...


class RunDiff(BaseModel):
    model_config = ConfigDict(strict=True)

    run_a: UUID
    run_b: UUID
    metric_deltas: dict[str, float]  # metric_name -> score_b - score_a
```

**Contract guarantees:**

* `diff` computes a difference, full stop. It does not judge whether that difference is a regression. That judgment is `regression/comparator.py`'s job in Phase 4, and Phase 4's `Comparator` takes a `RunDiff` as input rather than recomputing it. This boundary is deliberate: the ledger records, the accountant judges, and they are different files for a reason.

### `Session` (`instrumentation/sessions.py`)

Groups multiple `Trace`s (by `trace_id`) belonging to one multi-turn agent conversation. Lives in `instrumentation/`, sibling to `Span`/`Trace` in the layer they belong to, but defined in its own file rather than `spans.py` since it doesn't share `Span`/`Trace`'s validation coupling — it only references `Trace` objects by ID, the same "named pointer, not embedded copy" pattern this document already uses for `Baseline` referencing `Run`.

```python
class Session(BaseModel):
    model_config = ConfigDict(strict=True)

    session_id: UUID
    application_name: str = Field(min_length=1)
    trace_ids: list[UUID] = Field(default_factory=list)
    started_at: datetime
    ended_at: datetime | None = None
```

**Contract guarantees:**

* Unlike `Span`, `Session` is **not frozen**. A session is open and accumulates `trace_ids` as turns happen; `ended_at` is `None` while the session is ongoing, set once the session is explicitly closed.
* `Session` does not embed `Trace` objects, only their IDs, for the same reason `Baseline` doesn't embed `Run` objects: it keeps the Trace Repository as the single owner of `Trace` data.
* A `Trace`'s optional `session_id` field (see the Phase 1 `Trace` contract) is how a `Trace` is linked back to the `Session` that produced it; `Session.trace_ids` and `Trace.session_id` are expected to agree, but nothing in this contract enforces that bidirectionally at construction time. Callers that need that guarantee enforce it themselves.

### `SessionRepository` interface (`storage/session_repository.py`)

```python
class SessionRepository(Protocol):
    async def save_session(self, session: Session) -> None: ...
    async def get_session(self, session_id: UUID) -> Session | None: ...
```

**Contract guarantees:**

* `get_session` returns `None` for a missing session, it does not raise. Same "dumb, honest store" guarantee as `TraceRepository.get` (Phase 1) and `RunRepository.get_run` (Phase 2).
* Same relationship to any future, fuller session-management interface as `RunRepository` has to `ExperimentStore`: deliberately minimal now, expected to be satisfied as a subset by anything richer added later, not redefined by it.

---

## Phase 4 Contracts: Regression Detection & CI Gate

### `RegressionVerdict` (`regression/comparator.py`)

```python
class RegressionSeverity(str, Enum):
    NONE = "none"
    WARNING = "warning"
    BLOCKING = "blocking"


class RegressionVerdict(BaseModel):
    model_config = ConfigDict(strict=True)

    metric_name: str
    severity: RegressionSeverity
    z_score: float | None = None
    baseline_id: UUID
    run_id: UUID
    explanation: str
```

**Contract guarantees:**

* `severity` is always one of the three enum values; there is no raw boolean pass/fail anywhere in this contract. A `RegressionVerdict` that collapses to true/false before it reaches the Gate has thrown away information the Gate needs.
* `explanation` is required and must be non-empty. A regression verdict with no human-readable reason is not acceptable output; if the comparator can't explain itself, it hasn't finished computing the verdict.

### `GateVerdict` (`gate/verdict.py`)

```python
class GateVerdict(BaseModel):
    model_config = ConfigDict(strict=True)

    passed: bool
    confidence_interval: tuple[float, float]
    regression_verdicts: list[RegressionVerdict] = Field(default_factory=list)
    run_id: UUID
```

**Contract guarantees:**

* `confidence_interval` is required, not optional, even though `passed` alone would satisfy a naive CI integration. A gate that only emits `passed: bool` is a rubber stamp, not a gate. If a CI step only wants the boolean, it reads `.passed`, but the interval is always computed and always present in the contract.

### `Metric` interface extension for judges

`LightweightJudgeMetric` and `LLMJudgeMetric` (in `metrics/lightweight_judge.py` and `metrics/llm_judge.py`) implement the same `Metric` protocol from Phase 2. No new protocol is introduced. The only new field that becomes load-bearing here is `MetricResult.confidence`, populated by Statistical Gating (`metrics/statistical_gating.py`), which wraps a judge's raw output and recalibrates it against the gold set before it becomes a `MetricResult`.

```python
class StatisticalGate(Protocol):
    async def calibrate(
        self, raw_results: list[MetricResult], gold_set_id: str
    ) -> list[MetricResult]:
        """Return a new list of MetricResults with `confidence` populated,
        derived from calibration against the named gold set. Does not
        mutate raw_results in place (MetricResult should be treated as
        frozen in practice, even though frozen=True is not set on it,
        since results may need to carry forward original scores for
        audit purposes).
        """
        ...
```

---

## Phase 5 Contracts: Drift & Judge-Reliability Layer

### `AttributionVerdict` (`trust/attribution.py`)

This is the contract the entire Trust & Attribution Layer exists to produce. Get this one right or the whole phase is decorative.

```python
class DriftAttribution(str, Enum):
    NONE = "none"
    SYSTEM_DRIFT = "system_drift"
    JUDGE_DRIFT = "judge_drift"
    JOINT_DRIFT = (
        "joint_drift"  # Phase 5 (post-launch): both judge and system shifted significantly
    )
    INCONCLUSIVE = (
        "inconclusive"  # Phase 5 (post-launch): an input score distribution was empty or non-finite
    )


class AttributionVerdict(BaseModel):
    model_config = ConfigDict(strict=True)

    attribution: DriftAttribution
    anchor_set_id: str
    system_score_delta: float
    judge_score_delta: float
    evaluated_at: datetime
    explanation: str
```

**Contract guarantees:**

* `attribution` is exactly one of the five enum values, never a probability or a blend. The Attribution Engine is allowed to be uncertain internally, but it must commit to a verdict at this boundary. Anything downstream (Regression Detection, Reporting) treats this as a categorical fact, not a score to threshold again.
* `JOINT_DRIFT` means both the judge-side shift (`judge_score_delta`) and the system-side shift (`system_score_delta`) independently crossed their respective significance conditions in the same evaluation window (see the direction-constraint bullet below for what "crossed" means on the system side). It is a distinct state, not a tiebreak between `SYSTEM_DRIFT` and `JUDGE_DRIFT`: downstream consumers that only branch on those two will silently drop joint-drift verdicts, which is precisely the ambiguous case Reporting most needs surfaced.
* `SYSTEM_DRIFT` and `JOINT_DRIFT` require the system-side shift to be a **drop**, decided by statistical evidence rather than a raw magnitude threshold: `AttributionEngine.analyze` only sets the system-shift condition when the bootstrap confidence interval for `system_score_delta` excludes zero (and, for comparisons with at least five observations per group, a one-sided Mann-Whitney U test also rejects at the configured `alpha` after Holm-Bonferroni correction) **and** `system_score_delta < 0`. A production candidate whose score improved with the same statistical strength does not trigger `SYSTEM_DRIFT` or `JOINT_DRIFT` — it is reported as `NONE` (or `JUDGE_DRIFT`, if the judge side also shifted). This is intentional and asymmetric with the judge side: `JUDGE_DRIFT` fires on a two-sided rejection regardless of the sign of `judge_score_delta`, because a judge that silently drifts *either* looser or stricter is a reliability problem worth flagging, whereas a system that improved beyond the anchor set isn't the failure mode this layer exists to catch. Callers must not assume `SYSTEM_DRIFT`/`JOINT_DRIFT` cover "any large system-side change" — only statistically-supported, unexplained drops. See the **0.3.0 — Breaking Change** section below for the full statistical mechanism and for what replaced the earlier `significance_threshold` parameter.
* `INCONCLUSIVE` means the Attribution Engine could not evaluate the anchor or production score distributions at all — one of the four input score lists was empty or contained a non-finite value. `system_score_delta` and `judge_score_delta` are both `0.0` on an `INCONCLUSIVE` verdict; callers must not read `0.0` on these fields as "no drift" without first checking `attribution`.
* `system_score_delta` and `judge_score_delta` are both included even when `attribution` is `NONE`, so that Reporting's Judge Reliability Panel (Phase 5) can plot both time series regardless of whether a verdict crossed a threshold that day. Do not omit these fields "to save space" when there's no drift; the longitudinal panel needs the full series, not just the interesting points.

### `AnchorSet` (`trust/anchor_set.py`)

```python
class AnchorItem(BaseModel):
    model_config = ConfigDict(strict=True)

    anchor_id: str
    input_payload: str
    expected_output: str
    human_label: float = Field(ge=0.0, le=1.0)


class AnchorSet(BaseModel):
    model_config = ConfigDict(strict=True)

    anchor_set_id: str
    items: list[AnchorItem] = Field(min_length=1)
    created_at: datetime
```

**Contract guarantees:**

* `AnchorSet` is fixed once created. If the anchor set needs updating, that is a new `AnchorSet` with a new `anchor_set_id`, not an in-place edit. An anchor set that quietly changes underneath the Attribution Engine defeats the entire purpose of the layer, since you'd no longer be able to tell whether a score change came from the system, the judge, or the ruler you're measuring both with.

### `JudgeReliabilityStatus` (`reporting/judge_reliability.py`)

A coarse status for the Judge Reliability Panel. It summarizes whether the observed judge-drift rate remains within the configured warning threshold.

```python
class JudgeReliabilityStatus(str, Enum):
    STABLE = "stable"
    UNSTABLE = "unstable"
```

**Contract guarantees:**

* `JudgeReliabilityStatus` has exactly two possible values: `stable` and `unstable`.
* `STABLE` means the computed `judge_drift_rate` is less than or equal to the configured `drift_rate_warning` threshold.
* `UNSTABLE` means the computed `judge_drift_rate` is strictly greater than the configured `drift_rate_warning` threshold.
* The status is derived from a longitudinal window of `AttributionVerdict` objects; it is not a property of an individual verdict.
* `JudgeReliabilityStatus` is categorical reporting output. It does not replace or reinterpret the underlying drift rate.

### `JudgeReliabilityMetrics` (`reporting/judge_reliability.py`)

A longitudinal summary of judge behavior over a window of `AttributionVerdict` objects. It is populated from verdict history rather than from a single verdict, because rates, trends, and longitudinal score statistics require a window.

```python
class JudgeReliabilityMetrics(BaseModel):
    model_config = ConfigDict(strict=True)

    anchor_set_id: str
    period_start: datetime
    period_end: datetime
    verdict_count: int = Field(ge=1)
    judge_drift_rate: float = Field(ge=0.0, le=1.0)
    system_drift_rate: float = Field(ge=0.0, le=1.0)
    joint_drift_rate: float = Field(ge=0.0, le=1.0, default=0.0)  # Phase 5 (post-launch)
    inconclusive_rate: float = Field(ge=0.0, le=1.0, default=0.0)  # Phase 5 (post-launch)
    none_rate: float = Field(ge=0.0, le=1.0)
    mean_judge_score_delta: float
    judge_score_delta_std: float
    mean_calibration_mae: float | None = None
    status: JudgeReliabilityStatus
    flagged_verdicts: list[AttributionVerdict] = Field(default_factory=list)
```

**Contract guarantees:**

* `model_config = ConfigDict(strict=True)` means Pydantic performs strict validation rather than silently coercing incompatible input types.
* `verdict_count` must be at least `1`. An empty verdict window cannot produce a valid reliability summary.
* `judge_drift_rate`, `system_drift_rate`, `joint_drift_rate`, `inconclusive_rate`, and `none_rate` are bounded to `[0.0, 1.0]`. They represent fractions of the supplied verdict window, not percentages from `0` to `100`.
* `anchor_set_id` identifies the fixed `AnchorSet` against which the summarized verdicts were evaluated. A reliability window must not mix verdicts from different anchor sets.
* `period_start` is the earliest `evaluated_at` timestamp in the supplied verdict window, and `period_end` is the latest.
* `judge_drift_rate` is the fraction of verdicts whose `attribution` is `DriftAttribution.JUDGE_DRIFT` **or** `DriftAttribution.JOINT_DRIFT`. See the Phase 5 (post-launch) **Breaking Change** entry below: this is a change in meaning from the original definition of this field.
* `system_drift_rate` is the fraction of verdicts whose `attribution` is `DriftAttribution.SYSTEM_DRIFT` **or** `DriftAttribution.JOINT_DRIFT`. Same breaking-change note as `judge_drift_rate` applies.
* `joint_drift_rate` is the fraction of verdicts whose `attribution` is `DriftAttribution.JOINT_DRIFT`. It is already counted inside both `judge_drift_rate` and `system_drift_rate` above; it is exposed separately so a reader can recover the pure single-cause rates by subtraction (`judge_drift_rate - joint_drift_rate`, `system_drift_rate - joint_drift_rate`) without re-deriving them from `flagged_verdicts`.
* `inconclusive_rate` is the fraction of verdicts whose `attribution` is `DriftAttribution.INCONCLUSIVE`. These verdicts are excluded from `judge_drift_rate`, `system_drift_rate`, and `none_rate`.
* `none_rate` is the fraction of supplied verdicts whose `attribution` is `DriftAttribution.NONE`.
* `judge_drift_rate + system_drift_rate + none_rate + inconclusive_rate - joint_drift_rate` sums to `1.0` over the supplied window (the subtraction removes `JOINT_DRIFT`'s double-count in the first two terms).
* `mean_judge_score_delta` is the arithmetic mean of `judge_score_delta` across every supplied verdict **except** those whose attribution is `DriftAttribution.INCONCLUSIVE`. `AttributionEngine.analyze` reports `judge_score_delta = 0.0` on an `INCONCLUSIVE` verdict as a placeholder meaning "not measured," not as an observation of zero drift; including it would bias this mean toward zero. `NONE`, `SYSTEM_DRIFT`, `JUDGE_DRIFT`, and `JOINT_DRIFT` verdicts are all included, since each of those carries a real measured delta regardless of which threshold it crossed.
* `judge_score_delta_std` is the sample standard deviation of that same non-`INCONCLUSIVE` `judge_score_delta` series. For a window with exactly one non-`INCONCLUSIVE` verdict, it is `0.0` because there is no sample variation to estimate.
* `compute_judge_reliability` rejects a verdict window in which every verdict is `DriftAttribution.INCONCLUSIVE` with `ValueError`, since there is no measured delta to summarize. A window with at least one non-`INCONCLUSIVE` verdict alongside any number of `INCONCLUSIVE` ones is valid; the `INCONCLUSIVE` ones are still reflected in `inconclusive_rate`, `verdict_count`, and `flagged_verdicts`, just not in the delta statistics.
* `mean_calibration_mae` is optional because calibration data is not required to construct the reliability summary. When calibration errors are supplied and contain `mae` values, the field contains their arithmetic mean; otherwise it remains `None`.
* `flagged_verdicts` defaults to an empty list. When computed from a verdict window, it contains every verdict whose attribution is not `DriftAttribution.NONE`, preserving both judge-drift and system-drift verdicts for downstream reporting.
* `status` is `UNSTABLE` when the computed judge-drift rate is strictly greater than the configured warning threshold; otherwise it is `STABLE`. The current default warning threshold is `0.10`.
* `compute_judge_reliability` rejects an empty verdict list with `ValueError`.
* `compute_judge_reliability` rejects a verdict window containing multiple `anchor_set_id` values with `ValueError`. An anchor-set update creates a new `anchor_set_id`; verdicts from different rulers must therefore be summarized separately.
* The reliability summary's non-delta fields (`verdict_count`, `*_rate` fields, `flagged_verdicts`) are derived from the complete supplied verdict window. The delta statistics (`mean_judge_score_delta`, `judge_score_delta_std`) are derived from the non-`INCONCLUSIVE` subset only, per the bullets above; they are not restricted to `flagged_verdicts` (i.e. `NONE`-attribution verdicts are still included in the delta statistics, just not in `flagged_verdicts`).

### `DashboardSnapshot` (`reporting/dashboard.py`)

The reporting contract for one `system_type` at one point in time. This model contains reporting data only; it does not render a dashboard. A CLI, notebook, or future web UI is responsible for presenting it to a human.

```python
class DashboardSnapshot(BaseModel):
    model_config = ConfigDict(strict=True)

    generated_at: datetime
    system_type: str
    health_score: float = Field(ge=0.0, le=100.0)
    latest_attribution: AttributionVerdict | None = None
    judge_reliability: JudgeReliabilityMetrics | None = None
    regression_verdicts: list[RegressionVerdict] = Field(default_factory=list)
    gate_verdict: GateVerdict | None = None
```

**Contract guarantees:**

* `model_config = ConfigDict(strict=True)` means the snapshot validates its declared types without implicit coercion.
* `generated_at` records when the snapshot was assembled. The assembly function populates it with the current UTC time.
* `system_type` identifies the system represented by the snapshot.
* `health_score` is bounded to `[0.0, 100.0]`. It is the output of `compute_system_health_score`; `DashboardSnapshot` stores the resulting score rather than recomputing it.
* `latest_attribution` is optional and defaults to `None`. When attribution history is supplied, it contains the `AttributionVerdict` with the latest `evaluated_at` timestamp.
* `judge_reliability` is optional and defaults to `None`. It is populated from supplied attribution history when that history passes the reliability aggregation contract. It is not fabricated when no attribution history is available.
* `regression_verdicts` defaults to an empty list and represents the regression information available for the snapshot. The list is supplied by the caller and is not recomputed by dashboard assembly.
* `gate_verdict` is optional and defaults to `None`. When present, it carries the Phase 4 CI/deployment gate result rather than duplicating or reducing it to a boolean.
* `DashboardSnapshot` represents five distinct reporting signals without recomputing their underlying meanings: system health through `health_score`, attribution through `latest_attribution`, longitudinal judge reliability through `judge_reliability`, regression information through `regression_verdicts`, and CI/deployment gating through `gate_verdict`.
* `assemble_dashboard_snapshot` takes `quality_score` and `confidence` as direct inputs to `compute_system_health_score`. The reporting layer does not decide which upstream quality metric should represent the system.
* If `attribution_verdicts` is omitted or empty, `latest_attribution` remains `None`, `judge_reliability` remains `None`, and the health-score attribution input falls back to `DriftAttribution.NONE`.
* If attribution history is supplied, the latest verdict determines the attribution component used by the health-score computation.
* Judge reliability is computed from the supplied attribution history. If reliability aggregation fails validation, such as when the verdicts contain mixed anchor sets, the dashboard assembly logs the failure and continues with the health score rather than failing the entire snapshot.
* `regression_verdicts` and `gate_verdict` are optional reporting inputs. Omitting them produces an empty regression list and a `None` gate verdict respectively.
* The model is data only. It does not render, persist, or otherwise own presentation behavior.

## Phase 5 (post-launch) — Breaking Change: `DriftAttribution` expansion and `judge_drift_rate` / `system_drift_rate` redefinition

This section documents a breaking change to two Phase 5 contracts, per the Versioning Rule at the bottom of this document.

**What changed:**

1. `DriftAttribution` (`trust/attribution.py`) gained two new members: `JOINT_DRIFT` (both judge and system shifted significantly in the same window) and `INCONCLUSIVE` (an input score distribution was empty or non-finite). The enum went from three states to five. This part alone is additive to the enum's *domain*, but it is not additive to the *meaning* of the two rate fields below, because `compute_judge_reliability` folds `JOINT_DRIFT` into both of them.
2. `JudgeReliabilityMetrics.judge_drift_rate` (`reporting/judge_reliability.py`) no longer means "fraction of verdicts where `attribution == JUDGE_DRIFT`." It now means "fraction of verdicts where `attribution` is `JUDGE_DRIFT` or `JOINT_DRIFT`." `system_drift_rate` changed the same way with `SYSTEM_DRIFT` / `JOINT_DRIFT`. Two new fields, `joint_drift_rate` and `inconclusive_rate`, were added to let a reader recover the original single-cause rates.

**Why this is breaking, not additive:** the Versioning Rule treats "changing a field's meaning" as a breaking change even when the field's type and bounds are untouched. `judge_drift_rate` still validates as `float, ge=0.0, le=1.0`, but the same historical verdict window now produces a different value than it did before `JOINT_DRIFT` existed, because joint-drift verdicts are no longer silently absent from the rate — they're double-counted into both `judge_drift_rate` and `system_drift_rate`.

**Migration path for persisted data:** any `JudgeReliabilityMetrics` snapshot persisted before this change was computed under the old definition (pure `JUDGE_DRIFT` / `SYSTEM_DRIFT` fractions, with no `JOINT_DRIFT` or `INCONCLUSIVE` state to produce them) and remains valid under that old definition — it does not need to be rewritten, because `AttributionVerdict.attribution` in that historical data can only have been `NONE`, `SYSTEM_DRIFT`, or `JUDGE_DRIFT`. Do not recompute old snapshots against the new logic to "backfill" `joint_drift_rate`/`inconclusive_rate`; leave those two fields at their `0.0` default for pre-migration snapshots, which is correct since no verdict in that data can be `JOINT_DRIFT` or `INCONCLUSIVE`. Any code that compares a `judge_drift_rate` computed before this change against one computed after it, e.g. across the boundary in a longitudinal dashboard, is comparing two different metrics and must be updated to either recompute the old window under the new logic or clearly label the discontinuity.

**Version bump:** requires a version bump in `pyproject.toml` per the Versioning Rule; not yet applied as of this section being written.

## Phase 5 (0.3.0) — Breaking Change: statistical attribution replaces `significance_threshold`

This section documents a breaking change to `AttributionEngine` (`trust/attribution.py`), per the Versioning Rule at the bottom of this document.

**What changed:**

1. `AttributionEngine.__init__` no longer accepts `significance_threshold`. It accepts `alpha` (default `0.05`), `confidence_level` (default `0.95`), `n_bootstrap` (default `10000`), and an optional `seed`. There is no backward-compatible alias; a caller still passing `significance_threshold` gets a `TypeError` at construction.
2. `AttributionEngine.analyze` no longer decides `JUDGE_DRIFT` or `SYSTEM_DRIFT` by comparing `abs(score_delta)` against a fixed magnitude. It now requires statistical evidence:
   - A bootstrap confidence interval (at `confidence_level`, over `n_bootstrap` resamples) is always computed for both the judge-side and system-side delta. The interval must exclude zero for that side to be eligible for drift.
   - When both groups in a comparison have at least five observations, a Mann-Whitney U test is also run (two-sided for the judge side, one-sided "less" for the system side), and its p-value is subject to Holm-Bonferroni correction across the two hypotheses at `alpha`.
   - When either group has fewer than five observations, Mann-Whitney U is not run for that comparison. That comparison has no p-value, is excluded from the Holm-Bonferroni family entirely, and is decided on the bootstrap confidence interval alone. A fabricated placeholder p-value (e.g. `0.0` or `1.0`) must never be substituted into the correction; doing so distorts the threshold applied to the other comparison's real p-value.
   - The system-side direction constraint (`system_score_delta < 0`) described earlier in this document is unchanged; it is now applied on top of the statistical decision rather than the magnitude comparison.
3. `AttributionVerdict.explanation` now reports the statistical method used (`bootstrap_ci+mann_whitney` or `bootstrap_ci_only(n<5, uncorrected)`), the p-value where one exists, and `alpha`, instead of describing a raw-magnitude comparison as "statistically significant."
4. `DriftAttribution`'s five states, `AttributionVerdict`'s fields, and every downstream consumer's contract (`JudgeReliabilityMetrics`, `DashboardSnapshot`) are unchanged by this section. Only the internal decision rule that produces `attribution`, `system_score_delta`, and `judge_score_delta` changed; the shapes callers already integrate against did not.

**Why this is breaking, not additive:** `significance_threshold` is a removed constructor parameter with no alias, which is unambiguously breaking under the Versioning Rule. It is also a behavioral break independent of the parameter rename: the same pair of score distributions can produce a different `attribution` verdict under statistical evidence than it did under a raw mean-difference threshold, because sample size and variance now matter and previously did not. A small, noisy sample that used to trigger `SYSTEM_DRIFT` purely from a large mean gap may now report `NONE` if that gap isn't statistically supported, and vice versa for a large, low-variance sample with a smaller but well-supported gap.

**Migration path for callers:**

- Replace `AttributionEngine(significance_threshold=x)` with `AttributionEngine(alpha=x)` as a starting point, but treat this as a like-for-like parameter swap only, not an equivalence guarantee: `alpha` bounds a p-value, `significance_threshold` bounded a raw score gap, and the same numeric value does not carry the same meaning across the two.
- Callers must supply complete per-item score distributions (`list[float]`, one score per evaluated item) to `anchor_ref_scores`, `anchor_rescored_scores`, `prod_baseline_scores`, and `prod_candidate_scores`. Pre-aggregating to a mean before calling `analyze` was tolerated under the old magnitude comparison but defeats the statistical machinery now: `bootstrap_delta_ci` and `mann_whitney_regression` need the full sample to estimate variance and resample from, not a single collapsed number.
- Any caller or dashboard relying on `explanation` text matching a specific "statistically significant" string should re-check that parsing; the phrasing and the information it carries both changed (see point 3 above).
- Persisted `AttributionVerdict` records from before this change remain valid as data — `attribution`, `system_score_delta`, and `judge_score_delta` have the same shape and meaning as fields, only the rule that produced them differs. Do not recompute historical verdicts against the new logic to "backfill" statistical detail that was never captured (no historical p-values or confidence intervals exist to backfill with). Do not treat a longitudinal series that crosses this boundary as produced by one consistent rule; label the discontinuity if the series is presented across it.

**Version bump:** requires a version bump in `pyproject.toml` per the Versioning Rule (this change ships in `0.3.0`).

### `BehavioralAnchorMetric`

Implements the same `Metric` protocol from Phase 2. Its `MetricResult.details` carries the embedding-similarity band (`"aligned"`, `"neutral"`, `"deviation"`) as a string value, consistent with the `details` field's declared type. No new contract needed; this is the payoff of having designed `Metric` correctly in Phase 2.

---

## Import Direction Rule (applies to every phase)

To keep the "no circular dependency" requirement enforceable by tooling and not just by good intentions, imports flow in one direction only:

```text
instrumentation  →  orchestrator  →  metrics  →  trust
                                            ↘         ↘
                                             storage → regression → gate → reporting
```

A module may import from anything to its left in this chain. It may never import from anything to its right. `storage/models.py` is the one exception: because `Run` and `Baseline` embed `MetricResult`, `storage/models.py` is permitted to import the `MetricResult` type from `metrics/base.py` specifically, and nothing else from `metrics/`. If you find yourself importing `regression` from inside `metrics/`, or `reporting` from inside `storage/`, stop, that import is the circular dependency this rule exists to prevent, and the fix is to move the shared type into `storage/models.py` or `metrics/base.py`, not to add the import and suppress the warning.

`ruff`'s `TID` (flake8-tidy-imports) rules are configured in `pyproject.toml` to ban relative imports project-wide, which forces every cross-module import to be explicit and absolute (`from nirizan.metrics.base import Metric`), making violations of this rule easy to spot in review rather than hidden behind `from ..metrics import base`.

## Versioning Rule for This Document

Every contract above is versioned implicitly by the phase it was introduced in. A breaking change to any model (removing a field, changing a field's meaning, narrowing a type) requires:

1. A new section here titled with the phase or release it changes in, explicitly marked **Breaking Change**.
2. A stated migration path for any persisted data using the old shape.
3. A version bump in `pyproject.toml`.

Adding a new optional field with a default value is not a breaking change and does not require a new section, just an inline edit to the model above with a comment noting which phase added it.
