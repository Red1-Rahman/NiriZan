# tests/instrumentation/test_sdk.py
import logging

import pytest

from nirizan.instrumentation.exporters import InMemoryExporter
from nirizan.instrumentation.sdk import (
    generation,
    get_tracer,
    init_tracer,
    planning,
    retrieval,
    start_session,
    tool_use,
    trace_span,
)
from nirizan.instrumentation.spans import SpanKind


@pytest.mark.asyncio
async def test_sdk_decorator_nested_tracing() -> None:
    exporter = InMemoryExporter()
    init_tracer(application_name="sdk_app", exporter=exporter)

    @trace_span(kind=SpanKind.RETRIEVAL, name="db_fetch")
    async def fetch_data(query: str) -> str:
        return f"result for {query}"

    @trace_span(kind=SpanKind.GENERATION, name="llm_gen")
    async def generate_text(prompt: str) -> str:
        return "generated text"

    @trace_span(kind=SpanKind.PLANNING, name="pipeline")
    async def run_pipeline(user_query: str) -> str:
        data = await fetch_data(user_query)
        return await generate_text(data)

    result = await run_pipeline("hello")
    assert result == "generated text"

    traces = exporter.get_traces()
    assert len(traces) == 1
    trace = traces[0]

    assert len(trace.spans) == 3
    names = {s.name for s in trace.spans}
    assert names == {"pipeline", "db_fetch", "llm_gen"}


@pytest.mark.asyncio
async def test_sdk_convenience_decorators_and_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    exporter = InMemoryExporter()
    with caplog.at_level(logging.INFO):
        init_tracer(application_name="convenience_app", exporter=exporter)

    assert "Initialized global tracer for application 'convenience_app'" in caplog.text

    @planning(name="plan_step")
    async def do_plan(q: str) -> str:
        return f"plan: {q}"

    @retrieval()
    async def fetch(doc_id: str) -> str:
        return f"doc: {doc_id}"

    @tool_use()
    async def calc(expr: str) -> str:
        return "42"

    @generation()
    async def generate(prompt: str) -> str:
        return "final answer"

    async with start_session() as session_id:
        p = await do_plan("how to test")
        r = await fetch("doc123")
        t = await calc("1+1")
        g = await generate(prompt=p)

    assert g == "final answer"
    traces = exporter.get_traces()
    assert len(traces) == 4

    kinds = [t.spans[0].kind for t in traces]
    assert kinds == [
        SpanKind.PLANNING,
        SpanKind.RETRIEVAL,
        SpanKind.TOOL_USE,
        SpanKind.GENERATION,
    ]

    for trace in traces:
        assert trace.session_id == session_id
        span = trace.spans[0]
        assert span.input_payload is not None
