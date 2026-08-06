from __future__ import annotations

import functools
from typing import Any, Callable, Coroutine, Optional, ParamSpec, TypeVar
from uuid import UUID

from nirizan.instrumentation.exporters import BaseExporter
from nirizan.instrumentation.spans import SpanKind
from nirizan.instrumentation.tracer import Tracer

_GLOBAL_TRACER: Optional[Tracer] = None

P = ParamSpec("P")
R = TypeVar("R")


def init_tracer(
    application_name: str, exporter: Optional[BaseExporter] = None
) -> Tracer:
    """Initialize and register the global tracer instance."""
    global _GLOBAL_TRACER
    tracer = Tracer(application_name=application_name, exporter=exporter)
    _GLOBAL_TRACER = tracer
    return tracer


def get_tracer() -> Optional[Tracer]:
    """Return the currently configured global tracer instance."""
    return _GLOBAL_TRACER


def start_session(session_id: Optional[UUID] = None) -> Any:
    """SDK-level context manager pass-through for grouping traces into a session."""
    tracer = get_tracer()
    if tracer is None:
        raise RuntimeError("Tracer is not initialized. Call init_tracer() first.")
    return tracer.session(session_id=session_id)


def trace_span(
    kind: SpanKind,
    name: Optional[str] = None,
    tracer: Optional[Tracer] = None,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Decorator to instrument an async function with full signature preservation."""
    def decorator(
        func: Callable[P, Coroutine[Any, Any, R]]
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        span_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            active_tracer = tracer or get_tracer()
            if active_tracer is None:
                raise RuntimeError(
                    "Tracer is not initialized. Call init_tracer() before executing traced code."
                )

            async with active_tracer.start_span(name=span_name, kind=kind) as handle:
                result = await func(*args, **kwargs)
                if result is not None and handle.output_payload is None:
                    handle.output_payload = str(result)
                return result

        return wrapper

    return decorator
