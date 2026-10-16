# Profile: `src/nirizan/metrics/statistical_gating.py`

- Functions executed: **7**
- Total internal time: **0.000081 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000030 | 0.000030 | 1.495181 | 1.495181 | frozen/internal 1.495134s |
| `mann_whitney_regression` | 46 | 2 | 0.000012 | 0.000006 | 0.002053 | 0.001027 | stdlib:logging 0.000216s, built-ins (C) 0.000003s |
| `bootstrap_delta_ci` | 74 | 2 | 0.000008 | 0.000004 | 0.000755 | 0.000377 | stdlib:logging 0.000204s |
| `approximate_sample_size` | 146 | 5 | 0.000010 | 0.000002 | 0.000550 | 0.000110 | stdlib:logging 0.000131s |
| `validate_scores` | 41 | 8 | 0.000008 | 0.000001 | 0.000327 | 0.000041 | - |
| `holm_bonferroni` | 121 | 3 | 0.000007 | 0.000002 | 0.000217 | 0.000072 | stdlib:logging 0.000199s |
| `calibrate_gold_set` | 172 | 2 | 0.000006 | 0.000003 | 0.000153 | 0.000077 | stdlib:logging 0.000099s |
