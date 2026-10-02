"""Module for tracing.py."""
import functools
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def configure_tracing(service_name: str, otlp_endpoint: str):
    """Method documentation."""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "0.1.0",
        "deployment.environment": "production"
    })
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    # FastAPI and SQLAlchemy must be instrumented explicitly with their apps/engines

def traced_tool(func):
    """Method documentation."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        """Method documentation."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(func.__name__):
            return await func(*args, **kwargs)
    return wrapper
