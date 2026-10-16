# Profile: `src/nirizan/instrumentation/otel/semconv.py`

- Functions executed: **8**
- Total internal time: **0.017153 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `encode_sequence_attribute_value` | 305 | 623 | 0.010147 | 0.000016 | 0.037854 | 0.000061 | built-ins (C) 0.002913s, other 0.000170s |
| `_dumps_item` | 297 | 7679 | 0.002173 | 0.000000 | 0.024199 | 0.000003 | - |
| `dumps_attribute_json` | 267 | 8072 | 0.004764 | 0.000001 | 0.022663 | 0.000003 | stdlib:json 0.016588s, built-ins (C) 0.001311s |
| `<module> (import time)` | 1 | 1 | 0.000035 | 0.000035 | 0.000038 | 0.000038 | stdlib:json 0.000003s |
| `encode_sequence_key` | 235 | 9 | 0.000012 | 0.000001 | 0.000017 | 0.000002 | built-ins (C) 0.000001s |
| `truncate_attribute_value` | 201 | 7 | 0.000011 | 0.000002 | 0.000012 | 0.000002 | built-ins (C) 0.000002s |
| `decode_sequence_key` | 248 | 5 | 0.000006 | 0.000001 | 0.000010 | 0.000002 | - |
| `is_sequence_key` | 255 | 13 | 0.000006 | 0.000000 | 0.000010 | 0.000001 | built-ins (C) 0.000004s |
