import uuid
from datetime import datetime, timedelta
import random
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

from simulation.config import SimulationConfig
from simulation.data.meeting_corpus import SCENARIO_TEMPLATES, NAMES, get_random_scenario, generate_speakers

class AudioFormat(Enum):
    OPUS = "OPUS"
    WAV = "WAV"
    PCM16 = "PCM16"

class SessionStatus(Enum):
    CREATED = "CREATED"
    RECORDING = "RECORDING"
    PROCESSING = "PROCESSING"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSCRIBED = "TRANSCRIBED"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    EXTRACTING = "EXTRACTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class SearchMode(Enum):
    HYBRID = "HYBRID"
    SEMANTIC = "SEMANTIC"
    LEXICAL = "LEXICAL"

@dataclass
class SessionCreate:
    device_id: str
    audio_format: AudioFormat = AudioFormat.PCM16
    sample_rate: int = 16000
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class SessionResponse:
    id: uuid.UUID
    device_id: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    audio_format: Optional[str]
    duration_seconds: Optional[float]

@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    confidence: Optional[float]
    speaker: Optional[int]

@dataclass
class TranscriptSegment:
    segment_index: int
    speaker_label: str
    text: str
    start_time: float
    end_time: float
    confidence: Optional[float]
    words: List[WordTimestamp]

@dataclass
class TranscriptionResult:
    session_id: uuid.UUID
    segments: List[TranscriptSegment]
    language: str = 'en'
    duration_seconds: float = 0.0
    speaker_count: int = 0
    adapter_used: str = "default"

@dataclass
class SummaryResult:
    title: str
    executive_summary: str
    key_topics: List[str]
    participant_count: int

@dataclass
class ActionItem:
    description: str
    assignee: Optional[str]
    deadline: Optional[str]
    priority: str
    confidence: float
    source_quote: Optional[str]
    status: str

@dataclass
class ActionItemsResult:
    items: List[ActionItem]

@dataclass
class Decision:
    description: str
    made_by: Optional[str]
    context_quote: Optional[str]
    confidence: float
    timestamp: Optional[float]

@dataclass
class AgendaItem:
    topic: str
    summary: str
    duration_seconds: Optional[float]
    speakers_involved: List[str]

@dataclass
class FollowUp:
    description: str
    responsible_party: Optional[str]
    due_context: Optional[str]

@dataclass
class MOMResult:
    title: str
    date: datetime
    attendees: List[str]
    agenda_items: List[AgendaItem]
    decisions: List[Decision]
    action_items: List[ActionItem]
    follow_ups: List[FollowUp]
    executive_summary: str

@dataclass
class SentimentEntry:
    speaker_label: str
    sentiment: str
    confidence: float
    notable_moments: List[str]

@dataclass
class SentimentResult:
    overall_sentiment: str
    speaker_sentiments: List[SentimentEntry]
    sentiment_trend: List[Dict[str, Any]]

@dataclass
class SearchRequest:
    query: str
    search_mode: SearchMode
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None
    participant_names: Optional[List[str]] = None
    topic_tags: Optional[List[str]] = None
    session_ids: Optional[List[uuid.UUID]] = None
    limit: int = 10
    offset: int = 0

@dataclass
class SearchResultItem:
    segment_id: uuid.UUID
    session_id: uuid.UUID
    session_title: Optional[str]
    speaker_label: str
    speaker_name: Optional[str]
    text: str
    start_time: float
    end_time: float
    rrf_score: float
    vector_rank: Optional[int]
    text_rank: Optional[int]
    session_date: datetime

@dataclass
class FeatureResult:
    feature_name: str
    data: dict
    processing_time_ms: Optional[int] = None
    provider_model: Optional[str] = None
    version: int = 1

@dataclass
class AudioChunkMeta:
    chunk_index: int
    size_bytes: int
    checksum: str
    duration_ms: Optional[int] = None
    s3_key: str = ""


class SessionGenerator:
    def __init__(self, rand: random.Random):
        self.rand = rand

    def generate(self) -> tuple[SessionCreate, SessionResponse]:
        device_id = f"device-{self.rand.randint(1000, 9999)}"
        sc = SessionCreate(device_id=device_id)
        
        session_id = uuid.uuid4()
        now = datetime.utcnow()
        
        sr = SessionResponse(
            id=session_id,
            device_id=device_id,
            status=SessionStatus.COMPLETED,
            created_at=now - timedelta(hours=self.rand.randint(1, 48)),
            updated_at=now,
            audio_format=AudioFormat.PCM16.value,
            duration_seconds=self.rand.uniform(300, 3600)
        )
        return sc, sr

class TranscriptGenerator:
    def __init__(self, rand: random.Random):
        self.rand = rand
        
    def generate(self, session_id: uuid.UUID, duration: float) -> TranscriptionResult:
        scenario = get_random_scenario(self.rand)
        speakers = generate_speakers(scenario, self.rand)
        
        segments = []
        current_time = 0.0
        idx = 0
        
        dialogue = self.rand.choice(scenario["dialogue_patterns"])
        
        for p in dialogue:
            speaker_idx = self.rand.randint(0, len(speakers)-1)
            speaker_label = f"SPEAKER_{speaker_idx}"
            text = p["text"]
            dur = p["duration_sec"]
            
            words_list = []
            word_start = current_time
            for w in text.split():
                w_dur = dur / max(1, len(text.split()))
                words_list.append(WordTimestamp(
                    word=w,
                    start=word_start,
                    end=word_start + w_dur,
                    confidence=self.rand.uniform(0.8, 1.0),
                    speaker=speaker_idx
                ))
                word_start += w_dur
                
            segments.append(TranscriptSegment(
                segment_index=idx,
                speaker_label=speaker_label,
                text=text,
                start_time=current_time,
                end_time=current_time + dur,
                confidence=self.rand.uniform(0.85, 1.0),
                words=words_list
            ))
            
            current_time += dur + self.rand.uniform(0.1, 1.5)
            idx += 1
            
        return TranscriptionResult(
            session_id=session_id,
            segments=segments,
            duration_seconds=current_time,
            speaker_count=len(speakers)
        )

class FeatureGenerator:
    def __init__(self, rand: random.Random):
        self.rand = rand
        
    def generate(self, session_id: uuid.UUID, transcript: TranscriptionResult) -> Dict[str, FeatureResult]:
        summary = SummaryResult(
            title="Meeting Summary",
            executive_summary="This is an auto-generated executive summary based on the transcript.",
            key_topics=["planning", "review", "action items"],
            participant_count=transcript.speaker_count
        )
        
        action_item = ActionItem(
            description="Follow up on tasks.",
            assignee="SPEAKER_0",
            deadline="2026-10-10",
            priority="high",
            confidence=0.9,
            source_quote="I'll take that action item",
            status="pending"
        )
        actions = ActionItemsResult(items=[action_item])
        
        decision = Decision(
            description="Decided to move forward with the proposed architecture.",
            made_by="SPEAKER_1",
            context_quote="Let's do it.",
            confidence=0.95,
            timestamp=10.0
        )
        
        agenda = AgendaItem(
            topic="Review",
            summary="Review of the past week.",
            duration_seconds=300.0,
            speakers_involved=["SPEAKER_0", "SPEAKER_1"]
        )
        
        follow_up = FollowUp(
            description="Check back on Monday regarding the API deployment.",
            responsible_party="SPEAKER_0",
            due_context="Next week"
        )
        
        mom = MOMResult(
            title="Minutes of Meeting",
            date=datetime.utcnow(),
            attendees=[f"SPEAKER_{i}" for i in range(transcript.speaker_count)],
            agenda_items=[agenda],
            decisions=[decision],
            action_items=[action_item],
            follow_ups=[follow_up],
            executive_summary="Summary of meeting discussions."
        )
        
        sentiment = SentimentResult(
            overall_sentiment="positive",
            speaker_sentiments=[
                SentimentEntry(speaker_label="SPEAKER_0", sentiment="positive", confidence=0.8, notable_moments=[])
            ],
            sentiment_trend=[{"time": 0, "sentiment": "positive"}]
        )
        
        return {
            "summary": FeatureResult("summary", summary.__dict__, 1500, "gpt-4"),
            "action_items": FeatureResult("action_items", actions.__dict__, 1200, "gpt-4"),
            "mom": FeatureResult("mom", mom.__dict__, 2500, "gpt-4"),
            "sentiment": FeatureResult("sentiment", sentiment.__dict__, 800, "gpt-4")
        }

class SearchDataGenerator:
    def __init__(self, rand: random.Random):
        self.rand = rand

    def generate(self) -> tuple[SearchRequest, List[SearchResultItem]]:
        req = SearchRequest(query="action item", search_mode=SearchMode.HYBRID)
        item = SearchResultItem(
            segment_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            session_title="Weekly Sync",
            speaker_label="SPEAKER_0",
            speaker_name="Alice",
            text="I'll take that action item.",
            start_time=10.0,
            end_time=12.0,
            rrf_score=0.9,
            vector_rank=1,
            text_rank=1,
            session_date=datetime.utcnow()
        )
        return req, [item]

class EmbeddingGenerator:
    def generate(self, text: str) -> List[float]:
        h = hashlib.sha256(text.encode()).digest()
        rng = random.Random(int.from_bytes(h, 'little'))
        return [rng.uniform(-1.0, 1.0) for _ in range(1536)]

class SimulationDataGenerator:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.rand = random.Random(config.random_seed)
        self.session_gen = SessionGenerator(self.rand)
        self.transcript_gen = TranscriptGenerator(self.rand)
        self.feature_gen = FeatureGenerator(self.rand)
        self.search_gen = SearchDataGenerator(self.rand)
        self.embed_gen = EmbeddingGenerator()

    def generate_all(self):
        dataset = []
        for _ in range(self.config.num_sessions):
            sc, sr = self.session_gen.generate()
            transcript = self.transcript_gen.generate(sr.id, sr.duration_seconds or 1800.0)
            features = self.feature_gen.generate(sr.id, transcript)
            
            dataset.append({
                "session_create": sc,
                "session_response": sr,
                "transcript": transcript,
                "features": features
            })
            
        return dataset
