from contextlib import asynccontextmanager
from fastapi import FastAPI
from .api.v1.agent import router as agent_router
from .observability.tracing import configure_tracing
from .config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tracing("agent-service", settings.otlp_endpoint)
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(agent_router, prefix="/api/v1/agent", tags=["agent"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}
