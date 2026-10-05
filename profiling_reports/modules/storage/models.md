# Profile: `src/nirizan/storage/models.py`

- Functions executed: **11**
- Total internal time: **0.000323 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000016 | 0.000016 | 0.005353 | 0.005353 | built-ins (C) 0.005333s, frozen/internal 0.000004s |
| `TraceRecord.to_trace` | 81 | 10 | 0.000042 | 0.000004 | 0.000496 | 0.000050 | stdlib:uuid 0.000055s, pydantic 0.000045s, built-ins (C) 0.000007s |
| `TraceRecord.from_trace` | 69 | 8 | 0.000043 | 0.000005 | 0.000395 | 0.000049 | built-ins (C) 0.000034s, stdlib:uuid 0.000028s, pydantic 0.000024s |
| `SpanRecord.to_span` | 42 | 20 | 0.000079 | 0.000004 | 0.000363 | 0.000018 | stdlib:json 0.000115s, stdlib:uuid 0.000098s, pydantic 0.000045s |
| `<listcomp>` | 87 | 10 | 0.000013 | 0.000001 | 0.000347 | 0.000035 | - |
| `SpanRecord.from_span` | 27 | 14 | 0.000070 | 0.000005 | 0.000285 | 0.000020 | stdlib:json 0.000105s, built-ins (C) 0.000036s, pydantic 0.000035s |
| `<listcomp>` | 75 | 8 | 0.000015 | 0.000002 | 0.000264 | 0.000033 | - |
| `Run` | 94 | 1 | 0.000009 | 0.000009 | 0.000104 | 0.000104 | pydantic 0.000096s |
| `Baseline` | 107 | 1 | 0.000006 | 0.000006 | 0.000070 | 0.000070 | pydantic 0.000063s |
| `TraceRecord` | 58 | 1 | 0.000013 | 0.000013 | 0.000060 | 0.000060 | pydantic 0.000047s |
| `SpanRecord` | 13 | 1 | 0.000016 | 0.000016 | 0.000025 | 0.000025 | pydantic 0.000008s, stdlib:typing 0.000001s |
