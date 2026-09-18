from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, UploadFile, File, Form, Header
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis, get_storage, get_session_repo
from app.services.storage import S3StorageService
from app.services.task_dispatcher import TaskDispatcher
from app.services.audio_validator import AudioValidator, ValidationResult
from packages.contracts.audio import AudioFormat, AudioSessionConfig
from packages.db.repositories.session_repo import SessionRepository
from packages.db.models.session import SessionStatusEnum
from packages.db.models.audio_chunk import AudioChunk

router = APIRouter()

@router.websocket("/stream/{session_id}")
async def audio_stream(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    storage: S3StorageService = Depends(get_storage),
    session_repo: SessionRepository = Depends(get_session_repo)
) -> None:
    """WebSocket endpoint for audio streaming."""
    await websocket.accept()
    
    # Validate session
    session = await session_repo.get(session_id)
    if not session or session.status not in (SessionStatusEnum.CREATED, SessionStatusEnum.RECORDING):
        await websocket.close(code=4000, reason="Invalid session or status")
        return

    # Await initial config
    try:
        config_data = await websocket.receive_json()
        config = AudioSessionConfig(**config_data)
    except Exception:
        await websocket.close(code=4000, reason="Invalid config")
        return

    queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
    validator = AudioValidator()
    chunk_index = 0
    
    async def process_queue() -> None:
        nonlocal chunk_index
        while True:
            chunk = await queue.get()
            if chunk == b"__EOF__":
                break
                
            validation: ValidationResult = validator.validate_chunk(chunk, config.format)
            if validation.valid:
                # Upload to S3
                s3_key = await storage.upload_chunk(session_id, chunk_index, chunk, "application/octet-stream")
                
                # Compute hash
                checksum = hashlib.sha256(chunk).hexdigest()
                
                # Insert chunk (idempotent setup assuming db constraint)
                db_chunk = AudioChunk(
                    session_id=session_id,
                    chunk_index=chunk_index,
                    s3_key=s3_key,
                    checksum=checksum,
                    size_bytes=len(chunk)
                )
                db.add(db_chunk)
                await db.commit()
                chunk_index += 1
            queue.task_done()

    processor_task = asyncio.create_task(process_queue())

    try:
        while True:
            data = await websocket.receive_bytes()
            # backpressure
            await queue.put(data)
    except WebSocketDisconnect:
        pass
    finally:
        await queue.put(b"__EOF__")
        await processor_task
        
        # Dispatch transcription task
        dispatcher = TaskDispatcher(redis)
        # We might have multiple chunks, typically we'd dispatch per chunk or batch
        await dispatcher.dispatch_transcription(session_id, f"{session_id}/latest")
        
        # Finalize session
        session.status = SessionStatusEnum.PROCESSING
        await session_repo.update(session_id, status=SessionStatusEnum.PROCESSING)
        await db.commit()

@router.post("/{session_id}/upload")
async def upload_audio(
    session_id: str,
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    storage: S3StorageService = Depends(get_storage),
    session_repo: SessionRepository = Depends(get_session_repo)
) -> JSONResponse:
    """HTTP endpoint for audio upload."""
    if idempotency_key:
        is_set = await redis.setnx(f"upload:{idempotency_key}", "1")
        if not is_set:
            return JSONResponse(status_code=409, content={"message": "Duplicate request"})
            
    session = await session_repo.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    data = await file.read()
    validator = AudioValidator()
    if not validator.validate_chunk(data).valid:
        raise HTTPException(status_code=400, detail="Invalid audio format")
        
    s3_key = await storage.upload_file(session_id, file.filename or "upload.wav", data, file.content_type or "audio/wav")
    
    db_chunk = AudioChunk(
        session_id=session_id,
        chunk_index=0,
        s3_key=s3_key,
        checksum=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data)
    )
    db.add(db_chunk)
    
    session.status = SessionStatusEnum.PROCESSING
    await db.commit()
    
    dispatcher = TaskDispatcher(redis)
    await dispatcher.dispatch_transcription(session_id, s3_key)
    
    return JSONResponse(status_code=201, content={"session_id": session_id, "status": "processing"})

__all__ = ["router"]
