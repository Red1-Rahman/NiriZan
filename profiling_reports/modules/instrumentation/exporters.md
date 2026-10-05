# Profile: `src/nirizan/instrumentation/exporters.py`

- Functions executed: **9**
- Total internal time: **0.000024 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000010 | 0.000010 | 0.000106 | 0.000106 | built-ins (C) 0.000064s, stdlib:logging 0.000032s |
| `ConsoleExporter.export` | 42 | 1 | 0.000001 | 0.000001 | 0.000073 | 0.000073 | stdlib:logging 0.000072s |
| `InMemoryExporter.export` | 29 | 8 | 0.000003 | 0.000000 | 0.000003 | 0.000000 | - |
| `BaseExporter` | 10 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `InMemoryExporter.get_traces` | 32 | 7 | 0.000002 | 0.000000 | 0.000002 | 0.000000 | - |
| `InMemoryExporter` | 23 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `InMemoryExporter.__init__` | 26 | 5 | 0.000002 | 0.000000 | 0.000002 | 0.000000 | - |
| `InMemoryExporter.clear` | 35 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `ConsoleExporter` | 39 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |

## Functions never executed by the tests

- `BaseExporter.export` (line 13)
- `BaseExporter.shutdown` (line 18)
