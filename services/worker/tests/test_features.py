"""Unit tests for Worker Service features and pipeline."""
from __future__ import annotations

import pytest
from app.config import WorkerSettings, get_settings
from app.features.base import BaseFeatureProvider
from app.features.registry import FeatureRegistry
from packages.contracts.features import FeatureResult


class DummyFeatureProvider(BaseFeatureProvider):
    name = "dummy_test_feature"
    version = "1.0"
    required_context = ["transcript"]

    async def process(self, session_id: str, transcript_data: dict) -> FeatureResult:
        return FeatureResult(name=self.name, version=self.version, data={"status": "ok"})


class TestWorkerConfiguration:
    def test_worker_settings_defaults(self):
        settings = get_settings()
        assert "prohuman" in settings.database_url
        assert settings.s3_bucket_name == "audio-recordings"
        assert settings.embedding_dimensions == 1536
        assert settings.default_llm_model == "gpt-4o"
        assert settings.stt_primary_adapter == "deepgram"


class TestFeatureRegistry:
    def test_register_and_retrieve_feature(self):
        FeatureRegistry.register("dummy_feature", DummyFeatureProvider)
        provider_cls = FeatureRegistry.get("dummy_feature")
        assert provider_cls is DummyFeatureProvider

        all_providers = FeatureRegistry.get_all()
        assert "dummy_feature" in all_providers

    def test_base_feature_context_validation(self):
        provider = DummyFeatureProvider()
        assert provider.validate_context({"transcript": []}) is True
        assert provider.validate_context({"wrong_key": []}) is False
