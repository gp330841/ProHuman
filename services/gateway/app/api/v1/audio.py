from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, UploadFile, File, Header
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis, get_storage, get_session_repo
from app.services.storage import S3StorageService
from app.services.task_dispatcher import TaskDispatcher
from packages.contracts.audio import AudioFormat, AudioSessionConfig
from packages.db.repositories.session_repo import SessionRepository
from packages.db.models.session import SessionStatusEnum
from packages.db.models.audio_chunk import AudioChunk
from app.config import get_settings

router = APIRouter()
MAX_AUDIO_FILE_SIZE_BYTES = 100 * 1024 * 1024

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

    await session_repo.update(session_id, status=SessionStatusEnum.RECORDING)
    await db.commit()
    audio_data = bytearray()

    too_large = False
    try:
        while True:
            data = await websocket.receive_bytes()
            if len(audio_data) + len(data) > MAX_AUDIO_FILE_SIZE_BYTES:
                await websocket.close(code=1009, reason="Recording exceeds 100 MB limit")
                too_large = True
                break
            audio_data.extend(data)
    except WebSocketDisconnect:
        pass

    if too_large or not audio_data:
        await session_repo.update(session_id, status=SessionStatusEnum.FAILED)
        await db.commit()
        return

    content_type = "audio/webm" if config.format == AudioFormat.OPUS else "audio/wav"
    filename = "recording.webm" if config.format == AudioFormat.OPUS else "recording.wav"
    s3_key = await storage.upload_file(session_id, filename, bytes(audio_data), content_type)
    db.add(
        AudioChunk(
            session_id=session_id,
            chunk_index=0,
            s3_key=s3_key,
            checksum=hashlib.sha256(audio_data).hexdigest(),
            size_bytes=len(audio_data),
        )
    )
    await session_repo.update(
        session_id,
        status=SessionStatusEnum.PROCESSING,
        s3_key=s3_key,
        audio_format=config.format.value,
    )
    await db.commit()

    dispatcher = TaskDispatcher(redis, get_settings().redis_url)
    try:
        await dispatcher.dispatch_transcription(session_id, s3_key)
    except Exception as exc:
        await session_repo.update(session_id, status=SessionStatusEnum.FAILED)
        await db.commit()
        raise HTTPException(status_code=503, detail="Could not queue audio transcription") from exc

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
        
    data = await file.read(MAX_AUDIO_FILE_SIZE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    if len(data) > MAX_AUDIO_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Audio file exceeds 100 MB limit")

    filename = Path(file.filename or "audio-upload").name
    content_type = file.content_type or "application/octet-stream"
    s3_key = await storage.upload_file(session_id, filename, data, content_type)
    
    db_chunk = AudioChunk(
        session_id=session_id,
        chunk_index=0,
        s3_key=s3_key,
        checksum=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data)
    )
    db.add(db_chunk)
    
    session.status = SessionStatusEnum.PROCESSING
    session.s3_key = s3_key
    session.audio_format = content_type
    await db.commit()
    
    dispatcher = TaskDispatcher(redis, get_settings().redis_url)
    try:
        await dispatcher.dispatch_transcription(session_id, s3_key)
    except Exception as exc:
        await session_repo.update(session_id, status=SessionStatusEnum.FAILED)
        await db.commit()
        raise HTTPException(status_code=503, detail="Could not queue audio transcription") from exc
    
    return JSONResponse(status_code=201, content={"session_id": session_id, "status": "processing"})

__all__ = ["router"]
