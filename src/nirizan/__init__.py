# src/nirizan/__init__.py
"""NiriZan: Continuous evaluation infrastructure for production AI systems."""
from nirizan._logging import (
    disable_logging,
    enable_logging,
    get_logger,
    set_log_level,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "disable_logging",
    "enable_logging",
    "get_logger",
    "set_log_level",
]
