# Profile: `src/nirizan/storage/models.py`

- Functions executed: **18**
- Total internal time: **0.066654 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000038 | 0.000038 | 1.631420 | 1.631420 | frozen/internal 1.624845s, built-ins (C) 0.006514s |
| `TraceRecord.from_trace` | 143 | 59 | 0.000362 | 0.000006 | 0.148964 | 0.002525 | pydantic 0.000395s, stdlib:uuid 0.000228s |
| `<listcomp>` | 149 | 57 | 0.004255 | 0.000075 | 0.147461 | 0.002587 | - |
| `SpanRecord.from_span` | 100 | 8041 | 0.031679 | 0.000004 | 0.143321 | 0.000018 | stdlib:json 0.031157s, stdlib:uuid 0.016736s, pydantic 0.015629s |
| `TraceRecord.to_trace` | 155 | 84 | 0.000505 | 0.000006 | 0.061364 | 0.000731 | pydantic 0.001168s, stdlib:uuid 0.000585s |
| `<listcomp>` | 176 | 81 | 0.001321 | 0.000016 | 0.058352 | 0.000720 | - |
| `SpanRecord.to_span` | 115 | 2862 | 0.011411 | 0.000004 | 0.057124 | 0.000020 | stdlib:uuid 0.017252s, stdlib:json 0.011547s, pydantic 0.006440s |
| `_utc_isoformat` | 47 | 16142 | 0.012287 | 0.000001 | 0.044342 | 0.000003 | built-ins (C) 0.032055s |
| `_parse_utc_datetime` | 54 | 5823 | 0.004694 | 0.000001 | 0.009033 | 0.000002 | built-ins (C) 0.003645s |
| `_warn_legacy_naive_once` | 75 | 18 | 0.000023 | 0.000001 | 0.000693 | 0.000039 | stdlib:logging 0.000648s |
| `Run` | 183 | 1 | 0.000012 | 0.000012 | 0.000105 | 0.000105 | pydantic 0.000092s |
| `Baseline` | 197 | 1 | 0.000010 | 0.000010 | 0.000059 | 0.000059 | pydantic 0.000049s |
| `TraceRecord` | 132 | 1 | 0.000013 | 0.000013 | 0.000042 | 0.000042 | pydantic 0.000030s |
| `_OnceLatch.claim` | 33 | 18 | 0.000020 | 0.000001 | 0.000023 | 0.000001 | built-ins (C) 0.000003s |
| `SpanRecord` | 86 | 1 | 0.000012 | 0.000012 | 0.000020 | 0.000020 | pydantic 0.000008s |
| `_OnceLatch.__init__` | 29 | 8 | 0.000010 | 0.000001 | 0.000014 | 0.000002 | built-ins (C) 0.000004s |
| `_OnceLatch` | 16 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `<listcomp>` | 167 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |
