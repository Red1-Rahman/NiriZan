"""Ensure the existing AST gate resolves imported dangerous call aliases."""

import importlib.util
from pathlib import Path

import pytest


def test_scanner_flags_from_import_os_system(tmp_path, monkeypatch):
    source = tmp_path / "fixture.py"
    source.write_text('from os import system\nsystem("true")\n', encoding="utf-8")
    gate_path = Path(__file__).parents[1] / "test_security.py"
    spec = importlib.util.spec_from_file_location("security_gate", gate_path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    with pytest.raises(AssertionError, match="Dangerous calls found"):
        gate.test_no_dangerous_calls()
