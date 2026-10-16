# Profile: `src/nirizan/metrics/stats.py`

- Functions executed: **23**
- Total internal time: **0.403086 s**

## Executed functions (sorted by cumulative time)

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
| `_as_validated_pair` | 86 | 72 | 0.001389 | 0.000019 | 0.003333 | 0.000046 | numpy 0.001375s, built-ins (C) 0.000569s |
| `cohens_d` | 119 | 22 | 0.000115 | 0.000005 | 0.003016 | 0.000137 | built-ins (C) 0.001546s |
| `scale_logvar_statistic` | 386 | 13 | 0.000033 | 0.000003 | 0.000885 | 0.000068 | built-ins (C) 0.000004s |
| `calculate_sample_size` | 234 | 11 | 0.000042 | 0.000004 | 0.000841 | 0.000076 | scipy 0.000799s |
| `holm_bonferroni` | 202 | 56 | 0.000325 | 0.000006 | 0.000535 | 0.000010 | built-ins (C) 0.000210s |
| `permutation_p_value` | 279 | 48 | 0.000262 | 0.000005 | 0.000517 | 0.000011 | built-ins (C) 0.000254s |
| `compute_calibration_metrics` | 257 | 4 | 0.000037 | 0.000009 | 0.000111 | 0.000028 | numpy 0.000070s, built-ins (C) 0.000004s |
| `<lambda>` | 214 | 112 | 0.000021 | 0.000000 | 0.000021 | 0.000000 | - |
