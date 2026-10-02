"""Tests for packages database models and repositories."""
from __future__ import annotations

import uuid
from packages.db.models.session import SessionModel, SessionStatusEnum
from packages.db.models.transcript import TranscriptSegmentModel
from packages.db.models.feature_result import FeatureResultModel
from packages.db.models.audio_chunk import AudioChunk


class TestDatabaseModels:
    def test_session_model_creation(self):
        session_id = uuid.uuid4()
        session = SessionModel(
            id=session_id,
            device_id="hardware-device-01",
            status=SessionStatusEnum.CREATED,
            language="hi",
            extra_metadata={"client": "web"},
        )
        assert session.id == session_id
        assert session.device_id == "hardware-device-01"
        assert session.status == SessionStatusEnum.CREATED
        assert session.language == "hi"

    def test_transcript_segment_model_creation(self):
        session_id = uuid.uuid4()
        segment = TranscriptSegmentModel(
            session_id=session_id,
            segment_index=0,
            speaker_label="Speaker 0",
            text="Testing transcription model",
            start_time=0.0,
            end_time=2.5,
            confidence=0.98,
        )
        assert segment.session_id == session_id
        assert segment.text == "Testing transcription model"
        assert segment.confidence == 0.98

    def test_feature_result_model_creation(self):
        session_id = uuid.uuid4()
        feat = FeatureResultModel(
            session_id=session_id,
            feature_name="mom",
            version=1,
            data={"title": "Test Title", "executive_summary": "Summary here"},
        )
        assert feat.session_id == session_id
        assert feat.feature_name == "mom"
        assert feat.data["title"] == "Test Title"

    def test_audio_chunk_model_creation(self):
        session_id = uuid.uuid4()
        chunk = AudioChunk(
            session_id=session_id,
            chunk_index=0,
            s3_key=f"audio/{session_id}/chunk-0.opus",
            checksum="abcde12345",
            size_bytes=4096,
        )
        assert chunk.session_id == session_id
        assert chunk.size_bytes == 4096
        assert chunk.chunk_index == 0
