# src/nirizan/_logging.py
from __future__ import annotations

import logging
import os
import sys
from typing import TextIO, Union

_ROOT_LOGGER_NAME = "nirizan"
_ENV_VAR_LOG_LEVEL = "NIRIZAN_LOG_LEVEL"

LogLevel = Union[int, str]


class _NiriZanStreamHandler(logging.StreamHandler[TextIO]):
    """Internal StreamHandler subclass used to identify NiriZan-managed handlers."""


# Library-safe default: silence by default, let the host app opt in.
logging.getLogger(_ROOT_LOGGER_NAME).addHandler(logging.NullHandler())


def get_logger(module_name: str) -> logging.Logger:
    """Return a logger scoped under the `nirizan` hierarchy.

    Call as `get_logger(__name__)` from any module inside `nirizan/`.
    """
    return logging.getLogger(module_name)


class NiriZanFormatter(logging.Formatter):
    """Formats a record with millisecond precision and full exception trace support:

    [INFO] 2026-08-07 14:40:23.279 [NiriZan] tracer.py:182 Started trace 4baf5d17
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        ts = f"{ts}.{int(record.msecs):03d}"

        msg = (
            f"[{record.levelname}] {ts} [NiriZan] "
            f"{record.filename}:{record.lineno} {record.getMessage()}"
        )

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            msg = f"{msg}\n{record.exc_text}"

        if record.stack_info:
            msg = f"{msg}\n{self.formatStack(record.stack_info)}"

        return msg


def _parse_level(level: LogLevel | None) -> int:
    """Parse int, string, or environment variable into a valid logging level."""
    if level is None:
        env_val = os.getenv(_ENV_VAR_LOG_LEVEL, "INFO").upper()
        return getattr(logging, env_val, logging.INFO)

    if isinstance(level, str):
        numeric_level = getattr(logging, level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level string: {level!r}")
        return numeric_level

    return level


def enable_logging(
    level: LogLevel | None = None,
    stream: TextIO | None = None,
) -> logging.Logger:
    """Opt-in logging configuration for notebooks, CLI runs, or host apps.

    Accepts both string ("DEBUG", "INFO") and integer (logging.INFO) levels.
    If no level is supplied, checks the `NIRIZAN_LOG_LEVEL` environment variable,
    defaulting to `INFO`.

    Idempotent: replaces only NiriZan-managed handlers without touching
    handlers attached by host applications.
    """
    target_level = _parse_level(level)
    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.setLevel(target_level)

    # Clean up prior NiriZan-managed handlers
    for existing in list(root.handlers):
        if isinstance(existing, _NiriZanStreamHandler):
            root.removeHandler(existing)

    handler = _NiriZanStreamHandler(stream or sys.stderr)
    handler.setFormatter(NiriZanFormatter())
    root.addHandler(handler)

    return root


def set_log_level(level: LogLevel) -> None:
    """Dynamically update log level for all NiriZan loggers without re-attaching handlers."""
    target_level = _parse_level(level)
    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.setLevel(target_level)


def disable_logging() -> None:
    """Remove all NiriZan-managed handlers and silence output."""
    root = logging.getLogger(_ROOT_LOGGER_NAME)
    for existing in list(root.handlers):
        if isinstance(existing, _NiriZanStreamHandler):
            root.removeHandler(existing)
