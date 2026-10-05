<!-- nirizan-profiling-report -->
### ⏱️ NiriZan Profiling Report

`cProfile` + `pstats` over the test suite, split per module. Timings include profiler overhead: use them for *relative* comparison.

| Module | Functions run | Internal time (s) | Never executed |
| :--- | ---: | ---: | ---: |
| `metrics/stats.py` | 23 | 0.165229 | 0 |
| `regression/multivariate.py` | 26 | 0.005546 | 0 |
| `gate/verdict.py` | 10 | 0.000907 | 0 |
| `trust/attribution.py` | 10 | 0.000891 | 0 |
| `regression/comparator.py` | 10 | 0.000330 | 0 |
| `storage/models.py` | 11 | 0.000323 | 0 |
| `reporting/judge_reliability.py` | 25 | 0.000312 | 0 |
| `instrumentation/tracer.py` | 8 | 0.000268 | 1 |
| `storage/experiment_store.py` | 15 | 0.000212 | 5 |
| `orchestrator/collector.py` | 13 | 0.000211 | 1 |
| `storage/baselines.py` | 13 | 0.000165 | 6 |
| `gate/ci.py` | 5 | 0.000141 | 0 |
| `reporting/dashboard.py` | 4 | 0.000137 | 0 |
| `storage/trace_repository.py` | 9 | 0.000135 | 10 |
| `metrics/rag_triad.py` | 6 | 0.000120 | 0 |
| `regression/thresholds.py` | 4 | 0.000113 | 0 |
| `instrumentation/spans.py` | 7 | 0.000105 | 0 |
| `instrumentation/sdk.py` | 12 | 0.000099 | 0 |
| `metrics/behavioral_anchor.py` | 4 | 0.000084 | 1 |
| `metrics/lightweight_judge.py` | 7 | 0.000069 | 1 |
| `metrics/llm_judge.py` | 5 | 0.000054 | 0 |
| `_logging.py` | 4 | 0.000053 | 5 |
| `metrics/statistical_gating.py` | 7 | 0.000049 | 0 |
| `reporting/health_score.py` | 2 | 0.000048 | 0 |
| `orchestrator/scheduler.py` | 6 | 0.000028 | 2 |
| `instrumentation/exporters.py` | 9 | 0.000024 | 2 |
| `orchestrator/dispatcher.py` | 5 | 0.000023 | 0 |
| `metrics/base.py` | 4 | 0.000022 | 2 |
| `trust/anchor_set.py` | 3 | 0.000021 | 0 |
| `storage/run_repository.py` | 6 | 0.000011 | 2 |
| `instrumentation/sessions.py` | 0 | 0.000000 | 0 |
| `storage/session_repository.py` | 0 | 0.000000 | 5 |

#### Top 15 functions per module

<details>
<summary><code>src/nirizan/metrics/stats.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `_permutation_distribution` | 356 | 47 | 0.040291 | 0.000857 | 1.863550 | 0.039650 | numpy 0.002463s, other 0.002256s, frozen/internal 0.000053s |
| `dependence_max_t_test` | 542 | 24 | 0.000293 | 0.000012 | 1.781914 | 0.074246 | - |
| `_dependence_max_t_from_groups` | 497 | 3566 | 0.015002 | 0.000004 | 1.748570 | 0.000490 | numpy 0.078893s, built-ins (C) 0.005093s |
| `_rank_columns` | 459 | 7172 | 0.022555 | 0.000003 | 1.523722 | 0.000212 | scipy 1.500540s, numpy 0.000627s |
| `<module> (import time)` | 1 | 1 | 0.000032 | 0.000032 | 0.976962 | 0.976962 | frozen/internal 0.976893s |
| `_pearson_from_ranks` | 480 | 7132 | 0.060639 | 0.000009 | 0.136424 | 0.000019 | built-ins (C) 0.055301s, numpy 0.020484s |
| `scale_logvar_test` | 421 | 26 | 0.000221 | 0.000009 | 0.091147 | 0.003506 | built-ins (C) 0.000297s |
| `<lambda>` | 448 | 3572 | 0.000935 | 0.000000 | 0.072573 | 0.000020 | - |
| `_scale_logvar_from_arrays` | 408 | 3579 | 0.008447 | 0.000002 | 0.071882 | 0.000020 | built-ins (C) 0.063435s |
| `mann_whitney_regression` | 174 | 48 | 0.000263 | 0.000005 | 0.036591 | 0.000762 | scipy 0.035164s, built-ins (C) 0.000008s, stdlib:typing 0.000003s |
| `bootstrap_delta_ci` | 142 | 80 | 0.011869 | 0.000148 | 0.035265 | 0.000441 | numpy 0.021135s, frozen/internal 0.000074s, stdlib:threading 0.000046s |
| `validate_scores` | 42 | 485 | 0.002316 | 0.000005 | 0.006900 | 0.000014 | numpy 0.002373s, built-ins (C) 0.001295s, stdlib:logging 0.000916s |
| `permutation_test` | 307 | 10 | 0.000019 | 0.000002 | 0.003742 | 0.000374 | - |
| `dependence_max_t_statistic` | 516 | 6 | 0.000008 | 0.000001 | 0.002857 | 0.000476 | - |
| `validate_score_matrix` | 57 | 166 | 0.000924 | 0.000006 | 0.002360 | 0.000014 | numpy 0.000953s, built-ins (C) 0.000483s |

</details>

<details>
<summary><code>src/nirizan/regression/multivariate.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `MultivariateComparator.compare` | 389 | 29 | 0.000853 | 0.000029 | 1.148729 | 0.039611 | pydantic 0.000304s, stdlib:logging 0.000084s, stdlib:enum 0.000036s |
| `MultivariateComparator.compare_metric_results` | 554 | 5 | 0.000037 | 0.000007 | 0.079385 | 0.015877 | stdlib:logging 0.000400s |
| `<module> (import time)` | 1 | 1 | 0.000024 | 0.000024 | 0.011832 | 0.011832 | frozen/internal 0.007218s, built-ins (C) 0.004560s |
| `ScoreMatrix.from_metric_results` | 165 | 61 | 0.002587 | 0.000042 | 0.009755 | 0.000160 | built-ins (C) 0.004607s, pydantic 0.000817s, stdlib:uuid 0.000476s |
| `ScoreMatrix.validate_contract` | 144 | 60 | 0.000110 | 0.000002 | 0.000761 | 0.000013 | built-ins (C) 0.000014s |
| `<genexpr>` | 217 | 3948 | 0.000624 | 0.000000 | 0.000756 | 0.000000 | built-ins (C) 0.000132s |
| `<dictcomp>` | 439 | 17 | 0.000065 | 0.000004 | 0.000538 | 0.000032 | built-ins (C) 0.000473s |
| `derive_permutation_seed` | 343 | 41 | 0.000352 | 0.000009 | 0.000508 | 0.000012 | numpy 0.000148s, stdlib:uuid 0.000008s |
| `MultivariateComparator._complete_case_metric_deltas` | 643 | 4 | 0.000013 | 0.000003 | 0.000427 | 0.000107 | - |
| `<genexpr>` | 213 | 3959 | 0.000317 | 0.000000 | 0.000317 | 0.000000 | - |
| `<listcomp>` | 216 | 1178 | 0.000238 | 0.000000 | 0.000238 | 0.000000 | - |
| `MultivariateConfig` | 83 | 1 | 0.000011 | 0.000011 | 0.000215 | 0.000215 | pydantic 0.000203s |
| `MultivariateComparator.__init__` | 378 | 35 | 0.000091 | 0.000003 | 0.000211 | 0.000006 | stdlib:logging 0.000072s, stdlib:enum 0.000034s, pydantic 0.000013s |
| `MultivariateVerdict` | 255 | 1 | 0.000007 | 0.000007 | 0.000093 | 0.000093 | pydantic 0.000086s |
| `ScoreMatrix` | 126 | 1 | 0.000010 | 0.000010 | 0.000084 | 0.000084 | pydantic 0.000074s |

</details>

<details>
<summary><code>src/nirizan/gate/verdict.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000033 | 0.000033 | 1.149018 | 1.149018 | frozen/internal 1.147533s, built-ins (C) 0.001426s |
| `evaluate_gate` | 182 | 16 | 0.000110 | 0.000007 | 0.014086 | 0.000880 | stdlib:logging 0.001152s, pydantic 0.000064s, built-ins (C) 0.000002s |
| `bootstrap_delta_ci` | 74 | 19 | 0.000663 | 0.000035 | 0.013145 | 0.000692 | stdlib:logging 0.000294s, built-ins (C) 0.000011s |
| `select_decision_metric` | 136 | 17 | 0.000025 | 0.000001 | 0.000148 | 0.000009 | stdlib:logging 0.000080s, built-ins (C) 0.000034s, stdlib:enum 0.000009s |
| `GateVerdict` | 46 | 1 | 0.000009 | 0.000009 | 0.000070 | 0.000070 | pydantic 0.000061s |
| `_comparison_identity` | 166 | 16 | 0.000022 | 0.000001 | 0.000053 | 0.000003 | built-ins (C) 0.000030s |
| `<genexpr>` | 177 | 51 | 0.000017 | 0.000000 | 0.000018 | 0.000000 | stdlib:uuid 0.000001s |
| `<lambda>` | 152 | 28 | 0.000013 | 0.000000 | 0.000013 | 0.000000 | - |
| `<listcomp>` | 224 | 14 | 0.000012 | 0.000001 | 0.000012 | 0.000001 | - |
| `<listcomp>` | 227 | 14 | 0.000004 | 0.000000 | 0.000004 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/trust/attribution.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `AttributionEngine._shift_evidence` | 90 | 51 | 0.000196 | 0.000004 | 0.041768 | 0.000819 | stdlib:unittest 0.000145s, built-ins (C) 0.000007s |
| `AttributionEngine.analyze` | 149 | 41 | 0.000576 | 0.000014 | 0.041266 | 0.001006 | stdlib:unittest 0.000313s, pydantic 0.000193s, built-ins (C) 0.000068s |
| `<module> (import time)` | 1 | 1 | 0.000014 | 0.000014 | 0.001109 | 0.001109 | built-ins (C) 0.001094s, frozen/internal 0.000002s |
| `AttributionEngine.__init__` | 66 | 54 | 0.000043 | 0.000001 | 0.000043 | 0.000001 | - |
| `DriftAttribution` | 18 | 1 | 0.000003 | 0.000003 | 0.000035 | 0.000035 | stdlib:enum 0.000032s |
| `AttributionEngine._is_significant` | 136 | 64 | 0.000018 | 0.000000 | 0.000021 | 0.000000 | built-ins (C) 0.000004s |
| `AttributionEngine.analyze.<locals>._p_str` | 217 | 22 | 0.000018 | 0.000001 | 0.000018 | 0.000001 | - |
| `<dictcomp>` | 203 | 32 | 0.000017 | 0.000001 | 0.000017 | 0.000001 | - |
| `AttributionVerdict` | 26 | 1 | 0.000003 | 0.000003 | 0.000006 | 0.000006 | pydantic 0.000003s |
| `AttributionEngine` | 43 | 1 | 0.000004 | 0.000004 | 0.000004 | 0.000004 | - |

</details>

<details>
<summary><code>src/nirizan/regression/comparator.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `BaselineComparator.compare_metric` | 97 | 15 | 0.000158 | 0.000011 | 0.013823 | 0.000922 | stdlib:logging 0.000474s, pydantic 0.000084s, stdlib:enum 0.000011s |
| `BaselineComparator.compare` | 162 | 7 | 0.000071 | 0.000010 | 0.011197 | 0.001600 | stdlib:logging 0.000471s, pydantic 0.000017s, built-ins (C) 0.000011s |
| `<module> (import time)` | 1 | 1 | 0.000024 | 0.000024 | 0.004736 | 0.004736 | built-ins (C) 0.004157s, frozen/internal 0.000545s |
| `mean_delta` | 43 | 18 | 0.000014 | 0.000001 | 0.000184 | 0.000010 | built-ins (C) 0.000169s |
| `RegressionVerdict` | 30 | 1 | 0.000018 | 0.000018 | 0.000098 | 0.000098 | pydantic 0.000081s |
| `BaselineComparator.__init__` | 76 | 10 | 0.000017 | 0.000002 | 0.000059 | 0.000006 | stdlib:logging 0.000042s |
| `RegressionSeverity` | 24 | 1 | 0.000002 | 0.000002 | 0.000027 | 0.000027 | stdlib:enum 0.000025s |
| `classify_severity` | 50 | 23 | 0.000021 | 0.000001 | 0.000021 | 0.000001 | - |
| `<dictcomp>` | 199 | 5 | 0.000004 | 0.000001 | 0.000004 | 0.000001 | - |
| `BaselineComparator` | 75 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/storage/models.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000016 | 0.000016 | 0.005353 | 0.005353 | built-ins (C) 0.005333s, frozen/internal 0.000004s |
| `TraceRecord.to_trace` | 81 | 10 | 0.000042 | 0.000004 | 0.000496 | 0.000050 | stdlib:uuid 0.000055s, pydantic 0.000045s, built-ins (C) 0.000007s |
| `TraceRecord.from_trace` | 69 | 8 | 0.000043 | 0.000005 | 0.000395 | 0.000049 | built-ins (C) 0.000034s, stdlib:uuid 0.000028s, pydantic 0.000024s |
| `SpanRecord.to_span` | 42 | 20 | 0.000079 | 0.000004 | 0.000363 | 0.000018 | stdlib:json 0.000115s, stdlib:uuid 0.000098s, pydantic 0.000045s |
| `<listcomp>` | 87 | 10 | 0.000013 | 0.000001 | 0.000347 | 0.000035 | - |
| `SpanRecord.from_span` | 27 | 14 | 0.000070 | 0.000005 | 0.000285 | 0.000020 | stdlib:json 0.000105s, built-ins (C) 0.000036s, pydantic 0.000035s |
| `<listcomp>` | 75 | 8 | 0.000015 | 0.000002 | 0.000264 | 0.000033 | - |
| `Run` | 94 | 1 | 0.000009 | 0.000009 | 0.000104 | 0.000104 | pydantic 0.000096s |
| `Baseline` | 107 | 1 | 0.000006 | 0.000006 | 0.000070 | 0.000070 | pydantic 0.000063s |
| `TraceRecord` | 58 | 1 | 0.000013 | 0.000013 | 0.000060 | 0.000060 | pydantic 0.000047s |
| `SpanRecord` | 13 | 1 | 0.000016 | 0.000016 | 0.000025 | 0.000025 | pydantic 0.000008s, stdlib:typing 0.000001s |

</details>

<details>
<summary><code>src/nirizan/reporting/judge_reliability.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000014 | 0.000014 | 0.002824 | 0.002824 | built-ins (C) 0.002777s, frozen/internal 0.000002s |
| `compute_judge_reliability` | 76 | 14 | 0.000164 | 0.000012 | 0.001267 | 0.000090 | stdlib:logging 0.000847s, built-ins (C) 0.000115s, pydantic 0.000066s |
| `JudgeReliabilityMetrics` | 24 | 1 | 0.000012 | 0.000012 | 0.000206 | 0.000206 | pydantic 0.000194s |
| `_std` | 49 | 10 | 0.000015 | 0.000002 | 0.000033 | 0.000003 | built-ins (C) 0.000018s |
| `JudgeReliabilityStatus` | 17 | 1 | 0.000002 | 0.000002 | 0.000022 | 0.000022 | stdlib:enum 0.000020s |
| `_mean` | 45 | 12 | 0.000009 | 0.000001 | 0.000015 | 0.000001 | built-ins (C) 0.000005s |
| `<genexpr>` | 98 | 20 | 0.000014 | 0.000001 | 0.000014 | 0.000001 | - |
| `judge_score_delta_series` | 56 | 1 | 0.000001 | 0.000001 | 0.000010 | 0.000010 | built-ins (C) 0.000009s |
| `<genexpr>` | 52 | 31 | 0.000010 | 0.000000 | 0.000010 | 0.000000 | - |
| `<genexpr>` | 103 | 16 | 0.000009 | 0.000001 | 0.000009 | 0.000001 | - |
| `<setcomp>` | 87 | 13 | 0.000008 | 0.000001 | 0.000008 | 0.000001 | - |
| `system_score_delta_series` | 66 | 1 | 0.000001 | 0.000001 | 0.000008 | 0.000008 | built-ins (C) 0.000007s |
| `<genexpr>` | 110 | 26 | 0.000007 | 0.000000 | 0.000007 | 0.000000 | - |
| `<genexpr>` | 109 | 13 | 0.000007 | 0.000001 | 0.000007 | 0.000001 | - |
| `<genexpr>` | 108 | 13 | 0.000006 | 0.000000 | 0.000006 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/instrumentation/tracer.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `Tracer.start_span` | 54 | 48 | 0.000163 | 0.000003 | 0.000806 | 0.000017 | stdlib:uuid 0.000136s, pydantic 0.000106s, built-ins (C) 0.000067s |
| `<module> (import time)` | 1 | 1 | 0.000026 | 0.000026 | 0.000453 | 0.000453 | stdlib:dataclasses 0.000302s, built-ins (C) 0.000126s |
| `Tracer.get_assembled_trace` | 116 | 14 | 0.000037 | 0.000003 | 0.000148 | 0.000011 | pydantic 0.000077s, built-ins (C) 0.000005s |
| `Tracer` | 32 | 1 | 0.000010 | 0.000010 | 0.000097 | 0.000097 | stdlib:typing 0.000077s, stdlib:contextlib 0.000010s |
| `Tracer.session` | 44 | 8 | 0.000011 | 0.000001 | 0.000052 | 0.000007 | stdlib:uuid 0.000036s, built-ins (C) 0.000005s |
| `<listcomp>` | 119 | 14 | 0.000017 | 0.000001 | 0.000029 | 0.000002 | stdlib:uuid 0.000012s |
| `Tracer.__init__` | 35 | 9 | 0.000005 | 0.000001 | 0.000005 | 0.000001 | - |
| `SpanHandle` | 24 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/storage/experiment_store.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `SQLiteExperimentStore.__init__` | 35 | 5 | 0.000022 | 0.000004 | 0.014887 | 0.002977 | built-ins (C) 0.000382s |
| `SQLiteExperimentStore._init_db` | 41 | 5 | 0.000020 | 0.000004 | 0.014483 | 0.002897 | built-ins (C) 0.014463s |
| `SQLiteExperimentStore.record_run` | 59 | 12 | 0.000035 | 0.000003 | 0.000922 | 0.000077 | stdlib:asyncio 0.000639s, stdlib:json 0.000114s |
| `<module> (import time)` | 1 | 1 | 0.000016 | 0.000016 | 0.000813 | 0.000813 | built-ins (C) 0.000795s, frozen/internal 0.000002s |
| `SQLiteExperimentStore.get_run` | 83 | 12 | 0.000042 | 0.000004 | 0.000535 | 0.000045 | stdlib:asyncio 0.000302s, stdlib:json 0.000055s, stdlib:uuid 0.000042s |
| `SQLiteExperimentStore.diff` | 109 | 6 | 0.000018 | 0.000003 | 0.000266 | 0.000044 | pydantic 0.000004s, stdlib:uuid 0.000002s |
| `SQLiteExperimentStore.close` | 122 | 5 | 0.000010 | 0.000002 | 0.000194 | 0.000039 | built-ins (C) 0.000183s |
| `<listcomp>` | 60 | 6 | 0.000022 | 0.000004 | 0.000134 | 0.000022 | pydantic 0.000111s |
| `<listcomp>` | 96 | 4 | 0.000017 | 0.000004 | 0.000074 | 0.000018 | pydantic 0.000056s |
| `RunDiff` | 16 | 1 | 0.000005 | 0.000005 | 0.000009 | 0.000009 | pydantic 0.000004s |
| `SQLiteExperimentStore` | 32 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `<dictcomp>` | 115 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `<dictcomp>` | 119 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `ExperimentStore` | 26 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `<dictcomp>` | 116 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/orchestrator/collector.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `TraceCollector._process_queue` | 84 | 24 | 0.000066 | 0.000003 | 0.004796 | 0.000200 | stdlib:asyncio 0.000330s, stdlib:_weakrefset 0.000004s |
| `TraceCollector.__init__` | 45 | 5 | 0.000034 | 0.000007 | 0.003475 | 0.000695 | stdlib:asyncio 0.000046s |
| `_resolve_code_commit` | 14 | 5 | 0.000025 | 0.000005 | 0.003379 | 0.000676 | stdlib:subprocess 0.003336s, frozen/internal 0.000017s |
| `CollectorExporter.export` | 103 | 7 | 0.000009 | 0.000001 | 0.000177 | 0.000025 | - |
| `TraceCollector.enqueue_trace` | 74 | 7 | 0.000021 | 0.000003 | 0.000168 | 0.000024 | pydantic 0.000092s, stdlib:asyncio 0.000054s |
| `<module> (import time)` | 1 | 1 | 0.000021 | 0.000021 | 0.000132 | 0.000132 | built-ins (C) 0.000082s, stdlib:logging 0.000026s, stdlib:typing 0.000002s |
| `TraceCollector.start` | 56 | 5 | 0.000013 | 0.000003 | 0.000071 | 0.000014 | stdlib:asyncio 0.000058s |
| `TraceCollector.stop` | 63 | 10 | 0.000013 | 0.000001 | 0.000030 | 0.000003 | built-ins (C) 0.000015s, stdlib:asyncio 0.000001s |
| `_resolve_data_snapshot_id` | 31 | 5 | 0.000004 | 0.000001 | 0.000016 | 0.000003 | frozen/internal 0.000012s |
| `CollectorExporter.__init__` | 100 | 5 | 0.000003 | 0.000001 | 0.000003 | 0.000001 | - |
| `TraceCollector` | 42 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `CollectorExporter` | 97 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `TraceSink` | 36 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/storage/baselines.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `SQLiteBaselineRepository.__init__` | 23 | 4 | 0.000036 | 0.000009 | 0.008479 | 0.002120 | built-ins (C) 0.000352s |
| `SQLiteBaselineRepository._init_db` | 29 | 4 | 0.000016 | 0.000004 | 0.008092 | 0.002023 | built-ins (C) 0.008076s |
| `<module> (import time)` | 1 | 1 | 0.000015 | 0.000015 | 0.005053 | 0.005053 | frozen/internal 0.004990s, built-ins (C) 0.000048s |
| `SQLiteBaselineRepository.save_baseline` | 45 | 10 | 0.000032 | 0.000003 | 0.000833 | 0.000083 | stdlib:asyncio 0.000718s, stdlib:json 0.000060s |
| `SQLiteBaselineRepository.get_baseline` | 67 | 4 | 0.000010 | 0.000003 | 0.000322 | 0.000080 | stdlib:asyncio 0.000253s, stdlib:uuid 0.000005s |
| `SQLiteBaselineRepository.list_baselines` | 81 | 6 | 0.000008 | 0.000001 | 0.000157 | 0.000026 | stdlib:asyncio 0.000065s |
| `SQLiteBaselineRepository.close` | 100 | 4 | 0.000006 | 0.000002 | 0.000139 | 0.000035 | built-ins (C) 0.000133s |
| `SQLiteBaselineRepository._row_to_baseline` | 91 | 4 | 0.000025 | 0.000006 | 0.000135 | 0.000034 | stdlib:json 0.000044s, pydantic 0.000024s, stdlib:uuid 0.000022s |
| `<listcomp>` | 89 | 3 | 0.000003 | 0.000001 | 0.000084 | 0.000028 | - |
| `<listcomp>` | 46 | 5 | 0.000007 | 0.000001 | 0.000022 | 0.000004 | stdlib:uuid 0.000015s |
| `<listcomp>` | 95 | 4 | 0.000004 | 0.000001 | 0.000016 | 0.000004 | stdlib:uuid 0.000012s |
| `SQLiteBaselineRepository` | 20 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `BaselineRepository` | 14 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/gate/ci.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `serialize_gate_verdict` | 95 | 3 | 0.000017 | 0.000006 | 0.000444 | 0.000148 | stdlib:json 0.000298s, stdlib:logging 0.000072s, pydantic 0.000057s |
| `gate_exit_code` | 87 | 4 | 0.000008 | 0.000002 | 0.000442 | 0.000110 | stdlib:logging 0.000433s |
| `write_github_summary` | 70 | 4 | 0.000011 | 0.000003 | 0.000262 | 0.000066 | stdlib:logging 0.000207s, built-ins (C) 0.000001s |
| `format_gate_summary` | 23 | 12 | 0.000095 | 0.000008 | 0.000125 | 0.000010 | stdlib:enum 0.000020s, built-ins (C) 0.000010s |
| `<module> (import time)` | 1 | 1 | 0.000009 | 0.000009 | 0.000033 | 0.000033 | - |

</details>

<details>
<summary><code>src/nirizan/reporting/dashboard.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000020 | 0.000020 | 0.008722 | 0.008722 | frozen/internal 0.006656s, built-ins (C) 0.002020s |
| `assemble_dashboard_snapshot` | 51 | 16 | 0.000107 | 0.000007 | 0.001091 | 0.000068 | stdlib:logging 0.000259s, pydantic 0.000082s, built-ins (C) 0.000041s |
| `DashboardSnapshot` | 22 | 1 | 0.000008 | 0.000008 | 0.000097 | 0.000097 | pydantic 0.000089s |
| `<lambda>` | 88 | 8 | 0.000002 | 0.000000 | 0.000002 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/storage/trace_repository.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `SQLiteTraceRepository.__init__` | 53 | 4 | 0.000028 | 0.000007 | 0.025980 | 0.006495 | built-ins (C) 0.000362s |
| `SQLiteTraceRepository._init_db` | 60 | 4 | 0.000020 | 0.000005 | 0.025590 | 0.006398 | built-ins (C) 0.025570s |
| `SQLiteTraceRepository.save` | 98 | 14 | 0.000031 | 0.000002 | 0.004396 | 0.000314 | stdlib:asyncio 0.003988s |
| `SQLiteTraceRepository.list_by_application` | 188 | 12 | 0.000021 | 0.000002 | 0.000695 | 0.000058 | stdlib:asyncio 0.000181s |
| `<listcomp>` | 238 | 6 | 0.000010 | 0.000002 | 0.000493 | 0.000082 | - |
| `SQLiteTraceRepository.close` | 251 | 4 | 0.000007 | 0.000002 | 0.000167 | 0.000042 | built-ins (C) 0.000160s |
| `<module> (import time)` | 1 | 1 | 0.000011 | 0.000011 | 0.000120 | 0.000120 | built-ins (C) 0.000109s |
| `BaseTraceRepository` | 12 | 1 | 0.000006 | 0.000006 | 0.000073 | 0.000073 | stdlib:typing 0.000066s |
| `SQLiteTraceRepository` | 50 | 1 | 0.000002 | 0.000002 | 0.000003 | 0.000003 | - |

</details>

<details>
<summary><code>src/nirizan/metrics/rag_triad.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `RAGTriadMetric.evaluate` | 33 | 6 | 0.000084 | 0.000014 | 0.000710 | 0.000118 | stdlib:logging 0.000551s, pydantic 0.000031s, built-ins (C) 0.000009s |
| `<module> (import time)` | 1 | 1 | 0.000015 | 0.000015 | 0.000094 | 0.000094 | built-ins (C) 0.000022s |
| `RAGTriadMetric._extract_rag_fields` | 21 | 6 | 0.000015 | 0.000002 | 0.000029 | 0.000005 | - |
| `<listcomp>` | 40 | 6 | 0.000004 | 0.000001 | 0.000004 | 0.000001 | - |
| `RAGTriadMetric.__init__` | 18 | 5 | 0.000002 | 0.000000 | 0.000002 | 0.000000 | - |
| `RAGTriadMetric` | 13 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/regression/thresholds.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `mann_whitney_regression` | 31 | 16 | 0.000053 | 0.000003 | 0.012570 | 0.000786 | stdlib:logging 0.000998s, built-ins (C) 0.000005s |
| `validate_scores` | 22 | 36 | 0.000026 | 0.000001 | 0.000874 | 0.000024 | stdlib:logging 0.000055s |
| `holm_bonferroni` | 64 | 8 | 0.000021 | 0.000003 | 0.000362 | 0.000045 | stdlib:logging 0.000294s |
| `<module> (import time)` | 1 | 1 | 0.000013 | 0.000013 | 0.000041 | 0.000041 | - |

</details>

<details>
<summary><code>src/nirizan/instrumentation/spans.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000010 | 0.000010 | 0.004265 | 0.004265 | built-ins (C) 0.004253s, frozen/internal 0.000002s |
| `Trace` | 37 | 1 | 0.000012 | 0.000012 | 0.000153 | 0.000153 | pydantic 0.000140s |
| `Span` | 20 | 1 | 0.000010 | 0.000010 | 0.000096 | 0.000096 | pydantic 0.000086s |
| `Trace.validate_span_trace_ids` | 50 | 34 | 0.000046 | 0.000001 | 0.000068 | 0.000002 | stdlib:uuid 0.000021s |
| `SpanKind` | 11 | 1 | 0.000003 | 0.000003 | 0.000032 | 0.000032 | stdlib:enum 0.000029s |
| `Trace.spans_of_kind` | 61 | 25 | 0.000015 | 0.000001 | 0.000025 | 0.000001 | - |
| `<listcomp>` | 63 | 25 | 0.000009 | 0.000000 | 0.000009 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/instrumentation/sdk.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000029 | 0.000029 | 0.001316 | 0.001316 | frozen/internal 0.001238s, stdlib:typing 0.000012s |
| `trace_span.<locals>.decorator.<locals>.wrapper` | 62 | 7/5 | 0.000041 | 0.000006 | 0.000257 | 0.000051 | stdlib:contextlib 0.000205s, other 0.000051s, stdlib:_weakrefset 0.000004s |
| `init_tracer` | 21 | 2 | 0.000008 | 0.000004 | 0.000124 | 0.000062 | stdlib:logging 0.000115s |
| `trace_span.<locals>.decorator` | 59 | 7 | 0.000009 | 0.000001 | 0.000031 | 0.000004 | stdlib:functools 0.000022s |
| `start_session` | 35 | 1 | 0.000003 | 0.000003 | 0.000009 | 0.000009 | stdlib:contextlib 0.000003s, stdlib:logging 0.000003s |
| `_format_input_payload` | 44 | 7 | 0.000003 | 0.000000 | 0.000004 | 0.000001 | - |
| `trace_span` | 52 | 7 | 0.000002 | 0.000000 | 0.000002 | 0.000000 | - |
| `planning` | 85 | 1 | 0.000001 | 0.000001 | 0.000002 | 0.000002 | - |
| `get_tracer` | 30 | 8 | 0.000001 | 0.000000 | 0.000001 | 0.000000 | - |
| `retrieval` | 93 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `tool_use` | 109 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `generation` | 101 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/metrics/behavioral_anchor.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `BehavioralAnchorMetric.evaluate` | 28 | 2 | 0.000069 | 0.000035 | 0.000121 | 0.000060 | numpy 0.000025s, pydantic 0.000014s, stdlib:uuid 0.000005s |
| `<module> (import time)` | 1 | 1 | 0.000012 | 0.000012 | 0.000027 | 0.000027 | built-ins (C) 0.000016s |
| `BehavioralAnchorMetric.__init__` | 15 | 2 | 0.000003 | 0.000001 | 0.000004 | 0.000002 | built-ins (C) 0.000001s |
| `BehavioralAnchorMetric` | 12 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/metrics/lightweight_judge.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000025 | 0.000025 | 0.001253 | 0.001253 | built-ins (C) 0.001189s, frozen/internal 0.000003s |
| `LightweightJudge.evaluate_text` | 43 | 3 | 0.000019 | 0.000006 | 0.000601 | 0.000200 | stdlib:logging 0.000313s, pydantic 0.000007s, built-ins (C) 0.000005s |
| `RegexClassifier.predict_proba` | 26 | 2 | 0.000005 | 0.000003 | 0.000256 | 0.000128 | built-ins (C) 0.000251s |
| `<genexpr>` | 29 | 4 | 0.000006 | 0.000001 | 0.000247 | 0.000062 | stdlib:re 0.000241s |
| `LightweightJudge` | 34 | 1 | 0.000012 | 0.000012 | 0.000074 | 0.000074 | pydantic 0.000062s |
| `ClassificationModel` | 17 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `RegexClassifier` | 23 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/metrics/llm_judge.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000021 | 0.000021 | 0.001629 | 0.001629 | built-ins (C) 0.001578s, frozen/internal 0.000003s |
| `LLMJudge.evaluate` | 40 | 2 | 0.000020 | 0.000010 | 0.000241 | 0.000121 | stdlib:logging 0.000173s, stdlib:json 0.000034s, pydantic 0.000006s |
| `LLMJudgeResponse` | 17 | 1 | 0.000008 | 0.000008 | 0.000067 | 0.000067 | pydantic 0.000058s |
| `LLMJudge` | 24 | 1 | 0.000004 | 0.000004 | 0.000007 | 0.000007 | pydantic 0.000003s |
| `LLMJudge._build_prompt` | 33 | 2 | 0.000002 | 0.000001 | 0.000005 | 0.000002 | built-ins (C) 0.000003s |

</details>

<details>
<summary><code>src/nirizan/_logging.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `get_logger` | 23 | 13 | 0.000028 | 0.000002 | 0.000378 | 0.000029 | stdlib:logging 0.000350s |
| `<module> (import time)` | 1 | 1 | 0.000025 | 0.000025 | 0.000163 | 0.000163 | stdlib:typing 0.000069s, built-ins (C) 0.000038s, stdlib:logging 0.000032s |
| `NiriZanFormatter` | 31 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |
| `_NiriZanStreamHandler` | 15 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/metrics/statistical_gating.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000016 | 0.000016 | 0.979328 | 0.979328 | frozen/internal 0.979301s |
| `mann_whitney_regression` | 46 | 2 | 0.000008 | 0.000004 | 0.001355 | 0.000678 | stdlib:logging 0.000123s, built-ins (C) 0.000002s |
| `bootstrap_delta_ci` | 74 | 2 | 0.000006 | 0.000003 | 0.000483 | 0.000241 | stdlib:logging 0.000117s |
| `approximate_sample_size` | 146 | 5 | 0.000006 | 0.000001 | 0.000327 | 0.000065 | stdlib:logging 0.000062s |
| `validate_scores` | 41 | 8 | 0.000004 | 0.000000 | 0.000195 | 0.000024 | - |
| `holm_bonferroni` | 121 | 3 | 0.000004 | 0.000001 | 0.000122 | 0.000041 | stdlib:logging 0.000109s |
| `calibrate_gold_set` | 172 | 2 | 0.000004 | 0.000002 | 0.000089 | 0.000045 | stdlib:logging 0.000054s |

</details>

<details>
<summary><code>src/nirizan/reporting/health_score.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000004 | 0.000004 | 0.002538 | 0.002538 | frozen/internal 0.002534s |
| `compute_system_health_score` | 7 | 21 | 0.000044 | 0.000002 | 0.000081 | 0.000004 | built-ins (C) 0.000037s |

</details>

<details>
<summary><code>src/nirizan/orchestrator/scheduler.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000014 | 0.000014 | 0.006406 | 0.006406 | frozen/internal 0.006342s, built-ins (C) 0.000050s |
| `RunScheduler.run_on_demand` | 51 | 2 | 0.000012 | 0.000006 | 0.000350 | 0.000175 | stdlib:uuid 0.000007s, pydantic 0.000005s |
| `RunScheduler.__init__` | 41 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `TraceSource` | 18 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `RunSink` | 28 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |
| `RunScheduler` | 38 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/instrumentation/exporters.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000010 | 0.000010 | 0.000106 | 0.000106 | built-ins (C) 0.000064s, stdlib:logging 0.000032s |
| `ConsoleExporter.export` | 42 | 1 | 0.000001 | 0.000001 | 0.000073 | 0.000073 | stdlib:logging 0.000072s |
| `InMemoryExporter.export` | 29 | 8 | 0.000003 | 0.000000 | 0.000003 | 0.000000 | - |
| `BaseExporter` | 10 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `InMemoryExporter.get_traces` | 32 | 7 | 0.000002 | 0.000000 | 0.000002 | 0.000000 | - |
| `InMemoryExporter` | 23 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `InMemoryExporter.__init__` | 26 | 5 | 0.000002 | 0.000000 | 0.000002 | 0.000000 | - |
| `InMemoryExporter.clear` | 35 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `ConsoleExporter` | 39 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/orchestrator/dispatcher.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `MetricDispatcher.dispatch` | 18 | 3 | 0.000013 | 0.000004 | 0.000328 | 0.000109 | - |
| `<module> (import time)` | 1 | 1 | 0.000006 | 0.000006 | 0.000018 | 0.000018 | built-ins (C) 0.000013s |
| `MetricDispatcher.register` | 14 | 2 | 0.000002 | 0.000001 | 0.000003 | 0.000001 | - |
| `MetricDispatcher.__init__` | 11 | 2 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `MetricDispatcher` | 8 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

<details>
<summary><code>src/nirizan/metrics/base.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000013 | 0.000013 | 0.006746 | 0.006746 | frozen/internal 0.005262s, built-ins (C) 0.001471s |
| `MetricResult` | 13 | 1 | 0.000008 | 0.000008 | 0.000107 | 0.000107 | pydantic 0.000099s |
| `Metric` | 26 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `Scorer` | 36 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |

</details>

<details>
<summary><code>src/nirizan/trust/anchor_set.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000007 | 0.000007 | 0.001932 | 0.001932 | built-ins (C) 0.001922s, frozen/internal 0.000003s |
| `AnchorItem` | 8 | 1 | 0.000010 | 0.000010 | 0.000081 | 0.000081 | pydantic 0.000071s |
| `AnchorSet` | 17 | 1 | 0.000004 | 0.000004 | 0.000040 | 0.000040 | pydantic 0.000036s |

</details>

<details>
<summary><code>src/nirizan/storage/run_repository.py</code></summary>

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000006 | 0.000006 | 0.000043 | 0.000043 | built-ins (C) 0.000037s |
| `InMemoryRunRepository.save_run` | 23 | 1 | 0.000002 | 0.000002 | 0.000003 | 0.000003 | - |
| `InMemoryRunRepository.get_run` | 26 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `InMemoryRunRepository.__init__` | 20 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `InMemoryRunRepository` | 17 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `RunRepository` | 10 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

</details>

Full per-function reports, `nirizan_only.prof` and `full.prof` (open with `tuna nirizan_only.prof`) are in the `profiling-reports` workflow artifact.
