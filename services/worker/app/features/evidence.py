"""Attach transcript evidence to decisions and tasks that provide a verifiable quote."""

import re
import unicodedata

from packages.contracts.evidence import TranscriptEvidence
from packages.db.models.transcript import TranscriptSegment


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def attach_evidence(data: dict, segments: list[TranscriptSegment]) -> dict:
    normalized_segments = [(_normalize(segment.text), segment) for segment in segments]
    for key, quote_key, owner_key in (
        ("action_items", "source_quote", "assignee"),
        ("items", "source_quote", "assignee"),
        ("decisions", "context_quote", "made_by"),
    ):
        if key not in data:
            continue
        verified = []
        for item in data[key]:
            quote = _normalize(item.get(quote_key) or "")
            if len(quote) < 5:
                continue
            matches = [segment for text, segment in normalized_segments if quote in text]
            if len(matches) != 1:
                continue
            segment = matches[0]
            item["evidence"] = TranscriptEvidence(
                session_id=segment.session_id, segment_id=segment.id,
                start_time=segment.start_time, end_time=segment.end_time,
            ).model_dump(mode="json")
            if owner := item.get(owner_key):
                if not re.search(r"(?<!\w)" + re.escape(_normalize(owner)) + r"(?!\w)", quote):
                    item[owner_key] = None
            if item.get("deadline") and item["deadline"] not in quote:
                item["deadline"] = None
            if key == "decisions":
                item["timestamp"] = segment.start_time
            verified.append(item)
        data[key] = verified
    return data
