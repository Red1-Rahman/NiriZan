# Profile: `src/nirizan/gate/ci.py`

- Functions executed: **5**
- Total internal time: **0.000141 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `serialize_gate_verdict` | 95 | 3 | 0.000017 | 0.000006 | 0.000444 | 0.000148 | stdlib:json 0.000298s, stdlib:logging 0.000072s, pydantic 0.000057s |
| `gate_exit_code` | 87 | 4 | 0.000008 | 0.000002 | 0.000442 | 0.000110 | stdlib:logging 0.000433s |
| `write_github_summary` | 70 | 4 | 0.000011 | 0.000003 | 0.000262 | 0.000066 | stdlib:logging 0.000207s, built-ins (C) 0.000001s |
| `format_gate_summary` | 23 | 12 | 0.000095 | 0.000008 | 0.000125 | 0.000010 | stdlib:enum 0.000020s, built-ins (C) 0.000010s |
| `<module> (import time)` | 1 | 1 | 0.000009 | 0.000009 | 0.000033 | 0.000033 | - |
