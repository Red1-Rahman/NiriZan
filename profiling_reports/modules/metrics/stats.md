# Profile: `src/nirizan/metrics/stats.py`

- Functions executed: **23**
- Total internal time: **0.165229 s**

## Executed functions (sorted by cumulative time)

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
| `_as_validated_pair` | 86 | 72 | 0.000754 | 0.000010 | 0.001838 | 0.000026 | numpy 0.000733s, built-ins (C) 0.000351s |
| `cohens_d` | 119 | 22 | 0.000078 | 0.000004 | 0.001565 | 0.000071 | built-ins (C) 0.000864s |
| `calculate_sample_size` | 234 | 11 | 0.000032 | 0.000003 | 0.000548 | 0.000050 | scipy 0.000515s |
| `scale_logvar_statistic` | 386 | 13 | 0.000018 | 0.000001 | 0.000461 | 0.000035 | built-ins (C) 0.000003s |
| `holm_bonferroni` | 202 | 56 | 0.000260 | 0.000005 | 0.000435 | 0.000008 | built-ins (C) 0.000175s |
| `permutation_p_value` | 279 | 48 | 0.000232 | 0.000005 | 0.000404 | 0.000008 | built-ins (C) 0.000173s |
| `compute_calibration_metrics` | 257 | 4 | 0.000028 | 0.000007 | 0.000073 | 0.000018 | numpy 0.000044s, built-ins (C) 0.000002s |
| `<lambda>` | 214 | 112 | 0.000014 | 0.000000 | 0.000014 | 0.000000 | - |
