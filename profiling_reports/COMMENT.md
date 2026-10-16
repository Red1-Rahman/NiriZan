<!-- nirizan-profiling-report -->
### ⏱️ NiriZan Profiling Report

`cProfile` + `pstats` over the test suite, split per module. Timings include profiler overhead: use them for *relative* comparison.

| Module | Functions run | Internal time (s) | Never executed |
| :--- | ---: | ---: | ---: |
| `metrics/stats.py` | 23 | 0.403086 | 0 |
| `storage/models.py` | 18 | 0.066654 | 0 |
| `instrumentation/otel/_id_mapping.py` | 8 | 0.027866 | 0 |
| `instrumentation/otel/semconv.py` | 8 | 0.017153 | 0 |
| `regression/multivariate.py` | 26 | 0.008792 | 0 |
| `instrumentation/spans.py` | 8 | 0.005008 | 0 |
| `storage/trace_repository.py` | 12 | 0.001835 | 12 |
| `trust/attribution.py` | 10 | 0.001227 | 0 |
| `gate/verdict.py` | 10 | 0.001197 | 0 |
| `orchestrator/collector.py` | 13 | 0.000652 | 1 |
| `regression/comparator.py` | 10 | 0.000448 | 0 |
| `reporting/judge_reliability.py` | 25 | 0.000384 | 0 |
| `instrumentation/tracer.py` | 8 | 0.000374 | 1 |
| `gate/ci.py` | 5 | 0.000257 | 0 |
| `storage/experiment_store.py` | 15 | 0.000248 | 5 |
| `reporting/dashboard.py` | 4 | 0.000189 | 0 |
| `storage/baselines.py` | 13 | 0.000181 | 6 |
| `metrics/rag_triad.py` | 6 | 0.000152 | 0 |
| `regression/thresholds.py` | 4 | 0.000151 | 0 |
| `instrumentation/sdk.py` | 12 | 0.000137 | 0 |
| `metrics/lightweight_judge.py` | 7 | 0.000102 | 1 |
| `metrics/behavioral_anchor.py` | 4 | 0.000090 | 1 |
| `metrics/llm_judge.py` | 5 | 0.000089 | 0 |
| `metrics/statistical_gating.py` | 7 | 0.000081 | 0 |
| `reporting/health_score.py` | 2 | 0.000071 | 0 |
| `_logging.py` | 4 | 0.000052 | 5 |
| `orchestrator/loop_sink.py` | 6 | 0.000047 | 1 |
| `metrics/base.py` | 4 | 0.000041 | 2 |
| `instrumentation/exporters.py` | 9 | 0.000035 | 2 |
| `orchestrator/scheduler.py` | 6 | 0.000034 | 2 |
| `trust/anchor_set.py` | 3 | 0.000030 | 0 |
| `orchestrator/dispatcher.py` | 5 | 0.000028 | 0 |
| `storage/run_repository.py` | 6 | 0.000015 | 2 |
| `instrumentation/otel/from_otel.py` | 0 | 0.000000 | 76 |
| `instrumentation/otel/to_otel.py` | 0 | 0.000000 | 20 |
| `instrumentation/sessions.py` | 0 | 0.000000 | 0 |
| `storage/session_repository.py` | 0 | 0.000000 | 5 |

#### Top 15 functions per module

<details>
<summary><code>src/nirizan/metrics/stats.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `_permutation_distribution` | 356 | 47 | 0.100917 | 0.002147 | 4.254249 | 0.090516 | other 0.004685s, numpy 0.004231s, frozen/internal 0.000070s |
| `dependence_max_t_test` | 542 | 24 | 0.000347 | 0.000014 | 4.074699 | 0.169779 | - |
| `_dependence_max_t_from_groups` | 497 | 3566 | 0.037561 | 0.000011 | 3.993870 | 0.001120 | numpy 0.176519s, built-ins (C) 0.015307s |
| `_rank_columns` | 459 | 7172 | 0.062944 | 0.000009 | 3.458403 | 0.000482 | scipy 3.394466s, numpy 0.000994s |
| `<module> (import time)` | 1 | 1 | 0.000041 | 0.000041 | 1.372570 | 1.372570 | frozen/internal 1.372491s |
| `_pearson_from_ranks` | 480 | 7132 | 0.149394 | 0.000021 | 0.327179 | 0.000046 | built-ins (C) 0.131735s, numpy 0.046051s |
| `scale_logvar_test` | 421 | 26 | 0.000328 | 0.000013 | 0.197166 | 0.007583 | built-ins (C) 0.000537s |
| `<lambda>` | 448 | 3572 | 0.001938 | 0.000001 | 0.155766 | 0.000044 | - |
| `_scale_logvar_from_arrays` | 408 | 3579 | 0.018706 | 0.000005 | 0.154256 | 0.000043 | built-ins (C) 0.135550s |
| `bootstrap_delta_ci` | 142 | 80 | 0.022143 | 0.000277 | 0.066979 | 0.000837 | numpy 0.040366s, frozen/internal 0.000108s, stdlib:threading 0.000069s |
| `mann_whitney_regression` | 174 | 48 | 0.000332 | 0.000007 | 0.062967 | 0.001312 | scipy 0.060296s, built-ins (C) 0.000013s, stdlib:typing 0.000005s |
| `validate_scores` | 42 | 485 | 0.004544 | 0.000009 | 0.013192 | 0.000027 | numpy 0.004762s, built-ins (C) 0.002377s, stdlib:logging 0.001508s |
| `permutation_test` | 307 | 10 | 0.000030 | 0.000003 | 0.007835 | 0.000783 | - |
| `dependence_max_t_statistic` | 516 | 6 | 0.000014 | 0.000002 | 0.005617 | 0.000936 | - |
| `validate_score_matrix` | 57 | 166 | 0.001623 | 0.000010 | 0.004250 | 0.000026 | numpy 0.001808s, built-ins (C) 0.000819s |

</details>

<details>
<summary><code>src/nirizan/storage/models.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000038 | 0.000038 | 1.631420 | 1.631420 | frozen/internal 1.624845s, built-ins (C) 0.006514s |
| `TraceRecord.from_trace` | 143 | 59 | 0.000362 | 0.000006 | 0.148964 | 0.002525 | pydantic 0.000395s, stdlib:uuid 0.000228s |
| `<listcomp>` | 149 | 57 | 0.004255 | 0.000075 | 0.147461 | 0.002587 | - |
| `SpanRecord.from_span` | 100 | 8041 | 0.031679 | 0.000004 | 0.143321 | 0.000018 | stdlib:json 0.031157s, stdlib:uuid 0.016736s, pydantic 0.015629s |
| `TraceRecord.to_trace` | 155 | 84 | 0.000505 | 0.000006 | 0.061364 | 0.000731 | pydantic 0.001168s, stdlib:uuid 0.000585s |
| `<listcomp>` | 176 | 81 | 0.001321 | 0.000016 | 0.058352 | 0.000720 | - |
| `SpanRecord.to_span` | 115 | 2862 | 0.011411 | 0.000004 | 0.057124 | 0.000020 | stdlib:uuid 0.017252s, stdlib:json 0.011547s, pydantic 0.006440s |
| `_utc_isoformat` | 47 | 16142 | 0.012287 | 0.000001 | 0.044342 | 0.000003 | built-ins (C) 0.032055s |
| `_parse_utc_datetime` | 54 | 5823 | 0.004694 | 0.000001 | 0.009033 | 0.000002 | built-ins (C) 0.003645s |
| `_warn_legacy_naive_once` | 75 | 18 | 0.000023 | 0.000001 | 0.000693 | 0.000039 | stdlib:logging 0.000648s |
| `Run` | 183 | 1 | 0.000012 | 0.000012 | 0.000105 | 0.000105 | pydantic 0.000092s |
| `Baseline` | 197 | 1 | 0.000010 | 0.000010 | 0.000059 | 0.000059 | pydantic 0.000049s |
| `TraceRecord` | 132 | 1 | 0.000013 | 0.000013 | 0.000042 | 0.000042 | pydantic 0.000030s |
| `_OnceLatch.claim` | 33 | 18 | 0.000020 | 0.000001 | 0.000023 | 0.000001 | built-ins (C) 0.000003s |
| `SpanRecord` | 86 | 1 | 0.000012 | 0.000012 | 0.000020 | 0.000020 | pydantic 0.000008s |

</details>

<details>
<summary><code>src/nirizan/instrumentation/otel/_id_mapping.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `otel_trace_id_to_derived_uuid` | 94 | 10013 | 0.010745 | 0.000001 | 0.081738 | 0.000008 | stdlib:uuid 0.064834s |
| `otel_span_id_to_uuid` | 142 | 5016 | 0.010346 | 0.000002 | 0.031642 | 0.000006 | stdlib:uuid 0.014280s, built-ins (C) 0.003898s |
| `is_valid_otel_trace_id` | 38 | 10069 | 0.004440 | 0.000000 | 0.006211 | 0.000001 | built-ins (C) 0.001772s |
| `is_valid_otel_span_id` | 51 | 5040 | 0.002260 | 0.000000 | 0.003142 | 0.000001 | built-ins (C) 0.000882s |
| `otel_trace_id_to_uuid` | 76 | 20 | 0.000038 | 0.000002 | 0.000092 | 0.000005 | stdlib:uuid 0.000036s |
| `uuid_to_otel_trace_id` | 64 | 17 | 0.000014 | 0.000001 | 0.000034 | 0.000002 | stdlib:uuid 0.000004s |
| `<module> (import time)` | 1 | 1 | 0.000015 | 0.000015 | 0.000032 | 0.000032 | stdlib:uuid 0.000018s |
| `uuid_to_otel_span_id` | 123 | 6 | 0.000008 | 0.000001 | 0.000017 | 0.000003 | stdlib:uuid 0.000003s |

</details>

<details>
<summary><code>src/nirizan/instrumentation/otel/semconv.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `encode_sequence_attribute_value` | 305 | 623 | 0.010147 | 0.000016 | 0.037854 | 0.000061 | built-ins (C) 0.002913s, other 0.000170s |
| `_dumps_item` | 297 | 7679 | 0.002173 | 0.000000 | 0.024199 | 0.000003 | - |
| `dumps_attribute_json` | 267 | 8072 | 0.004764 | 0.000001 | 0.022663 | 0.000003 | stdlib:json 0.016588s, built-ins (C) 0.001311s |
| `<module> (import time)` | 1 | 1 | 0.000035 | 0.000035 | 0.000038 | 0.000038 | stdlib:json 0.000003s |
| `encode_sequence_key` | 235 | 9 | 0.000012 | 0.000001 | 0.000017 | 0.000002 | built-ins (C) 0.000001s |
| `truncate_attribute_value` | 201 | 7 | 0.000011 | 0.000002 | 0.000012 | 0.000002 | built-ins (C) 0.000002s |
| `decode_sequence_key` | 248 | 5 | 0.000006 | 0.000001 | 0.000010 | 0.000002 | - |
| `is_sequence_key` | 255 | 13 | 0.000006 | 0.000000 | 0.000010 | 0.000001 | built-ins (C) 0.000004s |

</details>

<details>
<summary><code>src/nirizan/regression/multivariate.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `MultivariateComparator.compare` | 389 | 29 | 0.001048 | 0.000036 | 2.594953 | 0.089481 | pydantic 0.000331s, stdlib:logging 0.000144s, stdlib:enum 0.000047s |
| `MultivariateComparator.compare_metric_results` | 554 | 5 | 0.000049 | 0.000010 | 0.181629 | 0.036326 | stdlib:logging 0.000540s |
| `ScoreMatrix.from_metric_results` | 165 | 61 | 0.004413 | 0.000072 | 0.016365 | 0.000268 | built-ins (C) 0.007564s, pydantic 0.001571s, stdlib:uuid 0.000782s |
| `<module> (import time)` | 1 | 1 | 0.000029 | 0.000029 | 0.006916 | 0.006916 | built-ins (C) 0.006858s, frozen/internal 0.000004s |
| `ScoreMatrix.validate_contract` | 144 | 60 | 0.000188 | 0.000003 | 0.001511 | 0.000025 | built-ins (C) 0.000023s |
| `<genexpr>` | 217 | 3948 | 0.001071 | 0.000000 | 0.001258 | 0.000000 | built-ins (C) 0.000187s |
| `<dictcomp>` | 439 | 17 | 0.000110 | 0.000006 | 0.000902 | 0.000053 | built-ins (C) 0.000792s |
| `derive_permutation_seed` | 343 | 41 | 0.000588 | 0.000014 | 0.000823 | 0.000020 | numpy 0.000225s, stdlib:uuid 0.000011s |
| `MultivariateComparator._complete_case_metric_deltas` | 643 | 4 | 0.000020 | 0.000005 | 0.000776 | 0.000194 | - |
| `<genexpr>` | 213 | 3959 | 0.000515 | 0.000000 | 0.000515 | 0.000000 | - |
| `<listcomp>` | 216 | 1178 | 0.000338 | 0.000000 | 0.000338 | 0.000000 | - |
| `MultivariateConfig` | 83 | 1 | 0.000025 | 0.000025 | 0.000310 | 0.000310 | pydantic 0.000286s |
| `MultivariateComparator.__init__` | 378 | 35 | 0.000119 | 0.000003 | 0.000276 | 0.000008 | stdlib:logging 0.000086s, stdlib:enum 0.000054s, pydantic 0.000016s |
| `<dictcomp>` | 671 | 3 | 0.000019 | 0.000006 | 0.000138 | 0.000046 | built-ins (C) 0.000119s |
| `ScoreMatrix` | 126 | 1 | 0.000014 | 0.000014 | 0.000101 | 0.000101 | pydantic 0.000087s |

</details>

<details>
<summary><code>src/nirizan/instrumentation/spans.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000013 | 0.000013 | 0.024417 | 0.024417 | built-ins (C) 0.024360s, frozen/internal 0.000044s |
| `Trace.validate_span_trace_ids` | 64 | 82 | 0.002872 | 0.000035 | 0.008858 | 0.000108 | stdlib:uuid 0.002083s |
| `<setcomp>` | 77 | 82 | 0.002044 | 0.000025 | 0.003901 | 0.000048 | stdlib:uuid 0.001857s |
| `Trace` | 51 | 1 | 0.000015 | 0.000015 | 0.000136 | 0.000136 | pydantic 0.000121s |
| `Span` | 34 | 1 | 0.000019 | 0.000019 | 0.000091 | 0.000091 | pydantic 0.000072s |
| `SpanKind` | 25 | 1 | 0.000004 | 0.000004 | 0.000046 | 0.000046 | stdlib:enum 0.000042s |
| `Trace.spans_of_kind` | 93 | 25 | 0.000024 | 0.000001 | 0.000042 | 0.000002 | - |
| `<listcomp>` | 95 | 25 | 0.000018 | 0.000001 | 0.000018 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/storage/trace_repository.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `SQLiteTraceRepository.__init__` | 166 | 63 | 0.000342 | 0.000005 | 0.395388 | 0.006276 | built-ins (C) 0.006227s, stdlib:threading 0.000053s |
| `SQLiteTraceRepository._init_db` | 174 | 63 | 0.000330 | 0.000005 | 0.388766 | 0.006171 | built-ins (C) 0.388436s |
| `SQLiteTraceRepository.save` | 218 | 113 | 0.000277 | 0.000002 | 0.161302 | 0.001427 | stdlib:asyncio 0.012089s |
| `SQLiteTraceRepository.get` | 326 | 130 | 0.000402 | 0.000003 | 0.065588 | 0.000505 | stdlib:asyncio 0.005605s, stdlib:uuid 0.000198s |
| `SQLiteTraceRepository.list_by_application` | 361 | 38 | 0.000113 | 0.000003 | 0.003902 | 0.000103 | stdlib:asyncio 0.001959s |
| `SQLiteTraceRepository.close` | 479 | 63 | 0.000190 | 0.000003 | 0.002635 | 0.000042 | built-ins (C) 0.002445s |
| `SQLiteTraceRepository.purge_older_than` | 407 | 20 | 0.000063 | 0.000003 | 0.002077 | 0.000104 | stdlib:asyncio 0.001861s |
| `<listcomp>` | 405 | 19 | 0.000044 | 0.000002 | 0.001830 | 0.000096 | - |
| `_normalize_cutoff_to_utc` | 18 | 11 | 0.000045 | 0.000004 | 0.000132 | 0.000012 | built-ins (C) 0.000087s |
| `<module> (import time)` | 1 | 1 | 0.000021 | 0.000021 | 0.000077 | 0.000077 | built-ins (C) 0.000056s |
| `BaseTraceRepository` | 125 | 1 | 0.000005 | 0.000005 | 0.000006 | 0.000006 | - |
| `SQLiteTraceRepository` | 163 | 1 | 0.000003 | 0.000003 | 0.000003 | 0.000003 | - |

</details>

<details>
<summary><code>src/nirizan/trust/attribution.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `AttributionEngine._shift_evidence` | 90 | 51 | 0.000276 | 0.000005 | 0.075907 | 0.001488 | stdlib:unittest 0.000202s, built-ins (C) 0.000010s |
| `AttributionEngine.analyze` | 149 | 41 | 0.000781 | 0.000019 | 0.074914 | 0.001827 | stdlib:unittest 0.000524s, pydantic 0.000245s, built-ins (C) 0.000087s |
| `<module> (import time)` | 1 | 1 | 0.000018 | 0.000018 | 0.001835 | 0.001835 | built-ins (C) 0.001815s, frozen/internal 0.000002s |
| `AttributionEngine.__init__` | 66 | 54 | 0.000061 | 0.000001 | 0.000061 | 0.000001 | - |
| `DriftAttribution` | 18 | 1 | 0.000004 | 0.000004 | 0.000061 | 0.000061 | stdlib:enum 0.000057s |
| `AttributionEngine._is_significant` | 136 | 64 | 0.000025 | 0.000000 | 0.000031 | 0.000000 | built-ins (C) 0.000006s |
| `<dictcomp>` | 203 | 32 | 0.000027 | 0.000001 | 0.000027 | 0.000001 | - |
| `AttributionEngine.analyze.<locals>._p_str` | 217 | 22 | 0.000024 | 0.000001 | 0.000024 | 0.000001 | - |
| `AttributionVerdict` | 26 | 1 | 0.000007 | 0.000007 | 0.000012 | 0.000012 | pydantic 0.000005s |
| `AttributionEngine` | 43 | 1 | 0.000005 | 0.000005 | 0.000005 | 0.000005 | - |

</details>

<details>
<summary><code>src/nirizan/gate/verdict.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `evaluate_gate` | 182 | 16 | 0.000170 | 0.000011 | 0.025445 | 0.001590 | stdlib:logging 0.001897s, pydantic 0.000112s, built-ins (C) 0.000005s |
| `bootstrap_delta_ci` | 74 | 19 | 0.000803 | 0.000042 | 0.024170 | 0.001272 | stdlib:logging 0.000529s, built-ins (C) 0.000018s |
| `<module> (import time)` | 1 | 1 | 0.000029 | 0.000029 | 0.017336 | 0.017336 | frozen/internal 0.015309s, built-ins (C) 0.001977s |
| `select_decision_metric` | 136 | 17 | 0.000048 | 0.000003 | 0.000266 | 0.000016 | stdlib:logging 0.000144s, built-ins (C) 0.000055s, stdlib:enum 0.000019s |
| `_comparison_identity` | 166 | 16 | 0.000056 | 0.000003 | 0.000100 | 0.000006 | built-ins (C) 0.000044s |
| `GateVerdict` | 46 | 1 | 0.000009 | 0.000009 | 0.000049 | 0.000049 | pydantic 0.000040s |
| `<genexpr>` | 177 | 51 | 0.000025 | 0.000000 | 0.000027 | 0.000001 | stdlib:uuid 0.000002s |
| `<listcomp>` | 224 | 14 | 0.000027 | 0.000002 | 0.000027 | 0.000002 | - |
| `<lambda>` | 152 | 28 | 0.000021 | 0.000001 | 0.000021 | 0.000001 | - |
| `<listcomp>` | 227 | 14 | 0.000008 | 0.000001 | 0.000008 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/orchestrator/collector.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `TraceCollector.__init__` | 45 | 17 | 0.000085 | 0.000005 | 0.023038 | 0.001355 | stdlib:asyncio 0.000095s |
| `_resolve_code_commit` | 14 | 17 | 0.000114 | 0.000007 | 0.022751 | 0.001338 | stdlib:subprocess 0.022547s, frozen/internal 0.000086s, built-ins (C) 0.000004s |
| `TraceCollector._process_queue` | 84 | 57 | 0.000241 | 0.000004 | 0.008626 | 0.000151 | stdlib:asyncio 0.001294s, other 0.000677s, stdlib:logging 0.000412s |
| `TraceCollector.enqueue_trace` | 74 | 26 | 0.000064 | 0.000002 | 0.000606 | 0.000023 | pydantic 0.000323s, stdlib:asyncio 0.000219s |
| `CollectorExporter.export` | 103 | 18 | 0.000022 | 0.000001 | 0.000475 | 0.000026 | - |
| `TraceCollector.start` | 56 | 16 | 0.000038 | 0.000002 | 0.000300 | 0.000019 | stdlib:asyncio 0.000262s |
| `TraceCollector.stop` | 63 | 32 | 0.000041 | 0.000001 | 0.000170 | 0.000005 | stdlib:asyncio 0.000093s, built-ins (C) 0.000036s |
| `<module> (import time)` | 1 | 1 | 0.000021 | 0.000021 | 0.000130 | 0.000130 | built-ins (C) 0.000087s, stdlib:logging 0.000020s, stdlib:typing 0.000002s |
| `_resolve_data_snapshot_id` | 31 | 17 | 0.000018 | 0.000001 | 0.000107 | 0.000006 | frozen/internal 0.000089s |
| `CollectorExporter.__init__` | 100 | 12 | 0.000005 | 0.000000 | 0.000005 | 0.000000 | - |
| `TraceCollector` | 42 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `CollectorExporter` | 97 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `TraceSink` | 36 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/regression/comparator.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `BaselineComparator.compare_metric` | 97 | 15 | 0.000241 | 0.000016 | 0.023608 | 0.001574 | stdlib:logging 0.000822s, pydantic 0.000104s, stdlib:enum 0.000018s |
| `BaselineComparator.compare` | 162 | 7 | 0.000091 | 0.000013 | 0.018995 | 0.002714 | stdlib:logging 0.000682s, pydantic 0.000015s, built-ins (C) 0.000013s |
| `<module> (import time)` | 1 | 1 | 0.000023 | 0.000023 | 0.003374 | 0.003374 | built-ins (C) 0.002488s, frozen/internal 0.000846s |
| `mean_delta` | 43 | 18 | 0.000023 | 0.000001 | 0.000403 | 0.000022 | built-ins (C) 0.000381s |
| `RegressionVerdict` | 30 | 1 | 0.000014 | 0.000014 | 0.000071 | 0.000071 | pydantic 0.000057s |
| `BaselineComparator.__init__` | 76 | 10 | 0.000020 | 0.000002 | 0.000061 | 0.000006 | stdlib:logging 0.000041s |
| `RegressionSeverity` | 24 | 1 | 0.000003 | 0.000003 | 0.000041 | 0.000041 | stdlib:enum 0.000038s |
| `classify_severity` | 50 | 23 | 0.000026 | 0.000001 | 0.000026 | 0.000001 | - |
| `<dictcomp>` | 199 | 5 | 0.000006 | 0.000001 | 0.000006 | 0.000001 | - |
| `BaselineComparator` | 75 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/reporting/judge_reliability.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000016 | 0.000016 | 0.004266 | 0.004266 | built-ins (C) 0.004224s, frozen/internal 0.000003s |
| `compute_judge_reliability` | 76 | 14 | 0.000181 | 0.000013 | 0.001673 | 0.000119 | stdlib:logging 0.001164s, built-ins (C) 0.000157s, pydantic 0.000070s |
| `JudgeReliabilityMetrics` | 24 | 1 | 0.000017 | 0.000017 | 0.000164 | 0.000164 | pydantic 0.000146s |
| `_std` | 49 | 10 | 0.000017 | 0.000002 | 0.000043 | 0.000004 | built-ins (C) 0.000026s |
| `JudgeReliabilityStatus` | 17 | 1 | 0.000003 | 0.000003 | 0.000032 | 0.000032 | stdlib:enum 0.000029s |
| `<genexpr>` | 98 | 20 | 0.000020 | 0.000001 | 0.000020 | 0.000001 | - |
| `_mean` | 45 | 12 | 0.000011 | 0.000001 | 0.000019 | 0.000002 | built-ins (C) 0.000008s |
| `<genexpr>` | 103 | 16 | 0.000014 | 0.000001 | 0.000014 | 0.000001 | - |
| `<genexpr>` | 52 | 31 | 0.000012 | 0.000000 | 0.000012 | 0.000000 | - |
| `<genexpr>` | 147 | 38 | 0.000012 | 0.000000 | 0.000012 | 0.000000 | - |
| `<listcomp>` | 159 | 10 | 0.000011 | 0.000001 | 0.000011 | 0.000001 | - |
| `<setcomp>` | 87 | 13 | 0.000011 | 0.000001 | 0.000011 | 0.000001 | - |
| `judge_score_delta_series` | 56 | 1 | 0.000002 | 0.000002 | 0.000011 | 0.000011 | built-ins (C) 0.000009s |
| `<listcomp>` | 117 | 11 | 0.000010 | 0.000001 | 0.000010 | 0.000001 | - |
| `<genexpr>` | 110 | 26 | 0.000010 | 0.000000 | 0.000010 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/instrumentation/tracer.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `Tracer.start_span` | 55 | 48 | 0.000237 | 0.000005 | 0.001356 | 0.000028 | stdlib:uuid 0.000237s, pydantic 0.000158s, built-ins (C) 0.000088s |
| `<module> (import time)` | 1 | 1 | 0.000028 | 0.000028 | 0.000467 | 0.000467 | stdlib:dataclasses 0.000385s, built-ins (C) 0.000054s |
| `Tracer.get_assembled_trace` | 120 | 14 | 0.000055 | 0.000004 | 0.000350 | 0.000025 | pydantic 0.000214s, built-ins (C) 0.000035s |
| `Tracer.session` | 45 | 8 | 0.000011 | 0.000001 | 0.000059 | 0.000007 | stdlib:uuid 0.000044s, built-ins (C) 0.000005s |
| `<listcomp>` | 123 | 14 | 0.000026 | 0.000002 | 0.000046 | 0.000003 | stdlib:uuid 0.000020s |
| `Tracer` | 33 | 1 | 0.000009 | 0.000009 | 0.000024 | 0.000024 | stdlib:contextlib 0.000015s |
| `Tracer.__init__` | 36 | 9 | 0.000006 | 0.000001 | 0.000006 | 0.000001 | - |
| `SpanHandle` | 25 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/gate/ci.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `gate_exit_code` | 87 | 4 | 0.000035 | 0.000009 | 0.000648 | 0.000162 | stdlib:logging 0.000613s |
| `serialize_gate_verdict` | 95 | 3 | 0.000023 | 0.000008 | 0.000639 | 0.000213 | stdlib:json 0.000432s, stdlib:logging 0.000119s, pydantic 0.000065s |
| `write_github_summary` | 70 | 4 | 0.000017 | 0.000004 | 0.000420 | 0.000105 | stdlib:logging 0.000325s, built-ins (C) 0.000002s |
| `format_gate_summary` | 23 | 12 | 0.000170 | 0.000014 | 0.000218 | 0.000018 | stdlib:enum 0.000033s, built-ins (C) 0.000014s |
| `<module> (import time)` | 1 | 1 | 0.000012 | 0.000012 | 0.000033 | 0.000033 | - |

</details>

<details>
<summary><code>src/nirizan/storage/experiment_store.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `SQLiteExperimentStore.__init__` | 35 | 5 | 0.000019 | 0.000004 | 0.014557 | 0.002911 | built-ins (C) 0.000453s |
| `SQLiteExperimentStore._init_db` | 41 | 5 | 0.000019 | 0.000004 | 0.014085 | 0.002817 | built-ins (C) 0.014066s |
| `<module> (import time)` | 1 | 1 | 0.000018 | 0.000018 | 0.001175 | 0.001175 | built-ins (C) 0.001153s, frozen/internal 0.000003s |
| `SQLiteExperimentStore.record_run` | 59 | 12 | 0.000041 | 0.000003 | 0.001096 | 0.000091 | stdlib:asyncio 0.000812s, stdlib:json 0.000107s |
| `SQLiteExperimentStore.get_run` | 83 | 12 | 0.000061 | 0.000005 | 0.000773 | 0.000064 | stdlib:asyncio 0.000493s, stdlib:uuid 0.000061s, stdlib:json 0.000057s |
| `SQLiteExperimentStore.diff` | 109 | 6 | 0.000023 | 0.000004 | 0.000478 | 0.000080 | pydantic 0.000005s, stdlib:uuid 0.000005s |
| `SQLiteExperimentStore.close` | 122 | 5 | 0.000008 | 0.000002 | 0.000175 | 0.000035 | built-ins (C) 0.000167s |
| `<listcomp>` | 60 | 6 | 0.000025 | 0.000004 | 0.000137 | 0.000023 | pydantic 0.000111s |
| `<listcomp>` | 96 | 4 | 0.000021 | 0.000005 | 0.000079 | 0.000020 | pydantic 0.000059s |
| `RunDiff` | 16 | 1 | 0.000007 | 0.000007 | 0.000013 | 0.000013 | pydantic 0.000006s |
| `<dictcomp>` | 115 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `SQLiteExperimentStore` | 32 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `ExperimentStore` | 26 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `<dictcomp>` | 119 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `<dictcomp>` | 116 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/reporting/dashboard.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000025 | 0.000025 | 0.013066 | 0.013066 | frozen/internal 0.010009s, built-ins (C) 0.003011s |
| `assemble_dashboard_snapshot` | 51 | 16 | 0.000148 | 0.000009 | 0.001614 | 0.000101 | stdlib:logging 0.000442s, pydantic 0.000111s, built-ins (C) 0.000044s |
| `DashboardSnapshot` | 22 | 1 | 0.000012 | 0.000012 | 0.000078 | 0.000078 | pydantic 0.000066s |
| `<lambda>` | 88 | 8 | 0.000003 | 0.000000 | 0.000003 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/storage/baselines.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000021 | 0.000021 | 0.031402 | 0.031402 | frozen/internal 0.031314s, built-ins (C) 0.000066s |
| `SQLiteBaselineRepository.__init__` | 23 | 4 | 0.000019 | 0.000005 | 0.013490 | 0.003372 | built-ins (C) 0.000376s |
| `SQLiteBaselineRepository._init_db` | 29 | 4 | 0.000016 | 0.000004 | 0.013095 | 0.003274 | built-ins (C) 0.013079s |
| `SQLiteBaselineRepository.save_baseline` | 45 | 10 | 0.000038 | 0.000004 | 0.000956 | 0.000096 | stdlib:asyncio 0.000827s, stdlib:json 0.000057s |
| `SQLiteBaselineRepository.get_baseline` | 67 | 4 | 0.000013 | 0.000003 | 0.000378 | 0.000095 | stdlib:asyncio 0.000279s, stdlib:uuid 0.000006s |
| `SQLiteBaselineRepository.list_baselines` | 81 | 6 | 0.000012 | 0.000002 | 0.000282 | 0.000047 | stdlib:asyncio 0.000169s |
| `SQLiteBaselineRepository._row_to_baseline` | 91 | 4 | 0.000030 | 0.000008 | 0.000177 | 0.000044 | stdlib:uuid 0.000051s, stdlib:json 0.000046s, pydantic 0.000021s |
| `SQLiteBaselineRepository.close` | 100 | 4 | 0.000006 | 0.000002 | 0.000152 | 0.000038 | built-ins (C) 0.000146s |
| `<listcomp>` | 89 | 3 | 0.000003 | 0.000001 | 0.000100 | 0.000033 | - |
| `<listcomp>` | 46 | 5 | 0.000012 | 0.000002 | 0.000034 | 0.000007 | stdlib:uuid 0.000022s |
| `<listcomp>` | 95 | 4 | 0.000006 | 0.000002 | 0.000026 | 0.000007 | stdlib:uuid 0.000020s |
| `SQLiteBaselineRepository` | 20 | 1 | 0.000003 | 0.000003 | 0.000003 | 0.000003 | - |
| `BaselineRepository` | 14 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/metrics/rag_triad.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `RAGTriadMetric.evaluate` | 33 | 6 | 0.000102 | 0.000017 | 0.001105 | 0.000184 | stdlib:logging 0.000887s, pydantic 0.000043s, built-ins (C) 0.000013s |
| `<module> (import time)` | 1 | 1 | 0.000015 | 0.000015 | 0.000071 | 0.000071 | built-ins (C) 0.000019s |
| `RAGTriadMetric._extract_rag_fields` | 21 | 6 | 0.000025 | 0.000004 | 0.000051 | 0.000008 | - |
| `<listcomp>` | 40 | 6 | 0.000005 | 0.000001 | 0.000005 | 0.000001 | - |
| `RAGTriadMetric.__init__` | 18 | 5 | 0.000003 | 0.000001 | 0.000003 | 0.000001 | - |
| `RAGTriadMetric` | 13 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/regression/thresholds.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `mann_whitney_regression` | 31 | 16 | 0.000073 | 0.000005 | 0.020807 | 0.001300 | stdlib:logging 0.001408s, built-ins (C) 0.000008s |
| `validate_scores` | 22 | 36 | 0.000038 | 0.000001 | 0.001445 | 0.000040 | stdlib:logging 0.000089s |
| `holm_bonferroni` | 64 | 8 | 0.000026 | 0.000003 | 0.000556 | 0.000069 | stdlib:logging 0.000478s |
| `<module> (import time)` | 1 | 1 | 0.000014 | 0.000014 | 0.000055 | 0.000055 | - |

</details>

<details>
<summary><code>src/nirizan/instrumentation/sdk.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000033 | 0.000033 | 0.001691 | 0.001691 | frozen/internal 0.001614s, stdlib:typing 0.000016s |
| `trace_span.<locals>.decorator.<locals>.wrapper` | 63 | 7/5 | 0.000060 | 0.000009 | 0.000489 | 0.000098 | stdlib:contextlib 0.000410s, other 0.000094s, stdlib:_weakrefset 0.000008s |
| `init_tracer` | 22 | 2 | 0.000011 | 0.000005 | 0.000307 | 0.000154 | stdlib:logging 0.000294s |
| `trace_span.<locals>.decorator` | 60 | 7 | 0.000015 | 0.000002 | 0.000052 | 0.000007 | stdlib:functools 0.000037s |
| `start_session` | 36 | 1 | 0.000003 | 0.000003 | 0.000013 | 0.000013 | stdlib:logging 0.000006s, stdlib:contextlib 0.000003s |
| `_format_input_payload` | 45 | 7 | 0.000005 | 0.000001 | 0.000005 | 0.000001 | - |
| `trace_span` | 53 | 7 | 0.000004 | 0.000001 | 0.000004 | 0.000001 | - |
| `planning` | 86 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `tool_use` | 110 | 1 | 0.000001 | 0.000001 | 0.000002 | 0.000002 | - |
| `generation` | 102 | 1 | 0.000001 | 0.000001 | 0.000002 | 0.000002 | - |
| `retrieval` | 94 | 1 | 0.000001 | 0.000001 | 0.000002 | 0.000002 | - |
| `get_tracer` | 31 | 8 | 0.000002 | 0.000000 | 0.000002 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/metrics/lightweight_judge.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000022 | 0.000022 | 0.001457 | 0.001457 | built-ins (C) 0.001397s, frozen/internal 0.000004s |
| `LightweightJudge.evaluate_text` | 43 | 3 | 0.000052 | 0.000017 | 0.001029 | 0.000343 | stdlib:logging 0.000550s, pydantic 0.000017s, built-ins (C) 0.000009s |
| `RegexClassifier.predict_proba` | 26 | 2 | 0.000007 | 0.000004 | 0.000402 | 0.000201 | built-ins (C) 0.000395s |
| `<genexpr>` | 29 | 4 | 0.000009 | 0.000002 | 0.000390 | 0.000097 | stdlib:re 0.000381s |
| `LightweightJudge` | 34 | 1 | 0.000010 | 0.000010 | 0.000048 | 0.000048 | pydantic 0.000038s |
| `ClassificationModel` | 17 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `RegexClassifier` | 23 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/metrics/behavioral_anchor.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `BehavioralAnchorMetric.evaluate` | 28 | 2 | 0.000072 | 0.000036 | 0.000141 | 0.000070 | numpy 0.000030s, pydantic 0.000018s, stdlib:uuid 0.000006s |
| `<module> (import time)` | 1 | 1 | 0.000013 | 0.000013 | 0.000032 | 0.000032 | built-ins (C) 0.000019s |
| `BehavioralAnchorMetric.__init__` | 15 | 2 | 0.000003 | 0.000002 | 0.000005 | 0.000002 | built-ins (C) 0.000002s |
| `BehavioralAnchorMetric` | 12 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |

</details>

<details>
<summary><code>src/nirizan/metrics/llm_judge.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000022 | 0.000022 | 0.002142 | 0.002142 | built-ins (C) 0.002085s, frozen/internal 0.000003s |
| `LLMJudge.evaluate` | 40 | 2 | 0.000032 | 0.000016 | 0.000448 | 0.000224 | stdlib:logging 0.000336s, stdlib:json 0.000038s, pydantic 0.000012s |
| `LLMJudgeResponse` | 17 | 1 | 0.000009 | 0.000009 | 0.000074 | 0.000074 | pydantic 0.000064s |
| `LLMJudge._build_prompt` | 33 | 2 | 0.000021 | 0.000010 | 0.000024 | 0.000012 | built-ins (C) 0.000004s |
| `LLMJudge` | 24 | 1 | 0.000005 | 0.000005 | 0.000011 | 0.000011 | pydantic 0.000006s |

</details>

<details>
<summary><code>src/nirizan/metrics/statistical_gating.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000030 | 0.000030 | 1.495181 | 1.495181 | frozen/internal 1.495134s |
| `mann_whitney_regression` | 46 | 2 | 0.000012 | 0.000006 | 0.002053 | 0.001027 | stdlib:logging 0.000216s, built-ins (C) 0.000003s |
| `bootstrap_delta_ci` | 74 | 2 | 0.000008 | 0.000004 | 0.000755 | 0.000377 | stdlib:logging 0.000204s |
| `approximate_sample_size` | 146 | 5 | 0.000010 | 0.000002 | 0.000550 | 0.000110 | stdlib:logging 0.000131s |
| `validate_scores` | 41 | 8 | 0.000008 | 0.000001 | 0.000327 | 0.000041 | - |
| `holm_bonferroni` | 121 | 3 | 0.000007 | 0.000002 | 0.000217 | 0.000072 | stdlib:logging 0.000199s |
| `calibrate_gold_set` | 172 | 2 | 0.000006 | 0.000003 | 0.000153 | 0.000077 | stdlib:logging 0.000099s |

</details>

<details>
<summary><code>src/nirizan/reporting/health_score.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000007 | 0.000007 | 0.003784 | 0.003784 | frozen/internal 0.003776s |
| `compute_system_health_score` | 7 | 21 | 0.000064 | 0.000003 | 0.000128 | 0.000006 | built-ins (C) 0.000064s |

</details>

<details>
<summary><code>src/nirizan/_logging.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `get_logger` | 23 | 14 | 0.000028 | 0.000002 | 0.000374 | 0.000027 | stdlib:logging 0.000346s |
| `<module> (import time)` | 1 | 1 | 0.000023 | 0.000023 | 0.000142 | 0.000142 | stdlib:typing 0.000051s, built-ins (C) 0.000036s, stdlib:logging 0.000032s |
| `NiriZanFormatter` | 31 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `_NiriZanStreamHandler` | 15 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/orchestrator/loop_sink.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `LoopTraceSink.enqueue_trace` | 53 | 2 | 0.000017 | 0.000009 | 0.000444 | 0.000222 | stdlib:logging 0.000391s, stdlib:asyncio 0.000031s, built-ins (C) 0.000004s |
| `<module> (import time)` | 1 | 1 | 0.000019 | 0.000019 | 0.000154 | 0.000154 | built-ins (C) 0.000098s, stdlib:logging 0.000034s, frozen/internal 0.000003s |
| `_log_failure` | 73 | 3 | 0.000006 | 0.000002 | 0.000133 | 0.000044 | stdlib:logging 0.000114s, stdlib:concurrent 0.000013s |
| `LoopTraceSink.__init__` | 49 | 5 | 0.000004 | 0.000001 | 0.000004 | 0.000001 | - |
| `LoopTraceSink` | 40 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `_AsyncTraceCollector` | 34 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/metrics/base.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000020 | 0.000020 | 0.002669 | 0.002669 | built-ins (C) 0.002645s, frozen/internal 0.000004s |
| `MetricResult` | 13 | 1 | 0.000019 | 0.000019 | 0.000148 | 0.000148 | pydantic 0.000129s |
| `Metric` | 26 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `Scorer` | 36 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/instrumentation/exporters.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `ConsoleExporter.export` | 42 | 1 | 0.000004 | 0.000004 | 0.000149 | 0.000149 | stdlib:logging 0.000145s |
| `<module> (import time)` | 1 | 1 | 0.000013 | 0.000013 | 0.000117 | 0.000117 | built-ins (C) 0.000073s, stdlib:logging 0.000030s |
| `InMemoryExporter.export` | 29 | 8 | 0.000005 | 0.000001 | 0.000006 | 0.000001 | - |
| `InMemoryExporter.get_traces` | 32 | 7 | 0.000004 | 0.000001 | 0.000004 | 0.000001 | - |
| `BaseExporter` | 10 | 1 | 0.000002 | 0.000002 | 0.000003 | 0.000003 | - |
| `InMemoryExporter.__init__` | 26 | 5 | 0.000003 | 0.000001 | 0.000003 | 0.000001 | - |
| `InMemoryExporter` | 23 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `InMemoryExporter.clear` | 35 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `ConsoleExporter` | 39 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/orchestrator/scheduler.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `RunScheduler.run_on_demand` | 51 | 2 | 0.000016 | 0.000008 | 0.000670 | 0.000335 | stdlib:uuid 0.000009s, pydantic 0.000007s, built-ins (C) 0.000001s |
| `<module> (import time)` | 1 | 1 | 0.000015 | 0.000015 | 0.000089 | 0.000089 | built-ins (C) 0.000074s |
| `RunSink` | 28 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `RunScheduler.__init__` | 41 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `TraceSource` | 18 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `RunScheduler` | 38 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/trust/anchor_set.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000010 | 0.000010 | 0.002619 | 0.002619 | built-ins (C) 0.002605s, frozen/internal 0.000004s |
| `AnchorItem` | 8 | 1 | 0.000013 | 0.000013 | 0.000067 | 0.000067 | pydantic 0.000054s |
| `AnchorSet` | 17 | 1 | 0.000007 | 0.000007 | 0.000040 | 0.000040 | pydantic 0.000033s |

</details>

<details>
<summary><code>src/nirizan/orchestrator/dispatcher.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `MetricDispatcher.dispatch` | 18 | 3 | 0.000014 | 0.000005 | 0.000427 | 0.000142 | built-ins (C) 0.000001s |
| `<module> (import time)` | 1 | 1 | 0.000008 | 0.000008 | 0.000023 | 0.000023 | built-ins (C) 0.000014s |
| `MetricDispatcher.register` | 14 | 2 | 0.000003 | 0.000001 | 0.000004 | 0.000002 | - |
| `MetricDispatcher` | 8 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `MetricDispatcher.__init__` | 11 | 2 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/storage/run_repository.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000009 | 0.000009 | 0.000081 | 0.000081 | built-ins (C) 0.000072s |
| `InMemoryRunRepository.save_run` | 23 | 1 | 0.000002 | 0.000002 | 0.000003 | 0.000003 | - |
| `InMemoryRunRepository.get_run` | 26 | 1 | 0.000001 | 0.000001 | 0.000002 | 0.000002 | built-ins (C) 0.000001s |
| `RunRepository` | 10 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `InMemoryRunRepository` | 17 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `InMemoryRunRepository.__init__` | 20 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

Full per-function reports, `nirizan_only.prof` and `full.prof` (open with `tuna nirizan_only.prof`) are in the `profiling-reports` workflow artifact.
