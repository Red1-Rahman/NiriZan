# Profile: `src/nirizan/trust/attribution.py`

- Functions executed: **10**
- Total internal time: **0.001227 s**

## Executed functions (sorted by cumulative time)

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
