# src/nirizan/regression/multivariate.py
"""Multivariate structure-track regression detection.

The structure track runs two permutation-calibrated tests against a
baseline/candidate pair of row-aligned score matrices:

* ``scale``: variance-only change, using ``metrics.stats.scale_logvar_test``.
* ``dependence``: rank-correlation change, using
  ``metrics.stats.dependence_max_t_test``.

Both are undirected (they fire on either an increase or a decrease of the
corresponding magnitude), so the default ``BALANCED`` mode caps their
authority at ``WARNING``. A structure change means *something* changed, not
that the system got worse, and the deployment gate's ``passed`` field must
not flip on a directionless signal. The ablation study that motivated this
module showed that any second block-capable track inflates the gate's
worst-configuration false-alarm rate above the nominal 5% unless its alpha
is carved out of the same budget the univariate comparator spends;
``BALANCED`` sidesteps that by capping the track's authority, and ``STRICT``
is an explicit opt-in for callers who have done the alpha-spending math.

The two tests are combined with Holm-Bonferroni at the structure track's
alpha. Below ``min_complete_rows``, or with a zero-variance metric column,
the comparator emits an INCONCLUSIVE verdict rather than a silent pass,
mirroring the ``AttributionVerdict.INCONCLUSIVE`` contract in
``trust/attribution.py``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from nirizan._logging import get_logger
from nirizan.metrics.base import MetricResult
from nirizan.metrics.stats import (
    dependence_max_t_test,
    holm_bonferroni,
    scale_logvar_test,
    validate_score_matrix,
)
from nirizan.regression.comparator import RegressionSeverity

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MultivariateMode(str, Enum):
    """Controls what the structure track may do, not which test runs.

    ``BALANCED`` may raise WARNING only; ``GateVerdict.passed`` is never
    affected. ``STRICT`` may raise BLOCKING, and the caller is responsible
    for carving the structure track's alpha out of the same budget the
    univariate comparator spends.
    """

    BALANCED = "balanced"
    STRICT = "strict"


class MultivariateMethod(str, Enum):
    """Which structure test produced a verdict."""

    SCALE = "scale"
    DEPENDENCE = "dependence"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class MultivariateConfig(BaseModel):
    """Configuration for the structure track. Frozen and strict.

    ``warning_effect`` and ``blocking_effect`` are placeholder defaults
    pending calibration against real NiriZan data; they will very likely
    need adjusting once the structure track runs against production
    distributions. Both are non-negative magnitudes because structure
    effects are undirected, which is the opposite convention from the
    univariate ``BaselineComparator``'s negative Cohen's d thresholds.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    mode: MultivariateMode = MultivariateMode.BALANCED
    structure_alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    n_permutations: int = Field(default=999, ge=199)
    min_complete_rows: int = Field(default=20, ge=10)
    warning_effect: float = Field(default=0.20, gt=0.0)
    blocking_effect: float = Field(default=0.40, gt=0.0)
    seed: int | None = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InsufficientDataError(ValueError):
    """Raised when a ScoreMatrix cannot be built from the given inputs."""


# ---------------------------------------------------------------------------
# ScoreMatrix
# ---------------------------------------------------------------------------


class ScoreMatrix(BaseModel):
    """Row-aligned ``(n_traces, n_metrics)`` score matrix.

    Construct via ``from_metric_results``. Direct instantiation is allowed
    for tests and for callers that already have a validated ndarray; the
    model does not re-validate the array's content on construction.
    """

    model_config = ConfigDict(
        strict=True,
        frozen=False,
        arbitrary_types_allowed=True,
    )

    values: np.ndarray
    metric_names: tuple[str, ...]
    dropped_rows: int = Field(default=0, ge=0)

    @classmethod
    def from_metric_results(
        cls,
        metric_results: Sequence[MetricResult],
        *,
        metric_names: Sequence[str],
        min_complete_rows: int = 20,
    ) -> ScoreMatrix:
        """Build a matrix from a flat list of ``MetricResult`` records.

        Pivots on ``trace_id`` and keeps complete cases only: a trace is
        retained only if it has a record for every metric in
        ``metric_names`` and every one of those scores is finite and in
        ``[0, 1]``. Incomplete or malformed traces are counted in
        ``dropped_rows``. Rows are ordered by ``trace_id`` for determinism,
        so two calls with the same records produce byte-identical matrices.
        """
        if not metric_names:
            raise ValueError("metric_names must contain at least one metric.")
        if len(set(metric_names)) != len(metric_names):
            raise ValueError("metric_names must be unique.")
        if min_complete_rows < 1:
            raise ValueError("min_complete_rows must be at least 1.")

        unique_metrics = tuple(metric_names)

        per_trace: dict[UUID, dict[str, float]] = {}
        for record in metric_results:
            if record.metric_name not in unique_metrics:
                continue
            slot = per_trace.setdefault(record.trace_id, {})
            # First-wins on duplicate (trace, metric) records; the
            # alternative (last-wins) would silently depend on list order.
            if record.metric_name not in slot:
                slot[record.metric_name] = float(record.score)

        rows: list[list[float]] = []
        dropped = 0
        for trace_id in sorted(per_trace.keys()):
            slot = per_trace[trace_id]
            if not all(name in slot for name in unique_metrics):
                dropped += 1
                continue
            row = [slot[name] for name in unique_metrics]
            if not all(math.isfinite(v) and 0.0 <= v <= 1.0 for v in row):
                dropped += 1
                continue
            rows.append(row)

        if len(rows) < min_complete_rows:
            raise InsufficientDataError(
                f"Only {len(rows)} complete row(s); need at least "
                f"{min_complete_rows} for a valid multivariate comparison."
            )

        values = np.asarray(rows, dtype=float)
        # Defense in depth: the per-row filter above is what lets us DROP
        # malformed traces rather than rejecting the whole matrix. The
        # validator call re-checks the surviving rows and guards against a
        # future regression in the filter.
        validate_score_matrix(values, min_rows=min_complete_rows, min_columns=1)

        return cls(
            values=values,
            metric_names=unique_metrics,
            dropped_rows=dropped,
        )

    @property
    def n_rows(self) -> int:
        return int(self.values.shape[0])

    @property
    def n_metrics(self) -> int:
        return int(self.values.shape[1])


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


class MultivariateVerdict(BaseModel):
    """One structure test's verdict.

    Separate from ``RegressionVerdict`` because a structure verdict has no
    single ``metric_name`` (the tests are inherently multi-metric) and no
    signed effect size (variance and dependence changes are undirected).
    ``effect_size`` is a non-negative magnitude, and ``inconclusive``
    distinguishes "the test ran and found nothing" from "the test could not
    run at all."

    ``metric_deltas`` is populated with per-metric mean differences
    ``candidate - baseline`` even when the verdict is INCONCLUSIVE, since
    the caller may want them for reporting. ``inconclusive=True`` takes
    precedence over any other field's nominal value.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    method: MultivariateMethod
    severity: RegressionSeverity
    p_value: float = Field(ge=0.0, le=1.0)
    statistic: float
    effect_size: float = Field(ge=0.0)
    baseline_id: UUID
    run_id: UUID
    explanation: str
    metric_deltas: dict[str, float] = Field(default_factory=dict)
    inconclusive: bool = False


# ---------------------------------------------------------------------------
# Severity classification and mode handling
# ---------------------------------------------------------------------------


def classify_structure_severity(
    *,
    significant: bool,
    effect_size: float,
    warning_effect: float,
    blocking_effect: float,
) -> RegressionSeverity:
    """Classify a structure-test result against positive-magnitude thresholds.

    Structure effects are non-negative, so the comparison is against
    positive thresholds and larger effects mean more structural change.
    This is opposite to ``comparator.classify_severity``, which compares a
    signed Cohen's d against negative thresholds. The two classifiers are
    intentionally separate functions, not an overloaded one.
    """
    if warning_effect <= 0.0:
        raise ValueError("warning_effect must be positive.")
    if blocking_effect <= warning_effect:
        raise ValueError("blocking_effect must be greater than warning_effect.")
    if effect_size < 0.0:
        raise ValueError("effect_size must be non-negative.")
    if not significant:
        return RegressionSeverity.NONE
    if effect_size >= blocking_effect:
        return RegressionSeverity.BLOCKING
    if effect_size >= warning_effect:
        return RegressionSeverity.WARNING
    return RegressionSeverity.NONE


def apply_mode(
    severity: RegressionSeverity,
    mode: MultivariateMode,
) -> RegressionSeverity:
    """BALANCED mode caps severity at WARNING; STRICT passes through.

    The cap is the entire reason ``BALANCED`` is the default. A structure
    change is undirected (a variance increase and a decrease of the same
    magnitude produce the same test statistic), and the deployment gate's
    ``passed`` field must not flip on a directionless signal. ``STRICT``
    is an explicit opt-in for callers that have carved alpha out of the
    same budget the univariate comparator spends.
    """
    if mode == MultivariateMode.BALANCED and severity == RegressionSeverity.BLOCKING:
        return RegressionSeverity.WARNING
    return severity


# ---------------------------------------------------------------------------
# Seed derivation
# ---------------------------------------------------------------------------


def derive_permutation_seed(
    *,
    run_id: UUID,
    baseline_id: UUID,
    override: int | None = None,
) -> int:
    """Deterministic permutation seed for a ``(run, baseline)`` comparison.

    A CI gate needs determinism more than it needs randomness, so the seed
    is a pure function of the identity of the comparison. Two evaluations
    of the same ``(run_id, baseline_id)`` pair on the same input data
    produce byte-identical permutation streams. An explicit ``override``
    (from ``MultivariateConfig.seed``) bypasses the derivation for tests
    that need to pin a specific stream.
    """
    if override is not None:
        return override
    seed_sequence = np.random.SeedSequence([int(run_id), int(baseline_id)])
    state = seed_sequence.generate_state(1, dtype=np.uint32)
    return int(state[0])


# ---------------------------------------------------------------------------
# Comparator
# ---------------------------------------------------------------------------


class MultivariateComparator:
    """Runs the scale and dependence structure tests with Holm correction.

    See the module docstring for the design rationale. The comparator is
    stateless apart from its frozen config, so two instances constructed
    with the same config behave identically for the same inputs.
    """

    def __init__(self, *, config: MultivariateConfig | None = None) -> None:
        self.config = config or MultivariateConfig()
        logger.debug(
            "Initialized MultivariateComparator (mode=%s, structure_alpha=%.4f, "
            "n_permutations=%d, min_complete_rows=%d)",
            self.config.mode.value,
            self.config.structure_alpha,
            self.config.n_permutations,
            self.config.min_complete_rows,
        )

    def compare(
        self,
        *,
        candidate: ScoreMatrix,
        baseline: ScoreMatrix,
        baseline_id: UUID,
        run_id: UUID,
    ) -> list[MultivariateVerdict]:
        """Compare a candidate ScoreMatrix against a baseline ScoreMatrix.

        Returns exactly two verdicts, one per method. When only one metric
        column is present, the dependence test is skipped (there is no
        off-diagonal pair to test) and its verdict is emitted as NONE with
        ``p_value=1.0`` and an explanation noting the skip.
        """
        if candidate.metric_names != baseline.metric_names:
            raise ValueError(
                f"Candidate metrics {candidate.metric_names} do not match "
                f"baseline metrics {baseline.metric_names}."
            )
        if candidate.n_metrics < 1:
            raise ValueError("ScoreMatrix must have at least one metric.")
        if candidate.n_rows < self.config.min_complete_rows:
            raise InsufficientDataError(
                f"Candidate has {candidate.n_rows} row(s); need at least "
                f"{self.config.min_complete_rows}."
            )
        if baseline.n_rows < self.config.min_complete_rows:
            raise InsufficientDataError(
                f"Baseline has {baseline.n_rows} row(s); need at least "
                f"{self.config.min_complete_rows}."
            )

        seed = derive_permutation_seed(
            run_id=run_id,
            baseline_id=baseline_id,
            override=self.config.seed,
        )

        metric_deltas = {
            name: float(candidate.values[:, i].mean() - baseline.values[:, i].mean())
            for i, name in enumerate(candidate.metric_names)
        }

        logger.info(
            "Multivariate structure comparison (mode=%s, run_id=%s, "
            "baseline_id=%s, n_candidate=%d, n_baseline=%d, n_metrics=%d, seed=%d)",
            self.config.mode.value,
            run_id,
            baseline_id,
            candidate.n_rows,
            baseline.n_rows,
            candidate.n_metrics,
            seed,
        )

        # --- Scale test ---------------------------------------------------
        scale_stat, _, scale_p = scale_logvar_test(
            baseline.values,
            candidate.values,
            n_permutations=self.config.n_permutations,
            seed=seed,
        )
        scale_effect = float(math.sqrt(scale_stat / candidate.n_metrics))

        # --- Dependence test (only when p >= 2) --------------------------
        run_dependence = candidate.n_metrics >= 2
        if run_dependence:
            dep_stat, _, dep_p = dependence_max_t_test(
                baseline.values,
                candidate.values,
                n_permutations=self.config.n_permutations,
                seed=seed + 1,
            )
            dep_effect = float(dep_stat)
        else:
            dep_stat, dep_p, dep_effect = 0.0, 1.0, 0.0

        # --- Holm correction across the two structure tests ---------------
        if run_dependence:
            corrected = holm_bonferroni(
                {"scale": scale_p, "dependence": dep_p},
                alpha=self.config.structure_alpha,
            )
            scale_significant = corrected["scale"]
            dep_significant = corrected["dependence"]
        else:
            scale_significant = scale_p < self.config.structure_alpha
            dep_significant = False

        scale_severity = apply_mode(
            classify_structure_severity(
                significant=scale_significant,
                effect_size=scale_effect,
                warning_effect=self.config.warning_effect,
                blocking_effect=self.config.blocking_effect,
            ),
            self.config.mode,
        )

        dep_severity = apply_mode(
            classify_structure_severity(
                significant=dep_significant,
                effect_size=dep_effect,
                warning_effect=self.config.warning_effect,
                blocking_effect=self.config.blocking_effect,
            ),
            self.config.mode,
        )

        scale_explanation = (
            f"scale permutation test: p={scale_p:.4e}, "
            f"effect={scale_effect:.4f}, mode={self.config.mode.value}, "
            f"significant_after_holm={scale_significant}"
        )
        if run_dependence:
            dep_explanation = (
                f"dependence maxT test: p={dep_p:.4e}, "
                f"effect={dep_effect:.4f}, mode={self.config.mode.value}, "
                f"significant_after_holm={dep_significant}"
            )
        else:
            dep_explanation = (
                "dependence maxT test: skipped, a single metric column has "
                "no off-diagonal pair to test"
            )

        return [
            MultivariateVerdict(
                method=MultivariateMethod.SCALE,
                severity=scale_severity,
                p_value=float(scale_p),
                statistic=float(scale_stat),
                effect_size=scale_effect,
                baseline_id=baseline_id,
                run_id=run_id,
                explanation=scale_explanation,
                metric_deltas=metric_deltas,
                inconclusive=False,
            ),
            MultivariateVerdict(
                method=MultivariateMethod.DEPENDENCE,
                severity=dep_severity,
                p_value=float(dep_p),
                statistic=float(dep_stat),
                effect_size=dep_effect,
                baseline_id=baseline_id,
                run_id=run_id,
                explanation=dep_explanation,
                metric_deltas=metric_deltas,
                inconclusive=False,
            ),
        ]

    def compare_metric_results(
        self,
        *,
        candidate_results: Sequence[MetricResult],
        baseline_results: Sequence[MetricResult],
        metric_names: Sequence[str],
        baseline_id: UUID,
        run_id: UUID,
    ) -> list[MultivariateVerdict]:
        """Build ScoreMatrices from raw records, or return INCONCLUSIVE.

        Convenience wrapper around ``compare`` for the common case where
        the caller has raw ``MetricResult`` records rather than pre-built
        matrices. Insufficient data at either end produces INCONCLUSIVE
        verdicts, not an exception, matching the
        ``AttributionVerdict.INCONCLUSIVE`` contract.
        """
        try:
            candidate = ScoreMatrix.from_metric_results(
                candidate_results,
                metric_names=metric_names,
                min_complete_rows=self.config.min_complete_rows,
            )
            baseline = ScoreMatrix.from_metric_results(
                baseline_results,
                metric_names=metric_names,
                min_complete_rows=self.config.min_complete_rows,
            )
        except InsufficientDataError as exc:
            logger.warning(
                "Multivariate comparison inconclusive for run_id=%s: %s",
                run_id,
                exc,
            )
            return self._inconclusive_verdicts(
                baseline_id=baseline_id,
                run_id=run_id,
                reason=str(exc),
            )

        return self.compare(
            candidate=candidate,
            baseline=baseline,
            baseline_id=baseline_id,
            run_id=run_id,
        )

    def _inconclusive_verdicts(
        self,
        *,
        baseline_id: UUID,
        run_id: UUID,
        reason: str,
    ) -> list[MultivariateVerdict]:
        explanation = f"INCONCLUSIVE: {reason}"
        return [
            MultivariateVerdict(
                method=MultivariateMethod.SCALE,
                severity=RegressionSeverity.NONE,
                p_value=1.0,
                statistic=0.0,
                effect_size=0.0,
                baseline_id=baseline_id,
                run_id=run_id,
                explanation=explanation,
                metric_deltas={},
                inconclusive=True,
            ),
            MultivariateVerdict(
                method=MultivariateMethod.DEPENDENCE,
                severity=RegressionSeverity.NONE,
                p_value=1.0,
                statistic=0.0,
                effect_size=0.0,
                baseline_id=baseline_id,
                run_id=run_id,
                explanation=explanation,
                metric_deltas={},
                inconclusive=True,
            ),
        ]


__all__ = [
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
]
