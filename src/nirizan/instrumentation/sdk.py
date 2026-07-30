import functools
from typing import Any, Callable, TypeVar

from nirizan.instrumentation.exporters import BaseExporter
from nirizan.instrumentation.spans import SpanKind
from nirizan.instrumentation.tracer import Tracer

_GLOBAL_TRACER: Tracer | None = None

F = TypeVar("F", bound=Callable[..., Any])


def init_tracer(
    application_name: str = "nirizan_app",
    exporter: BaseExporter | None = None,
) -> Tracer:
    """Initialize the global SDK tracer instance."""
    global _GLOBAL_TRACER
    _GLOBAL_TRACER = Tracer(application_name=application_name, exporter=exporter)
    return _GLOBAL_TRACER


def get_tracer() -> Tracer:
    """Retrieve the current global tracer instance, or lazy-initialize a default one."""
    global _GLOBAL_TRACER
    if _GLOBAL_TRACER is None:
        _GLOBAL_TRACER = Tracer(application_name="default_app")
    return _GLOBAL_TRACER


def trace_span(
    kind: SpanKind,
    name: str | None = None,
    tracer: Tracer | None = None,
) -> Callable[[F], F]:
    """Decorator to automatically instrument asynchronous functions with tracing."""

    def decorator(func: F) -> F:
        span_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            active_tracer = tracer or get_tracer()
            input_repr = str(args[0]) if args else (str(kwargs) if kwargs else None)

            async with active_tracer.start_span(
                name=span_name,
                kind=kind,
                input_payload=input_repr,
            ):
                return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
