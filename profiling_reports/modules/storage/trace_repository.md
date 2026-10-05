# Profile: `src/nirizan/storage/trace_repository.py`

- Functions executed: **9**
- Total internal time: **0.000135 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `SQLiteTraceRepository.__init__` | 53 | 4 | 0.000028 | 0.000007 | 0.025980 | 0.006495 | built-ins (C) 0.000362s |
| `SQLiteTraceRepository._init_db` | 60 | 4 | 0.000020 | 0.000005 | 0.025590 | 0.006398 | built-ins (C) 0.025570s |
| `SQLiteTraceRepository.save` | 98 | 14 | 0.000031 | 0.000002 | 0.004396 | 0.000314 | stdlib:asyncio 0.003988s |
| `SQLiteTraceRepository.list_by_application` | 188 | 12 | 0.000021 | 0.000002 | 0.000695 | 0.000058 | stdlib:asyncio 0.000181s |
| `<listcomp>` | 238 | 6 | 0.000010 | 0.000002 | 0.000493 | 0.000082 | - |
| `SQLiteTraceRepository.close` | 251 | 4 | 0.000007 | 0.000002 | 0.000167 | 0.000042 | built-ins (C) 0.000160s |
| `<module> (import time)` | 1 | 1 | 0.000011 | 0.000011 | 0.000120 | 0.000120 | built-ins (C) 0.000109s |
| `BaseTraceRepository` | 12 | 1 | 0.000006 | 0.000006 | 0.000073 | 0.000073 | stdlib:typing 0.000066s |
| `SQLiteTraceRepository` | 50 | 1 | 0.000002 | 0.000002 | 0.000003 | 0.000003 | - |

## Functions never executed by the tests

- `BaseTraceRepository.save` (line 22)
- `BaseTraceRepository.get` (line 27)
- `BaseTraceRepository.list_by_application` (line 34)
- `BaseTraceRepository.purge_older_than` (line 44)
- `SQLiteTraceRepository.save.<locals>._insert` (line 101)
- `SQLiteTraceRepository.get` (line 143)
- `SQLiteTraceRepository.get.<locals>._query` (line 146)
- `SQLiteTraceRepository.list_by_application.<locals>._query_list` (line 194)
- `SQLiteTraceRepository.purge_older_than` (line 240)
- `SQLiteTraceRepository.purge_older_than.<locals>._delete` (line 241)
