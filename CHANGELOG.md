# Changelog

All notable changes to NiriZan are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While NiriZan is on a `0.x` version, breaking changes are reflected in a
**minor** version bump (`0.1.0 → 0.2.0`), per the Versioning Rule in
[`docs/contracts.md`](docs/contracts.md#versioning-rule-for-this-document); the
jump to `1.0.0` is reserved for the point the public contract surface is
considered stable.

## [0.5.0] - 2026-10-16

### Added

- **Optional OpenTelemetry integration** through the `otel` extra, adding bidirectional interoperability between NiriZan traces and OpenTelemetry spans without requiring OpenTelemetry dependencies in core installations.
  - `NiriZanToOTelExporter` and `export_trace_to_otel` export validated NiriZan traces to an OpenTelemetry tracer, with parent-first span ordering, trace-context handling, span-kind mapping, status metadata, and identity provenance.
  - `NiriZanSpanProcessor` converts completed OpenTelemetry spans into validated NiriZan traces using per-trace buffering, parent resolution, and configurable ingestion policies.
  - `init_tracer()` initializes NiriZan's own async tracer and accepts an optional exporter. OpenTelemetry provider setup remains the application's responsibility; this release does not provide OTel metrics or logging initialization.
- **OpenTelemetry semantic-convention helpers** for GenAI operations, token usage, retrieval, tool use, planning, status metadata, and sequence-valued attributes. Canonical token-usage attributes are emitted alongside legacy aliases for compatibility.
- **Thread-safe asynchronous trace delivery** through `ThreadSafeTraceSink` and `LoopTraceSink`, bridging OpenTelemetry's synchronous span-processing callbacks to NiriZan's asynchronous trace collector.
- **Expanded OpenTelemetry regression tests** covering identifier mapping, export and ingestion, semantic conventions, trace assembly, parent-link integrity, privacy defaults, failure handling, and operation without the optional dependency.
- **Isolation test layers** covering the optional-extra boundary end to end: the core package imports and runs a full tracer-to-collector-to-SQLite pipeline with OpenTelemetry import-blocked in a subprocess, the installed metadata and declared extras are checked, core parity and non-mutation are checked with the bridge active and unused, round-trip fidelity is checked over deep chains, fan-outs, multi-root traces, every span kind, scalar types, unicode, empty and absent values, oversize truncation, and seeded random forests, an eight-thread concurrency test checks the buffer caps and the accounting invariants, and a real-event-loop test drives the thread-hop sink into SQLite with closed-loop, failing-collector, and failing-repository isolation.

### Changed

- **Breaking:** Trace timestamps are now stored and compared as instants. `save` rejects a naive (offset-less) `created_at`, `started_at`, or `ended_at` with `ValueError` before writing any row, and `purge_older_than` requires a timezone-aware cutoff, accepting a trailing `Z`. Every timestamp written is canonical UTC ISO-8601 text.
- **Breaking:** Timestamps read back from storage are always timezone-aware. A stored row without an offset is a legacy row: it is read as UTC, returned as an aware UTC `datetime`, and logged once per process. Consumers that re-attached a local offset to repository output must stop doing so.
- **Breaking:** `Trace` rejects an out-of-trace parent link unless the span is marked with `nirizan.parent.synthetic=True`.
- Trace persistence now replaces the stored span set for a trace. Saving an existing trace updates mutable span fields and removes spans absent from the incoming trace, including when the incoming trace contains no spans. Cross-trace span-ID collisions are rejected instead of overwriting another trace's data.
- List ordering compares by instant rather than by stored text, at millisecond resolution: two traces whose instants land in the same millisecond are ordered by stored text and then `trace_id`, while rows written since 0.5.0 are canonical UTC and therefore order exactly. Spans of one trace are ordered by exact instant. Pagination stays deterministic in every case: a total order with no gaps or duplicates. Normalizing legacy rows to canonical UTC text is an optional migration tracked separately in #84.
- `purge_older_than` is exact at full stored precision. It compares instants at microsecond resolution for canonical and legacy rows alike, so a trace a microsecond inside the cutoff's millisecond is now removed, and a trace exactly at the cutoff is still kept.
- **Removed hardcoded BibTeX citation blocks** from all submodule `__init__.py` files (`instrumentation/`, `metrics/`, `gate/`, `regression/`, `trust/`, `orchestrator/`, `storage/`, `reporting/`). Version metadata is now maintained only in `pyproject.toml` and `src/nirizan/__init__.py`, eliminating a maintenance hazard where submodule citation versions drifted independently (e.g., `instrumentation/` cited `0.5.0`, `trust/` cited `0.3.0`, `orchestrator/` and `storage/` cited `0.1.0`, `reporting/` cited `0.2.0`).
- **Content capture is disabled by default** in both OpenTelemetry export and ingestion. Prompt, completion, retrieval, tool, and planning content is withheld unless explicitly enabled. This covers the known content attributes only; an arbitrary custom attribute passes through unchanged in both directions.
- **Stashed NiriZan identifiers are no longer trusted by default.** Set `trust_stashed_ids=True` to recover NiriZan IDs from OpenTelemetry attributes; otherwise, identifiers are derived from OpenTelemetry IDs. A derived trace ID is a namespaced hash of the OTel trace ID rather than the OTel trace ID reinterpreted, so an untrusted incoming trace can never take a stored native trace's ID and overwrite it; the original OTel trace ID is kept on every ingested span as `otel.trace_id` for correlation.
- **Trace and span integrity is enforced.** Missing parent links must be explicitly marked as synthetic. During ingestion, genuinely missing local parents can be represented by synthetic-parent metadata under `orphan_policy="emit"`; children of dropped spans are re-attached to surviving in-trace ancestors without being marked synthetic solely because of that re-attachment.
- **OpenTelemetry ingestion is more defensive and resource-bounded**, with configurable queue, buffer, and payload limits; improved eviction and parent resolution; safer attribute serialization; and string-attribute truncation.
- **OpenTelemetry export and ingestion handle identity and context more consistently**, including W3C `tracestate`, explicit parent contexts, remote parents, GenAI span-kind inference, and identity provenance.
- **Dependency-graph generation scans nested Python packages recursively**, keeping the generated module graph aligned with the instrumentation package structure.
- **CI covers a two-dimensional matrix**: core-only installs and installs with the OpenTelemetry extra, each on the minimum supported Python and the latest stable. The core-only legs assert that OpenTelemetry is not importable and run the whole suite without it, so the optional-extra promise is enforced rather than described.

### Fixed

- The OpenTelemetry processor no longer buffers an unbounded backlog during its shutdown drain. The drain enforces the same `max_buffered_traces` and `max_buffered_spans` caps as the live intake path, so a backlog accumulated while the consumer was blocked cannot grow the buffers past the configured limits.
- Prevented untrusted stashed session IDs from being recovered when `trust_stashed_ids=False`.
- Prevented content-bearing attributes and extracted payloads from being captured during ingestion when `capture_content=False`.
- Corrected parent resolution for missing, remote, dropped, duplicate-ID, and late-arriving spans.
- Prevented malformed sequence attributes and unserializable values from unnecessarily discarding convertible spans.
- Prevented non-finite floating-point values from being emitted as non-standard JSON values.
- Preserved zero-valued token counts and `top_k` values during attribute conversion.
- Improved timestamp conversion precision and sequence-attribute encoding performance.
- Corrected `tracestate` serialization and improved handling of processor reinitialization and consumer-thread lifecycle.
- Prevented failed trace replacements and cross-trace span-ID collisions from leaving partially updated storage state.

### Documentation

- Documented the OpenTelemetry adapter architecture, optional dependencies, configuration defaults, identity trust policy, content-capture controls, asynchronous delivery path, and parent-link integrity contracts.
- Added the 0.5.0 breaking-change section to `docs/contracts.md` covering the timestamp policy, `save` replacement and collision semantics, marked synthetic parents, and the migration path for both callers and persisted data.
- Documented how OpenTelemetry isolation is designed and verified: the optional extra, the import boundaries, the import-linter contracts, the CI matrix, and the test layers that pin each of them.
- Updated the generated dependency graph to include nested instrumentation modules.

## [0.4.0] - 2026-09-20

This release adds a second, multivariate track to regression detection. It catches changes in how metrics vary together (variance and correlation shifts) that the per-metric comparator cannot see. It contains two breaking changes and a license change; see **Changed**.

### Added

- **Multivariate structure track** (`nirizan.regression.multivariate`). `MultivariateComparator` compares row-aligned baseline and candidate score matrices with two permutation-calibrated tests and always returns exactly two `MultivariateVerdict` records:
  - `scale`: variance-only drift, from epsilon-floored log-variance ratios. Invariant to location shifts.
  - `dependence`: correlation-only drift, from the largest change in within-group rank correlation. Invariant to rank-preserving changes in the individual metrics. Skipped, with a `NONE` verdict, when there is only one metric.
  - Both p-values use the `(k+1)/(R+1)` convention and are combined with Holm-Bonferroni at `structure_alpha`. Both tests are undirected: they flag that structure changed, not that quality dropped.
- **Severity modes** via the frozen Pydantic model `MultivariateConfig`. `BALANCED` (default) caps severity at `WARNING`, so an undirected structure change can never block a deploy on its own. `STRICT` allows `BLOCKING` and is intended for callers who have carved the structure alpha out of the univariate comparator's budget. The default effect thresholds (`warning_effect=0.20`, `blocking_effect=0.40`) are provisional pending calibration on real data.
- **Deterministic by default.** The permutation seed is derived from `(run_id, baseline_id)`, so re-evaluating the same comparison reproduces the same verdicts. Set `MultivariateConfig.seed` to pin it.
- **Score matrices from raw results.** `ScoreMatrix.from_metric_results` pivots `MetricResult` records into a matrix, keeping complete cases only. `MultivariateComparator.compare_metric_results` wraps the whole flow and returns `INCONCLUSIVE` verdicts, with descriptive metric deltas where complete rows exist, instead of raising when data is insufficient. `compare()` on pre-built matrices raises `InsufficientDataError`.
- **Gate integration.** `evaluate_gate()` accepts an optional `multivariate_verdicts` argument and fails on `BLOCKING` from either track (reachable only in `STRICT` mode). Decision-metric selection stays univariate-only. `GateVerdict.multivariate_verdicts` is a new field that defaults to an empty list.
- **CI summary and dashboard.** The GitHub summary renders a structure-track table when multivariate verdicts exist, and omits it otherwise. `DashboardSnapshot.multivariate_verdicts` and `assemble_dashboard_snapshot(multivariate_verdicts=...)` carry the verdicts as informational context; they do not affect `compute_system_health_score`.
- **Statistical primitives** in `nirizan.metrics.stats`, also exported from `nirizan.metrics`: `scale_logvar_statistic`, `scale_logvar_test`, `dependence_max_t_statistic`, `dependence_max_t_test`, `permutation_test`, `permutation_p_value`, `validate_score_matrix`, and `cohens_d`.
- Contracts, architecture, and user manual documentation for the structure track (Phase 6).

### Changed

- **Breaking:** `nirizan.metrics.bootstrap_delta_ci` now resolves to the canonical `nirizan.metrics.stats.bootstrap_delta_ci`. It previously resolved to a 2-tuple wrapper. Differences:
  - It returns `(delta_hat, ci_lower, ci_upper)` instead of `(ci_lower, ci_upper)`.
  - The `confidence` keyword is now `confidence_level`.
  - `n_bootstrap` defaults to `10000` (was `5000`).
  - `seed` defaults to `None` (was `42`), so results vary between calls unless you pass a seed.

```python
  # 0.3.0
  ci_lower, ci_upper = bootstrap_delta_ci(candidate, baseline, confidence=0.95)

  # 0.4.0
  _, ci_lower, ci_upper = bootstrap_delta_ci(
      candidate, baseline, confidence_level=0.95, seed=42
  )

  # or keep the old behavior unchanged
  from nirizan.metrics.statistical_gating import bootstrap_delta_ci
```
- **Breaking:** `evaluate_gate()` raises `ValueError` when its verdicts do not all share one `(run_id, baseline_id)` pair. Such input was previously combined silently.
- `cohens_d` moved to `nirizan.metrics.stats`; `nirizan.regression.comparator.cohens_d` remains as a re-export.
- **License:** NiriZan is now licensed under Apache-2.0 (previously GPL-3.0-or-later). Releases 0.1.0 to 0.3.0 remain available under GPL-3.0-or-later.

### Deprecated

- The 2-tuple `bootstrap_delta_ci` wrappers in `nirizan.metrics.statistical_gating` and `nirizan.gate.verdict`. They still work and delegate to the canonical implementation, but do not yet emit a `DeprecationWarning`. New code should call the canonical function.

### Fixed

- `nirizan.__version__` reported `0.2.0` in the published 0.3.0 release.

## [0.3.0] - 2026-09-01 (PyPI date)

### Added

- Statistical attribution in `AttributionEngine.analyze()` using bootstrap confidence intervals and Mann-Whitney U tests instead of raw mean-difference thresholds.
- Holm-Bonferroni correction across the judge-drift and system-drift hypotheses.
- Explicit small-sample behavior: when either comparison group has fewer than 5 observations, Mann-Whitney U is skipped and attribution relies on bootstrap confidence intervals.
- Configurable statistical parameters for attribution: `alpha`, `confidence_level`, `n_bootstrap`, and optional `seed`.
- Statistical method and evidence details in attribution explanations, including deltas, methods, p-values, and correction status.

### Changed

- **Breaking:** Replaced the `AttributionEngine` `significance_threshold` parameter with `alpha`, reflecting that attribution now uses statistical significance rather than a raw score-difference threshold.
- `AttributionEngine` now distinguishes judge drift using a two-sided statistical test, while system drift specifically tests for a statistically supported decrease in candidate scores.
- Drift decisions now require statistical evidence rather than treating an absolute mean-score delta of `significance_threshold` as sufficient evidence.
- `AttributionEngine` now applies Holm-Bonferroni correction across the judge and system hypotheses before classifying statistically significant drift.
- `AttributionEngine` reuses the centralized statistical helpers in `nirizan.metrics.stats` rather than maintaining attribution-specific statistical implementations.
- `DriftAttribution.NONE` explanations now report the statistical decision methodology instead of describing a raw threshold comparison as "statistically significant."
- Existing `DriftAttribution` states and downstream attribution fields remain unchanged.

### Fixed

- Removed the misleading use of `significance_threshold` as a proxy for statistical significance in `AttributionEngine.analyze()`.
- Prevented attribution from classifying drift solely from the magnitude of a mean-score difference without considering distributional evidence.
- Explicitly handled insufficient sample sizes by avoiding Mann-Whitney U when either comparison group has fewer than 5 observations.
- `INCONCLUSIVE` remains reserved for invalid or unusable score inputs, keeping zero/no-change observations distinguishable from unavailable statistical evidence.

## [0.2.0] - 2026-08-28

PR #35 closes #22 and carries the required `pyproject.toml` version bump per
the Versioning Rule.

### Added

- `DriftAttribution.JOINT_DRIFT` — a verdict for when the judge-side and
  system-side score deltas both cross the significance threshold in the same
  evaluation window. Previously such cases collapsed into `JUDGE_DRIFT`,
  discarding the system-side signal.
- `DriftAttribution.INCONCLUSIVE` — a verdict for when `AttributionEngine.analyze`
  cannot evaluate its input score distributions at all (empty or containing
  non-finite values), instead of forcing an unrelated result out of unusable
  inputs.
- `JudgeReliabilityMetrics.joint_drift_rate` and `JudgeReliabilityMetrics.inconclusive_rate`
  — longitudinal rates for the two new attribution states, each with a `0.0`
  default so existing callers are unaffected.
- Health-score penalty multipliers for `JOINT_DRIFT` (`0.70`) and `INCONCLUSIVE`
  (`0.85`) in `compute_system_health_score`.
- `docs/contracts.md`: full Phase 5 contract documentation for the five-state
  `DriftAttribution` enum, `JudgeReliabilityStatus`, `JudgeReliabilityMetrics`,
  and `DashboardSnapshot`.
- This `CHANGELOG.md`.

### Changed

- **Breaking:** `JudgeReliabilityMetrics.judge_drift_rate` and `system_drift_rate`
  now include `JOINT_DRIFT` verdicts in their counts. `judge_drift_rate` was
  previously "fraction of verdicts where `attribution == JUDGE_DRIFT`"; it is
  now "fraction where `attribution` is `JUDGE_DRIFT` **or** `JOINT_DRIFT`"
  (and correspondingly for `system_drift_rate` with `SYSTEM_DRIFT`). A verdict
  window summarized before and after this change can produce different rates
  for the same underlying data. See the **Phase 5 (post-launch) — Breaking
  Change** section of `docs/contracts.md` for the full migration note;
  historical `JudgeReliabilityMetrics` snapshots remain valid as-is and do not
  need to be recomputed.
- `compute_judge_reliability` now excludes `INCONCLUSIVE` verdicts from
  `mean_judge_score_delta` and `judge_score_delta_std`. `AttributionEngine.analyze`
  reports a `0.0` delta on `INCONCLUSIVE` verdicts as a "not measured"
  placeholder, not an observation of zero drift; including it previously
  biased both statistics toward zero. `INCONCLUSIVE` verdicts are still
  reflected in `verdict_count`, `inconclusive_rate`, and `flagged_verdicts`.
- `docs/architecture.md`: updated the Trust & Attribution Layer description
  from a three-state to a five-state verdict.
- `docs/contracts.md`: clarified that `SYSTEM_DRIFT`/`JOINT_DRIFT` require the
  system-side delta to be a **drop** (`system_score_delta < 0` and past the
  significance threshold), unlike `JUDGE_DRIFT`, which fires on a shift past
  the threshold in either direction.

### Fixed

- **`validate_scores`, `bootstrap_delta_ci`, and `mann_whitney_regression` had
  independently maintained duplicate implementations in
  `regression/thresholds.py`, `metrics/statistical_gating.py`, and (for
  `bootstrap_delta_ci`) `gate/verdict.py`, with different validation
  behavior on the same inputs** (#23): the `regression/thresholds.py`
  copy of `validate_scores` rejected non-1D input while the
  `metrics/statistical_gating.py` copy did not; the `statistical_gating.py`
  copy of `mann_whitney_regression` required at least 5 observations per
  group while the `thresholds.py` copy had no minimum; and the
  `gate/verdict.py` copy of `bootstrap_delta_ci` rejected `n_bootstrap < 1`
  with no score finiteness/range check, while the `statistical_gating.py`
  copy validated score finiteness/range but not `n_bootstrap`. Each copy's
  own tests only exercised its own historical behavior, so the divergence
  went undetected. Fixed by consolidating all four helpers into a single
  authoritative implementation in `src/nirizan/metrics/stats.py`, which
  every caller now delegates to; backwards-compatible aliases
  (`calculate_bootstrap_ci`, `compute_holm_bonferroni`, `compute_mann_whitney_u`)
  are re-exported from `nirizan.metrics` for existing callers, and tests
  (`tests/metrics/test_stats.py`) now exercise the previously-divergent
  edge cases explicitly (#33).

- `compute_judge_reliability` now raises `ValueError` on a verdict window
  where every verdict is `INCONCLUSIVE`, rather than silently computing delta
  statistics with no real observations behind them.
- Removed an unused `compute_system_health_score` import from
  `tests/integration/test_end_to_end.py`.
- Added missing assertions in `tests/trust/test_attribution.py` confirming
  `system_score_delta == 0.0` and `judge_score_delta == 0.0` on `INCONCLUSIVE`
  verdicts, per the contract's placeholder-delta guarantee.

## [0.1.0] - 2026-08-11

Initial public release of NiriZan, an open-source continuous evaluation
infrastructure and Python framework for production AI systems. First
available via PyPI on 2026-08-11; the corresponding GitHub Release was
published on 2026-08-23.

### Added

- Trace instrumentation and collection.
- RAG Triad evaluation: Context Relevance, Groundedness, Answer Relevance.
- LLM-as-Judge evaluation.
- Statistical regression detection.
- Judge reliability and drift detection (three-state: `NONE`, `SYSTEM_DRIFT`,
  `JUDGE_DRIFT`).
- Experiment tracking and baseline management.
- Deployment-aware CI/CD quality gates.
- Typed Pydantic contracts between components (`docs/contracts.md`).
- Security-focused CI/CD and supply-chain controls; PyPI publishing via
  GitHub Actions Trusted Publishing.

[0.5.0]: https://github.com/Red1-Rahman/NiriZan/releases/tag/v0.5.0
[0.1.0]: https://github.com/Red1-Rahman/NiriZan/releases/tag/v0.1.0
