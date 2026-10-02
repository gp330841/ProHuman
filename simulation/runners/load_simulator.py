"""
Load and resource simulation — estimates production costs, identifies
bottlenecks, and projects infrastructure usage at scale.
"""

import asyncio
import math
import random
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LoadResult:
    total_operations: int = 0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    errors: int = 0
    bottlenecks: List[str] = field(default_factory=list)
    throughput_per_second: float = 0.0
    queue_depths: Dict[str, int] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceEstimate:
    db_storage_mb: float = 0.0
    redis_memory_mb: float = 0.0
    s3_storage_mb: float = 0.0
    api_cost_usd: float = 0.0
    cost_projections: Dict[str, float] = field(default_factory=dict)
    breakdown: Dict[str, Any] = field(default_factory=dict)


class LoadSimulator:
    """Simulates concurrent load and projects resource usage."""

    # ── Cost constants (based on real pricing) ───────────────────────
    DEEPGRAM_COST_PER_MINUTE = 0.0043        # Nova-2 pay-as-you-go
    OPENAI_EMBEDDING_COST_PER_1K_TOKENS = 0.00002  # text-embedding-3-small
    OPENAI_GPT4O_INPUT_PER_1K = 0.005        # gpt-4o input
    OPENAI_GPT4O_OUTPUT_PER_1K = 0.015       # gpt-4o output
    POSTGRES_STORAGE_PER_GB_MONTH = 0.10     # managed DB
    S3_STORAGE_PER_GB_MONTH = 0.023          # S3 standard
    REDIS_PER_GB_HOUR = 0.0068               # ElastiCache

    # ── Per-session resource estimates ───────────────────────────────
    AVG_AUDIO_DURATION_MINUTES = 30
    AVG_AUDIO_SIZE_MB = 15                   # WebM/Opus at typical bitrate
    AVG_SEGMENTS_PER_SESSION = 35
    AVG_WORDS_PER_SEGMENT = 40
    AVG_EMBEDDING_DIM = 1536
    FEATURES_PER_SESSION = 5                 # summary, mom, action_items, sentiment, follow_up
    AVG_LLM_INPUT_TOKENS_PER_FEATURE = 2000
    AVG_LLM_OUTPUT_TOKENS_PER_FEATURE = 500

    async def simulate_concurrent_sessions(
        self, n_concurrent: int, config: dict
    ) -> LoadResult:
        """Simulate N sessions being processed concurrently."""
        rand = random.Random(42)
        latencies: List[float] = []
        errors = 0
        queue_depths = {"transcription": 0, "embedding": 0, "features": 0}

        async def simulate_session(session_idx: int):
            nonlocal errors
            start = time.time()
            try:
                # Simulate session phases with realistic latency distributions
                # Phase 1: Audio upload (network bound)
                upload_latency = rand.gauss(200, 50)  # mean 200ms, std 50ms
                await asyncio.sleep(max(0.001, upload_latency / 10000))

                # Phase 2: Transcription task queuing
                queue_depths["transcription"] += 1
                transcription_latency = rand.gauss(5000, 1500)  # 5s avg for STT
                await asyncio.sleep(max(0.001, transcription_latency / 100000))
                queue_depths["transcription"] -= 1

                # Phase 3: Embedding generation
                queue_depths["embedding"] += 1
                embed_latency = rand.gauss(1000, 300)  # 1s avg
                await asyncio.sleep(max(0.001, embed_latency / 100000))
                queue_depths["embedding"] -= 1

                # Phase 4: Feature extraction
                queue_depths["features"] += 1
                feature_latency = rand.gauss(8000, 2000)  # 8s avg for LLM calls
                await asyncio.sleep(max(0.001, feature_latency / 100000))
                queue_depths["features"] -= 1

                total_latency = upload_latency + transcription_latency + embed_latency + feature_latency
                latencies.append(total_latency)

            except Exception:
                errors += 1
                latencies.append(30000)  # timeout

        # Run concurrent sessions
        start_time = time.time()
        tasks = [simulate_session(i) for i in range(n_concurrent)]
        await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Calculate percentiles
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)

        bottlenecks = []
        avg_lat = statistics.mean(sorted_lat) if sorted_lat else 0

        # Detect bottlenecks
        if n_concurrent > 10:
            bottlenecks.append("Feature extraction queue (LLM calls) — consider increasing worker concurrency")
        if n_concurrent > 20:
            bottlenecks.append("STT processing — consider horizontal scaling of transcription workers")
        if n_concurrent > 50:
            bottlenecks.append("PostgreSQL connection pool — current pool_size=10, max_overflow=20 may be insufficient")
            bottlenecks.append("Redis connection pool — ensure sufficient connections for rate limiting under load")

        return LoadResult(
            total_operations=n_concurrent * 4,  # 4 phases per session
            avg_latency_ms=round(avg_lat, 1),
            p50_latency_ms=round(sorted_lat[n // 2], 1) if n else 0,
            p95_latency_ms=round(sorted_lat[int(n * 0.95)], 1) if n else 0,
            p99_latency_ms=round(sorted_lat[int(n * 0.99)], 1) if n else 0,
            max_latency_ms=round(sorted_lat[-1], 1) if n else 0,
            errors=errors,
            bottlenecks=bottlenecks,
            throughput_per_second=round(n_concurrent / max(0.001, total_time), 1),
            queue_depths={k: max(0, v) for k, v in queue_depths.items()},
            details={
                "concurrent_sessions": n_concurrent,
                "total_time_seconds": round(total_time, 3),
                "latency_distribution": {
                    "min": round(sorted_lat[0], 1) if sorted_lat else 0,
                    "max": round(sorted_lat[-1], 1) if sorted_lat else 0,
                    "std_dev": round(statistics.stdev(sorted_lat), 1) if len(sorted_lat) > 1 else 0,
                },
            },
        )

    async def simulate_burst_traffic(
        self, requests_per_second: int, duration_seconds: int
    ) -> LoadResult:
        """Simulate burst API traffic to test rate limiting."""
        rand = random.Random(42)
        total_requests = requests_per_second * duration_seconds
        latencies = []
        errors = 0
        rate_limited = 0

        # Simulate token bucket rate limiter (10 tokens/sec, burst 20)
        bucket_size = 20
        refill_rate = 10  # tokens per second
        tokens = bucket_size

        for second in range(duration_seconds):
            # Refill tokens
            tokens = min(bucket_size, tokens + refill_rate)

            for req in range(requests_per_second):
                if tokens >= 1:
                    tokens -= 1
                    latency = rand.gauss(50, 15)  # 50ms avg response
                    latencies.append(max(1, latency))
                else:
                    rate_limited += 1
                    errors += 1
                    latencies.append(0)  # 429 response

        accepted = [l for l in latencies if l > 0]
        sorted_lat = sorted(accepted) if accepted else [0]
        n = len(sorted_lat)

        bottlenecks = []
        if rate_limited > 0:
            bottlenecks.append(
                f"Rate limiter activated: {rate_limited}/{total_requests} requests rejected "
                f"({100*rate_limited/total_requests:.1f}%)"
            )
        if requests_per_second > refill_rate:
            bottlenecks.append(
                f"Sustained RPS ({requests_per_second}) exceeds rate limit ({refill_rate}/s) — "
                f"requests will queue or be rejected"
            )

        return LoadResult(
            total_operations=total_requests,
            avg_latency_ms=round(statistics.mean(sorted_lat), 1) if sorted_lat else 0,
            p50_latency_ms=round(sorted_lat[n // 2], 1) if n else 0,
            p95_latency_ms=round(sorted_lat[int(n * 0.95)], 1) if n else 0,
            p99_latency_ms=round(sorted_lat[int(n * 0.99)], 1) if n else 0,
            max_latency_ms=round(sorted_lat[-1], 1) if n else 0,
            errors=errors,
            bottlenecks=bottlenecks,
            throughput_per_second=round(len(accepted) / max(1, duration_seconds), 1),
            details={
                "total_requests": total_requests,
                "accepted": len(accepted),
                "rate_limited": rate_limited,
                "rate_limit_pct": round(100 * rate_limited / max(1, total_requests), 1),
                "bucket_size": bucket_size,
                "refill_rate_per_sec": refill_rate,
            },
        )

    def simulate_resource_usage(
        self, num_sessions: int, avg_duration_minutes: Optional[float] = None
    ) -> ResourceEstimate:
        """Project infrastructure costs for a given number of sessions."""
        dur = avg_duration_minutes or self.AVG_AUDIO_DURATION_MINUTES
        segs = self.AVG_SEGMENTS_PER_SESSION
        words = self.AVG_WORDS_PER_SEGMENT

        # ── Storage estimates ────────────────────────────────────────
        # PostgreSQL
        session_row_bytes = 500  # UUID + strings + JSONB metadata
        chunk_row_bytes = 200   # per chunk
        segment_row_bytes = (
            200                  # base fields
            + words * 5          # text (avg 5 bytes/word)
            + self.AVG_EMBEDDING_DIM * 4  # float32 vector
            + words * 40         # word_timestamps JSONB
        )
        feature_row_bytes = 2000  # JSONB payload avg

        db_bytes_per_session = (
            session_row_bytes
            + chunk_row_bytes * 2
            + segment_row_bytes * segs
            + feature_row_bytes * self.FEATURES_PER_SESSION
        )
        db_storage_mb = (db_bytes_per_session * num_sessions) / (1024 * 1024)

        # MinIO / S3
        s3_storage_mb = self.AVG_AUDIO_SIZE_MB * num_sessions

        # Redis (ephemeral: keys, rate limits, idempotency)
        redis_keys_per_session = 10  # idem keys + rate counters + task results
        redis_bytes_per_key = 256
        redis_memory_mb = (redis_keys_per_session * redis_bytes_per_key * num_sessions) / (1024 * 1024)

        # ── API cost estimates ───────────────────────────────────────
        # Deepgram STT
        deepgram_cost = self.DEEPGRAM_COST_PER_MINUTE * dur * num_sessions

        # OpenAI Embeddings
        total_embed_tokens = segs * words * num_sessions
        embedding_cost = (total_embed_tokens / 1000) * self.OPENAI_EMBEDDING_COST_PER_1K_TOKENS

        # OpenAI GPT-4o (feature extraction)
        total_input_tokens = self.AVG_LLM_INPUT_TOKENS_PER_FEATURE * self.FEATURES_PER_SESSION * num_sessions
        total_output_tokens = self.AVG_LLM_OUTPUT_TOKENS_PER_FEATURE * self.FEATURES_PER_SESSION * num_sessions
        llm_cost = (
            (total_input_tokens / 1000) * self.OPENAI_GPT4O_INPUT_PER_1K
            + (total_output_tokens / 1000) * self.OPENAI_GPT4O_OUTPUT_PER_1K
        )

        # Infrastructure hosting (monthly)
        infra_monthly = (
            (db_storage_mb / 1024) * self.POSTGRES_STORAGE_PER_GB_MONTH
            + (s3_storage_mb / 1024) * self.S3_STORAGE_PER_GB_MONTH
            + (redis_memory_mb / 1024) * self.REDIS_PER_GB_HOUR * 730  # hours/month
        )

        total_api_cost = deepgram_cost + embedding_cost + llm_cost
        total_cost = total_api_cost + infra_monthly

        # ── Projections ──────────────────────────────────────────────
        def project(n: int) -> float:
            return round(total_cost * (n / max(1, num_sessions)), 2)

        return ResourceEstimate(
            db_storage_mb=round(db_storage_mb, 2),
            redis_memory_mb=round(redis_memory_mb, 2),
            s3_storage_mb=round(s3_storage_mb, 2),
            api_cost_usd=round(total_api_cost, 2),
            cost_projections={
                "100_sessions": project(100),
                "1000_sessions": project(1000),
                "10000_sessions": project(10000),
                "100000_sessions": project(100000),
            },
            breakdown={
                "deepgram_stt": round(deepgram_cost, 4),
                "openai_embeddings": round(embedding_cost, 4),
                "openai_gpt4o_features": round(llm_cost, 4),
                "infra_monthly": round(infra_monthly, 4),
                "total_api_cost": round(total_api_cost, 4),
                "total_monthly_estimate": round(total_cost, 4),
                "per_session_cost": round(total_cost / max(1, num_sessions), 4),
                "per_session_breakdown": {
                    "stt": round(deepgram_cost / max(1, num_sessions), 4),
                    "embeddings": round(embedding_cost / max(1, num_sessions), 4),
                    "llm_features": round(llm_cost / max(1, num_sessions), 4),
                },
            },
        )
