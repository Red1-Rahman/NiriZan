# tests/test_otel_isolation.py
"""Guarantees for people who use NiriZan without OpenTelemetry.

The OpenTelemetry bridge is an optional adapter. These tests turn that claim into
checks that run in CI, in both the leg that installs the ``otel`` extra and the leg
that does not, so a regression cannot slip in unnoticed:

* the whole core package imports and works with OpenTelemetry *unavailable*
  (simulated in a subprocess, so it holds even where the package is installed);
* nothing outside the adapter imports the adapter or OpenTelemetry (a static scan,
  independent of the import-linter contract that enforces the same rule);
* OpenTelemetry is declared as an optional extra and is not pulled in by the core
  or ``dev`` dependencies;
* importing the adapter does not start threads or register a global provider.

This file must never import ``opentelemetry`` at module level.
"""

import ast
import json
import os
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import nirizan

PACKAGE_DIR = Path(nirizan.__file__).resolve().parent
PYPROJECT = PACKAGE_DIR.parents[1] / "pyproject.toml"
ADAPTER_PACKAGE = "nirizan.instrumentation.otel"
ADAPTER_DIR = PACKAGE_DIR / "instrumentation" / "otel"

# Modules of the adapter that need the ``otel`` extra to import.
OTEL_BACKED_MODULES = (f"{ADAPTER_PACKAGE}.to_otel", f"{ADAPTER_PACKAGE}.from_otel")

_BLOCKER = """
import importlib.abc
import sys


class _BlockOpenTelemetry(importlib.abc.MetaPathFinder):
    \"\"\"Make ``import opentelemetry`` fail even if the package is installed.\"\"\"

    def find_spec(self, name, path=None, target=None):
        if name == "opentelemetry" or name.startswith("opentelemetry."):
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return None


sys.meta_path.insert(0, _BlockOpenTelemetry())
"""

_WITHOUT_OPENTELEMETRY = (
    _BLOCKER
    + f"""
import asyncio
import importlib
import json
import pkgutil
import tempfile
from pathlib import Path
from uuid import UUID

OTEL_BACKED = {OTEL_BACKED_MODULES!r}

import nirizan

imported, failures = [], []
for info in pkgutil.walk_packages(nirizan.__path__, "nirizan."):
    if info.name in OTEL_BACKED:
        continue
    try:
        importlib.import_module(info.name)
        imported.append(info.name)
    except Exception as exc:
        failures.append(f"{{info.name}}: {{exc!r}}")

result = {{
    "imported": len(imported),
    "failures": failures,
    "leaked": sorted(m for m in sys.modules if m.split(".")[0] == "opentelemetry"),
}}

adapter_errors = {{}}
for name in OTEL_BACKED:
    try:
        importlib.import_module(name)
        adapter_errors[name] = None
    except ModuleNotFoundError as exc:
        adapter_errors[name] = exc.name
    except Exception as exc:
        adapter_errors[name] = repr(exc)
result["adapter_errors"] = adapter_errors

from nirizan.instrumentation.otel import _id_mapping, semconv

result["adapter_package_root_works"] = (
    _id_mapping.uuid_to_otel_trace_id(UUID(int=5)) == 5
    and semconv.encode_sequence_attribute_value(["a"]) == '["a"]'
)

from nirizan.instrumentation.exporters import InMemoryExporter
from nirizan.instrumentation.spans import SpanKind
from nirizan.instrumentation.tracer import Tracer


async def trace_once():
    exporter = InMemoryExporter()
    tracer = Tracer("standalone", exporter=exporter)
    async with tracer.start_span("root", SpanKind.PLANNING):
        async with tracer.start_span("child", SpanKind.GENERATION):
            pass
    return exporter.get_traces()


traces = asyncio.run(trace_once())
result["core_traces"] = [len(traces), sorted(s.name for s in traces[0].spans)]

# L1 mini end-to-end: tracer -> CollectorExporter -> TraceCollector ->
# SQLiteTraceRepository -> list_by_application, all with OpenTelemetry
# import-blocked. This is the pipeline the docs promise works core-only.
from nirizan.orchestrator.collector import CollectorExporter, TraceCollector
from nirizan.storage.trace_repository import SQLiteTraceRepository


async def mini_e2e_run(db_path):
    repository = SQLiteTraceRepository(db_path)
    collector = TraceCollector(repository)
    await collector.start()
    exporter = CollectorExporter(collector)
    tracer = Tracer("l1-app", exporter=exporter)
    async with tracer.start_span("pipeline-root", SpanKind.PLANNING):
        async with tracer.start_span("pipeline-child", SpanKind.GENERATION):
            pass
    await collector.stop()
    stored = await repository.list_by_application("l1-app")
    repository.close()
    return stored


with tempfile.TemporaryDirectory() as tmp:
    stored = asyncio.run(mini_e2e_run(str(Path(tmp) / "l1.db")))

result["l1_e2e"] = {{
    "traces": len(stored),
    "names": sorted(s.name for s in stored[0].spans) if stored else [],
    "created_aware": bool(stored) and stored[0].created_at.tzinfo is not None,
}}

print(json.dumps(result))
"""
)

_ADAPTER_SIDE_EFFECTS = """
import json
import threading

from opentelemetry import trace

before = {
    "threads": sorted(t.name for t in threading.enumerate()),
    "provider": type(trace.get_tracer_provider()).__name__,
}

import nirizan.instrumentation.otel.from_otel  # noqa: F401
import nirizan.instrumentation.otel.to_otel  # noqa: F401

after = {
    "threads": sorted(t.name for t in threading.enumerate()),
    "provider": type(trace.get_tracer_provider()).__name__,
}
print(json.dumps({"before": before, "after": after}))
"""


def _run_python(script: str) -> dict[str, Any]:
    """Run ``script`` in a fresh interpreter and parse the JSON line it prints."""
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in sys.path if p)}
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    parsed: dict[str, Any] = json.loads(completed.stdout.strip().splitlines()[-1])
    return parsed


@pytest.fixture(scope="module")
def without_opentelemetry() -> dict[str, Any]:
    """One subprocess run shared by every test about the OpenTelemetry-free case."""
    return _run_python(_WITHOUT_OPENTELEMETRY)


# ---------------------------------------------------------------------------
# The core works with OpenTelemetry unavailable
# ---------------------------------------------------------------------------


def test_every_core_module_imports_without_opentelemetry(
    without_opentelemetry: dict[str, Any],
) -> None:
    assert without_opentelemetry["failures"] == []
    # The walk really covered the package, not an empty or truncated tree.
    assert without_opentelemetry["imported"] >= 20


def test_importing_the_core_does_not_load_opentelemetry(
    without_opentelemetry: dict[str, Any],
) -> None:
    assert without_opentelemetry["leaked"] == []


def test_tracing_still_works_without_opentelemetry(
    without_opentelemetry: dict[str, Any],
) -> None:
    assert without_opentelemetry["core_traces"] == [1, ["child", "root"]]


def test_the_full_core_pipeline_runs_without_opentelemetry(
    without_opentelemetry: dict[str, Any],
) -> None:
    """L1 mini e2e: tracer -> collector -> SQLite repository, otel import-blocked.

    This is the pipeline the docs promise works in a core-only install: spans
    captured by the core tracer flow through the collector and land in the
    SQLite trace repository, with no OpenTelemetry module importable.
    """
    assert without_opentelemetry["l1_e2e"]["traces"] == 1
    assert without_opentelemetry["l1_e2e"]["names"] == [
        "pipeline-child",
        "pipeline-root",
    ]
    assert without_opentelemetry["l1_e2e"]["created_aware"] is True
    # The whole run happened with opentelemetry blocked: nothing leaked in.
    assert without_opentelemetry["leaked"] == []


def test_the_dependency_free_part_of_the_adapter_package_works_without_opentelemetry(
    without_opentelemetry: dict[str, Any],
) -> None:
    assert without_opentelemetry["adapter_package_root_works"] is True


def test_the_opentelemetry_backed_modules_fail_with_a_plain_import_error_naming_it(
    without_opentelemetry: dict[str, Any],
) -> None:
    """Without the extra, ``to_otel`` and ``from_otel`` fail at import, and say why."""
    assert without_opentelemetry["adapter_errors"] == {
        name: "opentelemetry" for name in OTEL_BACKED_MODULES
    }


# ---------------------------------------------------------------------------
# Nothing outside the adapter depends on it
# ---------------------------------------------------------------------------


def _core_python_files() -> Iterator[Path]:
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        if ADAPTER_DIR not in path.parents:
            yield path


def _imported_names(path: Path) -> Iterator[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            yield node.module
            for alias in node.names:
                yield f"{node.module}.{alias.name}"


def test_the_static_scan_covers_the_whole_core_package() -> None:
    files = list(_core_python_files())

    assert len(files) >= 20
    assert PACKAGE_DIR / "instrumentation" / "tracer.py" in files
    assert not any(ADAPTER_DIR in f.parents for f in files)


def test_nothing_outside_the_adapter_imports_the_adapter() -> None:
    offenders = [
        f"{path.relative_to(PACKAGE_DIR)} imports {name}"
        for path in _core_python_files()
        for name in _imported_names(path)
        if name == ADAPTER_PACKAGE or name.startswith(f"{ADAPTER_PACKAGE}.")
    ]

    assert offenders == []


def test_nothing_outside_the_adapter_imports_opentelemetry() -> None:
    offenders = [
        f"{path.relative_to(PACKAGE_DIR)} imports {name}"
        for path in _core_python_files()
        for name in _imported_names(path)
        if name == "opentelemetry" or name.startswith("opentelemetry.")
    ]

    assert offenders == []


# ---------------------------------------------------------------------------
# OpenTelemetry is an optional extra
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def project() -> dict[str, Any]:
    if not PYPROJECT.exists():
        pytest.skip("pyproject.toml is not available (package is not a source checkout)")
    parsed: dict[str, Any] = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return parsed["project"]


def _names(requirements: list[str]) -> set[str]:
    separators = "<>=!~;[ "
    names = set()
    for requirement in requirements:
        end = next((i for i, c in enumerate(requirement) if c in separators), len(requirement))
        names.add(requirement[:end].lower().replace("_", "-"))
    return names


def test_opentelemetry_is_not_a_core_dependency(project: dict[str, Any]) -> None:
    assert not any(name.startswith("opentelemetry") for name in _names(project["dependencies"]))


def test_the_otel_extra_declares_the_api_and_the_sdk(project: dict[str, Any]) -> None:
    extras = project["optional-dependencies"]

    assert {"opentelemetry-api", "opentelemetry-sdk"} <= _names(extras["otel"])


def test_the_dev_extra_does_not_pull_in_opentelemetry(project: dict[str, Any]) -> None:
    """Otherwise the leg that checks the OpenTelemetry-free case would not be one."""
    dev = _names(project["optional-dependencies"]["dev"])

    assert not any(name.startswith("opentelemetry") for name in dev)


# ---------------------------------------------------------------------------
# L2: installed metadata agrees with the declared extras
# ---------------------------------------------------------------------------


def test_installed_metadata_gates_opentelemetry_behind_the_otel_extra() -> None:
    """The *installed* distribution (not just pyproject) must gate otel deps.

    ``importlib.metadata.requires`` is what pip and other tools actually read;
    a stray un-gated ``opentelemetry-api`` line there would make every
    ``pip install nirizan`` pull OpenTelemetry in, silently defeating the
    optional-extra contract that the blocked-subprocess tests verify.
    """
    from importlib.metadata import PackageNotFoundError, requires

    try:
        requirements = requires("nirizan")
    except PackageNotFoundError:
        pytest.skip("nirizan is not installed as a distribution")
    assert requirements is not None

    otel_requirements = [r for r in requirements if "opentelemetry" in r.lower()]
    # Every otel requirement carries an "extra == 'otel'" marker.
    assert otel_requirements != []
    assert all('extra == "otel"' in r or "extra == 'otel'" in r for r in otel_requirements)
    # And no requirement outside the otel extra mentions it: a line without an
    # otel extra marker would install OpenTelemetry for every user.
    unmarked = [r for r in requirements if "opentelemetry" in r.lower() and "extra == " not in r]
    assert unmarked == []


def test_the_root_package_init_imports_no_opentelemetry_modules() -> None:
    """``nirizan/__init__.py`` must stay free of adapter/otel imports."""
    tree = ast.parse(
        (PACKAGE_DIR / "__init__.py").read_text(encoding="utf-8"),
        filename=str(PACKAGE_DIR / "__init__.py"),
    )
    offenders = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and (
            node.module == ADAPTER_PACKAGE
            or node.module.startswith(f"{ADAPTER_PACKAGE}.")
            or node.module == "opentelemetry"
            or node.module.startswith("opentelemetry.")
        )
    ]

    assert offenders == []


def test_the_adapter_package_root_imports_only_dependency_free_submodules() -> None:
    """``otel/__init__.py`` re-exports only modules that import without otel.

    Import Hygiene in that file promises exactly ``_id_mapping`` and
    ``semconv``; a third re-export that pulls in ``to_otel``/``from_otel``
    would break every core-only import of ``nirizan.instrumentation.otel``.
    """
    init_path = ADAPTER_DIR / "__init__.py"
    tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    otel_backed = imported_modules & {"opentelemetry"} | {
        m for m in imported_modules if m.startswith("opentelemetry.")
    }

    assert otel_backed == set()
    # The package root only re-exports the dependency-free submodules.
    import nirizan.instrumentation.otel as otel_pkg

    assert set(otel_pkg.__all__) == {"_id_mapping", "semconv"}


# ---------------------------------------------------------------------------
# Importing the adapter has no side effects
# ---------------------------------------------------------------------------


def test_importing_the_adapter_starts_no_threads_and_sets_no_global_provider() -> None:
    pytest.importorskip("opentelemetry.sdk")

    result = _run_python(_ADAPTER_SIDE_EFFECTS)

    assert result["after"]["threads"] == result["before"]["threads"]
    assert result["after"]["provider"] == result["before"]["provider"]
    assert result["after"]["provider"] == "ProxyTracerProvider"
