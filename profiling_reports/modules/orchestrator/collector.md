# Profile: `src/nirizan/orchestrator/collector.py`

- Functions executed: **13**
- Total internal time: **0.000211 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `TraceCollector._process_queue` | 84 | 24 | 0.000066 | 0.000003 | 0.004796 | 0.000200 | stdlib:asyncio 0.000330s, stdlib:_weakrefset 0.000004s |
| `TraceCollector.__init__` | 45 | 5 | 0.000034 | 0.000007 | 0.003475 | 0.000695 | stdlib:asyncio 0.000046s |
| `_resolve_code_commit` | 14 | 5 | 0.000025 | 0.000005 | 0.003379 | 0.000676 | stdlib:subprocess 0.003336s, frozen/internal 0.000017s |
| `CollectorExporter.export` | 103 | 7 | 0.000009 | 0.000001 | 0.000177 | 0.000025 | - |
| `TraceCollector.enqueue_trace` | 74 | 7 | 0.000021 | 0.000003 | 0.000168 | 0.000024 | pydantic 0.000092s, stdlib:asyncio 0.000054s |
| `<module> (import time)` | 1 | 1 | 0.000021 | 0.000021 | 0.000132 | 0.000132 | built-ins (C) 0.000082s, stdlib:logging 0.000026s, stdlib:typing 0.000002s |
| `TraceCollector.start` | 56 | 5 | 0.000013 | 0.000003 | 0.000071 | 0.000014 | stdlib:asyncio 0.000058s |
| `TraceCollector.stop` | 63 | 10 | 0.000013 | 0.000001 | 0.000030 | 0.000003 | built-ins (C) 0.000015s, stdlib:asyncio 0.000001s |
| `_resolve_data_snapshot_id` | 31 | 5 | 0.000004 | 0.000001 | 0.000016 | 0.000003 | frozen/internal 0.000012s |
| `CollectorExporter.__init__` | 100 | 5 | 0.000003 | 0.000001 | 0.000003 | 0.000001 | - |
| `TraceCollector` | 42 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `CollectorExporter` | 97 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `TraceSink` | 36 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

## Functions never executed by the tests

- `TraceSink.save` (line 39)
