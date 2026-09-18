from __future__ import annotations

import importlib
import pkgutil
from typing import Type

from app.features.base import BaseFeatureProvider

class FeatureRegistry:
    _providers: dict[str, Type[BaseFeatureProvider]] = {}

    @classmethod
    def register(cls, provider_class: Type[BaseFeatureProvider]) -> Type[BaseFeatureProvider]:
        cls._providers[provider_class.name] = provider_class
        return provider_class

    @classmethod
    def get(cls, name: str) -> Type[BaseFeatureProvider]:
        if name not in cls._providers:
            raise KeyError(f"Feature provider '{name}' not found in registry.")
        return cls._providers[name]

    @classmethod
    def get_all(cls) -> dict[str, Type[BaseFeatureProvider]]:
        return dict(cls._providers)

    @classmethod
    def discover(cls, package: str) -> None:
        module = importlib.import_module(package)
        if not hasattr(module, '__path__'):
            return
            
        for _, name, _ in pkgutil.iter_modules(module.__path__):
            importlib.import_module(f"{package}.{name}")

    @classmethod
    def list_names(cls) -> list[str]:
        return list(cls._providers.keys())
