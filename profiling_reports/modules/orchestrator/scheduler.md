# Profile: `src/nirizan/orchestrator/scheduler.py`

- Functions executed: **6**
- Total internal time: **0.000034 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `RunScheduler.run_on_demand` | 51 | 2 | 0.000016 | 0.000008 | 0.000670 | 0.000335 | stdlib:uuid 0.000009s, pydantic 0.000007s, built-ins (C) 0.000001s |
| `<module> (import time)` | 1 | 1 | 0.000015 | 0.000015 | 0.000089 | 0.000089 | built-ins (C) 0.000074s |
| `RunSink` | 28 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `RunScheduler.__init__` | 41 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `TraceSource` | 18 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `RunScheduler` | 38 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

## Functions never executed by the tests

- `TraceSource.list_by_application` (line 21)
- `RunSink.save_run` (line 35)
