# Data Policy

> Version: 1.0   
Applies to: All NiriZan deployments, pilot programs, and research studies.

---

# Purpose

NiriZan is an AI evaluation platform designed to improve the reliability, safety, and quality of production AI systems.

This document explains what data NiriZan collects, why it is collected, how it is protected, and the rights of organizations participating in evaluations.

This policy aligns with:

- ACM Code of Ethics and Professional Conduct
- Contributor Covenant
- GPL License
- Applicable privacy regulations

---

# Data Minimization

NiriZan follows the principle of collecting only the minimum amount of information required to perform evaluation.

Whenever possible, evaluation is performed using metadata instead of sensitive business content.

---

# Data We Collect

## System Metadata

- Timestamp
- Trace ID
- Session ID
- Model Version
- Prompt Version
- Evaluation Version

---

## Performance Metrics

- Latency
- Token Usage
- Cost Estimate
- Memory Usage
- CPU Usage
- GPU Usage
- Retrieval Latency

---

## Evaluation Metrics

- Groundedness
- Context Relevance
- Answer Relevance
- Hallucination Score
- Drift Score
- Judge Confidence
- Regression Score

---

## Optional Trace Data

Organizations may optionally enable:

- Prompt
- Model Response
- Retrieved Documents
- Tool Calls

These fields are disabled by default for enterprise deployments.

---

# Data We Never Collect

NiriZan never intentionally collects:

- Passwords
- API Keys
- Authentication Tokens
- Credit Card Information
- Personal Banking Information
- Government Identification Numbers

Organizations are responsible for preventing sensitive information from entering prompts where possible.

---

# Ownership

Organizations retain ownership of all submitted data.

NiriZan claims no ownership over customer data.

---

# Data Retention

Recommended defaults:

Raw traces:
90 days

Aggregated metrics:
1 year

Anonymous benchmark statistics:
Unlimited (non-identifiable only)

Organizations may configure custom retention periods.

---

# Data Sharing

NiriZan does not sell collected data.

Data is never shared with third parties without explicit written permission.

---

# Research Usage

Pilot participants may voluntarily opt-in to anonymous research.

Published research will:

- remove identifying information
- aggregate statistics
- avoid disclosure of confidential business information

unless explicit permission is granted.

---

# Security

Recommended deployment practices:

- TLS encryption
- Encryption at rest
- Role-based access control
- Audit logging
- Secret management
- Regular dependency updates

---

# Responsible Disclosure

Security issues should be reported according to SECURITY.md.

---

# Contact

Redwan Rahman
redwanrahman2002@outlook.com
