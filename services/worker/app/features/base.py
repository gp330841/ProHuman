"""Base feature provider module."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from packages.contracts.features import FeatureResult

class BaseFeatureProvider(ABC):
    """Base abstract class for feature extraction providers."""
    name: str
    version: str = '1.0'
    required_context: list[str] = ['transcript']
    
    @abstractmethod
    async def process(self, session_id: str, transcript_data: dict[str, Any]) -> FeatureResult:
        """Process a session transcript to extract a feature."""
        pass
    
    def validate_context(self, context: dict[str, Any]) -> bool:
        """Validate that the required context exists."""
        return all(key in context for key in self.required_context)
