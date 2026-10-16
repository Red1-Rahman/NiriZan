# tests/instrumentation/otel/test_conversion_roundtrip_isolation.py
"""L6 isolation layer: NiriZan -> OTel -> NiriZan round-trip fidelity.

The two adapters must be inverses of each other on the data the pipeline
actually carries: a NiriZan ``Trace`` exported into OpenTelemetry and then
ingested back by ``NiriZanSpanProcessor`` must come out as the same trace
shape, with identity, span kinds, parent links, and payloads preserved.
If the two halves drift (an attribute one side writes and the other stops
reading), traces silently degrade as they cross the bridge.

Requires the optional ``otel`` extra; deselect with ``-m "not otel"``.
"""

import pytest

pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.sdk")

import random  # noqa: E402
from datetime import UTC, datetime, timedelta, timezone  # noqa: E402
from typing import Any  # noqa: E402
from uuid import uuid4  # noqa: E402

from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter as OTelInMemoryExporter,
)

from nirizan.instrumentation.otel.from_otel import NiriZanSpanProcessor  # noqa: E402
from nirizan.instrumentation.otel.semconv import (  # noqa: E402
    CONTENT_ATTRIBUTE_KEYS,
    MAX_ATTR_VALUE_LENGTH,
    TRUNCATION_SUFFIX,
)
from nirizan.instrumentation.otel.to_otel import (  # noqa: E402
    OTelExporterConfig,
    export_trace_to_otel,
)
from nirizan.instrumentation.spans import (  # noqa: E402
    SYNTHETIC_PARENT_ATTRIBUTE,
    Span,
    SpanKind,
    Trace,
)

pytestmark = pytest.mark.otel

START = datetime(2026, 1, 1, tzinfo=UTC)


class RecordingSink:
    def __init__(self) -> None:
        self.traces: list[Trace] = []

    def enqueue_trace(self, trace: Trace) -> None:
        self.traces.append(trace)


def make_trace() -> Trace:
    """A parent/child trace with distinct start instants.

    The two spans start one second apart, which is what real nested spans
    look like: assembly orders spans by start time, so distinct starts make
    the resulting order independent of the random OTel span ids the SDK
    mints on every export.
    """
    trace_id = uuid4()
    root_id = uuid4()
    child_id = uuid4()
    return Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        session_id=uuid4(),
        spans=[
            Span(
                span_id=root_id,
                trace_id=trace_id,
                parent_span_id=None,
                kind=SpanKind.PLANNING,
                name="plan",
                started_at=START,
                ended_at=START + timedelta(milliseconds=500),
                input_payload="plan the thing",
            ),
            Span(
                span_id=child_id,
                trace_id=trace_id,
                parent_span_id=root_id,
                kind=SpanKind.RETRIEVAL,
                name="retrieve",
                started_at=START + timedelta(seconds=1),
                ended_at=START + timedelta(seconds=1, milliseconds=500),
                attributes={"retrieval.top_k": 3},
            ),
        ],
    )


def roundtrip(trace: Trace, sink: RecordingSink) -> None:
    """Export ``trace`` into a real OTel pipeline and ingest it back."""
    provider = TracerProvider()
    trusted = frozenset({trace.session_id}) if trace.session_id else frozenset()
    processor = NiriZanSpanProcessor(
        sink,
        trust_stashed_ids=True,
        trusted_session_ids=trusted,
        capture_content=True,
    )
    provider.add_span_processor(processor)
    provider.add_span_processor(SimpleSpanProcessor(OTelInMemoryExporter()))
    tracer = provider.get_tracer("l6-roundtrip")

    export_trace_to_otel(
        trace,
        tracer,
        config=OTelExporterConfig(capture_content=True),
    )
    assert processor.force_flush(timeout_millis=5_000) is True
    provider.shutdown()


def test_roundtrip_preserves_span_names_and_count() -> None:
    sink = RecordingSink()

    roundtrip(make_trace(), sink)

    assert len(sink.traces) == 1
    assert sorted(s.name for s in sink.traces[0].spans) == ["plan", "retrieve"]


def test_roundtrip_preserves_parent_links() -> None:
    sink = RecordingSink()

    roundtrip(make_trace(), sink)

    by_name = {s.name: s for s in sink.traces[0].spans}
    assert by_name["retrieve"].parent_span_id == by_name["plan"].span_id


def test_roundtrip_preserves_span_kinds() -> None:
    sink = RecordingSink()

    roundtrip(make_trace(), sink)

    by_name = {s.name: s for s in sink.traces[0].spans}
    assert by_name["plan"].kind == SpanKind.PLANNING
    assert by_name["retrieve"].kind == SpanKind.RETRIEVAL


def test_roundtrip_recovers_the_stashed_nirizan_trace_id() -> None:
    """The exported trace_id is derived; the stashed id must win when trusted."""
    trace = make_trace()
    sink = RecordingSink()

    roundtrip(trace, sink)

    assert sink.traces[0].trace_id == trace.trace_id


def test_roundtrip_recovers_the_stashed_session_id() -> None:
    trace = make_trace()
    sink = RecordingSink()

    roundtrip(trace, sink)

    assert sink.traces[0].session_id == trace.session_id


def test_roundtrip_preserves_payloads_when_capture_is_enabled() -> None:
    trace = make_trace()
    sink = RecordingSink()

    roundtrip(trace, sink)

    by_name = {s.name: s for s in sink.traces[0].spans}
    assert by_name["plan"].input_payload == "plan the thing"


def test_roundtrip_withholds_payloads_by_default() -> None:
    """The default config captures no content: payloads stay empty end to end."""
    trace = make_trace()
    sink = RecordingSink()
    provider = TracerProvider()
    processor = NiriZanSpanProcessor(sink)  # default config: capture_content=False
    provider.add_span_processor(processor)
    tracer = provider.get_tracer("l6-default")

    export_trace_to_otel(trace, tracer)
    assert processor.force_flush(timeout_millis=5_000) is True
    provider.shutdown()

    assert len(sink.traces) == 1
    by_name = {s.name: s for s in sink.traces[0].spans}
    assert by_name["plan"].input_payload is None


def test_roundtrip_preserves_scalar_attributes() -> None:
    trace = make_trace()
    sink = RecordingSink()

    roundtrip(trace, sink)

    by_name = {s.name: s for s in sink.traces[0].spans}
    assert by_name["retrieve"].attributes["retrieval.top_k"] == 3


def test_roundtrip_of_a_single_span_trace() -> None:
    trace_id = uuid4()
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                parent_span_id=None,
                kind=SpanKind.GENERATION,
                name="only",
                started_at=START,
                ended_at=START,
            )
        ],
    )
    sink = RecordingSink()

    roundtrip(trace, sink)

    assert len(sink.traces) == 1
    assert [s.name for s in sink.traces[0].spans] == ["only"]


def test_roundtrip_is_deterministic_across_repeats() -> None:
    """The same trace exported twice yields the same shape both times."""
    trace = make_trace()
    first, second = RecordingSink(), RecordingSink()

    roundtrip(trace, first)
    roundtrip(trace, second)

    assert [s.name for s in first.traces[0].spans] == [s.name for s in second.traces[0].spans]
    assert first.traces[0].trace_id == second.traces[0].trace_id


# ---------------------------------------------------------------------------
# Shape fidelity: the structures a real pipeline produces
# ---------------------------------------------------------------------------


def roundtrip_configured(
    trace: Trace,
    *,
    exporter_config: OTelExporterConfig | None = None,
    trust_stashed_ids: bool = True,
    capture_content: bool = True,
    trusted_session_ids: frozenset[Any] | None = None,
) -> RecordingSink:
    """Round trip ``trace`` with explicit configs on both sides of the bridge."""
    sink = RecordingSink()
    provider = TracerProvider()
    processor = NiriZanSpanProcessor(
        sink,
        trust_stashed_ids=trust_stashed_ids,
        trusted_session_ids=(
            trusted_session_ids
            if trusted_session_ids is not None
            else (frozenset({trace.session_id}) if trace.session_id else frozenset())
        ),
        capture_content=capture_content,
    )
    provider.add_span_processor(processor)
    provider.add_span_processor(SimpleSpanProcessor(OTelInMemoryExporter()))
    tracer = provider.get_tracer("l6-configured")

    export_trace_to_otel(
        trace,
        tracer,
        config=exporter_config or OTelExporterConfig(capture_content=capture_content),
    )
    assert processor.force_flush(timeout_millis=30_000) is True
    provider.shutdown()

    return sink


def single_trace(result: RecordingSink) -> Trace:
    """Assert exactly one trace arrived and return it."""
    assert len(result.traces) == 1
    return result.traces[0]


def by_name(trace: Trace) -> dict[str, Span]:
    return {span.name: span for span in trace.spans}


def parent_name_of(trace: Trace, span: Span) -> str | None:
    """The name of a span's parent, or ``None`` for a root or a dangling link."""
    if span.parent_span_id is None:
        return None
    for candidate in trace.spans:
        if candidate.span_id == span.parent_span_id:
            return candidate.name
    return "<outside-trace>"


def test_roundtrip_preserves_a_two_hundred_deep_chain() -> None:
    """A 200-span chain survives both hops without losing a parent link."""
    depth = 200
    trace_id = uuid4()
    spans: list[Span] = []
    previous: Any = None
    for index in range(depth):
        started = START + timedelta(milliseconds=index)
        spans.append(
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                parent_span_id=previous,
                kind=SpanKind.GENERATION,
                name=f"depth-{index:03d}",
                started_at=started,
                ended_at=started + timedelta(milliseconds=1),
            )
        )
        previous = spans[-1].span_id
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=spans,
    )

    result = single_trace(roundtrip_configured(trace))

    assert len(result.spans) == depth
    by_span_id = {span.span_id: span for span in result.spans}
    assert parent_name_of(result, by_span_id[spans[0].span_id]) is None
    for index in range(1, depth):
        assert parent_name_of(result, by_span_id[spans[index].span_id]) == (
            f"depth-{index - 1:03d}"
        )


def test_roundtrip_preserves_a_fan_out_under_one_parent() -> None:
    """One parent with many children keeps every child under that parent."""
    trace_id = uuid4()
    root_id = uuid4()
    children = 25
    spans = [
        Span(
            span_id=root_id,
            trace_id=trace_id,
            kind=SpanKind.PLANNING,
            name="fanout-root",
            started_at=START,
            ended_at=START + timedelta(seconds=children),
        )
    ]
    for index in range(children):
        started = START + timedelta(milliseconds=index)
        spans.append(
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                parent_span_id=root_id,
                kind=SpanKind.RETRIEVAL,
                name=f"child-{index:02d}",
                started_at=started,
                ended_at=started + timedelta(milliseconds=1),
            )
        )
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=spans,
    )

    result = single_trace(roundtrip_configured(trace))

    assert len(result.spans) == children + 1
    names = by_name(result)
    assert parent_name_of(result, names["fanout-root"]) is None
    for index in range(children):
        assert parent_name_of(result, names[f"child-{index:02d}"]) == "fanout-root"


def test_roundtrip_keeps_several_roots_in_one_trace() -> None:
    """A multi-root trace comes back as one trace with the same number of roots."""
    trace_id = uuid4()
    spans = [
        Span(
            span_id=uuid4(),
            trace_id=trace_id,
            kind=SpanKind.PLANNING,
            name=f"root-{index}",
            started_at=START + timedelta(seconds=index),
            ended_at=START + timedelta(seconds=index, milliseconds=500),
        )
        for index in range(3)
    ]
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=spans,
    )

    result = single_trace(roundtrip_configured(trace))

    assert len(result.spans) == 3
    assert sum(1 for span in result.spans if span.parent_span_id is None) == 3
    assert all(parent_name_of(result, span) is None for span in result.spans)


def test_roundtrip_turns_a_synthetic_parent_link_into_a_root() -> None:
    """Characterization: a synthetic dangling parent comes back as a root.

    The wire format cannot express "my parent is a NiriZan span that is not in
    this trace". The exporter anchors the span under a *remote* synthetic
    parent, and the documented ingest rule is that a span whose parent is
    remote becomes a root. So the link does not survive the round trip; what
    must survive is the marker itself, so a consumer can still tell that this
    span was orphaned upstream rather than genuinely a root.
    """
    trace_id = uuid4()
    orphan_parent_id = uuid4()
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                parent_span_id=orphan_parent_id,
                kind=SpanKind.GENERATION,
                name="orphan",
                started_at=START,
                ended_at=START + timedelta(seconds=1),
                attributes={SYNTHETIC_PARENT_ATTRIBUTE: True},
            )
        ],
    )

    result = single_trace(roundtrip_configured(trace))

    orphan = result.spans[0]
    assert orphan.name == "orphan"
    assert orphan.parent_span_id is None
    assert orphan.attributes[SYNTHETIC_PARENT_ATTRIBUTE] is True


@pytest.mark.parametrize("kind", list(SpanKind))
def test_roundtrip_preserves_every_span_kind(kind: SpanKind) -> None:
    """Every ``SpanKind`` crosses the bridge and comes back as the same kind."""
    trace_id = uuid4()
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=kind,
                name=f"kind-{kind.value}",
                started_at=START,
                ended_at=START + timedelta(seconds=1),
            )
        ],
    )

    result = single_trace(roundtrip_configured(trace))

    assert [span.kind for span in result.spans] == [kind]


# ---------------------------------------------------------------------------
# Value fidelity: the scalar shapes attributes can hold
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("flag_true", True),
        ("flag_false", False),
        ("count_zero", 0),
        ("ratio_zero", 0.0),
        ("text_empty", ""),
        ("text", "value"),
        ("number", 42),
        ("ratio", 1.5),
    ],
)
def test_roundtrip_keeps_scalar_attribute_types_and_values(
    key: str,
    value: bool | int | float | str,
) -> None:
    """Attribute scalars keep both their value and their Python type.

    ``bool`` matters most here: it is a subclass of ``int``, so an adapter that
    stringifies or int-casts attributes silently turns ``True`` into ``1``.
    """
    trace_id = uuid4()
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.GENERATION,
                name="scalars",
                started_at=START,
                ended_at=START + timedelta(seconds=1),
                attributes={key: value},
            )
        ],
    )

    result = single_trace(roundtrip_configured(trace))

    observed = result.spans[0].attributes[key]
    assert observed == value
    assert type(observed) is type(value)


def test_roundtrip_preserves_unicode_in_names_payloads_and_attributes() -> None:
    """Non-ASCII text is not mangled or escaped anywhere on the path."""
    trace_id = uuid4()
    text = "café über \U0001f680 日本語"
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.GENERATION,
                name=text,
                started_at=START,
                ended_at=START + timedelta(seconds=1),
                attributes={"note": text},
                input_payload=text,
                output_payload=text,
            )
        ],
    )

    result = single_trace(roundtrip_configured(trace))

    span = result.spans[0]
    assert span.name == text
    assert span.attributes["note"] == text
    assert span.input_payload == text
    assert span.output_payload == text


def test_roundtrip_distinguishes_an_absent_payload_from_an_empty_one() -> None:
    """``None`` and ``""`` are different facts and both must survive."""
    trace_id = uuid4()
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.GENERATION,
                name="with-empty",
                started_at=START,
                ended_at=START + timedelta(seconds=1),
                input_payload="",
            ),
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.GENERATION,
                name="without-payload",
                started_at=START,
                ended_at=START + timedelta(seconds=1),
            ),
        ],
    )

    result = single_trace(roundtrip_configured(trace))

    names = by_name(result)
    assert names["with-empty"].input_payload == ""
    assert names["without-payload"].input_payload is None


def test_roundtrip_preserves_a_maximum_length_name() -> None:
    """A name at the model's 200-character limit is not clamped on the way back."""
    name = "n" * 200
    trace_id = uuid4()
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.GENERATION,
                name=name,
                started_at=START,
                ended_at=START + timedelta(seconds=1),
            )
        ],
    )

    result = single_trace(roundtrip_configured(trace))

    assert result.spans[0].name == name


def test_roundtrip_truncates_an_oversize_payload_at_the_attribute_limit() -> None:
    """An oversize payload is truncated at the limit, with the suffix appended.

    The OTel attribute limit is what bounds this, so the round trip cannot
    return the original text; what it must return is a value that is at most
    the limit long and clearly marked as truncated.
    """
    trace_id = uuid4()
    payload = "p" * (MAX_ATTR_VALUE_LENGTH + 500)
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.GENERATION,
                name="oversize",
                started_at=START,
                ended_at=START + timedelta(seconds=1),
                input_payload=payload,
            )
        ],
    )

    result = single_trace(roundtrip_configured(trace))

    observed = result.spans[0].input_payload
    assert observed is not None
    assert len(observed) <= MAX_ATTR_VALUE_LENGTH
    assert observed.endswith(TRUNCATION_SUFFIX)


def test_roundtrip_preserves_a_zero_duration() -> None:
    """A span that starts and ends at the same instant keeps a zero duration."""
    trace_id = uuid4()
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.GENERATION,
                name="instant",
                started_at=START,
                ended_at=START,
            )
        ],
    )

    result = single_trace(roundtrip_configured(trace))

    span = result.spans[0]
    assert span.started_at == span.ended_at == START
    assert (span.ended_at - span.started_at) == timedelta(0)


def test_roundtrip_preserves_microsecond_precision() -> None:
    """Sub-second precision survives both hops exactly, not just to the second."""
    trace_id = uuid4()
    started = START + timedelta(microseconds=123_456)
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=started,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.GENERATION,
                name="micros",
                started_at=started,
                ended_at=started + timedelta(microseconds=7),
            )
        ],
    )

    result = single_trace(roundtrip_configured(trace))

    span = result.spans[0]
    assert span.started_at == started
    assert span.ended_at == started + timedelta(microseconds=7)


@pytest.mark.parametrize(
    ("hours", "minutes"),
    [(6, 0), (5, 30)],
)
def test_roundtrip_normalizes_non_utc_input_offsets(hours: int, minutes: int) -> None:
    """An aware non-UTC timestamp comes back as the same instant in UTC."""
    trace_id = uuid4()
    local = START.astimezone(timezone(timedelta(hours=hours, minutes=minutes)))
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=local,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.GENERATION,
                name="offset",
                started_at=local,
                ended_at=local + timedelta(seconds=1),
            )
        ],
    )

    result = single_trace(roundtrip_configured(trace))

    span = result.spans[0]
    assert span.started_at == START
    assert span.started_at.utcoffset() == timedelta(0)
    assert span.ended_at == START + timedelta(seconds=1)


def test_roundtrip_with_untrusted_stashed_ids_derives_identity_deterministically() -> None:
    """With ``trust_stashed_ids=False`` identity is a namespaced derived id.

    The derived value is a pure function of the OpenTelemetry trace id, so two
    exports of the same trace agree with each other. It is *not* the original
    NiriZan trace id, because the OpenTelemetry trace id is chosen by the
    producer: reusing the exact inverse mapping would let an incoming trace
    claim a stored native trace's id. The original OpenTelemetry trace id is
    recorded on the spans so the derived id stays traceable, and the trusted
    path still round trips exactly.
    """
    trace = make_trace()
    trusted = single_trace(roundtrip_configured(trace, trust_stashed_ids=True))
    first = single_trace(roundtrip_configured(trace, trust_stashed_ids=False))
    second = single_trace(roundtrip_configured(trace, trust_stashed_ids=False))
    otel_trace_id = format(trace.trace_id.int, "032x")

    assert trusted.trace_id == trace.trace_id
    assert first.trace_id == second.trace_id
    assert first.trace_id != trace.trace_id
    assert first.trace_id != trusted.trace_id
    assert sorted(s.name for s in first.spans) == sorted(s.name for s in second.spans)
    assert trusted.spans[0].attributes["nirizan.trace_id.source"] == "roundtrip"
    assert first.spans[0].attributes["nirizan.trace_id.source"] == "derived"
    assert first.spans[0].attributes["nirizan.span_id.source"] == "derived"
    # The original OpenTelemetry trace id is kept for correlation.
    assert first.spans[0].attributes["otel.trace_id"] == otel_trace_id
    assert trusted.spans[0].attributes["otel.trace_id"] == otel_trace_id


def test_roundtrip_of_seeded_random_forests_preserves_every_parent_link() -> None:
    """Seeded random forests of more than 200 spans keep their exact shape.

    Each span's parent is recorded by name before the export and compared by
    name after the ingest, so the check is about structure rather than about the
    random identifiers the OTel SDK mints on every run.
    """
    span_count = 240
    rng = random.Random(20260101)
    trace_id = uuid4()
    span_ids = [uuid4() for _ in range(span_count)]
    expected_parent: dict[str, str | None] = {}
    spans: list[Span] = []
    for index, span_id in enumerate(span_ids):
        # Index 0 is the root; every later span attaches to an earlier one, so
        # the input is a forest of one tree plus whatever roots the shape has.
        parent_index = None if index == 0 else rng.randrange(index)
        parent_name = None if parent_index is None else f"node-{parent_index:03d}"
        expected_parent[f"node-{index:03d}"] = parent_name
        started = START + timedelta(milliseconds=index)
        spans.append(
            Span(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=None if parent_index is None else span_ids[parent_index],
                kind=SpanKind.GENERATION,
                name=f"node-{index:03d}",
                started_at=started,
                ended_at=started + timedelta(milliseconds=1),
            )
        )
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=spans,
    )

    result = single_trace(roundtrip_configured(trace))

    assert len(result.spans) == span_count
    roots = [span.name for span in result.spans if parent_name_of(result, span) is None]
    assert roots == ["node-000"]
    for span in result.spans:
        assert parent_name_of(result, span) == expected_parent[span.name]


# ---------------------------------------------------------------------------
# Privacy: what capture_content=False actually covers, in both directions
# ---------------------------------------------------------------------------


def test_capture_content_off_withholds_content_in_both_directions() -> None:
    """With capture off on both sides, no payload text reaches the sink.

    The export side drops the payload before it becomes an attribute and the
    ingest side drops any content attribute that arrives anyway, so the two
    settings are independent defenses rather than one redundant setting.
    """
    trace_id = uuid4()
    text = "a prompt that must not be captured"
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.RETRIEVAL,
                name="retrieval",
                started_at=START,
                ended_at=START + timedelta(seconds=1),
                input_payload=text,
                output_payload=text,
            )
        ],
    )

    result = single_trace(
        roundtrip_configured(
            trace,
            exporter_config=OTelExporterConfig(capture_content=False),
            capture_content=False,
        )
    )

    span = result.spans[0]
    assert span.input_payload is None
    assert span.output_payload is None
    for key in CONTENT_ATTRIBUTE_KEYS:
        assert key not in span.attributes
    assert text not in str(span.attributes)


def test_ingest_capture_off_drops_content_attributes_an_exporter_still_sent() -> None:
    """Ingest drops known content attributes even when the exporter sent them.

    This is the half of the privacy contract the exporter cannot control: a
    foreign OTel producer emitting ``gen_ai.prompt`` is still filtered on the
    way in, because the ingest default is capture off.
    """
    provider = TracerProvider()
    sink = RecordingSink()
    processor = NiriZanSpanProcessor(sink, capture_content=False)
    provider.add_span_processor(processor)
    tracer = provider.get_tracer("l6-foreign")
    content_key = sorted(CONTENT_ATTRIBUTE_KEYS)[0]
    text = "sensitive retrieved content"

    with tracer.start_as_current_span(
        "foreign-retrieval",
        attributes={
            "nirizan.span.kind": "retrieval",
            content_key: text,
            "custom.keep": "kept",
        },
    ):
        pass

    assert processor.force_flush(timeout_millis=30_000) is True
    provider.shutdown()

    result = single_trace(sink)
    assert content_key not in result.spans[0].attributes
    assert text not in str(result.spans[0].attributes)


def test_arbitrary_custom_attributes_pass_through_the_bridge() -> None:
    """Characterization: capture off withholds known content keys only.

    ``capture_content=False`` is a known-key allowlist, not a blanket filter.
    An attribute NiriZan does not own passes through unchanged even with
    capture off, which is what makes the setting predictable for callers who
    put their own keys on spans.
    """
    provider = TracerProvider()
    sink = RecordingSink()
    processor = NiriZanSpanProcessor(sink, capture_content=False)
    provider.add_span_processor(processor)
    tracer = provider.get_tracer("l6-foreign")
    custom = {"my.app.tenant": "acme", "my.app.shard": 7, "my.app.shadow": False}

    with tracer.start_as_current_span(
        "foreign-generation",
        attributes={"nirizan.span.kind": "generation", **custom},
    ):
        pass

    assert processor.force_flush(timeout_millis=30_000) is True
    provider.shutdown()

    result = single_trace(sink)
    observed = result.spans[0].attributes
    for key, value in custom.items():
        assert observed[key] == value
        assert type(observed[key]) is type(value)
