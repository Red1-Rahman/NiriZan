# tests/gate/test_ci.py
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


def test_gate_summary_contains_metric_results(
    mock_verdict_pass: GateVerdict,
) -> None:
    summary = format_gate_summary(mock_verdict_pass)
    assert "groundedness" in summary
    assert "none" in summary
    assert "**Gate:** PASS" in summary


def test_write_github_summary_logs_and_writes(
    mock_verdict_pass: GateVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    buffer = io.StringIO()
    with caplog.at_level(logging.INFO):
        write_github_summary(mock_verdict_pass, output=buffer)

    assert "Writing GitHub CI summary for run_id=" in caplog.text
    assert "**Gate:** PASS" in buffer.getvalue()


def test_serialize_gate_verdict(
    mock_verdict_pass: GateVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        serialized = serialize_gate_verdict(mock_verdict_pass)

    data = json.loads(serialized)
    assert data["passed"] is True
    assert "Serializing GateVerdict for run_id=" in caplog.text
