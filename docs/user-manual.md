# NiriZan User Manual

*Continuous evaluation infrastructure for production AI systems.*
> version: `0.1.0`

---

## Table of Contents

- [Getting Started](#getting-started)
  - [Installation](#installation)
  - [Requirements](#requirements)
  - [Checking your version](#checking-your-version)
- [Guides](#guides)
  - [Logging](#logging)
  - [Instrumentation Concepts](#instrumentation-concepts)
  - [Tracing with the Tracer](#tracing-with-the-tracer)
  - [Decorator-Based Instrumentation](#decorator-based-instrumentation)
  - [Sessions](#sessions)
  - [Exporters](#exporters)
  - [Metrics Concepts](#metrics-concepts)
  - [Built-in Metrics: RAG Triad](#built-in-metrics-rag-triad)
  - [Built-in Metrics: Behavioral Anchor](#built-in-metrics-behavioral-anchor)
  - [Judges: Lightweight and LLM-Based](#judges-lightweight-and-llm-based)
  - [Statistical Gating](#statistical-gating)
  - [Writing a Custom Metric](#writing-a-custom-metric)
  - [Orchestration Concepts](#orchestration-concepts)
  - [Collecting and Persisting Traces](#collecting-and-persisting-traces)
  - [Dispatching Traces to Metrics](#dispatching-traces-to-metrics)
  - [Scheduling Evaluation Runs](#scheduling-evaluation-runs)
  - [Regression Concepts](#regression-concepts)
  - [Comparing a Baseline](#comparing-a-baseline)
  - [Comparing Many Metrics at Once](#comparing-many-metrics-at-once)
  - [Gate Concepts](#gate-concepts)
  - [Evaluating a Gate](#evaluating-a-gate)
  - [CI Integration](#ci-integration)
  - [Reporting Concepts](#reporting-concepts)
  - [System Health Score](#system-health-score)
  - [Judge Reliability](#judge-reliability)
  - [Assembling a Dashboard Snapshot](#assembling-a-dashboard-snapshot)
  - [Trust Concepts](#trust-concepts)
  - [Anchor Sets](#anchor-sets)
  - [Judge-Drift Attribution](#judge-drift-attribution)
  - [Storage Concepts](#storage-concepts)
  - [Storage Models](#storage-models)
  - [Trace Storage](#trace-storage)
  - [Run and Baseline Storage](#run-and-baseline-storage)
  - [Session Storage](#session-storage)
  - [Comparing Runs](#comparing-runs)
- [API Reference](#api-reference)
  - [nirizan](#nirizan-package)
  - [Logging API](#logging-api)
  - [Pydantic Model Conventions](#pydantic-model-conventions)
  - [nirizan.instrumentation.spans](#nirizaninstrumentationspans)
  - [nirizan.instrumentation.sessions](#nirizaninstrumentationsessions)
  - [nirizan.instrumentation.tracer](#nirizaninstrumentationtracer)
  - [nirizan.instrumentation.exporters](#nirizaninstrumentationexporters)
  - [nirizan.instrumentation.sdk](#nirizaninstrumentationsdk)
  - [nirizan.metrics.base](#nirizanmetricsbase)
  - [nirizan.metrics.rag_triad](#nirizanmetricsrag_triad)
  - [nirizan.metrics.behavioral_anchor](#nirizanmetricsbehavioral_anchor)
  - [nirizan.metrics.lightweight_judge](#nirizanmetricslightweight_judge)
  - [nirizan.metrics.llm_judge](#nirizanmetricsllm_judge)
  - [nirizan.metrics.statistical_gating](#nirizanmetricsstatistical_gating)
  - [nirizan.orchestrator.collector](#nirizanorchestratorcollector)
  - [nirizan.orchestrator.dispatcher](#nirizanorchestratordispatcher)
  - [nirizan.orchestrator.scheduler](#nirizanorchestratorscheduler)
  - [nirizan.regression](#nirizanregression-package)
  - [nirizan.regression.comparator](#nirizanregressioncomparator)
  - [nirizan.regression.thresholds](#nirizanregressionthresholds)
  - [nirizan.gate](#nirizangate-package)
  - [nirizan.gate.verdict](#nirizangateverdict)
  - [nirizan.gate.ci](#nirizangateci)
  - [nirizan.reporting.health_score](#nirizanreportinghealth_score)
  - [nirizan.reporting.judge_reliability](#nirizanreportingjudge_reliability)
  - [nirizan.reporting.dashboard](#nirizanreportingdashboard)
  - [nirizan.trust.anchor_set](#nirizantrustanchor_set)
  - [nirizan.trust.attribution](#nirizantrustattribution)
  - [nirizan.storage.models](#nirizanstoragemodels)
  - [nirizan.storage.trace_repository](#nirizanstoragetrace_repository)
  - [nirizan.storage.run_repository](#nirizanstoragerun_repository)
  - [nirizan.storage.baselines](#nirizanstoragebaselines)
  - [nirizan.storage.session_repository](#nirizanstoragesession_repository)
  - [nirizan.storage.experiment_store](#nirizanstorageexperiment_store)

---

## Getting Started

### Installation

Install NiriZan from PyPI:

```bash
pip install nirizan
```

This installs the `nirizan` package and makes its top-level API available:

```python
import nirizan
```

### Requirements
- **Python 3.11 or later.**
- **Core dependencies** (installed automatically):
  1. `pydantic` (2.7 or later, before 3.0)
  2. `numpy` (1.26.0 or later)
  3. `scipy` (1.10.0 or later)

> NiriZan has no other required dependencies; the SQLite-backed storage implementations covered in [Storage](#storage-concepts) use Python's built-in `sqlite3` module, and instrumentation's async context managers use only the standard library's `asyncio` and `contextvars`.

### Checking your version

The installed version is available as a plain string attribute on the package:

```python
import nirizan

print(nirizan.__version__)
# "0.1.0"
```

There is currently no separate version-checking function; read `nirizan.__version__` directly, or use `importlib.metadata.version("nirizan")` from the standard library.

---

## Guides

### Logging

NiriZan ships with a small, library-safe logging setup built on the standard `logging` module. By default, NiriZan stays silent: a `NullHandler` is attached to its root logger (`"nirizan"`) at import time, so nothing is printed unless the host application explicitly turns logging on.

This matters for two situations:

- **You're building an application on top of NiriZan** and want to see NiriZan's own log output (for example, while debugging tracing, exporting, or evaluation runs). Call `enable_logging()`.
- **You're writing a module inside NiriZan** (or extending it) and want a logger that follows this convention. Call `get_logger(__name__)`.

Turning logging on:

```python
import nirizan

nirizan.enable_logging()
```

This attaches a handler that writes formatted log lines to `sys.stderr` by default, at the `INFO` level by default. A typical line looks like:

```text
[INFO] 2026-08-07 14:40:23.279 [NiriZan] tracer.py:182 Started trace 4baf5d17
```

You can control the level either by passing it explicitly or through an environment variable:

```python
import nirizan

nirizan.enable_logging(level="DEBUG")
```

```bash
export NIRIZAN_LOG_LEVEL=DEBUG
```

If you call `enable_logging()` with no arguments and no environment variable is set, the level defaults to `INFO`.

Calling `enable_logging()` again is safe. It replaces only the handler NiriZan previously attached; it does not remove or duplicate handlers your own application has attached to the same logger hierarchy.

To silence NiriZan again later:

```python
nirizan.disable_logging()
```

To change the level without touching handlers (for example, to temporarily raise verbosity mid-run):

```python
nirizan.set_log_level("DEBUG")
# ... noisy section ...
nirizan.set_log_level("INFO")
```

If you're writing code that lives inside NiriZan itself, or an extension that wants to log through the same hierarchy, get a logger scoped under `"nirizan"`:

```python
from nirizan import get_logger

logger = get_logger(__name__)
logger.info("Trace exported")
```

Loggers obtained this way are ordinary `logging.Logger` instances; NiriZan does not wrap or restrict them. All standard `logging` methods (`debug`, `info`, `warning`, `error`, `exception`, and so on) work as expected.

### Instrumentation Concepts

NiriZan's instrumentation layer captures what actually happened inside a RAG pipeline, agent, or LLM call, at the level of individual execution steps. Four concepts make up this layer:

```
Session   →  a multi-turn conversation grouping several traces
  Trace   →  one full invocation of your application
    Span  →  one step inside that invocation (planning, retrieval, tool use, generation)
```

- **Span** is the atomic unit: a single step, tagged with a `SpanKind` (`planning`, `retrieval`, `tool_use`, or `generation`), a name, a start and end time, arbitrary attributes, and optional input/output payloads. Spans can have a parent span, which is how NiriZan represents nested steps within one invocation.
- **Trace** is the ordered collection of spans produced by one invocation of your instrumented application. All spans in a trace share the same `trace_id`.
- **Session** groups multiple trace ids that belong to one multi-turn conversation or interaction.

Everything in this layer is currently accessed through submodule imports; `nirizan.instrumentation` itself does not re-export these names at the package level. Import from the specific submodule, for example:

```python
from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.instrumentation.tracer import Tracer
```

### Tracing with the Tracer

`Tracer` is the core object that manages span lifecycles and assembles them into a `Trace`.

```python
from nirizan.instrumentation.tracer import Tracer
from nirizan.instrumentation.spans import SpanKind

tracer = Tracer(application_name="my-rag-app")

async def answer_question(question: str) -> str:
    async with tracer.start_span("retrieve_context", kind=SpanKind.RETRIEVAL) as span:
        context = await retrieve(question)
        span.output_payload = context

    async with tracer.start_span("generate_answer", kind=SpanKind.GENERATION) as span:
        answer = await generate(question, context)
        span.output_payload = answer

    return answer
```

A few behaviors worth understanding:

- **`start_span` is an async context manager.** It yields a `SpanHandle`, a small mutable object with a `span_id` and a settable `output_payload`. Set `span.output_payload` inside the block if you want the span to record the step's output; NiriZan does not infer it for you when you call `start_span` directly (contrast this with the decorators in [Decorator-Based Instrumentation](#decorator-based-instrumentation), which do infer it).
- **The first `start_span` call opens a trace; nested calls join it.** If no trace is currently active, opening a span starts a new trace (a fresh `trace_id`) and marks that span as the root. If a span is opened while another span is already active (for example, calling `start_span` again inside an existing `async with tracer.start_span(...)` block), it becomes a **child span**: `parent_span_id` is set automatically, and it joins the same trace. Trace and span context are tracked with `contextvars`, so this is safe across concurrent `asyncio` tasks.
- **The trace is assembled and exported when the root span closes**, not before. Only the outermost `start_span` block triggers `tracer.exporter.export(trace)`, if an exporter was configured on the `Tracer`.
- **Spans are recorded even if the wrapped code raises.** The span-closing logic runs in a `finally` block, so a span (and, if it was the root span, the assembled trace) is still recorded and exported even when an exception propagates out of the `async with` block. The exception itself is not suppressed; it continues to propagate after the span is recorded.
- **Non-primitive attribute values are stringified.** `attributes` passed to `start_span` are filtered to `str`, `int`, `float`, and `bool` as-is; any other type is converted with `str(...)` before being stored on the resulting `Span`.

You can assemble the current trace manually at any point with `tracer.get_assembled_trace()`, and clear the tracer's local span buffer with `tracer.clear()`. `clear()` only empties the in-memory buffer on the `Tracer` instance; it has no effect on anything already sent to an exporter.

### Decorator-Based Instrumentation

For the common case of wrapping an entire async function as one span, `nirizan.instrumentation.sdk` provides decorators that call `start_span` for you.

```python
from nirizan.instrumentation.sdk import init_tracer, retrieval, generation

init_tracer(application_name="my-rag-app")

@retrieval()
async def retrieve(question: str) -> str:
    ...
    return context

@generation()
async def generate(question: str, context: str) -> str:
    ...
    return answer
```

This SDK layer is built around one **global tracer**, set up once with `init_tracer(...)`. The decorators (`planning`, `retrieval`, `generation`, `tool_use`, and the more general `trace_span`) look up this global tracer automatically unless you pass a specific `Tracer` instance explicitly.

Behavior specific to the decorators:

- **They only work on `async def` functions.** Each decorator wraps a coroutine function and returns a coroutine function; it is not meant for synchronous functions.
- **The input payload is inferred, not the full call.** The span's `input_payload` is set to `str(...)` of the first positional argument if any were given, otherwise `str(...)` of the first keyword argument's value if any were given, otherwise `None`. It is not a serialization of the full argument list.
- **The output payload is inferred from the return value.** If the wrapped function returns a non-`None` value and nothing already set `handle.output_payload` inside the function body, the span's `output_payload` is set to `str(result)` automatically.
- **They raise if no tracer is available.** Calling a decorated function before `init_tracer()` has been called (and without passing an explicit `tracer=` argument to the decorator) raises `RuntimeError`.

`trace_span(kind, name=None, tracer=None)` is the general form; `planning()`, `retrieval()`, `generation()`, and `tool_use()` are convenience wrappers that call it with a fixed `SpanKind`.

If you're not using the global tracer, pass your `Tracer` explicitly:

```python
from nirizan.instrumentation.sdk import trace_span
from nirizan.instrumentation.spans import SpanKind

@trace_span(kind=SpanKind.TOOL_USE, tracer=my_tracer)
async def call_search_api(query: str) -> str:
    ...
```

### Sessions

A session groups the traces produced during one multi-turn interaction (for example, one chat conversation spanning several requests).

Scope traced calls to a session with `Tracer.session(...)`:

```python
async with tracer.session() as session_id:
    async with tracer.start_span("generate_answer", kind=SpanKind.GENERATION) as span:
        ...
```

Any trace assembled by `tracer.get_assembled_trace()` while a `session(...)` block is active picks up that `session_id` automatically. The SDK layer exposes the same behavior through `start_session(...)`, which delegates to the global tracer's `session(...)` and raises `RuntimeError` if no tracer has been initialized yet:

```python
from nirizan.instrumentation.sdk import start_session

async with start_session() as session_id:
    ...
```

The `Session` model (`nirizan.instrumentation.sessions.Session`) describes the shape of a session as a standalone record: an id, the owning application's name, the list of trace ids that belong to it, and start/end timestamps. `Tracer.session(...)` only propagates a `session_id` through context so that assembled traces are tagged with it; it does not itself construct, populate, or persist a `Session` object. Building and storing `Session` records is handled by the storage layer.

### Exporters

An exporter is where a completed `Trace` goes once its root span closes. `Tracer` calls `exporter.export(trace)` for you; you do not call it directly in normal use.

```python
from nirizan.instrumentation.tracer import Tracer
from nirizan.instrumentation.exporters import InMemoryExporter

exporter = InMemoryExporter()
tracer = Tracer(application_name="my-rag-app", exporter=exporter)

# ... run instrumented code ...

for trace in exporter.get_traces():
    print(trace.trace_id, len(trace.spans))
```

Two exporters ship with NiriZan:

- **`InMemoryExporter`** buffers exported traces in a local list. Intended for unit tests and local experiments; call `get_traces()` to read them back and `clear()` to empty the buffer.
- **`ConsoleExporter`** writes a one-line summary of each trace (trace id, application name, span count) through the standard `logging` module, at `INFO` level, under the `nirizan.instrumentation.exporters` logger name. Because this logger is a child of the `nirizan` root logger, calling `nirizan.enable_logging()` (see [Logging](#logging)) is enough to see this output; you do not need to configure it separately.

Both exporters are `async`, since exporting is expected to be I/O in general even though these two built-in implementations don't perform any.

**Writing a custom exporter.** Subclass `BaseExporter` and implement `export`:

```python
from nirizan.instrumentation.exporters import BaseExporter
from nirizan.instrumentation.spans import Trace

class MyExporter(BaseExporter):
    async def export(self, trace: Trace) -> None:
        ...  # send trace somewhere

    async def shutdown(self) -> None:
        ...  # optional: release connections or background workers
```

`export` is required and must be `async`. `shutdown` is optional to override; the base implementation is a no-op. NiriZan does not guarantee delivery, retries, or background execution on your behalf; a custom exporter is responsible for its own error handling, retry policy, and any batching it wants to do.

### Metrics Concepts

Once you have a `Trace`, NiriZan can score it. A **metric** takes a `Trace` and produces zero or more `MetricResult` objects, each one a single normalized score.

As with instrumentation, `nirizan.metrics` re-exports nothing at the package level; import from the specific submodule:

```python
from nirizan.metrics.base import Metric, MetricResult, Scorer
```

**`MetricResult`** is the shared output shape every metric produces: which metric produced it, which trace it scores, a score in `[0.0, 1.0]`, an optional confidence, a free-form `details` dict, and when it was computed. See the [full field reference](#metricresult).

**`Metric`** is a `typing.Protocol`, not a base class: any object with a `name: str` attribute and an `async def evaluate(self, trace: Trace) -> list[MetricResult]` method satisfies it, without needing to inherit from anything. `RAGTriadMetric` and `BehavioralAnchorMetric` (below) both satisfy this protocol. A `Metric` implementation must not mutate the `Trace` it's given, and is not responsible for persisting its own results.

**`Scorer`** is a second, smaller protocol: any callable of the form `(text_a: str, text_b: str) -> float` satisfies it. It's how `RAGTriadMetric` stays agnostic to which underlying text-similarity technique (embeddings, a cross-encoder, an LLM call, or something simpler) actually produces its scores.

Not every scoring class in `nirizan.metrics` implements the `Metric` protocol. `LightweightJudge` and `LLMJudge` (covered in [Judges](#judges-lightweight-and-llm-based)) score a single piece of text directly rather than a `Trace`, and their evaluation methods are synchronous. Use `RAGTriadMetric` or `BehavioralAnchorMetric` where you want something you can hand to a `Trace`-based evaluation pipeline; use the judges where you want to score arbitrary text (for example, text you've already pulled out of a trace, or text from outside NiriZan's tracing entirely).

### Built-in Metrics: RAG Triad

`RAGTriadMetric` computes the reference-free RAG Triad described in NiriZan's architecture: context relevance, groundedness, and answer relevance, each as its own `MetricResult`.

```python
from nirizan.metrics.rag_triad import RAGTriadMetric

def my_scorer(text_a: str, text_b: str) -> float:
    ...  # e.g. embedding cosine similarity, clipped to [0.0, 1.0]
    return score

rag_triad = RAGTriadMetric(scorer=my_scorer)
results = await rag_triad.evaluate(trace)
for result in results:
    print(result.metric_name, result.score)
```

**Where the three sub-metrics come from:** `RAGTriadMetric` reads three pieces of text out of the trace: the query, from the `input_payload` of the trace's first `PLANNING` span; the context, from the `output_payload` of its first `RETRIEVAL` span; and the answer, from the `output_payload` of its first `GENERATION` span. If a trace has more than one span of the same kind, only the first one (in the trace's span order) is used.

| Sub-metric (`MetricResult.metric_name`) | Compares | Requires |
|---|---|---|
| `context_relevance` | query vs. context | a `PLANNING` span and a `RETRIEVAL` span |
| `groundedness` | context vs. answer | a `RETRIEVAL` span and a `GENERATION` span |
| `answer_relevance` | query vs. answer | a `PLANNING` span and a `GENERATION` span |

Each is only computed, and only appears in the returned list, if both of its required texts are present. A trace missing a `PLANNING` span, for instance, still gets a `groundedness` result as long as it has `RETRIEVAL` and `GENERATION` spans; it just won't get `context_relevance` or `answer_relevance`. `evaluate` can therefore return anywhere from zero to three results. When any of the three fields is missing, every result it does return carries a `details["missing_fields"]` entry listing which fields were absent, as a comma-separated string.

**Score meaning:** each score is exactly whatever `my_scorer(text_a, text_b)` returns for that pair; `RAGTriadMetric` does not transform or clip it further. It's your `Scorer` implementation's responsibility to return a value in `[0.0, 1.0]`, since `MetricResult.score` requires that range.

**`confidence`** is not set by `RAGTriadMetric`; it's left at its default of `None` on every result.

**Note:** despite the class's own `name` attribute being `"rag_triad"` (used to identify the metric as a whole, e.g. in a dispatcher), the individual `MetricResult` objects it returns are tagged `context_relevance`, `groundedness`, and `answer_relevance`, not `rag_triad`.

### Built-in Metrics: Behavioral Anchor

`BehavioralAnchorMetric` scores each `GENERATION` span in a trace by embedding-similarity against a fixed target embedding, useful for detecting when a long-running agent's responses drift away from an intended persona or set of constraints.

```python
import numpy as np
from nirizan.metrics.behavioral_anchor import BehavioralAnchorMetric

anchor = BehavioralAnchorMetric(
    target_embedding=np.array([...]),   # your reference embedding
    threshold=0.85,
    embedding_fn=my_embedding_fn,       # text: str -> np.ndarray
)
results = await anchor.evaluate(trace)
```

**You must supply a real `embedding_fn`.** If `embedding_fn` is omitted, `BehavioralAnchorMetric` falls back to a placeholder that ignores its input text entirely and always returns an array of ones the same shape as `target_embedding`. With that default in place, every `GENERATION` span in every trace receives the same score, regardless of what the span actually said, because the "embedding" never varies with the text. Pass a real text-embedding function for the metric to be meaningful.

**Score:** for each `GENERATION` span, the cosine similarity between `embedding_fn(span.output_payload)` and `target_embedding`, floored at `0.0` and capped at `1.0` (a raw cosine similarity can be negative; negative values are reported as `0.0` here, so the score is not a literal cosine similarity when the true similarity is negative). If either vector has zero norm, the score is `0.0`.

**`confidence`** is always `1.0` on every result this metric produces.

**`details`** on each result includes:

| Key | Meaning |
|---|---|
| `band` | `"aligned"` if score ≥ `threshold`, `"neutral"` if `0.50` ≤ score < `threshold`, otherwise `"deviation"`. |
| `threshold` | The threshold value the metric was constructed with. |
| `span_id` | The id of the `GENERATION` span this result scores, as a string. |

**Applicable trace types:** any trace with at least one `GENERATION` span. A trace with none returns an empty list (no error).

### Judges: Lightweight and LLM-Based

`LightweightJudge` and `LLMJudge` score a piece of text directly. Neither implements the `Metric` protocol: both are `evaluate`-style methods that take text (or, for `LLMJudge`, keyword arguments) and return a single `MetricResult`, synchronously, rather than an async, `Trace`-taking `evaluate(trace) -> list[MetricResult]`. Keep this distinction in mind if you're wiring either into code that expects `Metric`-shaped objects.

#### `LightweightJudge`

Fast, local, high-throughput scoring, intended for the volume that makes an LLM-as-judge call too expensive to run on every trace.

```python
from nirizan.metrics.lightweight_judge import LightweightJudge

judge = LightweightJudge()  # uses the built-in RegexClassifier by default
result = judge.evaluate_text("This response was completely safe and helpful.")
print(result.score)
```

By default, `LightweightJudge` uses `RegexClassifier`, a small rule-based classifier meant for testing and offline scenarios rather than production-quality classification: it checks a fixed, small list of literal patterns (`hate`, `kill`, `toxic`, `bad`, as whole words) against the lowercased text and derives a `toxic`/`safe` split from how many of them matched. For real classification, pass your own `classifier` (anything with a `predict_proba(text: str) -> dict[str, float]` method) when constructing `LightweightJudge`.

`evaluate_text` returns a `MetricResult` whose `score` is the classifier's predicted probability for `target_class` (`"safe"` by default). Empty or whitespace-only input always scores `0.0` without calling the classifier. `confidence` and `details` are left at their defaults (`None` and `{}`) on the returned result.

#### `LLMJudge`

Prompted-LLM scoring: you supply a prompt template and a completion function; `LLMJudge` builds the prompt, calls your function, and parses the result.

```python
from nirizan.metrics.llm_judge import LLMJudge

def call_my_llm(prompt: str) -> str:
    # call your LLM provider here; must return a JSON string like
    # {"score": 0.9, "reasoning": "..."}
    ...

judge = LLMJudge(
    metric_name="helpfulness",
    prompt_template=(
        'Rate the helpfulness of this answer from 0 to 1.\n'
        'Question: {input}\nContext: {context}\nAnswer: {output}\n'
        'Respond as JSON: {{"score": <float>, "reasoning": "<why>"}}'
    ),
    completion_fn=call_my_llm,
)

result = judge.evaluate(
    input_text="What is NiriZan?",
    output_text="NiriZan is a continuous evaluation framework.",
    context="NiriZan docs...",
)
```

**The prompt template** is filled with `str.format(...)`, so it must use `{input}`, `{output}`, and `{context}` as its placeholders (`context` is substituted with an empty string if you don't pass one to `evaluate`).

**`completion_fn`** is called synchronously, once per `evaluate()` call, with the built prompt, and must return a string. `LLMJudge.evaluate` itself does not perform any I/O directly; all of the actual model call happens inside whatever `completion_fn` you provide. If that function performs network I/O, the call blocks the calling thread for its duration, since `evaluate` is not `async`.

**Expected completion format:** `LLMJudge` expects `completion_fn`'s return value to be a JSON string containing at least a numeric `"score"` field, and optionally a `"reasoning"` string field. `LLMJudgeResponse` (`nirizan.metrics.llm_judge.LLMJudgeResponse`) documents this expected shape as a model, but note that `LLMJudge.evaluate` does not currently validate the parsed JSON against it directly; it extracts `score` and `reasoning` from the parsed dict by hand.

**Failure handling:** if `completion_fn`'s output isn't valid JSON, or is missing a usable `"score"` key, `LLMJudge.evaluate` does not raise. It logs a warning and returns a `MetricResult` with `score=0.0` and a `details["reasoning"]` explaining that parsing failed, including a truncated copy of the raw completion. Design any code that consumes `LLMJudge` results with this soft-failure behavior in mind, since a `0.0` score can mean either "genuinely rated 0" or "the judge's output couldn't be parsed" — check `details["reasoning"]` to tell them apart.

`confidence` is not set by `LLMJudge`; it's left at its default of `None`.

### Statistical Gating

`nirizan.metrics.statistical_gating` is a set of standalone functions (not classes) for turning two distributions of scores, a candidate and a baseline, into a statistically grounded regression signal, following the Mann-Whitney U and Holm-Bonferroni approach described in NiriZan's architecture.

```python
import numpy as np
from nirizan.metrics.statistical_gating import (
    mann_whitney_regression,
    bootstrap_delta_ci,
    holm_bonferroni,
)

candidate_scores = np.array([0.71, 0.68, 0.74, 0.70, 0.66, 0.69])
baseline_scores = np.array([0.82, 0.85, 0.80, 0.83, 0.81, 0.79])

statistic, p_value = mann_whitney_regression(candidate_scores, baseline_scores)
ci_low, ci_high = bootstrap_delta_ci(candidate_scores, baseline_scores)

decisions = holm_bonferroni({"context_relevance": p_value, "groundedness": 0.03})
```

A typical flow: run `mann_whitney_regression` per metric to get a p-value per metric, correct the whole set of p-values at once with `holm_bonferroni` (so testing many metrics at once doesn't inflate your false-positive rate), and use `bootstrap_delta_ci` alongside either to report the actual size and uncertainty of the change, not just whether it was "significant."

See the [full API reference](#nirizanmetricsstatistical_gating) for exact signatures, validation rules, and what each return value means; the reference below documents `validate_scores`, `mann_whitney_regression`, `bootstrap_delta_ci`, `holm_bonferroni`, `approximate_sample_size`, and `calibrate_gold_set` individually, since each has its own required shape, defaults, and failure conditions.

### Writing a Custom Metric

Because `Metric` is a `typing.Protocol` rather than a base class, a custom metric doesn't need to inherit from anything. It needs a `name` attribute and an `async def evaluate(self, trace: Trace) -> list[MetricResult]` method:

```python
from datetime import datetime, timezone

from nirizan.instrumentation.spans import SpanKind, Trace
from nirizan.metrics.base import MetricResult

class ResponseLengthMetric:
    name = "response_length"

    async def evaluate(self, trace: Trace) -> list[MetricResult]:
        results = []
        for span in trace.spans_of_kind(SpanKind.GENERATION):
            length = len(span.output_payload or "")
            score = min(1.0, length / 500)  # normalize to [0.0, 1.0] yourself
            results.append(
                MetricResult(
                    metric_name=self.name,
                    trace_id=trace.trace_id,
                    score=score,
                    computed_at=datetime.now(timezone.utc),
                )
            )
        return results
```

Requirements for a `Metric` implementation are:

- `evaluate` must be `async def`, even if the implementation does no actual I/O.
- Every `MetricResult.score` must be normalized to `[0.0, 1.0]`; the model itself enforces this and raises a Pydantic `ValidationError` if you construct one outside that range.
- `evaluate` must not mutate the `Trace` it receives.
- `evaluate` is not responsible for persisting its own results; metric evaluation does not automatically persist the output.

If your metric needs pairwise text comparison the way `RAGTriadMetric` does, consider accepting a `Scorer`-shaped callable (`(text_a: str, text_b: str) -> float`) as a constructor argument instead of hardcoding one, so callers can swap the underlying comparison technique.

### Orchestration Concepts

The orchestrator layer is the control plane that connects the evaluation components: it receives traces in the background, decides which metrics apply to which traces, and turns the results into `Run` records. Three pieces make it up:

```
Trace  →  TraceCollector  →  (persisted trace)
Trace  →  MetricDispatcher →  list[MetricResult]
        →  RunScheduler    →  list[Run]
```

- **`TraceCollector`** receives traces asynchronously (typically via the `Tracer`'s exporter mechanism from [Exporters](#exporters)), tags each one with versioning metadata, and persists them through a repository you provide.
- **`MetricDispatcher`** holds a registry of which `Metric` instances apply to which system type, and routes a `Trace` to the right ones.
- **`RunScheduler`** ties the previous two together on demand: it pulls stored traces for an application, dispatches each through a `MetricDispatcher`, and saves the resulting `Run` records.

As with the layers before it, `nirizan.orchestrator` re-exports nothing at the package level; import from the specific submodule (`nirizan.orchestrator.collector`, `.dispatcher`, `.scheduler`).

**Note on `Run`:** `RunScheduler` constructs and persists `nirizan.storage.models.Run` objects. `Run` is now fully documented in [`nirizan.storage.models`](#nirizanstoragemodels); its complete field list is exactly the fields `RunScheduler` sets here (`run_id`, `trace_id`, `code_commit`, `data_snapshot_id`, `metric_results`, `created_at`), plus length-validation constraints on `code_commit` and `data_snapshot_id`.

### Collecting and Persisting Traces

`TraceCollector` decouples emitting a trace from persisting it: traces are pushed onto an in-memory queue and written out by a background worker task, rather than persisted synchronously at export time.

```python
from nirizan.orchestrator.collector import TraceCollector, CollectorExporter
from nirizan.instrumentation.tracer import Tracer

# `my_repository` must satisfy TraceSink: an async save(trace) -> None method.
collector = TraceCollector(repository=my_repository)
await collector.start()

tracer = Tracer(application_name="my-rag-app", exporter=CollectorExporter(collector))

# ... run instrumented code; traces flow into the collector automatically ...

await collector.stop()
```

**Versioning metadata.** `TraceCollector` resolves two values once, when it's constructed, not per-trace:

- `code_commit`: the `GIT_COMMIT_SHA` environment variable if set; otherwise the output of `git rev-parse HEAD` if the process is running where `git` is available and the working directory is a git repository; otherwise `None`. This value is never fabricated.
- `data_snapshot_id`: the `NIRIZAN_DATA_SNAPSHOT_ID` environment variable only, with no fallback. `None` if unset.

Every trace that passes through `enqueue_trace` gets tagged with whichever of these two values were resolved at construction time, overwriting whatever was already on the trace's `code_commit`/`data_snapshot_id` fields.

**Failure handling.** If persisting a queued trace raises an exception, `TraceCollector`'s background worker logs the error and moves on to the next item. It does not retry the failed trace and does not re-queue it; a persistence failure means that trace is dropped. Plan your `TraceSink` implementation's own error handling accordingly if you need stronger delivery guarantees.

**Connecting to the instrumentation layer.** `CollectorExporter` is an adapter: it implements `BaseExporter` (see [Exporters](#exporters)) by forwarding every exported trace into a `TraceCollector`'s queue. Pass a `CollectorExporter(collector)` as a `Tracer`'s `exporter` to have all its traces flow into the collector automatically, as in the example above.

### Dispatching Traces to Metrics

`MetricDispatcher` is a simple registry: it maps a system type (an arbitrary string you choose, e.g. `"rag"`, `"agent"`) to the list of `Metric` instances that should run against traces of that type.

```python
from nirizan.orchestrator.dispatcher import MetricDispatcher
from nirizan.metrics.rag_triad import RAGTriadMetric
from nirizan.metrics.behavioral_anchor import BehavioralAnchorMetric

dispatcher = MetricDispatcher()
dispatcher.register(RAGTriadMetric(scorer=my_scorer), applies_to={"rag"})
dispatcher.register(BehavioralAnchorMetric(target_embedding=my_target), applies_to={"agent"})

results = await dispatcher.dispatch(trace, system_type="rag")
```

Registration is explicit: nothing in `MetricDispatcher` registers a metric automatically at import time or elsewhere. A metric can be registered under more than one system type by passing more than one value in `applies_to`. `dispatch(trace, system_type)` calls `evaluate(trace)` on every metric registered for that system type, in registration order, and flattens all their results into a single list; a `system_type` with no registered metrics yields an empty list rather than an error.

### Scheduling Evaluation Runs

`RunScheduler` triggers an on-demand evaluation run across every stored trace for an application, dispatches each through a `MetricDispatcher`, and saves one `Run` per trace.

```python
from nirizan.orchestrator.scheduler import RunScheduler

# trace_source must satisfy TraceSource: async list_by_application(application_name, limit=100) -> list[Trace]
# run_repository must satisfy RunSink: async save_run(run) -> None
scheduler = RunScheduler(
    trace_source=my_trace_repository,
    dispatcher=dispatcher,
    run_repository=my_run_repository,
)

runs = await scheduler.run_on_demand(application_name="my-rag-app", system_type="rag")
```

For each trace returned by `trace_source.list_by_application(application_name)`, `run_on_demand` dispatches it through `dispatcher.dispatch(trace, system_type)`, builds a `Run` from the resulting `MetricResult` list, saves it via `run_repository.save_run(run)`, and includes it in the returned list. `list_by_application` is called with no explicit `limit`, so whichever default your own `TraceSource` implementation uses applies; the `limit: int = 100` shown in the `TraceSource` protocol documents the expected shape only; `typing.Protocol` itself does not supply or enforce that default.

**Versioning is currently a fixed placeholder here, not resolved per run.** Every `Run` built by `run_on_demand` is stamped with constant values, `code_commit="phase2-unversioned"` and `data_snapshot_id="unversioned"`, regardless of whatever `code_commit`/`data_snapshot_id` were already set on the underlying `Trace` (for example, by `TraceCollector`). If you need a `Run`'s versioning fields to reflect the trace's actual recorded commit and snapshot, read them from the `Trace` itself rather than from the `Run` objects `RunScheduler` produces in this release.

### Regression Concepts

The regression layer turns two sets of metric scores, a candidate run and a historical baseline, into a `RegressionVerdict` per metric: whether anything regressed, and how severely.

```python
from nirizan.regression import (
    BaselineComparator,
    RegressionSeverity,
    RegressionVerdict,
)
```

Unlike `nirizan.instrumentation`, `nirizan.metrics`, and `nirizan.orchestrator`, `nirizan.regression`'s `__init__.py` does re-export its comparator-level public names, so `from nirizan.regression import ...` works directly for `BaselineComparator`, `RegressionSeverity`, `RegressionVerdict`, `classify_severity`, `cohens_d`, and `mean_delta`. The lower-level statistical helpers in `nirizan.regression.thresholds` (covered below) are not re-exported at the package level; import those from their own submodule.

**`RegressionSeverity`** is a three-value enum: `NONE`, `WARNING`, `BLOCKING`.

**`RegressionVerdict`** is the result of comparing one metric's candidate scores against its baseline scores: which metric, the resulting severity, the statistical values behind that decision (`p_value`, `effect_size`; `z_score` is always `None` in this release, see the note below), which baseline and run it was computed against, and a human-readable `explanation` string.

**A note on `z_score`.** NiriZan's regression detection uses a Mann-Whitney U test and Cohen's d rather than a Z-score computation; `RegressionVerdict.z_score` exists as a field but is always set to `None` by this module. Don't rely on it being populated.

**Sign convention: negative means worse.** `cohens_d` (and therefore `effect_size` on a `RegressionVerdict`) is computed as `(candidate.mean() - baseline.mean()) / pooled_std`. If the candidate is worse than the baseline, its mean is lower, so the effect size is **negative**. `DEFAULT_WARNING_EFFECT` and `DEFAULT_BLOCKING_EFFECT` (from `nirizan.regression.thresholds`) are both negative numbers for exactly this reason. A positive effect size (candidate better than baseline) is never classified as `WARNING` or `BLOCKING`, no matter how statistically significant it is; see [`classify_severity`](#classify_severity).

### Comparing a Baseline

`BaselineComparator` is the entry point for regression detection. Construct one with your significance and effect-size thresholds, then compare candidate scores against baseline scores.

```python
import numpy as np
from uuid import uuid4
from nirizan.regression import BaselineComparator

comparator = BaselineComparator(alpha=0.05, warning_effect=-0.20, blocking_effect=-0.50)

verdict = comparator.compare_metric(
    metric_name="groundedness",
    candidate=np.array([0.71, 0.68, 0.74, 0.70, 0.66, 0.69]),
    baseline=np.array([0.82, 0.85, 0.80, 0.83, 0.81, 0.79]),
    baseline_id=uuid4(),
    run_id=uuid4(),
)

print(verdict.severity, verdict.effect_size, verdict.p_value)
```

`compare_metric` runs a one-sided Mann-Whitney U test (candidate stochastically less than baseline) to decide statistical significance at `self.alpha`, computes Cohen's d as the effect size, and classifies severity from those two values. It compares exactly one metric and does **not** apply any multiple-comparison correction; if you're calling `compare_metric` in a loop over several metrics yourself, each call's significance decision is independent of the others. For that, use `compare` instead (below).

**Threshold validation is deferred to call time, not construction time.** `BaselineComparator.__init__` validates only that `0.0 < alpha < 1.0`. It does *not* check that `warning_effect < 0` or that `blocking_effect < warning_effect` when the comparator is constructed; those checks live inside `classify_severity`, and only run (and raise `ValueError` if violated) the first time you call `compare_metric` or `compare`. Constructing `BaselineComparator(warning_effect=0.1)`, for instance, succeeds; calling `compare_metric` on it later raises.

### Comparing Many Metrics at Once

`compare` runs `compare_metric` across a whole dict of metrics, then applies Holm-Bonferroni correction across all of them together, so testing many metrics from the same run doesn't inflate your overall false-positive rate.

```python
verdicts = comparator.compare(
    candidate_scores={
        "context_relevance": np.array([...]),
        "groundedness": np.array([...]),
        "answer_relevance": np.array([...]),
    },
    baseline_scores={
        "context_relevance": np.array([...]),
        "groundedness": np.array([...]),
        "answer_relevance": np.array([...]),
    },
    baseline_id=uuid4(),
    run_id=uuid4(),
)

for verdict in verdicts:
    print(verdict.metric_name, verdict.severity)
```

**Both dicts must have exactly the same set of metric names.** `compare` raises `ValueError` immediately if `candidate_scores` is missing a key present in `baseline_scores`, or vice versa; it does not silently skip mismatched metrics.

**How correction changes the outcome.** `compare` first computes an uncorrected `RegressionVerdict` per metric via `compare_metric` (each judged individually against `self.alpha`), then reruns Holm-Bonferroni across the whole batch of p-values at the same `self.alpha`. Any metric whose uncorrected severity was `WARNING` or `BLOCKING` but does **not** survive that family-wise correction is downgraded to `RegressionSeverity.NONE` in the final result, with `"; not significant after Holm-Bonferroni correction"` appended to its `explanation`. Metrics that were already `NONE`, or that remain significant after correction, are returned unchanged. The list `compare` returns is always the corrected, final set of verdicts, in metric-name-sorted order; there is no way to get the uncorrected per-metric verdicts back out of `compare` itself (call `compare_metric` directly if you want those).

**A note on the statistical helper functions used here.** `BaselineComparator` is built on `mann_whitney_regression`, `holm_bonferroni`, and `validate_scores` from `nirizan.regression.thresholds`, not the similarly-named functions in `nirizan.metrics.statistical_gating` covered earlier in [Statistical Gating](#statistical-gating). The two modules implement the same statistical ideas independently and are **not interchangeable** — see the callout at the top of [`nirizan.regression.thresholds`](#nirizanregressionthresholds) for the exact differences before assuming one is a drop-in replacement for the other.

### Gate Concepts

The gate layer takes the output of regression detection and turns it into a single release decision: ship or block, plus a confidence interval to justify it. This is the layer meant to sit directly in a CI/CD pipeline.

```python
from nirizan.gate import GateVerdict, evaluate_gate, select_decision_metric
```

`nirizan.gate`'s `__init__.py` re-exports `GateVerdict`, `evaluate_gate`, and `select_decision_metric` from `nirizan.gate.verdict`. Everything in `nirizan.gate.ci` (covered in [CI Integration](#ci-integration)), along with `nirizan.gate.verdict`'s own `SEVERITY_WEIGHT` and `bootstrap_delta_ci`, is **not** re-exported at the package level; import those from their specific submodules.

**`GateVerdict`** is the outcome: `passed` (bool), a `confidence_interval` (a `(low, high)` tuple), the full list of `regression_verdicts` that went into the decision, and the `run_id` it was computed for.

**How the decision is made** is a two-part process, both driven by `evaluate_gate`:

1. **Pass/fail** is based on the whole list of `RegressionVerdict`s you pass in: the gate fails (`passed=False`) if **any** verdict in the list has `severity == RegressionSeverity.BLOCKING`, regardless of which metric that is. A single blocking regression anywhere blocks the release.
2. **The confidence interval** reported on the `GateVerdict`, by contrast, comes from only **one** metric: whichever `RegressionVerdict` `select_decision_metric` picks as the "worst" one (see below). The pass/fail outcome and the reported confidence interval are computed independently of each other; the confidence interval is there to characterize the severity of the worst finding, not to determine pass/fail itself.

### Evaluating a Gate

```python
import numpy as np
from nirizan.gate import evaluate_gate

# verdicts: list[RegressionVerdict], e.g. from BaselineComparator.compare(...)
# scores_by_metric maps each metric name that appears in `verdicts`
# to its (candidate_scores, baseline_scores) arrays.
scores_by_metric = {
    "context_relevance": (candidate_context_scores, baseline_context_scores),
    "groundedness": (candidate_groundedness_scores, baseline_groundedness_scores),
    "answer_relevance": (candidate_answer_scores, baseline_answer_scores),
}

gate_verdict = evaluate_gate(verdicts=verdicts, scores_by_metric=scores_by_metric)

if not gate_verdict.passed:
    raise SystemExit("Blocking regression detected")
```

**`scores_by_metric` must cover every metric that could be selected.** `evaluate_gate` doesn't know in advance which metric `select_decision_metric` will pick as "worst," so `scores_by_metric` needs an entry for every metric name appearing in `verdicts`, not just the ones you expect to be worst. If the selected metric's name is missing from `scores_by_metric`, `evaluate_gate` raises a plain `KeyError` (not a `ValueError` with a descriptive message) from the dictionary lookup.

**Selecting the "worst" metric.** `select_decision_metric(verdicts)` picks the single `RegressionVerdict` to represent the gate's confidence interval, by two-level ranking:

1. Highest severity first (`BLOCKING` > `WARNING` > `NONE`), using the module-level `SEVERITY_WEIGHT` mapping.
2. Among verdicts tied on severity, the one with the **most negative** (worst) `effect_size` wins the tie. A verdict with `effect_size=None` is treated as `0.0` for this comparison only; its actual `effect_size` field is left untouched.

`select_decision_metric` always returns something as long as `verdicts` is non-empty, even if every verdict's severity is `NONE` — in that case it still returns whichever `NONE`-severity verdict has the worst effect size, and `evaluate_gate` will still compute and report a confidence interval for that metric even though nothing regressed. Both `select_decision_metric` and `evaluate_gate` raise `ValueError` if `verdicts` is empty.

**The confidence interval itself** comes from `nirizan.gate.verdict.bootstrap_delta_ci`, called internally with its defaults (`n_bootstrap=5000`, `confidence=0.95`, `seed=42`); `evaluate_gate` does not expose parameters to change these. If you need a different bootstrap configuration, call `bootstrap_delta_ci` yourself and construct a `GateVerdict` directly.

**This is yet another `bootstrap_delta_ci`.** `nirizan.gate.verdict.bootstrap_delta_ci` is a third implementation of the same idea already covered twice: once in [`nirizan.metrics.statistical_gating`](#nirizanmetricsstatistical_gating) and referenced again in [Regression Concepts](#regression-concepts). It is not identical to the `metrics.statistical_gating` version — see the comparison in [`nirizan.gate.verdict`](#nirizangateverdict) for the exact differences (notably: this version validates `n_bootstrap >= 1`, which the `metrics` version does not, but does not validate score range or finiteness, which the `metrics` version does via `validate_scores`).

### CI Integration

`nirizan.gate.ci` turns a `GateVerdict` into the concrete outputs a CI pipeline needs: a human-readable summary, a process exit code, and a JSON payload.

```python
import sys
from nirizan.gate.ci import (
    format_gate_summary,
    write_github_summary,
    gate_exit_code,
    serialize_gate_verdict,
)

print(format_gate_summary(gate_verdict))
```

**`format_gate_summary`** renders a Markdown table, one row per entry in `gate_verdict.regression_verdicts` (in whatever order that list is already in; this function doesn't sort it), followed by a `**Gate:** PASS`/`BLOCK` line and a bootstrap CI line. **The "95%" in that CI line is a hardcoded label**, not derived from any confidence value stored on `GateVerdict` — if a `GateVerdict`'s `confidence_interval` was actually computed at a different confidence level (for example, by calling `bootstrap_delta_ci` yourself with `confidence=0.90` and constructing the `GateVerdict` by hand), the printed label will still say "95%" regardless.

**`write_github_summary(verdict, *, output)`** writes that same summary (plus a trailing newline) to a file-like object you provide. It does not open `$GITHUB_STEP_SUMMARY` or any other file itself; you're responsible for supplying the right `TextIO`:

```python
import os
from nirizan.gate.ci import write_github_summary

with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
    write_github_summary(gate_verdict, output=f)
```

**`gate_exit_code(verdict)`** returns `0` if `verdict.passed`, `1` otherwise, following the usual process-exit-code convention:

```python
import sys
sys.exit(gate_exit_code(gate_verdict))
```

**`serialize_gate_verdict(verdict)`** returns an indented JSON string via `verdict.model_dump(mode="json")`, suitable for writing to a file or piping to another tool. `mode="json"` means Pydantic converts non-JSON-native types itself (`UUID` to string, the `confidence_interval` tuple to a JSON array, `RegressionSeverity` members to their string values, `datetime` fields on nested `RegressionVerdict` objects to ISO 8601 strings, and so on); you don't need to convert these yourself before calling `json.dumps`.

### Reporting Concepts

The reporting layer combines everything covered so far, health, judge reliability, regression, and gate results, into one data snapshot for human inspection. It renders nothing itself.

```python
from nirizan.reporting.dashboard import DashboardSnapshot, assemble_dashboard_snapshot
from nirizan.reporting.health_score import compute_system_health_score
from nirizan.reporting.judge_reliability import (
    JudgeReliabilityStatus,
    JudgeReliabilityMetrics,
    compute_judge_reliability,
    judge_score_delta_series,
    system_score_delta_series,
)
```

`nirizan.reporting`'s own `__init__.py` re-exports nothing; import from the specific submodule, as shown above.

**A note on `nirizan.trust`:** `nirizan.reporting` depends on `AttributionVerdict` and `DriftAttribution` from `nirizan.trust.attribution`. Both are now fully documented in [`nirizan.trust.attribution`](#nirizantrustattribution); the fields referenced by this section (`AttributionVerdict.attribution`, `.evaluated_at`, `.judge_score_delta`, `.system_score_delta`, `.anchor_set_id`, and `DriftAttribution`'s three members `NONE`, `JUDGE_DRIFT`, `SYSTEM_DRIFT`) match that authoritative definition exactly, with no additional fields or members left unaccounted for.

`DashboardSnapshot` is a pure data model: it does not render, print, or format anything by itself. Turning it into something a human looks at, a CLI table, a notebook cell, a future web dashboard, is left to the caller.

### System Health Score

`compute_system_health_score` is a single, standalone function that turns a quality score and a confidence value into one 0-100 number, discounted if judge or system drift is present.

```python
from nirizan.reporting.health_score import compute_system_health_score
from nirizan.trust.attribution import DriftAttribution

score = compute_system_health_score(
    quality_score=0.87,
    confidence=0.95,
    attribution=DriftAttribution.NONE,
)
```

**Formula:** `round(quality_score * confidence * 100.0 * multiplier, 1)`, where `multiplier` depends on `attribution`:

| `attribution` | Multiplier |
|---|---|
| `DriftAttribution.NONE` | `1.00` |
| `DriftAttribution.JUDGE_DRIFT` | `0.90` |
| `DriftAttribution.SYSTEM_DRIFT` | `0.80` |
| anything else | `0.70` |

The last row matters if `DriftAttribution` (once documented in full under `nirizan.trust`) turns out to have members beyond these three, or if some other value is passed: `compute_system_health_score` does not raise in that case, it silently falls back to a `0.70` multiplier via a dict `.get(...)` default. Note that `quality_score` and `confidence` are not validated or clamped to `[0.0, 1.0]` by this function itself; passing values outside that range will produce a result outside the nominal `0`-`100` band without any warning or error, so it's the caller's responsibility to pass valid values here (the `DashboardSnapshot` model this feeds into does validate the final `health_score` field to `[0.0, 100.0]`, so an out-of-range result would only surface as a validation error one step downstream, in `assemble_dashboard_snapshot`).

### Judge Reliability

`compute_judge_reliability` aggregates a window of `AttributionVerdict` history into one longitudinal summary: how often the judge drifted, how often the system drifted, and whether the overall picture looks stable.

```python
from nirizan.reporting.judge_reliability import compute_judge_reliability

metrics = compute_judge_reliability(attribution_verdicts)
print(metrics.status, metrics.judge_drift_rate)
```

**All verdicts passed in must share one `anchor_set_id`.** Mixing verdicts from more than one anchor set raises `ValueError`; NiriZan's anchor sets are meant to be fixed and versioned (a change creates a new `anchor_set_id` rather than editing in place), so blending two anchor sets in one summary would mean averaging results from two different rulers. `compute_judge_reliability` also raises `ValueError` on an empty `verdicts` list; a reliability rate needs at least one observation.

**Rates** (`judge_drift_rate`, `system_drift_rate`, `none_rate`) are simple fractions of `verdicts` whose `.attribution` equals each corresponding `DriftAttribution` member; the three always sum to `1.0` over the input.

**`status`** is `UNSTABLE` if `judge_drift_rate` exceeds `drift_rate_warning` (default `0.10`, exposed as the module constant `DEFAULT_JUDGE_DRIFT_RATE_WARNING`), `STABLE` otherwise. This default is a starting point, not a value calibrated against real judge-drift data; treat it as a placeholder and override the `drift_rate_warning` parameter if you have your own base rates for calibration.

**`mean_judge_score_delta` / `judge_score_delta_std`** summarize `judge_score_delta` across every verdict in the window, drift or not, computed with a sample standard deviation (`ddof=1`, i.e. divided by `n-1`); with fewer than 2 verdicts, `judge_score_delta_std` is `0.0` rather than undefined.

**`mean_calibration_mae`** is only populated if you pass `calibration_errors`, a list of dicts each expected to have a `"mae"` key (for example, the output of `nirizan.metrics.statistical_gating.calibrate_gold_set`, which returns `{"mae": ..., "mse": ..., "rmse": ...}`); entries without an `"mae"` key are silently skipped rather than raising. If you omit `calibration_errors`, or none of the entries have `"mae"`, this field stays `None`.

**`flagged_verdicts`** is every verdict whose `.attribution` is not `DriftAttribution.NONE`, i.e. every judge-drift or system-drift verdict in the window, kept for drill-down.

Two smaller standalone functions produce the underlying time series without the full aggregation, useful for plotting:

```python
from nirizan.reporting.judge_reliability import (
    judge_score_delta_series,
    system_score_delta_series,
)

series = judge_score_delta_series(attribution_verdicts)  # [(datetime, float), ...]
```

Both `judge_score_delta_series` and `system_score_delta_series` return a list of `(evaluated_at, delta)` tuples sorted oldest to newest, across every verdict passed in regardless of its `attribution` (unlike `flagged_verdicts`, these are not filtered to drift-only entries).

### Assembling a Dashboard Snapshot

`assemble_dashboard_snapshot` is the single entry point that ties health score, judge reliability, and regression/gate results together into one `DashboardSnapshot`.

```python
from nirizan.reporting.dashboard import assemble_dashboard_snapshot

snapshot = assemble_dashboard_snapshot(
    system_type="rag",
    quality_score=0.87,
    confidence=0.95,
    attribution_verdicts=attribution_verdicts,   # list[AttributionVerdict] | None
    regression_verdicts=regression_verdicts,     # list[RegressionVerdict] | None
    gate_verdict=gate_verdict,                   # GateVerdict | None
    calibration_errors=calibration_errors,       # list[dict[str, float]] | None
)
```

**`quality_score` and `confidence` are yours to decide, not derived here.** This function does not compute or look up a quality score or confidence value on its own; it's a direct pass-through into `compute_system_health_score`. Deciding which metric's score (and what confidence) represents "the" system's overall quality is left to the caller.

**`attribution_verdicts` drives both `latest_attribution` and `judge_reliability`, and both are optional outcomes if it's empty or omitted:**

- If `attribution_verdicts` is a non-empty list, `latest_attribution` is set to whichever verdict has the latest `.evaluated_at`, and that verdict's `.attribution` feeds `compute_system_health_score` as the drift-penalty input.
- If `attribution_verdicts` is empty or `None`, `latest_attribution` stays `None`, and the health score is computed as if `attribution=DriftAttribution.NONE` — a real result is still produced, on the reasoning that no attribution history to penalize against isn't the same as evidence of drift.
- `judge_reliability` is only populated when `attribution_verdicts` is non-empty **and** `compute_judge_reliability` succeeds. If it raises `ValueError` (most likely: the verdicts span more than one `anchor_set_id`), `assemble_dashboard_snapshot` catches that specific exception, logs a warning, and returns a snapshot with `judge_reliability=None` rather than failing the whole call. Any other exception from `compute_judge_reliability` is not caught here and will propagate.

**Return value:** a `DashboardSnapshot` with `generated_at` set to the current time, `health_score` computed as above, `regression_verdicts` set to whatever list you passed (or `[]` if you passed `None`), and `gate_verdict` passed through unchanged.

**Synchronous.** Does not persist the snapshot anywhere; a `DashboardSnapshot` is not written to storage automatically. Logs at `INFO` on success, `WARNING` if judge reliability aggregation was skipped.

### Trust Concepts

The trust layer answers the question NiriZan's architecture treats as central: when a score drops, did the system actually get worse, or did the judge measuring it change? Two pieces make this possible:

```python
from nirizan.trust.anchor_set import AnchorItem, AnchorSet
from nirizan.trust.attribution import DriftAttribution, AttributionVerdict, AttributionEngine
```

- **`AnchorSet`** is a small, fixed, human-labeled set of `AnchorItem`s: known inputs with known expected outputs and a human-assigned label. Because it's fixed, rescoring the same anchor set later tells you whether the *judge's* behavior changed, independent of anything happening in production traffic.
- **`AttributionEngine`** compares anchor-set rescoring against production score movement, and produces an `AttributionVerdict`: `NONE`, `JUDGE_DRIFT`, or `SYSTEM_DRIFT`.

`nirizan.trust`'s own `__init__.py` re-exports nothing at the package level (only the module docstring); import from `nirizan.trust.anchor_set` or `nirizan.trust.attribution` directly, as shown above. `AttributionVerdict` and `DriftAttribution` are defined in `nirizan.trust.attribution`, documented in full below.

### Anchor Sets

An `AnchorSet` is a versioned, human-labeled reference set: the same fixed inputs, expected outputs, and human labels, rescored repeatedly over time so that a change in the score reveals something about the judge rather than about production traffic.

```python
from datetime import datetime, timezone
from nirizan.trust.anchor_set import AnchorItem, AnchorSet

anchor_set = AnchorSet(
    anchor_set_id="rag-anchors-v1",
    items=[
        AnchorItem(
            anchor_id="a1",
            input_payload="What is the capital of France?",
            expected_output="Paris",
            human_label=1.0,
        ),
        # ... at least one item is required ...
    ],
    created_at=datetime.now(timezone.utc),
)
```

**An `AnchorSet` always has at least one item.** `items` is constrained to a minimum length of 1; constructing one with an empty list raises a Pydantic `ValidationError`.

**`AnchorSet` does not enforce immutability of an existing `anchor_set_id` or the "never edit in place" convention**. An anchor set update is intended to create a new `anchor_set_id` rather than mutate the existing one. `AnchorSet` itself is not `frozen`, and the model does not prevent constructing two different `AnchorSet` objects that reuse the same `anchor_set_id` with different `items`. This convention is currently a matter of discipline at the call site rather than something the model enforces.

**Human labels are scores, not booleans.** `AnchorItem.human_label` is a `float` constrained to `[0.0, 1.0]`, the same normalized range used throughout NiriZan's metrics, rather than a pass/fail flag.

### Judge-Drift Attribution

`AttributionEngine.analyze` is the core comparison: it takes two pairs of score distributions, anchor-set scores (reference vs. rescored) and production scores (baseline vs. candidate), and decides whether any detected drop is attributable to the judge, the system, or neither.

```python
from nirizan.trust.attribution import AttributionEngine

engine = AttributionEngine(significance_threshold=0.05)

verdict = engine.analyze(
    anchor_set_id="rag-anchors-v1",
    anchor_ref_scores=[0.91, 0.88, 0.93, 0.90],       # judge's historical scores on the anchor set
    anchor_rescored_scores=[0.89, 0.87, 0.92, 0.91],  # judge's scores on the same anchor set, rescored now
    prod_baseline_scores=[0.85, 0.82, 0.88, 0.84],    # production scores from the baseline run
    prod_candidate_scores=[0.71, 0.68, 0.74, 0.70],   # production scores from the candidate run
)

print(verdict.attribution, verdict.explanation)
```

**The decision logic, in order:**

1. **Judge drift takes priority.** If the anchor set's rescored mean differs from its reference mean by at least `significance_threshold` in *either* direction (`abs(judge_delta) >= significance_threshold`), the verdict is `JUDGE_DRIFT`, regardless of what happened in production. The reasoning: if the judge's own behavior on a fixed, unchanging reference set has moved, any simultaneous change in production scores can't be trusted as evidence about the system, since the ruler itself moved.
2. **System drift is checked only if judge drift wasn't detected**, and only in one direction: production candidate scores must be lower than baseline by at least `significance_threshold` (`system_delta < 0`, not just `abs(system_delta) >= significance_threshold`). A production score *improvement* of the same magnitude is not classified as `SYSTEM_DRIFT`; it falls through to `NONE`.
3. **Otherwise, `NONE`.**

**This is a simple mean-difference threshold test, not a statistical significance test.** Despite the parameter being named `significance_threshold` and the generated `explanation` text using the phrase "statistically significant," `analyze` does not run any hypothesis test (no Mann-Whitney U, no t-test, no p-value); it computes `np.mean(...)` on each of the four input lists and compares raw mean differences against a fixed threshold. Contrast this with `nirizan.regression.comparator.BaselineComparator`, which does run an actual Mann-Whitney U test. If you need statistical rigor behind a drift decision (accounting for sample size and variance, not just the raw mean gap), this method alone does not provide it.

**All four score lists are required, with no default and no minimum-length check** beyond whatever `np.mean` itself does with the input (an empty list passed to `np.mean` produces a `RuntimeWarning` and a `nan` result via NumPy, rather than a `ValueError` raised by `analyze` itself; `analyze` does not validate its inputs before computing means).

**`AttributionVerdict.explanation`** is a plain, human-readable string reporting which condition matched and the relevant delta value; it's generated fresh by `analyze`, not configurable or templated.

### Storage Concepts

The storage layer persists everything the layers above produce or consume: traces, runs, baselines, sessions, and run-to-run comparisons. It's built around Protocol-based repository interfaces, each with at least one concrete implementation, so any layer that needs storage (the orchestrator's `TraceCollector`, for instance) depends only on a narrow Protocol shape, not on a specific backend.

```python
from nirizan.storage.models import SpanRecord, TraceRecord, Run, Baseline
```

`nirizan.orchestrator.scheduler.RunScheduler.run_on_demand` constructs and persists `Run` objects; `Run` is defined here in `nirizan.storage.models`. Its complete field list is `run_id`, `trace_id`, `code_commit`, `data_snapshot_id`, `metric_results`, and `created_at`, with validation constraints on `code_commit` and `data_snapshot_id` (see [Storage Models](#storage-models)).

**Repository/record split.** Several storage submodules draw a deliberate line between a *domain model* (`Trace`, `Span`, `Session`, from `nirizan.instrumentation`) and a *storage record* (`TraceRecord`, `SpanRecord`, from `nirizan.storage.models`): the record types are pure serialization shells with `str`-typed fields matching a database schema, and conversion happens explicitly at the boundary via `from_trace`/`to_trace` and `from_span`/`to_span`. Repository interfaces (`BaseTraceRepository`, and the various Protocols below) operate on the domain models at their public boundary; the record types are meant to stay an internal detail of `SQLiteTraceRepository`'s own implementation. If you're implementing your own trace repository against `BaseTraceRepository`, you don't need `TraceRecord` or `SpanRecord` at all unless your own backend happens to want the same serialization shape.

**Every repository interface here is a small, separate Protocol (or, for traces, an ABC) per concern**, not one unified storage interface: `BaselineRepository` (baselines only), `ExperimentStore` (runs, plus a diffing capability), `RunRepository` (runs, a narrower Protocol than `ExperimentStore`), `SessionRepository` (sessions only), and `BaseTraceRepository` (traces, as an `ABC` rather than a `Protocol`, so you subclass it rather than just duck-typing it). `RunRepository`'s own docstring describes itself as intentionally narrower than `ExperimentStore`; the two overlap on `Run` persistence but aren't the same interface and aren't declared to be interchangeable.

### Storage Models

`nirizan.storage.models` defines both the domain-facing `Run` and `Baseline` models, and the storage-internal `SpanRecord`/`TraceRecord` serialization shells.

```python
from nirizan.storage.models import Run, Baseline, SpanRecord, TraceRecord
```

**`Run`** ties a trace to the `MetricResult`s computed against it, plus versioning metadata:

```python
from datetime import datetime, timezone
from uuid import uuid4
from nirizan.storage.models import Run

run = Run(
    run_id=uuid4(),
    trace_id=uuid4(),
    code_commit="a1b2c3d",       # at least 7 characters, e.g. a short git SHA
    data_snapshot_id="v1",
    metric_results=[],
    created_at=datetime.now(timezone.utc),
)
```

`code_commit` is constrained to 7-40 characters (the range spanning a short to a full git SHA), and `data_snapshot_id` to a minimum of 1 character. **This means `RunScheduler.run_on_demand`'s placeholder values are right at the edge of validity, not comfortably inside it:** `"phase2-unversioned"` (19 characters) passes the `code_commit` length check only because it happens to be long enough, not because it resembles a commit SHA; `"unversioned"` easily satisfies `data_snapshot_id`'s minimum of 1. Neither placeholder is validated as looking like an actual SHA or snapshot identifier, only checked for length.

**`Baseline`** is a named, queryable set of "known good" historical runs, referenced by id rather than embedded:

```python
from nirizan.storage.models import Baseline

baseline = Baseline(
    baseline_id=uuid4(),
    system_type="rag",
    run_ids=[uuid4(), uuid4()],
    established_at=datetime.now(timezone.utc),
    label="pre-v0.3-release",
)
```

`run_ids` requires at least one id (empty list raises a Pydantic `ValidationError`); `label` requires at least one character. `Baseline` stores `Run` ids, not `Run` objects, so resolving a `Baseline` into the actual score arrays a `BaselineComparator` needs is left to the caller: fetch each `run_id` via a `Run`-persisting repository, pull out the relevant metric scores, and hand those arrays to `BaselineComparator.compare` or `compare_metric` yourself.

**`SpanRecord` and `TraceRecord`** are the storage-internal serialization pair described in [Storage Concepts](#storage-concepts): every timestamp and UUID field is stored as a plain `str` (via `.isoformat()` and `str(...)`), `attributes` is stored pre-serialized as a JSON string (`attributes_json`), and `SpanRecord`/`TraceRecord` are not `strict` Pydantic models (no `model_config` override at all, so default lax validation applies) unlike most other models in this manual. `SpanRecord.from_span(span)` / `.to_span()` and `TraceRecord.from_trace(trace)` / `.to_trace()` are the two-way conversion functions; they're used internally by `SQLiteTraceRepository` and are the pattern to follow if you implement your own record-based trace repository. Ordinary use of the storage layer (via `BaseTraceRepository`'s `save`/`get`/`list_by_application` methods) never requires touching `SpanRecord` or `TraceRecord` directly.

### Trace Storage

`BaseTraceRepository` is the abstract interface for persisting and querying traces; `SQLiteTraceRepository` is the one concrete implementation provided.

```python
from nirizan.storage.trace_repository import SQLiteTraceRepository

repo = SQLiteTraceRepository(db_path="nirizan_traces.db")

await repo.save(trace)
fetched = await repo.get(trace.trace_id)   # Trace | None
recent = await repo.list_by_application("my-rag-app", limit=50, offset=0)
deleted_count = await repo.purge_older_than("2026-01-01T00:00:00+00:00")

repo.close()
```

**Schema:** two tables, `traces` and `spans`, with a foreign key from `spans.trace_id` to `traces.trace_id` (`ON DELETE CASCADE`, and `PRAGMA foreign_keys = ON` is set on the connection), plus three indexes: `(application_name, created_at DESC)` on `traces`, and both `trace_id` alone and `(kind, started_at DESC)` on `spans`.

**`save(trace)`** upserts (`INSERT OR REPLACE`) the trace row and every one of its span rows in a single transaction. Calling `save` again with a `Trace` that reuses an existing `trace_id` replaces the stored row entirely; because of the cascading foreign key, replacing a trace this way does not orphan its old spans (a `REPLACE` on the parent row triggers the cascade delete on the old children first).

**`get(trace_id)`** returns the full `Trace`, spans included (ordered by `started_at` ascending), or `None` if no trace with that id exists. Never raises for a missing trace, per the interface's own docstring ("the repository stays a dumb, honest store").

**`list_by_application(application_name, limit=100, offset=0)`** returns traces for one application, newest first (`created_at DESC`), with standard SQL pagination via `LIMIT`/`OFFSET`. This is the concrete implementation behind the `TraceSource` Protocol used by `nirizan.orchestrator.scheduler.RunScheduler` (see [Scheduling Evaluation Runs](#scheduling-evaluation-runs)); `SQLiteTraceRepository` satisfies `TraceSource`'s shape.

**`purge_older_than(created_before_iso)`** deletes every trace (and, via cascade, its spans) with `created_at` earlier than the given ISO 8601 timestamp string, and returns the number of trace rows deleted. **The comparison is a plain string comparison** (SQL `WHERE created_at < ?` against text columns), not a parsed datetime comparison; this works correctly only if every stored `created_at` value uses a consistent, sortable ISO 8601 format (which `TraceRecord.from_trace` does produce, via `datetime.isoformat()`), and if the string you pass in uses the same format. Passing a differently-formatted timestamp string will silently produce an incorrect (not necessarily erroring) result rather than a type error.

**Concurrency:** every database operation, including the schema-initialization statements run once at construction, executes through `asyncio.to_thread`, so `SQLiteTraceRepository`'s async methods don't block the event loop even though `sqlite3` itself is synchronous. The single `sqlite3.Connection` is created with `check_same_thread=False` specifically to allow this. This does not add cross-process or cross-connection concurrency guarantees beyond what SQLite itself provides; it only keeps a single Python process's event loop unblocked.

**`close()`** closes the underlying connection. It is synchronous (not `async`), unlike every other method on this class.

`BaseTraceRepository` also satisfies the `TraceSink` Protocol from `nirizan.orchestrator.collector` (see [Collecting and Persisting Traces](#collecting-and-persisting-traces)): its `save(trace) -> None` method matches `TraceSink`'s required shape exactly, so `SQLiteTraceRepository` (or any subclass of `BaseTraceRepository`) can be passed directly as a `TraceCollector`'s `repository`.

### Run and Baseline Storage

Two overlapping-but-distinct interfaces exist for persisting `Run`s: the narrower `RunRepository` (with an in-memory implementation), and the broader `ExperimentStore` (with a SQLite implementation, covered in [Comparing Runs](#comparing-runs)). `Baseline` persistence has its own separate interface, `BaselineRepository`.

```python
from nirizan.storage.run_repository import RunRepository, InMemoryRunRepository
from nirizan.storage.baselines import BaselineRepository, SQLiteBaselineRepository
```

**`RunRepository`** (Protocol) requires only `save_run(run) -> None` and `get_run(run_id) -> Run | None`. `InMemoryRunRepository` is a plain dict-backed implementation:

```python
from nirizan.storage.run_repository import InMemoryRunRepository

repo = InMemoryRunRepository()
await repo.save_run(run)
fetched = await repo.get_run(run.run_id)  # Run | None; never raises for a missing id
```

`InMemoryRunRepository` satisfies `RunSink` from `nirizan.orchestrator.scheduler` (see [Scheduling Evaluation Runs](#scheduling-evaluation-runs)) as well as `RunRepository`; both Protocols only require `save_run`. It holds everything in a plain `dict[UUID, Run]` with no persistence across process restarts, no pagination, and no querying beyond exact-id lookup; there's no `list_runs`-style method on this interface at all.

**`BaselineRepository`** (Protocol) requires `save_baseline`, `get_baseline`, and `list_baselines(system_type)`. `SQLiteBaselineRepository` is the SQLite-backed implementation:

```python
from nirizan.storage.baselines import SQLiteBaselineRepository

repo = SQLiteBaselineRepository(db_path="nirizan_baselines.db")

await repo.save_baseline(baseline)
fetched = await repo.get_baseline(baseline.baseline_id)          # Baseline | None
all_rag_baselines = await repo.list_baselines(system_type="rag")  # newest first
repo.close()
```

`run_ids` on a `Baseline` is stored as a single JSON-encoded text column (`run_ids_json`), not a relational junction table, per the class's own docstring; there's no SQL-level foreign key from a baseline's `run_ids` back to the `runs` table (and, since `SQLiteBaselineRepository` and a `Run`-persisting repository like `SQLiteExperimentStore` use separate SQLite database files by default, there couldn't be an enforced foreign key across them even if the schema wanted one). `list_baselines` returns baselines for one `system_type`, ordered newest-established-first. `save_baseline` upserts by `baseline_id`. Same threading model as `SQLiteTraceRepository`: every query runs through `asyncio.to_thread`, and `close()` is synchronous.

### Session Storage

`SessionRepository` is the simplest interface in this layer: save and fetch a `Session` by id, nothing more.

```python
from nirizan.storage.session_repository import SessionRepository, InMemorySessionRepository

repo = InMemorySessionRepository()
await repo.save_session(session)
fetched = await repo.get_session(session.session_id)  # Session | None
```

`InMemorySessionRepository` is dict-backed, with the same characteristics as `InMemoryRunRepository`: no persistence across restarts, no querying beyond exact-id lookup, `get_session` returns `None` rather than raising for a missing id. There is no SQLite-backed `SessionRepository` implementation among the modules reviewed in this manual; if you need persistent session storage, you'd need to implement `SessionRepository` yourself, or use `InMemorySessionRepository` only where in-process storage is acceptable.

### Comparing Runs

`ExperimentStore` is a broader Protocol than `RunRepository`: it adds a `diff` capability for comparing two runs' metric scores directly. `SQLiteExperimentStore` is the SQLite-backed implementation.

```python
from nirizan.storage.experiment_store import ExperimentStore, SQLiteExperimentStore, RunDiff

store = SQLiteExperimentStore(db_path="nirizan_experiments.db")

await store.record_run(run)
fetched = await store.get_run(run.run_id)          # Run | None
diff = await store.diff(run_a_id, run_b_id)         # RunDiff
```

**`RunDiff`** is a small, purely computational model: `run_a`, `run_b` (the two run ids compared), and `metric_deltas`, a `dict[str, float]` mapping each metric name **present in both runs** to `score_b - score_a`. Per the class's own docstring, `RunDiff` "computes only, never judges whether it's a regression" — there's no severity, no significance test, no connection to `nirizan.regression` here at all. If a metric name appears in only one of the two runs, it's silently excluded from `metric_deltas` rather than raising or including a partial entry; `RunDiff` only reports on the intersection of the two runs' metric names.

**`diff(run_a, run_b)`** fetches both runs internally via `get_run` and raises `ValueError` if either id doesn't resolve to a stored `Run`. This is one of the few places in the storage layer that raises on a missing id rather than quietly returning `None`, because a diff of a nonexistent run has no meaningful result to fall back to.

**Schema differs from `SQLiteTraceRepository`'s design in the same way `SQLiteBaselineRepository` does:** `metric_results` is stored as a single JSON text column (`metric_results_json`) on the `runs` table, not a relational table of individual metric rows. On read, each entry is parsed back into a `MetricResult` via `MetricResult.model_validate(m, strict=False)`, explicitly overriding `MetricResult`'s own `strict=True` model config for this deserialization step; this is a deliberate choice to allow the lax type coercion strict mode would otherwise forbid when reading back JSON-round-tripped data (for example, where a JSON round-trip might represent a value in a technically different but compatible type).

**`ExperimentStore` vs. `RunRepository`:** both can save and fetch a `Run`, but they are declared as separate Protocols, not one extending the other, and `SQLiteExperimentStore` and `InMemoryRunRepository` are entirely separate classes with separate storage. Saving a `Run` through one does not make it visible through the other. Pick whichever Protocol shape a given call site actually needs (`RunSink`/`RunRepository`'s narrower shape, or `ExperimentStore`'s shape if you also need `diff`), and stay consistent about which concrete store backs it for a given `Run`'s lifecycle.

---

## API Reference

### `nirizan` package

Canonical import:

```python
import nirizan
```

| Name | Kind | Summary |
|---|---|---|
| `nirizan.__version__` | `str` attribute | The installed package version. |
| `nirizan.enable_logging` | function | Opt in to NiriZan's log output. |
| `nirizan.disable_logging` | function | Silence NiriZan's log output. |
| `nirizan.get_logger` | function | Get a logger scoped under the `nirizan` hierarchy. |
| `nirizan.set_log_level` | function | Change the active log level without touching handlers. |

These four functions are re-exported at the top level of the package specifically so that application code never needs to import from `nirizan._logging` directly. Use `from nirizan import ...`, not `from nirizan._logging import ...`.

---

### Logging API

#### `enable_logging`

**Import**

```python
from nirizan import enable_logging
```

**Purpose**

Opt-in configuration that turns on NiriZan's log output. Intended for notebooks, CLI runs, scripts, or host applications that want to see what NiriZan is doing.

**Signature**

```python
enable_logging(
    level: int | str | None = None,
    stream: TextIO | None = None,
) -> logging.Logger
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `level` | `int \| str \| None` | No | `None` | The log level to set. Accepts a standard `logging` integer level (e.g. `logging.DEBUG`) or a level name string (e.g. `"DEBUG"`, `"INFO"`, case-insensitive). If `None`, the level is read from the `NIRIZAN_LOG_LEVEL` environment variable, defaulting to `"INFO"` if that variable is unset. |
| `stream` | `TextIO \| None` | No | `None` | The stream log output is written to. If `None`, defaults to `sys.stderr`. |

Passing an unrecognized level string raises `ValueError` with a message identifying the invalid value.

**Return value**

Returns the underlying `logging.Logger` instance for the `"nirizan"` logger hierarchy, already configured. The returned logger is the same mutable logger object each call; NiriZan does not create a new logger per call.

**Synchronous.**

**Exceptions**

- `ValueError` — raised if `level` is a string that does not correspond to a valid `logging` level name.

**Side effects**

- Mutates global logging state: sets the level on, and attaches a handler to, the root `"nirizan"` logger.
- Removes any handler that NiriZan itself previously attached via `enable_logging`, before attaching the new one, so repeated calls do not accumulate duplicate handlers.
- Does not remove or otherwise touch handlers attached by anything other than NiriZan's own prior call to `enable_logging`.
- Performs no network calls, no persistence, and no background work.

**Example**

```python
import nirizan

nirizan.enable_logging(level="DEBUG")
```

---

#### `disable_logging`

**Import**

```python
from nirizan import disable_logging
```

**Purpose**

Removes NiriZan's own log handler(s), returning the `"nirizan"` logger to its silent, library-safe default.

**Signature**

```python
disable_logging() -> None
```

**Parameters**

None.

**Return value**

`None`.

**Synchronous.**

**Exceptions**

None.

**Side effects**

- Mutates global logging state: removes any handler previously attached by `enable_logging`.
- Leaves handlers attached by other code untouched.
- Does not reset the logger's level; only the handler is removed.

**Example**

```python
import nirizan

nirizan.enable_logging()
# ... later ...
nirizan.disable_logging()
```

---

#### `get_logger`

**Import**

```python
from nirizan import get_logger
```

**Purpose**

Returns a standard library logger scoped under the `"nirizan"` hierarchy. This is the intended way to obtain a logger from within NiriZan's own modules, and is also available to host applications or extensions that want to log through the same hierarchy.

**Signature**

```python
get_logger(module_name: str) -> logging.Logger
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `module_name` | `str` | Yes | — | The name to scope the logger under. Conventionally called as `get_logger(__name__)` so the resulting logger name matches the calling module's dotted path. |

**Return value**

A `logging.Logger` instance. This is a plain, unmodified standard library logger; it has no NiriZan-specific behavior beyond its position in the `"nirizan"` logger hierarchy.

**Synchronous.**

**Exceptions**

None expected under normal use; behavior for a non-string `module_name` follows whatever the standard library's `logging.getLogger` does, since this function is a thin pass-through.

**Side effects**

- No mutation beyond what `logging.getLogger` itself does internally (the standard library caches logger instances by name).
- No I/O, no persistence, no network calls.

**Example**

```python
from nirizan import get_logger

logger = get_logger(__name__)
logger.info("Trace exported")
```

---

#### `set_log_level`

**Import**

```python
from nirizan import set_log_level
```

**Purpose**

Changes the active log level for all NiriZan loggers without attaching, removing, or otherwise touching any handler. Useful for adjusting verbosity at runtime after `enable_logging()` has already been called.

**Signature**

```python
set_log_level(level: int | str) -> None
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `level` | `int \| str` | Yes | — | The new log level. Accepts a standard `logging` integer level or a level name string (case-insensitive). |

**Return value**

`None`.

**Synchronous.**

**Exceptions**

- `ValueError` — raised if `level` is a string that does not correspond to a valid `logging` level name.

**Side effects**

- Mutates global logging state: sets the level on the root `"nirizan"` logger.
- Does not attach or remove any handler. If `enable_logging()` has not been called yet, there is no handler in place, so no output will be visible regardless of the level set here.

**Example**

```python
import nirizan

nirizan.enable_logging()
nirizan.set_log_level("WARNING")
```

---

### Pydantic Model Conventions

Several public models in NiriZan (`Span`, `Trace`, `Session`, and others introduced in later sections) are built on `pydantic.BaseModel`. Rather than repeating the same inherited methods under every model, they're documented once here.

Every model documented in this manual additionally has the standard Pydantic v2 methods and behavior: `model_dump()`, `model_dump_json()`, `model_copy()`, `model_validate()`, `model_validate_json()`, `model_fields`, equality comparison by field values, and so on. Refer to [Pydantic's own documentation](https://docs.pydantic.dev/) for the full, general behavior of these. The sections below document only each model's own fields, its own methods (if it defines any beyond what Pydantic provides), and validation behavior specific to that model.

Two `model_config` settings recur across NiriZan's models and are called out per-model below:

- **`strict=True`** — fields do not perform the "lax" type coercion Pydantic normally allows (for example, a numeric string is not automatically coerced to an `int`). Values must already be (or be an unambiguous representation of) the declared type.
- **`frozen=True`** — the model is immutable after construction; attempting to set an attribute after creation raises an error. Models without `frozen=True` are ordinary mutable Pydantic models.

---

### `nirizan.instrumentation.spans`

Canonical import:

```python
from nirizan.instrumentation.spans import SpanKind, Span, Trace
```

#### `SpanKind`

**Purpose**

An enum identifying the functional role of a span.

**Values**

| Member | Value |
|---|---|
| `SpanKind.PLANNING` | `"planning"` |
| `SpanKind.RETRIEVAL` | `"retrieval"` |
| `SpanKind.TOOL_USE` | `"tool_use"` |
| `SpanKind.GENERATION` | `"generation"` |

`SpanKind` subclasses both `str` and `Enum`, so a `SpanKind` member compares equal to, and can be used anywhere, its underlying string value (`SpanKind.PLANNING == "planning"` is `True`).

---

#### `Span`

**Purpose**

The atomic unit of instrumentation: a single step in an AI execution graph, such as one retrieval call or one generation call.

**Model config:** `strict=True`, `frozen=True`. A `Span` is immutable once constructed.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `span_id` | `UUID` | Yes | — | Unique identifier for this span. |
| `trace_id` | `UUID` | Yes | — | The id of the `Trace` this span belongs to. |
| `parent_span_id` | `UUID \| None` | No | `None` | The id of the enclosing span, if this span was opened while another span was active. `None` for a root span. |
| `kind` | `SpanKind` | Yes | — | The functional role of this span. |
| `name` | `str` | Yes | — | A short human-readable name for the step. Must be 1 to 200 characters. |
| `started_at` | `datetime` | Yes | — | When the span began. |
| `ended_at` | `datetime` | Yes | — | When the span completed. |
| `attributes` | `dict[str, str \| int \| float \| bool]` | No | `{}` | Arbitrary key/value metadata attached to the span. |
| `input_payload` | `str \| None` | No | `None` | The step's input, if captured. |
| `output_payload` | `str \| None` | No | `None` | The step's output, if captured. |

**Why `trace_id` is required here but not user-supplied elsewhere:** you will rarely construct a `Span` directly; `Tracer.start_span(...)` builds one for you and stamps `trace_id` and `parent_span_id` from the active tracing context. The field is required on the model because a span with no trace to belong to isn't a meaningful telemetry record, even though callers of the high-level API never have to supply it themselves.

**Example construction**

```python
from datetime import datetime, timezone
from uuid import uuid4
from nirizan.instrumentation.spans import Span, SpanKind

span = Span(
    span_id=uuid4(),
    trace_id=uuid4(),
    kind=SpanKind.RETRIEVAL,
    name="retrieve_context",
    started_at=datetime.now(timezone.utc),
    ended_at=datetime.now(timezone.utc),
    attributes={"top_k": 5},
    input_payload="What is NiriZan?",
    output_payload="NiriZan is...",
)
```

In normal use, you won't build a `Span` this way; use `Tracer.start_span(...)` (see [Tracing with the Tracer](#tracing-with-the-tracer)) instead.

---

#### `Trace`

**Purpose**

An ordered collection of spans belonging to a single invocation of your application.

**Model config:** `strict=True`. Not frozen; a `Trace` remains mutable after construction, since fields such as `code_commit` and `data_snapshot_id` are stamped onto it later, at ingest by the component responsible for trace ingestion.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `trace_id` | `UUID` | Yes | — | Unique identifier shared by every span in this trace. |
| `application_name` | `str` | Yes | — | Name of the instrumented application, at least 1 character. |
| `spans` | `list[Span]` | No | `[]` | The spans that make up this trace. |
| `created_at` | `datetime` | Yes | — | When this `Trace` object was assembled. |
| `code_commit` | `str \| None` | No | `None` | The code commit this trace was produced under. Not set by the instrumentation layer; stamped at ingest time. |
| `data_snapshot_id` | `str \| None` | No | `None` | Identifier for the data/prompt configuration snapshot this trace was produced under. Not set by the instrumentation layer. |
| `session_id` | `UUID \| None` | No | `None` | The session this trace belongs to, if it was assembled inside a `Tracer.session(...)` block. |

**Validation**

`Trace` validates, on construction, that every span in `spans` has a `trace_id` matching the trace's own `trace_id`. If any span's `trace_id` doesn't match, construction fails with a Pydantic `ValidationError` (wrapping a `ValueError` describing which span and which ids mismatched). You will not normally hit this by hand; `Tracer.get_assembled_trace()` only ever includes spans it already filtered by matching `trace_id`.

**Methods**

##### `spans_of_kind`

```python
spans_of_kind(kind: SpanKind) -> list[Span]
```

Returns the subset of `self.spans` whose `kind` matches the given `SpanKind`. Synchronous. Does not mutate the trace.

**Example**

```python
retrieval_spans = trace.spans_of_kind(SpanKind.RETRIEVAL)
```

---

### `nirizan.instrumentation.sessions`

Canonical import:

```python
from nirizan.instrumentation.sessions import Session
```

#### `Session`

**Purpose**

Represents a multi-turn conversation or interaction as a standalone record: which traces belong to it, and when it started and (optionally) ended.

**Model config:** `strict=True`. Not frozen; a `Session` is described in its own docstring as open until ended, so it remains mutable.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `session_id` | `UUID` | Yes | — | Unique identifier for the session. |
| `application_name` | `str` | Yes | — | Name of the instrumented application, at least 1 character. |
| `trace_ids` | `list[UUID]` | No | `[]` | The traces that belong to this session so far. |
| `started_at` | `datetime` | Yes | — | When the session began. |
| `ended_at` | `datetime \| None` | No | `None` | When the session ended. `None` while the session is still open. |

**Note:** the instrumentation layer does not itself construct or persist `Session` objects; `Tracer.session(...)` only threads a `session_id` through context. This model documents the data shape; building and storing actual `Session` records is handled by the storage layer.

---

### `nirizan.instrumentation.tracer`

Canonical import:

```python
from nirizan.instrumentation.tracer import Tracer, SpanHandle
```

#### `SpanHandle`

**Purpose**

A small mutable handle yielded by `Tracer.start_span(...)`, used to set a span's `output_payload` from inside the `async with` block, before the immutable `Span` is built.

This is a plain `dataclasses.dataclass`, not a Pydantic model. It performs no validation of its own.

**Fields**

| Field | Type | Default | Meaning |
|---|---|---|---|
| `span_id` | `UUID` | — | The id of the span this handle belongs to. Matches the eventual `Span.span_id`. |
| `output_payload` | `str \| None` | `None` | Set this from inside the `async with tracer.start_span(...)` block to record the step's output. |

**Example**

```python
async with tracer.start_span("generate_answer", kind=SpanKind.GENERATION) as span:
    answer = await generate(question)
    span.output_payload = answer
```

---

#### `Tracer`

**Purpose**

The core telemetry object: manages span lifecycles, tracks parent/child relationships and trace/session context, assembles completed spans into a `Trace`, and dispatches finished traces to an exporter.

**Import**

```python
from nirizan.instrumentation.tracer import Tracer
```

**Signature**

```python
Tracer(
    application_name: str,
    exporter: BaseExporter | None = None,
)
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `application_name` | `str` | Yes | — | Name stamped onto every `Trace` this tracer assembles. |
| `exporter` | `BaseExporter \| None` | No | `None` | Where completed traces are sent. If `None`, traces are still assembled and buffered locally, but nothing is exported anywhere. |

**Attributes**

| Attribute | Type | Meaning |
|---|---|---|
| `application_name` | `str` | As passed to the constructor. |
| `exporter` | `BaseExporter \| None` | As passed to the constructor. |

##### `session`

```python
session(session_id: UUID | None = None) -> AsyncContextManager[UUID]
```

Async context manager. Scopes subsequent trace assembly to a session: any `Trace` assembled (via `get_assembled_trace()`, including the automatic assembly that happens when a root span closes) while inside this block has its `session_id` field set. Yields the session id in use, generating a new one with `uuid4()` if `session_id` was not supplied. Restores the prior session context on exit, even if the block raises.

**Async.** Mutates tracing context for the duration of the block (via `contextvars`, so it is safe under concurrent `asyncio` tasks). See [Sessions](#sessions).

##### `start_span`

```python
start_span(
    name: str,
    kind: SpanKind,
    attributes: dict[str, Any] | None = None,
    input_payload: str | None = None,
) -> AsyncContextManager[SpanHandle]
```

Async context manager. Opens a span, yields a `SpanHandle` you can use to set `output_payload`, and closes the span when the block exits, appending the completed `Span` to the tracer's internal buffer.

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `name` | `str` | Yes | — | Name for the resulting span. |
| `kind` | `SpanKind` | Yes | — | The functional role of this span. |
| `attributes` | `dict[str, Any] \| None` | No | `None` | Arbitrary metadata. Values that aren't already `str`, `int`, `float`, or `bool` are converted with `str(...)` before being stored. |
| `input_payload` | `str \| None` | No | `None` | The step's input, if you want it recorded. |

**Return value**

Yields a `SpanHandle`. See [`SpanHandle`](#spanhandle).

**Async.**

**Side effects**

- Appends a completed `Span` to the tracer's internal buffer on exit.
- If this is the outermost (root) span for the current trace context, also assembles the `Trace` via `get_assembled_trace()` and, if `self.exporter` is set, awaits `exporter.export(trace)`.
- Mutates trace/span `contextvars` for the duration of the block, restoring the prior span context on exit.
- Runs its closing logic in a `finally` block: a span is recorded, and a root span's trace is still exported, even if the code inside the `async with` block raises. The exception is not swallowed; it continues to propagate after the span-closing logic runs.

**Example:** see [Tracing with the Tracer](#tracing-with-the-tracer).

##### `get_assembled_trace`

```python
get_assembled_trace(trace_id: UUID | None = None) -> Trace
```

Assembles a `Trace` model from the tracer's currently buffered spans.

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `trace_id` | `UUID \| None` | No | `None` | Which trace to assemble. If `None`, uses the currently active trace context, falling back to a freshly generated id if there is no active trace. |

**Return value**

A `Trace` containing every currently buffered `Span` whose `trace_id` matches, `created_at` set to the current time, and `session_id` set from the currently active session context (if any is active at the time this method runs).

**Synchronous.** Does not mutate the tracer's span buffer; you can call it multiple times.

##### `clear`

```python
clear() -> None
```

Empties the tracer's internal span buffer. Does not affect anything already sent to an exporter, and does not reset trace or session context.

**Synchronous.**

---

### `nirizan.instrumentation.exporters`

Canonical import:

```python
from nirizan.instrumentation.exporters import BaseExporter, InMemoryExporter, ConsoleExporter
```

#### `BaseExporter`

**Purpose**

Abstract base class every trace exporter implements.

**Extension contract**

Subclass `BaseExporter` and implement:

```python
async def export(self, trace: Trace) -> None:
    ...
```

`export` is abstract and required; NiriZan will not instantiate a subclass that doesn't define it. NiriZan does not add retries, delivery guarantees, or batching around your implementation; if you need those, implement them inside `export`.

Optionally override:

```python
async def shutdown(self) -> None:
    ...
```

`shutdown` defaults to a no-op. Override it to release connections or background workers your exporter opened. NiriZan does not currently call `shutdown` automatically; it exists as a hook for the caller to invoke when the exporter needs to release resources.

**How NiriZan invokes it:** `Tracer.start_span(...)` calls `await exporter.export(trace)` once, when a root span closes, if an exporter was configured on the `Tracer`.

---

#### `InMemoryExporter`

**Purpose**

Buffers exported traces in a local list. Intended for unit tests and local experiments, not production use.

**Signature**

```python
InMemoryExporter()
```

Takes no arguments.

##### `export`

```python
async def export(self, trace: Trace) -> None
```

Appends `trace` to an internal list. **Async.** Mutates internal state. No I/O, no network calls.

##### `get_traces`

```python
get_traces() -> list[Trace]
```

Returns a copy of the traces exported so far. **Synchronous.** The returned list is a new list object; mutating it does not affect the exporter's internal buffer.

##### `clear`

```python
clear() -> None
```

Empties the internal buffer. **Synchronous.**

---

#### `ConsoleExporter`

**Purpose**

Logs a one-line summary of each exported trace instead of storing it.

**Signature**

```python
ConsoleExporter()
```

Takes no arguments.

##### `export`

```python
async def export(self, trace: Trace) -> None
```

Logs the trace id, application name, and span count at `INFO` level, through a standard `logging.getLogger(__name__)` logger (name: `nirizan.instrumentation.exporters`). Since this logger name falls under the `nirizan` hierarchy, it is silent by default and becomes visible once you call `nirizan.enable_logging()` (see [Logging](#logging)). **Async**, though the implementation itself performs no actual I/O beyond the logging call. Does not persist or store the trace anywhere.

---

### `nirizan.instrumentation.sdk`

Canonical import:

```python
from nirizan.instrumentation.sdk import (
    init_tracer,
    get_tracer,
    start_session,
    trace_span,
    planning,
    retrieval,
    generation,
    tool_use,
)
```

This module provides a convenience layer on top of `Tracer`, built around a single global tracer instance, so application code doesn't need to thread a `Tracer` object through every function.

#### `init_tracer`

```python
init_tracer(
    application_name: str,
    exporter: BaseExporter | None = None,
) -> Tracer
```

**Purpose**

Creates a `Tracer` and registers it as the global tracer used by `get_tracer()`, `start_session()`, and the decorators (`trace_span`, `planning`, `retrieval`, `generation`, `tool_use`) whenever they aren't given an explicit `tracer=` argument.

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `application_name` | `str` | Yes | — | Passed through to the new `Tracer`. |
| `exporter` | `BaseExporter \| None` | No | `None` | Passed through to the new `Tracer`. |

**Return value**

The newly created `Tracer` instance (the same one now registered globally).

**Synchronous.**

**Side effects**

- Replaces the module-level global tracer. Calling `init_tracer()` again replaces the previous global tracer; it does not merge or preserve state from it.
- Emits an `INFO`-level log line via `nirizan`'s logging (through `get_logger(__name__)`).

---

#### `get_tracer`

```python
get_tracer() -> Tracer | None
```

Returns the currently registered global tracer, or `None` if `init_tracer()` has not been called yet. **Synchronous.** No side effects.

---

#### `start_session`

```python
start_session(session_id: UUID | None = None) -> AsyncContextManager[UUID]
```

**Purpose**

SDK-level pass-through to the global tracer's `session(...)` context manager, so you don't need to call `get_tracer()` yourself.

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `session_id` | `UUID \| None` | No | `None` | As in `Tracer.session(...)`. |

**Return value**

The async context manager returned by the global tracer's `session(...)`; use it with `async with`. Yields the session id in use.

**Exceptions**

- `RuntimeError` — raised immediately (before returning the context manager) if `init_tracer()` has not been called yet.

**Example:** see [Sessions](#sessions).

---

#### `trace_span`

```python
trace_span(
    kind: SpanKind,
    name: str | None = None,
    tracer: Tracer | None = None,
) -> Callable[[AsyncFunc], AsyncFunc]
```

**Purpose**

Decorator factory that wraps an `async def` function so each call becomes one span.

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `kind` | `SpanKind` | Yes | — | The span kind recorded for every call to the decorated function. |
| `name` | `str \| None` | No | `None` | Span name. Defaults to the decorated function's `__name__` if not given. |
| `tracer` | `Tracer \| None` | No | `None` | Which tracer to use. Defaults to the global tracer (`get_tracer()`) if not given. |

**Return value**

A decorator. Applying it to an `async def` function returns a wrapped function with the same signature (preserved via `functools.wraps`) that, when called, opens a span around the original call.

**Applies only to `async def` functions.**

**Exceptions**

- `RuntimeError` — raised when the wrapped function is called, if neither `tracer` nor a previously-initialized global tracer is available.

**Side effects and inferred payloads**

- `input_payload` is inferred as `str(...)` of the first positional argument, or if there are none, `str(...)` of the first keyword argument's value, or `None` if the call had neither. It is not a serialization of the entire argument list.
- `output_payload` is set to `str(result)` automatically if the wrapped function returns a non-`None` value and nothing already set it inside the function body.
- Delegates all span lifecycle behavior (buffering, parent/child nesting, trace assembly, export, and export-on-exception) to `Tracer.start_span(...)`.

**Example:** see [Decorator-Based Instrumentation](#decorator-based-instrumentation).

---

#### `planning`, `retrieval`, `generation`, `tool_use`

```python
planning(name: str | None = None, tracer: Tracer | None = None) -> Callable[[AsyncFunc], AsyncFunc]
retrieval(name: str | None = None, tracer: Tracer | None = None) -> Callable[[AsyncFunc], AsyncFunc]
generation(name: str | None = None, tracer: Tracer | None = None) -> Callable[[AsyncFunc], AsyncFunc]
tool_use(name: str | None = None, tracer: Tracer | None = None) -> Callable[[AsyncFunc], AsyncFunc]
```

Convenience wrappers around `trace_span`, each fixing `kind` to the matching `SpanKind` member (`SpanKind.PLANNING`, `SpanKind.RETRIEVAL`, `SpanKind.GENERATION`, `SpanKind.TOOL_USE` respectively). Parameters, return value, exceptions, and side effects are otherwise identical to `trace_span`.

**Example:** see [Decorator-Based Instrumentation](#decorator-based-instrumentation).

---

### `nirizan.metrics.base`

Canonical import:

```python
from nirizan.metrics.base import MetricResult, Metric, Scorer
```

#### `MetricResult`

**Purpose**

The standard output shape for a single score produced by a metric.

**Model config:** `strict=True`. Not frozen.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `metric_name` | `str` | Yes | — | Identifies which metric (or sub-metric) produced this result, e.g. `"groundedness"`. |
| `trace_id` | `UUID` | Yes | — | The trace this result scores. |
| `score` | `float` | Yes | — | The score itself, constrained to `0.0 <= score <= 1.0`. |
| `confidence` | `float \| None` | No | `None` | Optional confidence in the score, also constrained to `[0.0, 1.0]` when present. Not every metric sets this; `None` means the metric didn't report one, not that confidence is `0`. |
| `details` | `dict[str, str \| int \| float \| bool]` | No | `{}` | Free-form metadata specific to the metric that produced this result. |
| `computed_at` | `datetime` | Yes | — | When this result was computed. |

**Validation:** constructing a `MetricResult` with `score` or `confidence` outside `[0.0, 1.0]` raises a Pydantic `ValidationError`.

**Example construction**

```python
from datetime import datetime, timezone
from uuid import uuid4
from nirizan.metrics.base import MetricResult

result = MetricResult(
    metric_name="groundedness",
    trace_id=uuid4(),
    score=0.82,
    confidence=0.9,
    details={"scorer": "cosine"},
    computed_at=datetime.now(timezone.utc),
)
```

---

#### `Metric`

**Purpose**

The `typing.Protocol` every `Trace`-based metric implements. Any object with the right shape satisfies it, no inheritance required.

**Required shape**

```python
class Metric(Protocol):
    name: str

    async def evaluate(self, trace: Trace) -> list[MetricResult]: ...
```

| Member | Meaning |
|---|---|
| `name` | A `str` attribute identifying the metric. |
| `evaluate(trace)` | `async`. Computes zero or more `MetricResult` objects for the given `Trace`. Must not mutate `trace`. Not responsible for persisting its own output. |

**How NiriZan invokes it:** `evaluate` can be called directly, or through `MetricDispatcher`. `RAGTriadMetric` and `BehavioralAnchorMetric` both satisfy this protocol; see [Writing a Custom Metric](#writing-a-custom-metric) for a minimal implementation.

---

#### `Scorer`

**Purpose**

A small `typing.Protocol` for pairwise text scoring: any callable of the right shape satisfies it.

**Required shape**

```python
class Scorer(Protocol):
    def __call__(self, text_a: str, text_b: str) -> float: ...
```

Takes two strings, returns a single `float`. Used by `RAGTriadMetric` as an injectable comparison technique; nothing about the protocol itself constrains what kind of comparison it performs, but callers expect the result to fall in `[0.0, 1.0]` since it typically ends up as a `MetricResult.score`.

---

### `nirizan.metrics.rag_triad`

Canonical import:

```python
from nirizan.metrics.rag_triad import RAGTriadMetric
```

#### `RAGTriadMetric`

**Purpose**

Reference-free RAG Triad metric: context relevance, groundedness, and answer relevance, each derived from a trace's `PLANNING`, `RETRIEVAL`, and `GENERATION` spans.

**Import**

```python
from nirizan.metrics.rag_triad import RAGTriadMetric
```

**Signature**

```python
RAGTriadMetric(scorer: Scorer)
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `scorer` | `Scorer` | Yes | — | The pairwise text-scoring callable used for all three sub-metrics. |

**Attributes**

| Attribute | Type | Meaning |
|---|---|---|
| `name` | `str` | `"rag_triad"`. Identifies the metric as a whole; not the same as the `metric_name` on each individual `MetricResult` it returns. |

##### `evaluate`

```python
async def evaluate(self, trace: Trace) -> list[MetricResult]
```

Computes `context_relevance`, `groundedness`, and `answer_relevance` where the relevant spans are present. See [Built-in Metrics: RAG Triad](#built-in-metrics-rag-triad) for the full field-extraction rules, the conditions under which each sub-metric is skipped, and what `details["missing_fields"]` contains.

**Async.** Does not mutate `trace`. Calls `self.scorer(...)` synchronously, up to three times, once per sub-metric that has both required texts present.

**Return value:** a list of zero to three `MetricResult` objects. `confidence` is left at `None` on all of them.

**Applicable trace types:** any trace; sub-metrics that lack their required spans are simply omitted rather than raising an error.

**Score semantics:** whatever `scorer(text_a, text_b)` returns, unmodified. `RAGTriadMetric` performs no clipping or transformation of its own.

**Dependencies:** none beyond the `Scorer` you supply.

**Limitations:** only the first span of each relevant kind is used; a trace with multiple `RETRIEVAL` spans (for example, multiple retrieval calls) only has its first one considered for `context_relevance` and `groundedness`.

---

### `nirizan.metrics.behavioral_anchor`

Canonical import:

```python
from nirizan.metrics.behavioral_anchor import BehavioralAnchorMetric
```

#### `BehavioralAnchorMetric`

**Purpose**

Scores each `GENERATION` span in a trace against a fixed target embedding, for detecting drift from an intended persona, tone, or set of constraints over the course of an agent's responses.

**Import**

```python
from nirizan.metrics.behavioral_anchor import BehavioralAnchorMetric
```

**Signature**

```python
BehavioralAnchorMetric(
    target_embedding: np.ndarray,
    threshold: float = 0.85,
    embedding_fn: Callable[[str], np.ndarray] | None = None,
)
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `target_embedding` | `np.ndarray` | Yes | — | The reference embedding every generation span's output is compared against. Stored internally as `float64`. |
| `threshold` | `float` | No | `0.85` | Cosine-similarity threshold at or above which a score is banded `"aligned"`. |
| `embedding_fn` | `Callable[[str], np.ndarray] \| None` | No | `None` | Function that embeds a piece of text. If omitted, falls back to a placeholder that ignores its input and always returns an array of ones shaped like `target_embedding` — see the warning in [Built-in Metrics: Behavioral Anchor](#built-in-metrics-behavioral-anchor). |

**Attributes**

| Attribute | Type | Meaning |
|---|---|---|
| `name` | `str` | `"behavioral_anchor"`. |
| `target_embedding` | `np.ndarray` | As passed to the constructor, coerced to `float64`. |
| `threshold` | `float` | As passed to the constructor. |
| `embedding_fn` | `Callable[[str], np.ndarray]` | The embedding function in use (your own, or the placeholder default). |

##### `evaluate`

```python
async def evaluate(self, trace: Trace) -> list[MetricResult]
```

**Applicable trace types:** any trace; returns `[]` if it has no `GENERATION` spans.

**Inputs:** each `GENERATION` span's `output_payload` (treated as an empty string if `None`).

**Score semantics:** cosine similarity between `embedding_fn(output_payload)` and `target_embedding`, floored at `0.0` and capped at `1.0`. `0.0` if either vector has zero norm.

**Score range:** `[0.0, 1.0]`.

**Confidence behavior:** always `1.0`.

**`details` field:** `band` (`"aligned"` / `"neutral"` / `"deviation"`), `threshold`, `span_id`. See [Built-in Metrics: Behavioral Anchor](#built-in-metrics-behavioral-anchor) for the exact band boundaries.

**Computational characteristics:** one call to `embedding_fn` per `GENERATION` span, plus a constant-time cosine-similarity computation via NumPy.

**Dependencies:** `numpy`; whatever your `embedding_fn` depends on.

**Async.** Does not mutate `trace`.

**Limitations:** with the default `embedding_fn`, every generation span in every trace scores identically, since the placeholder embedding never varies with input text. Meaningful use requires a real `embedding_fn`.

---

### `nirizan.metrics.lightweight_judge`

Canonical import:

```python
from nirizan.metrics.lightweight_judge import ClassificationModel, RegexClassifier, LightweightJudge
```

#### `ClassificationModel`

**Purpose**

A `typing.Protocol` describing the interface `LightweightJudge` expects from its `classifier`.

**Required shape**

```python
class ClassificationModel(Protocol):
    def predict_proba(self, text: str) -> dict[str, float]: ...
```

Takes a piece of text, returns a mapping of class label to predicted probability.

---

#### `RegexClassifier`

**Purpose**

A rule-based fallback classifier satisfying `ClassificationModel`, meant for testing and offline scenarios rather than production classification quality.

**Signature**

```python
RegexClassifier()
```

Takes no arguments.

##### `predict_proba`

```python
def predict_proba(self, text: str) -> dict[str, float]
```

Lowercases `text` and counts how many of a fixed set of whole-word patterns (`hate`, `kill`, `toxic`, `bad`) appear in it. Returns `{"toxic": score, "safe": 1.0 - score}`, where `score = min(1.0, matches * 0.33)`.

**Synchronous.** No I/O, no external dependencies beyond the standard library `re` module.

---

#### `LightweightJudge`

**Purpose**

Fast, local, high-throughput text scoring, intended for volumes where an LLM-as-judge call per item is too expensive.

**Model config:** `arbitrary_types_allowed=True`. Not `strict`, unlike `MetricResult`; its own field values are not restricted to exact-type-only validation.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `metric_name` | `str` | No | `"lightweight_quality_score"` | Name recorded on results this judge produces. |
| `classifier` | `Any` | No | `RegexClassifier()` | The classifier used to score text. Typed as `Any` rather than `ClassificationModel` so that arbitrary user-supplied classifier objects are accepted without Pydantic attempting to validate them; it is expected, but not enforced by the model, to implement `predict_proba(text: str) -> dict[str, float]`. |
| `target_class` | `str` | No | `"safe"` | Which key of `classifier.predict_proba(text)`'s return value becomes the result's `score`. |

**Why every field has a default:** unlike `LLMJudge` below, `LightweightJudge()` is meant to be usable with zero configuration, using the bundled `RegexClassifier`, for quick local testing; supplying your own `classifier` and `target_class` is how you point it at a real model.

##### `evaluate_text`

```python
def evaluate_text(
    self,
    text: str,
    *,
    trace_id: UUID | None = None,
) -> MetricResult
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `text` | `str` | Yes | — | The text to score. |
| `trace_id` | `UUID \| None` | No (keyword-only) | `None` | The `trace_id` to stamp on the resulting `MetricResult`. If omitted, a new random `UUID` is generated. |

**Return value:** a `MetricResult` whose `score` is `classifier.predict_proba(text).get(target_class, 0.0)`, clamped to `[0.0, 1.0]`. Empty or whitespace-only `text` always scores `0.0` without calling the classifier. `confidence` and `details` are left at their model defaults (`None` and `{}`).

**Synchronous.** Does not conform to the `Metric` protocol: it takes text directly rather than a `Trace`, is not `async`, and returns a single `MetricResult` rather than a list. See [Judges: Lightweight and LLM-Based](#judges-lightweight-and-llm-based).

**Side effects:** logs at `INFO` (start and completion), `WARNING` (empty input), and `DEBUG` (raw classifier output) through `nirizan`'s logging. No persistence, no network calls (unless your own `classifier` performs them).

---

### `nirizan.metrics.llm_judge`

Canonical import:

```python
from nirizan.metrics.llm_judge import LLMJudgeResponse, LLMJudge
```

#### `LLMJudgeResponse`

**Purpose**

Documents the expected shape of a parsed LLM judge completion: a score and its reasoning.

**Model config:** `strict=True`. Not frozen.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `score` | `float` | Yes | — | Constrained to `[0.0, 1.0]`. |
| `reasoning` | `str` | Yes | — | The judge's explanation for the score. |

**Note:** `LLMJudge.evaluate` (below) does not currently construct or validate against `LLMJudgeResponse` internally; it parses the completion JSON and extracts `score`/`reasoning` by hand. `LLMJudgeResponse` is documented here as the shape that a well-formed completion is expected to match, and is available for you to use yourself (for example, to validate a completion before handing it to `LLMJudge`).

---

#### `LLMJudge`

**Purpose**

Prompted LLM-as-judge scoring: builds a prompt from a template and the text being judged, calls a completion function you supply, and parses a score and reasoning out of the response.

**Model config:** `arbitrary_types_allowed=True`. Not `strict`.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `metric_name` | `str` | Yes | — | Name recorded on results this judge produces. No default, unlike `LightweightJudge.metric_name`, since there's no single sensible default judge prompt to name. |
| `prompt_template` | `str` | Yes | — | A `str.format`-style template. Must reference `{input}`, `{output}`, and optionally `{context}`. |
| `completion_fn` | `Callable[[str], str]` | Yes | — | A synchronous function that takes the built prompt and returns the raw completion text. Typically wraps a call to an LLM provider. |

##### `evaluate`

```python
def evaluate(
    self,
    *,
    input_text: str,
    output_text: str,
    context: str | None = None,
    trace_id: UUID | None = None,
) -> MetricResult
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `input_text` | `str` | Yes (keyword-only) | — | Fills `{input}` in the prompt template. |
| `output_text` | `str` | Yes (keyword-only) | — | Fills `{output}` in the prompt template. |
| `context` | `str \| None` | No (keyword-only) | `None` | Fills `{context}`; substituted as an empty string if not given. |
| `trace_id` | `UUID \| None` | No (keyword-only) | `None` | Stamped onto the result. A new random `UUID` is generated if omitted. |

**Return value:** a `MetricResult`. `score` comes from parsing `completion_fn(prompt)`'s return value as JSON and reading its `"score"` key (coerced to `float`, then clamped to `[0.0, 1.0]`). `details["reasoning"]` holds the parsed `"reasoning"` key (or a failure explanation, see below); `details["prompt"]` holds the exact prompt sent to `completion_fn`. `confidence` is left at `None`.

**Synchronous.** Does not conform to the `Metric` protocol (see [Judges: Lightweight and LLM-Based](#judges-lightweight-and-llm-based)).

**Exceptions:** does not raise on a malformed completion. If `completion_fn`'s output isn't valid JSON, or lacks a usable `"score"`, `evaluate` catches the parse failure internally, logs a warning, and returns a `MetricResult` with `score=0.0` and `details["reasoning"]` set to a message that includes a truncated copy of the raw completion.

**Side effects:** calls `completion_fn(prompt)` synchronously, once per call. Any network I/O inside `completion_fn` blocks the calling thread for its duration, since `evaluate` is not `async`. Logs at `INFO`, `DEBUG` (the built prompt), and `WARNING` (parse failures) through `nirizan`'s logging.

---

### `nirizan.metrics.statistical_gating`

Canonical import:

```python
from nirizan.metrics.statistical_gating import (
    validate_scores,
    mann_whitney_regression,
    bootstrap_delta_ci,
    holm_bonferroni,
    approximate_sample_size,
    calibrate_gold_set,
)
```

All functions in this module are synchronous, plain functions (not methods on a class), and depend on `numpy` and `scipy.stats`.

#### `validate_scores`

```python
def validate_scores(scores: np.ndarray) -> np.ndarray
```

Validates that `scores` is non-empty, contains only finite values, and every value is in `[0.0, 1.0]`. Returns the same array unchanged if valid (not a copy).

**Exceptions:** `ValueError` if `scores` is empty, contains non-finite values (`NaN`/`inf`), or contains any value outside `[0.0, 1.0]`.

**Synchronous.** No mutation, no I/O.

---

#### `mann_whitney_regression`

```python
def mann_whitney_regression(
    candidate: np.ndarray,
    baseline: np.ndarray,
) -> tuple[float, float]
```

Runs a one-sided Mann-Whitney U test (`alternative="less"`) testing whether `candidate` is stochastically less than `baseline`, i.e. whether the candidate distribution shows evidence of a regression relative to baseline.

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `candidate` | `np.ndarray` | Yes | The new/current distribution of scores. Validated via `validate_scores`. |
| `baseline` | `np.ndarray` | Yes | The historical distribution of scores to compare against. Validated via `validate_scores`. |

**Return value:** `(statistic, p_value)`, both `float`. A small `p_value` is evidence that `candidate` scores tend to be lower than `baseline` scores. The test is always one-sided ("less"); it does not test for the candidate being higher, and there is no parameter to change that.

**Exceptions:** `ValueError` if either array fails `validate_scores`, or if either has fewer than 5 observations (both groups need at least 5).

**Synchronous.**

---

#### `bootstrap_delta_ci`

```python
def bootstrap_delta_ci(
    candidate: np.ndarray,
    baseline: np.ndarray,
    *,
    n_bootstrap: int = 5000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]
```

Computes a bootstrap confidence interval for the difference in means, `mean(candidate) - mean(baseline)`, by resampling both arrays with replacement `n_bootstrap` times.

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `candidate` | `np.ndarray` | Yes | — | Validated via `validate_scores`. |
| `baseline` | `np.ndarray` | Yes | — | Validated via `validate_scores`. |
| `n_bootstrap` | `int` | No (keyword-only) | `5000` | Number of bootstrap resamples. |
| `confidence` | `float` | No (keyword-only) | `0.95` | Confidence level for the interval; must be strictly between 0 and 1. |
| `seed` | `int` | No (keyword-only) | `42` | Seed for `numpy`'s random generator. Results are deterministic for a fixed seed and fixed inputs; the default is a fixed value, not randomized per call. |

**Return value:** `(ci_low, ci_high)`, the `alpha/2` and `1 - alpha/2` quantiles of the bootstrap delta distribution, where `alpha = 1 - confidence`. This is a confidence interval for the *difference* in mean score, not for either distribution's individual scores.

**Exceptions:** `ValueError` if `confidence` is not strictly between 0 and 1, or if either array fails `validate_scores`.

**Synchronous.** No I/O; computation is CPU-bound and scales with `n_bootstrap` and the size of `candidate`/`baseline`.

---

#### `holm_bonferroni`

```python
def holm_bonferroni(
    p_values: Mapping[str, float],
    alpha: float = 0.05,
) -> dict[str, bool]
```

Applies the Holm-Bonferroni step-down correction to a set of p-values, for testing multiple metrics at once without inflating the overall false-positive rate.

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `p_values` | `Mapping[str, float]` | Yes | — | Metric name to p-value (for example, from repeated calls to `mann_whitney_regression`). |
| `alpha` | `float` | No | `0.05` | Family-wise significance level; must be strictly between 0 and 1. |

**Return value:** a `dict` with exactly the same keys as `p_values`, each mapped to `True` if that hypothesis is rejected (treated as statistically significant) under the correction, `False` otherwise. Every input key is present in the output, including ones the procedure never actually tests (see below). Returns `{}` if `p_values` is empty.

**Procedure:** p-values are sorted ascending. Each is compared, in order, against `alpha / (n - i)` (the standard Holm step-down threshold, `i` being its 0-indexed rank). The first p-value that exceeds its threshold stops the procedure entirely; every hypothesis from that point onward (in sorted order) remains `False`, even if a later p-value would individually have passed its own threshold. This is the standard closed-testing behavior for Holm-Bonferroni, not a bug: once one hypothesis is retained, all remaining ones are retained too.

**Exceptions:** `ValueError` if `alpha` is not strictly between 0 and 1.

**Synchronous.**

---

#### `approximate_sample_size`

```python
def approximate_sample_size(
    *,
    baseline_std: float,
    target_delta: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int
```

Estimates the number of observations needed per group to detect a given effect size, using a normal approximation consistent with the one-sided test used by `mann_whitney_regression`.

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `baseline_std` | `float` | Yes (keyword-only) | — | Standard deviation of the baseline score distribution. Must be positive. |
| `target_delta` | `float` | Yes (keyword-only) | — | The smallest score difference you want to be able to detect. Must be positive. |
| `alpha` | `float` | No (keyword-only) | `0.05` | Significance level, assuming a one-sided test. Must be strictly between 0 and 1. |
| `power` | `float` | No (keyword-only) | `0.80` | Desired statistical power. Must be strictly between 0 and 1. |

**Return value:** an `int`, the required sample size per group, rounded up.

**Exceptions:** `ValueError` if `baseline_std` or `target_delta` is not positive, or if `alpha`/`power` is not strictly between 0 and 1.

**Synchronous.** Depends on `scipy.stats.norm.ppf`.

---

#### `calibrate_gold_set`

```python
def calibrate_gold_set(
    predictions: np.ndarray,
    gold_labels: np.ndarray,
) -> dict[str, float]
```

Computes calibration error between a set of predicted scores and a human-labeled gold set: mean absolute error, mean squared error, and root mean squared error.

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `predictions` | `np.ndarray` | Yes | Predicted scores. |
| `gold_labels` | `np.ndarray` | Yes | Corresponding gold-standard labels, same shape as `predictions`. |

**Return value:** `{"mae": float, "mse": float, "rmse": float}`.

**Exceptions:** `ValueError` if `predictions.shape != gold_labels.shape`.

**Note:** unlike the other functions in this module, `calibrate_gold_set` does not call `validate_scores`; it only checks that the two arrays' shapes match, and does not require values to fall in `[0.0, 1.0]`.

**Synchronous.**

---

### `nirizan.orchestrator.collector`

Canonical import:

```python
from nirizan.orchestrator.collector import TraceSink, TraceCollector, CollectorExporter
```

#### `TraceSink`

**Purpose**

A `typing.Protocol` describing the shape `TraceCollector` needs from a repository, so the orchestrator layer doesn't need to import the storage layer directly.

**Required shape**

```python
class TraceSink(Protocol):
    async def save(self, trace: Trace) -> None: ...
```

Any object with an `async save(self, trace: Trace) -> None` method satisfies it.

---

#### `TraceCollector`

**Purpose**

Async ingestion component that buffers incoming traces on an internal queue and persists them via a background worker task, tagging each with commit and data-snapshot metadata at ingest time.

**Import**

```python
from nirizan.orchestrator.collector import TraceCollector
```

**Signature**

```python
TraceCollector(repository: TraceSink)
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `repository` | `TraceSink` | Yes | — | Where traces are persisted. Must satisfy `TraceSink` (an `async save(trace) -> None` method). |

**Attributes**

| Attribute | Type | Meaning |
|---|---|---|
| `repository` | `TraceSink` | As passed to the constructor. |
| `queue` | `asyncio.Queue[Trace]` | The internal buffer traces wait in before being persisted. |

##### `start`

```python
async def start(self) -> None
```

Starts the background worker task that drains `queue` and calls `repository.save(trace)` for each item. Idempotent: calling `start()` again while already running does nothing.

**Async.** Side effect: creates an `asyncio.Task`.

##### `stop`

```python
async def stop(self) -> None
```

Signals the worker to stop accepting new processing cycles, waits for everything currently on the queue to finish being processed (`queue.join()`), then cancels the worker task.

**Async.** Waits for queued work to drain before returning; safe to call once instrumented code has stopped producing new traces.

##### `enqueue_trace`

```python
async def enqueue_trace(self, trace: Trace) -> None
```

Creates a copy of `trace` (via `Trace.model_copy`, so the `trace` object you pass in is not mutated) with `code_commit` and `data_snapshot_id` overwritten to the values resolved when this `TraceCollector` was constructed, then places that copy on the internal queue.

**Async.** Does not mutate the `trace` argument. Does not persist anything directly; persistence happens later, in the background worker started by `start()`.

**Side effects and failure behavior:** see [Collecting and Persisting Traces](#collecting-and-persisting-traces) for exactly how `code_commit`/`data_snapshot_id` are resolved, and for the background worker's no-retry failure behavior.

---

#### `CollectorExporter`

**Purpose**

Adapter that implements the instrumentation layer's `BaseExporter` contract (see [Exporters](#exporters)) by forwarding every exported trace into a `TraceCollector`.

**Import**

```python
from nirizan.orchestrator.collector import CollectorExporter
```

**Signature**

```python
CollectorExporter(collector: TraceCollector)
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `collector` | `TraceCollector` | Yes | — | The collector traces are forwarded to. |

##### `export`

```python
async def export(self, trace: Trace) -> None
```

Calls `self.collector.enqueue_trace(trace)`. **Async.** Inherited `shutdown()` (from `BaseExporter`) is not overridden here; it remains a no-op.

**Example:** see [Collecting and Persisting Traces](#collecting-and-persisting-traces).

---

### `nirizan.orchestrator.dispatcher`

Canonical import:

```python
from nirizan.orchestrator.dispatcher import MetricDispatcher
```

#### `MetricDispatcher`

**Purpose**

Routes a `Trace` to the `Metric` instances registered for its system type, and collects their results.

**Import**

```python
from nirizan.orchestrator.dispatcher import MetricDispatcher
```

**Signature**

```python
MetricDispatcher()
```

Takes no arguments.

##### `register`

```python
def register(self, metric: Metric, applies_to: set[str]) -> None
```

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `metric` | `Metric` | Yes | Any object satisfying the `Metric` protocol (see [`Metric`](#metric)). |
| `applies_to` | `set[str]` | Yes | Which system type strings this metric should run for. A metric can be registered under more than one system type in one call. |

**Return value:** `None`.

**Synchronous.** Mutates the dispatcher's internal registry. Registration only happens when you call `register` explicitly; nothing registers a metric automatically.

##### `dispatch`

```python
async def dispatch(self, trace: Trace, system_type: str) -> list[MetricResult]
```

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `trace` | `Trace` | Yes | The trace to evaluate. |
| `system_type` | `str` | Yes | Which registered metrics to run. |

**Return value:** the flattened, concatenated results of calling `await metric.evaluate(trace)` on every `Metric` registered for `system_type`, in registration order. An empty list if no metrics are registered for that `system_type`.

**Async.** Does not mutate `trace` itself (though this depends on the registered metrics not doing so, per the `Metric` protocol's contract). No persistence.

**Example:** see [Dispatching Traces to Metrics](#dispatching-traces-to-metrics).

---

### `nirizan.orchestrator.scheduler`

Canonical import:

```python
from nirizan.orchestrator.scheduler import TraceSource, RunSink, RunScheduler
```

#### `TraceSource`

**Purpose**

A `typing.Protocol` describing the shape `RunScheduler` needs from trace storage, kept local so the orchestrator layer doesn't need to depend on a broader storage repository interface.

**Required shape**

```python
class TraceSource(Protocol):
    async def list_by_application(
        self,
        application_name: str,
        limit: int = 100,
    ) -> list[Trace]: ...
```

The `limit: int = 100` default shown here documents the expected signature; because `typing.Protocol` only checks shape, not behavior, whether that default is actually honored depends on your concrete implementation. `RunScheduler.run_on_demand` calls this method without passing `limit` explicitly.

---

#### `RunSink`

**Purpose**

A `typing.Protocol` describing the shape `RunScheduler` needs from run persistence.

**Required shape**

```python
class RunSink(Protocol):
    async def save_run(self, run: Run) -> None: ...
```

`Run` here refers to `nirizan.storage.models.Run`; see [`nirizan.storage.models`](#nirizanstoragemodels) for the full field reference.

---

#### `RunScheduler`

**Purpose**

Triggers an on-demand evaluation run: fetches an application's stored traces, dispatches each through a `MetricDispatcher`, and persists the resulting `Run` records.

**Import**

```python
from nirizan.orchestrator.scheduler import RunScheduler
```

**Signature**

```python
RunScheduler(
    trace_source: TraceSource,
    dispatcher: MetricDispatcher,
    run_repository: RunSink,
)
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `trace_source` | `TraceSource` | Yes | — | Where to fetch an application's stored traces from. |
| `dispatcher` | `MetricDispatcher` | Yes | — | Used to evaluate each fetched trace. |
| `run_repository` | `RunSink` | Yes | — | Where the resulting `Run` objects are persisted. |

**Attributes**

| Attribute | Type | Meaning |
|---|---|---|
| `trace_source` | `TraceSource` | As passed to the constructor. |
| `dispatcher` | `MetricDispatcher` | As passed to the constructor. |
| `run_repository` | `RunSink` | As passed to the constructor. |

##### `run_on_demand`

```python
async def run_on_demand(
    self,
    application_name: str,
    system_type: str,
) -> list[Run]
```

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `application_name` | `str` | Yes | Which application's stored traces to evaluate. Passed to `trace_source.list_by_application`. |
| `system_type` | `str` | Yes | Passed to `dispatcher.dispatch` for every trace. |

**Return value:** a list of `Run` objects, one per trace returned by `trace_source.list_by_application(application_name)`, in the same order. Each `Run` is built with a freshly generated `run_id`, the source trace's `trace_id`, the `metric_results` from dispatching that trace, and `created_at` set to the current time.

**`code_commit` and `data_snapshot_id` on the resulting `Run` objects are always the fixed placeholder values `"phase2-unversioned"` and `"unversioned"`** in this release, regardless of what's recorded on the underlying `Trace`. See [Scheduling Evaluation Runs](#scheduling-evaluation-runs).

**Async.** Calls `trace_source.list_by_application`, `dispatcher.dispatch`, and `run_repository.save_run` for each trace (one `save_run` call per trace, sequentially, not batched or parallelized).

**Exceptions:** propagates whatever `trace_source.list_by_application`, `dispatcher.dispatch` (and, transitively, any registered `Metric.evaluate`), or `run_repository.save_run` raise. `RunScheduler` does not catch or suppress errors from any of these itself.

---

### `nirizan.regression` package

Canonical import:

```python
from nirizan.regression import (
    BaselineComparator,
    RegressionSeverity,
    RegressionVerdict,
    classify_severity,
    cohens_d,
    mean_delta,
)
```

`nirizan/regression/__init__.py` re-exports these six names directly from `nirizan.regression.comparator`. This is the same top-level-re-export pattern used by `nirizan` itself for logging; unlike `nirizan.instrumentation`, `nirizan.metrics`, and `nirizan.orchestrator`, this submodule's `__init__.py` is not empty. The lower-level statistical functions and threshold constants in `nirizan.regression.thresholds` are not part of this re-export; import those from `nirizan.regression.thresholds` directly.

| Name | Kind | Summary |
|---|---|---|
| `BaselineComparator` | class | Compares candidate metric scores against baseline scores and produces `RegressionVerdict`s. |
| `RegressionSeverity` | enum | `NONE`, `WARNING`, `BLOCKING`. |
| `RegressionVerdict` | Pydantic model | The result of one metric comparison. |
| `classify_severity` | function | Turns a significance flag and effect size into a `RegressionSeverity`. |
| `cohens_d` | function | Computes Cohen's d effect size between two score distributions. |
| `mean_delta` | function | Computes the raw difference in means between two score distributions. |

---

### `nirizan.regression.comparator`

Canonical import: the names below are also importable directly from `nirizan.regression.comparator`, though `from nirizan.regression import ...` (above) is the shorter canonical form.

```python
from nirizan.regression.comparator import (
    RegressionSeverity,
    RegressionVerdict,
    cohens_d,
    mean_delta,
    classify_severity,
    BaselineComparator,
)
```

#### `RegressionSeverity`

**Purpose**

Enum identifying how severe a detected regression is.

**Values**

| Member | Value |
|---|---|
| `RegressionSeverity.NONE` | `"none"` |
| `RegressionSeverity.WARNING` | `"warning"` |
| `RegressionSeverity.BLOCKING` | `"blocking"` |

Subclasses both `str` and `Enum`, so `RegressionSeverity.WARNING == "warning"` is `True`.

---

#### `RegressionVerdict`

**Purpose**

The outcome of comparing one metric's candidate scores against its baseline scores.

**Model config:** `strict=True`. Not frozen.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `metric_name` | `str` | Yes | — | Which metric this verdict is about. |
| `severity` | `RegressionSeverity` | Yes | — | The classified severity. |
| `z_score` | `float \| None` | No | `None` | Present as a field, but not populated; see [the note in Regression Concepts](#regression-concepts). |
| `p_value` | `float \| None` | No | `None` | Constrained to `[0.0, 1.0]` when present. The p-value from the underlying Mann-Whitney U test. |
| `effect_size` | `float \| None` | No | `None` | Cohen's d between candidate and baseline. Negative means the candidate is worse. |
| `baseline_id` | `UUID` | Yes | — | Which baseline this comparison was made against. |
| `run_id` | `UUID` | Yes | — | Which run this comparison was made for. |
| `explanation` | `str` | Yes | — | Human-readable summary of the delta, p-value, and Cohen's d behind the verdict. |

---

#### `cohens_d`

```python
def cohens_d(candidate: np.ndarray, baseline: np.ndarray) -> float
```

**Purpose**

Computes Cohen's d, a standardized effect size, between a candidate and baseline score distribution.

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `candidate` | `np.ndarray` | Yes | Validated via `nirizan.regression.thresholds.validate_scores` before computing. |
| `baseline` | `np.ndarray` | Yes | Validated via `nirizan.regression.thresholds.validate_scores` before computing. |

**Formula:** `(candidate.mean() - baseline.mean()) / pooled_std`, where `pooled_std = sqrt((candidate.std(ddof=1)**2 + baseline.std(ddof=1)**2) / 2)`. Both standard deviations use Bessel's correction (`ddof=1`, i.e. the sample standard deviation). Note this pooling formula is the unweighted root-mean-square of the two groups' standard deviations; it does not weight by each group's sample size the way some "pooled standard deviation" definitions do. Returns `0.0` if `pooled_std` is exactly `0.0` (both groups have zero variance), rather than raising a division error.

**Sign convention:** negative means the candidate's mean is lower than the baseline's, i.e. worse under NiriZan's score convention (higher is better). See [Regression Concepts](#regression-concepts).

**Exceptions:** propagates whatever `validate_scores` raises (`ValueError`) for invalid input.

**Synchronous.**

---

#### `mean_delta`

```python
def mean_delta(candidate: np.ndarray, baseline: np.ndarray) -> float
```

Returns `candidate.mean() - baseline.mean()`, unstandardized (unlike `cohens_d`, not divided by any measure of spread).

**Does not validate its inputs itself.** Callers (such as `BaselineComparator.compare_metric`) are expected to have already validated `candidate`/`baseline` beforehand; calling `mean_delta` directly on unvalidated arrays (containing `NaN`, out-of-range values, or being empty) will not raise the same validation errors `cohens_d` or `validate_scores` would.

**Synchronous.**

---

#### `classify_severity`

```python
def classify_severity(
    *,
    significant: bool,
    effect_size: float,
    warning_effect: float = DEFAULT_WARNING_EFFECT,
    blocking_effect: float = DEFAULT_BLOCKING_EFFECT,
) -> RegressionSeverity
```

**Purpose**

Turns a statistical-significance flag and an effect size into a `RegressionSeverity`.

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `significant` | `bool` | Yes (keyword-only) | — | Whether the comparison was statistically significant, per whatever test you ran. |
| `effect_size` | `float` | Yes (keyword-only) | — | Typically a Cohen's d value, e.g. from `cohens_d`. |
| `warning_effect` | `float` | No (keyword-only) | `DEFAULT_WARNING_EFFECT` (`-0.20`) | The effect-size threshold at or below which a significant result is classified `WARNING`. Must be negative. |
| `blocking_effect` | `float` | No (keyword-only) | `DEFAULT_BLOCKING_EFFECT` (`-0.50`) | The effect-size threshold at or below which a significant result is classified `BLOCKING`. Must be more negative than `warning_effect`. |

**Logic, in order:**

1. If `warning_effect >= 0.0`: raises `ValueError`.
2. If `blocking_effect >= warning_effect`: raises `ValueError`.
3. If `not significant`: returns `RegressionSeverity.NONE`, regardless of `effect_size`.
4. If `effect_size <= blocking_effect`: returns `RegressionSeverity.BLOCKING`.
5. Else if `effect_size <= warning_effect`: returns `RegressionSeverity.WARNING`.
6. Else: returns `RegressionSeverity.NONE`.

Because `warning_effect` and `blocking_effect` are always negative (enforced by steps 1–2), a positive `effect_size` (candidate better than baseline) can never satisfy step 4 or 5, and always falls through to `NONE` in step 6 — an improvement is never reported as `WARNING` or `BLOCKING`, however statistically significant.

**Exceptions:** `ValueError` per steps 1–2 above.

**Synchronous.**

---

#### `BaselineComparator`

**Purpose**

Compares a candidate run's metric scores against a baseline's, producing one `RegressionVerdict` per metric, optionally with family-wise multiple-comparison correction across metrics.

**Import**

```python
from nirizan.regression import BaselineComparator
```

**Signature**

```python
BaselineComparator(
    *,
    alpha: float = DEFAULT_ALPHA,
    warning_effect: float = DEFAULT_WARNING_EFFECT,
    blocking_effect: float = DEFAULT_BLOCKING_EFFECT,
)
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `alpha` | `float` | No (keyword-only) | `DEFAULT_ALPHA` (`0.05`) | Significance level used both for the per-metric Mann-Whitney test and, in `compare`, for the Holm-Bonferroni correction. Must be strictly between 0 and 1 — validated immediately at construction. |
| `warning_effect` | `float` | No (keyword-only) | `DEFAULT_WARNING_EFFECT` (`-0.20`) | Passed through to `classify_severity` on every comparison. **Not validated at construction time**; see below. |
| `blocking_effect` | `float` | No (keyword-only) | `DEFAULT_BLOCKING_EFFECT` (`-0.50`) | Passed through to `classify_severity` on every comparison. **Not validated at construction time**; see below. |

**Deferred validation:** unlike `alpha`, `warning_effect` and `blocking_effect` are not checked when you construct a `BaselineComparator`. The `warning_effect < 0` and `blocking_effect < warning_effect` requirements are enforced inside `classify_severity`, which only runs when you actually call `compare_metric` or `compare`. Constructing a `BaselineComparator` with invalid thresholds succeeds silently; the `ValueError` only appears on first use.

**Attributes**

| Attribute | Type | Meaning |
|---|---|---|
| `alpha` | `float` | As passed to the constructor. |
| `warning_effect` | `float` | As passed to the constructor. |
| `blocking_effect` | `float` | As passed to the constructor. |

**Exceptions (constructor):** `ValueError` if `alpha` is not strictly between 0 and 1.

##### `compare_metric`

```python
def compare_metric(
    self,
    *,
    metric_name: str,
    candidate: np.ndarray,
    baseline: np.ndarray,
    baseline_id: UUID,
    run_id: UUID,
) -> RegressionVerdict
```

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `metric_name` | `str` | Yes (keyword-only) | Recorded on the resulting `RegressionVerdict`. |
| `candidate` | `np.ndarray` | Yes (keyword-only) | Candidate run's scores for this metric. Validated via `nirizan.regression.thresholds.validate_scores`. |
| `baseline` | `np.ndarray` | Yes (keyword-only) | Baseline scores for this metric. Validated the same way. |
| `baseline_id` | `UUID` | Yes (keyword-only) | Recorded on the resulting `RegressionVerdict`. |
| `run_id` | `UUID` | Yes (keyword-only) | Recorded on the resulting `RegressionVerdict`. |

**Return value:** a single `RegressionVerdict`. Computes `p_value` via `nirizan.regression.thresholds.mann_whitney_regression`, `effect_size` via `cohens_d`, and `severity` via `classify_severity(significant=p_value < self.alpha, effect_size=effect_size, warning_effect=self.warning_effect, blocking_effect=self.blocking_effect)`. `z_score` is always `None`.

**No multiple-comparison correction is applied here.** This method judges one metric's p-value directly against `self.alpha`. If you call it in a loop across several metrics, each call's significance decision is independent; use `compare` if you want family-wise correction across a batch.

**Exceptions:** propagates `ValueError` from `validate_scores` (invalid `candidate`/`baseline`), from `mann_whitney_regression` (see [`nirizan.regression.thresholds`](#nirizanregressionthresholds) for its exact validation), and from `classify_severity` (invalid `warning_effect`/`blocking_effect`, per the deferred-validation note above).

**Side effects:** logs at `DEBUG` (comparison details) and, if the resulting severity is `BLOCKING`, an additional `WARNING`-level log line.

**Synchronous.**

##### `compare`

```python
def compare(
    self,
    *,
    candidate_scores: dict[str, np.ndarray],
    baseline_scores: dict[str, np.ndarray],
    baseline_id: UUID,
    run_id: UUID,
) -> list[RegressionVerdict]
```

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `candidate_scores` | `dict[str, np.ndarray]` | Yes (keyword-only) | Metric name to candidate scores, for every metric to compare. |
| `baseline_scores` | `dict[str, np.ndarray]` | Yes (keyword-only) | Metric name to baseline scores. Must have exactly the same keys as `candidate_scores`. |
| `baseline_id` | `UUID` | Yes (keyword-only) | Passed through to every `compare_metric` call. |
| `run_id` | `UUID` | Yes (keyword-only) | Passed through to every `compare_metric` call. |

**Return value:** a list of `RegressionVerdict`, one per metric name, sorted by metric name. Computes an uncorrected verdict per metric via `compare_metric`, then applies `nirizan.regression.thresholds.holm_bonferroni` across all of their p-values at `self.alpha`. Any verdict whose severity was `WARNING` or `BLOCKING` but is not among the metrics that survive that correction is replaced (via `RegressionVerdict.model_copy`) with a copy whose `severity` is downgraded to `RegressionSeverity.NONE` and whose `explanation` has `"; not significant after Holm-Bonferroni correction"` appended. All other verdicts (already `NONE`, or still significant after correction) are returned unchanged.

**Exceptions:** `ValueError` if `candidate_scores` and `baseline_scores` don't have exactly the same set of keys (raised as soon as the first missing key is found, in sorted-metric-name order), plus everything `compare_metric` can raise.

**Side effects:** logs at `INFO` (start and completion) and, per downgraded metric, an `INFO`-level line noting the reclassification. `compare_metric`'s own logging (including the `BLOCKING`-severity `WARNING` log) still fires for the uncorrected pass, even for verdicts later downgraded to `NONE`.

**Synchronous.**

---

### `nirizan.regression.thresholds`

Canonical import:

```python
from nirizan.regression.thresholds import (
    DEFAULT_ALPHA,
    DEFAULT_WARNING_EFFECT,
    DEFAULT_BLOCKING_EFFECT,
    mann_whitney_regression,
    holm_bonferroni,
    validate_scores,
)
```

> **This module is not the same as `nirizan.metrics.statistical_gating`.** Both modules independently implement functions with the same names — `validate_scores`, `mann_whitney_regression`, `holm_bonferroni` — and the same general statistical approach, but their actual behavior differs. Do not assume a function imported from one module behaves like its same-named counterpart in the other. The differences:
>
> | Function | `nirizan.metrics.statistical_gating` | `nirizan.regression.thresholds` |
> |---|---|---|
> | `validate_scores` | Returns the validated `np.ndarray` (the same object). Checks non-empty, finite, and `[0.0, 1.0]`. Does not check dimensionality. | Returns `None`. Checks the same three conditions, **plus** requires the array to be exactly one-dimensional (`ndim == 1`), which the other version does not check. |
> | `mann_whitney_regression` | Coerces inputs with `np.asarray(..., dtype=float)`. Calls its own `validate_scores` internally. Requires **at least 5 observations** in each group, raising `ValueError` otherwise. | Does not coerce dtype. Does not call `validate_scores` internally; only checks that neither array is empty (`.size == 0`). Has **no minimum sample size** requirement beyond non-empty. |
> | `holm_bonferroni` | `alpha` is positional-or-keyword: `holm_bonferroni(p_values, 0.05)` works. | `alpha` is keyword-only: `holm_bonferroni(p_values, 0.05)` raises `TypeError`; you must write `holm_bonferroni(p_values, alpha=0.05)`. The correction algorithm itself is otherwise the same. |
>
> `BaselineComparator` (above) uses the `nirizan.regression.thresholds` versions exclusively. If you're validating scores or running these tests outside of `BaselineComparator`, pick the module deliberately rather than assuming either one matches what a metric-scoring pipeline built on `nirizan.metrics.statistical_gating` expects.

#### Constants

| Name | Value | Meaning |
|---|---|---|
| `DEFAULT_ALPHA` | `0.05` | Default significance level. |
| `DEFAULT_WARNING_EFFECT` | `-0.20` | Default Cohen's d threshold for `WARNING` severity. |
| `DEFAULT_BLOCKING_EFFECT` | `-0.50` | Default Cohen's d threshold for `BLOCKING` severity. |

---

#### `mann_whitney_regression`

```python
def mann_whitney_regression(
    candidate: np.ndarray,
    baseline: np.ndarray,
) -> tuple[float, float]
```

Runs a one-sided Mann-Whitney U test (`alternative="less"`), testing whether `candidate` is stochastically less than `baseline`.

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `candidate` | `np.ndarray` | Yes | Must already be a suitable `np.ndarray`; not coerced. |
| `baseline` | `np.ndarray` | Yes | Same. |

**Return value:** `(statistic, p_value)`, both `float`.

**Exceptions:** `ValueError` if `candidate` or `baseline` is empty (`.size == 0`). Unlike `nirizan.metrics.statistical_gating.mann_whitney_regression`, this function does not enforce a minimum sample size beyond non-empty, and does not itself validate score range or finiteness — see the comparison table above.

**Synchronous.**

---

#### `holm_bonferroni`

```python
def holm_bonferroni(
    p_values: Mapping[str, float],
    *,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, bool]
```

Applies the Holm-Bonferroni step-down correction. `alpha` is **keyword-only** here (unlike the same-named function in `nirizan.metrics.statistical_gating`).

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `p_values` | `Mapping[str, float]` | Yes | — | Metric name to p-value. |
| `alpha` | `float` | No (keyword-only) | `DEFAULT_ALPHA` | Family-wise significance level; must be strictly between 0 and 1. |

**Return value and procedure:** identical algorithm to `nirizan.metrics.statistical_gating.holm_bonferroni` — a `dict` with every input key present, `True` where the hypothesis is rejected under the correction, `False` otherwise, `{}` if `p_values` is empty. p-values are sorted ascending and compared against `alpha / (n - i)`; the first one that exceeds its threshold stops the procedure, and every hypothesis from that point on remains `False`.

**Exceptions:** `ValueError` if `alpha` is not strictly between 0 and 1.

**Synchronous.**

---

#### `validate_scores`

```python
def validate_scores(scores: np.ndarray) -> None
```

Validates a score array before statistical analysis. **Returns `None`**, not the array — this is the key difference from `nirizan.metrics.statistical_gating.validate_scores`, which returns the validated array.

**Checks, in order:**

1. `scores.ndim == 1` — must be one-dimensional.
2. `scores.size > 0` — must be non-empty.
3. All values finite (no `NaN`/`inf`).
4. All values in `[0.0, 1.0]`.

**Exceptions:** `ValueError`, with a distinct message for whichever check fails first.

**Synchronous.**

---

### `nirizan.gate` package

Canonical import:

```python
from nirizan.gate import GateVerdict, evaluate_gate, select_decision_metric
```

`nirizan/gate/__init__.py` re-exports these three names from `nirizan.gate.verdict`. Nothing from `nirizan.gate.ci` is re-exported here; import those functions from `nirizan.gate.ci` directly (see below). `SEVERITY_WEIGHT` and `bootstrap_delta_ci`, both also defined in `nirizan.gate.verdict`, are likewise not re-exported at this package level.

| Name | Kind | Summary |
|---|---|---|
| `GateVerdict` | Pydantic model | The pass/fail release decision, with its supporting confidence interval and regression verdicts. |
| `evaluate_gate` | function | Produces a `GateVerdict` from a list of `RegressionVerdict`s and their underlying score arrays. |
| `select_decision_metric` | function | Picks the single "worst" `RegressionVerdict` used to compute the gate's confidence interval. |

---

### `nirizan.gate.verdict`

Canonical import: the names below are also importable directly from `nirizan.gate.verdict`, though `from nirizan.gate import ...` (above) is the shorter canonical form for `GateVerdict`, `evaluate_gate`, and `select_decision_metric`.

```python
from nirizan.gate.verdict import (
    GateVerdict,
    SEVERITY_WEIGHT,
    bootstrap_delta_ci,
    select_decision_metric,
    evaluate_gate,
)
```

#### `GateVerdict`

**Purpose**

The final release decision produced by the gate layer.

**Model config:** `strict=True`. Not frozen.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `passed` | `bool` | Yes | — | `True` if no `BLOCKING`-severity regression was found anywhere in `regression_verdicts`. |
| `confidence_interval` | `tuple[float, float]` | Yes | — | `(low, high)` bootstrap confidence interval for the mean-score delta of the single "worst" metric, as selected by `select_decision_metric`. Not a confidence interval for every metric in `regression_verdicts`, only the selected one. |
| `regression_verdicts` | `list[RegressionVerdict]` | No | `[]` | The full list of regression verdicts this gate decision was based on. |
| `run_id` | `UUID` | Yes | — | The run this gate decision applies to. When built via `evaluate_gate`, this is taken from the selected decision metric's own `run_id`, not independently verified against the other verdicts' `run_id`s. |

---

#### `SEVERITY_WEIGHT`

**Purpose**

Module-level constant mapping each `RegressionSeverity` to an integer weight, used by `select_decision_metric` to rank verdicts by severity.

**Value**

```python
SEVERITY_WEIGHT: dict[RegressionSeverity, int] = {
    RegressionSeverity.BLOCKING: 3,
    RegressionSeverity.WARNING: 2,
    RegressionSeverity.NONE: 1,
}
```

Higher weight means higher severity. Not re-exported at the `nirizan.gate` package level; import it from `nirizan.gate.verdict` if you need it directly (for example, to replicate or extend the ranking `select_decision_metric` uses).

---

#### `bootstrap_delta_ci`

```python
def bootstrap_delta_ci(
    candidate: np.ndarray,
    baseline: np.ndarray,
    *,
    n_bootstrap: int = 5000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]
```

Computes a bootstrap confidence interval for `mean(candidate) - mean(baseline)`, by resampling both arrays with replacement `n_bootstrap` times. Same general approach as `nirizan.metrics.statistical_gating.bootstrap_delta_ci`, but a separate implementation with real behavioral differences; see the comparison table below.

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `candidate` | `np.ndarray` | Yes | — | Not coerced to a particular dtype; must already be a numeric array. |
| `baseline` | `np.ndarray` | Yes | — | Same. |
| `n_bootstrap` | `int` | No (keyword-only) | `5000` | Number of bootstrap resamples. Must be at least `1`. |
| `confidence` | `float` | No (keyword-only) | `0.95` | Confidence level; must be strictly between 0 and 1. |
| `seed` | `int` | No (keyword-only) | `42` | Seed for `numpy`'s random generator. Deterministic for a fixed seed and fixed inputs. |

**Return value:** `(ci_low, ci_high)`, the `alpha/2` and `1 - alpha/2` quantiles of the bootstrap delta distribution, where `alpha = 1 - confidence`.

**Exceptions:** `ValueError` if `candidate` or `baseline` is empty, if `n_bootstrap < 1`, or if `confidence` is not strictly between 0 and 1.

**Synchronous.**

> **Not the same as `nirizan.metrics.statistical_gating.bootstrap_delta_ci`.** Both compute the same statistic with the same default `n_bootstrap`/`confidence`/`seed`, but:
>
> | | `nirizan.metrics.statistical_gating` | `nirizan.gate.verdict` |
> |---|---|---|
> | Input validation | Calls `validate_scores` on both arrays: checks non-empty, finite, and every value in `[0.0, 1.0]`. Coerces inputs with `np.asarray(..., dtype=float)`. | Only checks `.size == 0` for both arrays. Does not check finiteness or `[0.0, 1.0]` range. Does not coerce dtype. |
> | `n_bootstrap` validation | Not checked; a value less than 1 is not explicitly rejected. | Explicitly checked: raises `ValueError` if `n_bootstrap < 1`. |
>
> `evaluate_gate` uses the `nirizan.gate.verdict` version exclusively. Pick the module deliberately if you're calling `bootstrap_delta_ci` outside of `evaluate_gate`.

---

#### `select_decision_metric`

```python
def select_decision_metric(
    verdicts: list[RegressionVerdict],
) -> RegressionVerdict
```

**Purpose**

Selects the single `RegressionVerdict` that represents the "worst" outcome across a list, used by `evaluate_gate` to decide which metric's confidence interval to report.

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `verdicts` | `list[RegressionVerdict]` | Yes | Must be non-empty. |

**Return value:** the `RegressionVerdict` with the highest `SEVERITY_WEIGHT`; ties broken by the most negative `effect_size` (an `effect_size` of `None` is treated as `0.0` for this comparison only, without modifying the verdict). See [Evaluating a Gate](#evaluating-a-gate) for the full ranking explanation, including the case where every verdict is `NONE` severity.

**Exceptions:** `ValueError` if `verdicts` is empty.

**Synchronous.**

---

#### `evaluate_gate`

```python
def evaluate_gate(
    *,
    verdicts: list[RegressionVerdict],
    scores_by_metric: dict[str, tuple[np.ndarray, np.ndarray]],
) -> GateVerdict
```

**Purpose**

Produces a `GateVerdict`: selects the worst metric via `select_decision_metric`, computes its bootstrap confidence interval, and decides pass/fail from whether any verdict in the full list is `BLOCKING`.

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `verdicts` | `list[RegressionVerdict]` | Yes (keyword-only) | Must be non-empty. |
| `scores_by_metric` | `dict[str, tuple[np.ndarray, np.ndarray]]` | Yes (keyword-only) | Maps each metric name that appears in `verdicts` to its `(candidate_scores, baseline_scores)` arrays. Must contain an entry for whichever metric `select_decision_metric` ends up selecting; since that isn't known in advance, it should generally cover every metric name in `verdicts`. |

**Return value:** a `GateVerdict`. `passed` is `True` only if no verdict in `verdicts` has `severity == RegressionSeverity.BLOCKING`; note this is evaluated over the **entire** `verdicts` list, independently of which metric was selected for the confidence interval. `confidence_interval` comes from calling `bootstrap_delta_ci` (this module's version, with its defaults; not configurable through `evaluate_gate`'s own parameters) on the selected metric's score arrays. `regression_verdicts` on the result is the full, unfiltered `verdicts` list you passed in. `run_id` is taken from the selected decision metric's `run_id`.

**Exceptions:**

- `ValueError` — if `verdicts` is empty.
- `KeyError` — if `scores_by_metric` doesn't contain an entry for the metric name `select_decision_metric` selects. This is a plain `KeyError` from the internal dictionary lookup, not a `ValueError` with a descriptive message.
- Also propagates any `ValueError` raised by the internal `bootstrap_delta_ci` call (empty score arrays for the selected metric, for instance).

**Synchronous.**

---

### `nirizan.gate.ci`

Canonical import:

```python
from nirizan.gate.ci import (
    format_gate_summary,
    write_github_summary,
    gate_exit_code,
    serialize_gate_verdict,
)
```

Not re-exported at the `nirizan.gate` package level; always import from `nirizan.gate.ci` directly.

#### `format_gate_summary`

```python
def format_gate_summary(verdict: GateVerdict) -> str
```

Renders a Markdown report for `verdict`: a table with one row per entry in `verdict.regression_verdicts` (columns: metric name, severity, p-value, effect size, each formatted or `"n/a"` if `None`), followed by a `**Gate:** PASS`/`**Gate:** BLOCK` line and a `**95% bootstrap CI:** \`low, high\`` line.

**The "95%" text is a fixed label**, not computed from any confidence value stored on `GateVerdict`; `GateVerdict` doesn't retain the confidence level its interval was computed at. If you construct a `GateVerdict` yourself with an interval computed at a different confidence, this function's output will still say "95%."

Rows appear in whatever order `verdict.regression_verdicts` is already in; this function does not sort them.

**Return value:** the report as a single string, without a trailing newline.

**Synchronous.** No I/O; does not mutate `verdict`.

---

#### `write_github_summary`

```python
def write_github_summary(
    verdict: GateVerdict,
    *,
    output: TextIO,
) -> None
```

Writes `format_gate_summary(verdict)` to `output`, followed by one additional newline.

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `verdict` | `GateVerdict` | Yes | The verdict to summarize. |
| `output` | `TextIO` | Yes (keyword-only) | Any writable file-like object. This function does not open `$GITHUB_STEP_SUMMARY` or any other file itself; you supply the destination. |

**Return value:** `None`.

**Side effects:** writes to `output`. Does not close `output`; that's the caller's responsibility.

**Synchronous.** Logs at `INFO` through `nirizan`'s logging before writing.

**Example:** see [CI Integration](#ci-integration).

---

#### `gate_exit_code`

```python
def gate_exit_code(verdict: GateVerdict) -> int
```

Returns `0` if `verdict.passed`, otherwise `1`, following the standard process-exit-code convention where `0` means success.

**Return value:** `int`, always `0` or `1`.

**Side effects:** logs at `INFO` if passed, `ERROR` if not.

**Synchronous.**

**Example:**

```python
import sys
from nirizan.gate.ci import gate_exit_code

sys.exit(gate_exit_code(gate_verdict))
```

---

#### `serialize_gate_verdict`

```python
def serialize_gate_verdict(verdict: GateVerdict) -> str
```

Serializes `verdict` to an indented (2-space) JSON string, via `verdict.model_dump(mode="json")` followed by `json.dumps`.

**Return value:** a JSON string. Because `mode="json"` is used, non-JSON-native field types are already converted for you: `UUID` fields become strings, the `confidence_interval` tuple becomes a JSON array, `RegressionSeverity` enum members become their string values, and any `datetime` fields on the nested `RegressionVerdict` objects become ISO 8601 strings.

**Synchronous.** Logs at `DEBUG` through `nirizan`'s logging.

---

### `nirizan.reporting.health_score`

Canonical import:

```python
from nirizan.reporting.health_score import compute_system_health_score
```

#### `compute_system_health_score`

```python
def compute_system_health_score(
    quality_score: float,
    confidence: float,
    attribution: DriftAttribution,
) -> float
```

**Purpose**

Computes a single composite System Health Score on a 0-100 scale from a quality score, a confidence value, and a drift attribution.

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `quality_score` | `float` | Yes | Not validated or clamped by this function; conventionally expected to be in `[0.0, 1.0]`. |
| `confidence` | `float` | Yes | Same expectation, not enforced here. |
| `attribution` | `DriftAttribution` | Yes | From `nirizan.trust.attribution`; see [`nirizan.trust.attribution`](#nirizantrustattribution) for the full enum reference. |

**Return value:** `round(quality_score * confidence * 100.0 * multiplier, 1)`, where `multiplier` is `1.00` for `DriftAttribution.NONE`, `0.90` for `DriftAttribution.JUDGE_DRIFT`, `0.80` for `DriftAttribution.SYSTEM_DRIFT`, and `0.70` for any other value (via a dict `.get(...)` default, not an explicit error path).

**Exceptions:** none raised by this function itself. Passing `quality_score` or `confidence` outside `[0.0, 1.0]` produces an out-of-nominal-range result rather than an error; validation only happens downstream, if the result is used to construct a `DashboardSnapshot`, whose `health_score` field is constrained to `[0.0, 100.0]`.

**Synchronous.** Pure function: no I/O, no logging, no side effects.

---

### `nirizan.reporting.judge_reliability`

Canonical import:

```python
from nirizan.reporting.judge_reliability import (
    DEFAULT_JUDGE_DRIFT_RATE_WARNING,
    JudgeReliabilityStatus,
    JudgeReliabilityMetrics,
    judge_score_delta_series,
    system_score_delta_series,
    compute_judge_reliability,
)
```

#### `DEFAULT_JUDGE_DRIFT_RATE_WARNING`

**Value:** `0.10`.

**Purpose:** default threshold (as a fraction of evaluated verdicts) above which `compute_judge_reliability` marks its result `UNSTABLE`. This is an uncalibrated starting default, not a value derived from real judge-drift base-rate data; pass your own `drift_rate_warning` to `compute_judge_reliability` if you have a better-informed threshold.

---

#### `JudgeReliabilityStatus`

**Purpose**

Coarse stable/unstable status for the Judge Reliability Panel, analogous in spirit to `RegressionSeverity` in the regression layer, but with two states instead of three.

**Values**

| Member | Value |
|---|---|
| `JudgeReliabilityStatus.STABLE` | `"stable"` |
| `JudgeReliabilityStatus.UNSTABLE` | `"unstable"` |

Subclasses both `str` and `Enum`.

---

#### `JudgeReliabilityMetrics`

**Purpose**

A longitudinal summary of judge behavior over a window of `AttributionVerdict`s. Always the output of aggregating a window of verdicts; a single verdict is not sufficient to construct one because a single verdict has no rate or trend to report.

**Model config:** `strict=True`. Not frozen.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `anchor_set_id` | `str` | Yes | — | The single anchor set every aggregated verdict shares. |
| `period_start` | `datetime` | Yes | — | Earliest `evaluated_at` among the aggregated verdicts. |
| `period_end` | `datetime` | Yes | — | Latest `evaluated_at` among the aggregated verdicts. |
| `verdict_count` | `int` | Yes | — | Number of verdicts aggregated. Constrained to `>= 1`. |
| `judge_drift_rate` | `float` | Yes | — | Fraction of verdicts attributed to judge drift. Constrained to `[0.0, 1.0]`. |
| `system_drift_rate` | `float` | Yes | — | Fraction attributed to system drift. Constrained to `[0.0, 1.0]`. |
| `none_rate` | `float` | Yes | — | Fraction with no drift attributed. Constrained to `[0.0, 1.0]`. These three rates always sum to `1.0`. |
| `mean_judge_score_delta` | `float` | Yes | — | Mean of `judge_score_delta` across all aggregated verdicts. |
| `judge_score_delta_std` | `float` | Yes | — | Sample standard deviation (`ddof=1`) of `judge_score_delta`. `0.0` if fewer than 2 verdicts were aggregated. |
| `mean_calibration_mae` | `float \| None` | No | `None` | Mean MAE across any supplied `calibration_errors` entries that had an `"mae"` key. `None` if none were supplied or none had that key. |
| `status` | `JudgeReliabilityStatus` | Yes | — | `UNSTABLE` if `judge_drift_rate` exceeded the warning threshold used at computation time, `STABLE` otherwise. |
| `flagged_verdicts` | `list[AttributionVerdict]` | No | `[]` | Every aggregated verdict whose attribution was not `DriftAttribution.NONE`. |

---

#### `judge_score_delta_series`

```python
def judge_score_delta_series(
    verdicts: list[AttributionVerdict],
) -> list[tuple[datetime, float]]
```

Returns `(evaluated_at, judge_score_delta)` for every verdict in `verdicts`, sorted oldest to newest. Includes every verdict regardless of `.attribution`, not filtered to drift-only entries.

**Synchronous.** Does not mutate `verdicts`.

---

#### `system_score_delta_series`

```python
def system_score_delta_series(
    verdicts: list[AttributionVerdict],
) -> list[tuple[datetime, float]]
```

Same as `judge_score_delta_series`, but for `system_score_delta`.

**Synchronous.** Does not mutate `verdicts`.

---

#### `compute_judge_reliability`

```python
def compute_judge_reliability(
    verdicts: list[AttributionVerdict],
    *,
    calibration_errors: list[dict[str, float]] | None = None,
    drift_rate_warning: float = DEFAULT_JUDGE_DRIFT_RATE_WARNING,
) -> JudgeReliabilityMetrics
```

**Purpose**

Aggregates a window of `AttributionVerdict`s into a `JudgeReliabilityMetrics` summary.

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `verdicts` | `list[AttributionVerdict]` | Yes | — | Must be non-empty and share exactly one `anchor_set_id`. |
| `calibration_errors` | `list[dict[str, float]] \| None` | No (keyword-only) | `None` | Optional list of calibration-error dicts (for example, from `nirizan.metrics.statistical_gating.calibrate_gold_set`). Entries without an `"mae"` key are silently skipped. |
| `drift_rate_warning` | `float` | No (keyword-only) | `DEFAULT_JUDGE_DRIFT_RATE_WARNING` (`0.10`) | Threshold above which `status` is `UNSTABLE`. |

**Return value:** a `JudgeReliabilityMetrics`. See the field table above for exactly how each field is derived.

**Exceptions:**

- `ValueError` — if `verdicts` is empty.
- `ValueError` — if `verdicts` contains more than one distinct `anchor_set_id`. NiriZan's anchor sets are fixed and versioned (a change creates a new `anchor_set_id` rather than editing an existing one in place), so mixing anchor sets in one summary would blend results from two different rulers.

**Synchronous.** Logs at `WARNING` if the resulting status is `UNSTABLE`, `INFO` otherwise.

---

### `nirizan.reporting.dashboard`

Canonical import:

```python
from nirizan.reporting.dashboard import DashboardSnapshot, assemble_dashboard_snapshot
```

#### `DashboardSnapshot`

**Purpose**

Assembled reporting data for one `system_type` at one point in time. Data only; this snapshot is not rendered directly. It is intended to be the single underlying signal set behind three views: a dashboard, a Judge Reliability Panel, and Drift & Regression Reports, rather than three independently computed views.

**Model config:** `strict=True`. Not frozen.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `generated_at` | `datetime` | Yes | — | When this snapshot was assembled. |
| `system_type` | `str` | Yes | — | Which system type this snapshot describes. |
| `health_score` | `float` | Yes | — | Constrained to `[0.0, 100.0]`. |
| `latest_attribution` | `AttributionVerdict \| None` | No | `None` | The most recent (by `evaluated_at`) attribution verdict considered, if any were supplied. |
| `judge_reliability` | `JudgeReliabilityMetrics \| None` | No | `None` | Set only if attribution verdicts were supplied and aggregation succeeded. |
| `regression_verdicts` | `list[RegressionVerdict]` | No | `[]` | Passed through from the caller. |
| `gate_verdict` | `GateVerdict \| None` | No | `None` | Passed through from the caller. |

---

#### `assemble_dashboard_snapshot`

```python
def assemble_dashboard_snapshot(
    *,
    system_type: str,
    quality_score: float,
    confidence: float,
    attribution_verdicts: list[AttributionVerdict] | None = None,
    regression_verdicts: list[RegressionVerdict] | None = None,
    gate_verdict: GateVerdict | None = None,
    calibration_errors: list[dict[str, float]] | None = None,
) -> DashboardSnapshot
```

**Purpose**

Combines a health score, judge reliability aggregation, and regression/gate output into one `DashboardSnapshot`.

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `system_type` | `str` | Yes (keyword-only) | — | Stamped onto the returned snapshot. |
| `quality_score` | `float` | Yes (keyword-only) | — | Passed directly into `compute_system_health_score`; not derived or looked up by this function. |
| `confidence` | `float` | Yes (keyword-only) | — | Same. |
| `attribution_verdicts` | `list[AttributionVerdict] \| None` | No (keyword-only) | `None` | Should be pre-fetched by the caller; this function does not query storage itself. |
| `regression_verdicts` | `list[RegressionVerdict] \| None` | No (keyword-only) | `None` | Passed through to the snapshot unchanged (`[]` if `None`). |
| `gate_verdict` | `GateVerdict \| None` | No (keyword-only) | `None` | Passed through to the snapshot unchanged. |
| `calibration_errors` | `list[dict[str, float]] \| None` | No (keyword-only) | `None` | Forwarded to `compute_judge_reliability` if `attribution_verdicts` is non-empty. |

**Return value:** a `DashboardSnapshot`. See [Assembling a Dashboard Snapshot](#assembling-a-dashboard-snapshot) for the full logic behind `latest_attribution`, `judge_reliability`, and the health-score fallback when `attribution_verdicts` is empty or omitted.

**Exceptions:** does not raise on a `ValueError` from `compute_judge_reliability` specifically (most likely caused by mixed `anchor_set_id`s in `attribution_verdicts`); that case is caught internally, logged as a warning, and the snapshot is returned with `judge_reliability=None`. Any other exception, including from `compute_system_health_score` (which itself does not raise) or from constructing the `DashboardSnapshot` model (a Pydantic `ValidationError`, for example if `health_score` ends up outside `[0.0, 100.0]`), propagates normally.

**Synchronous.** Does not persist the returned snapshot; no storage layer is called from here. Logs at `INFO` on completion, `WARNING` if judge reliability aggregation was skipped due to a caught `ValueError`.

---

### `nirizan.trust.anchor_set`

Canonical import:

```python
from nirizan.trust.anchor_set import AnchorItem, AnchorSet
```

#### `AnchorItem`

**Purpose**

One item in a fixed, human-labeled anchor set: a known input, its expected output, and a human-assigned label.

**Model config:** `strict=True`. Not frozen.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `anchor_id` | `str` | Yes | — | Identifier for this item within its anchor set. |
| `input_payload` | `str` | Yes | — | The fixed input text. |
| `expected_output` | `str` | Yes | — | The fixed expected output text. |
| `human_label` | `float` | Yes | — | Human-assigned score, constrained to `[0.0, 1.0]`. Not a boolean pass/fail flag. |

---

#### `AnchorSet`

**Purpose**

A versioned, human-labeled reference set: a fixed group of `AnchorItem`s, rescored repeatedly over time so that a change in score reveals judge behavior rather than production system behavior.

**Model config:** `strict=True`. Not frozen.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `anchor_set_id` | `str` | Yes | — | Identifier for this version of the anchor set. |
| `items` | `list[AnchorItem]` | Yes | — | Constrained to a minimum length of 1. |
| `created_at` | `datetime` | Yes | — | When this anchor set was created. |

**Validation:** constructing an `AnchorSet` with `items=[]` raises a Pydantic `ValidationError`.

**Note:** this model does not enforce the convention that an anchor set update creates a new `anchor_set_id` rather than editing in place. See [Anchor Sets](#anchor-sets) for the full explanation; this is currently a call-site discipline, not something `AnchorSet` itself checks or prevents.

---

### `nirizan.trust.attribution`

Canonical import:

```python
from nirizan.trust.attribution import DriftAttribution, AttributionVerdict, AttributionEngine
```

#### `DriftAttribution`

**Purpose**

Three-state enum identifying the outcome of a drift-attribution analysis.

**Values**

| Member | Value |
|---|---|
| `DriftAttribution.NONE` | `"none"` |
| `DriftAttribution.SYSTEM_DRIFT` | `"system_drift"` |
| `DriftAttribution.JUDGE_DRIFT` | `"judge_drift"` |

Subclasses both `str` and `Enum`. These three members are used by `compute_system_health_score`'s multiplier table and `compute_judge_reliability`'s rate arithmetic; this table is the authoritative definition.

---

#### `AttributionVerdict`

**Purpose**

The result of one drift-attribution analysis: which of the three states was decided, the deltas behind that decision, and a human-readable explanation.

**Model config:** `strict=True`. Not frozen.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `attribution` | `DriftAttribution` | Yes | — | The decided verdict. |
| `anchor_set_id` | `str` | Yes | — | Which anchor set this analysis used. |
| `system_score_delta` | `float` | Yes | — | `mean(prod_candidate_scores) - mean(prod_baseline_scores)`. Not constrained to any range; can be positive, negative, or (in principle) `nan` if empty score lists were passed to `AttributionEngine.analyze`. |
| `judge_score_delta` | `float` | Yes | — | `mean(anchor_rescored_scores) - mean(anchor_ref_scores)`. Same caveats as `system_score_delta`. |
| `evaluated_at` | `datetime` | Yes | — | When this analysis was run. |
| `explanation` | `str` | Yes | — | Human-readable summary of which condition matched and the relevant delta. |

**Note on always-populated deltas:** both delta fields are always set by `AttributionEngine.analyze`, regardless of which verdict was reached; this is what lets `nirizan.reporting.judge_reliability.judge_score_delta_series` and `system_score_delta_series` (covered earlier) plot a continuous series across every verdict, not just the ones flagged as drift.

---

#### `AttributionEngine`

**Purpose**

Compares anchor-set rescoring against production score movement and produces an `AttributionVerdict`.

**Import**

```python
from nirizan.trust.attribution import AttributionEngine
```

**Signature**

```python
AttributionEngine(significance_threshold: float = 0.05)
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `significance_threshold` | `float` | No | `0.05` | The minimum absolute mean-difference (on the same `[0.0, 1.0]`-normalized score scale used throughout NiriZan's metrics) required to call a delta meaningful. Not validated by the constructor; any float, including a negative one, is accepted without error. |

**Attributes**

| Attribute | Type | Meaning |
|---|---|---|
| `significance_threshold` | `float` | As passed to the constructor. |

##### `analyze`

```python
def analyze(
    self,
    anchor_set_id: str,
    anchor_ref_scores: list[float],
    anchor_rescored_scores: list[float],
    prod_baseline_scores: list[float],
    prod_candidate_scores: list[float],
) -> AttributionVerdict
```

**Parameters**

| Name | Type | Required | Meaning |
|---|---|---|---|
| `anchor_set_id` | `str` | Yes | Stamped onto the resulting `AttributionVerdict`. Not cross-checked against any actual `AnchorSet` object; this method does not require or accept an `AnchorSet` instance at all, only plain score lists. |
| `anchor_ref_scores` | `list[float]` | Yes | The judge's historical scores on the anchor set. |
| `anchor_rescored_scores` | `list[float]` | Yes | The judge's scores on the same anchor set, rescored now. |
| `prod_baseline_scores` | `list[float]` | Yes | Production scores from the baseline run. |
| `prod_candidate_scores` | `list[float]` | Yes | Production scores from the candidate run. |

**Decision logic:** see [Judge-Drift Attribution](#judge-drift-attribution) for the full three-step explanation (judge drift checked first and in either direction; system drift checked second and only for a decrease; otherwise `NONE`).

**Return value:** an `AttributionVerdict` with both delta fields always populated, `attribution` set per the decision logic, and a generated `explanation` string.

**Exceptions:** none raised directly by `analyze`. This method computes `np.mean(...)` on each input list without first validating that it's non-empty; an empty list produces a NumPy `RuntimeWarning` and a `nan` result rather than a `ValueError`, and that `nan` will propagate into the resulting `AttributionVerdict`'s delta fields and into the comparisons that decide `attribution`.

**Synchronous.** No I/O, no logging, no persistence. Does not mutate any of its list arguments.

**Important:** despite the parameter name `significance_threshold` and the word "statistically" appearing in generated `explanation` text, this is a fixed-threshold comparison of raw means, not a statistical hypothesis test. See the callout in [Judge-Drift Attribution](#judge-drift-attribution).

---

### `nirizan.storage.models`

Canonical import:

```python
from nirizan.storage.models import SpanRecord, TraceRecord, Run, Baseline
```

#### `SpanRecord`

**Purpose**

Database record representation of a `Span`: a pure serialization shell with `str`-typed fields, used internally by `SQLiteTraceRepository`.

**Model config:** none set (default Pydantic behavior; not `strict`, unlike most other models in this manual).

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `span_id` | `str` | Yes | — | String form of the span's `UUID`. |
| `trace_id` | `str` | Yes | — | String form of the owning trace's `UUID`. |
| `parent_span_id` | `str \| None` | No | `None` | String form of the parent span's `UUID`, if any. |
| `kind` | `str` | Yes | — | String form of the span's `SpanKind` value. |
| `name` | `str` | Yes | — | As on the domain `Span`. |
| `started_at` | `str` | Yes | — | ISO 8601 string (`datetime.isoformat()`). |
| `ended_at` | `str` | Yes | — | ISO 8601 string. |
| `attributes_json` | `str` | No | `"{}"` | The span's `attributes` dict, pre-serialized to a JSON string. |
| `input_payload` | `str \| None` | No | `None` | As on the domain `Span`. |
| `output_payload` | `str \| None` | No | `None` | As on the domain `Span`. |

##### `from_span` (classmethod)

```python
@classmethod
def from_span(cls, span: Span) -> "SpanRecord"
```

Converts a domain `Span` (from `nirizan.instrumentation.spans`) into a `SpanRecord`. **Synchronous.**

##### `to_span`

```python
def to_span(self) -> Span
```

The inverse of `from_span`: reconstructs a domain `Span` from this record. **Synchronous.**

---

#### `TraceRecord`

**Purpose**

Database record representation of a complete `Trace`, including its nested `SpanRecord`s.

**Model config:** none set (not `strict`).

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `trace_id` | `str` | Yes | — | String form of the trace's `UUID`. |
| `application_name` | `str` | Yes | — | As on the domain `Trace`. |
| `created_at` | `str` | Yes | — | ISO 8601 string. |
| `spans` | `list[SpanRecord]` | No | `[]` | The trace's spans, each as a `SpanRecord`. |
| `code_commit` | `str \| None` | No | `None` | As on the domain `Trace`. |
| `data_snapshot_id` | `str \| None` | No | `None` | As on the domain `Trace`. |
| `session_id` | `str \| None` | No | `None` | String form of the session's `UUID`, if any. |

##### `from_trace` (classmethod)

```python
@classmethod
def from_trace(cls, trace: Trace) -> "TraceRecord"
```

Converts a domain `Trace` into a `TraceRecord`, recursively converting every span via `SpanRecord.from_span`. **Synchronous.**

##### `to_trace`

```python
def to_trace(self) -> Trace
```

The inverse of `from_trace`. **Synchronous.**

---

#### `Run`

**Purpose**

A trace plus the `MetricResult`s computed against it, versioned by code commit and data snapshot. This is the model `nirizan.orchestrator.scheduler.RunScheduler.run_on_demand` constructs and persists (see [Scheduling Evaluation Runs](#scheduling-evaluation-runs)).

**Model config:** `strict=True`. Not frozen.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `run_id` | `UUID` | Yes | — | Unique identifier for this run. |
| `trace_id` | `UUID` | Yes | — | The trace this run evaluated. |
| `code_commit` | `str` | Yes | — | Constrained to 7-40 characters, the range spanning a short to a full git SHA. Not validated to actually look like a SHA, only checked for length. |
| `data_snapshot_id` | `str` | Yes | — | Constrained to a minimum of 1 character. |
| `metric_results` | `list[MetricResult]` | No | `[]` | The `MetricResult`s (from `nirizan.metrics.base`) computed for this run. |
| `created_at` | `datetime` | Yes | — | When this run was created. |

**Validation note:** `RunScheduler.run_on_demand`'s placeholder versioning values, `code_commit="phase2-unversioned"` (19 characters) and `data_snapshot_id="unversioned"`, both satisfy these length constraints, but only because they happen to be long enough; neither is validated as resembling an actual commit SHA or snapshot identifier. See [Storage Models](#storage-models).

---

#### `Baseline`

**Purpose**

A named, queryable set of "known good" historical runs, referenced by id rather than embedded.

**Model config:** `strict=True`. Not frozen.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `baseline_id` | `UUID` | Yes | — | Unique identifier for this baseline. |
| `system_type` | `str` | Yes | — | Which system type this baseline applies to. |
| `run_ids` | `list[UUID]` | Yes | — | Constrained to a minimum length of 1. The runs that make up this baseline, by id only; `Run` objects themselves are not embedded. |
| `established_at` | `datetime` | Yes | — | When this baseline was established. |
| `label` | `str` | Yes | — | Constrained to a minimum of 1 character. A human-readable name, e.g. `"pre-v0.3-release"`. |

**Validation:** constructing a `Baseline` with `run_ids=[]` raises a Pydantic `ValidationError`.

---

### `nirizan.storage.trace_repository`

Canonical import:

```python
from nirizan.storage.trace_repository import BaseTraceRepository, SQLiteTraceRepository
```

#### `BaseTraceRepository`

**Purpose**

Abstract storage interface (an `ABC`, not a `Protocol`) for persisting, querying, and managing traces. Operates on the domain `Trace` at its public boundary; `TraceRecord`/`SpanRecord` are internal to a concrete implementation and never cross this interface.

**Extension contract:** subclass and implement all four abstract methods:

```python
async def save(self, trace: Trace) -> None: ...
async def get(self, trace_id: UUID) -> Optional[Trace]: ...
async def list_by_application(self, application_name: str, limit: int = 100, offset: int = 0) -> list[Trace]: ...
async def purge_older_than(self, created_before_iso: str) -> int: ...
```

| Method | Contract |
|---|---|
| `save(trace)` | Persist a `Trace` and its child spans. |
| `get(trace_id)` | Retrieve by id. Must return `None` if not found, never raise for a missing trace. |
| `list_by_application(application_name, limit=100, offset=0)` | Paginated retrieval filtered by application name. |
| `purge_older_than(created_before_iso)` | Delete traces (and their spans) created before the given ISO timestamp; return the count deleted. |

`BaseTraceRepository` satisfies `TraceSink` (`nirizan.orchestrator.collector`) and `TraceSource` (`nirizan.orchestrator.scheduler`) by shape, since its `save`/`list_by_application` signatures match what those Protocols require.

---

#### `SQLiteTraceRepository`

**Purpose**

The one concrete `BaseTraceRepository` implementation provided: async SQLite persistence with indexes, pagination, and a purge capability.

**Import**

```python
from nirizan.storage.trace_repository import SQLiteTraceRepository
```

**Signature**

```python
SQLiteTraceRepository(db_path: str = "nirizan_traces.db")
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `db_path` | `str` | No | `"nirizan_traces.db"` | Path to the SQLite database file. Created (with schema) if it doesn't already exist. |

**Attributes**

| Attribute | Type | Meaning |
|---|---|---|
| `db_path` | `str` | As passed to the constructor. |

**Schema:** two tables, `traces` and `spans`, with `spans.trace_id` foreign-keyed to `traces.trace_id` with `ON DELETE CASCADE` (`PRAGMA foreign_keys = ON` is set on the connection). Indexes: `(application_name, created_at DESC)` on `traces`; `trace_id` alone and `(kind, started_at DESC)` on `spans`.

##### `save`

```python
async def save(self, trace: Trace) -> None
```

Upserts (`INSERT OR REPLACE`) the trace row and every span row, in one transaction. Replacing an existing `trace_id` does not orphan its old spans, since the cascading foreign key deletes them as part of the `REPLACE`.

**Async** (via `asyncio.to_thread`; `sqlite3` itself is synchronous).

##### `get`

```python
async def get(self, trace_id: UUID) -> Optional[Trace]
```

Returns the full `Trace` with spans ordered by `started_at` ascending, or `None` if not found. Never raises for a missing trace.

**Async.**

##### `list_by_application`

```python
async def list_by_application(
    self,
    application_name: str,
    limit: int = 100,
    offset: int = 0,
) -> list[Trace]
```

Returns matching traces, newest first (`created_at DESC`), with standard SQL `LIMIT`/`OFFSET` pagination. This is the method `nirizan.orchestrator.scheduler.RunScheduler` expects from a `TraceSource`; `SQLiteTraceRepository` satisfies that shape.

**Async.**

##### `purge_older_than`

```python
async def purge_older_than(self, created_before_iso: str) -> int
```

Deletes every trace (and, via cascade, its spans) with `created_at` earlier than `created_before_iso`, returning the number of trace rows deleted.

**The comparison is a plain SQL string comparison** (`WHERE created_at < ?` against text columns), not a parsed datetime comparison. This only produces correct results if every stored `created_at` uses a consistent, sortable ISO 8601 format (which `TraceRecord.from_trace` does produce) and the string you pass matches that format; a differently formatted timestamp string will not raise, it will silently produce an incorrect result.

**Async.**

##### `close`

```python
def close(self) -> None
```

Closes the underlying SQLite connection.

**Synchronous**, unlike every other method on this class.

**Concurrency note:** every database operation, including one-time schema initialization at construction, runs through `asyncio.to_thread` against a single `sqlite3.Connection` created with `check_same_thread=False`. This keeps a single process's event loop unblocked; it adds no cross-process or cross-connection concurrency guarantee beyond what SQLite itself provides.

---

### `nirizan.storage.run_repository`

Canonical import:

```python
from nirizan.storage.run_repository import RunRepository, InMemoryRunRepository
```

#### `RunRepository`

**Purpose**

A `typing.Protocol` for minimal, additive `Run` persistence, described in its own docstring as narrower than `ExperimentStore`.

**Required shape**

```python
class RunRepository(Protocol):
    async def save_run(self, run: Run) -> None: ...
    async def get_run(self, run_id: UUID) -> Optional[Run]: ...
```

---

#### `InMemoryRunRepository`

**Purpose**

A plain, dict-backed `RunRepository` implementation, with no persistence across process restarts.

**Signature**

```python
InMemoryRunRepository()
```

Takes no arguments.

##### `save_run`

```python
async def save_run(self, run: Run) -> None
```

Stores `run` in an internal `dict[UUID, Run]`, keyed by `run.run_id`. Overwrites any existing entry with the same `run_id`. **Async.** No I/O; the `async` signature exists to satisfy the `RunRepository`/`RunSink` shape, not because this implementation performs any actual asynchronous work.

##### `get_run`

```python
async def get_run(self, run_id: UUID) -> Optional[Run]
```

Returns the stored `Run`, or `None` if `run_id` isn't present. Never raises for a missing id. **Async.**

**Note:** `InMemoryRunRepository` also satisfies `RunSink` from `nirizan.orchestrator.scheduler` (see [Scheduling Evaluation Runs](#scheduling-evaluation-runs)), since `RunSink` only requires `save_run`.

---

### `nirizan.storage.baselines`

Canonical import:

```python
from nirizan.storage.baselines import BaselineRepository, SQLiteBaselineRepository
```

#### `BaselineRepository`

**Purpose**

A `typing.Protocol` for `Baseline` persistence.

**Required shape**

```python
class BaselineRepository(Protocol):
    async def save_baseline(self, baseline: Baseline) -> None: ...
    async def get_baseline(self, baseline_id: UUID) -> Optional[Baseline]: ...
    async def list_baselines(self, system_type: str) -> list[Baseline]: ...
```

---

#### `SQLiteBaselineRepository`

**Purpose**

SQLite-backed `BaselineRepository` implementation. Stores `run_ids` as a single JSON text column, not a relational junction table, per the class's own docstring.

**Import**

```python
from nirizan.storage.baselines import SQLiteBaselineRepository
```

**Signature**

```python
SQLiteBaselineRepository(db_path: str = "nirizan_baselines.db")
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `db_path` | `str` | No | `"nirizan_baselines.db"` | Path to the SQLite database file. |

**Schema:** one table, `baselines` (`baseline_id` primary key, `system_type`, `run_ids_json`, `established_at`, `label`), with an index on `system_type`.

##### `save_baseline`

```python
async def save_baseline(self, baseline: Baseline) -> None
```

Upserts (`INSERT OR REPLACE`) by `baseline_id`. `run_ids` is JSON-encoded (a list of stringified UUIDs) into `run_ids_json`. **Async** (via `asyncio.to_thread`).

##### `get_baseline`

```python
async def get_baseline(self, baseline_id: UUID) -> Optional[Baseline]
```

Returns the matching `Baseline`, or `None` if not found. **Async.**

##### `list_baselines`

```python
async def list_baselines(self, system_type: str) -> list[Baseline]
```

Returns every `Baseline` for `system_type`, ordered `established_at DESC` (newest first). **Async.**

##### `close`

```python
def close(self) -> None
```

Closes the underlying SQLite connection. **Synchronous.**

**Note:** there is no SQL-level foreign key from a baseline's `run_ids` to any `runs` table, and `SQLiteBaselineRepository` uses a separate database file from a `Run`-persisting repository like `SQLiteExperimentStore` by default, so there is no enforced referential integrity between a `Baseline`'s `run_ids` and any actual stored `Run` rows.

---

### `nirizan.storage.session_repository`

Canonical import:

```python
from nirizan.storage.session_repository import SessionRepository, InMemorySessionRepository
```

#### `SessionRepository`

**Purpose**

A `typing.Protocol` for minimal `Session` persistence.

**Required shape**

```python
class SessionRepository(Protocol):
    async def save_session(self, session: Session) -> None: ...
    async def get_session(self, session_id: UUID) -> Optional[Session]: ...
```

`Session` here is `nirizan.instrumentation.sessions.Session` (see [Sessions](#sessions)).

---

#### `InMemorySessionRepository`

**Purpose**

A plain, dict-backed `SessionRepository` implementation. The only `SessionRepository` implementation among the modules reviewed in this manual; there is no SQLite-backed equivalent.

**Signature**

```python
InMemorySessionRepository()
```

Takes no arguments.

##### `save_session`

```python
async def save_session(self, session: Session) -> None
```

Stores `session` in an internal `dict[UUID, Session]`, keyed by `session.session_id`. **Async.**

##### `get_session`

```python
async def get_session(self, session_id: UUID) -> Optional[Session]
```

Returns the stored `Session`, or `None` if not found. Never raises for a missing id. **Async.**

---

### `nirizan.storage.experiment_store`

Canonical import:

```python
from nirizan.storage.experiment_store import RunDiff, ExperimentStore, SQLiteExperimentStore
```

#### `RunDiff`

**Purpose**

A structured, purely computational difference between two runs' metric scores. Per its own docstring, it "computes only, never judges whether it's a regression" — no severity, no significance test, no connection to `nirizan.regression`.

**Model config:** `strict=True`. Not frozen.

**Fields**

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `run_a` | `UUID` | Yes | — | The first run compared. |
| `run_b` | `UUID` | Yes | — | The second run compared. |
| `metric_deltas` | `dict[str, float]` | Yes | — | Maps each metric name present in **both** runs to `score_b - score_a`. A metric name present in only one run is silently excluded, not included as a partial entry. |

---

#### `ExperimentStore`

**Purpose**

A `typing.Protocol`, broader than `RunRepository`, adding a `diff` capability for comparing two runs directly.

**Required shape**

```python
class ExperimentStore(Protocol):
    async def record_run(self, run: Run) -> None: ...
    async def get_run(self, run_id: UUID) -> Optional[Run]: ...
    async def diff(self, run_a: UUID, run_b: UUID) -> RunDiff: ...
```

**Note the method name difference from `RunRepository`:** this Protocol's save method is named `record_run`, not `save_run`. `ExperimentStore` and `RunRepository` are declared as separate Protocols, not one extending the other; a concrete class satisfying one does not automatically satisfy the other, and `SQLiteExperimentStore` (below) and `InMemoryRunRepository` are entirely separate classes with entirely separate storage. Saving a `Run` through one does not make it visible through the other.

---

#### `SQLiteExperimentStore`

**Purpose**

SQLite-backed `ExperimentStore` implementation. Stores `metric_results` as a single JSON text column, not a relational table of individual metric rows.

**Import**

```python
from nirizan.storage.experiment_store import SQLiteExperimentStore
```

**Signature**

```python
SQLiteExperimentStore(db_path: str = "nirizan_experiments.db")
```

**Parameters**

| Name | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `db_path` | `str` | No | `"nirizan_experiments.db"` | Path to the SQLite database file. |

**Schema:** one table, `runs` (`run_id` primary key, `trace_id`, `code_commit`, `data_snapshot_id`, `metric_results_json`, `created_at`), with indexes on `trace_id` and `code_commit`.

##### `record_run`

```python
async def record_run(self, run: Run) -> None
```

Upserts (`INSERT OR REPLACE`) by `run_id`. `metric_results` is serialized to JSON via `[m.model_dump(mode="json") for m in run.metric_results]`. **Async** (via `asyncio.to_thread`).

##### `get_run`

```python
async def get_run(self, run_id: UUID) -> Optional[Run]
```

Returns the matching `Run`, or `None` if not found.

**Deserialization detail:** each stored metric result is parsed back via `MetricResult.model_validate(m, strict=False)`, explicitly overriding `MetricResult`'s own `strict=True` model config for this read path. This is a deliberate relaxation to tolerate the kind of type differences a JSON round-trip can introduce, which strict mode would otherwise reject.

**Async.**

##### `diff`

```python
async def diff(self, run_a: UUID, run_b: UUID) -> RunDiff
```

Fetches both runs internally via `get_run`, computes `metric_deltas` over the intersection of their metric names (see [`RunDiff`](#rundiff)), and returns the result.

**Exceptions:** `ValueError` if either `run_a` or `run_b` does not resolve to a stored `Run`. This is one of the few methods in the storage layer that raises on a missing id rather than returning `None`, since a diff of a nonexistent run has no meaningful fallback result.

**Async.**

##### `close`

```python
def close(self) -> None
```

Closes the underlying SQLite connection. **Synchronous.**

---

# End of User Manual

<div align="center">
Rahman, R. NiriZan (Version 0.1.0) [Computer software]. https://github.com/Red1-Rahman/NiriZan
</div>
