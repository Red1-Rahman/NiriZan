# tests/regression/test_multivariate.py
from __future__ import annotations

from uuid import uuid4

import numpy as np
import pytest

from nirizan.metrics.stats import frobenius_covariance_permutation
from nirizan.regression.multivariate import CovarianceShiftDetector, CovarianceShiftVerdict

ALPHA = 0.05


def _sigmoid_multivariate(
    n: int,
    corr: np.ndarray,
    rng: np.random.Generator,
    *,
    shift: float = 0.0,
    scale: float = 1.0,
) -> np.ndarray:
    """[0, 1]-bounded correlated samples: Gaussian copula factor, squashed by
    a sigmoid. Not the Beta-copula generator the ablation notebook uses, but
    sufficient to control correlation structure, mean location, and spread
    independently for these tests without pulling scipy.stats.beta into the
    test suite.
    """
    p = corr.shape[0]
    L = np.linalg.cholesky(corr)
    z = rng.standard_normal(size=(n, p)) @ L.T
    z = z * scale + shift
    return 1.0 / (1.0 + np.exp(-z))


@pytest.fixture
def base_corr() -> np.ndarray:
    p = 3
    return np.eye(p) + 0.5 * (np.ones((p, p)) - np.eye(p))


@pytest.fixture
def detector() -> CovarianceShiftDetector:
    return CovarianceShiftDetector(alpha=ALPHA, n_perm=200, seed=123)


# ---------------------------------------------------------------------------
# Sanity checks: null / mean-shift / correlation-shift discrimination
# ---------------------------------------------------------------------------


def test_null_vs_null_does_not_fire(base_corr: np.ndarray, detector: CovarianceShiftDetector) -> None:
    rng = np.random.default_rng(1)
    x = _sigmoid_multivariate(100, base_corr, rng)
    y = _sigmoid_multivariate(100, base_corr, rng)

    verdict = detector.evaluate(candidate=y, baseline=x, baseline_id=uuid4(), run_id=uuid4())

    assert not verdict.is_drift
    assert verdict.explanation == "no significant covariance-structure drift detected"


def test_mean_shift_alone_does_not_fire(base_corr: np.ndarray, detector: CovarianceShiftDetector) -> None:
    """A pure mean/location shift, with correlation and relative spread
    unchanged, is Track 1's job, not Track 3's. This is the sanity check the
    ablation notebook runs before trusting the covariance test at all.
    """
    rng = np.random.default_rng(2)
    x = _sigmoid_multivariate(100, base_corr, rng, shift=0.0)
    y = _sigmoid_multivariate(100, base_corr, rng, shift=0.5)

    verdict = detector.evaluate(candidate=y, baseline=x, baseline_id=uuid4(), run_id=uuid4())

    assert not verdict.is_drift


def test_correlation_flip_fires_and_is_attributed_to_relationship_change(
    base_corr: np.ndarray, detector: CovarianceShiftDetector
) -> None:
    rng = np.random.default_rng(3)
    corr_flip = base_corr.copy()
    corr_flip[0, 1] = corr_flip[1, 0] = -0.4

    x = _sigmoid_multivariate(100, base_corr, rng)
    y = _sigmoid_multivariate(100, corr_flip, rng)

    verdict = detector.evaluate(candidate=y, baseline=x, baseline_id=uuid4(), run_id=uuid4())

    assert verdict.is_drift
    assert verdict.correlation_p_value is not None
    assert verdict.correlation_p_value < ALPHA
    assert "relationship between metrics" in verdict.explanation


# ---------------------------------------------------------------------------
# Variance-vs-correlation attribution (the Image 5 finding: a pure variance
# shift is real covariance drift, but is not a relationship/correlation
# change, and the verdict must say so rather than conflating the two).
# ---------------------------------------------------------------------------


def test_pure_variance_shift_fires_but_is_attributed_to_variance_not_correlation(
    detector: CovarianceShiftDetector,
) -> None:
    rng = np.random.default_rng(4)
    independent = np.eye(3)

    x = _sigmoid_multivariate(150, independent, rng, scale=0.5)
    y = _sigmoid_multivariate(150, independent, rng, scale=2.0)

    verdict = detector.evaluate(candidate=y, baseline=x, baseline_id=uuid4(), run_id=uuid4())

    assert verdict.is_drift, "a pure variance shift is real second-moment drift and must be flagged"
    assert verdict.correlation_p_value is not None
    assert verdict.correlation_p_value >= ALPHA, (
        "correlation-only sub-test must not fire when only variance changed"
    )
    assert "variance change" in verdict.explanation
    assert "relationship between metrics" not in verdict.explanation


def test_zero_variance_metric_degrades_to_primary_verdict_only(detector: CovarianceShiftDetector) -> None:
    """A metric that is constant within both groups makes correlation
    undefined. If real drift exists elsewhere (a correlation flip between
    the two remaining, non-constant metrics), the primary covariance-based
    verdict must still fire; only the correlation-only diagnostic is allowed
    to be missing, and the explanation must say so rather than silently
    reporting "no drift" or silently omitting the caveat.
    """
    rng = np.random.default_rng(5)
    base_corr_2d = np.array([[1.0, 0.5], [0.5, 1.0]])
    corr_flip_2d = np.array([[1.0, -0.4], [-0.4, 1.0]])

    x_active = _sigmoid_multivariate(100, base_corr_2d, rng)
    y_active = _sigmoid_multivariate(100, corr_flip_2d, rng)

    x = np.column_stack([np.full(100, 0.5), x_active])
    y = np.column_stack([np.full(100, 0.5), y_active])

    verdict = detector.evaluate(candidate=y, baseline=x, baseline_id=uuid4(), run_id=uuid4())

    assert verdict.is_drift, "the correlation flip in the non-constant metrics must still be caught"
    assert verdict.correlation_statistic is None
    assert verdict.correlation_p_value is None
    assert "could not be computed" in verdict.explanation


# ---------------------------------------------------------------------------
# Numeric edge cases (mirrors the ablation notebook's pre-flight suite)
# ---------------------------------------------------------------------------


def test_identical_candidate_and_baseline_gives_zero_statistic_and_max_p_value(
    base_corr: np.ndarray, detector: CovarianceShiftDetector
) -> None:
    rng = np.random.default_rng(6)
    x = _sigmoid_multivariate(50, base_corr, rng)

    verdict = detector.evaluate(candidate=x, baseline=x, baseline_id=uuid4(), run_id=uuid4())

    assert verdict.statistic == pytest.approx(0.0)
    assert verdict.p_value == pytest.approx(1.0)
    assert not verdict.is_drift


def test_singular_covariance_high_dimensional_does_not_raise(
    base_corr: np.ndarray, detector: CovarianceShiftDetector
) -> None:
    """p == n (3 samples, 3 metrics): the sample covariance matrix is
    singular. The permutation test must still run and return a valid
    p-value in [0, 1] rather than raising or returning NaN.
    """
    rng = np.random.default_rng(7)
    x = _sigmoid_multivariate(3, base_corr, rng)
    y = _sigmoid_multivariate(3, base_corr, rng)

    verdict = CovarianceShiftDetector(alpha=ALPHA, n_perm=50, seed=7).evaluate(
        candidate=y, baseline=x, baseline_id=uuid4(), run_id=uuid4()
    )

    assert 0.0 <= verdict.p_value <= 1.0


def test_asymmetric_sample_sizes_are_accepted(
    base_corr: np.ndarray, detector: CovarianceShiftDetector
) -> None:
    rng = np.random.default_rng(8)
    x = _sigmoid_multivariate(15, base_corr, rng)
    y = _sigmoid_multivariate(45, base_corr, rng)

    verdict = detector.evaluate(candidate=y, baseline=x, baseline_id=uuid4(), run_id=uuid4())

    assert 0.0 <= verdict.p_value <= 1.0


def test_affine_scale_transformation_is_p_value_invariant(
    base_corr: np.ndarray,
) -> None:
    """Y' = b + a * (Y - b) applied identically to both groups scales every
    covariance matrix by a common factor, which cancels out in the
    permutation's rank ordering. With a fixed seed, the p-value must match
    exactly.
    """
    rng = np.random.default_rng(9)
    corr_flip = base_corr.copy()
    corr_flip[0, 1] = corr_flip[1, 0] = -0.4

    x = _sigmoid_multivariate(100, base_corr, rng)
    y = _sigmoid_multivariate(100, corr_flip, rng)

    def affine(arr: np.ndarray, a: float, b: float = 0.5) -> np.ndarray:
        return b + a * (arr - b)

    _, p_original = frobenius_covariance_permutation(y, x, n_perm=200, seed=42)
    _, p_scaled = frobenius_covariance_permutation(
        affine(y, 0.5), affine(x, 0.5), n_perm=200, seed=42
    )

    assert p_original == pytest.approx(p_scaled)


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------


def test_nan_input_is_rejected(base_corr: np.ndarray, detector: CovarianceShiftDetector) -> None:
    rng = np.random.default_rng(10)
    x = _sigmoid_multivariate(20, base_corr, rng)
    y = x.copy()
    y[0, 0] = np.nan

    with pytest.raises(ValueError, match="non-finite"):
        detector.evaluate(candidate=y, baseline=x, baseline_id=uuid4(), run_id=uuid4())


def test_out_of_bounds_scores_are_rejected(base_corr: np.ndarray, detector: CovarianceShiftDetector) -> None:
    rng = np.random.default_rng(11)
    x = _sigmoid_multivariate(20, base_corr, rng)
    y = x.copy()
    y[0, 0] = 1.5

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        detector.evaluate(candidate=y, baseline=x, baseline_id=uuid4(), run_id=uuid4())


def test_mismatched_metric_counts_are_rejected(base_corr: np.ndarray, detector: CovarianceShiftDetector) -> None:
    rng = np.random.default_rng(12)
    x = _sigmoid_multivariate(20, base_corr, rng)
    y = _sigmoid_multivariate(20, np.eye(2), rng)

    with pytest.raises(ValueError, match="same number of metrics"):
        detector.evaluate(candidate=y, baseline=x, baseline_id=uuid4(), run_id=uuid4())


def test_single_metric_matrix_is_rejected(detector: CovarianceShiftDetector) -> None:
    rng = np.random.default_rng(13)
    x = rng.uniform(0.1, 0.9, size=(20, 1))
    y = rng.uniform(0.1, 0.9, size=(20, 1))

    with pytest.raises(ValueError, match="two metrics"):
        detector.evaluate(candidate=y, baseline=x, baseline_id=uuid4(), run_id=uuid4())


@pytest.mark.parametrize("bad_alpha", [0.0, 1.0, -0.1, 1.5])
def test_out_of_range_alpha_raises_at_construction(bad_alpha: float) -> None:
    with pytest.raises(ValueError, match="alpha must be between 0 and 1"):
        CovarianceShiftDetector(alpha=bad_alpha)


def test_non_positive_n_perm_raises_at_construction() -> None:
    with pytest.raises(ValueError, match="n_perm must be positive"):
        CovarianceShiftDetector(n_perm=0)


def test_n_perm_non_positive_raises_in_primitive(base_corr: np.ndarray) -> None:
    rng = np.random.default_rng(14)
    x = _sigmoid_multivariate(20, base_corr, rng)
    y = _sigmoid_multivariate(20, base_corr, rng)

    with pytest.raises(ValueError, match="n_perm must be positive"):
        frobenius_covariance_permutation(y, x, n_perm=0)


# ---------------------------------------------------------------------------
# Contract shape
# ---------------------------------------------------------------------------


def test_verdict_is_strict_pydantic_model(base_corr: np.ndarray, detector: CovarianceShiftDetector) -> None:
    rng = np.random.default_rng(15)
    x = _sigmoid_multivariate(30, base_corr, rng)
    y = _sigmoid_multivariate(30, base_corr, rng)

    verdict = detector.evaluate(candidate=y, baseline=x, baseline_id=uuid4(), run_id=uuid4())

    assert isinstance(verdict, CovarianceShiftVerdict)
    assert verdict.explanation, "explanation must be non-empty on every verdict"
    with pytest.raises(Exception):
        # strict=True config should reject an out-of-band type on assignment attempts
        # via model_construct bypass is not tested here; this checks strict validation
        # rejects a bad type at construction instead.
        CovarianceShiftVerdict(
            statistic="not-a-float",  # type: ignore[arg-type]
            p_value=0.5,
            baseline_id=uuid4(),
            run_id=uuid4(),
            is_drift=False,
            explanation="test",
        )
