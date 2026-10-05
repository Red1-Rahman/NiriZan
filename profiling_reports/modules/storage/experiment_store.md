# Profile: `src/nirizan/storage/experiment_store.py`

- Functions executed: **15**
- Total internal time: **0.000212 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `SQLiteExperimentStore.__init__` | 35 | 5 | 0.000022 | 0.000004 | 0.014887 | 0.002977 | built-ins (C) 0.000382s |
| `SQLiteExperimentStore._init_db` | 41 | 5 | 0.000020 | 0.000004 | 0.014483 | 0.002897 | built-ins (C) 0.014463s |
| `SQLiteExperimentStore.record_run` | 59 | 12 | 0.000035 | 0.000003 | 0.000922 | 0.000077 | stdlib:asyncio 0.000639s, stdlib:json 0.000114s |
| `<module> (import time)` | 1 | 1 | 0.000016 | 0.000016 | 0.000813 | 0.000813 | built-ins (C) 0.000795s, frozen/internal 0.000002s |
| `SQLiteExperimentStore.get_run` | 83 | 12 | 0.000042 | 0.000004 | 0.000535 | 0.000045 | stdlib:asyncio 0.000302s, stdlib:json 0.000055s, stdlib:uuid 0.000042s |
| `SQLiteExperimentStore.diff` | 109 | 6 | 0.000018 | 0.000003 | 0.000266 | 0.000044 | pydantic 0.000004s, stdlib:uuid 0.000002s |
| `SQLiteExperimentStore.close` | 122 | 5 | 0.000010 | 0.000002 | 0.000194 | 0.000039 | built-ins (C) 0.000183s |
| `<listcomp>` | 60 | 6 | 0.000022 | 0.000004 | 0.000134 | 0.000022 | pydantic 0.000111s |
| `<listcomp>` | 96 | 4 | 0.000017 | 0.000004 | 0.000074 | 0.000018 | pydantic 0.000056s |
| `RunDiff` | 16 | 1 | 0.000005 | 0.000005 | 0.000009 | 0.000009 | pydantic 0.000004s |
| `SQLiteExperimentStore` | 32 | 1 | 0.000002 | 0.000002 | 0.000002 | 0.000002 | - |
| `<dictcomp>` | 115 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `<dictcomp>` | 119 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `ExperimentStore` | 26 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `<dictcomp>` | 116 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

## Functions never executed by the tests

- `ExperimentStore.record_run` (line 27)
- `ExperimentStore.get_run` (line 28)
- `ExperimentStore.diff` (line 29)
- `SQLiteExperimentStore.record_run.<locals>._insert` (line 62)
- `SQLiteExperimentStore.get_run.<locals>._query` (line 86)
