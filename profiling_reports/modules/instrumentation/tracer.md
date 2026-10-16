# Profile: `src/nirizan/instrumentation/tracer.py`

- Functions executed: **8**
- Total internal time: **0.000374 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `Tracer.start_span` | 55 | 48 | 0.000237 | 0.000005 | 0.001356 | 0.000028 | stdlib:uuid 0.000237s, pydantic 0.000158s, built-ins (C) 0.000088s |
| `<module> (import time)` | 1 | 1 | 0.000028 | 0.000028 | 0.000467 | 0.000467 | stdlib:dataclasses 0.000385s, built-ins (C) 0.000054s |
| `Tracer.get_assembled_trace` | 120 | 14 | 0.000055 | 0.000004 | 0.000350 | 0.000025 | pydantic 0.000214s, built-ins (C) 0.000035s |
| `Tracer.session` | 45 | 8 | 0.000011 | 0.000001 | 0.000059 | 0.000007 | stdlib:uuid 0.000044s, built-ins (C) 0.000005s |
| `<listcomp>` | 123 | 14 | 0.000026 | 0.000002 | 0.000046 | 0.000003 | stdlib:uuid 0.000020s |
| `Tracer` | 33 | 1 | 0.000009 | 0.000009 | 0.000024 | 0.000024 | stdlib:contextlib 0.000015s |
| `Tracer.__init__` | 36 | 9 | 0.000006 | 0.000001 | 0.000006 | 0.000001 | - |
| `SpanHandle` | 25 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

## Functions never executed by the tests

- `Tracer.clear` (line 133)
