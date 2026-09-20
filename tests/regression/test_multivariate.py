# tests/regression/test_multivariate.py
"""Tests for :mod:`nirizan.regression.multivariate`.

Coverage is organised as a flat set of classes: one per public symbol, plus
a final regression-guard class for the ablation-critical invariants. Every
test that depends on randomness uses a fixed seed or an explicit
``MultivariateConfig.seed`` value so the suite is fully deterministic.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import numpy as np
import pytest
from pydantic import ValidationError

from nirizan.metrics.base import MetricResult
from nirizan.metrics.stats import dependence_max_t_statistic
from nirizan.regression import multivariate as mv
from nirizan.regression.comparator import RegressionSeverity
from nirizan.regression.multivariate import (
    InsufficientDataError,
    MultivariateComparator,
    MultivariateConfig,
    MultivariateMethod,
    MultivariateMode,
    MultivariateVerdict,
    ScoreMatrix,
    apply_mode,
    classify_structure_severity,
    derive_permutation_seed,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_metric_results(
    scores: np.ndarray,
    metric_names: list[str],
    *,
    trace_ids: list[UUID] | None = None,
) -> list[MetricResult]:
    """Flatten an ``(n, p)`` score matrix into a list of ``MetricResult``."""
    n, p = scores.shape
    if p != len(metric_names):
        raise ValueError("metric_names length must match scores.columns")
    if trace_ids is None:
        trace_ids = [uuid4() for _ in range(n)]
    if len(trace_ids) != n:
        raise ValueError("trace_ids length must match scores.rows")

    now = datetime.now(UTC)
    results: list[MetricResult] = []
    for i, tid in enumerate(trace_ids):
        for j, name in enumerate(metric_names):
            results.append(
                MetricResult(
                    metric_name=name,
                    trace_id=tid,
                    score=float(scores[i, j]),
                    computed_at=now,
                )
            )
    return results


def _build_matrix(
    scores: np.ndarray,
    metric_names: list[str],
    *,
    min_complete_rows: int = 2,
) -> ScoreMatrix:
    return ScoreMatrix.from_metric_results(
        _make_metric_results(scores, metric_names),
        metric_names=metric_names,
        min_complete_rows=min_complete_rows,
    )


def _fast_config(**overrides: object) -> MultivariateConfig:
    """A config with a small permutation count for fast tests.

    ``base`` is annotated as ``dict[str, object]`` so ``base.update(overrides)``
    type-checks. Without the annotation, the dict literal is inferred as
    ``dict[str, int]`` and the ``update`` call rejects the wider-typed
    ``overrides`` mapping.
    """
    base: dict[str, object] = {"n_permutations": 199, "min_complete_rows": 10}
    base.update(overrides)
    return MultivariateConfig(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# MultivariateMode
# ---------------------------------------------------------------------------


class TestMultivariateMode:
    def test_values(self) -> None:
        assert MultivariateMode.BALANCED.value == "balanced"
        assert MultivariateMode.STRICT.value == "strict"

    def test_is_str_enum(self) -> None:
        # str subclass is what lets these round-trip through JSON cleanly.
        assert isinstance(MultivariateMode.BALANCED, str)


# ---------------------------------------------------------------------------
# MultivariateMethod
# ---------------------------------------------------------------------------


class TestMultivariateMethod:
    def test_values(self) -> None:
        assert MultivariateMethod.SCALE.value == "scale"
        assert MultivariateMethod.DEPENDENCE.value == "dependence"

    def test_is_str_enum(self) -> None:
        assert isinstance(MultivariateMethod.SCALE, str)


# ---------------------------------------------------------------------------
# MultivariateConfig
# ---------------------------------------------------------------------------


class TestMultivariateConfig:
    def test_defaults(self) -> None:
        config = MultivariateConfig()
        assert config.mode == MultivariateMode.BALANCED
        assert config.structure_alpha == 0.05
        assert config.n_permutations == 999
        assert config.min_complete_rows == 20
        assert config.warning_effect == 0.20
        assert config.blocking_effect == 0.40
        assert config.seed is None

    def test_frozen(self) -> None:
        config = MultivariateConfig()
        with pytest.raises(ValidationError):
            config.mode = MultivariateMode.STRICT  # type: ignore[misc]

    def test_alpha_bounds(self) -> None:
        with pytest.raises(ValidationError):
            MultivariateConfig(structure_alpha=0.0)
        with pytest.raises(ValidationError):
            MultivariateConfig(structure_alpha=1.0)

    def test_n_permutations_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            MultivariateConfig(n_permutations=100)

    def test_min_complete_rows_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            MultivariateConfig(min_complete_rows=5)

    def test_warning_effect_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            MultivariateConfig(warning_effect=0.0)

    def test_blocking_effect_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            MultivariateConfig(blocking_effect=-0.1)

    def test_effect_thresholds_must_be_ordered(self) -> None:
        with pytest.raises(ValidationError, match="greater than warning_effect"):
            MultivariateConfig(warning_effect=0.4, blocking_effect=0.4)
        with pytest.raises(ValidationError, match="greater than warning_effect"):
            MultivariateConfig(warning_effect=0.4, blocking_effect=0.2)


# ---------------------------------------------------------------------------
# ScoreMatrix.from_metric_results
# ---------------------------------------------------------------------------


class TestScoreMatrixFromMetricResults:
    def test_complete_input_preserves_shape(self) -> None:
        scores = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]])
        results = _make_metric_results(scores, ["m1", "m2", "m3"])
        matrix = ScoreMatrix.from_metric_results(
            results, metric_names=["m1", "m2", "m3"], min_complete_rows=3
        )
        assert matrix.n_rows == 3
        assert matrix.n_metrics == 3
        assert matrix.dropped_rows == 0
        assert matrix.metric_names == ("m1", "m2", "m3")
        # Values retained, modulo row reordering by trace_id (which is
        # random here). The multiset of values per column must match.
        np.testing.assert_array_almost_equal(
            np.sort(matrix.values, axis=0), np.sort(scores, axis=0)
        )

    def test_drops_trace_missing_a_metric(self) -> None:
        now = datetime.now(UTC)
        good = uuid4()
        bad = uuid4()
        results = [
            MetricResult(metric_name="m1", trace_id=good, score=0.5, computed_at=now),
            MetricResult(metric_name="m2", trace_id=good, score=0.6, computed_at=now),
            MetricResult(metric_name="m1", trace_id=bad, score=0.5, computed_at=now),
            # bad is missing m2
        ]
        matrix = ScoreMatrix.from_metric_results(
            results, metric_names=["m1", "m2"], min_complete_rows=1
        )
        assert matrix.n_rows == 1
        assert matrix.dropped_rows == 1

    def test_drops_trace_with_non_finite_score(self) -> None:
        now = datetime.now(UTC)
        trace_id = uuid4()
        # Bypass pydantic validation to simulate a malformed upstream record.
        malformed = MetricResult.model_construct(
            metric_name="m1",
            trace_id=trace_id,
            score=float("nan"),
            confidence=None,
            details={},
            computed_at=now,
        )
        with pytest.raises(InsufficientDataError):
            ScoreMatrix.from_metric_results([malformed], metric_names=["m1"], min_complete_rows=1)

    def test_drops_trace_with_out_of_bounds_score(self) -> None:
        now = datetime.now(UTC)
        trace_id = uuid4()
        malformed = MetricResult.model_construct(
            metric_name="m1",
            trace_id=trace_id,
            score=1.5,
            confidence=None,
            details={},
            computed_at=now,
        )
        with pytest.raises(InsufficientDataError):
            ScoreMatrix.from_metric_results([malformed], metric_names=["m1"], min_complete_rows=1)

    def test_raises_when_below_min_complete_rows(self) -> None:
        scores = np.array([[0.1, 0.2]])
        results = _make_metric_results(scores, ["m1", "m2"])
        with pytest.raises(InsufficientDataError, match="complete row"):
            ScoreMatrix.from_metric_results(results, metric_names=["m1", "m2"], min_complete_rows=5)

    def test_empty_metric_names_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one metric"):
            ScoreMatrix.from_metric_results([], metric_names=[], min_complete_rows=1)

    def test_duplicate_metric_names_raises(self) -> None:
        with pytest.raises(ValueError, match="unique"):
            ScoreMatrix.from_metric_results([], metric_names=["m1", "m1"], min_complete_rows=1)

    def test_invalid_min_complete_rows_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            ScoreMatrix.from_metric_results([], metric_names=["m1"], min_complete_rows=0)

    def test_unrequested_metrics_are_ignored(self) -> None:
        now = datetime.now(UTC)
        trace_id = uuid4()
        results = [
            MetricResult(metric_name="m1", trace_id=trace_id, score=0.5, computed_at=now),
            MetricResult(metric_name="m2", trace_id=trace_id, score=0.6, computed_at=now),
            MetricResult(metric_name="other", trace_id=trace_id, score=0.9, computed_at=now),
        ]
        matrix = ScoreMatrix.from_metric_results(
            results, metric_names=["m1", "m2"], min_complete_rows=1
        )
        assert matrix.n_metrics == 2
        assert matrix.metric_names == ("m1", "m2")

    def test_row_order_is_deterministic_by_trace_id(self) -> None:
        scores = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
        trace_ids = [UUID(int=i) for i in (3, 1, 2)]
        results = _make_metric_results(scores, ["m1", "m2"], trace_ids=trace_ids)
        matrix = ScoreMatrix.from_metric_results(
            results, metric_names=["m1", "m2"], min_complete_rows=3
        )
        # Sorted by trace_id: 1, 2, 3 -> original rows 1, 2, 0 -> first-column
        # values 0.3, 0.5, 0.1.
        np.testing.assert_array_almost_equal(matrix.values[:, 0], np.array([0.3, 0.5, 0.1]))

    def test_duplicate_trace_metric_record_drops_ambiguous_trace(self) -> None:
        """Conflicting duplicates must never be resolved by input order."""
        now = datetime.now(UTC)
        duplicate_trace = UUID(int=1)
        good_trace = UUID(int=2)
        results = [
            MetricResult(metric_name="m1", trace_id=duplicate_trace, score=0.2, computed_at=now),
            MetricResult(metric_name="m1", trace_id=duplicate_trace, score=0.9, computed_at=now),
            MetricResult(metric_name="m1", trace_id=good_trace, score=0.7, computed_at=now),
        ]

        matrix = ScoreMatrix.from_metric_results(results, metric_names=["m1"], min_complete_rows=1)

        assert matrix.dropped_rows == 1
        np.testing.assert_array_equal(matrix.values, np.array([[0.7]]))

    def test_duplicate_trace_metric_records_are_input_order_independent(self) -> None:
        """Reordering conflicting duplicates must not change the matrix."""
        now = datetime.now(UTC)
        duplicate_trace = UUID(int=1)
        good_trace = UUID(int=2)
        first = MetricResult(metric_name="m1", trace_id=duplicate_trace, score=0.2, computed_at=now)
        second = MetricResult(
            metric_name="m1", trace_id=duplicate_trace, score=0.9, computed_at=now
        )
        good = MetricResult(metric_name="m1", trace_id=good_trace, score=0.7, computed_at=now)

        a = ScoreMatrix.from_metric_results(
            [first, second, good], metric_names=["m1"], min_complete_rows=1
        )
        b = ScoreMatrix.from_metric_results(
            [second, first, good], metric_names=["m1"], min_complete_rows=1
        )

        assert a.dropped_rows == b.dropped_rows == 1
        np.testing.assert_array_equal(a.values, b.values)


# ---------------------------------------------------------------------------
# ScoreMatrix direct-construction contract
# ---------------------------------------------------------------------------


class TestScoreMatrixDirectConstruction:
    def test_rejects_one_dimensional_values(self) -> None:
        with pytest.raises(ValidationError, match="two-dimensional"):
            ScoreMatrix(values=np.array([0.1, 0.2]), metric_names=("m1",))

    def test_rejects_zero_metric_columns(self) -> None:
        with pytest.raises(ValidationError, match="at least 1"):
            ScoreMatrix(values=np.empty((3, 0)), metric_names=("m1",))

    def test_rejects_non_finite_values(self) -> None:
        with pytest.raises(ValidationError, match="non-finite"):
            ScoreMatrix(
                values=np.array([[0.1, np.nan]]),
                metric_names=("m1", "m2"),
            )

    def test_rejects_out_of_range_values(self) -> None:
        with pytest.raises(ValidationError, match=r"normalized to \[0, 1\]"):
            ScoreMatrix(
                values=np.array([[0.1, 1.5]]),
                metric_names=("m1", "m2"),
            )

    def test_rejects_duplicate_metric_names(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            ScoreMatrix(
                values=np.array([[0.1, 0.2]]),
                metric_names=("m1", "m1"),
            )

    def test_rejects_metric_name_column_count_mismatch(self) -> None:
        with pytest.raises(ValidationError, match=r"values.shape\[1\]"):
            ScoreMatrix(
                values=np.array([[0.1, 0.2]]),
                metric_names=("m1",),
            )

    def test_accepts_valid_direct_matrix(self) -> None:
        matrix = ScoreMatrix(
            values=np.array([[0.1, 0.2], [0.3, 0.4]]),
            metric_names=("m1", "m2"),
        )
        assert matrix.n_rows == 2
        assert matrix.n_metrics == 2


# ---------------------------------------------------------------------------
# MultivariateVerdict
# ---------------------------------------------------------------------------


class TestMultivariateVerdict:
    def _verdict(self, **overrides: object) -> MultivariateVerdict:
        base: dict[str, object] = {
            "method": MultivariateMethod.SCALE,
            "severity": RegressionSeverity.NONE,
            "p_value": 0.5,
            "statistic": 0.0,
            "effect_size": 0.0,
            "baseline_id": uuid4(),
            "run_id": uuid4(),
            "explanation": "ok",
        }
        base.update(overrides)
        return MultivariateVerdict(**base)  # type: ignore[arg-type]

    def test_defaults(self) -> None:
        verdict = self._verdict()
        assert verdict.metric_deltas == {}
        assert verdict.inconclusive is False

    def test_p_value_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            self._verdict(p_value=1.5)

    def test_p_value_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            self._verdict(p_value=-0.1)

    def test_effect_size_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            self._verdict(effect_size=-0.1)

    def test_frozen(self) -> None:
        verdict = self._verdict()
        with pytest.raises(ValidationError):
            verdict.p_value = 0.1  # type: ignore[misc]

    def test_model_dump_round_trips(self) -> None:
        verdict = self._verdict(metric_deltas={"m1": -0.05})
        dumped = verdict.model_dump(mode="json")
        assert dumped["method"] == "scale"
        assert dumped["severity"] == "none"
        assert dumped["metric_deltas"] == {"m1": -0.05}


# ---------------------------------------------------------------------------
# classify_structure_severity
# ---------------------------------------------------------------------------


class TestClassifyStructureSeverity:
    def test_non_significant_is_none(self) -> None:
        assert (
            classify_structure_severity(
                significant=False,
                effect_size=1.0,
                warning_effect=0.2,
                blocking_effect=0.4,
            )
            == RegressionSeverity.NONE
        )

    def test_small_effect_below_warning_is_none(self) -> None:
        assert (
            classify_structure_severity(
                significant=True,
                effect_size=0.1,
                warning_effect=0.2,
                blocking_effect=0.4,
            )
            == RegressionSeverity.NONE
        )

    def test_effect_at_warning_boundary_is_warning(self) -> None:
        assert (
            classify_structure_severity(
                significant=True,
                effect_size=0.2,
                warning_effect=0.2,
                blocking_effect=0.4,
            )
            == RegressionSeverity.WARNING
        )

    def test_effect_at_blocking_boundary_is_blocking(self) -> None:
        assert (
            classify_structure_severity(
                significant=True,
                effect_size=0.4,
                warning_effect=0.2,
                blocking_effect=0.4,
            )
            == RegressionSeverity.BLOCKING
        )

    def test_effect_above_blocking_is_blocking(self) -> None:
        assert (
            classify_structure_severity(
                significant=True,
                effect_size=0.9,
                warning_effect=0.2,
                blocking_effect=0.4,
            )
            == RegressionSeverity.BLOCKING
        )

    def test_non_positive_warning_effect_raises(self) -> None:
        with pytest.raises(ValueError, match="warning_effect must be positive"):
            classify_structure_severity(
                significant=True,
                effect_size=0.3,
                warning_effect=0.0,
                blocking_effect=0.4,
            )

    def test_blocking_less_than_warning_raises(self) -> None:
        with pytest.raises(ValueError, match="blocking_effect must be greater"):
            classify_structure_severity(
                significant=True,
                effect_size=0.3,
                warning_effect=0.4,
                blocking_effect=0.2,
            )

    def test_negative_effect_size_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            classify_structure_severity(
                significant=True,
                effect_size=-0.1,
                warning_effect=0.2,
                blocking_effect=0.4,
            )


# ---------------------------------------------------------------------------
# apply_mode
# ---------------------------------------------------------------------------


class TestApplyMode:
    def test_balanced_caps_blocking_to_warning(self) -> None:
        assert (
            apply_mode(RegressionSeverity.BLOCKING, MultivariateMode.BALANCED)
            == RegressionSeverity.WARNING
        )

    def test_balanced_leaves_warning_alone(self) -> None:
        assert (
            apply_mode(RegressionSeverity.WARNING, MultivariateMode.BALANCED)
            == RegressionSeverity.WARNING
        )

    def test_balanced_leaves_none_alone(self) -> None:
        assert (
            apply_mode(RegressionSeverity.NONE, MultivariateMode.BALANCED)
            == RegressionSeverity.NONE
        )

    def test_strict_passes_blocking_through(self) -> None:
        assert (
            apply_mode(RegressionSeverity.BLOCKING, MultivariateMode.STRICT)
            == RegressionSeverity.BLOCKING
        )

    def test_strict_passes_warning_through(self) -> None:
        assert (
            apply_mode(RegressionSeverity.WARNING, MultivariateMode.STRICT)
            == RegressionSeverity.WARNING
        )

    def test_balanced_never_produces_blocking(self) -> None:
        """The whole point of BALANCED mode: no severity can be BLOCKING."""
        # Iterate over list(RegressionSeverity) rather than the enum class
        # directly: RegressionSeverity is iterable at runtime via its
        # EnumMeta, but some static analyzers (e.g. CodeQL) don't model
        # that protocol and flag direct class iteration as a potential
        # non-iterable-in-for-loop defect. list(...) gives the checker an
        # unambiguous, concretely-iterable object with no behavior change.
        for severity in list(RegressionSeverity):
            assert apply_mode(severity, MultivariateMode.BALANCED) != RegressionSeverity.BLOCKING


# ---------------------------------------------------------------------------
# derive_permutation_seed
# ---------------------------------------------------------------------------


class TestDerivePermutationSeed:
    def test_deterministic_for_same_ids(self) -> None:
        rid, bid = uuid4(), uuid4()
        assert derive_permutation_seed(run_id=rid, baseline_id=bid) == derive_permutation_seed(
            run_id=rid, baseline_id=bid
        )

    def test_different_run_ids_give_different_seeds(self) -> None:
        bid = uuid4()
        seeds = {derive_permutation_seed(run_id=uuid4(), baseline_id=bid) for _ in range(10)}
        assert len(seeds) == 10

    def test_different_baseline_ids_give_different_seeds(self) -> None:
        rid = uuid4()
        seeds = {derive_permutation_seed(run_id=rid, baseline_id=uuid4()) for _ in range(10)}
        assert len(seeds) == 10

    def test_override_bypasses_derivation(self) -> None:
        assert derive_permutation_seed(run_id=uuid4(), baseline_id=uuid4(), override=123) == 123

    def test_override_zero_is_honored(self) -> None:
        # Guard against a `if override:` bug that would skip the zero seed.
        assert derive_permutation_seed(run_id=uuid4(), baseline_id=uuid4(), override=0) == 0


# ---------------------------------------------------------------------------
# MultivariateComparator: construction
# ---------------------------------------------------------------------------


class TestMultivariateComparatorInit:
    def test_default_config(self) -> None:
        comparator = MultivariateComparator()
        assert comparator.config.mode == MultivariateMode.BALANCED

    def test_accepts_custom_config(self) -> None:
        config = MultivariateConfig(mode=MultivariateMode.STRICT, seed=123)
        comparator = MultivariateComparator(config=config)
        assert comparator.config is config


# ---------------------------------------------------------------------------
# MultivariateComparator.compare
# ---------------------------------------------------------------------------


class TestMultivariateComparatorCompare:
    def test_returns_two_verdicts_one_per_method(self) -> None:
        rng = np.random.default_rng(0)
        base = rng.uniform(0.3, 0.7, size=(30, 3))
        cand = rng.uniform(0.3, 0.7, size=(30, 3))
        baseline = _build_matrix(base, ["m1", "m2", "m3"], min_complete_rows=10)
        candidate = _build_matrix(cand, ["m1", "m2", "m3"], min_complete_rows=10)

        verdicts = MultivariateComparator(config=_fast_config(seed=1)).compare(
            candidate=candidate,
            baseline=baseline,
            baseline_id=uuid4(),
            run_id=uuid4(),
        )
        assert len(verdicts) == 2
        assert {v.method for v in verdicts} == {
            MultivariateMethod.SCALE,
            MultivariateMethod.DEPENDENCE,
        }
        for v in verdicts:
            assert isinstance(v, MultivariateVerdict)
            assert v.inconclusive is False
            assert 0.0 <= v.p_value <= 1.0
            assert v.effect_size >= 0.0

    def test_identical_inputs_give_none(self) -> None:
        rng = np.random.default_rng(1)
        scores = rng.uniform(0.3, 0.7, size=(40, 3))
        matrix = _build_matrix(scores, ["m1", "m2", "m3"], min_complete_rows=10)
        verdicts = MultivariateComparator(config=_fast_config(seed=1)).compare(
            candidate=matrix,
            baseline=matrix,
            baseline_id=uuid4(),
            run_id=uuid4(),
        )
        assert all(v.severity == RegressionSeverity.NONE for v in verdicts)

    def test_balanced_caps_blocking_to_warning_on_variance_change(self) -> None:
        """A strong variance change should be BLOCKING-worthy in STRICT
        mode but capped at WARNING in BALANCED mode.
        """
        rng = np.random.default_rng(2)
        base = rng.uniform(0.3, 0.7, size=(80, 3))
        center = base.mean(axis=0)
        inflated = center + (base - center) * 1.5
        assert inflated.min() >= 0.0 and inflated.max() <= 1.0

        baseline = _build_matrix(base, ["m1", "m2", "m3"], min_complete_rows=20)
        candidate = _build_matrix(inflated, ["m1", "m2", "m3"], min_complete_rows=20)

        common: dict[str, object] = {
            "n_permutations": 199,
            "min_complete_rows": 20,
            "seed": 1,
        }
        balanced = MultivariateComparator(
            config=MultivariateConfig(
                mode=MultivariateMode.BALANCED,
                **common,  # type: ignore[arg-type]
            )
        ).compare(
            candidate=candidate,
            baseline=baseline,
            baseline_id=uuid4(),
            run_id=uuid4(),
        )
        strict = MultivariateComparator(
            config=MultivariateConfig(
                mode=MultivariateMode.STRICT,
                **common,  # type: ignore[arg-type]
            )
        ).compare(
            candidate=candidate,
            baseline=baseline,
            baseline_id=uuid4(),
            run_id=uuid4(),
        )

        balanced_scale = next(v for v in balanced if v.method == MultivariateMethod.SCALE)
        strict_scale = next(v for v in strict if v.method == MultivariateMethod.SCALE)
        assert strict_scale.severity == RegressionSeverity.BLOCKING
        assert balanced_scale.severity == RegressionSeverity.WARNING

    def test_deterministic_across_instances(self) -> None:
        """Same run_id and baseline_id, same data -> same p-values."""
        rng = np.random.default_rng(3)
        base = rng.uniform(0.3, 0.7, size=(40, 3))
        cand = rng.uniform(0.3, 0.7, size=(40, 3))
        baseline = _build_matrix(base, ["m1", "m2", "m3"], min_complete_rows=10)
        candidate = _build_matrix(cand, ["m1", "m2", "m3"], min_complete_rows=10)

        config = _fast_config()
        baseline_id, run_id = uuid4(), uuid4()

        a = MultivariateComparator(config=config).compare(
            candidate=candidate,
            baseline=baseline,
            baseline_id=baseline_id,
            run_id=run_id,
        )
        b = MultivariateComparator(config=config).compare(
            candidate=candidate,
            baseline=baseline,
            baseline_id=baseline_id,
            run_id=run_id,
        )
        for va, vb in zip(a, b, strict=True):
            assert va.p_value == vb.p_value
            assert va.statistic == vb.statistic
            assert va.severity == vb.severity

    def test_single_metric_skips_dependence(self) -> None:
        rng = np.random.default_rng(5)
        base = rng.uniform(0.3, 0.7, size=(40, 1))
        cand = rng.uniform(0.3, 0.7, size=(40, 1))
        baseline = _build_matrix(base, ["m1"], min_complete_rows=10)
        candidate = _build_matrix(cand, ["m1"], min_complete_rows=10)

        verdicts = MultivariateComparator(config=_fast_config(seed=1)).compare(
            candidate=candidate,
            baseline=baseline,
            baseline_id=uuid4(),
            run_id=uuid4(),
        )
        dep = next(v for v in verdicts if v.method == MultivariateMethod.DEPENDENCE)
        assert dep.p_value == 1.0
        assert dep.statistic == 0.0
        assert dep.severity == RegressionSeverity.NONE
        assert "skipped" in dep.explanation

    def test_single_metric_boundary_alpha_yields_significant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicitly assert scale_p == config.structure_alpha yields scale_significant = True in single-metric mode."""
        config = _fast_config(structure_alpha=0.05, warning_effect=0.20)
        comparator = MultivariateComparator(config=config)

        # Mock scale_logvar_test to return scale_p exactly equal to structure_alpha (0.05)
        # and a statistic yielding an effect size above warning_effect (sqrt(0.09 / 1) = 0.30 >= 0.20).
        def mock_scale_logvar_test(
            x: np.ndarray, y: np.ndarray, n_permutations: int = 199, seed: int | None = None
        ) -> tuple[float, None, float]:
            return 0.09, None, 0.05

        monkeypatch.setattr(
            "nirizan.regression.multivariate.scale_logvar_test", mock_scale_logvar_test
        )

        base = np.zeros((20, 1))
        cand = np.zeros((20, 1))
        baseline = _build_matrix(base, ["m1"], min_complete_rows=10)
        candidate = _build_matrix(cand, ["m1"], min_complete_rows=10)

        verdicts = comparator.compare(
            candidate=candidate,
            baseline=baseline,
            baseline_id=uuid4(),
            run_id=uuid4(),
        )
        scale = next(v for v in verdicts if v.method == MultivariateMethod.SCALE)
        assert scale.p_value == 0.05
        assert "significant_after_holm=True" in scale.explanation
        assert scale.severity == RegressionSeverity.WARNING

    def test_mismatched_metric_names_raises(self) -> None:
        rng = np.random.default_rng(6)
        baseline = _build_matrix(
            rng.uniform(0.3, 0.7, size=(30, 2)), ["m1", "m2"], min_complete_rows=10
        )
        candidate = _build_matrix(
            rng.uniform(0.3, 0.7, size=(30, 2)), ["m1", "m3"], min_complete_rows=10
        )
        with pytest.raises(ValueError, match="do not match"):
            MultivariateComparator(config=_fast_config()).compare(
                candidate=candidate,
                baseline=baseline,
                baseline_id=uuid4(),
                run_id=uuid4(),
            )

    def test_insufficient_candidate_rows_raises(self) -> None:
        rng = np.random.default_rng(7)
        big = _build_matrix(rng.uniform(0.3, 0.7, size=(30, 2)), ["m1", "m2"], min_complete_rows=10)
        small = _build_matrix(
            rng.uniform(0.3, 0.7, size=(15, 2)), ["m1", "m2"], min_complete_rows=10
        )
        with pytest.raises(InsufficientDataError, match="Candidate has"):
            MultivariateComparator(config=_fast_config(min_complete_rows=20)).compare(
                candidate=small,
                baseline=big,
                baseline_id=uuid4(),
                run_id=uuid4(),
            )

    def test_metric_deltas_populated_on_both_verdicts(self) -> None:
        rng = np.random.default_rng(8)
        base = rng.uniform(0.4, 0.6, size=(30, 2))
        cand = np.clip(base - 0.1, 0.0, 1.0)
        baseline = _build_matrix(base, ["m1", "m2"], min_complete_rows=10)
        candidate = _build_matrix(cand, ["m1", "m2"], min_complete_rows=10)

        verdicts = MultivariateComparator(config=_fast_config(seed=1)).compare(
            candidate=candidate,
            baseline=baseline,
            baseline_id=uuid4(),
            run_id=uuid4(),
        )
        for v in verdicts:
            assert set(v.metric_deltas.keys()) == {"m1", "m2"}
            for d in v.metric_deltas.values():
                assert d < 0.0


# ---------------------------------------------------------------------------
# MultivariateComparator.compare_metric_results
# ---------------------------------------------------------------------------


class TestCompareMetricResults:
    def test_happy_path(self) -> None:
        rng = np.random.default_rng(8)
        base = rng.uniform(0.3, 0.7, size=(30, 2))
        cand = rng.uniform(0.3, 0.7, size=(30, 2))
        baseline_results = _make_metric_results(base, ["m1", "m2"])
        candidate_results = _make_metric_results(cand, ["m1", "m2"])

        verdicts = MultivariateComparator(config=_fast_config(seed=1)).compare_metric_results(
            candidate_results=candidate_results,
            baseline_results=baseline_results,
            metric_names=["m1", "m2"],
            baseline_id=uuid4(),
            run_id=uuid4(),
        )
        assert len(verdicts) == 2
        assert all(v.inconclusive is False for v in verdicts)

    def test_insufficient_data_returns_inconclusive(self, caplog: pytest.LogCaptureFixture) -> None:
        rng = np.random.default_rng(9)
        # Two complete rows is below min_complete_rows=10.
        base = rng.uniform(0.3, 0.7, size=(2, 2))
        cand = rng.uniform(0.3, 0.7, size=(2, 2))
        baseline_results = _make_metric_results(base, ["m1", "m2"])
        candidate_results = _make_metric_results(cand, ["m1", "m2"])

        with caplog.at_level(logging.WARNING):
            verdicts = MultivariateComparator(config=_fast_config()).compare_metric_results(
                candidate_results=candidate_results,
                baseline_results=baseline_results,
                metric_names=["m1", "m2"],
                baseline_id=uuid4(),
                run_id=uuid4(),
            )
        assert len(verdicts) == 2
        assert all(v.inconclusive is True for v in verdicts)
        assert all(v.severity == RegressionSeverity.NONE for v in verdicts)
        assert all(v.p_value == 1.0 for v in verdicts)
        assert all("INCONCLUSIVE" in v.explanation for v in verdicts)
        assert "inconclusive" in caplog.text.lower()

    def test_inconclusive_preserves_complete_case_metric_deltas(self) -> None:
        """Descriptive deltas survive even when the sample is too small to test."""
        base = np.array([[0.6, 0.7], [0.5, 0.6]])
        cand = np.array([[0.4, 0.5], [0.3, 0.4]])
        verdicts = MultivariateComparator(config=_fast_config()).compare_metric_results(
            candidate_results=_make_metric_results(cand, ["m1", "m2"]),
            baseline_results=_make_metric_results(base, ["m1", "m2"]),
            metric_names=["m1", "m2"],
            baseline_id=uuid4(),
            run_id=uuid4(),
        )

        for verdict in verdicts:
            assert verdict.inconclusive is True
            assert verdict.metric_deltas == {"m1": pytest.approx(-0.2), "m2": pytest.approx(-0.2)}

    def test_inconclusive_omits_deltas_without_complete_rows(self) -> None:
        """Partial rows cannot be used as complete-case descriptive data."""
        now = datetime.now(UTC)
        trace_id = uuid4()
        candidate_results = [
            MetricResult(metric_name="m1", trace_id=trace_id, score=0.4, computed_at=now),
        ]
        baseline_results = [
            MetricResult(metric_name="m1", trace_id=trace_id, score=0.6, computed_at=now),
            MetricResult(metric_name="m2", trace_id=trace_id, score=0.7, computed_at=now),
        ]
        verdicts = MultivariateComparator(config=_fast_config()).compare_metric_results(
            candidate_results=candidate_results,
            baseline_results=baseline_results,
            metric_names=["m1", "m2"],
            baseline_id=uuid4(),
            run_id=uuid4(),
        )

        assert all(verdict.inconclusive for verdict in verdicts)
        assert all(verdict.metric_deltas == {} for verdict in verdicts)

    def test_inconclusive_deltas_exclude_malformed_complete_cases(self) -> None:
        """Non-finite rows are dropped before descriptive means are computed."""
        now = datetime.now(UTC)
        good_trace, bad_trace, baseline_trace = uuid4(), uuid4(), uuid4()
        candidate_results = [
            MetricResult(metric_name="m1", trace_id=good_trace, score=0.4, computed_at=now),
            MetricResult(metric_name="m2", trace_id=good_trace, score=0.5, computed_at=now),
            MetricResult.model_construct(
                metric_name="m1",
                trace_id=bad_trace,
                score=float("nan"),
                confidence=None,
                details={},
                computed_at=now,
            ),
            MetricResult(metric_name="m2", trace_id=bad_trace, score=0.1, computed_at=now),
        ]
        baseline_results = [
            MetricResult(metric_name="m1", trace_id=baseline_trace, score=0.6, computed_at=now),
            MetricResult(metric_name="m2", trace_id=baseline_trace, score=0.7, computed_at=now),
        ]
        verdicts = MultivariateComparator(config=_fast_config()).compare_metric_results(
            candidate_results=candidate_results,
            baseline_results=baseline_results,
            metric_names=["m1", "m2"],
            baseline_id=uuid4(),
            run_id=uuid4(),
        )

        assert all(verdict.inconclusive for verdict in verdicts)
        for verdict in verdicts:
            assert verdict.metric_deltas == {
                "m1": pytest.approx(-0.2),
                "m2": pytest.approx(-0.2),
            }


# ---------------------------------------------------------------------------
# Regression guards (ablation-critical invariants)
# ---------------------------------------------------------------------------


class TestRegressionGuards:
    def test_balanced_mode_never_blocks_via_apply_mode(self) -> None:
        """If a future refactor removes the BALANCED cap, this fails."""
        # See the identical comment in TestApplyMode.test_balanced_never_
        # produces_blocking: list(...) avoids a CodeQL false positive on
        # direct enum-class iteration without changing behavior.
        for severity in list(RegressionSeverity):
            assert apply_mode(severity, MultivariateMode.BALANCED) != RegressionSeverity.BLOCKING

    def test_balanced_comparison_never_emits_blocking(self) -> None:
        """Same invariant, exercised end-to-end through the comparator."""
        rng = np.random.default_rng(11)
        base = rng.uniform(0.3, 0.7, size=(80, 3))
        center = base.mean(axis=0)
        # A deliberately huge variance change, to force a BLOCKING-worthy
        # effect if the cap were ever removed.
        inflated = center + (base - center) * 1.8
        inflated = np.clip(inflated, 0.0, 1.0)
        baseline = _build_matrix(base, ["m1", "m2", "m3"], min_complete_rows=20)
        candidate = _build_matrix(inflated, ["m1", "m2", "m3"], min_complete_rows=20)

        verdicts = MultivariateComparator(
            config=_fast_config(mode=MultivariateMode.BALANCED, min_complete_rows=20, seed=1)
        ).compare(
            candidate=candidate,
            baseline=baseline,
            baseline_id=uuid4(),
            run_id=uuid4(),
        )
        assert all(v.severity != RegressionSeverity.BLOCKING for v in verdicts)

    def test_dependence_statistic_ignores_rank_preserving_variance_change(self) -> None:
        """Ablation-critical: the dependence test must not fire on a pure
        variance change that preserves per-column rank order. This is what
        justified using rank correlation over covariance Frobenius.
        """
        rng = np.random.default_rng(12)
        base = rng.uniform(0.3, 0.7, size=(50, 3))
        center = base.mean(axis=0)
        inflated = center + (base - center) * 1.4
        stat = dependence_max_t_statistic(base, inflated)
        assert stat == pytest.approx(0.0, abs=1e-12)

    def test_module_all_exports_complete(self) -> None:
        expected = {
            "InsufficientDataError",
            "MultivariateComparator",
            "MultivariateConfig",
            "MultivariateMethod",
            "MultivariateMode",
            "MultivariateVerdict",
            "ScoreMatrix",
            "apply_mode",
            "classify_structure_severity",
            "derive_permutation_seed",
        }
        missing = expected - set(mv.__all__)
        assert not missing, f"Missing from multivariate.__all__: {sorted(missing)}"
