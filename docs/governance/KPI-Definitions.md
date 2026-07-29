# NiriZan KPI Definitions

This document standardizes all metrics collected during pilot studies.

---

# Engineering KPIs

## Evaluation Time

Average time required to evaluate an AI system.

Unit:
minutes

Lower is better.

---

## Manual Review Time

Human hours spent reviewing outputs.

Unit:
hours/week

Lower is better.

---

## Deployment Confidence

Average confidence engineers have before releasing models.

Scale:
1–5

Higher is better.

---

## Mean Time to Detect (MTTD)

Average time required to detect AI regressions.

Unit:
minutes

Lower is better.

---

## Mean Time to Recovery (MTTR)

Average time required to resolve detected AI issues.

Unit:
hours

Lower is better.

---

# Cost KPIs

## Evaluation Cost

Monthly evaluation infrastructure cost.

Unit:
USD/month

Lower is better.

---

## Cost per Evaluation

Average cost for one evaluated trace.

Unit:
USD

Lower is better.

---

## Engineer Hours Saved

Difference between baseline and pilot.

Unit:
hours/month

Higher is better.

---

# Quality KPIs

## Groundedness

Measures factual consistency with retrieved evidence.

Scale:
0–1

Higher is better.

---

## Context Relevance

Measures usefulness of retrieved context.

Scale:
0–1

Higher is better.

---

## Answer Relevance

Measures response quality.

Scale:
0–1

Higher is better.

---

## Hallucination Rate

Percentage of hallucinated responses.

Lower is better.

---

## Regression Detection Rate

Percentage of regressions detected before deployment.

Higher is better.

---

## Judge Agreement

Agreement between lightweight and LLM judges.

Higher is better.

---

## Drift Detection Accuracy

Percentage of correctly identified drift events.

Higher is better.

---

# Business KPIs

## Production Incidents

Number of AI incidents reaching production.

Lower is better.

---

## Release Frequency

Deployments per month.

Higher is better.

---

## Monitoring Cost Reduction

Baseline vs Pilot.

Formula:

((Baseline - Pilot) / Baseline) × 100

Higher is better.

---

## Productivity Gain

Engineer hours saved due to automated evaluation.

Higher is better.

---

## User Satisfaction

Likert Scale

1–5

Higher is better.
