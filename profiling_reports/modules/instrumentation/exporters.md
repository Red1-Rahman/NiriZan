# Profile: `src/nirizan/instrumentation/exporters.py`

- Functions executed: **9**
- Total internal time: **0.000035 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `ConsoleExporter.export` | 42 | 1 | 0.000004 | 0.000004 | 0.000149 | 0.000149 | stdlib:logging 0.000145s |
| `<module> (import time)` | 1 | 1 | 0.000013 | 0.000013 | 0.000117 | 0.000117 | built-ins (C) 0.000073s, stdlib:logging 0.000030s |
| `InMemoryExporter.export` | 29 | 8 | 0.000005 | 0.000001 | 0.000006 | 0.000001 | - |
| `InMemoryExporter.get_traces` | 32 | 7 | 0.000004 | 0.000001 | 0.000004 | 0.000001 | - |
| `BaseExporter` | 10 | 1 | 0.000002 | 0.000002 | 0.000003 | 0.000003 | - |
| `InMemoryExporter.__init__` | 26 | 5 | 0.000003 | 0.000001 | 0.000003 | 0.000001 | - |
| `InMemoryExporter` | 23 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `InMemoryExporter.clear` | 35 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `ConsoleExporter` | 39 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

## Functions never executed by the tests

- `BaseExporter.export` (line 13)
- `BaseExporter.shutdown` (line 18)
