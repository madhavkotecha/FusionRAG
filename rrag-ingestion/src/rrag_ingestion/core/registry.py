from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType, get_registered_components


class ComponentRegistry:
    """Registry that holds all available pipeline components."""

    def __init__(self):
        self._components: dict[str, type[BaseComponent]] = {}

    def register(self, component_cls: type[BaseComponent]) -> None:
        name = component_cls.name
        if not name:
            raise ValueError(f"Component {component_cls.__name__} has no name")
        self._components[name] = component_cls

    def get(self, name: str) -> type[BaseComponent]:
        if name not in self._components:
            available = ", ".join(sorted(self._components.keys()))
            raise KeyError(f"Component '{name}' not found. Available: {available}")
        return self._components[name]

    def create(self, name: str, **kwargs: Any) -> BaseComponent:
        cls = self.get(name)
        return cls(**kwargs)

    def list_by_type(self, component_type: ComponentType) -> list[dict]:
        return [
            cls.get_info(cls)
            for cls in self._components.values()
            if cls.component_type == component_type
        ]

    def list_all(self) -> list[dict]:
        return [cls.get_info(cls) for cls in self._components.values()]

    def auto_discover(self, package_name: str = "rrag_ingestion.components") -> None:
        """Walk the components package and register all decorated components."""
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            return

        if hasattr(package, "__path__"):
            for importer, modname, ispkg in pkgutil.walk_packages(
                package.__path__, prefix=package_name + "."
            ):
                try:
                    importlib.import_module(modname)
                except ImportError:
                    continue

        for cls in get_registered_components():
            if cls.name and cls.name not in self._components:
                self._components[cls.name] = cls
