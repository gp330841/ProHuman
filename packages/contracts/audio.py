from __future__ import annotations

from enum import Enum
from pydantic import BaseModel

class AudioFormat(str, Enum):
    OPUS = "OPUS"
    WAV = "WAV"
    PCM16 = "PCM16"

class AudioChunkMeta(BaseModel):
    chunk_index: int
    size_bytes: int
    checksum: str
    duration_ms: int | None = None
    s3_key: str

class AudioSessionConfig(BaseModel):
    sample_rate: int = 16000
    channels: int = 1
    format: AudioFormat
    chunk_size_bytes: int = 4096

MAX_CHUNK_SIZE_BYTES = 1_048_576
ALLOWED_SAMPLE_RATES = {8000, 16000, 44100, 48000}

AUDIO_MAGIC_BYTES = {
    AudioFormat.OPUS: b"OggS",
    AudioFormat.WAV: b"RIFF",
}
