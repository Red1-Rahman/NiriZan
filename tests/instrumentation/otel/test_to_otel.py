# tests/instrumentation/otel/test_to_otel.py
"""Tests for the NiriZan -> OpenTelemetry exporter (``to_otel.py``).

Strategy
--------
* **Real objects, not mocks.** Inputs are real, validated NiriZan ``Span`` and
  ``Trace`` models, and outputs are checked on real OpenTelemetry spans captured
  by an in-memory exporter behind a real ``TracerProvider``. A mock tracer can
  only confirm that the code calls what the code calls; the real SDK is what
  shows that parenting, trace ids, sampling and status really come out right.
  ``MagicMock`` is used only where a failure has to be injected into the OTel
  side.
* **Expected values are written out, not recomputed.** Attribute names, the
  synthetic parent id and timestamps are literals in the tests, so a change to
  either side of a mapping is a visible diff.
* **Privacy is tested end to end.** A scan of every exported attribute value
  proves that withheld content does not leak through any path.

Categories that do not apply here: persistence and schema migration (nothing is
stored), authentication and authorization.
"""

import pytest

# ``opentelemetry`` is an optional dependency installed via the ``otel`` extra.
# Skip this entire module if it is absent, so a contributor working on other
# parts of NiriZan is never forced to install OpenTelemetry to get a green
# build. CI installs ``nirizan[otel]`` in the job that actually exercises
# the bridge.
pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.sdk")

import asyncio  # noqa: E402
import importlib.metadata  # noqa: E402
import itertools  # noqa: E402
import logging  # noqa: E402
import random  # noqa: E402
from collections.abc import Iterator, Mapping  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import UTC, datetime, timedelta, timezone  # noqa: E402
from typing import Any  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402
from uuid import UUID  # noqa: E402

from opentelemetry import trace as otel_trace  # noqa: E402
from opentelemetry.context import Context  # noqa: E402
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF, ParentBased  # noqa: E402
from opentelemetry.trace import SpanContext, TraceFlags, Tracer  # noqa: E402
from opentelemetry.trace import SpanKind as OTelSpanKind  # noqa: E402
from opentelemetry.trace.status import StatusCode  # noqa: E402
from pydantic import ValidationError  # noqa: E402

import nirizan  # noqa: E402
from nirizan.instrumentation.exporters import BaseExporter  # noqa: E402
from nirizan.instrumentation.otel import to_otel  # noqa: E402
from nirizan.instrumentation.otel._id_mapping import uuid_to_otel_trace_id  # noqa: E402
from nirizan.instrumentation.otel.from_otel import _ns_to_datetime  # noqa: E402
from nirizan.instrumentation.otel.semconv import (  # noqa: E402
    GEN_AI_COMPLETION,
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROMPT,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_COMPLETION_TOKENS,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    GEN_AI_USAGE_PROMPT_TOKENS,
    ID_SOURCE_DERIVED,
    ID_SOURCE_ROUNDTRIP,
    MAX_ATTR_VALUE_LENGTH,
    NIRIZAN_INSTRUMENTATION_SCOPE,
    NIRIZAN_RETRIEVAL_QUERY,
    NIRIZAN_RETRIEVAL_TOP_K,
    NIRIZAN_SESSION_ID,
    NIRIZAN_SPAN_ID,
    NIRIZAN_SPAN_ID_SOURCE,
    NIRIZAN_SPAN_KIND,
    NIRIZAN_TOOL_NAME,
    NIRIZAN_TRACE_ID,
    NIRIZAN_TRACE_ID_SOURCE,
    OTEL_STATUS_CODE,
    OTEL_STATUS_DESCRIPTION,
    SEQ_ATTR_PREFIX,
)
from nirizan.instrumentation.otel.to_otel import (  # noqa: E402
    NiriZanToOTelExporter,
    OTelExporterConfig,
    _format_payload_value,
    _get_default_tracer,
    _status_from_attributes,
    _to_nanoseconds,
    _topological_sort_spans,
    convert_span_to_otel_attributes,
    export_span_to_otel,
    export_trace_to_otel,
)
from nirizan.instrumentation.spans import Span, SpanKind, Trace  # noqa: E402
from nirizan.instrumentation.tracer import Tracer as NiriZanTracer  # noqa: E402

_MODULE_LOGGER = "nirizan.instrumentation.otel.to_otel"

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

TRACE_UUID = UUID("87654321-4321-8765-4321-876543218765")
START = datetime(2024, 1, 1, tzinfo=UTC)
CONTENT_ON = OTelExporterConfig(capture_content=True)

# Written out on purpose: these names are the contract with OpenTelemetry backends.
EXPECTED_PAYLOAD_KEYS: dict[SpanKind, tuple[str, str]] = {
    SpanKind.GENERATION: ("gen_ai.prompt", "gen_ai.completion"),
    SpanKind.RETRIEVAL: ("nirizan.retrieval.query", "nirizan.retrieval.results"),
    SpanKind.TOOL_USE: ("nirizan.tool.arguments", "nirizan.tool.result"),
    SpanKind.PLANNING: ("nirizan.planning.context", "nirizan.planning.output"),
}
ALL_CONTENT_KEYS = {key for pair in EXPECTED_PAYLOAD_KEYS.values() for key in pair}

_ids = itertools.count(1_000)


def next_id() -> UUID:
    return UUID(int=next(_ids))


def nspan(
    *,
    name: str = "span",
    kind: SpanKind = SpanKind.GENERATION,
    span_id: UUID | None = None,
    parent: UUID | None = None,
    trace_id: UUID = TRACE_UUID,
    started_at: datetime = START,
    ended_at: datetime | None = None,
    attributes: Mapping[str, str | int | float | bool] | None = None,
    input_payload: str | None = None,
    output_payload: str | None = None,
) -> Span:
    """A real, validated NiriZan ``Span`` with predictable defaults."""
    return Span(
        span_id=span_id or next_id(),
        trace_id=trace_id,
        parent_span_id=parent,
        kind=kind,
        name=name,
        started_at=started_at,
        ended_at=ended_at or started_at + timedelta(seconds=1),
        attributes=dict(attributes or {}),
        input_payload=input_payload,
        output_payload=output_payload,
    )


def ntrace(
    *spans: Span, session_id: UUID | None = None, trace_id: UUID = TRACE_UUID
) -> Trace:
    return Trace(
        trace_id=trace_id,
        application_name="test-app",
        spans=list(spans),
        created_at=START,
        session_id=session_id,
    )


@dataclass
class OTel:
    """A real tracer provider whose finished spans can be inspected."""

    provider: TracerProvider
    memory: InMemorySpanExporter
    tracer: Tracer

    def spans(self) -> list[ReadableSpan]:
        return list(self.memory.get_finished_spans())

    def by_name(self) -> dict[str, ReadableSpan]:
        return {s.name: s for s in self.spans()}

    def by_nirizan_id(self) -> dict[str, ReadableSpan]:
        return {str(s.attributes[NIRIZAN_SPAN_ID]): s for s in self.spans() if s.attributes}


def _make_otel(**provider_kwargs: Any) -> OTel:
    memory = InMemorySpanExporter()
    provider = TracerProvider(shutdown_on_exit=False, **provider_kwargs)
    provider.add_span_processor(SimpleSpanProcessor(memory))
    return OTel(provider, memory, provider.get_tracer(NIRIZAN_INSTRUMENTATION_SCOPE))


@pytest.fixture
def otel() -> Iterator[OTel]:
    sdk = _make_otel()
    yield sdk
    sdk.provider.shutdown()


def span_context_of(span: ReadableSpan) -> SpanContext:
    ctx = span.get_span_context()
    assert ctx is not None
    return ctx


def attr_values(spans: list[ReadableSpan]) -> list[str]:
    return [str(v) for s in spans for v in (s.attributes or {}).values()]


# ===========================================================================
# OTelExporterConfig
# ===========================================================================


def test_config_defaults_are_privacy_first_and_backward_compatible() -> None:
    config = OTelExporterConfig()

    assert config.capture_content is False
    assert config.emit_legacy_attributes is True
    assert config.link_roots_to_trace_id is True


def test_config_is_immutable() -> None:
    config = OTelExporterConfig()
    field = "capture_content"
    with pytest.raises(ValidationError):
        setattr(config, field, True)


@pytest.mark.parametrize(
    "kwargs",
    [{"capture_content": "yes"}, {"capture_content": 1}, {"emit_legacy_attributes": None}],
    ids=["str", "int", "none"],
)
def test_config_is_strict_about_types(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        OTelExporterConfig(**kwargs)


def test_config_rejects_unknown_settings_so_typos_are_not_silently_ignored() -> None:
    with pytest.raises(ValidationError):
        OTelExporterConfig(capture_contents=True)  # type: ignore[call-arg]


def test_exporter_exposes_the_config_it_was_built_with() -> None:
    config = OTelExporterConfig(capture_content=True)

    assert NiriZanToOTelExporter(tracer=MagicMock(), config=config).config == config
    assert NiriZanToOTelExporter(tracer=MagicMock()).config == OTelExporterConfig()


# ===========================================================================
# Timestamps
# ===========================================================================


def test_to_nanoseconds_returns_none_for_none() -> None:
    assert _to_nanoseconds(None) is None


def test_to_nanoseconds_passes_through_an_int() -> None:
    assert _to_nanoseconds(1000) == 1000


@pytest.mark.parametrize("value", ["invalid", 1.5, True, False, b"1", [1]])
def test_to_nanoseconds_returns_none_for_unsupported_types(value: object) -> None:
    assert _to_nanoseconds(value) is None  # type: ignore[arg-type]


def test_to_nanoseconds_treats_a_naive_datetime_as_utc() -> None:
    assert _to_nanoseconds(datetime(2020, 1, 1)) == 1_577_836_800_000_000_000


def test_to_nanoseconds_converts_an_aware_datetime() -> None:
    assert _to_nanoseconds(datetime(2020, 1, 1, tzinfo=UTC)) == 1_577_836_800_000_000_000


def test_to_nanoseconds_is_exact_for_microseconds() -> None:
    """Regression: float math (``timestamp() * 1e9``) loses the microsecond digits.

    The expected value is built without the code under test and without floats
    for the sub-second part.
    """
    moment = datetime(2026, 9, 25, 12, 34, 56, 789_123, tzinfo=UTC)
    expected = int(moment.replace(microsecond=0).timestamp()) * 10**9 + 789_123_000

    assert _to_nanoseconds(moment) == expected
    assert _to_nanoseconds(moment) % 1_000 == 0  # type: ignore[operator]


def test_to_nanoseconds_handles_times_before_the_epoch() -> None:
    assert _to_nanoseconds(datetime(1969, 12, 31, 23, 59, 59, 500_000, tzinfo=UTC)) == -500_000_000


def test_to_nanoseconds_honors_the_timezone_offset() -> None:
    plus_530 = timezone(timedelta(hours=5, minutes=30))

    assert _to_nanoseconds(datetime(2020, 1, 1, 5, 30, tzinfo=plus_530)) == _to_nanoseconds(
        datetime(2020, 1, 1, tzinfo=UTC)
    )


def test_to_nanoseconds_round_trips_through_the_ingest_conversion() -> None:
    """Export then ingest returns the original instant at microsecond precision."""
    rng = random.Random(5)
    for _ in range(200):
        moment = datetime(2000, 1, 1, tzinfo=UTC) + timedelta(
            seconds=rng.randrange(0, 900_000_000), microseconds=rng.randrange(0, 1_000_000)
        )
        assert _ns_to_datetime(_to_nanoseconds(moment)) == moment


# ===========================================================================
# Payload formatting
# ===========================================================================


def test_format_payload_value_passes_none_through() -> None:
    assert _format_payload_value(None) is None


def test_format_payload_value_leaves_short_text_alone() -> None:
    assert _format_payload_value("hello") == "hello"
    assert _format_payload_value("") == ""


def test_format_payload_value_truncates_at_the_attribute_limit() -> None:
    exactly = "a" * MAX_ATTR_VALUE_LENGTH
    over = "a" * (MAX_ATTR_VALUE_LENGTH + 1)

    assert _format_payload_value(exactly) == exactly
    result = _format_payload_value(over)
    assert result is not None
    assert len(result) == MAX_ATTR_VALUE_LENGTH
    assert result.endswith("...[truncated]")


def test_format_payload_value_preserves_non_ascii_text() -> None:
    assert _format_payload_value("আপনি কেমন আছেন?") == "আপনি কেমন আছেন?"


# ===========================================================================
# Attribute mapping: identifiers, kind, provenance, session
# ===========================================================================


def test_attributes_always_carry_identifiers_kind_and_provenance() -> None:
    span = nspan(kind=SpanKind.PLANNING)

    attrs = convert_span_to_otel_attributes(span)

    assert attrs[NIRIZAN_SPAN_ID] == str(span.span_id)
    assert attrs[NIRIZAN_TRACE_ID] == str(span.trace_id)
    assert attrs[NIRIZAN_SPAN_KIND] == "planning"
    assert attrs[NIRIZAN_SPAN_ID_SOURCE] == "roundtrip"
    assert attrs[NIRIZAN_TRACE_ID_SOURCE] == "roundtrip"
    assert NIRIZAN_SESSION_ID not in attrs


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (SpanKind.PLANNING, "planning"),
        (SpanKind.RETRIEVAL, "retrieval"),
        (SpanKind.TOOL_USE, "tool_use"),
        (SpanKind.GENERATION, "generation"),
    ],
)
def test_attributes_name_every_span_kind(kind: SpanKind, expected: str) -> None:
    assert convert_span_to_otel_attributes(nspan(kind=kind))[NIRIZAN_SPAN_KIND] == expected


def test_span_kind_table_covers_every_span_kind() -> None:
    """Drift guard: a new ``SpanKind`` must get a payload mapping and tests."""
    assert set(EXPECTED_PAYLOAD_KEYS) == set(SpanKind)
    assert set(to_otel._PAYLOAD_ATTRIBUTES) == set(SpanKind)


def test_attributes_propagate_a_derived_provenance_marker() -> None:
    span = nspan(
        attributes={
            NIRIZAN_SPAN_ID_SOURCE: ID_SOURCE_DERIVED,
            NIRIZAN_TRACE_ID_SOURCE: ID_SOURCE_DERIVED,
        }
    )

    attrs = convert_span_to_otel_attributes(span)

    assert attrs[NIRIZAN_SPAN_ID_SOURCE] == "derived"
    assert attrs[NIRIZAN_TRACE_ID_SOURCE] == "derived"


@pytest.mark.parametrize("junk", ["bogus", "", 7, True])
def test_attributes_treat_unknown_provenance_as_roundtrip(junk: str | int | bool) -> None:
    span = nspan(attributes={NIRIZAN_SPAN_ID_SOURCE: junk, NIRIZAN_TRACE_ID_SOURCE: junk})

    attrs = convert_span_to_otel_attributes(span)

    assert attrs[NIRIZAN_SPAN_ID_SOURCE] == ID_SOURCE_ROUNDTRIP
    assert attrs[NIRIZAN_TRACE_ID_SOURCE] == ID_SOURCE_ROUNDTRIP


def test_attributes_carry_the_session_id_as_text() -> None:
    session = UUID("12345678-1234-5678-1234-567812345678")

    from_uuid = convert_span_to_otel_attributes(nspan(), session_id=session)
    from_str = convert_span_to_otel_attributes(nspan(), session_id="sess_123")

    assert from_uuid[NIRIZAN_SESSION_ID] == "12345678-1234-5678-1234-567812345678"
    assert from_str[NIRIZAN_SESSION_ID] == "sess_123"


@pytest.mark.parametrize("empty", [None, ""])
def test_attributes_omit_an_absent_session_id(empty: str | None) -> None:
    assert NIRIZAN_SESSION_ID not in convert_span_to_otel_attributes(nspan(), session_id=empty)


def test_attributes_are_always_valid_otel_attribute_values() -> None:
    span = nspan(
        kind=SpanKind.GENERATION,
        attributes={"s": "v", "i": 1, "f": 1.5, "b": True, "model": "m", "prompt_tokens": 3},
        input_payload="p",
        output_payload="c",
    )

    attrs = convert_span_to_otel_attributes(span, config=CONTENT_ON)

    assert all(isinstance(v, (str, int, float, bool)) for v in attrs.values())


# ===========================================================================
# Attribute mapping: content is opt-in
# ===========================================================================


@pytest.mark.parametrize("kind", list(SpanKind))
def test_content_is_not_exported_by_default(kind: SpanKind) -> None:
    span = nspan(kind=kind, input_payload="SECRET-IN", output_payload="SECRET-OUT")

    attrs = convert_span_to_otel_attributes(span)

    assert not (ALL_CONTENT_KEYS & set(attrs))
    assert not any("SECRET" in str(v) for v in attrs.values())


@pytest.mark.parametrize("kind", list(SpanKind))
def test_content_is_exported_when_capture_is_on(kind: SpanKind) -> None:
    in_key, out_key = EXPECTED_PAYLOAD_KEYS[kind]
    span = nspan(kind=kind, input_payload="the input", output_payload="the output")

    attrs = convert_span_to_otel_attributes(span, config=CONTENT_ON)

    assert attrs[in_key] == "the input"
    assert attrs[out_key] == "the output"


@pytest.mark.parametrize("kind", list(SpanKind))
def test_content_attributes_are_omitted_for_missing_payloads(kind: SpanKind) -> None:
    in_key, out_key = EXPECTED_PAYLOAD_KEYS[kind]

    only_input = convert_span_to_otel_attributes(nspan(kind=kind, input_payload="i"), config=CONTENT_ON)
    only_output = convert_span_to_otel_attributes(nspan(kind=kind, output_payload="o"), config=CONTENT_ON)
    neither = convert_span_to_otel_attributes(nspan(kind=kind), config=CONTENT_ON)

    assert in_key in only_input and out_key not in only_input
    assert out_key in only_output and in_key not in only_output
    assert not (ALL_CONTENT_KEYS & set(neither))


def test_content_is_truncated_and_keeps_non_ascii_text() -> None:
    span = nspan(input_payload="আ" * (MAX_ATTR_VALUE_LENGTH + 5), output_payload="কেমন আছেন")

    attrs = convert_span_to_otel_attributes(span, config=CONTENT_ON)

    assert len(str(attrs[GEN_AI_PROMPT])) == MAX_ATTR_VALUE_LENGTH
    assert attrs[GEN_AI_COMPLETION] == "কেমন আছেন"


def test_structure_is_exported_even_when_content_is_withheld() -> None:
    generation = nspan(
        kind=SpanKind.GENERATION,
        attributes={"provider": "openai", "model": "gpt-4", "prompt_tokens": 10},
        input_payload="SECRET",
    )
    tool = nspan(kind=SpanKind.TOOL_USE, attributes={"tool_name": "search"}, input_payload="SECRET")
    retrieval = nspan(kind=SpanKind.RETRIEVAL, attributes={"top_k": 5}, input_payload="SECRET")

    assert convert_span_to_otel_attributes(generation)[GEN_AI_REQUEST_MODEL] == "gpt-4"
    assert convert_span_to_otel_attributes(generation)[GEN_AI_USAGE_INPUT_TOKENS] == 10
    assert convert_span_to_otel_attributes(tool)[NIRIZAN_TOOL_NAME] == "search"
    assert convert_span_to_otel_attributes(retrieval)[NIRIZAN_RETRIEVAL_TOP_K] == 5


def test_withheld_content_does_not_leak_through_copied_span_attributes() -> None:
    """Spans ingested from OTel carry ``gen_ai.prompt`` and friends as plain attributes.

    With capture off those must be withheld too, in plain and in sequence-encoded
    form, or the opt-in would not protect anything on a round trip.
    """
    span = nspan(
        attributes={
            GEN_AI_PROMPT: "SECRET-PROMPT",
            NIRIZAN_RETRIEVAL_QUERY: "SECRET-QUERY",
            f"{SEQ_ATTR_PREFIX}{GEN_AI_COMPLETION}": '["SECRET-LIST"]',
            "http.method": "GET",
        },
    )

    withheld = convert_span_to_otel_attributes(span)
    allowed = convert_span_to_otel_attributes(span, config=CONTENT_ON)

    assert not any("SECRET" in str(v) for v in withheld.values())
    assert withheld["http.method"] == "GET"
    assert allowed[GEN_AI_PROMPT] == "SECRET-PROMPT"
    assert allowed[f"{SEQ_ATTR_PREFIX}{GEN_AI_COMPLETION}"] == '["SECRET-LIST"]'


def test_only_well_known_content_keys_are_withheld() -> None:
    span = nspan(attributes={"prompt": "user-defined-key", "gen_ai.prompt.extra": "other"})

    attrs = convert_span_to_otel_attributes(span)

    assert attrs["prompt"] == "user-defined-key"
    assert attrs["gen_ai.prompt.extra"] == "other"


# ===========================================================================
# Attribute mapping: generation
# ===========================================================================


def test_generation_maps_provider_model_tokens_and_operation() -> None:
    span = nspan(
        attributes={
            "provider": "openai",
            "model_name": "gpt-4",
            "prompt_tokens": 10,
            "completion_tokens": 20,
        }
    )

    attrs = convert_span_to_otel_attributes(span)

    assert attrs[GEN_AI_PROVIDER_NAME] == "openai"
    assert attrs[GEN_AI_SYSTEM] == "openai"
    assert attrs[GEN_AI_REQUEST_MODEL] == "gpt-4"
    assert attrs[GEN_AI_RESPONSE_MODEL] == "gpt-4"
    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 10
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 20
    assert attrs[GEN_AI_USAGE_PROMPT_TOKENS] == 10
    assert attrs[GEN_AI_USAGE_COMPLETION_TOKENS] == 20
    assert attrs[GEN_AI_OPERATION_NAME] == "chat"


def test_generation_legacy_names_can_be_switched_off() -> None:
    span = nspan(attributes={"provider": "openai", "prompt_tokens": 10, "completion_tokens": 20})

    attrs = convert_span_to_otel_attributes(
        span, config=OTelExporterConfig(emit_legacy_attributes=False)
    )

    assert attrs[GEN_AI_PROVIDER_NAME] == "openai"
    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 10
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 20
    assert GEN_AI_SYSTEM not in attrs
    assert GEN_AI_USAGE_PROMPT_TOKENS not in attrs
    assert GEN_AI_USAGE_COMPLETION_TOKENS not in attrs


def test_generation_zero_token_counts_are_exported() -> None:
    """Regression: an ``or`` chain treated 0 as missing, so a zero-token call reported no usage."""
    attrs = convert_span_to_otel_attributes(
        nspan(attributes={"prompt_tokens": 0, "completion_tokens": 0})
    )

    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 0
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 0
    assert attrs[GEN_AI_USAGE_PROMPT_TOKENS] == 0
    assert attrs[GEN_AI_USAGE_COMPLETION_TOKENS] == 0


def test_generation_zero_is_not_skipped_in_favor_of_a_later_key() -> None:
    attrs = convert_span_to_otel_attributes(
        nspan(attributes={"prompt_tokens": 0, GEN_AI_USAGE_INPUT_TOKENS: 99})
    )

    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 0


def test_generation_reads_the_canonical_token_names_written_by_ingest() -> None:
    attrs = convert_span_to_otel_attributes(
        nspan(attributes={GEN_AI_USAGE_INPUT_TOKENS: 7, GEN_AI_USAGE_OUTPUT_TOKENS: 9})
    )

    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 7
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 9
    assert attrs[GEN_AI_USAGE_PROMPT_TOKENS] == 7
    assert attrs[GEN_AI_USAGE_COMPLETION_TOKENS] == 9


def test_generation_reads_the_legacy_token_names_too() -> None:
    attrs = convert_span_to_otel_attributes(
        nspan(attributes={GEN_AI_USAGE_PROMPT_TOKENS: 3, GEN_AI_USAGE_COMPLETION_TOKENS: 4})
    )

    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 3
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 4


def test_generation_token_precedence_is_short_name_then_canonical_then_legacy() -> None:
    attrs = convert_span_to_otel_attributes(
        nspan(
            attributes={
                "prompt_tokens": 1,
                GEN_AI_USAGE_INPUT_TOKENS: 2,
                GEN_AI_USAGE_PROMPT_TOKENS: 3,
            }
        )
    )

    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 1


@pytest.mark.parametrize("bad", [True, False, 1.5, "10"])
def test_generation_ignores_token_values_that_are_not_integers(bad: bool | float | str) -> None:
    attrs = convert_span_to_otel_attributes(nspan(attributes={"prompt_tokens": bad}))

    assert GEN_AI_USAGE_INPUT_TOKENS not in attrs
    assert GEN_AI_USAGE_PROMPT_TOKENS not in attrs


def test_generation_omits_usage_provider_and_model_when_unknown() -> None:
    attrs = convert_span_to_otel_attributes(nspan())

    for key in (
        GEN_AI_PROVIDER_NAME,
        GEN_AI_SYSTEM,
        GEN_AI_REQUEST_MODEL,
        GEN_AI_RESPONSE_MODEL,
        GEN_AI_USAGE_INPUT_TOKENS,
        GEN_AI_USAGE_OUTPUT_TOKENS,
    ):
        assert key not in attrs
    assert attrs[GEN_AI_OPERATION_NAME] == "chat"


@pytest.mark.parametrize("source_key", ["provider", GEN_AI_PROVIDER_NAME, GEN_AI_SYSTEM])
def test_generation_reads_the_provider_from_any_known_key(source_key: str) -> None:
    attrs = convert_span_to_otel_attributes(nspan(attributes={source_key: "anthropic"}))

    assert attrs[GEN_AI_PROVIDER_NAME] == "anthropic"
    assert attrs[GEN_AI_SYSTEM] == "anthropic"


@pytest.mark.parametrize("source_key", ["model_name", "model", GEN_AI_REQUEST_MODEL])
def test_generation_reads_the_model_from_any_known_key(source_key: str) -> None:
    attrs = convert_span_to_otel_attributes(nspan(attributes={source_key: "gpt-4"}))

    assert attrs[GEN_AI_REQUEST_MODEL] == "gpt-4"
    assert attrs[GEN_AI_RESPONSE_MODEL] == "gpt-4"


def test_generation_keeps_a_distinct_response_model_when_known() -> None:
    attrs = convert_span_to_otel_attributes(
        nspan(attributes={"model": "gpt-4", GEN_AI_RESPONSE_MODEL: "gpt-4-0613"})
    )

    assert attrs[GEN_AI_REQUEST_MODEL] == "gpt-4"
    assert attrs[GEN_AI_RESPONSE_MODEL] == "gpt-4-0613"


def test_generation_operation_name_can_be_set_by_the_span() -> None:
    attrs = convert_span_to_otel_attributes(nspan(attributes={GEN_AI_OPERATION_NAME: "embeddings"}))

    assert attrs[GEN_AI_OPERATION_NAME] == "embeddings"


@pytest.mark.parametrize("kind", [SpanKind.RETRIEVAL, SpanKind.TOOL_USE, SpanKind.PLANNING])
def test_generation_attributes_are_only_added_to_generation_spans(kind: SpanKind) -> None:
    attrs = convert_span_to_otel_attributes(
        nspan(kind=kind, attributes={"model": "gpt-4", "prompt_tokens": 1})
    )

    assert GEN_AI_OPERATION_NAME not in attrs
    assert GEN_AI_USAGE_INPUT_TOKENS not in attrs


# ===========================================================================
# Attribute mapping: retrieval and tool use
# ===========================================================================


@pytest.mark.parametrize("source_key", ["top_k", NIRIZAN_RETRIEVAL_TOP_K])
def test_retrieval_top_k_is_read_from_either_key(source_key: str) -> None:
    attrs = convert_span_to_otel_attributes(nspan(kind=SpanKind.RETRIEVAL, attributes={source_key: 5}))

    assert attrs[NIRIZAN_RETRIEVAL_TOP_K] == 5


def test_retrieval_top_k_of_zero_is_exported() -> None:
    attrs = convert_span_to_otel_attributes(nspan(kind=SpanKind.RETRIEVAL, attributes={"top_k": 0}))

    assert attrs[NIRIZAN_RETRIEVAL_TOP_K] == 0


@pytest.mark.parametrize("bad", [True, 2.5, "5"])
def test_retrieval_top_k_must_be_an_integer(bad: bool | float | str) -> None:
    attrs = convert_span_to_otel_attributes(nspan(kind=SpanKind.RETRIEVAL, attributes={"top_k": bad}))

    assert NIRIZAN_RETRIEVAL_TOP_K not in attrs  # not mapped to the semantic attribute...
    assert attrs["top_k"] == bad  # ...but still carried over as the span's own attribute


@pytest.mark.parametrize("source_key", ["tool_name", "name", NIRIZAN_TOOL_NAME])
def test_tool_name_is_read_from_any_known_key(source_key: str) -> None:
    attrs = convert_span_to_otel_attributes(
        nspan(kind=SpanKind.TOOL_USE, attributes={source_key: "search"})
    )

    assert attrs[NIRIZAN_TOOL_NAME] == "search"


def test_tool_name_is_absent_when_unknown() -> None:
    assert NIRIZAN_TOOL_NAME not in convert_span_to_otel_attributes(nspan(kind=SpanKind.TOOL_USE))


# ===========================================================================
# Attribute mapping: carried-over attributes
# ===========================================================================


def test_other_attributes_are_carried_over_with_their_types() -> None:
    span = nspan(attributes={"s": "v", "i": 3, "f": 1.5, "b": True, "z": 0, "e": ""})

    attrs = convert_span_to_otel_attributes(span)

    assert attrs["s"] == "v"
    assert attrs["i"] == 3 and isinstance(attrs["i"], int) and not isinstance(attrs["i"], bool)
    assert attrs["f"] == 1.5
    assert attrs["b"] is True
    assert attrs["z"] == 0
    assert attrs["e"] == ""


def test_long_attribute_strings_are_truncated() -> None:
    attrs = convert_span_to_otel_attributes(nspan(attributes={"note": "x" * (MAX_ATTR_VALUE_LENGTH + 50)}))

    assert len(str(attrs["note"])) == MAX_ATTR_VALUE_LENGTH
    assert str(attrs["note"]).endswith("...[truncated]")


def test_sequence_encoded_attributes_pass_through_unchanged() -> None:
    span = nspan(attributes={f"{SEQ_ATTR_PREFIX}tags": '["a", "b"]'})

    assert convert_span_to_otel_attributes(span)[f"{SEQ_ATTR_PREFIX}tags"] == '["a", "b"]'


def test_non_ascii_attribute_values_are_preserved() -> None:
    attrs = convert_span_to_otel_attributes(nspan(attributes={"greeting": "আপনি কেমন আছেন?"}))

    assert attrs["greeting"] == "আপনি কেমন আছেন?"


def test_an_attribute_cannot_overwrite_a_computed_one() -> None:
    span = nspan(
        kind=SpanKind.GENERATION,
        attributes={
            NIRIZAN_SPAN_ID: "spoofed",
            NIRIZAN_TRACE_ID: "spoofed",
            NIRIZAN_SPAN_KIND: "spoofed",
            GEN_AI_OPERATION_NAME: "chat",
        },
        input_payload="the prompt",
    )

    attrs = convert_span_to_otel_attributes(span, config=CONTENT_ON)

    assert attrs[NIRIZAN_SPAN_ID] == str(span.span_id)
    assert attrs[NIRIZAN_TRACE_ID] == str(span.trace_id)
    assert attrs[NIRIZAN_SPAN_KIND] == "generation"
    assert attrs[GEN_AI_PROMPT] == "the prompt"


def test_conversion_does_not_mutate_the_span() -> None:
    span = nspan(attributes={"model": "m", "n": 1}, input_payload="p")
    before = (dict(span.attributes), span.input_payload, span.model_dump())

    convert_span_to_otel_attributes(span, config=CONTENT_ON)

    assert (dict(span.attributes), span.input_payload, span.model_dump()) == before


def test_conversion_is_idempotent() -> None:
    span = nspan(attributes={"model": "m"}, input_payload="p", output_payload="c")

    assert convert_span_to_otel_attributes(span, config=CONTENT_ON) == convert_span_to_otel_attributes(
        span, config=CONTENT_ON
    )


# ===========================================================================
# Status
# ===========================================================================


@pytest.mark.parametrize(
    ("attrs", "code", "description"),
    [
        ({OTEL_STATUS_CODE: "error", OTEL_STATUS_DESCRIPTION: "boom"}, StatusCode.ERROR, "boom"),
        ({OTEL_STATUS_CODE: "ERROR", OTEL_STATUS_DESCRIPTION: "boom"}, StatusCode.ERROR, "boom"),
        ({OTEL_STATUS_CODE: "error"}, StatusCode.ERROR, None),
        ({OTEL_STATUS_CODE: "error", OTEL_STATUS_DESCRIPTION: ""}, StatusCode.ERROR, None),
        ({OTEL_STATUS_CODE: "error", OTEL_STATUS_DESCRIPTION: 5}, StatusCode.ERROR, None),
        ({OTEL_STATUS_CODE: "ok"}, StatusCode.OK, None),
        ({OTEL_STATUS_CODE: "Ok", OTEL_STATUS_DESCRIPTION: "ignored"}, StatusCode.OK, None),
    ],
    ids=["error", "error-upper", "error-no-desc", "error-empty-desc", "error-bad-desc", "ok", "ok-desc"],
)
def test_status_is_rebuilt_from_the_captured_otel_attributes(
    attrs: dict[str, str | int], code: StatusCode, description: str | None
) -> None:
    status = _status_from_attributes(attrs)

    assert status is not None
    assert status.status_code == code
    assert status.description == description


@pytest.mark.parametrize(
    "attrs",
    [{}, {OTEL_STATUS_CODE: "unset"}, {OTEL_STATUS_CODE: "bogus"}, {OTEL_STATUS_CODE: 3}, {OTEL_STATUS_CODE: True}],
    ids=["absent", "unset", "unknown", "int", "bool"],
)
def test_no_status_is_set_for_unset_unknown_or_malformed_codes(attrs: dict[str, str | int | bool]) -> None:
    assert _status_from_attributes(attrs) is None


# ===========================================================================
# export_span_to_otel
# ===========================================================================


def test_export_span_produces_a_real_otel_span_with_the_expected_fields(otel: OTel) -> None:
    span = nspan(
        name="my-span",
        kind=SpanKind.GENERATION,
        started_at=datetime(2024, 1, 1, 0, 0, 0, 123_456, tzinfo=UTC),
        ended_at=datetime(2024, 1, 1, 0, 0, 2, 654_321, tzinfo=UTC),
        attributes={"model": "gpt-4"},
        input_payload="prompt",
        output_payload="completion",
    )

    result = export_span_to_otel(span, tracer=otel.tracer, config=CONTENT_ON)

    [exported] = otel.spans()
    assert result.get_span_context() == exported.get_span_context()
    assert exported.name == "my-span"
    assert exported.start_time == 1_704_067_200_123_456_000
    assert exported.end_time == 1_704_067_202_654_321_000
    assert exported.kind is OTelSpanKind.INTERNAL
    assert exported.instrumentation_scope is not None
    assert exported.instrumentation_scope.name == "nirizan"
    assert exported.attributes is not None
    assert exported.attributes[GEN_AI_PROMPT] == "prompt"
    assert exported.attributes[GEN_AI_COMPLETION] == "completion"
    assert exported.attributes[GEN_AI_REQUEST_MODEL] == "gpt-4"


def test_export_span_without_a_parent_starts_a_new_trace(otel: OTel) -> None:
    export_span_to_otel(nspan(), tracer=otel.tracer)

    [exported] = otel.spans()
    assert exported.parent is None
    assert span_context_of(exported).is_valid


def test_export_span_never_attaches_to_the_active_otel_span(otel: OTel) -> None:
    """Parenting is explicit: the result must not depend on where the export is called from."""
    ambient_tracer = otel.provider.get_tracer("app")

    with ambient_tracer.start_as_current_span("ambient") as ambient:
        export_span_to_otel(nspan(name="exported"), tracer=otel.tracer)

    exported = otel.by_name()["exported"]
    assert exported.parent is None
    assert span_context_of(exported).trace_id != ambient.get_span_context().trace_id


def test_export_span_links_to_the_given_parent_context(otel: OTel) -> None:
    parent = SpanContext(
        trace_id=0x1234567890ABCDEF1234567890ABCDEF,
        span_id=0xABC,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )

    export_span_to_otel(nspan(name="child"), tracer=otel.tracer, parent_context=parent)

    exported = otel.by_name()["child"]
    assert exported.parent is not None and exported.parent.span_id == 0xABC
    assert span_context_of(exported).trace_id == 0x1234567890ABCDEF1234567890ABCDEF


def test_export_span_warns_when_a_declared_parent_has_no_context(
    otel: OTel, caplog: pytest.LogCaptureFixture
) -> None:
    missing_parent = next_id()
    span = nspan(name="child", parent=missing_parent)

    with caplog.at_level(logging.WARNING, logger=_MODULE_LOGGER):
        export_span_to_otel(span, tracer=otel.tracer)

    assert any(str(missing_parent) in r.getMessage() for r in caplog.records)
    assert otel.by_name()["child"].parent is None


def test_export_span_passes_the_session_id_through(otel: OTel) -> None:
    session = UUID("12345678-1234-5678-1234-567812345678")

    export_span_to_otel(nspan(), tracer=otel.tracer, session_id=session)

    [exported] = otel.spans()
    assert exported.attributes is not None
    assert exported.attributes[NIRIZAN_SESSION_ID] == str(session)


def test_export_span_rebuilds_error_status_from_attributes(otel: OTel) -> None:
    span = nspan(attributes={OTEL_STATUS_CODE: "error", OTEL_STATUS_DESCRIPTION: "upstream failed"})

    export_span_to_otel(span, tracer=otel.tracer)

    [exported] = otel.spans()
    assert exported.status.status_code is StatusCode.ERROR
    assert exported.status.description == "upstream failed"


def test_export_span_rebuilds_ok_status_and_leaves_others_unset(otel: OTel) -> None:
    export_span_to_otel(nspan(name="ok", attributes={OTEL_STATUS_CODE: "ok"}), tracer=otel.tracer)
    export_span_to_otel(nspan(name="plain"), tracer=otel.tracer)
    export_span_to_otel(nspan(name="unset", attributes={OTEL_STATUS_CODE: "unset"}), tracer=otel.tracer)

    spans = otel.by_name()
    assert spans["ok"].status.status_code is StatusCode.OK
    assert spans["plain"].status.status_code is StatusCode.UNSET
    assert spans["unset"].status.status_code is StatusCode.UNSET


def test_export_span_always_ends_the_span_even_if_setting_the_status_fails() -> None:
    otel_span = MagicMock()
    otel_span.set_status.side_effect = RuntimeError("status failure")
    tracer = MagicMock()
    tracer.start_span.return_value = otel_span
    span = nspan(
        ended_at=datetime(2024, 1, 1, 0, 0, 5, tzinfo=UTC),
        attributes={OTEL_STATUS_CODE: "error"},
    )

    with pytest.raises(RuntimeError, match="status failure"):
        export_span_to_otel(span, tracer=tracer)

    otel_span.end.assert_called_once_with(end_time=1_704_067_205_000_000_000)


def test_export_span_ends_the_span_exactly_once_with_its_end_time() -> None:
    otel_span = MagicMock()
    tracer = MagicMock()
    tracer.start_span.return_value = otel_span

    export_span_to_otel(nspan(ended_at=datetime(2024, 1, 1, 0, 0, 5, tzinfo=UTC)), tracer=tracer)

    otel_span.end.assert_called_once_with(end_time=1_704_067_205_000_000_000)


def test_export_span_hands_the_tracer_an_explicit_empty_context() -> None:
    tracer = MagicMock()

    export_span_to_otel(nspan(), tracer=tracer)

    assert tracer.start_span.call_args.kwargs["context"] == Context()


def test_export_span_propagates_a_tracer_failure_to_its_caller() -> None:
    """Only the exporter class isolates failures; the function reports them."""
    tracer = MagicMock()
    tracer.start_span.side_effect = RuntimeError("tracer is broken")

    with pytest.raises(RuntimeError, match="tracer is broken"):
        export_span_to_otel(nspan(), tracer=tracer)


def test_export_span_honors_the_content_setting(otel: OTel) -> None:
    export_span_to_otel(nspan(name="a", input_payload="SECRET"), tracer=otel.tracer)
    export_span_to_otel(nspan(name="b", input_payload="SECRET"), tracer=otel.tracer, config=CONTENT_ON)

    spans = otel.by_name()
    assert GEN_AI_PROMPT not in (spans["a"].attributes or {})
    assert (spans["b"].attributes or {})[GEN_AI_PROMPT] == "SECRET"


# ===========================================================================
# Default tracer
# ===========================================================================


def test_default_tracer_uses_the_nirizan_scope_and_package_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_get_tracer(name: str, version: str | None = None) -> Tracer:
        calls.append((name, version))
        return MagicMock(spec=Tracer)

    monkeypatch.setattr(otel_trace, "get_tracer", fake_get_tracer)
    monkeypatch.setattr(nirizan, "__version__", "9.9.9", raising=False)

    _get_default_tracer()

    assert calls == [(NIRIZAN_INSTRUMENTATION_SCOPE, "9.9.9")]
    assert NIRIZAN_INSTRUMENTATION_SCOPE == "nirizan"


def test_default_tracer_falls_back_to_installed_package_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(nirizan, "__version__", raising=False)
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "1.2.3")

    assert to_otel._package_version() == "1.2.3"


def test_default_tracer_has_no_version_when_none_can_be_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def not_installed(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.delattr(nirizan, "__version__", raising=False)
    monkeypatch.setattr(importlib.metadata, "version", not_installed)

    assert to_otel._package_version() is None


@pytest.mark.parametrize("bad", ["", None, 5])
def test_package_version_ignores_an_unusable_version_attribute(
    monkeypatch: pytest.MonkeyPatch, bad: object
) -> None:
    monkeypatch.setattr(nirizan, "__version__", bad, raising=False)
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "4.5.6")

    assert to_otel._package_version() == "4.5.6"


def test_export_span_uses_the_default_tracer_when_none_is_given(
    otel: OTel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(otel_trace, "get_tracer", lambda name, version=None: otel.tracer)

    export_span_to_otel(nspan(name="via-default"))

    assert "via-default" in otel.by_name()


# ===========================================================================
# Topological sort
# ===========================================================================


def names(spans: list[Span]) -> list[str]:
    return [s.name for s in spans]


def test_topological_sort_puts_parents_before_children() -> None:
    root = nspan(name="root")
    child = nspan(name="child", parent=root.span_id)
    grandchild = nspan(name="grandchild", parent=child.span_id)

    assert names(_topological_sort_spans([grandchild, root, child])) == ["root", "child", "grandchild"]


def test_topological_sort_of_nothing_is_nothing() -> None:
    assert _topological_sort_spans([]) == []


def test_topological_sort_treats_a_span_with_an_unknown_parent_as_a_root() -> None:
    orphan = nspan(name="orphan", parent=next_id())

    assert names(_topological_sort_spans([orphan])) == ["orphan"]


def test_topological_sort_keeps_every_span_of_a_cycle() -> None:
    a_id, b_id = next_id(), next_id()
    a = nspan(name="a", span_id=a_id, parent=b_id)
    b = nspan(name="b", span_id=b_id, parent=a_id)

    assert sorted(names(_topological_sort_spans([a, b]))) == ["a", "b"]


def test_topological_sort_keeps_sibling_insertion_order() -> None:
    root = nspan(name="r")
    c1 = nspan(name="c1", parent=root.span_id)
    c2 = nspan(name="c2", parent=root.span_id)

    assert names(_topological_sort_spans([root, c1, c2])) == ["r", "c1", "c2"]


def test_topological_sort_returns_each_span_once_even_when_span_ids_repeat() -> None:
    """Regression: a repeated id used to queue its children twice."""
    shared = next_id()
    first = nspan(name="first", span_id=shared)
    second = nspan(name="second", span_id=shared)
    child = nspan(name="child", parent=shared)

    ordered = _topological_sort_spans([first, second, child])

    assert sorted(names(ordered)) == ["child", "first", "second"]
    assert len(ordered) == 3


def test_topological_sort_orders_every_random_forest_parents_first() -> None:
    rng = random.Random(11)
    for _ in range(100):
        count = rng.randrange(1, 25)
        spans: list[Span] = []
        for index in range(count):
            parent = rng.choice(spans).span_id if spans and rng.random() < 0.7 else None
            spans.append(nspan(name=f"s{index}", parent=parent))
        shuffled = spans[:]
        rng.shuffle(shuffled)

        ordered = _topological_sort_spans(shuffled)

        position = {s.span_id: i for i, s in enumerate(ordered)}
        assert len(ordered) == count
        assert all(
            s.parent_span_id is None or position[s.parent_span_id] < position[s.span_id]
            for s in ordered
        )


# ===========================================================================
# export_trace_to_otel
# ===========================================================================

OTEL_TRACE_ID = uuid_to_otel_trace_id(TRACE_UUID)


def test_every_span_of_a_nirizan_trace_lands_in_one_otel_trace_with_the_same_id(otel: OTel) -> None:
    root = nspan(name="root")
    left = nspan(name="left", parent=root.span_id)
    right = nspan(name="right", parent=root.span_id)
    leaf = nspan(name="leaf", parent=left.span_id)

    export_trace_to_otel(ntrace(root, left, right, leaf), tracer=otel.tracer)

    spans = otel.spans()
    assert len(spans) == 4
    assert {span_context_of(s).trace_id for s in spans} == {OTEL_TRACE_ID}


def test_a_trace_with_several_roots_stays_in_one_otel_trace(otel: OTel) -> None:
    """Regression: roots and orphans used to each start their own random OTel trace."""
    root_a = nspan(name="root-a")
    root_b = nspan(name="root-b")
    orphan = nspan(name="orphan", parent=next_id())
    child = nspan(name="child", parent=root_a.span_id)

    export_trace_to_otel(ntrace(root_a, root_b, orphan, child), tracer=otel.tracer)

    assert {span_context_of(s).trace_id for s in otel.spans()} == {OTEL_TRACE_ID}


def test_parent_and_child_are_linked_through_real_otel_span_ids(otel: OTel) -> None:
    root = nspan(name="root")
    child = nspan(name="child", parent=root.span_id)
    grandchild = nspan(name="grandchild", parent=child.span_id)

    export_trace_to_otel(ntrace(grandchild, root, child), tracer=otel.tracer)

    spans = otel.by_name()
    assert spans["child"].parent is not None
    assert spans["child"].parent.span_id == span_context_of(spans["root"]).span_id
    assert spans["grandchild"].parent is not None
    assert spans["grandchild"].parent.span_id == span_context_of(spans["child"]).span_id
    assert spans["child"].parent.is_remote is False


def test_roots_hang_off_a_synthetic_remote_parent_that_is_sampled(otel: OTel) -> None:
    export_trace_to_otel(ntrace(nspan(name="root")), tracer=otel.tracer)

    [root] = otel.spans()
    assert root.parent is not None
    assert root.parent.is_remote is True
    assert root.parent.span_id == 0x4E6972695A616E01
    assert root.parent.trace_id == OTEL_TRACE_ID
    assert root.parent.trace_flags.sampled is True


def test_orphans_are_anchored_to_the_trace_and_reported(
    otel: OTel, caplog: pytest.LogCaptureFixture
) -> None:
    missing = next_id()
    orphan = nspan(name="orphan", parent=missing)

    with caplog.at_level(logging.WARNING, logger=_MODULE_LOGGER):
        export_trace_to_otel(ntrace(orphan), tracer=otel.tracer)

    [exported] = otel.spans()
    assert exported.parent is not None and exported.parent.is_remote is True
    assert span_context_of(exported).trace_id == OTEL_TRACE_ID
    assert any(str(missing) in r.getMessage() for r in caplog.records)


def test_a_trace_is_never_attached_to_the_active_otel_span(otel: OTel) -> None:
    root = nspan(name="root")
    child = nspan(name="child", parent=root.span_id)

    with otel.provider.get_tracer("app").start_as_current_span("ambient") as ambient:
        export_trace_to_otel(ntrace(root, child), tracer=otel.tracer)

    exported = {k: v for k, v in otel.by_name().items() if k != "ambient"}
    assert {span_context_of(s).trace_id for s in exported.values()} == {OTEL_TRACE_ID}
    assert OTEL_TRACE_ID != ambient.get_span_context().trace_id
    assert exported["root"].parent is not None and exported["root"].parent.is_remote is True


def test_linking_can_be_turned_off_so_each_root_starts_its_own_trace(otel: OTel) -> None:
    root_a = nspan(name="root-a")
    root_b = nspan(name="root-b")
    child = nspan(name="child", parent=root_a.span_id)

    export_trace_to_otel(
        ntrace(root_a, root_b, child),
        tracer=otel.tracer,
        config=OTelExporterConfig(link_roots_to_trace_id=False),
    )

    spans = otel.by_name()
    assert spans["root-a"].parent is None and spans["root-b"].parent is None
    assert span_context_of(spans["root-a"]).trace_id != span_context_of(spans["root-b"]).trace_id
    assert span_context_of(spans["child"]).trace_id == span_context_of(spans["root-a"]).trace_id
    assert OTEL_TRACE_ID not in {span_context_of(s).trace_id for s in spans.values()}


def test_unlinked_roots_are_not_given_a_synthetic_parent_even_when_ambient_spans_exist(
    otel: OTel,
) -> None:
    with otel.provider.get_tracer("app").start_as_current_span("ambient"):
        export_trace_to_otel(
            ntrace(nspan(name="root")),
            tracer=otel.tracer,
            config=OTelExporterConfig(link_roots_to_trace_id=False),
        )

    assert otel.by_name()["root"].parent is None


def test_anchored_spans_are_recorded_even_when_the_root_sampler_would_drop_them() -> None:
    """The synthetic parent is sampled, so a parent-based sampler follows it.

    With linking off, the provider's own root sampling decision applies instead.
    """
    sdk = _make_otel(sampler=ParentBased(ALWAYS_OFF))
    try:
        export_trace_to_otel(ntrace(nspan(name="anchored")), tracer=sdk.tracer)
        export_trace_to_otel(
            ntrace(nspan(name="unlinked")),
            tracer=sdk.tracer,
            config=OTelExporterConfig(link_roots_to_trace_id=False),
        )

        assert [s.name for s in sdk.spans()] == ["anchored"]
    finally:
        sdk.provider.shutdown()


def test_a_nil_trace_id_cannot_anchor_and_falls_back_to_separate_traces(
    otel: OTel, caplog: pytest.LogCaptureFixture
) -> None:
    nil = UUID(int=0)
    root = nspan(name="root", trace_id=nil)

    with caplog.at_level(logging.WARNING, logger=_MODULE_LOGGER):
        export_trace_to_otel(ntrace(root, trace_id=nil), tracer=otel.tracer)

    [exported] = otel.spans()
    assert exported.parent is None
    assert any("cannot be used as an OTel trace id" in r.getMessage() for r in caplog.records)


def test_a_bare_sequence_of_spans_is_accepted_and_anchored_by_its_first_span(otel: OTel) -> None:
    root = nspan(name="root")
    child = nspan(name="child", parent=root.span_id)

    exported = export_trace_to_otel([child, root], tracer=otel.tracer)

    assert len(exported) == 2
    assert {span_context_of(s).trace_id for s in otel.spans()} == {OTEL_TRACE_ID}


def test_exporting_nothing_returns_nothing_and_touches_no_tracer() -> None:
    tracer = MagicMock()

    assert export_trace_to_otel([], tracer=tracer) == []
    assert export_trace_to_otel(ntrace(), tracer=tracer) == []

    tracer.start_span.assert_not_called()


def test_export_trace_uses_the_default_tracer_when_none_is_given(
    otel: OTel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(otel_trace, "get_tracer", lambda name, version=None: otel.tracer)

    export_trace_to_otel(ntrace(nspan(name="via-default")))

    assert "via-default" in otel.by_name()


def test_spans_are_exported_parents_first_whatever_the_input_order(otel: OTel) -> None:
    root = nspan(name="root")
    child = nspan(name="child", parent=root.span_id)
    grandchild = nspan(name="grandchild", parent=child.span_id)

    export_trace_to_otel(ntrace(grandchild, child, root), tracer=otel.tracer)

    # The in-memory exporter records spans in the order they ended.
    assert [s.name for s in otel.spans()] == ["root", "child", "grandchild"]


def test_the_session_id_is_attached_to_every_span(otel: OTel) -> None:
    session = UUID("12345678-1234-5678-1234-567812345678")
    root = nspan(name="root")
    child = nspan(name="child", parent=root.span_id)

    export_trace_to_otel(ntrace(root, child, session_id=session), tracer=otel.tracer)

    assert all((s.attributes or {})[NIRIZAN_SESSION_ID] == str(session) for s in otel.spans())


def test_a_trace_without_a_session_gets_no_session_attribute(otel: OTel) -> None:
    export_trace_to_otel(ntrace(nspan()), tracer=otel.tracer)

    assert NIRIZAN_SESSION_ID not in (otel.spans()[0].attributes or {})


def test_repeated_span_ids_do_not_export_a_span_twice(otel: OTel) -> None:
    shared = next_id()
    first = nspan(name="first", span_id=shared)
    second = nspan(name="second", span_id=shared)
    child = nspan(name="child", parent=shared)

    exported = export_trace_to_otel(ntrace(first, second, child), tracer=otel.tracer)

    assert len(exported) == 3
    assert len(otel.spans()) == 3


def test_a_cyclic_trace_is_exported_without_losing_spans(otel: OTel) -> None:
    a_id, b_id = next_id(), next_id()

    exported = export_trace_to_otel(
        ntrace(nspan(name="a", span_id=a_id, parent=b_id), nspan(name="b", span_id=b_id, parent=a_id)),
        tracer=otel.tracer,
    )

    assert len(exported) == 2


def test_a_very_deep_trace_is_exported_without_recursion(otel: OTel) -> None:
    depth = 1_500
    spans: list[Span] = []
    parent: UUID | None = None
    for index in range(depth):
        spans.append(nspan(name=f"s{index}", parent=parent))
        parent = spans[-1].span_id

    exported = export_trace_to_otel(ntrace(*spans), tracer=otel.tracer)

    assert len(exported) == depth
    last = otel.by_name()[f"s{depth - 1}"]
    assert last.parent is not None
    assert last.parent.span_id == span_context_of(otel.by_name()[f"s{depth - 2}"]).span_id


def test_exported_content_follows_the_config_for_a_whole_trace(otel: OTel) -> None:
    root = nspan(name="root", kind=SpanKind.PLANNING, input_payload="SECRET-PLAN")
    child = nspan(name="child", parent=root.span_id, input_payload="SECRET-PROMPT")

    export_trace_to_otel(ntrace(root, child), tracer=otel.tracer)
    withheld = attr_values(otel.spans())
    otel.memory.clear()
    export_trace_to_otel(ntrace(root, child), tracer=otel.tracer, config=CONTENT_ON)
    allowed = attr_values(otel.spans())

    assert not any("SECRET" in v for v in withheld)
    assert any("SECRET-PLAN" in v for v in allowed)
    assert any("SECRET-PROMPT" in v for v in allowed)


def test_random_forests_always_export_in_one_trace_with_correct_links(otel: OTel) -> None:
    rng = random.Random(23)
    for _ in range(40):
        otel.memory.clear()
        spans: list[Span] = []
        for index in range(rng.randrange(1, 20)):
            roll = rng.random()
            if spans and roll < 0.6:
                parent: UUID | None = rng.choice(spans).span_id
            elif roll < 0.7:
                parent = next_id()  # an orphan
            else:
                parent = None
            spans.append(nspan(name=f"s{index}", parent=parent))

        export_trace_to_otel(ntrace(*spans), tracer=otel.tracer)

        exported = otel.by_nirizan_id()
        assert len(exported) == len(spans)
        assert {span_context_of(s).trace_id for s in exported.values()} == {OTEL_TRACE_ID}
        for span in spans:
            out = exported[str(span.span_id)]
            if str(span.parent_span_id) in exported:
                assert out.parent is not None
                assert out.parent.span_id == span_context_of(exported[str(span.parent_span_id)]).span_id
            else:
                assert out.parent is not None and out.parent.is_remote is True


# ===========================================================================
# NiriZanToOTelExporter
# ===========================================================================


def test_exporter_satisfies_the_base_exporter_contract() -> None:
    assert isinstance(NiriZanToOTelExporter(tracer=MagicMock()), BaseExporter)


@pytest.mark.asyncio
async def test_exporter_exports_a_trace_to_otel(otel: OTel) -> None:
    exporter = NiriZanToOTelExporter(tracer=otel.tracer)
    root = nspan(name="root")
    child = nspan(name="child", parent=root.span_id)

    await exporter.export(ntrace(root, child))

    assert sorted(otel.by_name()) == ["child", "root"]
    assert exporter.export_failures == 0


@pytest.mark.asyncio
async def test_exporter_applies_its_config(otel: OTel) -> None:
    exporter = NiriZanToOTelExporter(tracer=otel.tracer, config=CONTENT_ON)

    await exporter.export(ntrace(nspan(input_payload="the prompt")))

    assert (otel.spans()[0].attributes or {})[GEN_AI_PROMPT] == "the prompt"


@pytest.mark.asyncio
async def test_exporter_does_not_raise_when_the_otel_pipeline_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tracer = MagicMock()
    tracer.start_span.side_effect = RuntimeError("collector unreachable")
    exporter = NiriZanToOTelExporter(tracer=tracer)
    trace = ntrace(nspan())

    with caplog.at_level(logging.ERROR, logger=_MODULE_LOGGER):
        await exporter.export(trace)  # must not raise

    assert exporter.export_failures == 1
    assert any(str(trace.trace_id) in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_exporter_counts_every_failure_and_recovers_afterwards(otel: OTel) -> None:
    failing = MagicMock()
    failing.start_span.side_effect = [RuntimeError("one"), RuntimeError("two")]
    exporter = NiriZanToOTelExporter(tracer=failing)

    await exporter.export(ntrace(nspan()))
    await exporter.export(ntrace(nspan()))
    assert exporter.export_failures == 2

    exporter._tracer = otel.tracer
    await exporter.export(ntrace(nspan(name="after")))

    assert exporter.export_failures == 2
    assert "after" in otel.by_name()


@pytest.mark.asyncio
async def test_exporter_does_not_swallow_task_cancellation() -> None:
    tracer = MagicMock()
    tracer.start_span.side_effect = asyncio.CancelledError()
    exporter = NiriZanToOTelExporter(tracer=tracer)

    with pytest.raises(asyncio.CancelledError):
        await exporter.export(ntrace(nspan()))

    assert exporter.export_failures == 0


@pytest.mark.asyncio
async def test_exporter_works_without_a_configured_tracer_provider() -> None:
    """With no global provider OpenTelemetry hands back no-op spans; nothing may break."""
    exporter = NiriZanToOTelExporter()
    root = nspan()
    child = nspan(parent=root.span_id)

    await exporter.export(ntrace(root, child))

    assert exporter.export_failures == 0


def test_exporter_helpers_export_spans_and_traces_directly(otel: OTel) -> None:
    exporter = NiriZanToOTelExporter(tracer=otel.tracer)
    root = nspan(name="root")
    child = nspan(name="child", parent=root.span_id)

    single = exporter.export_span(nspan(name="single"))
    many = exporter.export_trace([root, child])

    assert single.get_span_context().is_valid
    assert len(many) == 2
    assert sorted(otel.by_name()) == ["child", "root", "single"]


def test_exporter_reuses_the_tracer_it_was_built_with() -> None:
    tracer = MagicMock()
    exporter = NiriZanToOTelExporter(tracer=tracer)

    exporter.export_span(nspan())
    exporter.export_span(nspan())

    assert tracer.start_span.call_count == 2


def test_exporter_helpers_do_not_swallow_failures() -> None:
    tracer = MagicMock()
    tracer.start_span.side_effect = RuntimeError("direct call failure")
    exporter = NiriZanToOTelExporter(tracer=tracer)

    with pytest.raises(RuntimeError, match="direct call failure"):
        exporter.export_span(nspan())
    assert exporter.export_failures == 0


# ===========================================================================
# With NiriZan's own Tracer
# ===========================================================================


@pytest.mark.asyncio
async def test_nirizan_tracer_traces_arrive_as_one_linked_otel_trace(otel: OTel) -> None:
    tracer = NiriZanTracer("app", exporter=NiriZanToOTelExporter(tracer=otel.tracer))

    async with tracer.start_span("plan", SpanKind.PLANNING):
        async with tracer.start_span("retrieve", SpanKind.RETRIEVAL):
            pass
        async with tracer.start_span("generate", SpanKind.GENERATION):
            pass

    spans = otel.by_name()
    assert sorted(spans) == ["generate", "plan", "retrieve"]
    assert len({span_context_of(s).trace_id for s in spans.values()}) == 1
    plan_id = span_context_of(spans["plan"]).span_id
    assert spans["retrieve"].parent is not None and spans["retrieve"].parent.span_id == plan_id
    assert spans["generate"].parent is not None and spans["generate"].parent.span_id == plan_id


@pytest.mark.asyncio
async def test_nirizan_tracer_keeps_working_when_the_otel_pipeline_is_broken() -> None:
    """The application is untouched and the next trace starts cleanly."""
    broken = MagicMock()
    broken.start_span.side_effect = RuntimeError("collector unreachable")
    exporter = NiriZanToOTelExporter(tracer=broken)
    tracer = NiriZanTracer("app", exporter=exporter)

    async with tracer.start_span("first", SpanKind.PLANNING):
        result = "application result"
    async with tracer.start_span("second", SpanKind.PLANNING) as handle:
        handle.output_payload = "ok"

    assert result == "application result"
    assert exporter.export_failures == 2
    second = [s for s in tracer._spans if s.name == "second"]
    assert second and second[0].parent_span_id is None


@pytest.mark.asyncio
async def test_prompt_text_is_not_sent_to_otel_by_default_end_to_end(otel: OTel) -> None:
    tracer = NiriZanTracer("app", exporter=NiriZanToOTelExporter(tracer=otel.tracer))

    async with tracer.start_span(
        "generate",
        SpanKind.GENERATION,
        attributes={"model": "m", GEN_AI_PROMPT: "SECRET-ATTR"},
        input_payload="SECRET-PROMPT",
    ) as handle:
        handle.output_payload = "SECRET-COMPLETION"

    values = attr_values(otel.spans())
    assert values
    assert not any("SECRET" in v for v in values)
