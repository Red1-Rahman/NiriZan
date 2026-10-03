# tests/instrumentation/otel/test_from_otel.py
"""Tests for the OTel -> NiriZan span processor (``from_otel.py``).

Strategy
--------
* **Real OTel objects, not mocks.** Spans are real ``ReadableSpan`` instances
  and the integration tests use a real ``TracerProvider``. Mocks would only
  check that the code calls what the code calls; real objects check that it
  works with what OpenTelemetry actually produces.
* **Deterministic state-machine tests.** Anything that depends on time or on
  thread scheduling (idle flush, maximum age, buffer cap, flush rules, dropped
  markers) runs against an *inert* processor: one that was constructed and then
  shut down, so its consumer thread is gone and the test drives the internals
  synchronously with a fake clock. No sleeps, no races.
* **A small number of live-thread tests** cover what only a running consumer
  can show: end-to-end delivery, ``force_flush`` semantics, back-pressure,
  resilience to sink and consumer errors, concurrency, and fork safety.
  They synchronize with ``force_flush`` or events, never with ``sleep``.
* **Oracles over examples where it pays off.** Parent resolution is checked
  against a deliberately naive reference implementation on randomized forests
  (seeded, so failures reproduce).

Categories that do not apply here: persistence and schema migration (the
processor stores nothing), authentication and authorization.
"""

import pytest

# ``opentelemetry`` is an optional dependency installed via the ``otel`` extra.
# Skip this entire module if it is absent, so a contributor working on other
# parts of NiriZan is never forced to install OpenTelemetry to get a green
# build. CI installs ``nirizan[otel]`` in the job that actually exercises
# the bridge.
pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.sdk")

import itertools  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import threading  # noqa: E402
from collections.abc import Callable, Iterator  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from functools import lru_cache  # noqa: E402
from typing import Any  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402
from uuid import UUID, uuid4  # noqa: E402

from opentelemetry import trace as otel_trace  # noqa: E402
from opentelemetry.sdk.resources import Resource  # noqa: E402
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider  # noqa: E402
from opentelemetry.sdk.util.instrumentation import InstrumentationScope  # noqa: E402
from opentelemetry.trace import (  # noqa: E402
    NonRecordingSpan,
    SpanContext,
    TraceFlags,
    TraceState,
)
from opentelemetry.trace.status import Status, StatusCode  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from nirizan.instrumentation.otel import from_otel  # noqa: E402
from nirizan.instrumentation.otel._id_mapping import (  # noqa: E402
    otel_span_id_to_uuid,
    otel_trace_id_to_uuid,
)
from nirizan.instrumentation.otel.from_otel import (  # noqa: E402
    _MAX_SPAN_NAME_LENGTH,
    NiriZanSpanProcessor,
    ProcessorConfig,
    StatReason,
    _convert_attributes,
    _extract_nirizan_span_id,
    _extract_nirizan_trace_id,
    _extract_payloads,
    _has_conflicting_trace_ids,
    _infer_span_kind,
    _int_or_zero,
    _ns_to_datetime,
    _parse_stashed_uuid,
    _resolve_parents,
    _scope_name,
    _start_key,
    _TraceBuffer,
)
from nirizan.instrumentation.otel.semconv import (  # noqa: E402
    GEN_AI_COMPLETION,
    GEN_AI_PROMPT,
    ID_SOURCE_DERIVED,
    ID_SOURCE_ROUNDTRIP,
    MAX_ATTR_VALUE_LENGTH,
    NIRIZAN_INSTRUMENTATION_SCOPE,
    NIRIZAN_PLANNING_CONTEXT,
    NIRIZAN_PLANNING_OUTPUT,
    NIRIZAN_RETRIEVAL_QUERY,
    NIRIZAN_RETRIEVAL_RESULTS,
    NIRIZAN_SESSION_ID,
    NIRIZAN_SPAN_ID,
    NIRIZAN_SPAN_ID_SOURCE,
    NIRIZAN_SPAN_KIND,
    NIRIZAN_TOOL_ARGUMENTS,
    NIRIZAN_TOOL_RESULT,
    NIRIZAN_TRACE_ID,
    NIRIZAN_TRACE_ID_SOURCE,
    OTEL_SAMPLED,
    OTEL_SPAN_ID,
    OTEL_STATUS_CODE,
    OTEL_STATUS_DESCRIPTION,
    OTEL_TRACE_STATE,
    SEQ_ATTR_PREFIX,
    SPAN_ID_SOURCE_DERIVED,
    SPAN_ID_SOURCE_ROUNDTRIP,
)
from nirizan.instrumentation.spans import Span, SpanKind, Trace  # noqa: E402

_MODULE_LOGGER = "nirizan.instrumentation.otel.from_otel"

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

TRACE_ID = 0x1234567890ABCDEF1234567890ABCDEF
OTHER_TRACE_ID = 0x0FEDCBA0987654321FEDCBA098765432
T0 = 1_600_000_000_000_000_000  # an arbitrary epoch-nanosecond start
SECOND = 1_000_000_000

_ALL_STAT_REASONS = {
    "invalid_span_context",
    "invalid_trace_id",
    "invalid_span_id",
    "late_arrival",
    "duplicate_span_id",
    "duplicate_nirizan_span_id",
    "conflicting_trace_id",
    "unrecognized_kind",
    "orphan_parent_missing",
    "orphan_emitted",
    "cycle_broken",
    "conversion_error",
    "queue_full",
    "own_scope_skipped",
    "evicted_open_trace",
    "trace_span_cap",
    "consumer_error",
}


@lru_cache(maxsize=None)
def _resource(service: str | None) -> Resource:
    """A resource with exactly the given ``service.name`` (or none at all)."""
    return Resource({"service.name": service} if service else {})


@lru_cache(maxsize=None)
def _scope(name: str) -> InstrumentationScope:
    return InstrumentationScope(name)


def make_span(
    span_id: int,
    *,
    trace_id: int = TRACE_ID,
    parent: int | None = None,
    remote_parent: bool = False,
    name: str | None = "span",
    start: int | None = None,
    end: int | None = None,
    attributes: dict[str, Any] | None = None,
    recognized: bool = True,
    service: str | None = "my-service",
    status: Status | None = None,
    scope: str = "tests",
    sampled: bool = True,
    trace_state: TraceState | None = None,
) -> ReadableSpan:
    """Build a real ``ReadableSpan``.

    Spans are "recognized" (assigned a NiriZan kind) by default through an
    explicit ``nirizan.span.kind`` attribute. Start times default to a value
    that increases with ``span_id`` so ordering is predictable.
    """
    attrs: dict[str, Any] = {NIRIZAN_SPAN_KIND: "generation"} if recognized else {}
    attrs.update(attributes or {})
    start_ns = T0 + span_id if start is None else start
    end_ns = start_ns + SECOND if end is None else end
    parent_ctx = (
        SpanContext(
            trace_id=trace_id,
            span_id=parent,
            is_remote=remote_parent,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        if parent is not None
        else None
    )
    return ReadableSpan(
        name=name,
        context=SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED if sampled else TraceFlags.DEFAULT),
            trace_state=trace_state or TraceState(),
        ),
        parent=parent_ctx,
        resource=_resource(service),
        attributes=attrs,
        status=status or Status(StatusCode.UNSET),
        start_time=start_ns,
        end_time=end_ns,
        instrumentation_scope=_scope(scope),
    )


def buffer_of(*spans: ReadableSpan, trace_id: int = TRACE_ID, now: float = 0.0) -> _TraceBuffer:
    buf = _TraceBuffer(trace_id, now)
    for span in spans:
        buf.add(span, now)
    return buf


class FakeClock:
    """A manually advanced monotonic clock."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class RecordingSink:
    """Thread-safe sink that records traces and can be told to fail."""

    def __init__(self) -> None:
        self.traces: list[Trace] = []
        self.raise_on_enqueue = False
        self._lock = threading.Lock()

    def enqueue_trace(self, trace: Trace) -> None:
        if self.raise_on_enqueue:
            raise RuntimeError("sink failure")
        with self._lock:
            self.traces.append(trace)


class BlockingSink(RecordingSink):
    """Sink that parks the consumer thread inside ``enqueue_trace`` until released."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def enqueue_trace(self, trace: Trace) -> None:
        self.entered.set()
        assert self.release.wait(timeout=10), "test never released the sink"
        super().enqueue_trace(trace)


def span_names(trace: Trace) -> list[str]:
    return [s.name for s in trace.spans]


def by_name(trace: Trace) -> dict[str, Span]:
    return {s.name: s for s in trace.spans}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sink() -> RecordingSink:
    return RecordingSink()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_processor(
    sink: RecordingSink, clock: FakeClock, request: pytest.FixtureRequest
) -> Callable[..., NiriZanSpanProcessor]:
    """Factory for *live* processors (consumer thread running), always shut down."""

    def factory(**kwargs: Any) -> NiriZanSpanProcessor:
        kwargs.setdefault("clock", clock)
        processor = NiriZanSpanProcessor(kwargs.pop("sink", sink), **kwargs)
        request.addfinalizer(processor.shutdown)
        return processor

    return factory


@pytest.fixture
def make_inert(
    sink: RecordingSink, clock: FakeClock
) -> Callable[..., NiriZanSpanProcessor]:
    """Factory for *inert* processors: built, then shut down.

    With the consumer thread gone, a test can call the internal methods
    (``_buffer_span``, ``_sweep_idle_traces``, ``_flush_quiescent``, ...)
    synchronously and deterministically, advancing ``clock`` by hand.
    """

    def factory(**kwargs: Any) -> NiriZanSpanProcessor:
        kwargs.setdefault("clock", clock)
        processor = NiriZanSpanProcessor(kwargs.pop("sink", sink), **kwargs)
        processor.shutdown()
        assert not processor._consumer.is_alive()
        return processor

    return factory


@pytest.fixture
def inert(make_inert: Callable[..., NiriZanSpanProcessor]) -> NiriZanSpanProcessor:
    return make_inert()


def consumer_threads() -> list[threading.Thread]:
    return [
        t
        for t in threading.enumerate()
        if t.name == "nirizan-otel-span-consumer" and t.is_alive()
    ]


# ===========================================================================
# StatReason
# ===========================================================================


def test_stat_reason_values_are_the_documented_counter_keys() -> None:
    """Operators read these keys from ``get_stats``; renaming one is a breaking change."""
    assert {reason.value for reason in StatReason} == _ALL_STAT_REASONS


def test_stat_reason_is_interchangeable_with_plain_string_keys(
    inert: NiriZanSpanProcessor,
) -> None:
    inert._record_stat(StatReason.LATE_ARRIVAL)
    inert._record_stat("late_arrival")

    assert inert.get_stats() == {"late_arrival": 2}
    assert inert.get_stats()[StatReason.LATE_ARRIVAL] == 2
    assert str(StatReason.LATE_ARRIVAL) == "late_arrival"


# ===========================================================================
# ProcessorConfig and constructor
# ===========================================================================


def test_config_defaults_match_documented_values() -> None:
    config = ProcessorConfig()

    assert config.idle_timeout_seconds == 5.0
    assert config.max_trace_age_seconds == 300.0
    assert config.max_buffered_traces == 1000
    assert config.max_queue_size == 50_000
    assert config.max_spans_per_trace == 10_000
    assert config.orphan_policy == "emit"
    assert config.unrecognized_span_policy == "drop"
    assert config.ignore_own_scope is True


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        pytest.param({"idle_timeout_seconds": 0}, "idle_timeout_seconds must be positive", id="idle-zero"),
        pytest.param({"idle_timeout_seconds": -1.0}, "idle_timeout_seconds must be positive", id="idle-negative"),
        pytest.param({"idle_timeout_seconds": float("nan")}, "idle_timeout_seconds must be positive", id="idle-nan"),
        pytest.param({"idle_timeout_seconds": float("inf")}, "idle_timeout_seconds must be positive", id="idle-inf"),
        pytest.param(
            {"idle_timeout_seconds": 5.0, "max_trace_age_seconds": 5.0},
            "max_trace_age_seconds must be greater than idle_timeout_seconds",
            id="age-equal-to-idle",
        ),
        pytest.param(
            {"idle_timeout_seconds": 5.0, "max_trace_age_seconds": 4.0},
            "max_trace_age_seconds must be greater than idle_timeout_seconds",
            id="age-below-idle",
        ),
        pytest.param({"max_trace_age_seconds": float("nan")}, "max_trace_age_seconds must be finite", id="age-nan"),
        pytest.param({"max_trace_age_seconds": float("inf")}, "max_trace_age_seconds must be finite", id="age-inf"),
        pytest.param({"max_buffered_traces": 0}, "max_buffered_traces must be at least 1", id="buffered-zero"),
        pytest.param({"max_queue_size": 0}, "max_queue_size must be at least 1", id="queue-zero"),
        pytest.param({"max_spans_per_trace": 0}, "max_spans_per_trace must be at least 1", id="spans-zero"),
        pytest.param({"orphan_policy": "bogus"}, "orphan_policy must be 'emit' or 'drop'", id="orphan-policy"),
        pytest.param(
            {"unrecognized_span_policy": "bogus"},
            "unrecognized_span_policy must be 'drop' or 'generation'",
            id="unrecognized-policy",
        ),
    ],
)
def test_config_rejects_invalid_values_with_a_message_naming_the_field(
    kwargs: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        ProcessorConfig(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_queue_size": True},
        {"max_buffered_traces": "10"},
        {"idle_timeout_seconds": "5"},
        {"ignore_own_scope": 1},
    ],
    ids=["bool-for-int", "str-for-int", "str-for-float", "int-for-bool"],
)
def test_config_is_strict_about_types(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ProcessorConfig(**kwargs)


def test_config_accepts_an_int_where_a_float_is_expected() -> None:
    assert ProcessorConfig(idle_timeout_seconds=1).idle_timeout_seconds == 1.0


def test_config_accepts_the_smallest_valid_values() -> None:
    config = ProcessorConfig(
        idle_timeout_seconds=0.001,
        max_trace_age_seconds=0.002,
        max_buffered_traces=1,
        max_queue_size=1,
        max_spans_per_trace=1,
    )
    assert config.max_buffered_traces == 1


def test_config_is_immutable() -> None:
    config = ProcessorConfig()
    with pytest.raises(ValidationError):
        config.max_queue_size = 5  # type: ignore[misc]


def test_processor_exposes_its_validated_config_and_round_trips_through_from_config(
    sink: RecordingSink, clock: FakeClock, request: pytest.FixtureRequest
) -> None:
    config = ProcessorConfig(max_buffered_traces=7, orphan_policy="drop", ignore_own_scope=False)

    processor = NiriZanSpanProcessor.from_config(sink, config, clock=clock)
    request.addfinalizer(processor.shutdown)

    assert processor.config == config


def test_processor_accepts_every_keyword_from_the_original_constructor(
    sink: RecordingSink, make_processor: Callable[..., NiriZanSpanProcessor]
) -> None:
    """Backward compatibility: the keyword-argument interface is unchanged."""
    processor = make_processor(
        idle_timeout_seconds=2.0,
        max_trace_age_seconds=20.0,
        max_buffered_traces=5,
        max_queue_size=100,
        orphan_policy="drop",
        unrecognized_span_policy="generation",
        clock=FakeClock(),
    )
    assert processor.config.orphan_policy == "drop"


def test_processor_rejects_unknown_keywords(sink: RecordingSink) -> None:
    with pytest.raises(TypeError):
        NiriZanSpanProcessor(sink, not_a_setting=1)  # type: ignore[call-arg]


def test_invalid_configuration_does_not_start_a_consumer_thread(sink: RecordingSink) -> None:
    before = len(consumer_threads())

    with pytest.raises(ValueError):
        NiriZanSpanProcessor(sink, max_queue_size=0)

    assert len(consumer_threads()) == before


def test_generation_policy_logs_a_warning(
    sink: RecordingSink,
    make_processor: Callable[..., NiriZanSpanProcessor],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger=_MODULE_LOGGER):
        make_processor(unrecognized_span_policy="generation")

    assert any("unrecognized_span_policy='generation'" in r.getMessage() for r in caplog.records)


def test_default_policy_does_not_log_a_warning(
    make_processor: Callable[..., NiriZanSpanProcessor],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger=_MODULE_LOGGER):
        make_processor()

    assert caplog.records == []


def test_consumer_thread_is_a_named_daemon(
    make_processor: Callable[..., NiriZanSpanProcessor],
) -> None:
    """A daemon thread cannot keep the interpreter alive after the application exits."""
    processor = make_processor()

    assert processor._consumer.daemon is True
    assert processor._consumer.name == "nirizan-otel-span-consumer"


# ===========================================================================
# Pure helpers
# ===========================================================================


def test_ns_to_datetime_converts_to_timezone_aware_utc_truncating_to_microseconds() -> None:
    result = _ns_to_datetime(1_600_000_000_123_456_789)

    assert result == datetime(2020, 9, 13, 12, 26, 40, 123_456, tzinfo=UTC)
    assert result.tzinfo == UTC


def test_ns_to_datetime_truncates_rather_than_rounds() -> None:
    assert _ns_to_datetime(999_999_999).microsecond == 999_999


def test_ns_to_datetime_handles_the_epoch() -> None:
    assert _ns_to_datetime(0) == datetime(1970, 1, 1, tzinfo=UTC)


def test_ns_to_datetime_substitutes_now_for_a_missing_timestamp() -> None:
    before = datetime.now(UTC)
    result = _ns_to_datetime(None)
    after = datetime.now(UTC)

    assert before <= result <= after


_SAMPLE_UUID = UUID("12345678-1234-5678-1234-567812345678")


@pytest.mark.parametrize(
    "raw",
    [
        "12345678-1234-5678-1234-567812345678",
        "12345678-1234-5678-1234-567812345678".upper(),
        "12345678123456781234567812345678",
        "urn:uuid:12345678-1234-5678-1234-567812345678",
        "{12345678-1234-5678-1234-567812345678}",
    ],
    ids=["canonical", "uppercase", "no-dashes", "urn", "braces"],
)
def test_parse_stashed_uuid_accepts_and_normalizes_the_formats_uuid_accepts(raw: str) -> None:
    assert _parse_stashed_uuid(raw) == _SAMPLE_UUID


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not-a-uuid",
        "12345678-1234-5678-1234-56781234567",
        "a" * 10_000,
        "00000000-0000-0000-0000-000000000000",
        None,
        123,
        b"12345678-1234-5678-1234-567812345678",
        _SAMPLE_UUID,
    ],
    ids=["empty", "garbage", "too-short", "huge", "nil", "none", "int", "bytes", "uuid-object"],
)
def test_parse_stashed_uuid_rejects_untrusted_values(raw: object) -> None:
    """Stashed ids come from span attributes, which any producer can set."""
    assert _parse_stashed_uuid(raw) is None


def _ctx_of(span: ReadableSpan) -> SpanContext:
    ctx = span.get_span_context()
    assert ctx is not None
    return ctx


def test_extract_span_id_recovers_a_stashed_id_as_roundtrip() -> None:
    span = make_span(0xAB, attributes={NIRIZAN_SPAN_ID: str(_SAMPLE_UUID)})

    assert _extract_nirizan_span_id(span, _ctx_of(span)) == (_SAMPLE_UUID, ID_SOURCE_ROUNDTRIP)


def test_extract_span_id_derives_an_id_when_nothing_is_stashed() -> None:
    span = make_span(0xAB)

    assert _extract_nirizan_span_id(span, _ctx_of(span)) == (
        otel_span_id_to_uuid(0xAB),
        ID_SOURCE_DERIVED,
    )


@pytest.mark.parametrize(
    "stashed",
    ["garbage", "00000000-0000-0000-0000-000000000000", 42, ""],
    ids=["garbage", "nil", "non-string", "empty"],
)
def test_extract_span_id_falls_back_to_derivation_for_unusable_stashes(stashed: object) -> None:
    span = make_span(0xAB, attributes={NIRIZAN_SPAN_ID: stashed})

    assert _extract_nirizan_span_id(span, _ctx_of(span)) == (
        otel_span_id_to_uuid(0xAB),
        ID_SOURCE_DERIVED,
    )


def test_extract_span_id_preserves_a_stashed_derived_provenance() -> None:
    """An id that was derived before export is still derived after re-ingest."""
    span = make_span(
        0xAB,
        attributes={NIRIZAN_SPAN_ID: str(_SAMPLE_UUID), NIRIZAN_SPAN_ID_SOURCE: ID_SOURCE_DERIVED},
    )

    assert _extract_nirizan_span_id(span, _ctx_of(span)) == (_SAMPLE_UUID, ID_SOURCE_DERIVED)


@pytest.mark.parametrize("prior", [ID_SOURCE_ROUNDTRIP, "bogus", None, 7])
def test_extract_span_id_treats_any_other_stashed_provenance_as_roundtrip(prior: object) -> None:
    span = make_span(
        0xAB,
        attributes={NIRIZAN_SPAN_ID: str(_SAMPLE_UUID), NIRIZAN_SPAN_ID_SOURCE: prior},
    )

    assert _extract_nirizan_span_id(span, _ctx_of(span))[1] == ID_SOURCE_ROUNDTRIP


def test_extract_trace_id_derives_from_the_otel_trace_id_by_default() -> None:
    spans = {1: make_span(1)}

    assert _extract_nirizan_trace_id(spans, TRACE_ID) == (
        otel_trace_id_to_uuid(TRACE_ID),
        ID_SOURCE_DERIVED,
    )


def test_extract_trace_id_recovers_a_stashed_id_even_if_only_one_span_has_it() -> None:
    spans = {
        1: make_span(1),
        2: make_span(2, attributes={NIRIZAN_TRACE_ID: str(_SAMPLE_UUID)}),
    }

    assert _extract_nirizan_trace_id(spans, TRACE_ID) == (_SAMPLE_UUID, ID_SOURCE_ROUNDTRIP)


def test_extract_trace_id_skips_unusable_stashes_and_uses_a_later_valid_one() -> None:
    spans = {
        1: make_span(1, attributes={NIRIZAN_TRACE_ID: "garbage"}),
        2: make_span(2, attributes={NIRIZAN_TRACE_ID: str(_SAMPLE_UUID)}),
    }

    assert _extract_nirizan_trace_id(spans, TRACE_ID)[0] == _SAMPLE_UUID


def test_extract_trace_id_resolves_conflicts_by_start_time_not_arrival_order() -> None:
    first = make_span(1, start=T0, attributes={NIRIZAN_TRACE_ID: str(UUID(int=1))})
    second = make_span(2, start=T0 + 10, attributes={NIRIZAN_TRACE_ID: str(UUID(int=2))})

    in_order = _extract_nirizan_trace_id({1: first, 2: second}, TRACE_ID)
    reversed_ = _extract_nirizan_trace_id({2: second, 1: first}, TRACE_ID)

    assert in_order == reversed_
    assert in_order[0] == UUID(int=1)


def test_extract_trace_id_preserves_a_stashed_derived_provenance() -> None:
    spans = {
        1: make_span(
            1,
            attributes={
                NIRIZAN_TRACE_ID: str(_SAMPLE_UUID),
                NIRIZAN_TRACE_ID_SOURCE: ID_SOURCE_DERIVED,
            },
        )
    }

    assert _extract_nirizan_trace_id(spans, TRACE_ID) == (_SAMPLE_UUID, ID_SOURCE_DERIVED)


@pytest.mark.parametrize(
    ("stashes", "expected"),
    [
        ([], False),
        ([str(UUID(int=1))], False),
        ([str(UUID(int=1)), str(UUID(int=1))], False),
        ([str(UUID(int=1)), str(UUID(int=2))], True),
        ([str(UUID(int=1)), "garbage"], False),
        ([str(UUID(int=1)), "00000000-0000-0000-0000-000000000000"], False),
    ],
    ids=["none", "one", "same-twice", "two-distinct", "one-invalid", "one-nil"],
)
def test_has_conflicting_trace_ids(stashes: list[str], expected: bool) -> None:
    spans = {
        i + 1: make_span(i + 1, attributes={NIRIZAN_TRACE_ID: stash})
        for i, stash in enumerate(stashes)
    }
    spans[99] = make_span(99)  # a span with no stash never counts

    assert _has_conflicting_trace_ids(spans) is expected


@pytest.mark.parametrize(
    ("attrs", "expected"),
    [
        ({NIRIZAN_SPAN_KIND: "generation"}, SpanKind.GENERATION),
        ({NIRIZAN_SPAN_KIND: "GENERATION"}, SpanKind.GENERATION),
        ({NIRIZAN_SPAN_KIND: "Planning"}, SpanKind.PLANNING),
        ({NIRIZAN_SPAN_KIND: "retrieval"}, SpanKind.RETRIEVAL),
        ({NIRIZAN_SPAN_KIND: "tool_use"}, SpanKind.TOOL_USE),
        ({NIRIZAN_SPAN_KIND: "nirizan.span.TOOL_USE"}, SpanKind.TOOL_USE),
        ({GEN_AI_PROMPT: "p"}, SpanKind.GENERATION),
        ({GEN_AI_COMPLETION: "c"}, SpanKind.GENERATION),
        ({NIRIZAN_RETRIEVAL_QUERY: "q"}, SpanKind.RETRIEVAL),
        ({NIRIZAN_RETRIEVAL_RESULTS: "r"}, SpanKind.RETRIEVAL),
        ({NIRIZAN_TOOL_ARGUMENTS: "{}"}, SpanKind.TOOL_USE),
        ({NIRIZAN_TOOL_RESULT: "{}"}, SpanKind.TOOL_USE),
        ({NIRIZAN_PLANNING_CONTEXT: "c"}, SpanKind.PLANNING),
        ({NIRIZAN_PLANNING_OUTPUT: "o"}, SpanKind.PLANNING),
        ({NIRIZAN_SPAN_KIND: "planning", GEN_AI_PROMPT: "p"}, SpanKind.PLANNING),
        ({GEN_AI_PROMPT: "p", NIRIZAN_RETRIEVAL_QUERY: "q"}, SpanKind.GENERATION),
        ({NIRIZAN_SPAN_KIND: "weird", GEN_AI_PROMPT: "p"}, SpanKind.GENERATION),
        ({NIRIZAN_SPAN_KIND: 123, NIRIZAN_RETRIEVAL_QUERY: "q"}, SpanKind.RETRIEVAL),
    ],
)
def test_infer_span_kind_recognizes_explicit_and_implicit_kinds(
    attrs: dict[str, Any], expected: SpanKind
) -> None:
    assert _infer_span_kind(attrs) is expected


@pytest.mark.parametrize(
    "attrs",
    [{}, {"http.method": "GET"}, {NIRIZAN_SPAN_KIND: "weird"}, {NIRIZAN_SPAN_KIND: "TOOL"}],
    ids=["empty", "unrelated", "unknown-explicit", "exporter-alias-not-a-kind"],
)
def test_infer_span_kind_returns_none_when_nothing_is_recognizable(attrs: dict[str, Any]) -> None:
    assert _infer_span_kind(attrs) is None


_PAYLOAD_KEYS: dict[SpanKind, tuple[str, str]] = {
    SpanKind.GENERATION: (GEN_AI_PROMPT, GEN_AI_COMPLETION),
    SpanKind.RETRIEVAL: (NIRIZAN_RETRIEVAL_QUERY, NIRIZAN_RETRIEVAL_RESULTS),
    SpanKind.TOOL_USE: (NIRIZAN_TOOL_ARGUMENTS, NIRIZAN_TOOL_RESULT),
    SpanKind.PLANNING: (NIRIZAN_PLANNING_CONTEXT, NIRIZAN_PLANNING_OUTPUT),
}


def test_payload_key_table_covers_every_span_kind() -> None:
    """Drift guard: adding a ``SpanKind`` must come with a payload mapping and a test."""
    assert set(_PAYLOAD_KEYS) == set(SpanKind)


@pytest.mark.parametrize("kind", list(SpanKind))
def test_extract_payloads_maps_each_kind_to_its_own_keys(kind: SpanKind) -> None:
    in_key, out_key = _PAYLOAD_KEYS[kind]

    assert _extract_payloads(kind, {in_key: "in", out_key: "out"}) == ("in", "out")
    assert _extract_payloads(kind, {in_key: "in"}) == ("in", None)
    assert _extract_payloads(kind, {out_key: "out"}) == (None, "out")
    assert _extract_payloads(kind, {}) == (None, None)


def test_extract_payloads_coerces_non_strings_and_ignores_other_kinds_keys() -> None:
    attrs = {GEN_AI_PROMPT: 42, NIRIZAN_RETRIEVAL_QUERY: "not mine"}

    assert _extract_payloads(SpanKind.GENERATION, attrs) == ("42", None)


def _convert(otel_attrs: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "service_name": None,
        "span_id_hex": None,
        "span_id_source": ID_SOURCE_DERIVED,
        "trace_id_source": ID_SOURCE_DERIVED,
        "sampled": None,
        "trace_state": None,
        "status_code": None,
        "status_description": None,
    }
    kwargs.update(overrides)
    return dict(_convert_attributes(otel_attrs, **kwargs))


def test_convert_attributes_preserves_scalar_types() -> None:
    result = _convert({"s": "v", "i": 3, "f": 1.5, "b": True, "z": 0, "e": ""})

    assert result["s"] == "v"
    assert result["i"] == 3 and isinstance(result["i"], int)
    assert result["f"] == 1.5
    assert result["b"] is True
    assert result["z"] == 0
    assert result["e"] == ""


def test_convert_attributes_skips_none_values() -> None:
    assert "n" not in _convert({"n": None})


@pytest.mark.parametrize("sequence", [["a", "b"], ("a", "b")], ids=["list", "tuple"])
def test_convert_attributes_encodes_sequences_under_the_reserved_prefix(
    sequence: Sequence[str] | list[str] | tuple[str, ...],
) -> None:
    result = _convert({"tags": sequence})

    assert "tags" not in result
    assert json.loads(result[f"{SEQ_ATTR_PREFIX}tags"]) == ["a", "b"]


def test_convert_attributes_does_not_double_prefix_an_already_prefixed_key() -> None:
    result = _convert({f"{SEQ_ATTR_PREFIX}tags": ["a"]})

    assert list(result)[0] == f"{SEQ_ATTR_PREFIX}tags"
    assert f"{SEQ_ATTR_PREFIX}{SEQ_ATTR_PREFIX}tags" not in result


def test_convert_attributes_keeps_non_ascii_sequence_items_unescaped() -> None:
    result = _convert({"words": ["বাংলা", "العربية"]})

    assert "\\u" not in result[f"{SEQ_ATTR_PREFIX}words"]
    assert json.loads(result[f"{SEQ_ATTR_PREFIX}words"]) == ["বাংলা", "العربية"]


def test_convert_attributes_stringifies_and_truncates_unsupported_types() -> None:
    class Odd:
        def __str__(self) -> str:
            return "odd-" + "x" * (MAX_ATTR_VALUE_LENGTH * 2)

    result = _convert({"odd": Odd(), "raw": b"bytes"})

    assert len(result["odd"]) == MAX_ATTR_VALUE_LENGTH
    assert result["odd"].endswith("...[truncated]")
    assert result["raw"] == "b'bytes'"


def test_convert_attributes_drops_a_sequence_that_cannot_be_encoded_and_keeps_the_rest(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def failing_encoder(_: Any) -> str:
        raise ValueError("cannot encode")

    monkeypatch.setattr(from_otel, "encode_sequence_attribute_value", failing_encoder)

    with caplog.at_level(logging.WARNING, logger=_MODULE_LOGGER):
        result = _convert({"tags": ["a"], "keep": "me"})

    assert result["keep"] == "me"
    assert not any(key.endswith("tags") for key in result)
    assert any("Dropping sequence attribute 'tags'" in r.getMessage() for r in caplog.records)


def test_convert_attributes_writes_all_metadata_when_present() -> None:
    result = _convert(
        {},
        service_name="svc",
        span_id_hex="00000000000000ab",
        span_id_source=ID_SOURCE_ROUNDTRIP,
        trace_id_source=ID_SOURCE_DERIVED,
        sampled=False,
        trace_state="vendor=x",
        status_code="error",
        status_description="boom",
    )

    assert result["otel.service.name"] == "svc"
    assert result[OTEL_SPAN_ID] == "00000000000000ab"
    assert result[NIRIZAN_SPAN_ID_SOURCE] == ID_SOURCE_ROUNDTRIP
    assert result[NIRIZAN_TRACE_ID_SOURCE] == ID_SOURCE_DERIVED
    assert result[OTEL_SAMPLED] is False
    assert result[OTEL_TRACE_STATE] == "vendor=x"
    assert result[OTEL_STATUS_CODE] == "error"
    assert result[OTEL_STATUS_DESCRIPTION] == "boom"


def test_convert_attributes_omits_absent_metadata_but_always_writes_provenance() -> None:
    result = _convert({})

    assert set(result) == {NIRIZAN_SPAN_ID_SOURCE, NIRIZAN_TRACE_ID_SOURCE}


def test_convert_attributes_cannot_be_spoofed_by_producer_supplied_metadata() -> None:
    """Provenance and captured OTel metadata are computed, never copied from the producer."""
    spoofed = {
        NIRIZAN_SPAN_ID_SOURCE: "spoofed",
        NIRIZAN_TRACE_ID_SOURCE: "spoofed",
        OTEL_SPAN_ID: "spoofed",
    }

    result = _convert(spoofed, span_id_hex="00000000000000ab")

    assert result[NIRIZAN_SPAN_ID_SOURCE] == ID_SOURCE_DERIVED
    assert result[NIRIZAN_TRACE_ID_SOURCE] == ID_SOURCE_DERIVED
    assert result[OTEL_SPAN_ID] == "00000000000000ab"


def test_convert_attributes_truncates_a_long_trace_state() -> None:
    result = _convert({}, trace_state="k=" + "v" * (MAX_ATTR_VALUE_LENGTH * 2))

    assert len(result[OTEL_TRACE_STATE]) == MAX_ATTR_VALUE_LENGTH


def test_convert_attributes_does_not_mutate_its_input() -> None:
    original = {"tags": ["a"], "n": None}
    snapshot = {"tags": ["a"], "n": None}

    _convert(original)

    assert original == snapshot


def test_scope_name_reads_the_scope_and_falls_back_to_the_deprecated_info() -> None:
    assert _scope_name(make_span(1, scope="my.lib")) == "my.lib"

    legacy = MagicMock(spec=["instrumentation_info"])
    legacy.instrumentation_info.name = "old.lib"
    assert _scope_name(legacy) == "old.lib"


@pytest.mark.parametrize("span", [object(), MagicMock(), MagicMock(spec=[])], ids=["bare", "mock", "empty-spec"])
def test_scope_name_is_none_when_the_name_is_unavailable_or_not_a_string(span: Any) -> None:
    assert _scope_name(span) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [(5, 5), (0, 0), (-3, -3), (True, 0), (False, 0), (None, 0), ("7", 0), (1.5, 0)],
)
def test_int_or_zero(value: object, expected: int) -> None:
    assert _int_or_zero(value) == expected


# ===========================================================================
# _TraceBuffer
# ===========================================================================


def test_trace_buffer_add_stores_by_otel_span_id_and_reports_duplicates() -> None:
    buf = _TraceBuffer(TRACE_ID, now=1.0)
    first = make_span(1, name="first")
    replacement = make_span(1, name="replacement")

    assert buf.add(first, now=2.0) is False
    assert buf.add(replacement, now=3.0) is True

    assert buf.spans[1] is replacement
    assert len(buf.spans) == 1
    assert buf.last_seen == 3.0
    assert buf.first_seen == 1.0


def test_trace_buffer_tracks_open_spans_and_never_goes_negative() -> None:
    buf = _TraceBuffer(TRACE_ID, now=0.0)

    buf.add(make_span(1), now=1.0)  # an end with no recorded start
    assert buf.open_spans == 0

    buf.mark_started(now=2.0)
    buf.mark_started(now=2.0)
    assert buf.open_spans == 2

    buf.add(make_span(2), now=3.0)
    assert buf.open_spans == 1
    buf.discard(now=4.0)
    assert buf.open_spans == 0
    buf.discard(now=5.0)
    assert buf.open_spans == 0
    assert buf.last_seen == 5.0


def test_trace_buffer_discard_does_not_store_a_span() -> None:
    buf = _TraceBuffer(TRACE_ID, now=0.0)
    buf.mark_started(now=1.0)

    buf.discard(now=2.0)

    assert buf.spans == {}
    assert buf.open_spans == 0


def test_trace_buffer_ignores_a_span_without_a_context() -> None:
    buf = _TraceBuffer(TRACE_ID, now=0.0)
    contextless = ReadableSpan(name="no-context", context=None)

    assert buf.add(contextless, now=1.0) is False
    assert buf.spans == {}


def test_trace_buffer_starts_with_trustworthy_accounting() -> None:
    buf = _TraceBuffer(TRACE_ID, now=0.0)

    assert (buf.open_spans, buf.has_untracked_start, buf.has_untracked_end, buf.cap_warned) == (
        0,
        False,
        False,
        False,
    )


def test_start_key_orders_by_start_time_then_span_id_and_tolerates_unknown_spans() -> None:
    buf = buffer_of(make_span(5, start=T0), make_span(3, start=T0), make_span(9, start=T0 - 1))

    assert sorted([5, 3, 9], key=lambda oid: _start_key(buf, oid)) == [9, 3, 5]
    assert _start_key(buf, 12345) == (0, 12345)


# ===========================================================================
# _resolve_parents
# ===========================================================================


def resolve(
    spans: list[ReadableSpan],
    *,
    kinds: set[int] | None = None,
    policy: str = "emit",
) -> from_otel._ParentResolution:
    buf = buffer_of(*spans)
    ids = {_ctx_of(s).span_id for s in spans} if kinds is None else kinds
    kind_map = dict.fromkeys(sorted(ids), SpanKind.GENERATION)
    return _resolve_parents(buf, kind_map, policy)  # type: ignore[arg-type]


def test_resolve_parents_single_root() -> None:
    result = resolve([make_span(1)])

    assert result.parent_of == {1: None}
    assert result.dropped == set() and result.synthetic_origin == {}


def test_resolve_parents_chain_links_each_span_to_its_parent() -> None:
    result = resolve([make_span(1), make_span(2, parent=1), make_span(3, parent=2)])

    assert result.parent_of == {1: None, 2: 1, 3: 2}


def test_resolve_parents_siblings_share_a_parent() -> None:
    result = resolve([make_span(1), make_span(2, parent=1), make_span(3, parent=1)])

    assert result.parent_of == {1: None, 2: 1, 3: 1}


@pytest.mark.parametrize("policy", ["emit", "drop"])
def test_resolve_parents_treats_an_absent_remote_parent_as_a_root_not_an_orphan(
    policy: str,
) -> None:
    """A parent in an upstream service is a trace boundary, not missing data."""
    result = resolve([make_span(2, parent=0xAAA, remote_parent=True)], policy=policy)

    assert result.parent_of == {2: None}
    assert result.dropped == set()
    assert result.synthetic_origin == {}


def test_resolve_parents_attaches_to_a_remote_parent_that_is_present_locally() -> None:
    result = resolve([make_span(1), make_span(2, parent=1, remote_parent=True)])

    assert result.parent_of == {1: None, 2: 1}


def test_resolve_parents_emit_policy_gives_an_orphan_a_synthetic_origin() -> None:
    result = resolve([make_span(2, parent=0xAAA)], policy="emit")

    assert result.parent_of == {2: 0xAAA}
    assert result.synthetic_origin == {2: 0xAAA}
    assert result.dropped == set()


def test_resolve_parents_drop_policy_drops_an_orphan_and_its_whole_subtree() -> None:
    spans = [
        make_span(2, parent=0xAAA),
        make_span(3, parent=2),
        make_span(4, parent=3),
        make_span(10),  # an unrelated root is unaffected
    ]

    result = resolve(spans, policy="drop")

    assert result.dropped == {2, 3, 4}
    assert result.parent_of == {10: None}


def test_resolve_parents_emit_policy_keeps_the_orphans_subtree_attached_to_it() -> None:
    result = resolve([make_span(2, parent=0xAAA), make_span(3, parent=2)], policy="emit")

    assert result.parent_of == {2: 0xAAA, 3: 2}
    assert result.synthetic_origin == {2: 0xAAA}


def test_resolve_parents_reattaches_children_across_a_skipped_span() -> None:
    spans = [make_span(1), make_span(2, parent=1), make_span(3, parent=2)]

    result = resolve(spans, kinds={1, 3})

    assert result.parent_of == {1: None, 3: 1}


def test_resolve_parents_promotes_a_child_to_root_when_every_ancestor_is_skipped() -> None:
    spans = [make_span(1), make_span(2, parent=1), make_span(3, parent=2)]

    result = resolve(spans, kinds={3})

    assert result.parent_of == {3: None}


def test_resolve_parents_looks_through_skipped_spans_to_a_missing_ancestor() -> None:
    spans = [make_span(2, parent=0xAAA), make_span(3, parent=2)]

    result = resolve(spans, kinds={3}, policy="emit")

    assert result.parent_of == {3: 0xAAA}
    assert result.synthetic_origin == {3: 0xAAA}


def test_resolve_parents_treats_an_invalid_parent_id_as_no_parent() -> None:
    result = resolve([make_span(2, parent=0)])

    assert result.parent_of == {2: None}


def test_resolve_parents_with_no_candidates_resolves_nothing() -> None:
    result = resolve([make_span(1), make_span(2, parent=1)], kinds=set())

    assert (result.parent_of, result.dropped, result.synthetic_origin) == ({}, set(), {})


def test_resolve_parents_breaks_a_two_span_cycle_with_exactly_one_root() -> None:
    result = resolve([make_span(1, parent=2), make_span(2, parent=1)])

    assert sorted(result.parent_of) == [1, 2]
    assert list(result.parent_of.values()).count(None) == 1
    assert result.cycles_broken == 1


def test_resolve_parents_breaks_a_self_parented_span() -> None:
    result = resolve([make_span(5, parent=5)])

    assert result.parent_of == {5: None}
    assert result.cycles_broken == 1


def test_resolve_parents_attaches_a_tail_that_feeds_into_a_cycle() -> None:
    result = resolve([make_span(1, parent=2), make_span(2, parent=3), make_span(3, parent=2), make_span(9, parent=1)])

    assert sorted(result.parent_of) == [1, 2, 3, 9]
    assert result.parent_of[9] == 1
    assert list(result.parent_of.values()).count(None) == 1
    assert result.cycles_broken == 1


@pytest.mark.parametrize("order", list(itertools.permutations([0, 1, 2])))
def test_resolve_parents_breaks_cycles_identically_for_every_arrival_order(
    order: tuple[int, ...],
) -> None:
    """Which span is promoted to root must not depend on the order spans arrived in."""
    spans = [make_span(1, parent=3), make_span(2, parent=1), make_span(3, parent=2)]

    result = resolve([spans[i] for i in order])
    baseline = resolve(spans)

    assert result.parent_of == baseline.parent_of


def test_resolve_parents_handles_chains_deeper_than_the_recursion_limit() -> None:
    """Regression: the walk used to be recursive and failed on ~1000-deep chains."""
    depth = 5_000
    spans = [make_span(1)] + [make_span(i, parent=i - 1) for i in range(2, depth + 1)]

    result = resolve(spans)

    assert result.parent_of[1] is None
    assert result.parent_of[depth] == depth - 1
    assert len(result.parent_of) == depth
    assert result.cycles_broken == 0


def _random_forest(rng: random.Random) -> tuple[list[ReadableSpan], set[int]]:
    """Random acyclic forest with missing, remote and skipped spans."""
    count = rng.randrange(1, 30)
    ids = list(range(1, count + 1))
    spans: list[ReadableSpan] = []
    for index, span_id in enumerate(ids):
        roll = rng.random()
        if roll < 0.20 or index == 0:
            spans.append(make_span(span_id))
        elif roll < 0.80:
            spans.append(make_span(span_id, parent=rng.choice(ids[:index])))
        elif roll < 0.90:
            spans.append(make_span(span_id, parent=1_000 + span_id))  # missing, local
        elif roll < 0.95:
            spans.append(make_span(span_id, parent=2_000 + span_id, remote_parent=True))
        else:
            spans.append(make_span(span_id, parent=rng.choice(ids[:index]), remote_parent=True))
    kinds = {span_id for span_id in ids if rng.random() < 0.7}
    return spans, kinds


def _reference_resolve(
    buf: _TraceBuffer, kinds: set[int], policy: str
) -> tuple[dict[int, int | None], set[int], dict[int, int]]:
    """A deliberately naive resolver: no memoization, plain recursion, acyclic input only."""

    def physical_parent(span_id: int) -> int | None:
        parent = buf.spans[span_id].parent
        if parent is None or parent.span_id == 0:
            return None
        if parent.is_remote and parent.span_id not in buf.spans:
            return None
        return parent.span_id

    def nearest(span_id: int) -> tuple[str, int | None]:
        current = physical_parent(span_id)
        while True:
            if current is None:
                return ("root", None)
            if current not in buf.spans:
                return ("missing", current)
            if current in kinds:
                return ("via", current)
            current = physical_parent(current)

    memo: dict[int, tuple[str, int | None]] = {}

    def state(span_id: int) -> tuple[str, int | None]:
        if span_id in memo:
            return memo[span_id]
        kind, target = nearest(span_id)
        if kind == "root":
            out: tuple[str, int | None] = ("root", None)
        elif kind == "missing":
            out = ("dropped", None) if policy == "drop" else ("synthetic", target)
        else:
            assert target is not None
            out = ("dropped", None) if state(target)[0] == "dropped" else ("attach", target)
        memo[span_id] = out
        return out

    parent_of: dict[int, int | None] = {}
    dropped: set[int] = set()
    synthetic: dict[int, int] = {}
    for span_id in kinds:
        kind, target = state(span_id)
        if kind == "dropped":
            dropped.add(span_id)
        elif kind == "synthetic":
            assert target is not None
            parent_of[span_id] = target
            synthetic[span_id] = target
        else:
            parent_of[span_id] = target
    return parent_of, dropped, synthetic


@pytest.mark.parametrize("policy", ["emit", "drop"])
def test_resolve_parents_matches_a_naive_reference_on_random_forests(policy: str) -> None:
    rng = random.Random(20260402)

    for _ in range(300):
        spans, kinds = _random_forest(rng)
        buf = buffer_of(*spans)
        kind_map = dict.fromkeys(sorted(kinds), SpanKind.GENERATION)

        actual = _resolve_parents(buf, kind_map, policy)  # type: ignore[arg-type]
        expected_parent_of, expected_dropped, expected_synthetic = _reference_resolve(
            buf, kinds, policy
        )

        assert actual.parent_of == expected_parent_of
        assert actual.dropped == expected_dropped
        assert actual.synthetic_origin == expected_synthetic
        assert actual.cycles_broken == 0


def test_resolve_parents_result_does_not_depend_on_insertion_order() -> None:
    rng = random.Random(7)

    for _ in range(100):
        spans, kinds = _random_forest(rng)
        shuffled = spans[:]
        rng.shuffle(shuffled)
        kind_map = dict.fromkeys(sorted(kinds), SpanKind.GENERATION)

        a = _resolve_parents(buffer_of(*spans), kind_map, "emit")  # type: ignore[arg-type]
        b = _resolve_parents(buffer_of(*shuffled), kind_map, "emit")  # type: ignore[arg-type]

        assert a.parent_of == b.parent_of
        assert a.dropped == b.dropped


# ===========================================================================
# Trace assembly (synchronous, via an inert processor)
# ===========================================================================


def assemble(
    processor: NiriZanSpanProcessor, *spans: ReadableSpan, trace_id: int = TRACE_ID
) -> Trace | None:
    return processor._assemble_trace(buffer_of(*spans, trace_id=trace_id))


def assemble_ok(
    processor: NiriZanSpanProcessor, *spans: ReadableSpan, trace_id: int = TRACE_ID
) -> Trace:
    result = assemble(processor, *spans, trace_id=trace_id)
    assert result is not None
    return result


def test_assembly_returns_none_for_an_empty_buffer(inert: NiriZanSpanProcessor) -> None:
    assert inert._assemble_trace(_TraceBuffer(TRACE_ID, 0.0)) is None


def test_assembly_of_one_span_produces_a_valid_trace(inert: NiriZanSpanProcessor) -> None:
    trace = assemble_ok(inert, make_span(0xAB, name="only"))

    assert isinstance(trace, Trace)
    assert trace.trace_id == otel_trace_id_to_uuid(TRACE_ID)
    assert span_names(trace) == ["only"]
    assert trace.spans[0].parent_span_id is None
    assert trace.created_at.tzinfo is not None


def test_assembly_upholds_the_trace_and_span_contracts(inert: NiriZanSpanProcessor) -> None:
    """Contracts from docs/contracts.md that the bridge must honor."""
    spans = [
        make_span(1),
        make_span(2, parent=1),
        make_span(3, parent=1),
        make_span(4, parent=0xAAA),  # orphan
    ]

    trace = assemble_ok(inert, *spans)

    assert all(s.trace_id == trace.trace_id for s in trace.spans)
    assert len({s.span_id for s in trace.spans}) == len(trace.spans)
    assert all(isinstance(v, (str, int, float, bool)) for s in trace.spans for v in s.attributes.values())
    assert trace.application_name
    with pytest.raises(ValidationError):
        trace.spans[0].name = "mutated"  # type: ignore[misc]  # Span is frozen


def test_assembly_orders_spans_by_start_time_then_span_id(inert: NiriZanSpanProcessor) -> None:
    trace = assemble_ok(
        inert,
        make_span(3, name="c", start=T0 + 5),
        make_span(1, name="a", start=T0 + 9),
        make_span(2, name="b", start=T0 + 5),
    )

    assert span_names(trace) == ["b", "c", "a"]


def test_assembly_links_parents_using_each_spans_nirizan_id(inert: NiriZanSpanProcessor) -> None:
    stashed = UUID("87654321-4321-8765-4321-876543218765")
    trace = assemble_ok(
        inert,
        make_span(1, name="root", attributes={NIRIZAN_SPAN_ID: str(stashed)}),
        make_span(2, name="child", parent=1),
    )

    spans = by_name(trace)
    assert spans["root"].span_id == stashed
    assert spans["child"].span_id == otel_span_id_to_uuid(2)
    assert spans["child"].parent_span_id == stashed


def test_assembly_reports_provenance_for_spans_and_the_trace(inert: NiriZanSpanProcessor) -> None:
    trace = assemble_ok(
        inert,
        make_span(1, name="stashed", attributes={NIRIZAN_SPAN_ID: str(uuid4())}),
        make_span(2, name="plain"),
    )

    spans = by_name(trace)
    assert spans["stashed"].attributes[NIRIZAN_SPAN_ID_SOURCE] == SPAN_ID_SOURCE_ROUNDTRIP
    assert spans["plain"].attributes[NIRIZAN_SPAN_ID_SOURCE] == SPAN_ID_SOURCE_DERIVED
    assert all(s.attributes[NIRIZAN_TRACE_ID_SOURCE] == ID_SOURCE_DERIVED for s in trace.spans)


def test_assembly_recovers_a_stashed_trace_id(inert: NiriZanSpanProcessor) -> None:
    stashed = uuid4()

    trace = assemble_ok(inert, make_span(1, attributes={NIRIZAN_TRACE_ID: str(stashed)}))

    assert trace.trace_id == stashed
    assert trace.spans[0].trace_id == stashed
    assert trace.spans[0].attributes[NIRIZAN_TRACE_ID_SOURCE] == ID_SOURCE_ROUNDTRIP


def test_assembly_records_a_conflict_between_stashed_trace_ids(
    inert: NiriZanSpanProcessor, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=_MODULE_LOGGER):
        trace = assemble_ok(
            inert,
            make_span(1, attributes={NIRIZAN_TRACE_ID: str(UUID(int=1))}),
            make_span(2, attributes={NIRIZAN_TRACE_ID: str(UUID(int=2))}),
        )

    assert trace.trace_id == UUID(int=1)
    assert inert.get_stats()["conflicting_trace_id"] == 1
    assert any("more than one distinct nirizan.trace_id" in r.getMessage() for r in caplog.records)


def test_assembly_gives_a_duplicate_stashed_span_id_a_derived_replacement(
    inert: NiriZanSpanProcessor,
) -> None:
    """``Span.span_id`` is unique per span: a second claimant is re-derived."""
    shared = str(uuid4())

    trace = assemble_ok(
        inert,
        make_span(1, name="first", attributes={NIRIZAN_SPAN_ID: shared}),
        make_span(2, name="second", attributes={NIRIZAN_SPAN_ID: shared}),
    )

    spans = by_name(trace)
    assert spans["first"].span_id == UUID(shared)
    assert spans["second"].span_id == otel_span_id_to_uuid(2)
    assert spans["second"].attributes[NIRIZAN_SPAN_ID_SOURCE] == SPAN_ID_SOURCE_DERIVED
    assert len({s.span_id for s in trace.spans}) == 2
    assert inert.get_stats()["duplicate_nirizan_span_id"] == 1


def test_assembly_keeps_children_attached_to_the_right_duplicate(
    inert: NiriZanSpanProcessor,
) -> None:
    shared = str(uuid4())

    trace = assemble_ok(
        inert,
        make_span(1, name="first", attributes={NIRIZAN_SPAN_ID: shared}),
        make_span(2, name="second", attributes={NIRIZAN_SPAN_ID: shared}),
        make_span(3, name="child-of-second", parent=2),
    )

    spans = by_name(trace)
    assert spans["child-of-second"].parent_span_id == spans["second"].span_id
    assert spans["child-of-second"].parent_span_id != spans["first"].span_id


def test_assembly_drops_a_span_whose_replacement_id_also_collides(
    inert: NiriZanSpanProcessor,
) -> None:
    """Astronomically unlikely, but it must never produce duplicate ids."""
    squatter = make_span(1, name="squatter", attributes={NIRIZAN_SPAN_ID: str(otel_span_id_to_uuid(2))})
    victim = make_span(2, name="victim")

    trace = assemble_ok(inert, squatter, victim)

    assert span_names(trace) == ["squatter"]
    assert inert.get_stats()["duplicate_nirizan_span_id"] == 1


def test_assembly_application_name_comes_from_the_root_spans_service(
    inert: NiriZanSpanProcessor,
) -> None:
    trace = assemble_ok(
        inert,
        make_span(1, service="root-service"),
        make_span(2, parent=1, service="child-service"),
    )

    assert trace.application_name == "root-service"


def test_assembly_application_name_falls_back_to_any_span_with_a_service(
    inert: NiriZanSpanProcessor,
) -> None:
    trace = assemble_ok(
        inert,
        make_span(1, service=None),
        make_span(2, parent=1, service="child-service"),
    )

    assert trace.application_name == "child-service"


def test_assembly_application_name_is_unknown_without_any_service_name(
    inert: NiriZanSpanProcessor,
) -> None:
    assert assemble_ok(inert, make_span(1, service=None)).application_name == "unknown"


def test_assembly_application_name_survives_when_the_promoted_root_has_the_name(
    inert: NiriZanSpanProcessor,
) -> None:
    """Regression: root resolution runs on surviving spans only."""
    trace = assemble_ok(
        inert,
        make_span(1, recognized=False, service=None),
        make_span(2, parent=1, service="promoted-root"),
    )

    assert trace.application_name == "promoted-root"
    assert trace.spans[0].parent_span_id is None


def test_assembly_session_id_uses_the_first_valid_session_by_start_time(
    inert: NiriZanSpanProcessor,
) -> None:
    first, second = uuid4(), uuid4()

    trace = assemble_ok(
        inert,
        make_span(2, start=T0 + 20, attributes={NIRIZAN_SESSION_ID: str(second)}),
        make_span(1, start=T0 + 10, attributes={NIRIZAN_SESSION_ID: str(first)}),
    )

    assert trace.session_id == first


def test_assembly_ignores_an_invalid_session_id(inert: NiriZanSpanProcessor) -> None:
    trace = assemble_ok(
        inert,
        make_span(1, attributes={NIRIZAN_SESSION_ID: "garbage"}),
        make_span(2, attributes={NIRIZAN_SESSION_ID: 7}),
    )

    assert trace.session_id is None


def test_assembly_clamps_and_defaults_span_names(inert: NiriZanSpanProcessor) -> None:
    trace = assemble_ok(
        inert,
        make_span(1, name="a" * 300),
        make_span(2, name=""),
        make_span(3, name=None),
        make_span(4, name="b" * _MAX_SPAN_NAME_LENGTH),
    )

    names = {s.attributes[OTEL_SPAN_ID]: s.name for s in trace.spans}
    assert names[format(1, "016x")] == "a" * _MAX_SPAN_NAME_LENGTH
    assert names[format(2, "016x")] == "unnamed"
    assert names[format(3, "016x")] == "unnamed"
    assert names[format(4, "016x")] == "b" * _MAX_SPAN_NAME_LENGTH


def test_assembly_converts_timestamps_to_utc_datetimes(inert: NiriZanSpanProcessor) -> None:
    trace = assemble_ok(
        inert,
        make_span(1, start=1_600_000_000_000_000_000, end=1_600_000_002_500_000_000),
    )

    span = trace.spans[0]
    assert span.started_at == datetime(2020, 9, 13, 12, 26, 40, tzinfo=UTC)
    assert span.ended_at == datetime(2020, 9, 13, 12, 26, 42, 500_000, tzinfo=UTC)


@pytest.mark.parametrize(
    ("status", "code", "description"),
    [
        (Status(StatusCode.ERROR, "boom"), "error", "boom"),
        (Status(StatusCode.OK), "ok", None),
        (Status(StatusCode.UNSET), "unset", None),
    ],
    ids=["error", "ok", "unset"],
)
def test_assembly_captures_otel_status_as_attributes(
    inert: NiriZanSpanProcessor, status: Status, code: str, description: str | None
) -> None:
    attrs = assemble_ok(inert, make_span(1, status=status)).spans[0].attributes

    assert attrs[OTEL_STATUS_CODE] == code
    assert attrs.get(OTEL_STATUS_DESCRIPTION) == description


@pytest.mark.parametrize("sampled", [True, False])
def test_assembly_captures_the_sampled_flag(inert: NiriZanSpanProcessor, sampled: bool) -> None:
    attrs = assemble_ok(inert, make_span(1, sampled=sampled)).spans[0].attributes

    assert attrs[OTEL_SAMPLED] is sampled


def test_assembly_captures_trace_state_only_when_present(inert: NiriZanSpanProcessor) -> None:
    with_state = assemble_ok(inert, make_span(1, trace_state=TraceState([("vendor", "x")])))
    without = assemble_ok(inert, make_span(2))

    assert with_state.spans[0].attributes[OTEL_TRACE_STATE] == "vendor=x"
    assert OTEL_TRACE_STATE not in without.spans[0].attributes


def test_assembly_captures_service_and_span_id_metadata(inert: NiriZanSpanProcessor) -> None:
    attrs = assemble_ok(inert, make_span(0xAB, service="svc")).spans[0].attributes

    assert attrs["otel.service.name"] == "svc"
    assert attrs[OTEL_SPAN_ID] == "00000000000000ab"


def test_assembly_preserves_the_original_otel_attributes(inert: NiriZanSpanProcessor) -> None:
    attrs = (
        assemble_ok(inert, make_span(1, attributes={"http.method": "GET", "retries": 3}))
        .spans[0]
        .attributes
    )

    assert attrs["http.method"] == "GET"
    assert attrs["retries"] == 3


def test_assembly_encodes_sequence_attributes(inert: NiriZanSpanProcessor) -> None:
    attrs = assemble_ok(inert, make_span(1, attributes={"tags": ("a", "b")})).spans[0].attributes

    assert json.loads(attrs[f"{SEQ_ATTR_PREFIX}tags"]) == ["a", "b"]


@pytest.mark.parametrize("kind", list(SpanKind))
def test_assembly_extracts_payloads_for_every_kind(
    inert: NiriZanSpanProcessor, kind: SpanKind
) -> None:
    in_key, out_key = _PAYLOAD_KEYS[kind]
    span = make_span(
        1,
        attributes={NIRIZAN_SPAN_KIND: kind.value, in_key: "the input", out_key: "the output"},
    )

    result = assemble_ok(inert, span).spans[0]

    assert (result.kind, result.input_payload, result.output_payload) == (
        kind,
        "the input",
        "the output",
    )


def test_assembly_preserves_non_ascii_text(inert: NiriZanSpanProcessor) -> None:
    span = make_span(
        1,
        name="বাংলা পরীক্ষা",
        attributes={GEN_AI_PROMPT: "আপনি কেমন আছেন?", "words": ["বাংলা", "العربية"]},
    )

    result = assemble_ok(inert, span).spans[0]

    assert result.name == "বাংলা পরীক্ষা"
    assert result.input_payload == "আপনি কেমন আছেন?"
    assert "\\u" not in result.attributes[f"{SEQ_ATTR_PREFIX}words"]


def test_assembly_drops_unrecognized_spans_by_default_and_counts_them(
    inert: NiriZanSpanProcessor,
) -> None:
    trace = assemble_ok(
        inert,
        make_span(1, name="known"),
        make_span(2, name="http-span", recognized=False),
    )

    assert span_names(trace) == ["known"]
    assert inert.get_stats()["unrecognized_kind"] == 1


def test_assembly_returns_none_when_nothing_is_recognizable(inert: NiriZanSpanProcessor) -> None:
    assert assemble(inert, make_span(1, recognized=False), make_span(2, recognized=False)) is None
    assert inert.get_stats()["unrecognized_kind"] == 2


def test_assembly_generation_policy_labels_unrecognized_spans_as_generation(
    make_inert: Callable[..., NiriZanSpanProcessor],
) -> None:
    processor = make_inert(unrecognized_span_policy="generation")

    trace = assemble_ok(processor, make_span(1, name="http-span", recognized=False))

    assert trace.spans[0].kind is SpanKind.GENERATION
    assert "unrecognized_kind" not in processor.get_stats()


def test_assembly_reattaches_children_of_dropped_unrecognized_spans(
    inert: NiriZanSpanProcessor,
) -> None:
    trace = assemble_ok(
        inert,
        make_span(1, name="root"),
        make_span(2, name="middleware", parent=1, recognized=False),
        make_span(3, name="leaf", parent=2),
    )

    spans = by_name(trace)
    assert set(spans) == {"root", "leaf"}
    assert spans["leaf"].parent_span_id == spans["root"].span_id


def test_assembly_promotes_a_child_whose_ancestors_are_all_dropped(
    inert: NiriZanSpanProcessor,
) -> None:
    trace = assemble_ok(
        inert,
        make_span(1, name="skipped-root", recognized=False),
        make_span(2, name="promoted", parent=1),
    )

    assert trace.spans[0].parent_span_id is None


def test_assembly_survives_a_span_that_cannot_be_converted_and_reattaches_its_children(
    inert: NiriZanSpanProcessor, caplog: pytest.LogCaptureFixture
) -> None:
    """A bad timestamp loses one span, not the trace, and leaves no dangling parent."""
    bad = make_span(2, name="bad", parent=1, start=10**30, end=10**30 + 1)

    with caplog.at_level(logging.WARNING, logger=_MODULE_LOGGER):
        trace = assemble_ok(
            inert,
            make_span(1, name="root"),
            bad,
            make_span(3, name="leaf", parent=2),
        )

    spans = by_name(trace)
    assert set(spans) == {"root", "leaf"}
    assert spans["leaf"].parent_span_id == spans["root"].span_id
    assert inert.get_stats()["conversion_error"] == 1
    assert any("Failed to convert OTel span 'bad'" in r.getMessage() for r in caplog.records)


def test_assembly_returns_none_when_every_span_fails_conversion(
    inert: NiriZanSpanProcessor,
) -> None:
    assert assemble(inert, make_span(1, start=10**30, end=10**30 + 1)) is None
    assert inert.get_stats()["conversion_error"] == 1


def test_assembly_emit_policy_gives_an_orphan_a_deterministic_synthetic_parent(
    inert: NiriZanSpanProcessor,
) -> None:
    trace = assemble_ok(inert, make_span(3, name="orphan", parent=0x9999))

    assert trace.spans[0].parent_span_id == otel_span_id_to_uuid(0x9999)
    assert inert.get_stats()["orphan_emitted"] == 1


def test_assembly_drop_policy_discards_orphans_and_counts_them(
    make_inert: Callable[..., NiriZanSpanProcessor],
) -> None:
    processor = make_inert(orphan_policy="drop")

    trace = assemble(processor, make_span(3, parent=0x9999))

    assert trace is None
    assert processor.get_stats()["orphan_parent_missing"] == 1


@pytest.mark.parametrize("policy", ["emit", "drop"])
def test_assembly_keeps_a_remote_parented_span_as_a_root(
    make_inert: Callable[..., NiriZanSpanProcessor], policy: str
) -> None:
    processor = make_inert(orphan_policy=policy)

    trace = assemble_ok(processor, make_span(2, parent=0xAAA, remote_parent=True))

    assert trace.spans[0].parent_span_id is None
    assert "orphan_emitted" not in processor.get_stats()


def test_assembly_counts_a_broken_cycle(inert: NiriZanSpanProcessor) -> None:
    trace = assemble_ok(inert, make_span(1, parent=2), make_span(2, parent=1))

    assert len(trace.spans) == 2
    assert sum(1 for s in trace.spans if s.parent_span_id is None) == 1
    assert inert.get_stats()["cycle_broken"] == 1


def test_assembly_does_not_mutate_the_buffer(inert: NiriZanSpanProcessor) -> None:
    buf = buffer_of(make_span(1), make_span(2, parent=1))
    before = dict(buf.spans)

    inert._assemble_trace(buf)

    assert buf.spans == before


def test_assembly_is_deterministic_for_any_arrival_order(inert: NiriZanSpanProcessor) -> None:
    spans = [
        make_span(1),
        make_span(2, parent=1),
        make_span(3, parent=1),
        make_span(4, parent=2),
        make_span(5, parent=0xAAA),
    ]
    baseline = assemble_ok(inert, *spans)

    for order in itertools.islice(itertools.permutations(spans), 24):
        again = assemble_ok(inert, *order)
        assert again.spans == baseline.spans
        assert again.trace_id == baseline.trace_id


def test_assembly_is_repeatable_on_the_same_buffer(inert: NiriZanSpanProcessor) -> None:
    buf = buffer_of(make_span(1), make_span(2, parent=1))

    first = inert._assemble_trace(buf)
    second = inert._assemble_trace(buf)

    assert first is not None and second is not None
    assert first.spans == second.spans


def test_assembled_trace_survives_a_json_round_trip(inert: NiriZanSpanProcessor) -> None:
    trace = assemble_ok(
        inert,
        make_span(1, attributes={GEN_AI_PROMPT: "বাংলা", "tags": ["a"]}),
        make_span(2, parent=1, status=Status(StatusCode.ERROR, "boom")),
    )

    restored = Trace.model_validate_json(trace.model_dump_json())

    assert restored == trace


@pytest.mark.parametrize("policy", ["emit", "drop"])
def test_assembly_invariants_hold_on_random_forests(
    make_inert: Callable[..., NiriZanSpanProcessor], policy: str
) -> None:
    processor = make_inert(orphan_policy=policy)
    rng = random.Random(99)

    for _ in range(150):
        spans, _ = _random_forest(rng)
        missing_ids = {
            parent.span_id
            for s in spans
            if (parent := s.parent) is not None
            and parent.span_id not in {_ctx_of(x).span_id for x in spans}
        }
        trace = processor._assemble_trace(buffer_of(*spans))
        if trace is None:
            continue

        ids = {s.span_id for s in trace.spans}
        assert len(ids) == len(trace.spans)
        assert all(s.trace_id == trace.trace_id for s in trace.spans)
        assert all(s.parent_span_id != s.span_id for s in trace.spans)
        assert [s.started_at for s in trace.spans] == sorted(s.started_at for s in trace.spans)
        synthetic_parents = {otel_span_id_to_uuid(m) for m in missing_ids}
        for span in trace.spans:
            if span.parent_span_id is None:
                continue
            if policy == "drop":
                assert span.parent_span_id in ids
            else:
                assert span.parent_span_id in ids | synthetic_parents


# ===========================================================================
# Processor state machine (synchronous, via an inert processor)
# ===========================================================================


def flush_state(processor: NiriZanSpanProcessor, trace_id: int = TRACE_ID) -> bool:
    return trace_id in processor._recent_flushes


@pytest.mark.parametrize(
    ("span", "reason"),
    [
        (ReadableSpan(name="no-context", context=None), "invalid_span_context"),
        (make_span(1, trace_id=0), "invalid_trace_id"),
        (make_span(0), "invalid_span_id"),
    ],
    ids=["no-context", "zero-trace-id", "zero-span-id"],
)
def test_buffering_rejects_invalid_spans_and_counts_them(
    inert: NiriZanSpanProcessor, span: ReadableSpan, reason: str
) -> None:
    inert._buffer_span(span)

    assert inert._buffers == {}
    assert inert.get_stats() == {reason: 1}


def test_buffering_creates_one_buffer_per_trace(inert: NiriZanSpanProcessor) -> None:
    inert._buffer_span(make_span(1))
    inert._buffer_span(make_span(2))
    inert._buffer_span(make_span(3, trace_id=OTHER_TRACE_ID))

    assert set(inert._buffers) == {TRACE_ID, OTHER_TRACE_ID}
    assert set(inert._buffers[TRACE_ID].spans) == {1, 2}


def test_buffering_counts_a_duplicate_otel_span_id_and_keeps_the_latest(
    inert: NiriZanSpanProcessor, caplog: pytest.LogCaptureFixture
) -> None:
    inert._buffer_span(make_span(1, name="first"))
    with caplog.at_level(logging.WARNING, logger=_MODULE_LOGGER):
        inert._buffer_span(make_span(1, name="second"))

    assert inert._buffers[TRACE_ID].spans[1].name == "second"
    assert inert.get_stats() == {"duplicate_span_id": 1}
    assert any("Duplicate OTel span_id" in r.getMessage() for r in caplog.records)


def test_a_span_arriving_after_its_trace_was_flushed_is_dropped_and_counted(
    inert: NiriZanSpanProcessor, sink: RecordingSink
) -> None:
    inert._buffer_span(make_span(1))
    inert._flush_trace(TRACE_ID, reason="test")

    inert._buffer_span(make_span(2))

    assert len(sink.traces) == 1
    assert TRACE_ID not in inert._buffers
    assert inert.get_stats() == {"late_arrival": 1}


def test_start_markers_are_ignored_for_an_already_flushed_trace(
    inert: NiriZanSpanProcessor,
) -> None:
    inert._buffer_span(make_span(1))
    inert._flush_trace(TRACE_ID, reason="test")

    inert._mark_span_started(TRACE_ID, 0.0)

    assert TRACE_ID not in inert._buffers


def test_start_and_end_markers_balance_the_open_span_count(inert: NiriZanSpanProcessor) -> None:
    inert._mark_span_started(TRACE_ID, 0.0)
    inert._mark_span_started(TRACE_ID, 0.0)
    assert inert._buffers[TRACE_ID].open_spans == 2

    inert._buffer_span(make_span(1))
    assert inert._buffers[TRACE_ID].open_spans == 1


def test_idle_flush_waits_for_the_idle_timeout(
    make_inert: Callable[..., NiriZanSpanProcessor], clock: FakeClock, sink: RecordingSink
) -> None:
    processor = make_inert(idle_timeout_seconds=5.0, max_trace_age_seconds=60.0)
    processor._buffer_span(make_span(1))

    clock.advance(4.999)
    processor._sweep_idle_traces()
    assert sink.traces == []

    clock.advance(0.001)
    processor._sweep_idle_traces()
    assert len(sink.traces) == 1


def test_idle_flush_does_not_flush_a_trace_with_an_open_span(
    make_inert: Callable[..., NiriZanSpanProcessor], clock: FakeClock, sink: RecordingSink
) -> None:
    processor = make_inert(idle_timeout_seconds=5.0, max_trace_age_seconds=60.0)
    processor._mark_span_started(TRACE_ID, clock())
    processor._buffer_span(make_span(1))
    processor._mark_span_started(TRACE_ID, clock())  # a second span is still open

    clock.advance(30.0)
    processor._sweep_idle_traces()

    assert sink.traces == []
    assert TRACE_ID in processor._buffers


def test_max_age_flushes_even_a_trace_with_an_open_span(
    make_inert: Callable[..., NiriZanSpanProcessor], clock: FakeClock, sink: RecordingSink
) -> None:
    processor = make_inert(idle_timeout_seconds=5.0, max_trace_age_seconds=60.0)
    processor._mark_span_started(TRACE_ID, clock())
    processor._mark_span_started(TRACE_ID, clock())
    processor._buffer_span(make_span(1))

    clock.advance(59.999)
    processor._sweep_idle_traces()
    assert sink.traces == []

    clock.advance(0.001)
    processor._sweep_idle_traces()
    assert len(sink.traces) == 1


@pytest.mark.parametrize(
    ("open_spans", "untracked_start", "untracked_end", "quiescent"),
    [
        (0, False, False, True),
        (1, False, False, False),
        (0, True, False, False),
        (0, False, True, False),
        (2, True, True, False),
    ],
)
def test_quiescence_requires_no_open_spans_and_trustworthy_accounting(
    open_spans: int, untracked_start: bool, untracked_end: bool, quiescent: bool
) -> None:
    buf = _TraceBuffer(TRACE_ID, 0.0)
    buf.open_spans = open_spans
    buf.has_untracked_start = untracked_start
    buf.has_untracked_end = untracked_end

    assert NiriZanSpanProcessor._is_quiescent(buf) is quiescent


@pytest.mark.parametrize(
    ("idle_for", "open_spans", "untracked_start", "untracked_end", "flushable"),
    [
        (4.0, 0, False, False, False),  # not idle long enough
        (5.0, 0, False, False, True),  # idle, nothing open
        (5.0, 1, False, False, False),  # idle but a span is open
        (5.0, 0, True, False, False),  # a dropped start: the count could be too low
        (5.0, 3, False, True, True),  # a dropped end: the count is too high, trust silence
        (5.0, 1, True, True, False),  # both: the count is meaningless, wait for max age
        (4.0, 3, False, True, False),  # a dropped end still needs the idle timeout
    ],
)
def test_idle_flush_rule_truth_table(
    make_inert: Callable[..., NiriZanSpanProcessor],
    clock: FakeClock,
    idle_for: float,
    open_spans: int,
    untracked_start: bool,
    untracked_end: bool,
    flushable: bool,
) -> None:
    processor = make_inert(idle_timeout_seconds=5.0, max_trace_age_seconds=60.0)
    buf = _TraceBuffer(TRACE_ID, clock())
    buf.open_spans = open_spans
    buf.has_untracked_start = untracked_start
    buf.has_untracked_end = untracked_end
    clock.advance(idle_for)

    assert processor._is_idle_flushable(buf, clock()) is flushable


def test_a_dropped_end_marker_lets_an_idle_trace_flush_despite_a_stuck_open_count(
    make_inert: Callable[..., NiriZanSpanProcessor], clock: FakeClock, sink: RecordingSink
) -> None:
    """Regression: a lost span end left ``open_spans`` stuck, so the trace waited for max age."""
    processor = make_inert(idle_timeout_seconds=5.0, max_trace_age_seconds=600.0)
    processor._mark_span_started(TRACE_ID, clock())
    processor._mark_span_started(TRACE_ID, clock())
    processor._buffer_span(make_span(1))  # one span ended; the other's end was dropped
    processor._note_dropped_marker(processor._dropped_end_traces, TRACE_ID)

    clock.advance(5.0)
    processor._sweep_idle_traces()

    assert len(sink.traces) == 1
    assert processor.get_stats()["queue_full"] == 1


def test_a_dropped_start_marker_keeps_a_trace_from_flushing_on_idle_but_not_on_age(
    make_inert: Callable[..., NiriZanSpanProcessor], clock: FakeClock, sink: RecordingSink
) -> None:
    processor = make_inert(idle_timeout_seconds=5.0, max_trace_age_seconds=60.0)
    processor._buffer_span(make_span(1))
    processor._note_dropped_marker(processor._dropped_start_traces, TRACE_ID)

    clock.advance(30.0)
    processor._sweep_idle_traces()
    assert sink.traces == []

    clock.advance(30.0)
    processor._sweep_idle_traces()
    assert len(sink.traces) == 1


def test_pending_dropped_markers_are_applied_by_the_sweep_without_new_activity(
    make_inert: Callable[..., NiriZanSpanProcessor], clock: FakeClock
) -> None:
    processor = make_inert(idle_timeout_seconds=5.0, max_trace_age_seconds=600.0)
    processor._mark_span_started(TRACE_ID, clock())
    processor._note_dropped_marker(processor._dropped_end_traces, TRACE_ID)

    processor._sweep_idle_traces()

    assert processor._buffers[TRACE_ID].has_untracked_end is True
    assert processor._dropped_end_traces == {}


def test_a_dropped_marker_is_consumed_exactly_once(inert: NiriZanSpanProcessor) -> None:
    inert._note_dropped_marker(inert._dropped_start_traces, TRACE_ID)

    assert inert._consume_dropped_start(TRACE_ID) is True
    assert inert._consume_dropped_start(TRACE_ID) is False
    assert inert._consume_dropped_end(TRACE_ID) is False


def test_dropped_marker_tables_are_bounded_and_evict_the_oldest(
    inert: NiriZanSpanProcessor, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(from_otel, "_RECENT_FLUSHES_MAX", 3)

    for trace_id in range(1, 7):
        inert._note_dropped_marker(inert._dropped_end_traces, trace_id)

    assert list(inert._dropped_end_traces) == [4, 5, 6]


def test_recent_flush_memory_is_bounded_and_evicts_the_oldest(
    inert: NiriZanSpanProcessor, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(from_otel, "_RECENT_FLUSHES_MAX", 3)

    for trace_id in range(1, 7):
        inert._buffer_span(make_span(1, trace_id=trace_id))
        inert._flush_trace(trace_id, reason="test")

    assert list(inert._recent_flushes) == [4, 5, 6]


def test_force_flush_rule_flushes_finished_traces_and_leaves_in_flight_ones(
    inert: NiriZanSpanProcessor, sink: RecordingSink
) -> None:
    inert._buffer_span(make_span(1, trace_id=0xA))  # finished
    inert._mark_span_started(0xB, 0.0)  # in flight
    inert._buffer_span(make_span(1, trace_id=0xB))
    inert._mark_span_started(0xB, 0.0)

    inert._flush_quiescent(reason="force_flush")

    assert [t.trace_id for t in sink.traces] == [otel_trace_id_to_uuid(0xA)]
    assert set(inert._buffers) == {0xB}


def test_force_flush_rule_does_not_poison_an_in_flight_trace(
    inert: NiriZanSpanProcessor, sink: RecordingSink
) -> None:
    """Regression: flushing an in-flight trace made its remaining spans 'late arrivals'."""
    inert._mark_span_started(TRACE_ID, 0.0)
    inert._mark_span_started(TRACE_ID, 0.0)
    inert._buffer_span(make_span(2, parent=1))

    inert._flush_quiescent(reason="force_flush")
    inert._buffer_span(make_span(1))  # the root finishes afterwards
    inert._flush_quiescent(reason="force_flush")

    assert len(sink.traces) == 1
    assert span_names(sink.traces[0]) == ["span", "span"]
    assert "late_arrival" not in inert.get_stats()


def test_force_flush_rule_applies_pending_dropped_markers_before_deciding(
    inert: NiriZanSpanProcessor, sink: RecordingSink
) -> None:
    inert._buffer_span(make_span(1))
    inert._note_dropped_marker(inert._dropped_end_traces, TRACE_ID)

    inert._flush_quiescent(reason="force_flush")

    assert sink.traces == []  # a lost span end means we cannot call this trace finished


def test_flush_all_flushes_every_trace_including_in_flight_ones(
    inert: NiriZanSpanProcessor, sink: RecordingSink
) -> None:
    inert._mark_span_started(0xB, 0.0)
    inert._mark_span_started(0xB, 0.0)
    inert._buffer_span(make_span(1, trace_id=0xB))
    inert._buffer_span(make_span(1, trace_id=0xA))

    inert._flush_all(reason="shutdown")

    assert len(sink.traces) == 2
    assert inert._buffers == {}


def test_buffer_cap_evicts_finished_traces_before_in_flight_ones(
    make_inert: Callable[..., NiriZanSpanProcessor], clock: FakeClock, sink: RecordingSink
) -> None:
    processor = make_inert(max_buffered_traces=2)

    processor._mark_span_started(0xA, clock())  # the oldest trace is still in flight
    processor._mark_span_started(0xA, clock())
    processor._buffer_span(make_span(1, trace_id=0xA))
    clock.advance(1)
    processor._buffer_span(make_span(1, trace_id=0xB))
    clock.advance(1)
    processor._buffer_span(make_span(1, trace_id=0xC))

    processor._enforce_buffer_cap()

    assert [t.trace_id for t in sink.traces] == [otel_trace_id_to_uuid(0xB)]
    assert set(processor._buffers) == {0xA, 0xC}
    assert "evicted_open_trace" not in processor.get_stats()


def test_buffer_cap_evicts_the_oldest_in_flight_trace_only_when_it_must(
    make_inert: Callable[..., NiriZanSpanProcessor], clock: FakeClock, sink: RecordingSink
) -> None:
    processor = make_inert(max_buffered_traces=1)
    for trace_id in (0xA, 0xB):
        processor._mark_span_started(trace_id, clock())
        processor._mark_span_started(trace_id, clock())
        processor._buffer_span(make_span(1, trace_id=trace_id))
        clock.advance(1)

    processor._enforce_buffer_cap()

    assert [t.trace_id for t in sink.traces] == [otel_trace_id_to_uuid(0xA)]
    assert processor.get_stats()["evicted_open_trace"] == 1


def test_buffer_cap_is_a_no_op_at_or_below_the_limit(
    make_inert: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_inert(max_buffered_traces=2)
    processor._buffer_span(make_span(1, trace_id=0xA))
    processor._buffer_span(make_span(1, trace_id=0xB))

    processor._enforce_buffer_cap()

    assert sink.traces == []
    assert len(processor._buffers) == 2


def test_per_trace_span_cap_drops_extra_spans_warns_once_and_counts_each(
    make_inert: Callable[..., NiriZanSpanProcessor], caplog: pytest.LogCaptureFixture
) -> None:
    processor = make_inert(max_spans_per_trace=3)

    with caplog.at_level(logging.WARNING, logger=_MODULE_LOGGER):
        for span_id in range(1, 7):
            processor._mark_span_started(TRACE_ID, 0.0)
            processor._buffer_span(make_span(span_id))

    buf = processor._buffers[TRACE_ID]
    assert set(buf.spans) == {1, 2, 3}
    assert buf.open_spans == 0
    assert processor.get_stats()["trace_span_cap"] == 3
    assert sum("max_spans_per_trace" in r.getMessage() for r in caplog.records) == 1


def test_per_trace_span_cap_still_accepts_a_replacement_for_a_stored_span(
    make_inert: Callable[..., NiriZanSpanProcessor],
) -> None:
    processor = make_inert(max_spans_per_trace=1)
    processor._buffer_span(make_span(1, name="first"))

    processor._buffer_span(make_span(1, name="second"))

    assert processor._buffers[TRACE_ID].spans[1].name == "second"
    assert "trace_span_cap" not in processor.get_stats()


def test_flushing_a_trace_with_only_unrecognized_spans_delivers_nothing_and_does_not_raise(
    inert: NiriZanSpanProcessor, sink: RecordingSink
) -> None:
    inert._buffer_span(make_span(1, recognized=False))

    inert._flush_trace(TRACE_ID, reason="test")

    assert sink.traces == []
    assert flush_state(inert)


def test_flushing_an_unknown_trace_is_a_no_op(inert: NiriZanSpanProcessor, sink: RecordingSink) -> None:
    inert._flush_trace(0xDEAD, reason="test")

    assert sink.traces == []
    assert inert._recent_flushes == {}


def test_a_failing_sink_does_not_raise_and_does_not_resurrect_the_trace(
    inert: NiriZanSpanProcessor, sink: RecordingSink, caplog: pytest.LogCaptureFixture
) -> None:
    sink.raise_on_enqueue = True
    inert._buffer_span(make_span(1))

    with caplog.at_level(logging.ERROR, logger=_MODULE_LOGGER):
        inert._flush_trace(TRACE_ID, reason="test")

    assert flush_state(inert)
    assert TRACE_ID not in inert._buffers
    assert any("TraceSink.enqueue_trace raised" in r.getMessage() for r in caplog.records)


def test_an_assembly_failure_does_not_raise_and_still_marks_the_trace_flushed(
    inert: NiriZanSpanProcessor,
    sink: RecordingSink,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def explode(_: _TraceBuffer) -> Trace:
        raise RuntimeError("assembly bug")

    inert._buffer_span(make_span(1))
    monkeypatch.setattr(inert, "_assemble_trace", explode)

    with caplog.at_level(logging.ERROR, logger=_MODULE_LOGGER):
        inert._flush_trace(TRACE_ID, reason="test")

    assert sink.traces == []
    assert flush_state(inert)
    assert any("Failed to assemble NiriZan Trace" in r.getMessage() for r in caplog.records)


def test_stats_are_a_copy_and_start_empty(inert: NiriZanSpanProcessor) -> None:
    assert inert.get_stats() == {}

    inert._record_stat(StatReason.LATE_ARRIVAL)
    snapshot = inert.get_stats()
    snapshot["late_arrival"] = 999

    assert inert.get_stats() == {"late_arrival": 1}


def test_stat_recording_is_thread_safe(inert: NiriZanSpanProcessor) -> None:
    threads, per_thread = 8, 500

    def hammer() -> None:
        for _ in range(per_thread):
            inert._record_stat(StatReason.LATE_ARRIVAL)

    workers = [threading.Thread(target=hammer) for _ in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert inert.get_stats() == {"late_arrival": threads * per_thread}


def test_fake_clock_drives_buffer_timestamps(
    make_inert: Callable[..., NiriZanSpanProcessor], clock: FakeClock
) -> None:
    processor = make_inert()
    clock.now = 1234.5

    processor._buffer_span(make_span(1))

    assert processor._buffers[TRACE_ID].first_seen == 1234.5


# ===========================================================================
# on_start / on_end entry points
# ===========================================================================


def test_entry_points_are_no_ops_after_shutdown(
    inert: NiriZanSpanProcessor, sink: RecordingSink
) -> None:
    inert.on_start(make_span(1))
    inert.on_end(make_span(1))

    assert inert._queue.empty()
    assert inert.force_flush() is False


def test_on_start_ignores_spans_with_an_invalid_context(
    make_processor: Callable[..., NiriZanSpanProcessor],
) -> None:
    processor = make_processor()

    processor.on_start(ReadableSpan(name="no-context", context=None))
    processor.on_start(make_span(1, trace_id=0))

    assert processor.force_flush()
    assert processor._buffers == {}


def test_own_scope_spans_are_skipped_by_default_and_counted(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor()
    own = make_span(1, scope=NIRIZAN_INSTRUMENTATION_SCOPE)

    processor.on_start(own)
    processor.on_end(own)

    assert processor.force_flush()
    assert sink.traces == []
    assert processor.get_stats() == {"own_scope_skipped": 1}


def test_own_scope_spans_are_ingested_when_the_guard_is_disabled(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor(ignore_own_scope=False)
    own = make_span(1, scope=NIRIZAN_INSTRUMENTATION_SCOPE)

    processor.on_start(own)
    processor.on_end(own)

    assert processor.force_flush()
    assert len(sink.traces) == 1


def test_other_scopes_are_never_skipped(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor()

    processor.on_end(make_span(1, scope="nirizan.other"))
    processor.on_end(make_span(2, scope="NiriZan"))

    assert processor.force_flush()
    assert len(sink.traces) == 1
    assert len(sink.traces[0].spans) == 2


# ===========================================================================
# Live processor: delivery, force_flush, shutdown
# ===========================================================================


def test_end_to_end_delivery_of_a_two_span_trace(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor()
    session = uuid4()
    stashed = uuid4()
    root = make_span(
        0x1111,
        name="parent-span",
        attributes={NIRIZAN_SESSION_ID: str(session), NIRIZAN_SPAN_ID: str(stashed), GEN_AI_PROMPT: "hi"},
    )
    child = make_span(0x2222, name="child-span", parent=0x1111, attributes={GEN_AI_COMPLETION: "yo"})

    processor.on_end(root)
    processor.on_end(child)

    assert processor.force_flush(timeout_millis=5_000) is True
    assert len(sink.traces) == 1
    trace = sink.traces[0]
    assert trace.application_name == "my-service"
    assert trace.session_id == session
    spans = by_name(trace)
    assert spans["parent-span"].span_id == stashed
    assert spans["child-span"].parent_span_id == stashed
    assert spans["child-span"].span_id == otel_span_id_to_uuid(0x2222)
    assert processor.get_stats() == {}


def test_force_flush_keeps_a_trace_with_open_spans_buffered_and_delivers_it_whole_later(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    """Regression: ``force_flush`` used to cut in-flight traces short and lose their tails."""
    processor = make_processor()
    root = make_span(1, name="root")
    child = make_span(2, name="child", parent=1)

    processor.on_start(root)
    processor.on_start(child)
    processor.on_end(child)
    assert processor.force_flush(timeout_millis=5_000) is True
    assert sink.traces == []

    processor.on_end(root)
    assert processor.force_flush(timeout_millis=5_000) is True

    assert len(sink.traces) == 1
    assert sorted(span_names(sink.traces[0])) == ["child", "root"]
    assert by_name(sink.traces[0])["child"].parent_span_id == by_name(sink.traces[0])["root"].span_id
    assert processor.get_stats() == {}


def test_force_flush_delivers_each_finished_trace_once(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor()
    processor.on_end(make_span(1))

    assert processor.force_flush() is True
    assert processor.force_flush() is True

    assert len(sink.traces) == 1


def test_force_flush_with_nothing_buffered_succeeds(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    assert make_processor().force_flush() is True
    assert sink.traces == []


def test_a_span_arriving_after_a_completed_flush_is_a_late_arrival(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor()
    processor.on_end(make_span(1))
    assert processor.force_flush()

    processor.on_end(make_span(2))
    assert processor.force_flush()

    assert len(sink.traces) == 1
    assert processor.get_stats() == {"late_arrival": 1}


def test_shutdown_flushes_in_flight_traces(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor()
    root = make_span(1, name="never-ends")
    child = make_span(2, name="child", parent=1)
    processor.on_start(root)
    processor.on_start(child)
    processor.on_end(child)

    processor.shutdown()

    assert len(sink.traces) == 1
    assert span_names(sink.traces[0]) == ["child"]


def test_shutdown_is_idempotent_and_releases_the_consumer_thread(
    sink: RecordingSink,
) -> None:
    processor = NiriZanSpanProcessor(sink)
    thread = processor._consumer

    processor.shutdown()
    processor.shutdown()

    assert not thread.is_alive()
    assert thread not in consumer_threads()
    assert processor.force_flush() is False


def test_shutdown_delivers_spans_queued_before_it(sink: RecordingSink) -> None:
    processor = NiriZanSpanProcessor(sink)
    processor.on_end(make_span(1))

    processor.shutdown()

    assert len(sink.traces) == 1


def test_force_flush_times_out_when_the_queue_is_saturated_and_data_is_not_lost_silently(
    make_processor: Callable[..., NiriZanSpanProcessor],
) -> None:
    """Back-pressure: a stuck sink fills the queue; the processor degrades, it does not block."""
    blocking = BlockingSink()
    processor = make_processor(sink=blocking, max_queue_size=2)

    processor.on_end(make_span(1, trace_id=0xA))
    flusher = threading.Thread(target=processor.force_flush, kwargs={"timeout_millis": 10_000})
    flusher.start()
    assert blocking.entered.wait(timeout=5), "consumer never reached the sink"

    # The consumer is parked in the sink; fill the two-slot queue.
    processor.on_end(make_span(1, trace_id=0xB))
    processor.on_end(make_span(2, trace_id=0xB))
    # Everything from here on is dropped without blocking the caller.
    processor.on_end(make_span(3, trace_id=0xB))
    processor.on_start(make_span(4, trace_id=0xC))

    assert processor.get_stats()["queue_full"] == 2
    assert processor.force_flush(timeout_millis=50) is False

    blocking.release.set()
    flusher.join(timeout=10)
    assert not flusher.is_alive()
    assert processor.force_flush(timeout_millis=5_000) is True

    delivered = {t.trace_id: t for t in blocking.traces}
    assert otel_trace_id_to_uuid(0xA) in delivered


def test_a_trace_that_lost_a_span_end_is_held_by_force_flush_and_delivered_on_shutdown(
    make_processor: Callable[..., NiriZanSpanProcessor],
) -> None:
    blocking = BlockingSink()
    processor = make_processor(sink=blocking, max_queue_size=2)

    processor.on_end(make_span(1, trace_id=0xA))
    flusher = threading.Thread(target=processor.force_flush, kwargs={"timeout_millis": 10_000})
    flusher.start()
    assert blocking.entered.wait(timeout=5)

    processor.on_end(make_span(1, trace_id=0xB))
    processor.on_end(make_span(2, trace_id=0xB))
    processor.on_end(make_span(3, trace_id=0xB))  # dropped: trace B lost a span end

    blocking.release.set()
    flusher.join(timeout=10)
    assert processor.force_flush(timeout_millis=5_000) is True

    assert [t.trace_id for t in blocking.traces] == [otel_trace_id_to_uuid(0xA)]

    processor.shutdown()

    delivered = {t.trace_id: t for t in blocking.traces}
    assert len(delivered[otel_trace_id_to_uuid(0xB)].spans) == 2


def test_a_failing_sink_does_not_stop_later_deliveries(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor()
    sink.raise_on_enqueue = True
    processor.on_end(make_span(1, trace_id=0xA))
    assert processor.force_flush() is True
    assert sink.traces == []

    sink.raise_on_enqueue = False
    processor.on_end(make_span(1, trace_id=0xB))
    assert processor.force_flush() is True

    assert [t.trace_id for t in sink.traces] == [otel_trace_id_to_uuid(0xB)]
    assert processor._consumer.is_alive()


def test_an_unexpected_error_in_the_consumer_is_counted_and_the_thread_survives(
    make_processor: Callable[..., NiriZanSpanProcessor],
    sink: RecordingSink,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    processor = make_processor()
    original = processor._buffer_span
    calls = {"n": 0}

    def flaky(span: ReadableSpan) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("unexpected")
        original(span)

    monkeypatch.setattr(processor, "_buffer_span", flaky)

    with caplog.at_level(logging.ERROR, logger=_MODULE_LOGGER):
        processor.on_end(make_span(1, trace_id=0xA))
        processor.on_end(make_span(1, trace_id=0xB))
        assert processor.force_flush() is True

    assert processor._consumer.is_alive()
    assert processor.get_stats() == {"consumer_error": 1}
    assert [t.trace_id for t in sink.traces] == [otel_trace_id_to_uuid(0xB)]
    assert any("Unexpected error in NiriZanSpanProcessor consumer" in r.getMessage() for r in caplog.records)


def test_a_flush_waiter_is_released_even_if_the_flush_itself_fails(
    make_processor: Callable[..., NiriZanSpanProcessor],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processor = make_processor()

    def explode(*, reason: str) -> None:
        raise RuntimeError("flush bug")

    monkeypatch.setattr(processor, "_flush_quiescent", explode)

    assert processor.force_flush(timeout_millis=5_000) is True
    assert processor.get_stats() == {"consumer_error": 1}


# ===========================================================================
# Concurrency
# ===========================================================================


def test_many_producer_threads_lose_no_spans_and_never_mix_traces(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor()
    producers, traces_each = 8, 25

    def produce(worker: int) -> None:
        for n in range(1, traces_each + 1):
            trace_id = (worker << 32) | n
            root = make_span(1, trace_id=trace_id, name=f"root-{worker}-{n}")
            mid = make_span(2, trace_id=trace_id, parent=1, name="mid")
            leaf = make_span(3, trace_id=trace_id, parent=2, name="leaf")
            for span in (root, mid, leaf):
                processor.on_start(span)
            for span in (leaf, mid, root):
                processor.on_end(span)

    workers = [threading.Thread(target=produce, args=(w,)) for w in range(1, producers + 1)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert processor.force_flush(timeout_millis=30_000) is True

    assert len(sink.traces) == producers * traces_each
    assert processor.get_stats() == {}
    assert len({t.trace_id for t in sink.traces}) == producers * traces_each
    for trace in sink.traces:
        spans = by_name(trace)
        assert set(spans) == {name for name in span_names(trace)}
        assert len(trace.spans) == 3
        assert spans["leaf"].parent_span_id == spans["mid"].span_id
        assert spans["mid"].parent_span_id == next(
            s.span_id for s in trace.spans if s.name.startswith("root-")
        )


# ===========================================================================
# Fork safety
# ===========================================================================


@pytest.mark.skipif(not hasattr(os, "fork"), reason="fork is not available on this platform")
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_the_consumer_is_restarted_in_a_forked_child_and_the_parent_is_unaffected(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor()
    processor.on_end(make_span(1, trace_id=0xA))
    assert processor.force_flush()
    assert len(sink.traces) == 1

    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # pragma: no cover - runs in the child process
        exit_code = 1
        try:
            os.close(read_fd)
            processor.on_end(make_span(1, trace_id=0xB))
            flushed = processor.force_flush(timeout_millis=5_000)
            report = f"{flushed},{processor._consumer.is_alive()},{len(sink.traces)}"
            os.write(write_fd, report.encode())
            exit_code = 0
        except BaseException as err:
            os.write(write_fd, f"error:{err!r}".encode())
        finally:
            os._exit(exit_code)

    os.close(write_fd)
    with os.fdopen(read_fd) as reader:
        report = reader.read()
    _, status = os.waitpid(pid, 0)

    assert os.waitstatus_to_exitcode(status) == 0, report
    # In the child: flush succeeded, a fresh consumer is alive, and its sink copy now
    # holds the parent's earlier trace plus the child's own.
    assert report == "True,True,2"

    processor.on_end(make_span(1, trace_id=0xC))
    assert processor.force_flush()
    assert [t.trace_id for t in sink.traces] == [
        otel_trace_id_to_uuid(0xA),
        otel_trace_id_to_uuid(0xC),
    ]


def test_a_processor_that_was_shut_down_stays_shut_down_after_a_simulated_fork(
    inert: NiriZanSpanProcessor,
) -> None:
    inert._reinit_after_fork()

    assert not inert._consumer.is_alive()
    assert inert.force_flush() is False


def test_reinit_after_fork_replaces_inherited_state_and_restarts_the_consumer(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor()
    processor.on_start(make_span(1, trace_id=0xA))
    processor.on_end(make_span(2, trace_id=0xA))
    assert processor.force_flush()
    old_queue, old_lock = processor._queue, processor._stats_lock
    processor._record_stat(StatReason.LATE_ARRIVAL)

    processor._reinit_after_fork()

    assert processor._queue is not old_queue
    assert processor._stats_lock is not old_lock
    assert processor._buffers == {} and processor._recent_flushes == {}
    assert processor.get_stats() == {}
    processor.on_end(make_span(1, trace_id=0xB))
    assert processor.force_flush()
    assert [t.trace_id for t in sink.traces] == [otel_trace_id_to_uuid(0xB)]


def test_live_processors_are_registered_for_fork_handling_without_keeping_them_alive(
    sink: RecordingSink,
) -> None:
    processor = NiriZanSpanProcessor(sink)
    assert processor in from_otel._LIVE_PROCESSORS

    processor.shutdown()
    ref_count_before = len(from_otel._LIVE_PROCESSORS)
    del processor

    assert len(from_otel._LIVE_PROCESSORS) <= ref_count_before


# ===========================================================================
# Integration with a real OpenTelemetry SDK
# ===========================================================================


@pytest.fixture
def provider(
    make_processor: Callable[..., NiriZanSpanProcessor],
) -> Iterator[tuple[TracerProvider, NiriZanSpanProcessor]]:
    processor = make_processor()
    tracer_provider = TracerProvider(
        resource=Resource({"service.name": "sdk-service"}), shutdown_on_exit=False
    )
    tracer_provider.add_span_processor(processor)
    yield tracer_provider, processor
    tracer_provider.shutdown()


def test_sdk_nested_spans_become_a_linked_trace(
    provider: tuple[TracerProvider, NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    tracer_provider, _ = provider
    tracer = tracer_provider.get_tracer("app")

    with tracer.start_as_current_span("plan", attributes={NIRIZAN_SPAN_KIND: "planning"}):
        with tracer.start_as_current_span("retrieve", attributes={NIRIZAN_RETRIEVAL_QUERY: "q"}):
            pass
        with tracer.start_as_current_span("generate", attributes={GEN_AI_PROMPT: "p"}):
            pass

    assert tracer_provider.force_flush() is True
    assert len(sink.traces) == 1
    trace = sink.traces[0]
    assert trace.application_name == "sdk-service"
    spans = by_name(trace)
    assert spans["plan"].kind is SpanKind.PLANNING
    assert spans["retrieve"].kind is SpanKind.RETRIEVAL
    assert spans["generate"].kind is SpanKind.GENERATION
    assert spans["plan"].parent_span_id is None
    assert spans["retrieve"].parent_span_id == spans["plan"].span_id
    assert spans["generate"].parent_span_id == spans["plan"].span_id
    assert spans["retrieve"].input_payload == "q"


def test_sdk_exception_is_captured_as_an_error_status(
    provider: tuple[TracerProvider, NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    tracer_provider, _ = provider
    tracer = tracer_provider.get_tracer("app")

    with pytest.raises(ValueError, match="kaboom"):
        with tracer.start_as_current_span("failing", attributes={NIRIZAN_SPAN_KIND: "planning"}):
            raise ValueError("kaboom")

    assert tracer_provider.force_flush() is True
    attrs = sink.traces[0].spans[0].attributes
    assert attrs[OTEL_STATUS_CODE] == "error"
    assert "kaboom" in str(attrs[OTEL_STATUS_DESCRIPTION])


def test_sdk_in_flight_trace_survives_a_force_flush(
    provider: tuple[TracerProvider, NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    tracer_provider, _ = provider
    tracer = tracer_provider.get_tracer("app")

    with tracer.start_as_current_span("root", attributes={NIRIZAN_SPAN_KIND: "planning"}):
        with tracer.start_as_current_span("child", attributes={GEN_AI_PROMPT: "p"}):
            pass
        assert tracer_provider.force_flush() is True  # e.g. a serverless hook mid-request
        assert sink.traces == []

    assert tracer_provider.force_flush() is True
    assert sorted(span_names(sink.traces[0])) == ["child", "root"]


def test_sdk_remote_parent_makes_a_root_even_when_orphans_are_dropped(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor(orphan_policy="drop")
    tracer_provider = TracerProvider(shutdown_on_exit=False)
    tracer_provider.add_span_processor(processor)
    tracer = tracer_provider.get_tracer("app")
    remote = SpanContext(
        trace_id=TRACE_ID,
        span_id=0xABCDEF,
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    context = otel_trace.set_span_in_context(NonRecordingSpan(remote))

    span = tracer.start_span("local-root", context=context, attributes={NIRIZAN_SPAN_KIND: "planning"})
    span.end()

    assert tracer_provider.force_flush() is True
    assert len(sink.traces) == 1
    assert sink.traces[0].spans[0].parent_span_id is None
    assert processor.get_stats() == {}
    tracer_provider.shutdown()


def test_sdk_tuple_attributes_are_encoded_as_sequences(
    provider: tuple[TracerProvider, NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    tracer_provider, _ = provider
    tracer = tracer_provider.get_tracer("app")

    with tracer.start_as_current_span(
        "tagged", attributes={NIRIZAN_SPAN_KIND: "planning", "tags": ["a", "b"]}
    ):
        pass

    assert tracer_provider.force_flush() is True
    attrs = sink.traces[0].spans[0].attributes
    assert json.loads(attrs[f"{SEQ_ATTR_PREFIX}tags"]) == ["a", "b"]


def test_sdk_spans_from_the_nirizan_scope_are_ignored_unless_opted_in(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    ignoring = make_processor()
    ingesting = make_processor(ignore_own_scope=False, sink=RecordingSink())
    tracer_provider = TracerProvider(shutdown_on_exit=False)
    tracer_provider.add_span_processor(ignoring)
    tracer_provider.add_span_processor(ingesting)

    with tracer_provider.get_tracer(NIRIZAN_INSTRUMENTATION_SCOPE).start_as_current_span(
        "exported", attributes={NIRIZAN_SPAN_KIND: "planning"}
    ):
        pass

    assert tracer_provider.force_flush() is True
    assert sink.traces == []
    assert len(ingesting._sink.traces) == 1  # type: ignore[attr-defined]
    tracer_provider.shutdown()


def test_sdk_shutdown_flushes_traces_that_are_still_open(
    make_processor: Callable[..., NiriZanSpanProcessor], sink: RecordingSink
) -> None:
    processor = make_processor()
    tracer_provider = TracerProvider(shutdown_on_exit=False)
    tracer_provider.add_span_processor(processor)
    tracer = tracer_provider.get_tracer("app")

    root = tracer.start_span("root", attributes={NIRIZAN_SPAN_KIND: "planning"})
    context = otel_trace.set_span_in_context(root)
    child = tracer.start_span("child", context=context, attributes={NIRIZAN_SPAN_KIND: "planning"})
    child.end()

    tracer_provider.shutdown()

    assert len(sink.traces) == 1
    assert span_names(sink.traces[0]) == ["child"]
