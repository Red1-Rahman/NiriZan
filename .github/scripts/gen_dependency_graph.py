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

Note on output format: this script renders Markdown (with an embedded
Mermaid code block) to a local file for a documentation PR -- it does not
build or serve HTML, and none of the rendered strings are ever interpreted
as markup by a browser. Static analysis that flags string-building
functions for XSS-style risk (e.g. ast-grep's html-string-from-parameters
rule) does not apply to this file for that reason.
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

# Documented layer order from docs/contracts.md's Import Direction Rule.
DOCUMENTED_LAYER_ORDER = [
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


@dataclass
class ModuleInfo:
    """Everything this script knows about one scanned module."""

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


def _extract_imports(tree: ast.Module) -> tuple[set[str], dict[str, set[str]]]:
    """Return (in_package_import_targets, {module: {imported names}}).

    Relative imports (node.level > 0) are skipped rather than resolved,
    since ruff's TID rules ban them project-wide -- there should be none
    to find, and this keeps that assumption visible rather than silently
    handling a case that shouldn't exist.
    """
    import_targets: set[str] = set()
    imported_names: dict[str, set[str]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("nirizan"):
                    import_targets.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module and node.module.startswith("nirizan"):
                import_targets.add(node.module)
                names = imported_names.setdefault(node.module, set())
                for alias in node.names:
                    names.add(alias.name)

    return import_targets, imported_names


def _extract_exports(tree: ast.Module) -> set[str]:
    """Return the module's exported names: its `__all__` list if one is
    assigned at module level, otherwise every public (non-underscore-
    prefixed) top-level function or class.
    """
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
        return set(explicit_all)

    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    }


def parse_module(path: Path) -> tuple[set[str], dict[str, set[str]], set[str]]:
    """Parse one file and return (in_package_import_targets, {module: names}, exports)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        print(f"warning: could not parse {path}: {exc}", file=sys.stderr)
        return set(), {}, set()

    import_targets, imported_names = _extract_imports(tree)
    exports = _extract_exports(tree)
    return import_targets, imported_names, exports


def build_modules() -> dict[str, ModuleInfo]:
    """Scan every allowed file and build the full module map."""
    modules: dict[str, ModuleInfo] = {}
    for path in discover_files():
        dotted, layer = module_dotted_name(path)
        import_targets, imported_names, exports = parse_module(path)
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
    """Return the set of (source_layer, target_layer) edges implied by imports."""
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


def _layer_node_line(layer: str) -> str:
    """Render one Mermaid node declaration line for a layer."""
    if layer == "root":
        return '    root["nirizan (root)"]'
    return f'    {layer}["nirizan.{layer}"]'


def render_mermaid(edges: set[tuple[str, str]], layers: list[str]) -> str:
    """Render the layer-level Mermaid flowchart block."""
    lines = ["```mermaid", "flowchart TB"]
    lines.extend(_layer_node_line(layer) for layer in layers)
    lines.extend(f"    {src} --> {dst}" for src, dst in sorted(edges))
    lines.append("```")
    return "\n".join(lines)


def render_file_table(modules: dict[str, ModuleInfo]) -> str:
    """Render the per-module file/import Markdown table."""
    rows = ["| Module | File | Imports (in-package) |", "|---|---|---|"]
    for dotted in sorted(modules):
        mod = modules[dotted]
        imports = ", ".join(f"`{i}`" for i in sorted(mod.imports)) or "_none_"
        rows.append(f"| `{dotted}` | `{mod.path.as_posix()}` | {imports} |")
    return "\n".join(rows)


def render_unused_exports(modules: dict[str, ModuleInfo]) -> str:
    """Render the possibly-unused-exports Markdown table.

    A name is flagged if it is exported (via __all__ or a public top-level
    def/class) and no other scanned module does
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
        return (
            "_No exported names found unreferenced by an explicit "
            "`from ... import` elsewhere in the scanned tree._"
        )
    return "\n".join(rows)


def _ordered_layers(modules: dict[str, ModuleInfo]) -> list[str]:
    """Return observed layers in documented order, with any unexpected ones appended."""
    layers = {mod.layer for mod in modules.values()}
    ordered = [layer for layer in DOCUMENTED_LAYER_ORDER if layer in layers]
    ordered.extend(layer for layer in sorted(layers) if layer not in DOCUMENTED_LAYER_ORDER)
    return ordered


def render(modules: dict[str, ModuleInfo]) -> str:
    """Render the full contents of docs/dependency-graph.md."""
    ordered_layers = _ordered_layers(modules)
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
    """Scan the source tree and (re)write docs/dependency-graph.md."""
    modules = build_modules()
    if not modules:
        print(f"warning: no .py files found under {SRC_ROOT}", file=sys.stderr)
    text = render(modules)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(text, encoding="utf-8")
    print(f"Wrote {DEST.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
