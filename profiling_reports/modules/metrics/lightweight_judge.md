# Profile: `src/nirizan/metrics/lightweight_judge.py`

- Functions executed: **7**
- Total internal time: **0.000069 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000025 | 0.000025 | 0.001253 | 0.001253 | built-ins (C) 0.001189s, frozen/internal 0.000003s |
| `LightweightJudge.evaluate_text` | 43 | 3 | 0.000019 | 0.000006 | 0.000601 | 0.000200 | stdlib:logging 0.000313s, pydantic 0.000007s, built-ins (C) 0.000005s |
| `RegexClassifier.predict_proba` | 26 | 2 | 0.000005 | 0.000003 | 0.000256 | 0.000128 | built-ins (C) 0.000251s |
| `<genexpr>` | 29 | 4 | 0.000006 | 0.000001 | 0.000247 | 0.000062 | stdlib:re 0.000241s |
| `LightweightJudge` | 34 | 1 | 0.000012 | 0.000012 | 0.000074 | 0.000074 | pydantic 0.000062s |
| `ClassificationModel` | 17 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `RegexClassifier` | 23 | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | - |

## Functions never executed by the tests

- `ClassificationModel.predict_proba` (line 20)
