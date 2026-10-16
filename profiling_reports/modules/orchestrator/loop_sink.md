# Profile: `src/nirizan/orchestrator/loop_sink.py`

- Functions executed: **6**
- Total internal time: **0.000047 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `LoopTraceSink.enqueue_trace` | 53 | 2 | 0.000017 | 0.000009 | 0.000444 | 0.000222 | stdlib:logging 0.000391s, stdlib:asyncio 0.000031s, built-ins (C) 0.000004s |
| `<module> (import time)` | 1 | 1 | 0.000019 | 0.000019 | 0.000154 | 0.000154 | built-ins (C) 0.000098s, stdlib:logging 0.000034s, frozen/internal 0.000003s |
| `_log_failure` | 73 | 3 | 0.000006 | 0.000002 | 0.000133 | 0.000044 | stdlib:logging 0.000114s, stdlib:concurrent 0.000013s |
| `LoopTraceSink.__init__` | 49 | 5 | 0.000004 | 0.000001 | 0.000004 | 0.000001 | - |
| `LoopTraceSink` | 40 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `_AsyncTraceCollector` | 34 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

## Functions never executed by the tests

- `_AsyncTraceCollector.enqueue_trace` (line 37)
