# Profile: `src/nirizan/metrics/statistical_gating.py`

- Functions executed: **7**
- Total internal time: **0.000049 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000016 | 0.000016 | 0.979328 | 0.979328 | frozen/internal 0.979301s |
| `mann_whitney_regression` | 46 | 2 | 0.000008 | 0.000004 | 0.001355 | 0.000678 | stdlib:logging 0.000123s, built-ins (C) 0.000002s |
| `bootstrap_delta_ci` | 74 | 2 | 0.000006 | 0.000003 | 0.000483 | 0.000241 | stdlib:logging 0.000117s |
| `approximate_sample_size` | 146 | 5 | 0.000006 | 0.000001 | 0.000327 | 0.000065 | stdlib:logging 0.000062s |
| `validate_scores` | 41 | 8 | 0.000004 | 0.000000 | 0.000195 | 0.000024 | - |
| `holm_bonferroni` | 121 | 3 | 0.000004 | 0.000001 | 0.000122 | 0.000041 | stdlib:logging 0.000109s |
| `calibrate_gold_set` | 172 | 2 | 0.000004 | 0.000002 | 0.000089 | 0.000045 | stdlib:logging 0.000054s |
