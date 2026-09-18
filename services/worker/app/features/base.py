from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from packages.contracts.features import FeatureResult

class BaseFeatureProvider(ABC):
    name: str
    version: str = '1.0'
    required_context: list[str] = ['transcript']
    
    @abstractmethod
    async def process(self, session_id: str, transcript_data: dict[str, Any]) -> FeatureResult:
        pass
    
    def validate_context(self, context: dict[str, Any]) -> bool:
        return all(key in context for key in self.required_context)
