# Profile: `src/nirizan/storage/trace_repository.py`

- Functions executed: **12**
- Total internal time: **0.001835 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `SQLiteTraceRepository.__init__` | 166 | 63 | 0.000342 | 0.000005 | 0.395388 | 0.006276 | built-ins (C) 0.006227s, stdlib:threading 0.000053s |
| `SQLiteTraceRepository._init_db` | 174 | 63 | 0.000330 | 0.000005 | 0.388766 | 0.006171 | built-ins (C) 0.388436s |
| `SQLiteTraceRepository.save` | 218 | 113 | 0.000277 | 0.000002 | 0.161302 | 0.001427 | stdlib:asyncio 0.012089s |
| `SQLiteTraceRepository.get` | 326 | 130 | 0.000402 | 0.000003 | 0.065588 | 0.000505 | stdlib:asyncio 0.005605s, stdlib:uuid 0.000198s |
| `SQLiteTraceRepository.list_by_application` | 361 | 38 | 0.000113 | 0.000003 | 0.003902 | 0.000103 | stdlib:asyncio 0.001959s |
| `SQLiteTraceRepository.close` | 479 | 63 | 0.000190 | 0.000003 | 0.002635 | 0.000042 | built-ins (C) 0.002445s |
| `SQLiteTraceRepository.purge_older_than` | 407 | 20 | 0.000063 | 0.000003 | 0.002077 | 0.000104 | stdlib:asyncio 0.001861s |
| `<listcomp>` | 405 | 19 | 0.000044 | 0.000002 | 0.001830 | 0.000096 | - |
| `_normalize_cutoff_to_utc` | 18 | 11 | 0.000045 | 0.000004 | 0.000132 | 0.000012 | built-ins (C) 0.000087s |
| `<module> (import time)` | 1 | 1 | 0.000021 | 0.000021 | 0.000077 | 0.000077 | built-ins (C) 0.000056s |
| `BaseTraceRepository` | 125 | 1 | 0.000005 | 0.000005 | 0.000006 | 0.000006 | - |
| `SQLiteTraceRepository` | 163 | 1 | 0.000003 | 0.000003 | 0.000003 | 0.000003 | - |

## Functions never executed by the tests

- `_span_depths` (line 37)
- `_span_record_from_row` (line 81)
- `_order_span_records` (line 97)
- `BaseTraceRepository.save` (line 135)
- `BaseTraceRepository.get` (line 140)
- `BaseTraceRepository.list_by_application` (line 147)
- `BaseTraceRepository.purge_older_than` (line 157)
- `SQLiteTraceRepository.save.<locals>._insert` (line 221)
- `SQLiteTraceRepository.get.<locals>._query` (line 329)
- `SQLiteTraceRepository.list_by_application.<locals>._query_list` (line 367)
- `SQLiteTraceRepository.list_by_application.<locals>._query_list_locked` (line 371)
- `SQLiteTraceRepository.purge_older_than.<locals>._delete` (line 422)
