import asyncio
import json
import uuid
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import random

@dataclass
class TranscriptionResult:
    text: str
    confidence: float
    words: List[Dict[str, Any]]
    duration: float

class MockSTTAdapter:
    """Mock Deepgram Speech-to-Text adapter."""
    
    def __init__(self, processing_factor: float = 0.1):
        # processing_factor: time taken relative to audio duration
        self.processing_factor = processing_factor
        self.calls = 0

    async def transcribe(self, audio_data: bytes, metadata: Dict[str, Any] = None) -> TranscriptionResult:
        self.calls += 1
        duration = metadata.get("duration", 60.0) if metadata else 60.0
        
        # Simulate network or processing latency proportional to audio duration
        await asyncio.sleep(min(duration * self.processing_factor, 2.0))
        
        # Error simulation based on some random chance or specific metadata
        if metadata and metadata.get("simulate_error") == "timeout":
            raise TimeoutError("Simulated STT timeout")
            
        if metadata and metadata.get("simulate_error") == "rate_limit":
            raise Exception("429 Too Many Requests")

        # Generate realistic-looking segments
        num_words = int(duration * 2.5) # approx 2.5 words per second
        words = []
        current_time = 0.0
        text_parts = []
        
        sample_words = ["okay", "so", "the", "project", "is", "going", "well", "we", "need", "to", "focus", "on", "the", "backend"]
        
        for i in range(num_words):
            word_str = random.choice(sample_words)
            text_parts.append(word_str)
            word_dur = random.uniform(0.2, 0.6)
            words.append({
                "word": word_str,
                "start": current_time,
                "end": current_time + word_dur,
                "confidence": random.uniform(0.8, 0.99)
            })
            current_time += word_dur + random.uniform(0.0, 0.2)

        return TranscriptionResult(
            text=" ".join(text_parts),
            confidence=0.92,
            words=words,
            duration=duration
        )


class MockLLMClient:
    """Mock LiteLLM + Instructor client."""
    
    def __init__(self, latency_ms: int = 500):
        self.latency_ms = latency_ms
        self.calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.history = []

    async def generate_structured(self, prompt: str, schema: Any, feature_type: str = "general") -> Any:
        """
        Simulates structured output generation. 
        `schema` is expected to be a Pydantic model class.
        """
        self.calls += 1
        
        # Simulate latency
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)
            
        # Simulate token usage (rough approximation)
        input_tokens = len(prompt.split()) * 1.3
        output_tokens = 150
        self.total_input_tokens += int(input_tokens)
        self.total_output_tokens += int(output_tokens)
        
        self.history.append({
            "feature": feature_type,
            "prompt_length": len(prompt),
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens)
        })
        
        # Error simulation hooks can be added here
        if "SIMULATE_RATE_LIMIT" in prompt:
            raise Exception("Rate limit exceeded")

        # Generate mock response based on feature type
        mock_data = {}
        if feature_type == "summary":
            mock_data = {"summary": "This is a simulated summary of the conversation.", "key_points": ["Point 1", "Point 2"]}
        elif feature_type == "mom":
            mock_data = {"minutes": "Meeting started. Discussed topics.", "participants": ["Speaker A"]}
        elif feature_type == "action_items":
            mock_data = {"items": [{"owner": "John", "task": "Update the database schema", "deadline": "Tomorrow"}]}
        elif feature_type == "sentiment":
            mock_data = {"overall": "positive", "score": 0.85}
        else:
            mock_data = {"result": "Default mock response"}

        # Attempt to construct the schema if it's a Pydantic model or similar
        try:
            return schema(**mock_data)
        except Exception:
            # Fallback to returning raw dict if schema instantiation fails
            return mock_data

class MockEmbeddingClient:
    """Mock OpenAI Embeddings client."""
    
    def __init__(self):
        self.calls = 0
        self.total_tokens = 0
        self.vector_dim = 1536

    def _generate_vector(self, text: str) -> List[float]:
        """Generates a deterministic vector for a given string."""
        # Use a hash to seed a random number generator for determinism
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        
        # Generate normalized vector
        vec = [rng.gauss(0, 1) for _ in range(self.vector_dim)]
        magnitude = sum(x**2 for x in vec) ** 0.5
        if magnitude > 0:
            vec = [x / magnitude for x in vec]
        return vec

    async def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Simulates batch embedding."""
        self.calls += 1
        
        if len(texts) > batch_size * 10:
            raise ValueError(f"Batch size too large: {len(texts)}")
            
        results = []
        for text in texts:
            # Simulate token usage
            self.total_tokens += int(len(text.split()) * 1.3)
            
            vec = self._generate_vector(text)
            results.append(vec)
            
        # Simulate small latency
        await asyncio.sleep(0.05 * len(texts))
        
        return results

    async def embed(self, text: str) -> List[float]:
        res = await self.embed_batch([text])
        return res[0]
