# Profile: `src/nirizan/instrumentation/spans.py`

- Functions executed: **7**
- Total internal time: **0.000105 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000010 | 0.000010 | 0.004265 | 0.004265 | built-ins (C) 0.004253s, frozen/internal 0.000002s |
| `Trace` | 37 | 1 | 0.000012 | 0.000012 | 0.000153 | 0.000153 | pydantic 0.000140s |
| `Span` | 20 | 1 | 0.000010 | 0.000010 | 0.000096 | 0.000096 | pydantic 0.000086s |
| `Trace.validate_span_trace_ids` | 50 | 34 | 0.000046 | 0.000001 | 0.000068 | 0.000002 | stdlib:uuid 0.000021s |
| `SpanKind` | 11 | 1 | 0.000003 | 0.000003 | 0.000032 | 0.000032 | stdlib:enum 0.000029s |
| `Trace.spans_of_kind` | 61 | 25 | 0.000015 | 0.000001 | 0.000025 | 0.000001 | - |
| `<listcomp>` | 63 | 25 | 0.000009 | 0.000000 | 0.000009 | 0.000000 | - |
