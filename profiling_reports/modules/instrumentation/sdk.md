# Profile: `src/nirizan/instrumentation/sdk.py`

- Functions executed: **12**
- Total internal time: **0.000099 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000029 | 0.000029 | 0.001316 | 0.001316 | frozen/internal 0.001238s, stdlib:typing 0.000012s |
| `trace_span.<locals>.decorator.<locals>.wrapper` | 62 | 7/5 | 0.000041 | 0.000006 | 0.000257 | 0.000051 | stdlib:contextlib 0.000205s, other 0.000051s, stdlib:_weakrefset 0.000004s |
| `init_tracer` | 21 | 2 | 0.000008 | 0.000004 | 0.000124 | 0.000062 | stdlib:logging 0.000115s |
| `trace_span.<locals>.decorator` | 59 | 7 | 0.000009 | 0.000001 | 0.000031 | 0.000004 | stdlib:functools 0.000022s |
| `start_session` | 35 | 1 | 0.000003 | 0.000003 | 0.000009 | 0.000009 | stdlib:contextlib 0.000003s, stdlib:logging 0.000003s |
| `_format_input_payload` | 44 | 7 | 0.000003 | 0.000000 | 0.000004 | 0.000001 | - |
| `trace_span` | 52 | 7 | 0.000002 | 0.000000 | 0.000002 | 0.000000 | - |
| `planning` | 85 | 1 | 0.000001 | 0.000001 | 0.000002 | 0.000002 | - |
| `get_tracer` | 30 | 8 | 0.000001 | 0.000000 | 0.000001 | 0.000000 | - |
| `retrieval` | 93 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `tool_use` | 109 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `generation` | 101 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
