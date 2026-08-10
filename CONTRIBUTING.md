# Contributing to NiriZan

Thank you for considering contributing to NiriZan. Phases 1 through 5 of
the roadmap are implemented, tested, and merged to `main`: instrumentation
and trace storage, the RAG Triad metrics, experiment tracking and
baselines, regression detection with a CI gate, and the drift and
judge-reliability layer (attribution engine, anchor sets, judge reliability
panel, and dashboard assembly). Phase 6, an evaluation and ablation suite
benchmarking that implementation against its own targets, is in progress
in `experiments/`. This document describes the process as it exists today.
If something here contradicts how the project actually works by the time
you read it, open an issue and ask; don't assume this document is quietly
out of date and guess.

## Where the Project Actually Is Right Now

Read these three documents before writing any code. They are not optional
background reading, they are the actual specification you'll be
implementing against:

- **`ARCHITECTURE.md`** — what each component does and how data flows
  between them.
- **`docs/contracts.md`** — the exact pydantic models and plugin interfaces
  each component promises to the components around it. If you're
  implementing a component, this is your interface contract, not a
  suggestion.
- **`README.md`** — the project's purpose and positioning, useful for
  understanding why a design decision was made the way it was.

There is real, tested, CI-enforced code in `src/nirizan/` today. Five
GitHub Actions workflows (`ci.yml`, `nirizan_gate.yml`, `packaging.yml`,
`cross-platform.yml`, `test-pypi.yml`) run against it on every push. The
most valuable contributions right now depend on where you want to work:

- **Closing known gaps in what's already built.** `docs/contracts.md`
  doesn't yet document `JudgeReliabilityMetrics` or `DashboardSnapshot`
  (implemented ahead of their contract, a documentation debt worth
  fixing). `gate/verdict.py` and `metrics/statistical_gating.py` each
  independently define an identical `bootstrap_delta_ci`, worth
  consolidating. These are good first contributions: scoped, well-defined,
  and don't require designing anything new.
- **Phase 6: evaluation and benchmarking.** `experiments/` has a working
  ablation and meta-evaluation notebook; extending its coverage (more
  configurations, real rather than synthetic gold-set data, external
  competitor comparison) is active, welcome work.
- **New capability work.** Phase 7 and beyond (integrity-checked
  evaluation, enterprise governance and metadata, production packaging and
  a CLI) are real but not yet contract-defined. If you want to work here,
  start with a Contract Change issue, not an implementation PR.

## How to Contribute Right Now

### 1. Start with an issue, not a pull request

Open an issue before writing code, even for something that feels small. A
short issue describing what you plan to build and which contract it
implements (or which existing gap it closes) saves both of us a wasted
pull request.

### 2. Pick work that matches an active or upcoming phase

Check `docs/contracts.md` for which phase's contracts are already defined
and stable. Phases 1 through 5 are implemented; Phase 6 is in progress;
Phase 7 onward are roadmap items without contracts yet. If you want to
work on something from a later phase because it's more interesting, that's
understandable, but flag it explicitly in your issue as "early work on
Phase N" so it's reviewed with the right expectations, not treated as if
it should merge immediately.

### 3. Follow the contracts, don't improvise around them

If you're implementing or modifying a component, it must implement the
relevant protocol exactly as defined in `docs/contracts.md`. If the
contract seems wrong, incomplete, or (as with `JudgeReliabilityMetrics`
and `DashboardSnapshot` today) simply undocumented for something that
already shipped, that's a legitimate finding, but the fix is a pull
request against `docs/contracts.md` first, discussed and merged on its
own, not a silent deviation in your implementation PR. A contract that
drifts from its own documentation defeats the entire point of writing it
down.

### 4. Respect the import direction rule

`docs/contracts.md` defines a one-way import direction across components
(instrumentation → orchestrator → metrics → trust → storage → regression →
gate → reporting). This is enforced by `ruff`'s `TID` rules and by
`import-linter` (`lint-imports`) in CI, but tooling catches syntax, not
intent. If your change requires importing "backwards," that's a signal the
shared type belongs in `storage/models.py` or `metrics/base.py`, not a
signal to add the import anyway.

## Development Setup

```bash
git clone https://github.com/Red1-Rahman/NiriZan.git
cd NiriZan
pip install -e ".[dev]"
```

This project targets Python 3.11 or later, per `pyproject.toml`
(`requires-python = ">=3.11"`). If you're on an earlier version, use
`pyenv` or a similar tool to get a supported interpreter.

### Before opening a pull request, run:

```bash
ruff check src tests
ruff format --check src tests
mypy
pytest
lint-imports
```

All five must pass. `mypy` is configured in `strict` mode project-wide
(see `pyproject.toml`), which means every function signature needs real
types, not `Any`. If you're not used to strict mypy, it will feel
unreasonably picky at first; that strictness is what keeps the plugin
boundaries in `docs/contracts.md` honest as the codebase grows past one
contributor.

## Code Standards

- **Typing:** Every public function and method has complete type
  annotations. `disallow_untyped_defs` and `disallow_any_generics` are
  both on in `pyproject.toml`; this isn't a style preference, it's
  enforced.
- **Data models:** Use `pydantic.BaseModel` for any structured data
  crossing a component boundary, matching the models in
  `docs/contracts.md` exactly. Don't invent a parallel dataclass or
  dict-shaped return value that happens to look similar.
- **Async:** Instrumentation and orchestration code is async by design
  (see Design Principle 2 in `ARCHITECTURE.md`: evaluation must never sit
  on the user-facing critical path). Don't introduce blocking calls into
  `instrumentation/` or `orchestrator/` without a specific, discussed
  reason.
- **Tests:** New code needs tests in the mirrored path under `tests/`,
  matching the module you're testing (e.g. `src/nirizan/metrics/rag_triad.py`
  → `tests/metrics/test_rag_triad.py`). A component with no test directory
  content is not considered complete, regardless of whether the code runs.
- **No circular imports:** Enforced by `ruff`'s `TID` rules,
  `import-linter`, and the import direction rule above. If CI flags a
  circular import, that's a design problem to fix, not a lint rule to
  suppress.

## Commit and PR Conventions

- Keep commits scoped to one logical change. A PR that touches
  `instrumentation/` and `reporting/` at the same time, with no shared
  cause, will be asked to split.
- Reference the phase and component your change belongs to in the PR
  description (e.g. "Phase 6: extends the evaluation notebook's gold-set
  coverage").
- If your change modifies a contract in `docs/contracts.md`, say so
  explicitly and explain whether it's additive (new optional field, safe)
  or breaking (removed/changed field, needs a version bump per the
  Versioning Rule at the end of that document).

## Code of Conduct

This project follows the Contributor Covenant. Participation in this
project, including issues, pull requests, and any other project spaces, is
governed by it. Report unacceptable behavior as described in
`CODE_OF_CONDUCT.md`.

## Licensing

NiriZan is licensed under the GNU General Public License v3 (or later). By
contributing, you agree that your contributions are licensed under the
same terms.

## What This Document Doesn't Cover Yet

This is a living document for an early-stage project, not a finished
contribution guide. Things it doesn't address yet, because the project
isn't far enough along for them to be real questions: a formal
review/maintainer-approval process beyond "the maintainer reviews it," a
governance model for when there's more than one regular contributor, and
a triage process for issues. These will be added as the project actually
reaches the point where they matter, not preemptively guessed at now. If
you hit one of these gaps in practice, that's useful signal, open an issue
about the gap itself.
