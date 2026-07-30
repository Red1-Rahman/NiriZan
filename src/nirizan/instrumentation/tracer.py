from contextlib import asynccontextmanager
import contextvars
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

from nirizan.instrumentation.exporters import BaseExporter
from nirizan.instrumentation.spans import Span, SpanKind, Trace

# Context variables ensuring async-safe context propagation across coroutines
_CURRENT_TRACE_ID: contextvars.ContextVar[UUID | None] = contextvars.ContextVar(
    "nirizan_current_trace_id", default=None
)
_CURRENT_SPAN_ID: contextvars.ContextVar[UUID | None] = contextvars.ContextVar(
    "nirizan_current_span_id", default=None
)


class Tracer:
    """Core telemetry tracer managing span lifecycles and parent-child hierarchies."""

    def __init__(
        self,
        application_name: str,
        exporter: BaseExporter | None = None,
    ) -> None:
        self.application_name = application_name
        self.exporter = exporter
        self._spans: list[Span] = []

    @asynccontextmanager
    async def start_span(
        self,
        name: str,
        kind: SpanKind,
        attributes: dict[str, Any] | None = None,
        input_payload: str | None = None,
    ) -> AsyncGenerator[UUID, None]:
        """Async context manager to automatically open, track, and close execution spans."""
        trace_id = _CURRENT_TRACE_ID.get()
        is_root = trace_id is None

        if is_root:
            trace_id = uuid4()
            _CURRENT_TRACE_ID.set(trace_id)

        parent_span_id = _CURRENT_SPAN_ID.get()
        span_id = uuid4()
        started_at = datetime.now(timezone.utc)

        # Update current active span context token
        token_span = _CURRENT_SPAN_ID.set(span_id)

        try:
            yield span_id
        finally:
            ended_at = datetime.now(timezone.utc)

            # Restrict attributes to valid primitive types
            clean_attrs: dict[str, str | int | float | bool] = {}
            if attributes:
                for k, v in attributes.items():
                    if isinstance(v, (str, int, float, bool)):
                        clean_attrs[k] = v
                    else:
                        clean_attrs[k] = str(v)

            completed_span = Span(
                span_id=span_id,
                trace_id=trace_id,  # type: ignore[arg-type]
                parent_span_id=parent_span_id,
                kind=kind,
                name=name,
                started_at=started_at,
                ended_at=ended_at,
                attributes=clean_attrs,
                input_payload=input_payload,
            )
            self._spans.append(completed_span)

            # Restore previous parent span context
            _CURRENT_SPAN_ID.reset(token_span)

            # When the root span closes, assemble the trace and dispatch to exporter
            if is_root:
                trace = self.get_assembled_trace(trace_id=trace_id)
                if self.exporter:
                    await self.exporter.export(trace)
                _CURRENT_TRACE_ID.set(None)

    def get_assembled_trace(self, trace_id: UUID | None = None) -> Trace:
        """Assemble collected spans into a validated Trace model."""
        target_id = trace_id or _CURRENT_TRACE_ID.get() or uuid4()
        matching_spans = [s for s in self._spans if s.trace_id == target_id]

        return Trace(
            trace_id=target_id,
            application_name=self.application_name,
            spans=matching_spans,
            created_at=datetime.now(timezone.utc),
        )

    def clear(self) -> None:
        """Clear local trace buffer."""
        self._spans.clear()
