# tests/conftest.py
"""Fixtures shared by more than one test module."""

import pytest

from nirizan.storage import models
from nirizan.storage.models import _OnceLatch


@pytest.fixture
def fresh_legacy_latch(monkeypatch: pytest.MonkeyPatch) -> _OnceLatch:
    """Install an unclaimed legacy-row warning latch.

    The once-per-process warning latch is process-wide by design, so any test
    that counts warnings has to own a fresh one, otherwise it depends on
    whether another test already tripped it. The latch is replaced, never
    mutated behind its own lock.
    """
    latch = _OnceLatch()
    monkeypatch.setattr(models, "_legacy_naive_warning_latch", latch)
    return latch
