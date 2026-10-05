# Profile: `src/nirizan/storage/baselines.py`

- Functions executed: **13**
- Total internal time: **0.000165 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `SQLiteBaselineRepository.__init__` | 23 | 4 | 0.000036 | 0.000009 | 0.008479 | 0.002120 | built-ins (C) 0.000352s |
| `SQLiteBaselineRepository._init_db` | 29 | 4 | 0.000016 | 0.000004 | 0.008092 | 0.002023 | built-ins (C) 0.008076s |
| `<module> (import time)` | 1 | 1 | 0.000015 | 0.000015 | 0.005053 | 0.005053 | frozen/internal 0.004990s, built-ins (C) 0.000048s |
| `SQLiteBaselineRepository.save_baseline` | 45 | 10 | 0.000032 | 0.000003 | 0.000833 | 0.000083 | stdlib:asyncio 0.000718s, stdlib:json 0.000060s |
| `SQLiteBaselineRepository.get_baseline` | 67 | 4 | 0.000010 | 0.000003 | 0.000322 | 0.000080 | stdlib:asyncio 0.000253s, stdlib:uuid 0.000005s |
| `SQLiteBaselineRepository.list_baselines` | 81 | 6 | 0.000008 | 0.000001 | 0.000157 | 0.000026 | stdlib:asyncio 0.000065s |
| `SQLiteBaselineRepository.close` | 100 | 4 | 0.000006 | 0.000002 | 0.000139 | 0.000035 | built-ins (C) 0.000133s |
| `SQLiteBaselineRepository._row_to_baseline` | 91 | 4 | 0.000025 | 0.000006 | 0.000135 | 0.000034 | stdlib:json 0.000044s, pydantic 0.000024s, stdlib:uuid 0.000022s |
| `<listcomp>` | 89 | 3 | 0.000003 | 0.000001 | 0.000084 | 0.000028 | - |
| `<listcomp>` | 46 | 5 | 0.000007 | 0.000001 | 0.000022 | 0.000004 | stdlib:uuid 0.000015s |
| `<listcomp>` | 95 | 4 | 0.000004 | 0.000001 | 0.000016 | 0.000004 | stdlib:uuid 0.000012s |
| `SQLiteBaselineRepository` | 20 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `BaselineRepository` | 14 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

## Functions never executed by the tests

- `BaselineRepository.save_baseline` (line 15)
- `BaselineRepository.get_baseline` (line 16)
- `BaselineRepository.list_baselines` (line 17)
- `SQLiteBaselineRepository.save_baseline.<locals>._insert` (line 48)
- `SQLiteBaselineRepository.get_baseline.<locals>._query` (line 70)
- `SQLiteBaselineRepository.list_baselines.<locals>._query` (line 82)
