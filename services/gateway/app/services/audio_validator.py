"""Module for audio_validator.py."""
from __future__ import annotations

from typing import NamedTuple

from packages.contracts.audio import AudioFormat, MAX_CHUNK_SIZE_BYTES, AUDIO_MAGIC_BYTES

class ValidationResult(NamedTuple):
    """Class documentation."""
    valid: bool
    format_detected: AudioFormat | None
    error: str | None

class AudioValidator:
    """Validates audio chunks."""
    
    def validate_chunk(self, data: bytes, expected_format: AudioFormat | None = None) -> ValidationResult:
        """Validate an audio chunk."""
        if len(data) > MAX_CHUNK_SIZE_BYTES:
            return ValidationResult(False, None, f"Chunk size {len(data)} exceeds max {MAX_CHUNK_SIZE_BYTES}")
            
        detected_format = None
        for fmt, magic in AUDIO_MAGIC_BYTES.items():
            if magic and data.startswith(magic):
                detected_format = fmt
                break
        
        # If no magic bytes matched and we didn't require any (e.g. PCM)
        if detected_format is None and AudioFormat.PCM in AUDIO_MAGIC_BYTES:
            detected_format = AudioFormat.PCM
            
        if expected_format and detected_format and expected_format != detected_format:
             return ValidationResult(False, detected_format, f"Expected {expected_format}, got {detected_format}")
             
        return ValidationResult(True, detected_format, None)

__all__ = ["ValidationResult", "AudioValidator"]
