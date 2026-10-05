# Profile: `src/nirizan/trust/attribution.py`

- Functions executed: **10**
- Total internal time: **0.000891 s**

## Executed functions (sorted by cumulative time)

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
