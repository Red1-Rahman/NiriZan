# Profile: `src/nirizan/instrumentation/otel/_id_mapping.py`

- Functions executed: **8**
- Total internal time: **0.027866 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `otel_trace_id_to_derived_uuid` | 94 | 10013 | 0.010745 | 0.000001 | 0.081738 | 0.000008 | stdlib:uuid 0.064834s |
| `otel_span_id_to_uuid` | 142 | 5016 | 0.010346 | 0.000002 | 0.031642 | 0.000006 | stdlib:uuid 0.014280s, built-ins (C) 0.003898s |
| `is_valid_otel_trace_id` | 38 | 10069 | 0.004440 | 0.000000 | 0.006211 | 0.000001 | built-ins (C) 0.001772s |
| `is_valid_otel_span_id` | 51 | 5040 | 0.002260 | 0.000000 | 0.003142 | 0.000001 | built-ins (C) 0.000882s |
| `otel_trace_id_to_uuid` | 76 | 20 | 0.000038 | 0.000002 | 0.000092 | 0.000005 | stdlib:uuid 0.000036s |
| `uuid_to_otel_trace_id` | 64 | 17 | 0.000014 | 0.000001 | 0.000034 | 0.000002 | stdlib:uuid 0.000004s |
| `<module> (import time)` | 1 | 1 | 0.000015 | 0.000015 | 0.000032 | 0.000032 | stdlib:uuid 0.000018s |
| `uuid_to_otel_span_id` | 123 | 6 | 0.000008 | 0.000001 | 0.000017 | 0.000003 | stdlib:uuid 0.000003s |
