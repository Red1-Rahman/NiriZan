<!--
Thanks for opening a PR. Phases 1-5 are implemented and CI-enforced;
Phase 6 (evaluation & benchmarking) is in progress. Please fill in every
section below rather than deleting what doesn't seem to apply; "N/A" is a
valid answer.
-->

## Summary

<!-- What does this PR do, in a sentence or two? -->

## Which phase does this belong to?

<!-- Match the issue templates' phase options. Pick one. -->

- [ ] Phase 1: Instrumentation & Trace Storage
- [ ] Phase 2: RAG Triad Metrics
- [ ] Phase 3: Experiment Tracking & Baselines
- [ ] Phase 4: Regression Detection & CI Gate
- [ ] Phase 5: Drift & Judge-Reliability Layer
- [ ] Phase 6: Evaluation Ablation & Benchmarking
- [ ] Not phase-specific (docs, tooling, dependency update, etc.)

## Related issue(s)

<!-- Link the issue(s) this PR closes or addresses, e.g. "Closes #12". -->

## Contract impact

<!--
Per docs/contracts.md and CONTRIBUTING.md: a change to any pydantic model
or plugin interface in docs/contracts.md is discussed and approved via a
Contract Change issue BEFORE the implementation PR, not alongside it. Note:
JudgeReliabilityMetrics and DashboardSnapshot currently ship without a
docs/contracts.md entry, a known, tracked gap; don't treat their existing
shape as precedent for skipping this process on new work.
-->

- [ ] This PR does **not** touch `docs/contracts.md`.
- [ ] This PR **does** touch `docs/contracts.md`, and the change was discussed and approved in Contract Change issue: #____

<!--
If this PR touches docs/contracts.md and there is no linked, approved
Contract Change issue, expect this PR to be asked to split into a
contract-change discussion first, per the process in CONTRIBUTING.md.
-->

## Import direction

<!-- Per docs/import-boundaries.md. -->

- [ ] I did not add any new cross-module imports.
- [ ] I added new cross-module import(s), and they follow the layer direction in `docs/import-boundaries.md` (`instrumentation → orchestrator → metrics → trust → storage → regression → gate → reporting`).

## Local checks

<!--
CI enforcement for human-authored PRs is not wired up yet. Until it is,
please confirm you've run these locally.
-->

- [ ] `pytest` passes
- [ ] `mypy --strict` passes
- [ ] `lint-imports` passes

## Contact (optional)

<!--
Optional. Leave blank if you'd rather not share it. If provided, this may
be used to reach out about this PR specifically (e.g. follow-up questions,
or potential paid/contract work related to this contribution).
-->

Email: ____

## Anything reviewers should look at closely?

<!-- Optional: tricky edge cases, deliberate tradeoffs, things you're unsure about. -->
