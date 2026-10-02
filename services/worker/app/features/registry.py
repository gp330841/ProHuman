"""Feature registry module."""
from __future__ import annotations

import importlib
import pkgutil
from typing import Type

from app.features.base import BaseFeatureProvider

class FeatureRegistry:
    """Registry for managing and discovering feature providers."""
    _providers: dict[str, Type[BaseFeatureProvider]] = {}

    @classmethod
    def register(cls, provider_class: Type[BaseFeatureProvider]) -> Type[BaseFeatureProvider]:
        """Register a feature provider class."""
        cls._providers[provider_class.name] = provider_class
        return provider_class

    @classmethod
    def get(cls, name: str) -> Type[BaseFeatureProvider]:
        """Get a feature provider by name."""
        if name not in cls._providers:
            raise KeyError(f"Feature provider '{name}' not found in registry.")
        return cls._providers[name]

    @classmethod
    def get_all(cls) -> dict[str, Type[BaseFeatureProvider]]:
        """Get all registered feature providers."""
        return dict(cls._providers)

    @classmethod
    def discover(cls, package: str) -> None:
        """Discover and register feature providers in a package."""
        module = importlib.import_module(package)
        if not hasattr(module, '__path__'):
            return
            
        for _, name, _ in pkgutil.iter_modules(module.__path__):
            importlib.import_module(f"{package}.{name}")

    @classmethod
    def list_names(cls) -> list[str]:
        """List all registered feature provider names."""
        return list(cls._providers.keys())
