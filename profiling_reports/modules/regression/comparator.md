# Profile: `src/nirizan/regression/comparator.py`

- Functions executed: **10**
- Total internal time: **0.000330 s**

## Executed functions (sorted by cumulative time)

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
