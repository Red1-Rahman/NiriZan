# Security Policy

## Project Status

NiriZan is an early-stage, independent open-source project (pre-1.0). There is no dedicated security team, no bug bounty program, and no service level agreement on response time. This document sets expectations honestly rather than gesturing at a formal process that does not exist yet. As the project matures, this policy will be revisited and tightened.

## Supported Versions

No version of NiriZan has reached a stable 1.0 release yet. Security fixes, when needed, will be applied to the latest commit on the default branch. There is no long-term support branch at this stage.

| Version | Supported |
|---|---|
| `main` (pre-release) | Yes, best effort |
| Tagged releases before 1.0 | No, upgrade to `main` |

This table will be replaced with a real support matrix once NiriZan has a stable release line.

## Reporting a Vulnerability

If you believe you have found a security vulnerability in NiriZan, please report it privately rather than opening a public GitHub issue. Public issues are fine for bugs; they are not fine for anything that could be actively exploited before a fix ships.

**To report privately:**
- Email **redwanrahman2002@outlook.com** with a description of the issue, steps to reproduce, and, if possible, an assessment of impact.
- If the repository has GitHub's private vulnerability reporting enabled by the time you read this, that is the preferred channel; check the repository's Security tab first.

Please include:
- The component affected, e.g. instrumentation, orchestration, metrics, trust/attribution, storage, regression, deployment gate, or reporting
- Whether the issue requires local access, network access, or a malicious input to trigger
- Any proof-of-concept code, kept minimal and non-destructive

**What to expect:**
- Acknowledgment of your report as soon as reasonably possible. As a single-maintainer project at this stage, that may not be within 24 hours, but it will not be ignored.
- No promise of a bounty or financial reward. Credit in the fix's changelog and release notes, if you want it.
- Coordinated disclosure: please give the maintainer a reasonable window to produce a fix before disclosing publicly. If you don't hear back after a genuinely reasonable effort to reach out, use your judgment; silence is not a demand for indefinite secrecy.

## Scope and Areas of Particular Concern

NiriZan is evaluation infrastructure that sits close to production AI traffic, which means certain classes of issue matter more here than in an average project:

- **Trace and payload data handling.** `instrumentation/` and `storage/` may capture prompts, retrieved context, and model outputs, some of which can contain sensitive user data. Vulnerabilities that leak trace contents across tenants, applications, or users are treated as high severity.
- **Judge and third-party API credentials.** The `metrics/llm_judge.py` module and similar integrations call out to external LLM providers. Any issue that could exfiltrate API keys, or that allows a crafted input to manipulate a judge prompt into leaking configuration or credentials (prompt injection against the judge itself), is in scope.
- **Deployment-Aware Gate integrity.** `gate/` produces the pass/fail signal that CI/CD pipelines rely on to block or allow a release, as described in `ARCHITECTURE.md` and `docs/contracts.md`. Any vulnerability that lets a `GateVerdict` be forged, bypassed, or manipulated to always return `passed: true` is treated as high severity, since it undermines the entire reason the project exists.
- **Attribution and anchor set tampering.** The Trust & Attribution Layer's `AnchorSet` (`trust/anchor_set.py`) is meant to be fixed and trustworthy per `docs/contracts.md`. Any way to modify an anchor set undetected, or to spoof `AttributionVerdict` output, defeats the judge-drift detection the layer exists to provide.

## Not a Security Report

General bugs, feature requests, and questions about usage belong in the repository's normal issue tracker, not in a private security report. If you are not sure whether something qualifies, err toward a private report; it costs little to be told "this is fine as a public issue."

## Dependencies

NiriZan's dependency versions are pinned with explicit lower and upper bounds in `pyproject.toml` specifically so that a vulnerable transitive dependency can be patched deliberately, with a version bump, rather than silently through an unpinned range. If you find a known-vulnerable dependency version in use, a report is welcome, but checking `pyproject.toml` against the relevant CVE database first is appreciated.
