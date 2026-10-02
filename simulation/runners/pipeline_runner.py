"""
End-to-end pipeline simulation runner.

Wires together data generators, mock infrastructure, contract validators,
data-integrity validators, and feature-quality assessors to exercise every
phase of the ProHuman processing pipeline WITHOUT real infrastructure.
"""

import asyncio
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from simulation.config import SimulationConfig, get_config
from simulation.data.generators import (
    SimulationDataGenerator,
    SessionGenerator,
    TranscriptGenerator,
    FeatureGenerator,
    SearchDataGenerator,
    EmbeddingGenerator,
    SessionStatus,
    AudioFormat,
)
from simulation.mocks.infrastructure import (
    MockDatabase,
    MockRedis,
    MockS3,
    MockCeleryBroker,
    InfrastructureReport,
)
from simulation.mocks.adapters import MockSTTAdapter, MockLLMClient, MockEmbeddingClient
from simulation.validators.contracts import ContractValidator
from simulation.validators.data_integrity import DataIntegrityValidator
from simulation.validators.quality import FeatureQualityAssessor

import random


# ── Result dataclasses ───────────────────────────────────────────────

@dataclass
class PhaseResult:
    phase_name: str
    duration_ms: float = 0.0
    records_processed: int = 0
    validations_passed: int = 0
    validations_failed: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    duration_ms: float = 0.0
    phase_results: Dict[str, Any] = field(default_factory=dict)
    records_processed: int = 0
    validations_passed: int = 0
    validations_failed: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    quality_scores: Dict[str, Any] = field(default_factory=dict)
    infra_report: Dict[str, Any] = field(default_factory=dict)
    edge_case_results: Dict[str, Any] = field(default_factory=dict)
    production_issues: List[Dict[str, str]] = field(default_factory=list)


# ── Pipeline Runner ──────────────────────────────────────────────────

class PipelineRunner:
    """Simulates the full ProHuman data pipeline end-to-end."""

    def __init__(self, config: Optional[SimulationConfig] = None):
        self.config = config or get_config()
        self.rand = random.Random(self.config.random_seed)

        # Mock infrastructure
        self.db = MockDatabase()
        self.redis = MockRedis()
        self.s3 = MockS3()
        self.celery = MockCeleryBroker(delay_ms=0)

        # Mock adapters
        self.stt = MockSTTAdapter()
        self.llm = MockLLMClient()
        self.embedder = MockEmbeddingClient()

        # Generators
        self.data_gen = SimulationDataGenerator(self.config)
        self.session_gen = SessionGenerator(self.rand)
        self.transcript_gen = TranscriptGenerator(self.rand)
        self.feature_gen = FeatureGenerator(self.rand)
        self.search_gen = SearchDataGenerator(self.rand)
        self.embed_gen = EmbeddingGenerator()

        # Validators
        self.contract_v = ContractValidator()
        self.integrity_v = DataIntegrityValidator()
        self.quality_v = FeatureQualityAssessor()

        # Internal state
        self._sessions: List[Dict[str, Any]] = []
        self._transcripts: Dict[str, Any] = {}  # session_id -> TranscriptionResult
        self._features: Dict[str, Any] = {}      # session_id -> feature dict
        self._embeddings: Dict[str, List[float]] = {}  # segment text hash -> vector

    # ── Phase 1: Session Creation ────────────────────────────────────

    async def _phase_session_creation(self) -> PhaseResult:
        start = time.time()
        result = PhaseResult(phase_name="Session Creation")
        n = self.config.num_sessions

        for i in range(n):
            sc, sr = self.session_gen.generate()

            # Store in mock DB
            session_record = {
                "id": str(sr.id),
                "device_id": sr.device_id,
                "status": SessionStatus.CREATED.value,
                "audio_format": sr.audio_format,
                "sample_rate": 16000,
                "duration_seconds": sr.duration_seconds,
                "created_at": sr.created_at.isoformat(),
                "updated_at": sr.updated_at.isoformat(),
                "metadata": {},
                "s3_key": None,
            }
            await self.db.create("sessions", session_record)

            # Validate contracts
            v = self.contract_v.validate_session_response(session_record)
            if v.is_valid:
                result.validations_passed += 1
            else:
                result.validations_failed += 1
                result.errors.extend([e.message for e in v.errors])

            self._sessions.append(session_record)
            result.records_processed += 1

        result.duration_ms = (time.time() - start) * 1000
        return result

    # ── Phase 2: Audio Ingestion ─────────────────────────────────────

    async def _phase_audio_ingestion(self) -> PhaseResult:
        start = time.time()
        result = PhaseResult(phase_name="Audio Ingestion")

        for session in self._sessions:
            sid = session["id"]

            # Simulate 2 audio chunks per session
            for chunk_idx in range(2):
                # Generate mock audio data
                audio_data = self.rand.randbytes(self.rand.randint(8192, 65536))
                checksum = hashlib.sha256(audio_data).hexdigest()
                s3_key = f"{sid}/chunk_{chunk_idx}.webm"

                # Upload to mock S3
                await self.s3.put_object("audio-recordings", s3_key, audio_data)

                # Idempotency check via Redis setnx
                idem_key = f"upload:{sid}:{checksum}"
                is_new = await self.redis.setnx(idem_key, "1", ex=3600)

                if is_new:
                    # Store chunk record in DB
                    chunk_record = {
                        "id": str(uuid.uuid4()),
                        "session_id": sid,
                        "chunk_index": chunk_idx,
                        "index": chunk_idx,  # alias for constraint check
                        "s3_key": s3_key,
                        "size_bytes": len(audio_data),
                        "duration_ms": self.rand.randint(5000, 30000),
                        "checksum": checksum,
                    }
                    await self.db.create("audio_chunks", chunk_record)

                    v = self.contract_v.validate_audio_chunk_meta(chunk_record)
                    if v.is_valid:
                        result.validations_passed += 1
                    else:
                        result.validations_failed += 1
                        result.errors.extend([e.message for e in v.errors])

                    result.records_processed += 1

            # Update session status
            await self.db.update("sessions", sid, {"status": SessionStatus.PROCESSING.value})

            # Dispatch transcription task
            await self.celery.send_task(
                "app.tasks.transcription.transcribe_session",
                args=(sid,),
                queue="transcription",
            )

        # Test duplicate upload idempotency
        dup_key = f"upload:{self._sessions[0]['id']}:duplicate_test"
        first = await self.redis.setnx(dup_key, "1", ex=3600)
        second = await self.redis.setnx(dup_key, "1", ex=3600)
        if first and not second:
            result.validations_passed += 1
            result.details["idempotency"] = "PASS"
        else:
            result.validations_failed += 1
            result.errors.append("Idempotency check failed")
            result.details["idempotency"] = "FAIL"

        result.duration_ms = (time.time() - start) * 1000
        return result

    # ── Phase 3: Transcription ───────────────────────────────────────

    async def _phase_transcription(self) -> PhaseResult:
        start = time.time()
        result = PhaseResult(phase_name="Transcription")

        for session in self._sessions:
            sid = session["id"]
            duration = session.get("duration_seconds", 1800.0) or 1800.0

            # Update status
            await self.db.update("sessions", sid, {"status": SessionStatus.TRANSCRIBING.value})

            # Generate transcript via mock STT
            transcript = self.transcript_gen.generate(uuid.UUID(sid), duration)
            self._transcripts[sid] = transcript

            # Store segments in DB
            for seg in transcript.segments:
                seg_record = {
                    "id": str(uuid.uuid4()),
                    "session_id": sid,
                    "segment_index": seg.segment_index,
                    "speaker_label": seg.speaker_label,
                    "text": seg.text,
                    "start_time": seg.start_time,
                    "end_time": seg.end_time,
                    "confidence": seg.confidence,
                    "word_timestamps": [
                        {"word": w.word, "start": w.start, "end": w.end,
                         "confidence": w.confidence, "speaker": w.speaker}
                        for w in seg.words
                    ],
                    "embedding": None,
                }
                await self.db.create("transcript_segments", seg_record)

                # Validate segment contract
                v = self.contract_v.validate_transcript_segment(seg_record)
                if v.is_valid:
                    result.validations_passed += 1
                else:
                    result.validations_failed += 1
                    result.errors.extend([e.message for e in v.errors])

                result.records_processed += 1

            # Update session status
            await self.db.update("sessions", sid, {"status": SessionStatus.TRANSCRIBED.value})

            # Dispatch downstream tasks
            await self.celery.send_task(
                "app.tasks.embedding.generate_embeddings",
                args=(sid,),
                queue="embedding",
            )
            await self.celery.send_task(
                "app.tasks.feature_pipeline.run_feature_pipeline",
                args=(sid,),
                queue="features",
            )

        # Validate transcript continuity across all sessions
        all_segments = await self.db.list("transcript_segments", limit=10000)
        by_session: Dict[str, list] = {}
        for s in all_segments:
            by_session.setdefault(s["session_id"], []).append(s)

        for sid, segs in by_session.items():
            iv = self.integrity_v.validate_transcript_continuity(segs)
            if iv.is_valid:
                result.validations_passed += 1
            else:
                result.validations_failed += 1
                result.errors.extend([v.details for v in iv.violations])

        result.details["total_segments"] = len(all_segments)
        result.details["sessions_with_transcripts"] = len(by_session)
        result.duration_ms = (time.time() - start) * 1000
        return result

    # ── Phase 4: Embedding Generation ────────────────────────────────

    async def _phase_embedding(self) -> PhaseResult:
        start = time.time()
        result = PhaseResult(phase_name="Embedding Generation")

        all_segments = await self.db.list("transcript_segments", limit=10000)
        batch_size = 32
        batches = [all_segments[i:i + batch_size] for i in range(0, len(all_segments), batch_size)]

        for batch in batches:
            for seg in batch:
                if seg.get("embedding") is None:
                    embedding = self.embed_gen.generate(seg["text"])

                    # Validate dimension
                    if len(embedding) == 1536:
                        result.validations_passed += 1
                    else:
                        result.validations_failed += 1
                        result.errors.append(f"Embedding dim={len(embedding)}, expected 1536")

                    await self.db.update("transcript_segments", seg["id"], {"embedding": embedding})
                    self._embeddings[seg["text"][:64]] = embedding
                    result.records_processed += 1

        # Validate all segments now have embeddings
        updated_segments = await self.db.list("transcript_segments", limit=10000)
        missing = sum(1 for s in updated_segments if s.get("embedding") is None)
        if missing == 0:
            result.validations_passed += 1
            result.details["embedding_coverage"] = "100%"
        else:
            result.validations_failed += 1
            result.errors.append(f"{missing} segments still missing embeddings")
            result.details["embedding_coverage"] = f"{100 * (len(updated_segments) - missing) / max(1, len(updated_segments)):.1f}%"

        # Update session statuses
        for session in self._sessions:
            await self.db.update("sessions", session["id"], {"status": SessionStatus.INDEXED.value})

        result.details["total_embeddings"] = result.records_processed
        result.details["batches_processed"] = len(batches)
        result.duration_ms = (time.time() - start) * 1000
        return result

    # ── Phase 5: Feature Extraction ──────────────────────────────────

    async def _phase_feature_extraction(self) -> PhaseResult:
        start = time.time()
        result = PhaseResult(phase_name="Feature Extraction")

        feature_names = ["summary", "action_items", "mom", "sentiment", "follow_up"]

        for session in self._sessions:
            sid = session["id"]
            await self.db.update("sessions", sid, {"status": SessionStatus.EXTRACTING.value})

            transcript = self._transcripts.get(sid)
            if not transcript:
                result.warnings.append(f"No transcript for session {sid}")
                continue

            features = self.feature_gen.generate(uuid.UUID(sid), transcript)
            self._features[sid] = features

            # Store each feature result with versioning
            for fname, fresult in features.items():
                # Check for existing version
                existing = await self.db.list("feature_results", filters={"session_id": sid, "name": fname})
                version = len(existing) + 1

                feature_record = {
                    "id": str(uuid.uuid4()),
                    "session_id": sid,
                    "feature_name": fname,
                    "name": fname,  # alias for constraint
                    "version": version,
                    "data": fresult.data,
                    "processing_time_ms": fresult.processing_time_ms,
                    "provider_model": fresult.provider_model,
                }
                await self.db.create("feature_results", feature_record)

                # Contract validation
                v = self.contract_v.validate_feature_result(feature_record)
                if v.is_valid:
                    result.validations_passed += 1
                else:
                    result.validations_failed += 1
                    result.errors.extend([e.message for e in v.errors])

                result.records_processed += 1

            await self.db.update("sessions", sid, {"status": SessionStatus.COMPLETED.value})

        # Run quality assessments
        quality_scores = {}
        for sid, features in self._features.items():
            transcript = self._transcripts.get(sid)
            if not transcript:
                continue

            seg_dicts = [
                {"speaker_label": s.speaker_label, "text": s.text,
                 "start_time": s.start_time, "end_time": s.end_time}
                for s in transcript.segments
            ]

            if "summary" in features:
                q = self.quality_v.assess_summary_quality(features["summary"].data, seg_dicts)
                quality_scores.setdefault("summary", []).append(q.overall_score)

            if "action_items" in features:
                items = features["action_items"].data.get("items", [])
                if isinstance(items, list):
                    q = self.quality_v.assess_action_items_quality(
                        [i if isinstance(i, dict) else i.__dict__ for i in items],
                        seg_dicts
                    )
                    quality_scores.setdefault("action_items", []).append(q.overall_score)

            if "sentiment" in features:
                q = self.quality_v.assess_sentiment_quality(features["sentiment"].data, seg_dicts)
                quality_scores.setdefault("sentiment", []).append(q.overall_score)

        # Average quality scores
        result.details["quality_scores"] = {
            k: round(sum(v) / len(v), 1) for k, v in quality_scores.items() if v
        }

        result.duration_ms = (time.time() - start) * 1000
        return result

    # ── Phase 6: Search Validation ───────────────────────────────────

    async def _phase_search_validation(self) -> PhaseResult:
        start = time.time()
        result = PhaseResult(phase_name="Search Validation")

        # Generate search queries and simulate results
        queries = [
            "action items from standup",
            "database migration timeline",
            "API rate limiting discussion",
            "deployment blockers",
            "performance optimization",
        ]

        all_segments = await self.db.list("transcript_segments", limit=10000)

        for query in queries:
            # Simulate RRF hybrid search
            query_embedding = self.embed_gen.generate(query)

            # Score each segment (simplified cosine-like comparison)
            scored = []
            for seg in all_segments:
                seg_emb = seg.get("embedding")
                text = seg.get("text", "").lower()

                # Text rank: keyword match
                text_score = sum(1 for word in query.lower().split() if word in text)

                # Vector rank: simplified dot product proxy
                vector_score = 0.0
                if seg_emb and query_embedding:
                    dot = sum(a * b for a, b in zip(query_embedding[:32], seg_emb[:32]))
                    vector_score = abs(dot)

                # RRF fusion
                rrf_k = 60
                rrf_score = 0.0
                if text_score > 0:
                    rrf_score += 1.0 / (rrf_k + text_score)
                if vector_score > 0:
                    rrf_score += 1.0 / (rrf_k + 1)

                if rrf_score > 0:
                    scored.append({
                        "segment_id": seg["id"],
                        "session_id": seg["session_id"],
                        "session_title": None,
                        "speaker_label": seg["speaker_label"],
                        "speaker_name": None,
                        "text": seg["text"],
                        "start_time": seg["start_time"],
                        "end_time": seg["end_time"],
                        "rrf_score": rrf_score,
                        "vector_rank": 1,
                        "text_rank": text_score,
                        "session_date": seg.get("created_at"),
                    })

            # Sort by RRF score descending, take top 10
            scored.sort(key=lambda x: x["rrf_score"], reverse=True)
            top_results = scored[:10]

            # Validate search results
            for sr in top_results:
                v = self.contract_v.validate_search_result_item(sr)
                if v.is_valid:
                    result.validations_passed += 1
                else:
                    result.validations_failed += 1
                    result.errors.extend([e.message for e in v.errors])

            # Validate no duplicates
            seen_ids = set()
            for sr in top_results:
                if sr["segment_id"] in seen_ids:
                    result.validations_failed += 1
                    result.errors.append("Duplicate search result found")
                else:
                    seen_ids.add(sr["segment_id"])

            result.records_processed += len(top_results)

        result.details["queries_tested"] = len(queries)
        result.duration_ms = (time.time() - start) * 1000
        return result

    # ── Phase 7: Edge Case Testing ───────────────────────────────────

    async def _phase_edge_cases(self) -> PhaseResult:
        start = time.time()
        result = PhaseResult(phase_name="Edge Case Testing")
        test_cases = []

        # Test 1: Empty transcript session
        try:
            empty_session = {
                "id": str(uuid.uuid4()), "device_id": "edge-device-001",
                "status": "COMPLETED", "audio_format": "OPUS",
                "duration_seconds": 0.0,
                "created_at": "2026-10-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z",
            }
            await self.db.create("sessions", empty_session)
            result.validations_passed += 1
            test_cases.append({"name": "empty_transcript", "status": "PASS"})
        except Exception as e:
            result.validations_failed += 1
            result.errors.append(f"Empty transcript test failed: {e}")
            test_cases.append({"name": "empty_transcript", "status": "FAIL", "error": str(e)})

        # Test 2: Single speaker session
        try:
            single_seg = {
                "id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()),
                "segment_index": 0, "speaker_label": "SPEAKER_0",
                "text": "This is a monologue session with only one speaker talking the entire time.",
                "start_time": 0.0, "end_time": 120.0, "confidence": 0.95,
                "word_timestamps": [], "embedding": None,
            }
            await self.db.create("transcript_segments", single_seg)
            result.validations_passed += 1
            test_cases.append({"name": "single_speaker", "status": "PASS"})
        except Exception as e:
            result.validations_failed += 1
            test_cases.append({"name": "single_speaker", "status": "FAIL", "error": str(e)})

        # Test 3: Very long session (100+ segments)
        try:
            long_sid = str(uuid.uuid4())
            for i in range(120):
                seg = {
                    "id": str(uuid.uuid4()), "session_id": long_sid,
                    "segment_index": i, "speaker_label": f"SPEAKER_{i % 4}",
                    "text": f"Segment {i}: discussing topic {i // 10}.",
                    "start_time": float(i * 10), "end_time": float(i * 10 + 9),
                    "confidence": 0.9, "word_timestamps": [], "embedding": None,
                }
                await self.db.create("transcript_segments", seg)
            segs = await self.db.list("transcript_segments", filters={"session_id": long_sid}, limit=200)
            if len(segs) == 120:
                result.validations_passed += 1
                test_cases.append({"name": "long_session_120_segments", "status": "PASS"})
            else:
                result.validations_failed += 1
                test_cases.append({"name": "long_session_120_segments", "status": "FAIL"})
        except Exception as e:
            result.validations_failed += 1
            test_cases.append({"name": "long_session_120_segments", "status": "FAIL", "error": str(e)})

        # Test 4: Constraint violation — end_time < start_time
        try:
            bad_seg = {
                "id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()),
                "segment_index": 0, "speaker_label": "SPEAKER_0",
                "text": "Bad timestamps",
                "start_time": 100.0, "end_time": 50.0,
                "confidence": 0.5, "word_timestamps": [], "embedding": None,
            }
            await self.db.create("transcript_segments", bad_seg)
            result.validations_failed += 1
            result.errors.append("DB accepted invalid end_time < start_time")
            test_cases.append({"name": "time_constraint_violation", "status": "FAIL"})
        except ValueError:
            result.validations_passed += 1
            test_cases.append({"name": "time_constraint_violation", "status": "PASS"})

        # Test 5: Duplicate chunk checksum (idempotency at DB level)
        try:
            dup_sid = str(uuid.uuid4())
            chunk1 = {
                "id": str(uuid.uuid4()), "session_id": dup_sid,
                "chunk_index": 0, "index": 0,
                "s3_key": f"{dup_sid}/chunk_0.webm",
                "size_bytes": 1024, "checksum": "a" * 64,
            }
            await self.db.create("audio_chunks", chunk1)
            chunk2 = {
                "id": str(uuid.uuid4()), "session_id": dup_sid,
                "chunk_index": 1, "index": 1,
                "s3_key": f"{dup_sid}/chunk_1.webm",
                "size_bytes": 1024, "checksum": "a" * 64,  # same checksum!
            }
            await self.db.create("audio_chunks", chunk2)
            result.validations_failed += 1
            result.errors.append("DB accepted duplicate chunk checksum for same session")
            test_cases.append({"name": "duplicate_chunk_checksum", "status": "FAIL"})
        except ValueError:
            result.validations_passed += 1
            test_cases.append({"name": "duplicate_chunk_checksum", "status": "PASS"})

        # Test 6: Unicode and special characters
        try:
            unicode_seg = {
                "id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()),
                "segment_index": 0, "speaker_label": "SPEAKER_0",
                "text": "Discussion about münchen café résumé: 日本語テスト 🚀 <script>alert('xss')</script>",
                "start_time": 0.0, "end_time": 10.0,
                "confidence": 0.9, "word_timestamps": [], "embedding": None,
            }
            await self.db.create("transcript_segments", unicode_seg)
            result.validations_passed += 1
            test_cases.append({"name": "unicode_special_chars", "status": "PASS"})
        except Exception as e:
            result.validations_failed += 1
            test_cases.append({"name": "unicode_special_chars", "status": "FAIL", "error": str(e)})

        # Test 7: Feature version uniqueness constraint
        try:
            feat_sid = str(uuid.uuid4())
            f1 = {
                "id": str(uuid.uuid4()), "session_id": feat_sid,
                "feature_name": "summary", "name": "summary",
                "version": 1, "data": {"title": "v1"},
                "processing_time_ms": 100, "provider_model": "gpt-4o",
            }
            await self.db.create("feature_results", f1)
            f2 = {
                "id": str(uuid.uuid4()), "session_id": feat_sid,
                "feature_name": "summary", "name": "summary",
                "version": 1, "data": {"title": "v1 duplicate"},
                "processing_time_ms": 100, "provider_model": "gpt-4o",
            }
            await self.db.create("feature_results", f2)
            result.validations_failed += 1
            result.errors.append("DB accepted duplicate feature version")
            test_cases.append({"name": "feature_version_uniqueness", "status": "FAIL"})
        except ValueError:
            result.validations_passed += 1
            test_cases.append({"name": "feature_version_uniqueness", "status": "PASS"})

        # Test 8: Rate limiting simulation
        try:
            rate_key = "rate:192.168.1.1"
            for _ in range(100):
                await self.redis.incr(rate_key)
            val = await self.redis.get(rate_key)
            if int(val) == 100:
                result.validations_passed += 1
                test_cases.append({"name": "rate_limiting_counter", "status": "PASS"})
            else:
                result.validations_failed += 1
                test_cases.append({"name": "rate_limiting_counter", "status": "FAIL"})
        except Exception as e:
            result.validations_failed += 1
            test_cases.append({"name": "rate_limiting_counter", "status": "FAIL", "error": str(e)})

        # Test 9: S3 object lifecycle
        try:
            test_data = b"test audio data"
            await self.s3.put_object("test-bucket", "test/file.wav", test_data)
            retrieved = await self.s3.get_object("test-bucket", "test/file.wav")
            if retrieved == test_data:
                result.validations_passed += 1
            else:
                result.validations_failed += 1
            await self.s3.delete_object("test-bucket", "test/file.wav")
            try:
                await self.s3.get_object("test-bucket", "test/file.wav")
                result.validations_failed += 1
            except FileNotFoundError:
                result.validations_passed += 1
            test_cases.append({"name": "s3_object_lifecycle", "status": "PASS"})
        except Exception as e:
            result.validations_failed += 1
            test_cases.append({"name": "s3_object_lifecycle", "status": "FAIL", "error": str(e)})

        # Test 10: Session status lifecycle validation
        try:
            valid_transitions = [
                SessionStatus.CREATED, SessionStatus.RECORDING,
                SessionStatus.PROCESSING, SessionStatus.TRANSCRIBING,
                SessionStatus.TRANSCRIBED, SessionStatus.INDEXING,
                SessionStatus.INDEXED, SessionStatus.EXTRACTING,
                SessionStatus.COMPLETED,
            ]
            lifecycle_records = [
                {"id": "lifecycle-test", "status": s.value, "updated_at": f"2026-10-01T0{i}:00:00Z"}
                for i, s in enumerate(valid_transitions)
            ]
            iv = self.integrity_v.validate_session_lifecycle(lifecycle_records)
            if iv.is_valid:
                result.validations_passed += 1
                test_cases.append({"name": "session_lifecycle", "status": "PASS"})
            else:
                result.validations_failed += 1
                test_cases.append({"name": "session_lifecycle", "status": "FAIL"})
        except Exception as e:
            result.validations_failed += 1
            test_cases.append({"name": "session_lifecycle", "status": "FAIL", "error": str(e)})

        result.details["test_cases"] = test_cases
        result.details["passed"] = sum(1 for t in test_cases if t["status"] == "PASS")
        result.details["failed"] = sum(1 for t in test_cases if t["status"] == "FAIL")
        result.duration_ms = (time.time() - start) * 1000
        return result

    # ── Production Readiness Assessment ──────────────────────────────

    def _assess_production_readiness(self, pipeline_result: PipelineResult) -> Dict[str, Any]:
        """Score the system's production readiness across multiple dimensions."""
        scores = {}
        issues = []

        # 1. Contract compliance (40 points max)
        total_v = pipeline_result.validations_passed + pipeline_result.validations_failed
        pass_rate = 0.0
        if total_v > 0:
            pass_rate = pipeline_result.validations_passed / total_v
            scores["contract_compliance"] = round(pass_rate * 40, 1)
        else:
            scores["contract_compliance"] = 0
        if scores["contract_compliance"] < 40:
            issues.append({
                "severity": "critical",
                "area": "Contract Compliance",
                "description": f"Validation pass rate: {pass_rate*100:.1f}% ({pipeline_result.validations_failed} failures)",
                "recommendation": "Fix all contract validation failures before production deployment",
            })

        # 2. Data integrity (20 points max)
        edge_results = pipeline_result.edge_case_results
        edge_passed = edge_results.get("passed", 0)
        edge_total = edge_passed + edge_results.get("failed", 0)
        if edge_total > 0:
            scores["data_integrity"] = round((edge_passed / edge_total) * 20, 1)
        else:
            scores["data_integrity"] = 20
        if scores["data_integrity"] < 20:
            issues.append({
                "severity": "major",
                "area": "Data Integrity",
                "description": f"Edge case pass rate: {edge_passed}/{edge_total}",
                "recommendation": "Review constraint enforcement and error handling",
            })

        # 3. Feature quality (20 points max)
        quality = pipeline_result.quality_scores
        if quality:
            avg_q = sum(quality.values()) / len(quality)
            scores["feature_quality"] = round((avg_q / 100) * 20, 1)
        else:
            scores["feature_quality"] = 10  # partial credit for running
        if scores["feature_quality"] < 15:
            issues.append({
                "severity": "major",
                "area": "Feature Quality",
                "description": f"Average feature quality: {scores['feature_quality']*5:.0f}%",
                "recommendation": "Improve prompt engineering and add output validation",
            })

        # 4. Error handling (10 points max)
        if not pipeline_result.errors:
            scores["error_handling"] = 10
        else:
            scores["error_handling"] = max(0, 10 - len(pipeline_result.errors))
        if scores["error_handling"] < 10:
            issues.append({
                "severity": "minor",
                "area": "Error Handling",
                "description": f"{len(pipeline_result.errors)} errors during simulation",
                "recommendation": "Add retry logic and graceful degradation",
            })

        # 5. Infrastructure resilience (10 points max)
        infra = pipeline_result.infra_report
        scores["infra_resilience"] = 10  # base score from successful mock execution

        total_score = sum(scores.values())

        # Production enhancement recommendations
        recommendations = [
            {
                "priority": "P0 - Critical",
                "title": "Add circuit breakers for external API calls",
                "details": "Deepgram STT and OpenAI LLM calls need circuit breakers with exponential backoff. "
                           "Current retry logic is basic. Use tenacity or custom CircuitBreaker.",
            },
            {
                "priority": "P0 - Critical",
                "title": "Implement dead letter queue (DLQ) for failed Celery tasks",
                "details": "Failed transcription/embedding/feature tasks should be routed to a DLQ "
                           "with alerting, rather than silently failing.",
            },
            {
                "priority": "P1 - High",
                "title": "Add request-level tracing across all services",
                "details": "Agent service has OTLP tracing, but gateway and worker services lack "
                           "distributed tracing. Add trace propagation headers.",
            },
            {
                "priority": "P1 - High",
                "title": "Implement graceful WebSocket reconnection",
                "details": "Audio streaming WebSocket has no reconnection logic. Client should "
                           "resume from last acknowledged chunk_index on disconnect.",
            },
            {
                "priority": "P1 - High",
                "title": "Add output schema validation for LLM responses",
                "details": "Feature extraction relies on Instructor for structured output, but "
                           "doesn't validate the schema of returned data before persisting. "
                           "Add Pydantic validation layer post-LLM call.",
            },
            {
                "priority": "P2 - Medium",
                "title": "Implement embedding cache to avoid recomputation",
                "details": "Identical text segments across sessions will generate the same embedding. "
                           "Cache embeddings by text hash in Redis to reduce OpenAI API costs.",
            },
            {
                "priority": "P2 - Medium",
                "title": "Add pagination to transcript segment queries",
                "details": "Long sessions with 100+ segments loaded eagerly. Implement cursor-based "
                           "pagination for the detail endpoint.",
            },
            {
                "priority": "P2 - Medium",
                "title": "Add health check dependencies (DB, Redis, S3 connectivity)",
                "details": "Current /health returns static OK. Should verify DB connection pool, "
                           "Redis ping, and S3 bucket access.",
            },
            {
                "priority": "P3 - Low",
                "title": "Add feature result diffing for version comparison",
                "details": "Feature versioning stores full JSONB snapshots. Add a diff endpoint "
                           "to compare versions and track extraction improvements.",
            },
            {
                "priority": "P3 - Low",
                "title": "Implement search result caching with TTL",
                "details": "Hybrid search queries are expensive (embedding generation + RRF SQL). "
                           "Cache results in Redis with session-invalidation hooks.",
            },
        ]

        return {
            "total_score": round(total_score, 1),
            "max_score": 100,
            "dimension_scores": scores,
            "issues": issues,
            "recommendations": recommendations,
            "grade": (
                "A" if total_score >= 90 else
                "B" if total_score >= 75 else
                "C" if total_score >= 60 else
                "D" if total_score >= 40 else "F"
            ),
        }

    # ── Main orchestrator ────────────────────────────────────────────

    async def run_full_pipeline(self, config: Optional[dict] = None) -> PipelineResult:
        """Execute all pipeline phases and produce a comprehensive result."""
        overall_start = time.time()
        pipeline_result = PipelineResult()

        phases = [
            ("Session Creation", self._phase_session_creation),
            ("Audio Ingestion", self._phase_audio_ingestion),
            ("Transcription", self._phase_transcription),
            ("Embedding Generation", self._phase_embedding),
            ("Feature Extraction", self._phase_feature_extraction),
            ("Search Validation", self._phase_search_validation),
            ("Edge Case Testing", self._phase_edge_cases),
        ]

        for phase_name, phase_fn in phases:
            try:
                pr = await phase_fn()
                pipeline_result.phase_results[phase_name] = {
                    "phase_name": pr.phase_name,
                    "duration_ms": round(pr.duration_ms, 2),
                    "records_processed": pr.records_processed,
                    "validations_passed": pr.validations_passed,
                    "validations_failed": pr.validations_failed,
                    "errors": pr.errors,
                    "warnings": pr.warnings,
                    "details": pr.details,
                }
                pipeline_result.records_processed += pr.records_processed
                pipeline_result.validations_passed += pr.validations_passed
                pipeline_result.validations_failed += pr.validations_failed
                pipeline_result.errors.extend(pr.errors)
                pipeline_result.warnings.extend(pr.warnings)

                # Capture quality scores and edge case results
                if "quality_scores" in pr.details:
                    pipeline_result.quality_scores.update(pr.details["quality_scores"])
                if phase_name == "Edge Case Testing":
                    pipeline_result.edge_case_results = pr.details

            except Exception as e:
                pipeline_result.phase_results[phase_name] = {
                    "phase_name": phase_name,
                    "duration_ms": 0,
                    "records_processed": 0,
                    "validations_passed": 0,
                    "validations_failed": 1,
                    "errors": [f"Phase crashed: {e}"],
                    "warnings": [],
                    "details": {},
                }
                pipeline_result.validations_failed += 1
                pipeline_result.errors.append(f"Phase '{phase_name}' crashed: {e}")

        # Infrastructure report
        pipeline_result.infra_report = InfrastructureReport(
            db_queries=self.db.query_count,
            db_query_time_ms=self.db.query_time_ms,
            redis_ops=self.redis.operations_count,
            s3_uploads=self.s3.uploads,
            s3_downloads=self.s3.downloads,
            s3_bytes_uploaded=self.s3.bytes_uploaded,
            s3_bytes_downloaded=self.s3.bytes_downloaded,
            celery_tasks_queued=self.celery.tasks_queued,
            celery_tasks_executed=self.celery.tasks_executed,
            celery_task_execution_time_ms=self.celery.task_execution_time_ms,
            queue_counts=dict(self.celery.queue_counts),
        ).generate_summary()

        # Production readiness assessment
        pipeline_result.production_issues = self._assess_production_readiness(pipeline_result)

        pipeline_result.duration_ms = (time.time() - overall_start) * 1000
        return pipeline_result

    def get_pipeline_report(self) -> dict:
        return {}
