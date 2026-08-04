import functools
from contextlib import AbstractAsyncContextManager
from typing import Any, Awaitable, Callable, ParamSpec, TypeVar
from uuid import UUID

from nirizan.instrumentation.exporters import BaseExporter
from nirizan.instrumentation.spans import SpanKind
from nirizan.instrumentation.tracer import Tracer

_GLOBAL_TRACER: Tracer | None = None

P = ParamSpec("P")
R = TypeVar("R")


def init_tracer(
    application_name: str = "nirizan_app",
    exporter: BaseExporter | None = None,
) -> Tracer:
    global _GLOBAL_TRACER
    _GLOBAL_TRACER = Tracer(application_name=application_name, exporter=exporter)
    return _GLOBAL_TRACER


def get_tracer() -> Tracer:
    global _GLOBAL_TRACER
    if _GLOBAL_TRACER is None:
        _GLOBAL_TRACER = Tracer(application_name="default_app")
    return _GLOBAL_TRACER


def start_session(
    session_id: UUID | None = None,
    tracer: Tracer | None = None,
) -> AbstractAsyncContextManager[UUID]:
    """SDK-level convenience wrapper around Tracer.session(), mirroring trace_span's relationship to start_span.

    Unlike trace_span, this is not a decorator: a session spans multiple
    turns/calls, so it's used as `async with start_session(): ...` around a
    sequence of trace_span-decorated calls, not around a single function.
    """
    active_tracer = tracer or get_tracer()
    return active_tracer.session(session_id)


def trace_span(
    kind: SpanKind,
    name: str | None = None,
    tracer: Tracer | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        span_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            active_tracer = tracer or get_tracer()
            input_repr = str(args[0]) if args else (str(kwargs) if kwargs else None)

            async with active_tracer.start_span(
                name=span_name,
                kind=kind,
                input_payload=input_repr,
            ) as handle:
                result = await func(*args, **kwargs)
                if result is not None:
                    handle.output_payload = str(result)
                return result

        return wrapper

    return decorator
