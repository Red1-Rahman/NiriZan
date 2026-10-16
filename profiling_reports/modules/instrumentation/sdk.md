# Profile: `src/nirizan/instrumentation/sdk.py`

- Functions executed: **12**
- Total internal time: **0.000137 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000033 | 0.000033 | 0.001691 | 0.001691 | frozen/internal 0.001614s, stdlib:typing 0.000016s |
| `trace_span.<locals>.decorator.<locals>.wrapper` | 63 | 7/5 | 0.000060 | 0.000009 | 0.000489 | 0.000098 | stdlib:contextlib 0.000410s, other 0.000094s, stdlib:_weakrefset 0.000008s |
| `init_tracer` | 22 | 2 | 0.000011 | 0.000005 | 0.000307 | 0.000154 | stdlib:logging 0.000294s |
| `trace_span.<locals>.decorator` | 60 | 7 | 0.000015 | 0.000002 | 0.000052 | 0.000007 | stdlib:functools 0.000037s |
| `start_session` | 36 | 1 | 0.000003 | 0.000003 | 0.000013 | 0.000013 | stdlib:logging 0.000006s, stdlib:contextlib 0.000003s |
| `_format_input_payload` | 45 | 7 | 0.000005 | 0.000001 | 0.000005 | 0.000001 | - |
| `trace_span` | 53 | 7 | 0.000004 | 0.000001 | 0.000004 | 0.000001 | - |
| `planning` | 86 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `tool_use` | 110 | 1 | 0.000001 | 0.000001 | 0.000002 | 0.000002 | - |
| `generation` | 102 | 1 | 0.000001 | 0.000001 | 0.000002 | 0.000002 | - |
| `retrieval` | 94 | 1 | 0.000001 | 0.000001 | 0.000002 | 0.000002 | - |
| `get_tracer` | 31 | 8 | 0.000002 | 0.000000 | 0.000002 | 0.000000 | - |
