# Profile: `src/nirizan/regression/multivariate.py`

- Functions executed: **26**
- Total internal time: **0.005546 s**

## Executed functions (sorted by cumulative time)

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
| `<dictcomp>` | 671 | 3 | 0.000010 | 0.000003 | 0.000079 | 0.000026 | built-ins (C) 0.000069s |
| `classify_structure_severity` | 290 | 42 | 0.000044 | 0.000001 | 0.000044 | 0.000001 | - |
| `MultivariateComparator._inconclusive_verdicts` | 606 | 4 | 0.000019 | 0.000005 | 0.000041 | 0.000010 | pydantic 0.000022s |
| `apply_mode` | 320 | 45 | 0.000040 | 0.000001 | 0.000040 | 0.000001 | - |
| `ScoreMatrix.n_metrics` | 245 | 74 | 0.000038 | 0.000001 | 0.000038 | 0.000001 | - |
| `ScoreMatrix.n_rows` | 241 | 75 | 0.000027 | 0.000000 | 0.000027 | 0.000000 | - |
| `MultivariateMode` | 58 | 1 | 0.000002 | 0.000002 | 0.000022 | 0.000022 | stdlib:enum 0.000021s |
| `MultivariateConfig.validate_effect_ordering` | 104 | 38 | 0.000021 | 0.000001 | 0.000021 | 0.000001 | - |
| `MultivariateMethod` | 71 | 1 | 0.000002 | 0.000002 | 0.000018 | 0.000018 | stdlib:enum 0.000017s |
| `MultivariateComparator` | 370 | 1 | 0.000004 | 0.000004 | 0.000004 | 0.000004 | - |
| `InsufficientDataError` | 117 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |
