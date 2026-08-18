from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Any

from .base import CompositeComponent
from .minio_client import download_component_file


class ComponentLoadError(Exception):
    pass


class ComponentLoader:
    _class_cache: dict[str, type] = {}

    def __init__(self, minio_client: Any, cache_dir: Path = Path("/data/components")):
        self.minio = minio_client
        self.cache_dir = cache_dir

    def load_from_cache(self, component) -> CompositeComponent:
        file_hash = component.file_hash
        if file_hash in self._class_cache:
            return self._class_cache[file_hash]()

        local_path = self.cache_dir / component.file_path
        if not local_path.exists():
            raise ComponentLoadError(
                f"Component file not found at {local_path}. "
                "Run ensure_cached() first."
            )

        cls = self._import_component_class(component.type, local_path)
        self._class_cache[file_hash] = cls
        return cls()

    def ensure_cached(self, component) -> Path:
        local_path = self.cache_dir / component.file_path
        if local_path.exists():
            local_hash = hashlib.md5(local_path.read_bytes()).hexdigest()
            if local_hash == component.file_hash:
                return local_path

        local_path.parent.mkdir(parents=True, exist_ok=True)
        content = download_component_file(self.minio, component.file_path)
        local_path.write_bytes(content)
        return local_path

    def load(self, component) -> CompositeComponent:
        self.ensure_cached(component)
        return self.load_from_cache(component)

    def _import_component_class(self, module_name: str, path: Path) -> type:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ComponentLoadError(f"Cannot create module spec for {path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if isinstance(obj, type) and hasattr(obj, "_component_meta"):
                return obj

        raise ComponentLoadError(f"No @component class found in {path}")
