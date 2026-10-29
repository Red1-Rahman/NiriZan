# tests/security/test_ast_security_gate.py
"""Ensure the existing AST gate resolves imported dangerous call aliases."""

import importlib.util
from pathlib import Path

import pytest


@pytest.mark.xfail(strict=True, reason="tracked: NZ-SEC-001")
def test_scanner_flags_from_import_os_system(tmp_path, monkeypatch):
    # Finding NZ-SEC-001: tests/test_security.py resolves a call name via its
    # final attribute segment, so `from os import system; system(...)` is
    # seen as bare `system`, not `os.system`, and evades the dangerous-call
    # gate. Remove this xfail once tests/test_security.py tracks import
    # bindings (ast.Import / ast.ImportFrom) instead of attribute suffixes.
    source = tmp_path / "fixture.py"
    source.write_text('from os import system\nsystem("true")\n', encoding="utf-8")
    gate_path = Path(__file__).parents[1] / "test_security.py"
    spec = importlib.util.spec_from_file_location("security_gate", gate_path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    with pytest.raises(AssertionError, match="Dangerous calls found"):
        gate.test_no_dangerous_calls()