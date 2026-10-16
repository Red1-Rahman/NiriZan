# Profile: `src/nirizan/storage/baselines.py`

- Functions executed: **13**
- Total internal time: **0.000181 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000021 | 0.000021 | 0.031402 | 0.031402 | frozen/internal 0.031314s, built-ins (C) 0.000066s |
| `SQLiteBaselineRepository.__init__` | 23 | 4 | 0.000019 | 0.000005 | 0.013490 | 0.003372 | built-ins (C) 0.000376s |
| `SQLiteBaselineRepository._init_db` | 29 | 4 | 0.000016 | 0.000004 | 0.013095 | 0.003274 | built-ins (C) 0.013079s |
| `SQLiteBaselineRepository.save_baseline` | 45 | 10 | 0.000038 | 0.000004 | 0.000956 | 0.000096 | stdlib:asyncio 0.000827s, stdlib:json 0.000057s |
| `SQLiteBaselineRepository.get_baseline` | 67 | 4 | 0.000013 | 0.000003 | 0.000378 | 0.000095 | stdlib:asyncio 0.000279s, stdlib:uuid 0.000006s |
| `SQLiteBaselineRepository.list_baselines` | 81 | 6 | 0.000012 | 0.000002 | 0.000282 | 0.000047 | stdlib:asyncio 0.000169s |
| `SQLiteBaselineRepository._row_to_baseline` | 91 | 4 | 0.000030 | 0.000008 | 0.000177 | 0.000044 | stdlib:uuid 0.000051s, stdlib:json 0.000046s, pydantic 0.000021s |
| `SQLiteBaselineRepository.close` | 100 | 4 | 0.000006 | 0.000002 | 0.000152 | 0.000038 | built-ins (C) 0.000146s |
| `<listcomp>` | 89 | 3 | 0.000003 | 0.000001 | 0.000100 | 0.000033 | - |
| `<listcomp>` | 46 | 5 | 0.000012 | 0.000002 | 0.000034 | 0.000007 | stdlib:uuid 0.000022s |
| `<listcomp>` | 95 | 4 | 0.000006 | 0.000002 | 0.000026 | 0.000007 | stdlib:uuid 0.000020s |
| `SQLiteBaselineRepository` | 20 | 1 | 0.000003 | 0.000003 | 0.000003 | 0.000003 | - |
| `BaselineRepository` | 14 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

## Functions never executed by the tests

- `BaselineRepository.save_baseline` (line 15)
- `BaselineRepository.get_baseline` (line 16)
- `BaselineRepository.list_baselines` (line 17)
- `SQLiteBaselineRepository.save_baseline.<locals>._insert` (line 48)
- `SQLiteBaselineRepository.get_baseline.<locals>._query` (line 70)
- `SQLiteBaselineRepository.list_baselines.<locals>._query` (line 82)
