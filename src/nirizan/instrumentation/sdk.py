# src/nirizan/instrumentation/sdk.py
from __future__ import annotations

import functools
from typing import Any, Callable, Coroutine, Optional, ParamSpec, TypeVar
from uuid import UUID

from nirizan._logging import get_logger
from nirizan.instrumentation.exporters import BaseExporter
from nirizan.instrumentation.spans import SpanKind
from nirizan.instrumentation.tracer import Tracer

logger = get_logger(__name__)

_GLOBAL_TRACER: Optional[Tracer] = None

P = ParamSpec("P")
R = TypeVar("R")


def init_tracer(application_name: str, exporter: Optional[BaseExporter] = None) -> Tracer:
    """Initialize and register the global tracer instance."""
    global _GLOBAL_TRACER
    tracer = Tracer(application_name=application_name, exporter=exporter)
    _GLOBAL_TRACER = tracer
    logger.info("Initialized global tracer for application '%s'", application_name)
    return tracer


def get_tracer() -> Optional[Tracer]:
    """Return the currently configured global tracer instance."""
    return _GLOBAL_TRACER


def start_session(session_id: Optional[UUID] = None) -> Any:
    """SDK-level context manager pass-through for grouping traces into a session."""
    tracer = get_tracer()
    if tracer is None:
        raise RuntimeError("Tracer is not initialized. Call init_tracer() first.")
    logger.debug("Starting SDK session (session_id=%s)", session_id)
    return tracer.session(session_id=session_id)


def _format_input_payload(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
    if args:
        return str(args[0])
    if kwargs:
        return str(next(iter(kwargs.values())))
    return None


def trace_span(
    kind: SpanKind,
    name: Optional[str] = None,
    tracer: Optional[Tracer] = None,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Decorator to instrument an async function with full signature preservation."""

    def decorator(func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, Coroutine[Any, Any, R]]:
        span_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            active_tracer = tracer or get_tracer()
            if active_tracer is None:
                raise RuntimeError(
                    "Tracer is not initialized. Call init_tracer() before executing traced code."
                )

            input_payload = _format_input_payload(args, kwargs)

            async with active_tracer.start_span(
                name=span_name, kind=kind, input_payload=input_payload
            ) as handle:
                result = await func(*args, **kwargs)
                if result is not None and handle.output_payload is None:
                    handle.output_payload = str(result)
                return result

        return wrapper

    return decorator


def planning(
    name: Optional[str] = None,
    tracer: Optional[Tracer] = None,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Convenience decorator for PLANNING span instrumentation."""
    return trace_span(kind=SpanKind.PLANNING, name=name, tracer=tracer)


def retrieval(
    name: Optional[str] = None,
    tracer: Optional[Tracer] = None,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Convenience decorator for RETRIEVAL span instrumentation."""
    return trace_span(kind=SpanKind.RETRIEVAL, name=name, tracer=tracer)


def generation(
    name: Optional[str] = None,
    tracer: Optional[Tracer] = None,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Convenience decorator for GENERATION span instrumentation."""
    return trace_span(kind=SpanKind.GENERATION, name=name, tracer=tracer)


def tool_use(
    name: Optional[str] = None,
    tracer: Optional[Tracer] = None,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Convenience decorator for TOOL_USE span instrumentation."""
    return trace_span(kind=SpanKind.TOOL_USE, name=name, tracer=tracer)
