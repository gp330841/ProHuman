from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

class ErrorResponse(BaseModel):
    """Structured error response."""
    error_id: str
    message: str
    details: Any | None = None

def setup_error_handlers(app: FastAPI) -> None:
    """Setup global exception handlers."""
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        error_id = str(uuid.uuid4())
        await logger.awarning("validation_error", error_id=error_id, errors=exc.errors())
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error_id=error_id,
                message="Validation Error",
                details=exc.errors()
            ).model_dump()
        )
        
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
        
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        error_id = str(uuid.uuid4())
        await logger.aerror("unhandled_error", error_id=error_id, error=str(exc))
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_id=error_id,
                message="Internal Server Error"
            ).model_dump()
        )

__all__ = ["ErrorResponse", "setup_error_handlers"]
