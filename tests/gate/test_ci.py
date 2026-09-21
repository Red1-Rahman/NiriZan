# tests/gate/test_ci.py
from __future__ import annotations

import io
import json
import logging
from uuid import uuid4

import pytest
from nirizan.gate.ci import (
    format_gate_summary,
    gate_exit_code,
    serialize_gate_verdict,
    write_github_summary,
)
from nirizan.gate.verdict import GateVerdict
from nirizan.regression.comparator import RegressionSeverity, RegressionVerdict
from nirizan.regression.multivariate import (
    MultivariateMethod,
    MultivariateVerdict,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_verdict_pass() -> GateVerdict:
    b_id = uuid4()
    r_id = uuid4()
    return GateVerdict(
        passed=True,
        confidence_interval=(-0.01, 0.02),
        regression_verdicts=[
            RegressionVerdict(
                metric_name="groundedness",
                severity=RegressionSeverity.NONE,
                p_value=0.42,
                effect_size=-0.05,
                baseline_id=b_id,
                run_id=r_id,
                explanation="No regression detected",
            )
        ],
        run_id=r_id,
    )


@pytest.fixture
def mock_verdict_block() -> GateVerdict:
    b_id = uuid4()
    r_id = uuid4()
    return GateVerdict(
        passed=False,
        confidence_interval=(-0.25, -0.15),
        regression_verdicts=[
            RegressionVerdict(
                metric_name="groundedness",
                severity=RegressionSeverity.BLOCKING,
                p_value=0.001,
                effect_size=-0.65,
                baseline_id=b_id,
                run_id=r_id,
                explanation="Blocking regression in groundedness",
            )
        ],
        run_id=r_id,
    )


def _mv_verdict(
    method: MultivariateMethod,
    severity: RegressionSeverity,
    *,
    p_value: float = 0.03,
    effect_size: float = 0.5,
    inconclusive: bool = False,
    baseline_id=None,
    run_id=None,
) -> MultivariateVerdict:
    return MultivariateVerdict(
        method=method,
        severity=severity,
        p_value=p_value,
        statistic=1.0,
        effect_size=effect_size,
        baseline_id=baseline_id or uuid4(),
        run_id=run_id or uuid4(),
        explanation="test",
        inconclusive=inconclusive,
    )


@pytest.fixture
def mock_verdict_with_multivariate() -> GateVerdict:
    """A gate verdict that carries both univariate and multivariate verdicts."""
    b_id = uuid4()
    r_id = uuid4()
    return GateVerdict(
        passed=False,
        confidence_interval=(-0.30, -0.10),
        regression_verdicts=[
            RegressionVerdict(
                metric_name="groundedness",
                severity=RegressionSeverity.BLOCKING,
                p_value=0.001,
                effect_size=-0.70,
                baseline_id=b_id,
                run_id=r_id,
                explanation="Blocking univariate regression",
            )
        ],
        multivariate_verdicts=[
            _mv_verdict(
                MultivariateMethod.SCALE,
                RegressionSeverity.WARNING,
                p_value=0.0123,
                effect_size=0.42,
            ),
            _mv_verdict(
                MultivariateMethod.DEPENDENCE,
                RegressionSeverity.NONE,
                p_value=0.8731,
                effect_size=0.05,
            ),
        ],
        run_id=r_id,
    )


# ---------------------------------------------------------------------------
# Exit code behaviour
# ---------------------------------------------------------------------------


def test_passed_gate_returns_zero_exit_code(
    mock_verdict_pass: GateVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        code = gate_exit_code(mock_verdict_pass)

    assert code == 0
    assert "CI Gate PASSED" in caplog.text
    assert str(mock_verdict_pass.run_id) in caplog.text


def test_blocked_gate_returns_one_exit_code(
    mock_verdict_block: GateVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        code = gate_exit_code(mock_verdict_block)

    assert code == 1
    assert "CI Gate BLOCKED" in caplog.text
    assert str(mock_verdict_block.run_id) in caplog.text


# ---------------------------------------------------------------------------
# Summary formatting: univariate only (backward compatibility)
# ---------------------------------------------------------------------------


def test_gate_summary_contains_metric_results(
    mock_verdict_pass: GateVerdict,
) -> None:
    summary = format_gate_summary(mock_verdict_pass)
    assert "groundedness" in summary
    assert "none" in summary
    assert "**Gate:** PASS" in summary


def test_gate_summary_omits_structure_table_when_no_multivariate(
    mock_verdict_pass: GateVerdict,
) -> None:
    """Without multivariate verdicts, the summary must be byte-identical to
    the pre-multivariate-track output. The specific test is that the
    structure-track header never appears.
    """
    summary = format_gate_summary(mock_verdict_pass)
    assert "Structure track (multivariate):" not in summary
    assert "| Method |" not in summary


def test_gate_summary_omits_structure_table_for_empty_list(
    mock_verdict_pass: GateVerdict,
) -> None:
    """An explicit empty list is treated the same as the default."""
    verdict = mock_verdict_pass.model_copy(update={"multivariate_verdicts": []})
    summary = format_gate_summary(verdict)
    assert "Structure track (multivariate):" not in summary


# ---------------------------------------------------------------------------
# Summary formatting: with multivariate verdicts
# ---------------------------------------------------------------------------


def test_gate_summary_renders_structure_table(
    mock_verdict_with_multivariate: GateVerdict,
) -> None:
    summary = format_gate_summary(mock_verdict_with_multivariate)
    assert "Structure track (multivariate):" in summary
    # Both methods appear as rows.
    assert "scale" in summary
    assert "dependence" in summary
    # The header row for the structure table.
    assert "| Method | Severity | P-Value | Effect Size | Inconclusive |" in summary


def test_gate_summary_structure_table_includes_severities(
    mock_verdict_with_multivariate: GateVerdict,
) -> None:
    summary = format_gate_summary(mock_verdict_with_multivariate)
    # The scale row carries warning; the dependence row carries none.
    # Both are expected to appear somewhere after the structure header.
    header_idx = summary.index("Structure track (multivariate):")
    structure_section = summary[header_idx:]
    assert "warning" in structure_section
    assert "none" in structure_section


def test_gate_summary_structure_table_formats_p_value_and_effect(
    mock_verdict_with_multivariate: GateVerdict,
) -> None:
    summary = format_gate_summary(mock_verdict_with_multivariate)
    # p-value formatted with 4 decimal places in scientific notation
    assert "1.2300e-02" in summary
    assert "8.7310e-01" in summary
    # effect size with 3 decimals
    assert "0.420" in summary
    assert "0.050" in summary


def test_gate_summary_structure_table_marks_inconclusive(
    mock_verdict_pass: GateVerdict,
) -> None:
    """An INCONCLUSIVE multivariate verdict must be visibly flagged in the
    summary, since it is meaningfully different from a NONE verdict.
    """
    mv = _mv_verdict(
        MultivariateMethod.SCALE,
        RegressionSeverity.NONE,
        inconclusive=True,
    )
    verdict = mock_verdict_pass.model_copy(update={"multivariate_verdicts": [mv]})
    summary = format_gate_summary(verdict)
    structure_section = summary[summary.index("Structure track (multivariate):") :]
    assert "| yes |" in structure_section


def test_gate_summary_univariate_and_multivariate_both_rendered(
    mock_verdict_with_multivariate: GateVerdict,
) -> None:
    """The univariate table appears before the structure track table."""
    summary = format_gate_summary(mock_verdict_with_multivariate)
    univariate_idx = summary.index("| Metric |")
    structure_idx = summary.index("Structure track (multivariate):")
    assert univariate_idx < structure_idx
    assert "groundedness" in summary
    assert "blocking" in summary


# ---------------------------------------------------------------------------
# write_github_summary
# ---------------------------------------------------------------------------


def test_write_github_summary_logs_and_writes(
    mock_verdict_pass: GateVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    buffer = io.StringIO()
    with caplog.at_level(logging.INFO):
        write_github_summary(mock_verdict_pass, output=buffer)

    assert "Writing GitHub CI summary for run_id=" in caplog.text
    assert "**Gate:** PASS" in buffer.getvalue()


def test_write_github_summary_logs_both_track_counts(
    mock_verdict_with_multivariate: GateVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    buffer = io.StringIO()
    with caplog.at_level(logging.INFO):
        write_github_summary(mock_verdict_with_multivariate, output=buffer)

    assert "univariate_verdicts=1" in caplog.text
    assert "multivariate_verdicts=2" in caplog.text
    # And the multivariate section made it into the output.
    assert "Structure track (multivariate):" in buffer.getvalue()


def test_write_github_summary_appends_trailing_newline(
    mock_verdict_pass: GateVerdict,
) -> None:
    buffer = io.StringIO()
    write_github_summary(mock_verdict_pass, output=buffer)
    assert buffer.getvalue().endswith("\n")


# ---------------------------------------------------------------------------
# serialize_gate_verdict
# ---------------------------------------------------------------------------


def test_serialize_gate_verdict(
    mock_verdict_pass: GateVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        serialized = serialize_gate_verdict(mock_verdict_pass)

    data = json.loads(serialized)
    assert data["passed"] is True
    assert "Serializing GateVerdict for run_id=" in caplog.text


def test_serialize_gate_verdict_includes_multivariate_verdicts(
    mock_verdict_with_multivariate: GateVerdict,
) -> None:
    """JSON output must carry the structure-track verdicts so downstream
    consumers can render them without re-running the comparator.
    """
    serialized = serialize_gate_verdict(mock_verdict_with_multivariate)
    data = json.loads(serialized)

    assert "multivariate_verdicts" in data
    assert len(data["multivariate_verdicts"]) == 2
    methods = {mv["method"] for mv in data["multivariate_verdicts"]}
    assert methods == {"scale", "dependence"}
    # Enums serialize as their string values under mode="json".
    for mv in data["multivariate_verdicts"]:
        assert mv["severity"] in {"none", "warning", "blocking"}
        assert "inconclusive" in mv


def test_serialize_gate_verdict_empty_multivariate_is_empty_list(
    mock_verdict_pass: GateVerdict,
) -> None:
    """When no multivariate verdicts exist, the field is present as an
    empty list rather than missing, so downstream consumers can rely on
    the key always existing.
    """
    serialized = serialize_gate_verdict(mock_verdict_pass)
    data = json.loads(serialized)
    assert data["multivariate_verdicts"] == []
