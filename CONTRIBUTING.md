# Contributing to NiriZan

Thank you for considering contributing to NiriZan. This document is itself pre-release: NiriZan has not shipped a single line of implementation code yet, so this file describes the process as it exists today, not a mature open-source project's steady-state contribution guide. Expect it to change, sometimes significantly, as the project moves through its early development phases. If something here contradicts how the project actually works by the time you read it, open an issue and ask; don't assume this document is quietly out of date and guess.

## Where the Project Actually Is Right Now

Read these three documents before writing any code. They are not optional background reading, they are the actual specification you'll be implementing against:

- **`ARCHITECTURE.md`** — what each component does and how data flows between them.
- **`docs/contracts.md`** — the exact pydantic models and plugin interfaces each component promises to the components around it. If you're implementing a component, this is your interface contract, not a suggestion.
- **`README.md`** — the project's purpose and positioning, useful for understanding why a design decision was made the way it was.

NiriZan is currently pre-implementation. There is no working code yet, no released package, no CI pipeline running against real code. The most valuable contributions right now are the ones that get Phase 1 (Instrumentation & Trace Storage) into a working, tested state, not new architectural ideas layered on top of a system that doesn't exist yet.

## How to Contribute Right Now

### 1. Start with an issue, not a pull request

Open an issue before writing code, even for something that feels small. At this stage, with no implementation to anchor against, two people can easily build incompatible things against the same architecture document. A short issue describing what you plan to build and which contract it implements saves both of us a wasted pull request.

### 2. Pick work that matches the current phase

Check `docs/contracts.md` for which phase's contracts are already defined and stable, and prefer contributing there over jumping ahead. If you want to work on something from a later phase because it's more interesting, that's understandable, but flag it explicitly in your issue as "early work on Phase N" so it's reviewed with the right expectations, not treated as if it should merge immediately.

### 3. Follow the contracts, don't improvise around them

If you're implementing `metrics/rag_triad.py`, it must implement the `Metric` protocol exactly as defined in `docs/contracts.md`, returning `MetricResult` objects with scores normalized to `[0.0, 1.0]`. If the contract seems wrong or incomplete for what you're building, that's a legitimate finding, but the fix is a pull request against `docs/contracts.md` first, discussed and merged on its own, not a silent deviation in your implementation PR. A contract that drifts from its own documentation defeats the entire point of writing it down.

### 4. Respect the import direction rule

`docs/contracts.md` defines a one-way import direction across components (instrumentation → orchestrator → metrics → trust/storage → regression → gate → reporting). This is enforced by `ruff`'s `TID` rules in `pyproject.toml`, but tooling catches syntax, not intent. If your change requires importing "backwards," that's a signal the shared type belongs in `storage/models.py` or `metrics/base.py`, not a signal to add the import anyway.

## Development Setup

```bash
git clone https://github.com/Red1-Rahman/NiriZan.git
cd NiriZan
pip install -e ".[dev]"
```

This project targets Python 3.10 or 3.11, per `pyproject.toml`. If you're on 3.12+, use `pyenv` or a similar tool to get a supported interpreter; the upper bound in `pyproject.toml` is intentional, not an oversight.

### Before opening a pull request, run:

```bash
ruff check src tests
ruff format --check src tests
mypy
pytest
```

All four must pass. `mypy` is configured in `strict` mode project-wide (see `pyproject.toml`), which means every function signature needs real types, not `Any`. If you're not used to strict mypy, it will feel unreasonably picky at first; that strictness is what keeps the plugin boundaries in `docs/contracts.md` honest as the codebase grows past one contributor.

## Code Standards

- **Typing:** Every public function and method has complete type annotations. `disallow_untyped_defs` and `disallow_any_generics` are both on in `pyproject.toml`; this isn't a style preference, it's enforced.
- **Data models:** Use `pydantic.BaseModel` for any structured data crossing a component boundary, matching the models in `docs/contracts.md` exactly. Don't invent a parallel dataclass or dict-shaped return value that happens to look similar.
- **Async:** Instrumentation and orchestration code is async by design (see Design Principle 2 in `ARCHITECTURE.md`: evaluation must never sit on the user-facing critical path). Don't introduce blocking calls into `instrumentation/` or `orchestrator/` without a specific, discussed reason.
- **Tests:** New code needs tests in the mirrored path under `tests/`, matching the module you're testing (e.g. `src/nirizan/metrics/rag_triad.py` → `tests/metrics/test_rag_triad.py`). A component with no test directory content is not considered complete, regardless of whether the code runs.
- **No circular imports:** Enforced by `ruff`'s `TID` rules and the import direction rule above. If CI flags a circular import, that's a design problem to fix, not a lint rule to suppress.

## Commit and PR Conventions

- Keep commits scoped to one logical change. A PR that touches `instrumentation/` and `reporting/` at the same time, with no shared cause, will be asked to split.
- Reference the phase and component your change belongs to in the PR description (e.g. "Phase 2: implements `RAGTriadMetric` per `docs/contracts.md` §Phase 2 Contracts").
- If your change modifies a contract in `docs/contracts.md`, say so explicitly and explain whether it's additive (new optional field, safe) or breaking (removed/changed field, needs a version bump per the Versioning Rule at the end of that document).

## Code of Conduct

This project follows the Contributor Covenant. Participation in this project, including issues, pull requests, and any other project spaces, is governed by it. Report unacceptable behavior as described in `CODE_OF_CONDUCT.md`.

## Licensing

NiriZan is licensed under the GNU General Public License v3 (or later). By contributing, you agree that your contributions are licensed under the same terms.

## What This Document Doesn't Cover Yet

This is a living document for a pre-release project, not a finished contribution guide. Things it doesn't address yet, because the project isn't far enough along for them to be real questions: release/versioning process for the package itself, a formal review/maintainer-approval process beyond "the maintainer reviews it," a governance model for when there's more than one regular contributor, and a triage process for issues. These will be added as the project actually reaches the point where they matter, not preemptively guessed at now. If you hit one of these gaps in practice, that's useful signal, open an issue about the gap itself.
