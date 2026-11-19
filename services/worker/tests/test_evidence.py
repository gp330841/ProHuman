"""Check quote grounding across supported recording languages."""

from uuid import uuid4

import pytest

from app.features.evidence import attach_evidence
from packages.db.models.transcript import TranscriptSegment


@pytest.mark.parametrize("text, assignee", [
    ("Mira will send the budget.", "Mira"),
    ("मीरा बजट भेजेंगी।", "मीरा"),
    ("Mira kal budget bhejegi.", "Mira"),
])
def test_exact_source_links_and_unknown_fields(text, assignee):
    segment = TranscriptSegment(
        id=uuid4(), session_id=uuid4(), start_time=2.5, end_time=4.0, text=text,
    )
    result = attach_evidence({"action_items": [
        {"description": "Send budget", "source_quote": text, "assignee": assignee, "deadline": "2030-01-02"},
        {"description": "Invented", "source_quote": "No such claim"},
    ]}, [segment])
    item, = result["action_items"]
    assert item["assignee"] == assignee
    assert item["deadline"] is None
    assert item["evidence"]["segment_id"] == str(segment.id)
    assert item["evidence"]["start_time"] == 2.5


def test_gemini_normalization_preserves_quotes_for_grounding():
    from app.llm.client import LLMClient
    from packages.contracts.features import ActionItemsResult, MOMResult

    client = LLMClient()
    task = {"description": "Send budget", "source_quote": "Mira will send the budget."}
    decision = {"description": "Approve budget", "context_quote": "The budget is approved."}
    mom = client._normalize_and_validate({"action_items": [task], "decisions": [decision]}, MOMResult)
    actions = client._normalize_and_validate({"items": [task]}, ActionItemsResult)

    assert mom.decisions[0].context_quote == decision["context_quote"]
    assert mom.action_items[0].source_quote == task["source_quote"]
    assert actions.items[0].source_quote == task["source_quote"]
    assert mom.action_items[0].assignee is None
