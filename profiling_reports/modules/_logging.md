# Profile: `src/nirizan/_logging.py`

- Functions executed: **4**
- Total internal time: **0.000052 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `get_logger` | 23 | 14 | 0.000028 | 0.000002 | 0.000374 | 0.000027 | stdlib:logging 0.000346s |
| `<module> (import time)` | 1 | 1 | 0.000023 | 0.000023 | 0.000142 | 0.000142 | stdlib:typing 0.000051s, built-ins (C) 0.000036s, stdlib:logging 0.000032s |
| `NiriZanFormatter` | 31 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `_NiriZanStreamHandler` | 15 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |

## Functions never executed by the tests

- `NiriZanFormatter.format` (line 37)
- `_parse_level` (line 57)
- `enable_logging` (line 72)
- `set_log_level` (line 101)
- `disable_logging` (line 108)
