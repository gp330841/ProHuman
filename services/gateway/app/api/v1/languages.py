from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

SUPPORTED_LANGUAGES = [
    {"code": "auto", "name": "Auto-detect"},
    {"code": "en", "name": "English"},
    {"code": "hi", "name": "Hindi"},
    {"code": "es", "name": "Spanish"},
    {"code": "fr", "name": "French"},
    {"code": "de", "name": "German"},
    {"code": "ja", "name": "Japanese"},
    {"code": "ko", "name": "Korean"},
    {"code": "zh", "name": "Chinese"},
    {"code": "pt", "name": "Portuguese"},
    {"code": "ar", "name": "Arabic"},
    {"code": "ru", "name": "Russian"},
    {"code": "it", "name": "Italian"},
    {"code": "nl", "name": "Dutch"},
    {"code": "pl", "name": "Polish"},
    {"code": "sv", "name": "Swedish"},
    {"code": "tr", "name": "Turkish"},
    {"code": "id", "name": "Indonesian"},
    {"code": "da", "name": "Danish"},
    {"code": "el", "name": "Greek"},
    {"code": "th", "name": "Thai"}
]

@router.get("")
async def get_languages():
    return {
        "languages": SUPPORTED_LANGUAGES,
        "default": "auto"
    }
