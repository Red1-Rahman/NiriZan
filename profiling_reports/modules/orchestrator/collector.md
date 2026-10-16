# Profile: `src/nirizan/orchestrator/collector.py`

- Functions executed: **13**
- Total internal time: **0.000652 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `TraceCollector.__init__` | 45 | 17 | 0.000085 | 0.000005 | 0.023038 | 0.001355 | stdlib:asyncio 0.000095s |
| `_resolve_code_commit` | 14 | 17 | 0.000114 | 0.000007 | 0.022751 | 0.001338 | stdlib:subprocess 0.022547s, frozen/internal 0.000086s, built-ins (C) 0.000004s |
| `TraceCollector._process_queue` | 84 | 57 | 0.000241 | 0.000004 | 0.008626 | 0.000151 | stdlib:asyncio 0.001294s, other 0.000677s, stdlib:logging 0.000412s |
| `TraceCollector.enqueue_trace` | 74 | 26 | 0.000064 | 0.000002 | 0.000606 | 0.000023 | pydantic 0.000323s, stdlib:asyncio 0.000219s |
| `CollectorExporter.export` | 103 | 18 | 0.000022 | 0.000001 | 0.000475 | 0.000026 | - |
| `TraceCollector.start` | 56 | 16 | 0.000038 | 0.000002 | 0.000300 | 0.000019 | stdlib:asyncio 0.000262s |
| `TraceCollector.stop` | 63 | 32 | 0.000041 | 0.000001 | 0.000170 | 0.000005 | stdlib:asyncio 0.000093s, built-ins (C) 0.000036s |
| `<module> (import time)` | 1 | 1 | 0.000021 | 0.000021 | 0.000130 | 0.000130 | built-ins (C) 0.000087s, stdlib:logging 0.000020s, stdlib:typing 0.000002s |
| `_resolve_data_snapshot_id` | 31 | 17 | 0.000018 | 0.000001 | 0.000107 | 0.000006 | frozen/internal 0.000089s |
| `CollectorExporter.__init__` | 100 | 12 | 0.000005 | 0.000000 | 0.000005 | 0.000000 | - |
| `TraceCollector` | 42 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `CollectorExporter` | 97 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `TraceSink` | 36 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

## Functions never executed by the tests

- `TraceSink.save` (line 39)
