# Profile: `src/nirizan/instrumentation/tracer.py`

- Functions executed: **8**
- Total internal time: **0.000268 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `Tracer.start_span` | 54 | 48 | 0.000163 | 0.000003 | 0.000806 | 0.000017 | stdlib:uuid 0.000136s, pydantic 0.000106s, built-ins (C) 0.000067s |
| `<module> (import time)` | 1 | 1 | 0.000026 | 0.000026 | 0.000453 | 0.000453 | stdlib:dataclasses 0.000302s, built-ins (C) 0.000126s |
| `Tracer.get_assembled_trace` | 116 | 14 | 0.000037 | 0.000003 | 0.000148 | 0.000011 | pydantic 0.000077s, built-ins (C) 0.000005s |
| `Tracer` | 32 | 1 | 0.000010 | 0.000010 | 0.000097 | 0.000097 | stdlib:typing 0.000077s, stdlib:contextlib 0.000010s |
| `Tracer.session` | 44 | 8 | 0.000011 | 0.000001 | 0.000052 | 0.000007 | stdlib:uuid 0.000036s, built-ins (C) 0.000005s |
| `<listcomp>` | 119 | 14 | 0.000017 | 0.000001 | 0.000029 | 0.000002 | stdlib:uuid 0.000012s |
| `Tracer.__init__` | 35 | 9 | 0.000005 | 0.000001 | 0.000005 | 0.000001 | - |
| `SpanHandle` | 24 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

## Functions never executed by the tests

- `Tracer.clear` (line 129)
