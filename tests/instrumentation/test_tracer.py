import pytest

from nirizan.instrumentation.exporters import InMemoryExporter
from nirizan.instrumentation.spans import SpanKind
from nirizan.instrumentation.tracer import Tracer


@pytest.mark.asyncio
async def test_tracer_parent_child_linking() -> None:
    exporter = InMemoryExporter()
    tracer = Tracer(application_name="test_tracer_app", exporter=exporter)

    async with tracer.start_span("root_span", SpanKind.PLANNING) as root_handle:
        async with tracer.start_span("child_span_1", SpanKind.RETRIEVAL) as child1_handle:
            pass
        async with tracer.start_span("child_span_2", SpanKind.GENERATION) as child2_handle:
            pass

    traces = exporter.get_traces()
    assert len(traces) == 1
    trace = traces[0]
    assert len(trace.spans) == 3

    # Find root and child spans
    root_spans = [s for s in trace.spans if s.parent_span_id is None]
    child_spans = [s for s in trace.spans if s.parent_span_id is not None]

    assert len(root_spans) == 1
    assert root_spans[0].span_id == root_handle.span_id
    assert len(child_spans) == 2

    for child in child_spans:
        assert child.parent_span_id == root_handle.span_id
        assert child.trace_id == trace.trace_id


@pytest.mark.asyncio
async def test_tracer_attributes_cleaning() -> None:
    exporter = InMemoryExporter()
    tracer = Tracer(application_name="clean_attrs_app", exporter=exporter)

    raw_attributes = {
        "str_val": "test",
        "int_val": 42,
        "bool_val": True,
        "complex_obj": [1, 2, 3],
    }

    async with tracer.start_span("attr_span", SpanKind.TOOL_USE, attributes=raw_attributes):
        pass

    trace = exporter.get_traces()[0]
    span = trace.spans[0]

    assert span.attributes["str_val"] == "test"
    assert span.attributes["int_val"] == 42
    assert span.attributes["bool_val"] is True
    assert span.attributes["complex_obj"] == "[1, 2, 3]"
