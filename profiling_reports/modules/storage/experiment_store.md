# Profile: `src/nirizan/storage/experiment_store.py`

- Functions executed: **15**
- Total internal time: **0.000248 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `SQLiteExperimentStore.__init__` | 35 | 5 | 0.000019 | 0.000004 | 0.014557 | 0.002911 | built-ins (C) 0.000453s |
| `SQLiteExperimentStore._init_db` | 41 | 5 | 0.000019 | 0.000004 | 0.014085 | 0.002817 | built-ins (C) 0.014066s |
| `<module> (import time)` | 1 | 1 | 0.000018 | 0.000018 | 0.001175 | 0.001175 | built-ins (C) 0.001153s, frozen/internal 0.000003s |
| `SQLiteExperimentStore.record_run` | 59 | 12 | 0.000041 | 0.000003 | 0.001096 | 0.000091 | stdlib:asyncio 0.000812s, stdlib:json 0.000107s |
| `SQLiteExperimentStore.get_run` | 83 | 12 | 0.000061 | 0.000005 | 0.000773 | 0.000064 | stdlib:asyncio 0.000493s, stdlib:uuid 0.000061s, stdlib:json 0.000057s |
| `SQLiteExperimentStore.diff` | 109 | 6 | 0.000023 | 0.000004 | 0.000478 | 0.000080 | pydantic 0.000005s, stdlib:uuid 0.000005s |
| `SQLiteExperimentStore.close` | 122 | 5 | 0.000008 | 0.000002 | 0.000175 | 0.000035 | built-ins (C) 0.000167s |
| `<listcomp>` | 60 | 6 | 0.000025 | 0.000004 | 0.000137 | 0.000023 | pydantic 0.000111s |
| `<listcomp>` | 96 | 4 | 0.000021 | 0.000005 | 0.000079 | 0.000020 | pydantic 0.000059s |
| `RunDiff` | 16 | 1 | 0.000007 | 0.000007 | 0.000013 | 0.000013 | pydantic 0.000006s |
| `<dictcomp>` | 115 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `SQLiteExperimentStore` | 32 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `ExperimentStore` | 26 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `<dictcomp>` | 119 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `<dictcomp>` | 116 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

## Functions never executed by the tests

- `ExperimentStore.record_run` (line 27)
- `ExperimentStore.get_run` (line 28)
- `ExperimentStore.diff` (line 29)
- `SQLiteExperimentStore.record_run.<locals>._insert` (line 62)
- `SQLiteExperimentStore.get_run.<locals>._query` (line 86)
