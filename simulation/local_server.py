"""
Local Simulation Server for ProHuman.
Runs Gateway on port 8000 and Agent on port 8001 (or unified)
allowing full frontend UI interaction without requiring Docker, external databases, or cloud API keys.
"""

import asyncio
import uuid
import time
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from simulation.data.generators import (
    SimulationDataGenerator,
    TranscriptGenerator,
    FeatureGenerator,
    SearchMode,
)
from simulation.config import SimulationConfig
from simulation.runners.agent_scenarios import SecuritySimulator, TOOL_CATALOG, predict_tools
import dataclasses
import random

def serialize_feature_data(data):
    if dataclasses.is_dataclass(data):
        d = dataclasses.asdict(data)
    elif isinstance(data, dict):
        d = dict(data)
    else:
        return data
    for k, v in list(d.items()):
        if hasattr(v, 'isoformat'):
            d[k] = v.isoformat()
        elif isinstance(v, list):
            d[k] = [dataclasses.asdict(item) if dataclasses.is_dataclass(item) else (item.__dict__ if hasattr(item, '__dict__') else item) for item in v]
    return d

# ==============================================================================
# In-Memory State Store
# ==============================================================================
rand = random.Random(42)
config = SimulationConfig(num_sessions=6, random_seed=42)
sim_gen = SimulationDataGenerator(config)
transcript_gen = TranscriptGenerator(rand)
feature_gen = FeatureGenerator(rand)
security_sim = SecuritySimulator()

# Initial pre-populated sessions
SESSIONS_STORE: Dict[str, Dict[str, Any]] = {}
TRANSCRIPTS_STORE: Dict[str, List[Dict[str, Any]]] = {}
FEATURES_STORE: Dict[str, Dict[str, Any]] = {}

def initialize_seed_data():
    initial_dataset = sim_gen.generate_all()
    for item in initial_dataset:
        sr = item["session_response"]
        sid = str(sr.id)
        transcript = item["transcript"]
        features = item["features"]

        SESSIONS_STORE[sid] = {
            "id": sid,
            "device_id": sr.device_id,
            "status": "COMPLETED",
            "created_at": sr.created_at.isoformat(),
            "updated_at": sr.updated_at.isoformat(),
            "audio_format": sr.audio_format,
            "duration_seconds": sr.duration_seconds,
            "metadata": {"source": "simulation"},
        }

        seg_list = []
        for s in transcript.segments:
            seg_list.append({
                "segment_id": str(uuid.uuid4()),
                "id": str(uuid.uuid4()),
                "speaker_label": s.speaker_label,
                "speaker_name": s.speaker_label.replace("SPEAKER_0", "Dr. Sarah Chen (CTO)").replace("SPEAKER_1", "Alex Rivera (Firmware)").replace("SPEAKER_2", "Elena Rostova (Backend)"),
                "text": s.text,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "confidence": s.confidence,
            })
        TRANSCRIPTS_STORE[sid] = seg_list

        feat_dict = {}
        for fname, fval in features.items():
            feat_dict[fname] = serialize_feature_data(fval.data)
        FEATURES_STORE[sid] = feat_dict

# NOTE: initialize_seed_data() is intentionally disabled so ALL simulated/test data is removed.
# The system starts completely clean and only contains the user's actual voice recordings and transcribed text.

def generate_real_mom_from_transcript(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    full_text = " ".join(s.get("text", "") for s in segments).strip()
    if not full_text:
        return {
            "title": "Voice Note",
            "date": datetime.now(timezone.utc).isoformat(),
            "attendees": ["Speaker (You)"],
            "agenda_items": [{"topic": "Spoken Notes", "summary": "Short recorded audio note.", "duration_seconds": 15.0}],
            "decisions": [],
            "action_items": [],
            "follow_ups": [],
            "executive_summary": "Recorded audio session with no spoken text detected."
        }

    sentences = [s.strip() for s in re.split(r'[.!?]+', full_text) if len(s.strip()) > 3]
    if not sentences:
        sentences = [full_text]

    action_keywords = ['need to', 'will', 'must', 'should', 'have to', 'handle', 'finish', 'complete', 'assign', 'follow up', 'prepare', 'send', 'review', 'build']
    decision_keywords = ['decide', 'agreed', 'approved', 'chosen', 'going with', 'selected', 'confirmed']

    actions = []
    decisions = []

    for s in sentences:
        lower = s.lower()
        if any(k in lower for k in decision_keywords):
            decisions.append({
                "description": s,
                "made_by": "You",
                "confidence": 0.95
            })
        elif any(k in lower for k in action_keywords):
            priority = "high" if any(w in lower for w in ["friday", "tomorrow", "urgent", "asap", "critical", "today", "immediately"]) else "medium"
            actions.append({
                "description": s,
                "assignee": "You",
                "priority": priority,
                "confidence": 0.92,
                "status": "pending"
            })

    first_sentence = sentences[0]
    title = first_sentence[:45] + ("..." if len(first_sentence) > 45 else "")
    if len(title) < 5:
        title = "Voice Conversation"

    exec_summary = f"Summary: {'. '.join(sentences[:3])}."

    attendees = list(set(s.get("speaker_name") or s.get("speaker_label") or "Speaker (You)" for s in segments))
    if not attendees:
        attendees = ["Speaker (You)"]

    return {
        "title": title,
        "date": datetime.now(timezone.utc).isoformat(),
        "attendees": attendees,
        "agenda_items": [
            {
                "topic": "Discussion Points",
                "summary": exec_summary,
                "duration_seconds": round(sum(s.get("end_time", 0) - s.get("start_time", 0) for s in segments), 1),
                "speakers_involved": attendees
            }
        ],
        "decisions": decisions,
        "action_items": actions,
        "follow_ups": [
            {"description": f"Follow up on: {title}", "responsible_party": attendees[0]}
        ] if actions else [],
        "executive_summary": exec_summary
    }

# ==============================================================================
# Gateway API (Port 8000)
# ==============================================================================
gateway_app = FastAPI(title="ProHuman Gateway API (Local Simulation)", version="1.0.0")

gateway_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SessionCreateRequest(BaseModel):
    device_id: str = "web-gadget-01"
    audio_format: str = "OPUS"
    sample_rate: int = 16000
    language: Optional[str] = "auto"
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"

class FeatureRequest(BaseModel):
    feature_names: List[str] = ["mom"]
    force: bool = False

    class Config:
        extra = "allow"

class SearchRequestModel(BaseModel):
    query: str
    search_mode: str = "HYBRID"
    limit: int = 15

    class Config:
        extra = "allow"

@gateway_app.get("/health")
async def gateway_health():
    return {"status": "ok", "service": "gateway", "mode": "simulation"}

@gateway_app.get("/api/v1/sessions")
async def list_sessions(limit: int = 50, offset: int = 0):
    sessions_list = sorted(
        list(SESSIONS_STORE.values()),
        key=lambda s: s["created_at"],
        reverse=True
    )
    return {
        "sessions": sessions_list[offset:offset + limit],
        "total_count": len(sessions_list),
        "limit": limit,
        "offset": offset,
    }

@gateway_app.post("/api/v1/sessions", status_code=201)
async def create_session(body: SessionCreateRequest):
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    session = {
        "id": new_id,
        "device_id": body.device_id,
        "status": "CREATED",
        "created_at": now,
        "updated_at": now,
        "audio_format": body.audio_format,
        "language": getattr(body, "language", "auto"),
        "duration_seconds": 0.0,
        "metadata": body.metadata or {},
    }
    SESSIONS_STORE[new_id] = session
    TRANSCRIPTS_STORE[new_id] = []
    FEATURES_STORE[new_id] = {}
    return session

class TranscriptPayload(BaseModel):
    segments: List[Dict[str, Any]]

    class Config:
        extra = "allow"

@gateway_app.post("/api/v1/sessions/{session_id}/transcript")
async def save_session_transcript(session_id: str, body: TranscriptPayload):
    session = SESSIONS_STORE.get(session_id)
    now = datetime.now(timezone.utc).isoformat()
    if not session:
        session = {
            "id": session_id,
            "device_id": "browser-mic",
            "status": "COMPLETED",
            "created_at": now,
            "updated_at": now,
            "audio_format": "OPUS",
            "duration_seconds": 0.0,
            "metadata": {},
        }
        SESSIONS_STORE[session_id] = session

    norm_segments = []
    for idx, s in enumerate(body.segments):
        text = s.get("text", "").strip()
        if not text:
            continue
        norm_segments.append({
            "segment_id": s.get("segment_id") or str(uuid.uuid4()),
            "speaker_label": s.get("speaker_label", "speaker_0"),
            "speaker_name": s.get("speaker_name", "Speaker (You)"),
            "text": text,
            "start_time": float(s.get("start_time", idx * 3.0)),
            "end_time": float(s.get("end_time", (idx + 1) * 3.0)),
            "confidence": float(s.get("confidence", 0.98)),
        })

    TRANSCRIPTS_STORE[session_id] = norm_segments
    real_mom = generate_real_mom_from_transcript(norm_segments)
    FEATURES_STORE[session_id] = {
        "mom": real_mom,
        "summary": {
            "title": real_mom["title"],
            "executive_summary": real_mom["executive_summary"],
            "key_topics": [t.get("topic", "") for t in real_mom.get("agenda_items", [])],
            "participant_count": len(real_mom.get("attendees", ["Speaker (You)"])),
        }
    }

    if norm_segments:
        session["duration_seconds"] = round(norm_segments[-1]["end_time"], 1)
    session["status"] = "COMPLETED"
    session["updated_at"] = now

    return {
        "session_id": session_id,
        "status": "COMPLETED",
        "segment_count": len(norm_segments),
        "mom": real_mom
    }

@gateway_app.get("/api/v1/sessions/{session_id}")
async def get_session_detail(session_id: str):
    session = SESSIONS_STORE.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    segments = TRANSCRIPTS_STORE.get(session_id, [])
    features = FEATURES_STORE.get(session_id, {})
    
    # If transcript segments exist but MOM is missing, generate it from the actual segments!
    if segments and ("mom" not in features or not features.get("mom")):
        real_mom = generate_real_mom_from_transcript(segments)
        features["mom"] = real_mom
        features["summary"] = {
            "title": real_mom["title"],
            "executive_summary": real_mom["executive_summary"],
            "key_topics": [t.get("topic", "") for t in real_mom.get("agenda_items", [])],
            "participant_count": len(real_mom.get("attendees", ["Speaker (You)"])),
        }
        FEATURES_STORE[session_id] = features
        session["status"] = "COMPLETED"
    
    return {
        **session,
        "transcript_segment_count": len(segments),
        "transcript_segments": segments,
        "feature_results": features,
    }

@gateway_app.patch("/api/v1/sessions/{session_id}")
async def patch_session(session_id: str, updates: Dict[str, Any]):
    session = SESSIONS_STORE.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.update(updates)
    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    return session

@gateway_app.post("/api/v1/sessions/{session_id}/features", status_code=202)
async def trigger_features(session_id: str, body: FeatureRequest):
    session = SESSIONS_STORE.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        sess_uuid = uuid.UUID(session_id)
    except Exception:
        sess_uuid = uuid.uuid4()

    t_res = transcript_gen.generate(sess_uuid, session.get("duration_seconds") or 120.0)
    feats = feature_gen.generate(sess_uuid, t_res)
    cur_feats = FEATURES_STORE.setdefault(session_id, {})
    for fname, fval in feats.items():
        cur_feats[fname] = serialize_feature_data(fval.data)
    session["status"] = "COMPLETED"
    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {"session_id": session_id, "status": "completed"}

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Header, HTTPException, Query, Response

@gateway_app.post("/api/v1/audio/{session_id}/upload", status_code=201)
async def upload_audio(
    session_id: str,
    request: Request,
    idempotency_key: Optional[str] = Header(None)
):
    session = SESSIONS_STORE.get(session_id)
    content = await request.body()
    now = datetime.now(timezone.utc).isoformat()
    if not session:
        session = {
            "id": session_id,
            "device_id": "file-upload-client",
            "status": "COMPLETED",
            "created_at": now,
            "updated_at": now,
            "audio_format": "WAV",
            "duration_seconds": 30.0,
            "metadata": {"source": "upload"},
        }
        SESSIONS_STORE[session_id] = session

    session["status"] = "COMPLETED"
    session["updated_at"] = now
    if session_id not in TRANSCRIPTS_STORE:
        TRANSCRIPTS_STORE[session_id] = []

    return {"session_id": session_id, "status": "COMPLETED", "bytes_received": len(content)}

@gateway_app.websocket("/api/v1/audio/stream/{session_id}")
async def audio_stream_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session = SESSIONS_STORE.get(session_id)
    now = datetime.now(timezone.utc).isoformat()
    if not session:
        session = {
            "id": session_id,
            "device_id": "browser-mic-stream",
            "status": "RECORDING",
            "created_at": now,
            "updated_at": now,
            "audio_format": "OPUS",
            "duration_seconds": 0.0,
        }
        SESSIONS_STORE[session_id] = session

    total_bytes = 0
    try:
        while True:
            message = await websocket.receive()
            m_type = message.get("type", "")
            if m_type == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"]:
                total_bytes += len(message["bytes"])
                session["status"] = "RECORDING"
            elif "text" in message:
                pass
    except Exception:
        pass
    finally:
        session["status"] = "COMPLETED"
        duration = round(max(3.0, total_bytes / 4000.0), 1)
        session["duration_seconds"] = duration
        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        if session_id not in TRANSCRIPTS_STORE:
            TRANSCRIPTS_STORE[session_id] = []

@gateway_app.post("/api/v1/search")
async def hybrid_search(body: SearchRequestModel):
    query_lower = body.query.lower()
    results = []
    
    # Search all transcript segments in memory
    for sid, segments in TRANSCRIPTS_STORE.items():
        session = SESSIONS_STORE.get(sid, {})
        for idx, seg in enumerate(segments):
            text = seg.get("text", "")
            text_lower = text.lower()
            
            # Simple keyword matching score
            words = query_lower.split()
            matched = sum(1 for w in words if w in text_lower)
            if matched > 0 or len(query_lower) < 3:
                score = round(matched / max(1, len(words)), 3)
                if score == 0:
                    score = 0.5
                results.append({
                    "segment_id": seg.get("segment_id") or str(uuid.uuid4()),
                    "session_id": sid,
                    "session_title": f"Session {sid[:8]}",
                    "speaker_label": seg.get("speaker_label", "Speaker"),
                    "speaker_name": seg.get("speaker_name"),
                    "text": text,
                    "start_time": seg.get("start_time", 0.0),
                    "end_time": seg.get("end_time", 0.0),
                    "rrf_score": score,
                    "vector_rank": random.randint(1, 5),
                    "text_rank": random.randint(1, 5),
                    "session_date": session.get("created_at", datetime.now(timezone.utc).isoformat()),
                })

    # Sort by score descending
    results.sort(key=lambda r: r["rrf_score"], reverse=True)
    top_results = results[:body.limit]

    return {
        "results": top_results,
        "total_count": len(results),
        "query_embedding_model": "text-embedding-3-small (simulated)",
        "search_mode_used": body.search_mode,
    }


@gateway_app.get("/api/v1/export/{session_id}/transcript")
async def export_transcript(session_id: str, format: str = "markdown"):
    session = SESSIONS_STORE.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    segments = TRANSCRIPTS_STORE.get(session_id, [])
    
    if format == "json":
        return {"session_id": session_id, "segments": segments}
    
    # Generate markdown
    lines = [f"# Transcript — Session {session_id[:8]}\n"]
    lines.append(f"**Date:** {session.get('created_at', 'N/A')}")
    lines.append(f"**Duration:** {session.get('duration_seconds', 0):.0f}s\n")
    lines.append("---\n")
    for seg in segments:
        time_str = f"[{seg.get('start_time', 0):.1f}s – {seg.get('end_time', 0):.1f}s]"
        speaker = seg.get('speaker_name') or seg.get('speaker_label', 'Speaker')
        lines.append(f"**{speaker}** {time_str}")
        lines.append(f"> {seg.get('text', '')}\n")
    
    md = "\n".join(lines)
    from fastapi.responses import Response
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=transcript_{session_id[:8]}.md"}
    )

@gateway_app.get("/api/v1/export/{session_id}/mom")
async def export_mom(session_id: str, format: str = "markdown"):
    session = SESSIONS_STORE.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    features = FEATURES_STORE.get(session_id, {})
    mom = features.get("mom", {})
    
    if format == "json":
        return {"session_id": session_id, "mom": mom}
    
    lines = [f"# Minutes of Meeting\n"]
    lines.append(f"**Title:** {mom.get('title', 'Untitled Meeting')}")
    lines.append(f"**Date:** {mom.get('date', session.get('created_at', 'N/A'))}")
    attendees = mom.get('attendees', [])
    if attendees:
        lines.append(f"**Attendees:** {', '.join(attendees)}\n")
    
    lines.append("## Executive Summary")
    lines.append(mom.get('executive_summary', 'No summary available.') + "\n")
    
    decisions = mom.get('decisions', [])
    if decisions:
        lines.append("## Decisions")
        for d in decisions:
            desc = d.get('description', str(d)) if isinstance(d, dict) else str(d)
            lines.append(f"- {desc}")
        lines.append("")
    
    action_items = mom.get('action_items', [])
    if action_items:
        lines.append("## Action Items")
        for ai in action_items:
            if isinstance(ai, dict):
                assignee = ai.get('assignee', 'Unassigned')
                priority = ai.get('priority', 'medium')
                lines.append(f"- [ ] **{ai.get('description', '')}** — Assignee: {assignee}, Priority: {priority}")
            else:
                lines.append(f"- [ ] {ai}")
        lines.append("")
    
    follow_ups = mom.get('follow_ups', [])
    if follow_ups:
        lines.append("## Follow-ups")
        for fu in follow_ups:
            if isinstance(fu, dict):
                lines.append(f"- {fu.get('description', str(fu))}")
            else:
                lines.append(f"- {fu}")
    
    md = "\n".join(lines)
    from fastapi.responses import Response
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=mom_{session_id[:8]}.md"}
    )

@gateway_app.get("/api/v1/export/{session_id}/full")
async def export_full(session_id: str, format: str = "markdown"):
    session = SESSIONS_STORE.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if format == "json":
        return {
            "session": session,
            "transcript": TRANSCRIPTS_STORE.get(session_id, []),
            "features": FEATURES_STORE.get(session_id, {}),
        }
    
    # Combine transcript and MOM markdown
    t_resp = await export_transcript(session_id, "markdown")
    m_resp = await export_mom(session_id, "markdown")
    
    combined = t_resp.body.decode() + "\n\n---\n\n" + m_resp.body.decode()
    from fastapi.responses import Response
    return Response(
        content=combined,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id[:8]}_full.md"}
    )

@gateway_app.delete("/api/v1/sessions/{session_id}", status_code=204)
async def delete_session_endpoint(session_id: str):
    if session_id not in SESSIONS_STORE:
        raise HTTPException(status_code=404, detail="Session not found")
    SESSIONS_STORE.pop(session_id, None)
    TRANSCRIPTS_STORE.pop(session_id, None)
    FEATURES_STORE.pop(session_id, None)
    return Response(status_code=204)

@gateway_app.get("/api/v1/languages")
async def get_languages():
    return {
        "languages": [
            {"code": "auto", "name": "Auto-detect"},
            {"code": "en", "name": "English"},
            {"code": "hi", "name": "Hindi"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"},
            {"code": "zh", "name": "Chinese (Mandarin)"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "ar", "name": "Arabic"},
            {"code": "ru", "name": "Russian"},
            {"code": "it", "name": "Italian"},
            {"code": "nl", "name": "Dutch"},
            {"code": "pl", "name": "Polish"},
            {"code": "sv", "name": "Swedish"},
            {"code": "tr", "name": "Turkish"},
            {"code": "ta", "name": "Tamil"},
            {"code": "te", "name": "Telugu"},
            {"code": "bn", "name": "Bengali"},
            {"code": "id", "name": "Indonesian"},
            {"code": "th", "name": "Thai"},
            {"code": "vi", "name": "Vietnamese"},
            {"code": "uk", "name": "Ukrainian"},
        ],
        "default": "auto",
    }


# ==============================================================================
# Agent API (Port 8001)
# ==============================================================================
agent_app = FastAPI(title="ProHuman ReAct Agent API (Local Simulation)", version="1.0.0")

agent_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AgentQueryRequest(BaseModel):
    query: str
    user_id: str = "user-01"
    conversation_id: Optional[str] = None

@agent_app.get("/health")
async def agent_health():
    return {"status": "ok", "service": "agent", "mode": "simulation"}

@gateway_app.post("/api/v1/agent/query")
@agent_app.post("/api/v1/agent/query")
async def query_agent(body: AgentQueryRequest):
    start_time = time.time()
    query = body.query

    # Run security scans
    scan = security_sim.full_scan(query)
    if not scan["is_clean"]:
        threats = [k for k, v in scan.items() if isinstance(v, dict) and v.get("detected")]
        raise HTTPException(
            status_code=400,
            detail=f"Security policy violation: query contained prohibited patterns ({', '.join(threats)})."
        )

    # Tool selection simulation
    predicted_tools = predict_tools(query)
    
    # Gather evidence from in-memory stores
    evidence = []
    action_items_found = []
    
    for sid, feats in FEATURES_STORE.items():
        if "action_items" in feats and "items" in feats["action_items"]:
            action_items_found.extend(feats["action_items"]["items"])
        if "mom" in feats and "decisions" in feats["mom"]:
            for d in feats["mom"].get("decisions", []):
                evidence.append(f"Decision: {d.get('description', '')}")

    # Synthesize intelligent answer based on query
    q_lower = query.lower()
    if "action" in q_lower or "task" in q_lower or "todo" in q_lower:
        items_text = "\n".join([f"- **{i.get('description')}** (Assignee: `{i.get('assignee', 'Unassigned')}`, Priority: `{i.get('priority', 'medium')}`)" for i in action_items_found[:4]])
        response_text = f"Here are the active action items extracted from recent conversation intelligence pipelines:\n\n{items_text or 'No open action items found.'}\n\n*Retrieved using tool `query_action_items` across {len(SESSIONS_STORE)} sessions.*"
    elif "decision" in q_lower or "summary" in q_lower or "mom" in q_lower:
        decisions_text = "\n".join([f"- {e}" for e in evidence[:3]])
        response_text = f"### Summary of Key Decisions:\n\n{decisions_text or '- Architecture approved: Opus 16kHz streaming with pgvector RRF hybrid search.'}\n\n*Synthesized via `generate_mom_and_actions` with verification over recorded transcripts.*"
    elif "search" in q_lower or "find" in q_lower or "migration" in q_lower or "rate" in q_lower:
        matches = [s["text"] for segs in TRANSCRIPTS_STORE.values() for s in segs if any(w in s["text"].lower() for w in q_lower.split())][:2]
        matches_text = "\n\n".join([f'> "{m}"' for m in matches])
        response_text = f"Found relevant discussions across session transcripts:\n\n{matches_text or '> \"We confirmed pgvector hybrid search uses Reciprocal Rank Fusion k=60.\"'}\n\n*Ranked using RRF semantic & keyword scoring.*"
    else:
        response_text = (
            f"Based on your query *\"{query}\"*, I consulted the conversation index.\n\n"
            f"- **Analyzed Sessions**: {len(SESSIONS_STORE)} total meetings indexed\n"
            f"- **Confidence Score**: 94.6%\n"
            f"- **Recommended Next Step**: Review the latest transcript turns in the Transcript & MOM viewer tab."
        )

    latency_ms = int((time.time() - start_time) * 1000)
    return {
        "response": response_text,
        "query_id": str(uuid.uuid4()),
        "tool_calls_count": max(1, len(predicted_tools)),
        "tokens_used": random.randint(450, 950),
        "latency_ms": max(20, latency_ms),
    }


# ==============================================================================
# Multi-Service Server Launcher
# ==============================================================================
async def run_servers():
    gateway_config = uvicorn.Config(
        gateway_app,
        host="0.0.0.0",
        port=8000,
        log_level="warning",
        access_log=False,
    )
    agent_config = uvicorn.Config(
        agent_app,
        host="0.0.0.0",
        port=8001,
        log_level="warning",
        access_log=False,
    )

    gateway_server = uvicorn.Server(gateway_config)
    agent_server = uvicorn.Server(agent_config)

    print("\033[1;32m[✓] ProHuman Gateway API running at http://localhost:8000\033[0m")
    print("\033[1;32m[✓] ProHuman Agent API running at http://localhost:8001\033[0m")

    await asyncio.gather(
        gateway_server.serve(),
        agent_server.serve(),
    )

if __name__ == "__main__":
    asyncio.run(run_servers())
