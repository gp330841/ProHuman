"""Tests for shared packages contracts."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.contracts.audio import (
    ALLOWED_SAMPLE_RATES,
    AUDIO_MAGIC_BYTES,
    MAX_CHUNK_SIZE_BYTES,
    AudioChunkMeta,
    AudioFormat,
    AudioSessionConfig,
)
from packages.contracts.features import (
    ActionItem,
    ActionItemsResult,
    AgendaItem,
    Decision,
    FeatureResult,
    FollowUp,
    MOMResult,
    SentimentEntry,
    SentimentResult,
    SummaryResult,
)
from packages.contracts.hinglish import devanagari_to_hinglish
from packages.contracts.search import (
    SearchMode,
    SearchRequest,
    SearchResultItem,
    SearchResponse,
)
from packages.contracts.sessions import (
    SessionCreate,
    SessionDetail,
    SessionListResponse,
    SessionResponse,
    SessionStatus,
)
from packages.contracts.transcription import (
    TranscriptSegment,
    TranscriptionResult,
    WordTimestamp,
)


class TestAudioContracts:
    def test_audio_format_enum(self):
        assert AudioFormat.OPUS == "OPUS"
        assert AudioFormat.WAV == "WAV"
        assert AudioFormat.PCM16 == "PCM16"

    def test_audio_session_config_defaults(self):
        config = AudioSessionConfig(format=AudioFormat.OPUS)
        assert config.format == AudioFormat.OPUS
        assert config.sample_rate == 16000
        assert config.channels == 1

    def test_audio_session_config_custom(self):
        config = AudioSessionConfig(
            format=AudioFormat.WAV,
            sample_rate=44100,
            channels=2,
            language="en",
        )
        assert config.format == AudioFormat.WAV
        assert config.sample_rate == 44100
        assert config.channels == 2

    def test_audio_chunk_meta(self):
        meta = AudioChunkMeta(
            chunk_index=0,
            size_bytes=1024,
            duration_ms=250.0,
            s3_key="audio/session-123/chunk-0.opus",
            checksum="abc123sha256",
        )
        assert meta.chunk_index == 0
        assert meta.size_bytes == 1024


class TestSessionContracts:
    def test_session_status_enum(self):
        assert SessionStatus.CREATED == "CREATED"
        assert SessionStatus.RECORDING == "RECORDING"
        assert SessionStatus.COMPLETED == "COMPLETED"
        assert SessionStatus.FAILED == "FAILED"

    def test_session_create(self):
        create_req = SessionCreate(
            device_id="hardware-mic-1",
            audio_format=AudioFormat.OPUS,
            language="hi",
            metadata={"user_name": "Test User"},
        )
        assert create_req.device_id == "hardware-mic-1"
        assert create_req.language == "hi"
        assert create_req.metadata["user_name"] == "Test User"

    def test_session_response_validation(self):
        session_id = uuid4()
        resp = SessionResponse(
            id=session_id,
            device_id="device-01",
            status=SessionStatus.RECORDING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert resp.id == session_id
        assert resp.status == SessionStatus.RECORDING


class TestTranscriptionContracts:
    def test_word_timestamp(self):
        wt = WordTimestamp(word="Namaste", start=0.0, end=0.5, confidence=0.99)
        assert wt.word == "Namaste"
        assert wt.end == 0.5
        assert wt.confidence == 0.99

    def test_transcript_segment(self):
        seg = TranscriptSegment(
            segment_index=0,
            speaker_label="Speaker 1",
            text="Aaj ki meeting shuru karte hain",
            start_time=0.0,
            end_time=3.5,
            confidence=0.95,
        )
        assert seg.speaker_label == "Speaker 1"
        assert "meeting" in seg.text

    def test_transcription_result(self):
        session_id = uuid4()
        res = TranscriptionResult(
            session_id=session_id,
            segments=[
                TranscriptSegment(
                    segment_index=0,
                    speaker_label="A",
                    text="Hello",
                    start_time=0.0,
                    end_time=1.0,
                )
            ],
            duration_seconds=1.0,
            language="hi",
            speaker_count=1,
            adapter_used="test",
        )
        assert res.session_id == session_id
        assert len(res.segments) == 1


class TestFeatureContracts:
    def test_action_item_model(self):
        item = ActionItem(
            description="Submit budget proposal",
            assignee="Yogeshwar",
            priority="high",
            deadline="2026-10-15",
        )
        assert item.assignee == "Yogeshwar"
        assert item.priority == "high"

    def test_mom_result(self):
        mom = MOMResult(
            title="Q3 Strategy Review",
            date=datetime.now(timezone.utc),
            executive_summary="Team reviewed progress and agreed on budget.",
            attendees=["Yogeshwar", "Amit"],
            action_items=[
                ActionItem(description="Review slides", assignee="Amit", priority="medium")
            ],
            decisions=[
                Decision(description="Approve Q3 budget", made_by="Yogeshwar")
            ],
            agenda_items=[
                AgendaItem(topic="Budget Review", summary="Budget approved", duration_seconds=600, speakers_involved=["Amit"])
            ],
            follow_ups=[
                FollowUp(description="Send updated spreadsheet", responsible_party="Amit")
            ],
        )
        assert mom.title == "Q3 Strategy Review"
        assert len(mom.attendees) == 2
        assert len(mom.action_items) == 1
        assert len(mom.decisions) == 1
        assert len(mom.agenda_items) == 1
        assert len(mom.follow_ups) == 1

    def test_summary_result(self):
        summary = SummaryResult(
            executive_summary="Short meeting overview.",
            title="Planning meeting",
            key_topics=["Budget", "Timeline"],
            participant_count=2,
        )
        assert len(summary.key_topics) == 2
        assert summary.participant_count == 2


class TestSearchContracts:
    def test_search_mode_values(self):
        assert SearchMode.HYBRID == "HYBRID"
        assert SearchMode.SEMANTIC == "SEMANTIC"
        assert SearchMode.LEXICAL == "LEXICAL"

    def test_search_request_defaults(self):
        req = SearchRequest(query="budget discussions")
        assert req.query == "budget discussions"
        assert req.search_mode == SearchMode.HYBRID
        assert req.limit == 10

    def test_search_response(self):
        item = SearchResultItem(
            segment_id=uuid4(),
            session_id=uuid4(),
            session_date=datetime.now(timezone.utc),
            speaker_label="Speaker 1",
            text="The budget is approved",
            start_time=10.0,
            end_time=15.0,
            rrf_score=0.985,
        )
        resp = SearchResponse(
            total_count=1,
            query_embedding_model="test",
            search_mode_used=SearchMode.HYBRID,
            results=[item],
        )
        assert resp.total_count == 1
        assert resp.results[0].rrf_score == 0.985


class TestHinglishTransliteration:
    def test_common_replacements(self):
        res = devanagari_to_hinglish("यह मीटिंग बहुत अच्छा है")
        assert "yeh" in res
        assert "meeting" in res
        assert "accha" in res
        assert "hai" in res

    def test_empty_string(self):
        assert devanagari_to_hinglish("") == ""

    def test_english_passthrough(self):
        assert devanagari_to_hinglish("Hello world") == "Hello world"
