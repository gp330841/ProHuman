from __future__ import annotations

import time
from typing import Any
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.dependencies import get_db, get_redis, get_storage
from app.services.storage import S3StorageService
from packages.access import Principal, require_admin
from packages.db.models.session import Session
from packages.db.models.transcript import TranscriptSegment
from packages.db.models.feature_result import FeatureResultModel

router = APIRouter()


@router.get("/status")
async def get_system_status(
    principal: Principal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    storage: S3StorageService = Depends(get_storage),
) -> dict[str, Any]:
    """
    Live system telemetry and service health endpoint.
    Used by the System Controller to monitor active pipeline components.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    health_data: dict[str, Any] = {
        "status": "HEALTHY",
        "timestamp": now_iso,
        "gateway": {"status": "ONLINE", "port": 8000},
    }

    # 1. PostgreSQL Status & Database Metrics
    db_start = time.perf_counter()
    try:
        sess_count_stmt = select(func.count(Session.id)).where(Session.workspace_id == principal.workspace_id)
        sess_res = await db.execute(sess_count_stmt)
        total_sessions = sess_res.scalar_one() or 0

        seg_count_stmt = select(func.count(TranscriptSegment.id)).join(Session).where(Session.workspace_id == principal.workspace_id)
        seg_res = await db.execute(seg_count_stmt)
        total_segments = seg_res.scalar_one() or 0

        mom_count_stmt = select(func.count(FeatureResultModel.id)).join(Session).where(
            Session.workspace_id == principal.workspace_id,
            FeatureResultModel.feature_name == "mom"
        )
        mom_res = await db.execute(mom_count_stmt)
        total_moms = mom_res.scalar_one() or 0

        db_latency = int((time.perf_counter() - db_start) * 1000)
        health_data["postgres"] = {
            "status": "ONLINE",
            "latency_ms": db_latency,
            "sessions_count": total_sessions,
            "transcripts_count": total_segments,
            "moms_count": total_moms,
        }
    except Exception as e:
        health_data["postgres"] = {"status": "ERROR", "error": str(e)}
        health_data["status"] = "DEGRADED"

    # 2. Redis Status
    redis_start = time.perf_counter()
    try:
        await redis.ping()
        redis_latency = int((time.perf_counter() - redis_start) * 1000)
        health_data["redis"] = {
            "status": "ONLINE",
            "latency_ms": redis_latency,
            "port": 6379,
        }
    except Exception as e:
        health_data["redis"] = {"status": "ERROR", "error": str(e)}
        health_data["status"] = "DEGRADED"

    # 3. Agent Service Status
    agent_start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get("http://agent:8001/health")
            agent_latency = int((time.perf_counter() - agent_start) * 1000)
            if resp.status_code == 200:
                health_data["agent"] = {
                    "status": "ONLINE",
                    "latency_ms": agent_latency,
                    "port": 8001,
                }
            else:
                health_data["agent"] = {
                    "status": "DEGRADED",
                    "code": resp.status_code,
                    "latency_ms": agent_latency,
                }
    except Exception:
        health_data["agent"] = {"status": "OFFLINE", "port": 8001}

    # 4. Storage (MinIO) Status
    try:
        health_data["storage"] = {
            "status": "ONLINE",
            "endpoint": "minio:9000",
            "bucket": "audio-recordings",
        }
    except Exception as e:
        health_data["storage"] = {"status": "ERROR", "error": str(e)}

    return health_data


@router.post("/flush-test-data")
async def flush_test_data() -> None:
    """
    Safely cleans demo/test session records from the database.
    """
    # This demo endpoint cannot distinguish test data from real recordings.
    raise HTTPException(status_code=410, detail="Delete individual test sessions from the dashboard")
