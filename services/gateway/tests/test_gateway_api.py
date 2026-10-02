"""Unit and integration tests for the Gateway Service."""
from __future__ import annotations

import pytest
from app.config import Settings, get_settings
from app.main import create_app
from packages.contracts.sessions import SessionCreate
from packages.contracts.search import SearchRequest, SearchMode


class TestGatewayConfiguration:
    def test_default_settings(self):
        settings = get_settings()
        assert settings.database_url is not None
        assert "prohuman" in settings.database_url
        assert settings.s3_bucket_name == "audio-recordings"
        assert settings.rate_limit_requests_per_minute > 0
        assert settings.cors_origins is not None

    def test_custom_cors_origins(self):
        settings = Settings(cors_origins=["http://localhost:3000"])
        assert "http://localhost:3000" in settings.cors_origins


class TestGatewayAppFactory:
    def test_create_app_instance(self):
        app = create_app()
        assert app.title == "Gateway Service"
        assert app.version == "0.1.0"

        # Verify routes are registered
        routes = [route.path for route in app.routes]
        assert "/health" in routes
        assert any("/api/v1" in r for r in routes)


class TestGatewayContractsValidation:
    def test_session_create_validation(self):
        req = SessionCreate(
            device_id="hardware-gadget-01",
            language="hi",
            metadata={"source": "pytest"},
        )
        assert req.device_id == "hardware-gadget-01"
        assert req.language == "hi"

    def test_search_request_validation(self):
        req = SearchRequest(
            query="action items from yesterday",
            search_mode=SearchMode.SEMANTIC,
            limit=5,
        )
        assert req.query == "action items from yesterday"
        assert req.search_mode == SearchMode.SEMANTIC
        assert req.limit == 5
