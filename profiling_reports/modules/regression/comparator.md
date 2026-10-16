# Profile: `src/nirizan/regression/comparator.py`

- Functions executed: **10**
- Total internal time: **0.000448 s**

## Executed functions (sorted by cumulative time)

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
