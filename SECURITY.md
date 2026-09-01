# Security Policy

## Project Status

NiriZan is an independent open-source project. The latest released version is `0.2.0`, published on PyPI on 2026-08-28. `0.3.0` is drafted (see `CHANGELOG.md`) and has not been released yet. The package is publicly available on PyPI and can be installed with:

```bash
pip install nirizan
```

NiriZan is pre-1.0 software. There is currently no dedicated security team, bug bounty program, or formal security response SLA. Security reports are handled on a best-effort basis by the project maintainer.

The project maintains automated security checks covering source-code security, static analysis, dependency vulnerabilities, package artifacts, secrets, and CI/CD workflows.

This policy describes the current security posture and reporting process. It will evolve as the project matures.

## Supported Versions

NiriZan currently has a single branch, `main`. There are no separate maintenance or long-term-support branches.

The latest released version is `0.2.0` (released 2026-08-28). Releases are published to PyPI via GitHub Actions Trusted Publishing and are not consistently marked with a git tag: `v0.1.0` has a corresponding tag, but `0.2.0` was published directly from a `main` commit with no tag created for it. `CHANGELOG.md`, not the repository's git tags, is the authoritative record of what has been released. `main` currently also carries the unreleased `0.3.0` changes described there.

| Version / Branch     | Supported          |
| --------------------- | ------------------- |
| `main` (incl. unreleased `0.3.0`) | Yes, best effort |
| `0.2.0` (latest released version)  | Yes, best effort |
| Older releases         | No, upgrade to the latest release |

Security fixes are developed on `main` and incorporated into subsequent releases as appropriate.

Because NiriZan is pre-1.0, there is currently no formal long-term-support policy.

## Reporting a Vulnerability

If you believe you have discovered a security vulnerability in NiriZan, please report it privately rather than opening a public GitHub issue.

### Private Reporting

The preferred channel is GitHub's private vulnerability reporting:

**[github.com/Red1-Rahman/NiriZan/security/advisories/new](https://github.com/Red1-Rahman/NiriZan/security/advisories/new)**

If you would rather not use GitHub, emailing is perfectly fine:

**redwanrahman2002@outlook.com**

Please include, where possible:

- The NiriZan version affected
- A description of the vulnerability
- Steps to reproduce the issue
- The expected and actual behavior
- The conditions required for exploitation
- The potential confidentiality, integrity, or availability impact
- A minimal, non-destructive proof of concept
- Relevant logs or error messages

If you are unsure whether an issue qualifies as a security vulnerability, err toward private disclosure.

### What to Expect

NiriZan is currently maintained independently and does not provide a guaranteed response SLA.

Credible reports will be investigated as soon as reasonably possible, depending on severity, complexity, and maintainer availability.

There is currently:

- No bug bounty program
- No guaranteed monetary reward
- No formal response-time guarantee
- No guaranteed remediation deadline

Security researchers may receive credit in release notes or other project documentation if they request it.

### Coordinated Disclosure

Please allow reasonable time for investigation and remediation before publicly disclosing a vulnerability.

The appropriate disclosure period depends on the severity and exploitability of the issue. Critical vulnerabilities may require expedited handling.

If the maintainer cannot be reached after a reasonable effort, researchers should use their judgment regarding responsible disclosure. Lack of response should not be interpreted as a requirement for indefinite secrecy.

## Scope and Areas of Particular Concern

NiriZan is evaluation infrastructure that may operate alongside production AI systems. Security issues affecting the confidentiality, integrity, or availability of evaluation data and results are therefore particularly important.

### Evaluation Data

Evaluation traces may contain application data such as prompts, retrieved context, model outputs, metadata, or other information supplied by the application.

Security vulnerabilities that could cause unauthorized access, unintended disclosure, cross-application data leakage, or unauthorized modification of evaluation data are in scope.

Applications using NiriZan remain responsible for deciding what information is appropriate to send into their evaluation pipeline.

### Evaluation Integrity

NiriZan can be used as part of automated evaluation and deployment workflows. Vulnerabilities that allow evaluation results or deployment decisions to be forged, bypassed, or manipulated are security-relevant.

This includes issues that could cause a deployment to be incorrectly considered safe, or to pass an evaluation that should have failed.

### Trust and Attribution Integrity

NiriZan includes mechanisms intended to help distinguish changes in the evaluated system from changes in the evaluation process.

Unauthorized modification or manipulation of trusted evaluation data, attribution results, or other integrity-sensitive evaluation state is therefore in scope.

### Credentials and External Services

Where NiriZan integrations use external services or credentials, vulnerabilities that expose credentials, redirect sensitive data, or allow malicious input to cross an intended security boundary are in scope.

Users should not commit API keys, tokens, passwords, or other credentials to the NiriZan repository.

### Supply Chain and CI/CD

Because NiriZan is distributed as a Python package, vulnerabilities affecting dependencies, package artifacts, build processes, GitHub Actions, or other parts of the software supply chain are security-relevant.

Compromise of the build or release process that could result in a malicious or unauthorized package artifact should be reported privately.

## Automated Security Controls

NiriZan maintains automated security checks as part of its development and CI/CD process.

The current security tooling includes:

- AST-based security regression tests for project-specific security invariants
- Bandit for Python security analysis
- flake8, dlint, and dodgy for additional source-level checks
- Semgrep for static security analysis
- CodeQL for code security analysis
- pip-audit for Python dependency vulnerabilities
- Google OSV Scanner for known vulnerabilities in project dependencies and files
- Trivy for filesystem and dependency security scanning
- GuardDog for suspicious or malicious package behavior
- VirusTotal for analysis of built distribution artifacts
- Gitleaks for accidental secret exposure
- Zizmor for GitHub Actions workflow security
- Dependabot for automated dependency update monitoring

These controls are intended to provide multiple layers of detection across source code, dependencies, package artifacts, secrets, and the project's software supply chain.

The security checks are automated safeguards, not a guarantee that the project is free from vulnerabilities.

## Dependency Management

NiriZan uses explicit dependency constraints in `pyproject.toml` and automated dependency monitoring.

Dependabot monitors both Python dependencies and GitHub Actions dependencies.

Dependency updates are validated by the project's automated test and quality checks before being incorporated.

Patch and minor dependency updates may be automatically merged when the configured checks pass. Major dependency updates require manual review because passing tests alone cannot establish compatibility or security for a major upstream change.

If a known vulnerable dependency materially affects the security of NiriZan, please report it privately. Including the relevant CVE, GHSA, or other advisory identifier is helpful.

## Not a Security Report

The following generally belong in the normal issue tracker rather than a private security report:

- Ordinary bugs without a security impact
- Feature requests
- Documentation issues
- General performance issues
- Questions about using NiriZan
- Security hardening suggestions that do not describe an exploitable vulnerability

If there is reasonable uncertainty about whether an issue is security-sensitive, private disclosure is preferred.

## Security Limitations

Automated security tooling cannot guarantee that NiriZan is vulnerability-free.

Security scanners may produce false positives or false negatives, and they cannot reliably detect every logical, architectural, or application-specific security issue.

In particular, passing the project's security checks does not constitute:

- A guarantee of security
- A formal security certification
- A guarantee that dependencies contain no undiscovered vulnerabilities
- A guarantee that published artifacts cannot be compromised
- A guarantee that an application's deployment environment is secure

Security is treated as an ongoing engineering concern, and the project's security controls will evolve alongside the software.

## Policy Changes

This policy will be updated as NiriZan develops stable release lines, broader adoption, additional integrations, or new deployment models.

Changes to the supported versions, reporting process, or security expectations will be reflected here as the project's security practices mature.
