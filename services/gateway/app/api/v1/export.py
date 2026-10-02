from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, JSONResponse
from app.dependencies import get_session_repo
from packages.db.repositories.session_repo import SessionRepository

router = APIRouter()

def format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

@router.get("/{session_id}/transcript")
async def export_transcript(
    session_id: UUID,
    format: str = Query("json", description="Export format: json or markdown"),
    session_repo: SessionRepository = Depends(get_session_repo)
):
    session = await session_repo.get_with_details(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if format.lower() == "json":
        data = [
            {
                "speaker": seg.speaker_label,
                "text": seg.text,
                "start": seg.start_time,
                "end": seg.end_time
            }
            for seg in session.transcript_segments
        ]
        return JSONResponse(content=data)
    elif format.lower() == "markdown":
        md_lines = [f"# Transcript for Session {session_id}\n"]
        for seg in session.transcript_segments:
            start_fmt = format_time(seg.start_time)
            md_lines.append(f"**[{start_fmt}] {seg.speaker_label}:** {seg.text}")
        
        md_content = "\n\n".join(md_lines)
        return Response(
            content=md_content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="transcript_{session_id}.md"'}
        )
    
    raise HTTPException(status_code=400, detail="Invalid format")

@router.get("/{session_id}/mom")
async def export_mom(
    session_id: UUID,
    format: str = Query("json", description="Export format: json or markdown"),
    session_repo: SessionRepository = Depends(get_session_repo)
):
    session = await session_repo.get_with_details(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    mom_data = None
    for feat in session.feature_results:
        if feat.feature_name.lower() == "mom":
            mom_data = feat.data
            break
            
    if not mom_data:
        raise HTTPException(status_code=404, detail="MOM not found for this session")

    if format.lower() == "json":
        return JSONResponse(content=mom_data)
    elif format.lower() == "markdown":
        md_lines = [f"# Minutes of Meeting: Session {session_id}\n"]
        
        if isinstance(mom_data, dict):
            if "executive_summary" in mom_data:
                md_lines.append("## Executive Summary")
                md_lines.append(str(mom_data["executive_summary"]))
                
            if "attendees" in mom_data:
                md_lines.append("## Attendees")
                for att in mom_data["attendees"]:
                    md_lines.append(f"- {att}")
                    
            if "agenda_items" in mom_data:
                md_lines.append("## Agenda Items")
                for item in mom_data["agenda_items"]:
                    md_lines.append(f"- {item}")
                    
            if "decisions" in mom_data:
                md_lines.append("## Decisions")
                for d in mom_data["decisions"]:
                    md_lines.append(f"- {d}")
                    
            if "action_items" in mom_data:
                md_lines.append("## Action Items")
                for ai in mom_data["action_items"]:
                    if isinstance(ai, dict):
                        assignee = ai.get('assignee', 'Unassigned')
                        priority = ai.get('priority', 'Normal')
                        task = ai.get('task', str(ai))
                        md_lines.append(f"- [ ] **{assignee}** ({priority}): {task}")
                    else:
                        md_lines.append(f"- [ ] {ai}")
                    
            if "follow_ups" in mom_data:
                md_lines.append("## Follow-ups")
                for fu in mom_data["follow_ups"]:
                    md_lines.append(f"- {fu}")
                    
        md_content = "\n\n".join(md_lines)
        return Response(
            content=md_content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="mom_{session_id}.md"'}
        )
    
    raise HTTPException(status_code=400, detail="Invalid format")

@router.get("/{session_id}/full")
async def export_full(
    session_id: UUID,
    format: str = Query("markdown", description="Export format"),
    session_repo: SessionRepository = Depends(get_session_repo)
):
    if format.lower() != "markdown":
        raise HTTPException(status_code=400, detail="Only markdown format is supported for full export")
        
    session = await session_repo.get_with_details(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    md_lines = [f"# Full Export for Session {session_id}\n"]
    
    mom_data = None
    for feat in session.feature_results:
        if feat.feature_name.lower() == "mom":
            mom_data = feat.data
            break
            
    if mom_data and isinstance(mom_data, dict):
        md_lines.append("## Minutes of Meeting\n")
        if "executive_summary" in mom_data:
            md_lines.append("### Executive Summary")
            md_lines.append(str(mom_data["executive_summary"]))
        if "action_items" in mom_data:
            md_lines.append("### Action Items")
            for ai in mom_data["action_items"]:
                if isinstance(ai, dict):
                    assignee = ai.get('assignee', 'Unassigned')
                    priority = ai.get('priority', 'Normal')
                    task = ai.get('task', str(ai))
                    md_lines.append(f"- [ ] **{assignee}** ({priority}): {task}")
                else:
                    md_lines.append(f"- [ ] {ai}")
    
    md_lines.append("\n## Transcript\n")
    for seg in session.transcript_segments:
        start_fmt = format_time(seg.start_time)
        md_lines.append(f"**[{start_fmt}] {seg.speaker_label}:** {seg.text}")
        
    md_content = "\n\n".join(md_lines)
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="full_session_{session_id}.md"'}
    )
