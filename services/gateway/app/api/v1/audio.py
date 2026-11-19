"""Authenticated recording capture, upload, and playback."""

import asyncio
import hashlib
import re
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select

from packages.access import Principal, require_principal
from app.config import get_settings
import structlog
from app.services.live_transcription import LiveTranscription
from app.dependencies import get_session_repo, get_storage
from app.services.storage import S3StorageService
from packages.contracts.audio import MAX_CHUNK_SIZE_BYTES
from packages.db.models.audio_chunk import AudioChunk
from packages.db.models.session import Session, SessionStatusEnum
from packages.db.repositories.pipeline_repo import enqueue_stage
from packages.db.repositories.session_repo import SessionRepository

router = APIRouter()
logger = structlog.get_logger(__name__)
MAX_AUDIO_FILE_SIZE_BYTES = 100 * 1024 * 1024
AUDIO_EXTENSIONS = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/wav": "wav"}
PROTOCOL = "prohuman.audio.v1"


class StartCapture(BaseModel):
    type: str
    mime_type: str = Field(max_length=50)


class FinishCapture(BaseModel):
    type: str
    chunk_count: int = Field(gt=0)


async def _queue_recording(repo: SessionRepository, session: Session, key: str, mime_type: str):
    session.s3_key = key
    session.audio_format = mime_type
    session.status = SessionStatusEnum.PROCESSING
    await enqueue_stage(repo.session, session.id, "transcription")
    await repo.session.commit()


@router.websocket("/stream/{session_id}")
async def audio_stream(
    websocket: WebSocket,
    session_id: UUID,
    repo: SessionRepository = Depends(get_session_repo),
    storage: S3StorageService = Depends(get_storage),
) -> None:
    if PROTOCOL not in websocket.scope["subprotocols"]:
        await websocket.close(code=1002)
        return

    await websocket.accept(subprotocol=PROTOCOL)
    db = repo.session
    live = None
    try:
        start = StartCapture.model_validate(await asyncio.wait_for(websocket.receive_json(), timeout=10))
        mime_type = start.mime_type.split(";", 1)[0]
        if start.type != "start" or mime_type not in AUDIO_EXTENSIONS:
            await websocket.close(code=1003, reason="Unsupported audio format")
            return

        session = await repo.get_for_update(session_id)
        if session is None:
            await websocket.close(code=1008, reason="Recording unavailable")
            return
        if session.s3_key:
            await websocket.send_json({"type": "finished"})
            await websocket.close()
            return
        if session.status not in {SessionStatusEnum.CREATED, SessionStatusEnum.RECORDING}:
            await websocket.close(code=1008, reason="Recording unavailable")
            return
        if session.status == SessionStatusEnum.RECORDING and session.audio_format != mime_type:
            await websocket.close(code=1003, reason="Recording format changed")
            return
        session.status = SessionStatusEnum.RECORDING
        session.audio_format = mime_type
        next_chunk = await db.scalar(
            select(func.count()).select_from(AudioChunk).where(AudioChunk.session_id == session_id)
        )
        await db.commit()
        api_key = get_settings().deepgram_api_key
        if api_key and next_chunk == 0 and mime_type in {"audio/webm", "audio/ogg", "audio/wav"}:
            language = (session.metadata_ or {}).get("language", "auto")
            live = LiveTranscription(api_key, "multi" if language in {"auto", "multi"} else language, websocket.send_json)
        await websocket.send_json({"type": "ready", "next_chunk": next_chunk, "live_captions": live is not None})

        while True:
            frame = await asyncio.wait_for(websocket.receive(), timeout=90)
            if frame["type"] == "websocket.disconnect":
                return
            session = await repo.get_for_update(session_id)
            if session is None or session.status != SessionStatusEnum.RECORDING:
                if session is not None and session.s3_key:
                    await websocket.send_json({"type": "finished"})
                    await websocket.close()
                    return
                await websocket.close(code=1008, reason="Recording unavailable")
                return

            if (binary := frame.get("bytes")) is not None:
                data = binary[4:]
                if not data or len(data) > MAX_CHUNK_SIZE_BYTES:
                    await websocket.close(code=1009, reason="Invalid audio chunk length")
                    return
                index = int.from_bytes(binary[:4], "big")
                chunks, total_bytes = (await db.execute(
                    select(func.count(), func.coalesce(func.sum(AudioChunk.size_bytes), 0))
                    .where(AudioChunk.session_id == session_id)
                )).one()
                checksum = hashlib.sha256(data).hexdigest()
                if index < chunks:
                    previous = await db.scalar(
                        select(AudioChunk.checksum).where(
                            AudioChunk.session_id == session_id, AudioChunk.chunk_index == index
                        )
                    )
                    if previous != checksum:
                        await websocket.close(code=1008, reason="Conflicting audio chunk")
                        return
                elif index != chunks or total_bytes + len(data) > MAX_AUDIO_FILE_SIZE_BYTES:
                    await websocket.close(code=1009, reason="Audio chunk out of sequence or recording too large")
                    return
                else:
                    key = await storage.upload_chunk(str(session_id), index, data, mime_type)
                    db.add(AudioChunk(session_id=session_id, chunk_index=index, s3_key=key,
                                      size_bytes=len(data), checksum=checksum))
                await db.commit()
                await websocket.send_json({"type": "ack", "index": index})
                if live and index == chunks:
                    live.append(data)
                continue

            finish = FinishCapture.model_validate_json(frame.get("text") or "")
            chunks = (await db.scalars(
                select(AudioChunk).where(AudioChunk.session_id == session_id)
                .order_by(AudioChunk.chunk_index)
            )).all()
            if finish.type != "finish" or finish.chunk_count != len(chunks):
                await websocket.close(code=1008, reason="Recording still has missing chunks")
                return
            filename = f"recording.{AUDIO_EXTENSIONS[mime_type]}"
            key = await storage.assemble_recording(
                str(session_id), filename, [chunk.s3_key for chunk in chunks], mime_type
            )
            await _queue_recording(repo, session, key, mime_type)
            await websocket.send_json({"type": "finished"})
            await websocket.close()
            return
    except TimeoutError:
        await websocket.close(code=1001, reason="Recording connection idle")
    except WebSocketDisconnect:
        return
    except (ValidationError, ValueError):
        await websocket.close(code=1003, reason="Invalid capture message")
    finally:
        if live:
            await live.close()


@router.post("/{session_id}/upload", status_code=201)
async def upload_audio(
    session_id: UUID,
    file: UploadFile = File(...),
    repo: SessionRepository = Depends(get_session_repo),
    storage: S3StorageService = Depends(get_storage),
):
    session = await repo.get_for_update(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    data = await file.read(MAX_AUDIO_FILE_SIZE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    if len(data) > MAX_AUDIO_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Audio file exceeds 100 MB limit")
    checksum = hashlib.sha256(data).hexdigest()
    existing = await repo.session.scalar(select(AudioChunk).where(
        AudioChunk.session_id == session_id, AudioChunk.chunk_index == 0
    ))
    if session.s3_key:
        if not existing or existing.checksum != checksum or existing.s3_key != session.s3_key:
            raise HTTPException(status_code=409, detail="Session already has a recording")
    else:
        if session.status != SessionStatusEnum.CREATED:
            raise HTTPException(status_code=409, detail="Session already has an active recording")
        filename = Path(file.filename or "audio-upload").name
        mime_type = file.content_type or "application/octet-stream"
        key = await storage.upload_file(str(session_id), f"uploads/{filename}", data, mime_type)
        repo.session.add(AudioChunk(session_id=session_id, chunk_index=0, s3_key=key,
                                    size_bytes=len(data), checksum=checksum))
        await _queue_recording(repo, session, key, mime_type)
    return {"session_id": str(session_id), "status": session.status.value}


@router.get("/{session_id}/playback")
async def playback(
    session_id: UUID,
    request: Request,
    principal: Principal = Depends(require_principal),
    repo: SessionRepository = Depends(get_session_repo),
    storage: S3StorageService = Depends(get_storage),
):
    session = await repo.get(session_id)
    if not session or not session.s3_key:
        raise HTTPException(status_code=404, detail="Recording unavailable")
    range_header = request.headers.get("range")
    if range_header and not re.fullmatch(r"bytes=(?:\d+-\d*|-\d+)", range_header):
        raise HTTPException(status_code=416, detail="Invalid byte range")
    response = await storage.playback_response(session.s3_key, range_header)
    logger.info("recording_playback", workspace_id=str(principal.workspace_id),
                session_id=str(session_id), user_id=principal.user_id)
    return response
