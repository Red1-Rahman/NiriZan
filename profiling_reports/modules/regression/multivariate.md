# Profile: `src/nirizan/regression/multivariate.py`

- Functions executed: **26**
- Total internal time: **0.008792 s**

## Executed functions (sorted by cumulative time)

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
| `MultivariateVerdict` | 255 | 1 | 0.000011 | 0.000011 | 0.000076 | 0.000076 | pydantic 0.000065s |
| `MultivariateComparator._inconclusive_verdicts` | 606 | 4 | 0.000024 | 0.000006 | 0.000061 | 0.000015 | pydantic 0.000037s |
| `classify_structure_severity` | 290 | 42 | 0.000049 | 0.000001 | 0.000049 | 0.000001 | - |
| `ScoreMatrix.n_metrics` | 245 | 74 | 0.000042 | 0.000001 | 0.000042 | 0.000001 | - |
| `apply_mode` | 320 | 45 | 0.000041 | 0.000001 | 0.000041 | 0.000001 | - |
| `ScoreMatrix.n_rows` | 241 | 75 | 0.000035 | 0.000000 | 0.000035 | 0.000000 | - |
| `MultivariateConfig.validate_effect_ordering` | 104 | 38 | 0.000034 | 0.000001 | 0.000034 | 0.000001 | - |
| `MultivariateMode` | 58 | 1 | 0.000003 | 0.000003 | 0.000032 | 0.000032 | stdlib:enum 0.000029s |
| `MultivariateMethod` | 71 | 1 | 0.000002 | 0.000002 | 0.000030 | 0.000030 | stdlib:enum 0.000028s |
| `MultivariateComparator` | 370 | 1 | 0.000004 | 0.000004 | 0.000004 | 0.000004 | - |
| `InsufficientDataError` | 117 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |
