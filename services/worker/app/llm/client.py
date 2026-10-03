"""LLM client module."""
from __future__ import annotations

import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Any, TypeVar, Type
import httpx

import litellm
import instructor
from pydantic import BaseModel
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

class LLMClient:
    """Client for generating text and structured data via Google Gemini and LiteLLM/OpenAI."""
    def __init__(self, default_model: str = "gemini-3.8-flash"):
        """Initialize the LLM client."""
        self.default_model = default_model
        self.gemini_api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")

        # Configure litellm api keys
        if self.openai_api_key:
            litellm.openai_key = self.openai_api_key
        if self.gemini_api_key:
            litellm.gemini_key = self.gemini_api_key

        try:
            self.instructor_client = instructor.from_litellm(litellm.acompletion)
        except Exception:
            self.instructor_client = None

    async def generate_structured(
        self, 
        messages: list[dict[str, Any]], 
        response_model: Type[T], 
        model: str | None = None, 
        max_retries: int = 3, 
        temperature: float = 0.2
    ) -> T:
        """Generate structured data using Gemini API (1500 daily free requests) or instructor/litellm."""
        # 1. Primary: Google Gemini API
        if self.gemini_api_key:
            gemini_models = [
                "gemini-3.8-flash",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
            ]
            for gemini_model in gemini_models:
                try:
                    result = await self._call_gemini_structured(gemini_model, messages, response_model)
                    if result:
                        logger.info("gemini_structured_success", model=gemini_model, schema=response_model.__name__)
                        return result
                except Exception as e:
                    logger.warning("gemini_structured_attempt_failed", model=gemini_model, error=str(e))

        # 2. Fallback: instructor with litellm (OpenAI, Anthropic)
        target_model = model or self.default_model
        if self.instructor_client and self.openai_api_key:
            try:
                response = await self.instructor_client.chat.completions.create(
                    model=target_model,
                    messages=messages,
                    response_model=response_model,
                    max_retries=max_retries,
                    temperature=temperature
                )
                return response
            except Exception as e:
                logger.warning("instructor_structured_failed", error=str(e))

        raise RuntimeError("No configured LLM provider succeeded in generating structured response. Please check GEMINI_API_KEY in .env.")

    async def _call_gemini_structured(
        self,
        model: str,
        messages: list[dict[str, Any]],
        response_model: Type[T]
    ) -> T:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_api_key}"
        
        system_text = ""
        user_text = ""
        for m in messages:
            if m.get("role") == "system":
                system_text += m.get("content", "") + "\n\n"
            else:
                user_text += m.get("content", "") + "\n"

        if response_model.__name__ == "MOMResult":
            schema_repr = (
                '{\n'
                '  "title": "Smart descriptive title in English or Hindi+English (never copy the first word like Hailo)",\n'
                '  "executive_summary": "Detailed summary explaining what was discussed, conclusions, and next steps in English or natural Hindi+English",\n'
                '  "attendees": ["Speaker 1"],\n'
                '  "agenda_items": [{"topic": "Topic Name", "summary": "Discussion summary", "duration_seconds": 60, "speakers_involved": ["Speaker 1"]}],\n'
                '  "decisions": [{"description": "What was agreed or decided", "made_by": "Speaker 1"}],\n'
                '  "action_items": [{"description": "Action task", "assignee": "Speaker 1", "priority": "medium", "status": "pending"}],\n'
                '  "follow_ups": [{"description": "Next steps", "responsible_party": "Speaker 1"}]\n'
                '}'
            )
        elif response_model.__name__ == "SummaryResult":
            schema_repr = (
                '{\n'
                '  "title": "Smart descriptive title",\n'
                '  "executive_summary": "Executive summary in English or natural Hindi+English",\n'
                '  "key_topics": ["Topic 1", "Topic 2"],\n'
                '  "participant_count": 1\n'
                '}'
            )
        elif response_model.__name__ == "ActionItemsResult":
            schema_repr = (
                '{\n'
                '  "items": [{"description": "Action item description", "assignee": "Team", "priority": "medium", "status": "pending"}]\n'
                '}'
            )
        else:
            schema_repr = json.dumps(response_model.model_json_schema(), indent=2)

        prompt = (
            f"{system_text}\n"
            f"Transcript Content:\n{user_text}\n\n"
            "CRITICAL FORMAT REQUIREMENT: You MUST output a strictly valid JSON object matching this structure:\n"
            f"{schema_repr}\n\n"
            "INSTRUCTIONS:\n"
            "1. Output MUST be valid JSON only. Do NOT output markdown ticks or conversational preambles.\n"
            "2. Understand the discussion deeply. Generate a smart, professional executive title. CRITICAL: If any speaker explicitly suggests, dictates, or asks to keep a specific title (e.g. 'iska title rakhna...', 'title suggest kar raha hoon ki...', 'title should be...'), adopt that exact suggested title!\n"
            "3. Generate an insightful Executive Summary in clean English or natural Hindi+English (as spoken in meeting, keeping all technical terms in standard English).\n"
            "4. Extract genuine decisions and action items with assignees.\n"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            }
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        text_content = data["candidates"][0]["content"]["parts"][0]["text"]
        cleaned = text_content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed_json = json.loads(cleaned.strip())
        return self._normalize_and_validate(parsed_json, response_model)

    def _normalize_and_validate(self, parsed_json: dict, response_model: Type[T]) -> T:
        # Normalize schema fields
        if response_model.__name__ == "MOMResult":
            parsed_json["title"] = parsed_json.get("title") or parsed_json.get("meeting_title") or parsed_json.get("topic") or "Meeting Summary"
            parsed_json["executive_summary"] = parsed_json.get("executive_summary") or parsed_json.get("summary") or parsed_json.get("overview") or "Meeting discussion review."
            parsed_json.setdefault("date", datetime.now(timezone.utc).isoformat())
            parsed_json.setdefault("attendees", ["Speaker", "Participant"])
            parsed_json.setdefault("agenda_items", [])
            parsed_json.setdefault("decisions", [])
            parsed_json.setdefault("action_items", [])
            parsed_json.setdefault("follow_ups", [])

            if isinstance(parsed_json.get("decisions"), list):
                norm_dec = []
                for d in parsed_json["decisions"]:
                    if isinstance(d, str):
                        norm_dec.append({"description": d})
                    elif isinstance(d, dict):
                        norm_dec.append({"description": d.get("description") or d.get("decision") or str(d)})
                parsed_json["decisions"] = norm_dec

            if isinstance(parsed_json.get("action_items"), list):
                norm_act = []
                for a in parsed_json["action_items"]:
                    if isinstance(a, str):
                        norm_act.append({"description": a, "assignee": "Team", "priority": "medium", "status": "pending"})
                    elif isinstance(a, dict):
                        desc = a.get("description") or a.get("task") or a.get("action") or str(a)
                        p = str(a.get("priority", "medium")).lower()
                        norm_act.append({
                            "description": desc,
                            "assignee": a.get("assignee") or "Team",
                            "priority": p if p in ["critical", "high", "medium", "low"] else "medium",
                            "status": "pending",
                        })
                parsed_json["action_items"] = norm_act

            if isinstance(parsed_json.get("agenda_items"), list):
                norm_ag = []
                for ag in parsed_json["agenda_items"]:
                    if isinstance(ag, str):
                        norm_ag.append({"topic": ag, "summary": ag, "speakers_involved": []})
                    elif isinstance(ag, dict):
                        norm_ag.append({
                            "topic": ag.get("topic") or ag.get("title") or "Discussion",
                            "summary": ag.get("summary") or ag.get("topic") or "Review",
                            "speakers_involved": ag.get("speakers_involved") or [],
                        })
                parsed_json["agenda_items"] = norm_ag

            if isinstance(parsed_json.get("follow_ups"), list):
                norm_fu = []
                for fu in parsed_json["follow_ups"]:
                    if isinstance(fu, str):
                        norm_fu.append({"description": fu, "responsible_party": "Team"})
                    elif isinstance(fu, dict):
                        norm_fu.append({
                            "description": fu.get("description") or fu.get("task") or str(fu),
                            "responsible_party": fu.get("responsible_party") or "Team",
                        })
                parsed_json["follow_ups"] = norm_fu

        elif response_model.__name__ == "SummaryResult":
            parsed_json["title"] = parsed_json.get("title") or parsed_json.get("meeting_title") or parsed_json.get("topic") or "Meeting Summary"
            parsed_json["executive_summary"] = parsed_json.get("executive_summary") or parsed_json.get("summary") or parsed_json.get("overview") or "Discussion summary."
            parsed_json.setdefault("key_topics", ["Charcha & Review", "Action Points"])
            parsed_json.setdefault("participant_count", 2)

        elif response_model.__name__ == "ActionItemsResult":
            items_raw = parsed_json.get("items") or parsed_json.get("action_items") or []
            if isinstance(parsed_json, list):
                items_raw = parsed_json
            norm_items = []
            for it in items_raw:
                if isinstance(it, str):
                    norm_items.append({"description": it, "priority": "medium", "status": "pending"})
                elif isinstance(it, dict):
                    desc = it.get("description") or it.get("task") or str(it)
                    norm_items.append({
                        "description": desc,
                        "assignee": it.get("assignee") or "Team",
                        "priority": "medium",
                        "status": "pending",
                    })
            parsed_json = {"items": norm_items}

        return response_model.model_validate(parsed_json)

    async def generate_text(
        self, 
        messages: list[dict[str, Any]], 
        model: str | None = None, 
        max_tokens: int = 4096
    ) -> str:
        """Generate unstructured text via Google Gemini or LiteLLM."""
        if self.gemini_api_key:
            gemini_models = [
                "gemini-3.8-flash",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
            ]
            for m in gemini_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.gemini_api_key}"
                    combined = "\n\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in messages])
                    payload = {"contents": [{"parts": [{"text": combined}]}]}
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(url, json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            candidates = data.get("candidates", [])
                            if candidates and "content" in candidates[0]:
                                parts = candidates[0]["content"].get("parts", [])
                                if parts and "text" in parts[0]:
                                    return parts[0]["text"]
                except Exception as e:
                    logger.warning("gemini_generate_text_failed", model=m, error=str(e))

        target_model = model or self.default_model
        response = await litellm.acompletion(
            model=target_model,
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    async def generate_embeddings(
        self, 
        texts: list[str], 
        model: str | None = None
    ) -> list[list[float]]:
        """Generate embeddings for text."""
        target_model = model or settings.embedding_model
        all_embeddings = []
        batch_size = 32
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = await litellm.aembedding(
                    model=target_model,
                    input=batch
                )
                batch_embeddings = [data["embedding"] for data in response["data"]]
                all_embeddings.extend(batch_embeddings)
            except Exception:
                # Zero-vector fallback if embedding API is unconfigured
                all_embeddings.extend([[0.0] * 1536 for _ in batch])
            
        return all_embeddings
