"""
Audio-related data contracts.

Defines schemas and constants for audio formats, metadata, and configuration
used throughout the audio processing pipeline.
"""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel

class AudioFormat(str, Enum):
    """Supported audio formats for recording and processing."""
    OPUS = "OPUS"
    WAV = "WAV"
    PCM16 = "PCM16"

class AudioChunkMeta(BaseModel):
    """Metadata for a single chunk of audio data."""
    chunk_index: int
    size_bytes: int
    checksum: str
    duration_ms: int | None = None
    s3_key: str

class AudioSessionConfig(BaseModel):
    """Configuration for an audio recording session."""
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
