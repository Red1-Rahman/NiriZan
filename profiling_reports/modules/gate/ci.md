# Profile: `src/nirizan/gate/ci.py`

- Functions executed: **5**
- Total internal time: **0.000257 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `gate_exit_code` | 87 | 4 | 0.000035 | 0.000009 | 0.000648 | 0.000162 | stdlib:logging 0.000613s |
| `serialize_gate_verdict` | 95 | 3 | 0.000023 | 0.000008 | 0.000639 | 0.000213 | stdlib:json 0.000432s, stdlib:logging 0.000119s, pydantic 0.000065s |
| `write_github_summary` | 70 | 4 | 0.000017 | 0.000004 | 0.000420 | 0.000105 | stdlib:logging 0.000325s, built-ins (C) 0.000002s |
| `format_gate_summary` | 23 | 12 | 0.000170 | 0.000014 | 0.000218 | 0.000018 | stdlib:enum 0.000033s, built-ins (C) 0.000014s |
| `<module> (import time)` | 1 | 1 | 0.000012 | 0.000012 | 0.000033 | 0.000033 | - |
