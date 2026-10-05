#!/usr/bin/env python3
"""Non-invasive profiling driver for NiriZan.

Nothing under ``src/nirizan`` is modified or imports cProfile/pstats.
Instead, this script (which lives outside the package):

1. Starts a ``cProfile.Profile`` and runs the test suite in-process under it,
   so every function that the tests exercise is measured.
2. Saves the raw profile (``full.prof``) plus a filtered ``nirizan_only.prof``
   (only src/nirizan functions, caller edges pruned) for ``tuna``.
3. Uses ``pstats`` to split the stats per source file and writes a
   function-by-function report for every module matching:

       src/nirizan/*.py
       src/nirizan/*/*.py
       src/nirizan/*/*/*.py

   including the heaviest *external* callees of each function (numpy, stdlib,
   built-ins, ...) so a high cumtime is explained, and functions that were
   *never executed* (found via ``ast``), so gaps
   in test coverage are visible.

Usage (from the repository root):

    python .github/scripts/profile_runner.py
    python .github/scripts/profile_runner.py --top 20 -- -k "not slow"

Everything after ``--`` is forwarded to pytest.

Local visualisation:

    tuna profiling_reports/nirizan_only.prof   # focused on your code
    tuna profiling_reports/full.prof           # everything
"""

from __future__ import annotations

import argparse
import ast
import cProfile
import io
import marshal
import pstats
import sys
import sysconfig
from dataclasses import dataclass, field
from pathlib import Path

MAX_DEPTH = 3  # src/nirizan/*.py, */*.py, */*/*.py
COMMENT_LIMIT = 60_000  # GitHub comment hard limit is 65,536 chars


@dataclass
class FuncRow:
    name: str
    line: int
    ncalls: int
    prim_calls: int
    tottime: float
    cumtime: float
    externals: dict[str, float] = field(default_factory=dict)

    @property
    def tot_percall(self) -> float:
        return self.tottime / self.ncalls if self.ncalls else 0.0

    @property
    def cum_percall(self) -> float:
        return self.cumtime / self.prim_calls if self.prim_calls else 0.0


@dataclass
class ModuleReport:
    rel: Path
    rows: list[FuncRow] = field(default_factory=list)
    unexecuted: list[tuple[int, str]] = field(default_factory=list)

    @property
    def total_tottime(self) -> float:
        return sum(r.tottime for r in self.rows)


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def discover_modules(src: Path, include_init: bool) -> list[Path]:
    """Return .py files at depth 1..MAX_DEPTH under ``src`` (resolved paths)."""
    found: set[Path] = set()
    for depth in range(MAX_DEPTH):
        pattern = "/".join(["*"] * depth + ["*.py"])
        for p in src.glob(pattern):
            if p.name == "__init__.py" and not include_init:
                continue
            found.add(p.resolve())
    return sorted(found)


def collect_defs(path: Path) -> dict[int, str]:
    """Map first-line-number -> qualified name for every def in ``path``."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return {}

    defs: dict[int, str] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                qual = f"{prefix}{child.name}"
                # co_firstlineno points at the first decorator, if any.
                first = min([child.lineno, *(d.lineno for d in child.decorator_list)])
                defs[first] = qual
                visit(child, f"{qual}.<locals>.")
            elif isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            else:
                visit(child, prefix)

    visit(tree, "")
    return defs


# --------------------------------------------------------------------------- #
# Path helpers
# --------------------------------------------------------------------------- #
_STDLIB = Path(sysconfig.get_paths()["stdlib"]).resolve()


class PathResolver:
    """Cached ``str -> resolved Path | None`` for pstats filenames."""

    def __init__(self) -> None:
        self._cache: dict[str, Path | None] = {}

    def __call__(self, filename: str) -> Path | None:
        if filename not in self._cache:
            if not filename or filename.startswith(("<", "~")):
                self._cache[filename] = None
            else:
                try:
                    self._cache[filename] = Path(filename).resolve()
                except OSError:
                    self._cache[filename] = None
        return self._cache[filename]


def classify_external(filename: str, resolved: Path | None, src_root: Path) -> str:
    """Bucket a non-reported function into a short human label."""
    if filename.startswith("~"):
        return "built-ins (C)"  # includes C extensions such as numpy's ndarray methods
    if filename.startswith("<"):
        return "frozen/internal"
    if resolved is None:
        return "other"
    parts = resolved.parts
    for marker in ("site-packages", "dist-packages"):  # check before stdlib: often nested
        if marker in parts:
            idx = parts.index(marker) + 1
            if idx < len(parts):
                return parts[idx].removesuffix(".py")
    if resolved.is_relative_to(_STDLIB):
        idx = len(_STDLIB.parts)
        if idx < len(parts):
            return f"stdlib:{parts[idx].removesuffix('.py')}"
    if resolved.is_relative_to(src_root):
        return "nirizan (unlisted file)"
    return "other"


# --------------------------------------------------------------------------- #
# Profiling
# --------------------------------------------------------------------------- #
def run_profiled_pytest(pytest_args: list[str], prof_path: Path) -> int:
    import pytest  # imported lazily so --help works without dev deps

    profiler = cProfile.Profile()
    exit_code = profiler.runcall(pytest.main, pytest_args)
    profiler.dump_stats(str(prof_path))
    return int(exit_code)


def build_reports(
    prof_path: Path, modules: list[Path], src: Path, resolver: PathResolver
) -> list[ModuleReport]:
    stats = pstats.Stats(str(prof_path), stream=io.StringIO())
    src_root = src.resolve()
    wanted = {m: ModuleReport(rel=m.relative_to(src_root)) for m in modules}
    row_by_key: dict[tuple[str, int, str], FuncRow] = {}

    # Pass 1: rows for functions that live in the reported modules.
    for key, (_cc, nc, tt, ct, _callers) in stats.stats.items():  # type: ignore[attr-defined]
        filename, line, name = key
        target = resolver(filename)
        if target is None or target not in wanted:
            continue
        row = FuncRow(name, line, nc, _cc, tt, ct)
        wanted[target].rows.append(row)
        row_by_key[key] = row

    # Pass 2: attribute time spent in *external* direct callees to the calling row.
    # For an edge caller -> callee, the callee's ``callers`` dict holds
    # (ncalls, primcalls, tottime, cumtime) for that edge. Only direct callees
    # are counted, so nested external calls are not double counted.
    for key, (_cc, _nc, _tt, _ct, callers) in stats.stats.items():  # type: ignore[attr-defined]
        if key in row_by_key:
            continue  # internal callee, already reported on its own
        label: str | None = None
        for caller_key, edge in callers.items():
            row = row_by_key.get(caller_key)
            if row is None or not isinstance(edge, tuple):
                continue
            if label is None:
                label = classify_external(key[0], resolver(key[0]), src_root)
            row.externals[label] = row.externals.get(label, 0.0) + edge[3]

    for path, report in wanted.items():
        defs = collect_defs(path)
        executed_lines = {r.line for r in report.rows if not r.name.startswith("<")}
        for row in report.rows:
            if row.name == "<module>":
                row.name = "<module> (import time)"
            elif not row.name.startswith("<"):
                qual = defs.get(row.line)
                if qual is not None and qual.rsplit(".", 1)[-1] == row.name:
                    row.name = qual
        report.rows.sort(key=lambda r: r.cumtime, reverse=True)
        report.unexecuted = sorted(
            (ln, qual) for ln, qual in defs.items() if ln not in executed_lines
        )
    return [wanted[m] for m in modules]


def write_filtered_prof(
    prof_path: Path, modules: list[Path], out_path: Path, resolver: PathResolver
) -> int:
    """Write a .prof containing only reported-module functions (for tuna/pstats).

    Caller edges pointing at removed functions (pytest, stdlib, ...) are pruned
    so the file stays self-consistent. Returns the number of functions kept.
    """
    stats = pstats.Stats(str(prof_path), stream=io.StringIO())
    wanted = set(modules)
    raw = stats.stats  # type: ignore[attr-defined]
    keep = {k for k in raw if (resolver(k[0]) in wanted)}
    filtered = {
        k: (cc, nc, tt, ct, {c: e for c, e in callers.items() if c in keep})
        for k, (cc, nc, tt, ct, callers) in raw.items()
        if k in keep
    }
    with open(out_path, "wb") as f:
        marshal.dump(filtered, f)
    return len(filtered)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _fmt(x: float) -> str:
    return f"{x:.6f}"


def _externals(row: FuncRow, limit: int = 3) -> str:
    items = sorted(
        ((k, v) for k, v in row.externals.items() if v >= 1e-6),
        key=lambda kv: kv[1],
        reverse=True,
    )[:limit]
    return ", ".join(f"{k} {v:.6f}s" for k, v in items) if items else "-"


def _table(rows: list[FuncRow]) -> list[str]:
    out = [
        "| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call "
        "| Top external callees (cumtime) |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
    ]
    for r in rows:
        calls = str(r.ncalls) if r.ncalls == r.prim_calls else f"{r.ncalls}/{r.prim_calls}"
        out.append(
            f"| `{r.name}` | {r.line} | {calls} | {_fmt(r.tottime)} | "
            f"{_fmt(r.tot_percall)} | {_fmt(r.cumtime)} | {_fmt(r.cum_percall)} | {_externals(r)} |"
        )
    return out


def render_module(report: ModuleReport, src_name: str) -> str:
    lines = [f"# Profile: `{src_name}/{report.rel.as_posix()}`", ""]
    if not report.rows:
        lines.append("_No functions from this module were executed by the test suite._")
    else:
        lines += [
            f"- Functions executed: **{len(report.rows)}**",
            f"- Total internal time: **{_fmt(report.total_tottime)} s**",
            "",
            "## Executed functions (sorted by cumulative time)",
            "",
            *_table(report.rows),
        ]
    if report.unexecuted:
        lines += ["", "## Functions never executed by the tests", ""]
        lines += [f"- `{qual}` (line {ln})" for ln, qual in report.unexecuted]
    lines.append("")
    return "\n".join(lines)


def render_summary(reports: list[ModuleReport], top: int, src_name: str, exit_code: int) -> str:
    lines = [
        "### ⏱️ NiriZan Profiling Report",
        "",
        "`cProfile` + `pstats` over the test suite, split per module. "
        "Timings include profiler overhead: use them for *relative* comparison.",
        "",
    ]
    if exit_code != 0:
        lines += [f"> ⚠️ pytest exited with code `{exit_code}`. Results may be partial.", ""]

    lines += [
        "| Module | Functions run | Internal time (s) | Never executed |",
        "| :--- | ---: | ---: | ---: |",
    ]
    for r in sorted(reports, key=lambda r: r.total_tottime, reverse=True):
        lines.append(
            f"| `{r.rel.as_posix()}` | {len(r.rows)} | {_fmt(r.total_tottime)} | {len(r.unexecuted)} |"
        )

    lines += ["", f"#### Top {top} functions per module", ""]
    for r in sorted(reports, key=lambda r: r.total_tottime, reverse=True):
        if not r.rows:
            continue
        lines += [
            "<details>",
            f"<summary><code>{src_name}/{r.rel.as_posix()}</code></summary>",
            "",
            *_table(r.rows[:top]),
            "",
            "</details>",
            "",
        ]
    lines += [
        "Full per-function reports, `nirizan_only.prof` and `full.prof` "
        "(open with `tuna nirizan_only.prof`) are in the `profiling-reports` workflow artifact.",
        "",
    ]
    return "\n".join(lines)


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit("\n", 1)[0] + "\n\n_…truncated; see the workflow artifact for the full report._\n"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    if "--" in argv:
        idx = argv.index("--")
        own, pytest_extra = argv[:idx], argv[idx + 1 :]
    else:
        own, pytest_extra = argv, []

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", default="src/nirizan", help="Package directory to report on.")
    p.add_argument("--tests", default="tests", help="Test path passed to pytest.")
    p.add_argument("--out", default="profiling_reports", help="Output directory.")
    p.add_argument("--top", type=int, default=15, help="Rows per module in the summary.")
    p.add_argument("--include-init", action="store_true", help="Also report __init__.py files.")
    p.add_argument(
        "--fail-on-test-failure",
        action="store_true",
        help="Exit non-zero if pytest fails (default: still publish the reports).",
    )
    return p.parse_args(own), pytest_extra


def main(argv: list[str] | None = None) -> int:
    args, pytest_extra = parse_args(sys.argv[1:] if argv is None else argv)

    src = Path(args.src)
    if not src.is_dir():
        print(f"error: source directory not found: {src}", file=sys.stderr)
        return 2

    out = Path(args.out)
    (out / "modules").mkdir(parents=True, exist_ok=True)

    modules = discover_modules(src, args.include_init)
    print(f"Discovered {len(modules)} modules under {src}")

    prof_path = out / "full.prof"
    pytest_args = [args.tests, "-q", "-p", "no:cacheprovider", *pytest_extra]
    exit_code = run_profiled_pytest(pytest_args, prof_path)
    if exit_code == 5:
        print("warning: pytest collected no tests; reports will be empty.", file=sys.stderr)

    resolver = PathResolver()
    reports = build_reports(prof_path, modules, src, resolver)
    kept = write_filtered_prof(prof_path, modules, out / "nirizan_only.prof", resolver)
    print(f"nirizan_only.prof: {kept} functions kept")
    for report in reports:
        target = out / "modules" / report.rel.with_suffix(".md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_module(report, src.as_posix()), encoding="utf-8")

    summary = render_summary(reports, args.top, src.as_posix(), exit_code)
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    (out / "COMMENT.md").write_text(
        "<!-- nirizan-profiling-report -->\n" + truncate(summary, COMMENT_LIMIT),
        encoding="utf-8",
    )
    print(f"Wrote {len(reports)} module reports to {out}/")

    return exit_code if args.fail_on_test_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
