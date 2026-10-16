# Profile: `src/nirizan/instrumentation/spans.py`

- Functions executed: **8**
- Total internal time: **0.005008 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000013 | 0.000013 | 0.024417 | 0.024417 | built-ins (C) 0.024360s, frozen/internal 0.000044s |
| `Trace.validate_span_trace_ids` | 64 | 82 | 0.002872 | 0.000035 | 0.008858 | 0.000108 | stdlib:uuid 0.002083s |
| `<setcomp>` | 77 | 82 | 0.002044 | 0.000025 | 0.003901 | 0.000048 | stdlib:uuid 0.001857s |
| `Trace` | 51 | 1 | 0.000015 | 0.000015 | 0.000136 | 0.000136 | pydantic 0.000121s |
| `Span` | 34 | 1 | 0.000019 | 0.000019 | 0.000091 | 0.000091 | pydantic 0.000072s |
| `SpanKind` | 25 | 1 | 0.000004 | 0.000004 | 0.000046 | 0.000046 | stdlib:enum 0.000042s |
| `Trace.spans_of_kind` | 93 | 25 | 0.000024 | 0.000001 | 0.000042 | 0.000002 | - |
| `<listcomp>` | 95 | 25 | 0.000018 | 0.000001 | 0.000018 | 0.000001 | - |
