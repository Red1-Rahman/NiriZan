# .github/scripts/gen_dependency_graph.py
"""Generate docs/dependency-graph.md from a static scan of the source tree.

Scope is deliberately narrow and enforced in code, not just by convention:

  READS  : src/nirizan/*.py, src/nirizan/*/*.py, docs/dependency-graph.md
  WRITES : docs/dependency-graph.md (only)

This script has no third-party dependencies (stdlib `ast` only) so that its
read/write footprint is fully auditable from this file alone -- no package
install step, no arbitrary code execution, no risk of a tool walking paths
outside the two glob patterns above.

Invoked by .github/workflows/dependency-graph.yml on a manual
(workflow_dispatch) trigger only. The workflow opens a PR with the result;
this script never commits, pushes, or touches git at all.
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "nirizan"
DEST = REPO_ROOT / "docs" / "dependency-graph.md"

# The only two read patterns this script is permitted to touch.
READ_GLOBS = ("*.py", "*/*.py")


@dataclass
class ModuleInfo:
    dotted: str
    layer: str  # "root" for src/nirizan/*.py, else the subdirectory name
    path: Path
    imports: set[str] = field(default_factory=set)  # in-package dotted imports
    exports: set[str] = field(default_factory=set)  # __all__, or public top-level names
    imported_names: dict[str, set[str]] = field(
        default_factory=dict
    )  # module_dotted -> {names imported from it}


def discover_files() -> list[Path]:
    """Return exactly the files matching the two allowed read globs, deduped."""
    if not SRC_ROOT.is_dir():
        return []
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in READ_GLOBS:
        for path in sorted(SRC_ROOT.glob(pattern)):
            if path.is_file() and path.suffix == ".py" and path not in seen:
                seen.add(path)
                files.append(path)
    return files


def module_dotted_name(path: Path) -> tuple[str, str]:
    """Return (dotted_module_name, layer) for a file under SRC_ROOT."""
    rel = path.relative_to(SRC_ROOT)
    parts = rel.with_suffix("").parts  # e.g. ("metrics", "stats") or ("_logging",)
    if len(parts) == 1:
        layer = "root"
        stem = parts[0]
        dotted = "nirizan" if stem == "__init__" else f"nirizan.{stem}"
    else:
        layer = parts[0]
        stem = parts[1]
        dotted = f"nirizan.{layer}" if stem == "__init__" else f"nirizan.{layer}.{stem}"
    return dotted, layer


def parse_module(path: Path, dotted: str) -> tuple[set[str], dict[str, set[str]], set[str]]:
    """Return (in_package_import_targets, {module: {names}}, exported_names)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        print(f"warning: could not parse {path}: {exc}", file=sys.stderr)
        return set(), {}, set()

    import_targets: set[str] = set()
    imported_names: dict[str, set[str]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("nirizan"):
                    import_targets.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative imports are banned project-wide by ruff's TID
                # rules; nothing to resolve here.
                continue
            if node.module and node.module.startswith("nirizan"):
                import_targets.add(node.module)
                names = imported_names.setdefault(node.module, set())
                for alias in node.names:
                    names.add(alias.name)

    exports: set[str] = set()
    explicit_all: list[str] | None = None
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__all__"
            and isinstance(node.value, (ast.List, ast.Tuple))
        ):
            explicit_all = [
                elt.value
                for elt in node.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            ]

    if explicit_all is not None:
        exports = set(explicit_all)
    else:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.startswith("_"):
                    exports.add(node.name)

    return import_targets, imported_names, exports


def build_modules() -> dict[str, ModuleInfo]:
    modules: dict[str, ModuleInfo] = {}
    for path in discover_files():
        dotted, layer = module_dotted_name(path)
        import_targets, imported_names, exports = parse_module(path, dotted)
        modules[dotted] = ModuleInfo(
            dotted=dotted,
            layer=layer,
            path=path.relative_to(REPO_ROOT),
            imports=import_targets,
            exports=exports,
            imported_names=imported_names,
        )
    return modules


def layer_edges(modules: dict[str, ModuleInfo]) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for mod in modules.values():
        for target in mod.imports:
            target_mod = modules.get(target)
            if target_mod is None:
                # Import of a nirizan module outside the scanned two-level
                # glob (shouldn't normally happen given the layer rule) --
                # skip rather than guess.
                continue
            if target_mod.layer != mod.layer:
                edges.add((mod.layer, target_mod.layer))
    return edges


def render_mermaid(edges: set[tuple[str, str]], layers: list[str]) -> str:
    lines = ["```mermaid", "flowchart TB"]
    for layer in layers:
        lines.append(f'    {layer}["nirizan.{layer}"]' if layer != "root" else '    root["nirizan (root)"]')
    for src, dst in sorted(edges):
        lines.append(f"    {src} --> {dst}")
    lines.append("```")
    return "\n".join(lines)


def render_file_table(modules: dict[str, ModuleInfo]) -> str:
    rows = ["| Module | File | Imports (in-package) |", "|---|---|---|"]
    for dotted in sorted(modules):
        mod = modules[dotted]
        imports = ", ".join(f"`{i}`" for i in sorted(mod.imports)) or "_none_"
        rows.append(f"| `{dotted}` | `{mod.path.as_posix()}` | {imports} |")
    return "\n".join(rows)


def render_unused_exports(modules: dict[str, ModuleInfo]) -> str:
    """A name is flagged if it is exported (via __all__ or a public
    top-level def/class) and no other scanned module does
    `from <module> import <name>`. This only catches that one import form --
    it will not see usage via `import module; module.name(...)`, so treat
    results as candidates to check, not a verdict.
    """
    imported_by_module: dict[str, set[str]] = {}
    for mod in modules.values():
        for target, names in mod.imported_names.items():
            imported_by_module.setdefault(target, set()).update(names)

    rows = ["| Module | Exported name | Imported elsewhere? |", "|---|---|---|"]
    any_flagged = False
    for dotted in sorted(modules):
        mod = modules[dotted]
        used = imported_by_module.get(dotted, set())
        for name in sorted(mod.exports):
            if name not in used:
                any_flagged = True
                rows.append(f"| `{dotted}` | `{name}` | no (via `from ... import`) |")

    if not any_flagged:
        return "_No exported names found unreferenced by an explicit `from ... import` elsewhere in the scanned tree._"
    return "\n".join(rows)


def render(modules: dict[str, ModuleInfo]) -> str:
    layers = sorted({mod.layer for mod in modules.values()})
    # Keep the documented layer order first, append anything unexpected after.
    documented_order = [
        "root",
        "instrumentation",
        "orchestrator",
        "metrics",
        "trust",
        "storage",
        "regression",
        "gate",
        "reporting",
    ]
    ordered_layers = [layer for layer in documented_order if layer in layers]
    ordered_layers += [layer for layer in layers if layer not in documented_order]

    edges = layer_edges(modules)

    parts = [
        "# Dependency Graph (generated)",
        "",
        "> Generated by `.github/scripts/gen_dependency_graph.py` via the",
        "> `dependency-graph` GitHub Actions workflow (manual trigger only).",
        "> The generator reads only `src/nirizan/*.py`, `src/nirizan/*/*.py`,",
        "> and this file, and writes only this file. Do not hand-edit; changes",
        "> will be overwritten the next time the workflow runs.",
        "",
        "## Layer-level diagram",
        "",
        render_mermaid(edges, ordered_layers),
        "",
        "## File-level imports",
        "",
        render_file_table(modules),
        "",
        "## Possibly-unused exports",
        "",
        render_unused_exports(modules),
        "",
    ]
    return "\n".join(parts)


def main() -> None:
    modules = build_modules()
    if not modules:
        print(f"warning: no .py files found under {SRC_ROOT}", file=sys.stderr)
    text = render(modules)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(text, encoding="utf-8")
    print(f"Wrote {DEST.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
