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
````

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
    code_commit: str | None = None       # Phase 3: stamped by collector.py at ingest
    data_snapshot_id: str | None = None  # Phase 3: stamped by collector.py at ingest
    session_id: UUID | None = None       # Phase 3: set when captured inside Tracer.session(...)

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
    async def list_by_application(
        self, application_name: str, limit: int = 100
    ) -> list[Trace]: ...
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

    async def dispatch(self, trace: Trace, system_type: str) -> list[MetricResult]:
        ...
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

* `attribution` is exactly one of the three enum values, never a probability or a blend. The Attribution Engine is allowed to be uncertain internally, but it must commit to a verdict at this boundary. Anything downstream (Regression Detection, Reporting) treats this as a categorical fact, not a score to threshold again.
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

### `BehavioralAnchorMetric`

Implements the same `Metric` protocol from Phase 2. Its `MetricResult.details` carries the embedding-similarity band (`"aligned"`, `"neutral"`, `"deviation"`) as a string value, consistent with the `details` field's declared type. No new contract needed; this is the payoff of having designed `Metric` correctly in Phase 2.

### `JudgeReliabilityStatus` (`reporting/judge_reliability.py`)

A coarse status for the longitudinal Judge Reliability Panel.

```python
from enum import Enum


class JudgeReliabilityStatus(str, Enum):
    STABLE = "stable"
    UNSTABLE = "unstable"
```

**Contract guarantees:**

* `JudgeReliabilityStatus` has exactly two possible values: `stable` and `unstable`.
* The status is categorical rather than a numeric score. Consumers should use the enum value to represent the coarse panel state rather than attempting to reconstruct it from the underlying rates.
* `UNSTABLE` is selected by `compute_judge_reliability` when the computed `judge_drift_rate` is strictly greater than the configured `drift_rate_warning` threshold. Equality with the threshold remains `STABLE`.
* The current default warning threshold is `0.10` (10%). This is an initial operational default, not a calibrated statistical threshold; the implementation explicitly leaves room for later calibration against evaluation/ablation results.

### `JudgeReliabilityMetrics` (`reporting/judge_reliability.py`)

A longitudinal summary of judge behavior over a window of `AttributionVerdict` objects. It is not a single-verdict model: the aggregation function requires at least one verdict and computes rates, averages, and trends across the supplied window.

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JudgeReliabilityMetrics(BaseModel):
    model_config = ConfigDict(strict=True)

    anchor_set_id: str
    period_start: datetime
    period_end: datetime
    verdict_count: int = Field(ge=1)
    judge_drift_rate: float = Field(ge=0.0, le=1.0)
    system_drift_rate: float = Field(ge=0.0, le=1.0)
    none_rate: float = Field(ge=0.0, le=1.0)
    mean_judge_score_delta: float
    judge_score_delta_std: float
    mean_calibration_mae: float | None = None
    status: JudgeReliabilityStatus
    flagged_verdicts: list[AttributionVerdict] = Field(default_factory=list)
```

**Contract guarantees:**

* `model_config = ConfigDict(strict=True)` means the model uses Pydantic strict validation. Fields are not implicitly coerced across incompatible types.
* `anchor_set_id` identifies the fixed `AnchorSet` against which the summarized verdicts were evaluated.
* `period_start` and `period_end` describe the temporal window represented by the supplied verdicts. `compute_judge_reliability` derives them from the minimum and maximum `AttributionVerdict.evaluated_at` values in the window.
* `verdict_count` is required and must be at least `1`. Pydantic enforces this with `Field(ge=1)`. The aggregation function separately rejects an empty input list before constructing the model.
* `judge_drift_rate`, `system_drift_rate`, and `none_rate` are required normalized rates. Each is constrained by Pydantic to `[0.0, 1.0]`.
* `judge_drift_rate` is the fraction of supplied verdicts whose `attribution` is `DriftAttribution.JUDGE_DRIFT`.
* `system_drift_rate` is the fraction of supplied verdicts whose `attribution` is `DriftAttribution.SYSTEM_DRIFT`.
* `none_rate` is the fraction of supplied verdicts whose attribution is neither judge drift nor system drift, corresponding to `DriftAttribution.NONE` in the current `DriftAttribution` contract.
* The three rates are computed from the same verdict window. The aggregation function counts judge-drift and system-drift verdicts explicitly and derives the remaining count as the `NONE` count.
* `mean_judge_score_delta` is the arithmetic mean of `judge_score_delta` across every verdict in the window, including verdicts whose attribution is `NONE` or `SYSTEM_DRIFT`. The complete series is retained because `AttributionVerdict` always provides `judge_score_delta`.
* `judge_score_delta_std` is the sample standard deviation of the judge score deltas. For a one-verdict window, the implementation returns `0.0` because a sample standard deviation cannot be computed from fewer than two observations.
* `mean_calibration_mae` is optional and defaults to `None`. When calibration errors are supplied and at least one supplied calibration record contains a `"mae"` value, the implementation computes the arithmetic mean of those MAE values. If no usable MAE values are present, the field remains `None`.
* `status` is a `JudgeReliabilityStatus`, never an arbitrary string. The aggregation function marks the panel `UNSTABLE` when `judge_drift_rate` is strictly greater than the configured warning threshold; otherwise it marks it `STABLE`.
* `flagged_verdicts` defaults to a new empty list for each model instance via `default_factory=list`. It contains the supplied verdicts whose attribution is not `DriftAttribution.NONE`, i.e. the judge-drift and system-drift verdicts identified in the summarized window.
* The reliability summary is explicitly longitudinal. `compute_judge_reliability` rejects an empty verdict list with `ValueError`, because a single summary with no observations cannot provide a meaningful rate or trend.
* All verdicts passed to `compute_judge_reliability` must share the same `anchor_set_id`. If more than one anchor-set ID is present, the function raises `ValueError` rather than blending observations measured against different anchor sets.
* This same-anchor-set requirement preserves the meaning of the reliability statistics: one summary represents one fixed measurement ruler. Updating an anchor set creates a new `anchor_set_id` rather than silently mixing old and new measurements.
* The `AttributionVerdict` objects in `flagged_verdicts` retain their complete attribution records rather than reducing them to IDs or counts, allowing downstream reporting to inspect the original attribution, score deltas, evaluation time, and explanation.
* `JudgeReliabilityMetrics` itself does not enforce cross-field mathematical relationships through Pydantic validators. Its rate bounds, minimum verdict count, and field types are model-level guarantees; the relationships between those fields and the underlying verdict window are guarantees of `compute_judge_reliability`.
* The current default judge-drift warning threshold is `0.10`. This threshold is intentionally documented as an initial default rather than a statistically calibrated guarantee.

### `DashboardSnapshot` (`reporting/dashboard.py`)

The assembled reporting contract for one `system_type` at one point in time. This model contains reporting data only; it does not render a dashboard or perform presentation logic.

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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

* `model_config = ConfigDict(strict=True)` means the snapshot uses Pydantic strict validation.
* `generated_at` records when the snapshot was assembled. `assemble_dashboard_snapshot` populates it with the current UTC time.
* `system_type` identifies the system represented by the snapshot. The value is supplied by the caller and is not inferred from the reporting inputs.
* `health_score` is required and constrained to `[0.0, 100.0]` by `Field(ge=0.0, le=100.0)`. The score is produced by `compute_system_health_score` from the supplied `quality_score`, `confidence`, and attribution state.
* `latest_attribution` is optional and defaults to `None`. When attribution verdicts are supplied, `assemble_dashboard_snapshot` selects the verdict with the greatest `evaluated_at` timestamp.
* `judge_reliability` is optional and defaults to `None`. When attribution history is available, the assembly function attempts to compute `JudgeReliabilityMetrics` from that history. If aggregation fails validation, such as when verdicts contain multiple anchor-set IDs, the function logs the failure and leaves this reporting component unset rather than failing the complete snapshot.
* `regression_verdicts` defaults to a new empty list through `default_factory=list`. The assembly function also normalizes an omitted or `None` input to an empty list.
* `gate_verdict` is optional and defaults to `None`. A snapshot can therefore represent a reporting state in which no gate result is available.
* `DashboardSnapshot` represents four distinct reporting signals without recomputing their underlying meanings: system health through `health_score`, attribution through `latest_attribution`, longitudinal judge reliability through `judge_reliability`, regression information through `regression_verdicts`, and CI/deployment gating through `gate_verdict`.
* `assemble_dashboard_snapshot` does not derive `quality_score` or `confidence`. Those values are explicitly supplied by the caller because choosing which quality and confidence measurements represent "the" system quality is a call-site decision.
* If `attribution_verdicts` is omitted or empty, `latest_attribution` remains `None`, `judge_reliability` remains `None`, and the attribution input to the health-score calculation is `DriftAttribution.NONE`. The health score therefore does not incur an attribution penalty when there is no attribution history to evaluate.
* If attribution history is present, the latest verdict's `attribution` is used as the attribution input to `compute_system_health_score`.
* `judge_reliability` is calculated from the supplied attribution history rather than from the latest verdict alone. This preserves the longitudinal nature of `JudgeReliabilityMetrics`.
* The dashboard assembly is intentionally resilient to judge-reliability aggregation failure. A mixed-anchor-set or otherwise invalid verdict window does not invalidate the health score, regression results, or gate result; the judge-reliability panel is skipped instead.
* `regression_verdicts` contains the caller-provided `RegressionVerdict` objects and is not recomputed by the dashboard assembly layer.
* `gate_verdict` contains the caller-provided `GateVerdict` and is not recomputed by the dashboard assembly layer.
* `DashboardSnapshot` is data only. It does not render a dashboard, produce UI output, persist reporting data, or otherwise take ownership of presentation concerns. CLI, notebook, or future web UI layers consume the snapshot.
* The model's health-score bound is enforced directly by Pydantic. The semantic calculation of the score is delegated to `compute_system_health_score`; the dashboard layer does not duplicate that calculation.
* Optional reporting components use `None` to represent unavailable information, while `regression_verdicts` uses an empty list to represent no regression verdicts. This distinction is intentional and part of the contract.

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
