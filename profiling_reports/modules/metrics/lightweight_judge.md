# Profile: `src/nirizan/metrics/lightweight_judge.py`

- Functions executed: **7**
- Total internal time: **0.000102 s**

## Executed functions (sorted by cumulative time)

| Function | Line | ncalls | tottime (s) | tottime/call | cumtime (s) | cumtime/call | Top external callees (cumtime) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `<module> (import time)` | 1 | 1 | 0.000022 | 0.000022 | 0.001457 | 0.001457 | built-ins (C) 0.001397s, frozen/internal 0.000004s |
| `LightweightJudge.evaluate_text` | 43 | 3 | 0.000052 | 0.000017 | 0.001029 | 0.000343 | stdlib:logging 0.000550s, pydantic 0.000017s, built-ins (C) 0.000009s |
| `RegexClassifier.predict_proba` | 26 | 2 | 0.000007 | 0.000004 | 0.000402 | 0.000201 | built-ins (C) 0.000395s |
| `<genexpr>` | 29 | 4 | 0.000009 | 0.000002 | 0.000390 | 0.000097 | stdlib:re 0.000381s |
| `LightweightJudge` | 34 | 1 | 0.000010 | 0.000010 | 0.000048 | 0.000048 | pydantic 0.000038s |
| `ClassificationModel` | 17 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |
| `RegexClassifier` | 23 | 1 | 0.000001 | 0.000001 | 0.000001 | 0.000001 | - |

## Functions never executed by the tests

- `ClassificationModel.predict_proba` (line 20)
