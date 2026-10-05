# Profile: `src/nirizan/orchestrator/scheduler.py`

- Functions executed: **6**
- Total internal time: **0.000028 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000014 | 0.000014 | 0.006406 | 0.006406 | frozen/internal 0.006342s, built-ins (C) 0.000050s |
| `RunScheduler.run_on_demand` | 51 | 2 | 0.000012 | 0.000006 | 0.000350 | 0.000175 | stdlib:uuid 0.000007s, pydantic 0.000005s |
| `RunScheduler.__init__` | 41 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `TraceSource` | 18 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `RunSink` | 28 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |
| `RunScheduler` | 38 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |

## Functions never executed by the tests

- `TraceSource.list_by_application` (line 21)
- `RunSink.save_run` (line 35)
