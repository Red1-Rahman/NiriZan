# tests/trust/test_anchor_set.py
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from nirizan.trust.anchor_set import AnchorItem, AnchorSet


def test_anchor_item_valid():
    item = AnchorItem(
        anchor_id="anchor-001",
        input_payload="Summarize the return policy.",
        expected_output="Items can be returned within 30 days.",
        human_label=1.0,
    )
    assert item.anchor_id == "anchor-001"
    assert item.human_label == 1.0


def test_anchor_item_label_bounds():
    # Label > 1.0 should fail validation
    with pytest.raises(ValidationError):
        AnchorItem(
            anchor_id="anchor-002",
            input_payload="Test",
            expected_output="Test",
            human_label=1.5,
        )

    # Label < 0.0 should fail validation
    with pytest.raises(ValidationError):
        AnchorItem(
            anchor_id="anchor-003",
            input_payload="Test",
            expected_output="Test",
            human_label=-0.1,
        )


def test_anchor_set_creation_and_min_length():
    valid_item = AnchorItem(
        anchor_id="anchor-001",
        input_payload="Prompt",
        expected_output="Completion",
        human_label=0.9,
    )

    now = datetime.now(timezone.utc)
    anchor_set = AnchorSet(
        anchor_set_id="v1-gold-set",
        items=[valid_item],
        created_at=now,
    )

    assert anchor_set.anchor_set_id == "v1-gold-set"
    assert len(anchor_set.items) == 1

    # Empty items list must fail min_length=1 validation constraint
    with pytest.raises(ValidationError):
        AnchorSet(
            anchor_set_id="empty-set",
            items=[],
            created_at=now,
        )
