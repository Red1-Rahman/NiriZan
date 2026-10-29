# Security regression suite

Run Python checks with `pytest tests/security/`. The manually dispatched workflow
also runs the independent Node static checks under `tests/security/js/`.

`xfail(strict=True)` marks a finding that currently reproduces an accepted or
tracked weakness. A fix turns it into XPASS and fails the manual run so the
finding can be reviewed and its exception removed. Each ID is defined in
`js/known-findings.json`.

| Finding | Test |
|---|---|
| NZ-SEC-002 | `test_otel_service_name_is_bound_to_a_producer_identity` |
| NZ-SEC-003 | `test_trace_upsert_rejects_application_name_takeover` |
| NZ-SEC-004 | `test_native_tracer_retains_only_bounded_span_history` |
| NZ-SEC-005 | `test_cohens_d_rejects_single_observation_samples` |
| NZ-SEC-006 | `test_judge_rejects_nonfinite_or_out_of_range_scores` |
| NZ-SEC-007 | `test_trace_collector_queue_has_a_finite_capacity` |
| NZ-SEC-008 | `test_formatted_logs_escape_injected_crlf` |

Cross-trace span ID collision rejection is a passing check for the remediation
documented in `docs/contracts.md`.
