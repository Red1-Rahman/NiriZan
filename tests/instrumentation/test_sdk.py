import pytest

from nirizan.instrumentation.exporters import InMemoryExporter
from nirizan.instrumentation.sdk import init_tracer, trace_span
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