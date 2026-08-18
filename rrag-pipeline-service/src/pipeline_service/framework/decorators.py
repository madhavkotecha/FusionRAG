from __future__ import annotations

from typing import Any


def component(
    category: str,
    name: str,
    description: str = "",
    config_schema: dict | None = None,
    input_ports: list[dict[str, str]] | None = None,
    output_ports: list[dict[str, str]] | None = None,
):
    """Class decorator that attaches _component_meta to the class.

    Pure metadata — does not alter class behavior.
    """

    def decorator(cls):
        # Collect @step methods already attached to the class
        steps = []
        for attr_name in list(vars(cls)):
            attr = getattr(cls, attr_name, None)
            if callable(attr) and hasattr(attr, "_step_meta"):
                steps.append(attr._step_meta)

        steps.sort(key=lambda s: s["order"])

        # Check for CONFIG_SCHEMA class attribute fallback
        effective_config_schema = config_schema
        if effective_config_schema is None and hasattr(cls, "CONFIG_SCHEMA"):
            effective_config_schema = cls.CONFIG_SCHEMA

        cls._component_meta = {
            "category": category,
            "name": name,
            "description": description,
            "config_schema": effective_config_schema,
            "input_ports": input_ports,
            "output_ports": output_ports,
            "is_composite": len(steps) > 0,
            "steps": steps,
        }
        # Derive component type from class name (snake_case)
        if not hasattr(cls, "_component_type"):
            cls._component_type = _to_snake_case(cls.__name__)

        return cls

    return decorator


def step(
    order: int,
    name: str | None = None,
    description: str = "",
    retry: int = 0,
    retry_condition: str | None = None,
    outputs: list[str] | None = None,
    config_schema: dict | None = None,
):
    """Method decorator that attaches _step_meta to the method.

    Pure metadata — does not alter method behavior.
    """

    def decorator(func):
        func._step_meta = {
            "order": order,
            "name": name or func.__name__.replace("_", " ").title(),
            "method": func.__name__,
            "description": description,
            "retry": retry,
            "retry_condition": retry_condition,
            "outputs": outputs,
            "config_schema": config_schema,
        }
        return func

    return decorator


def _to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case, handling acronyms.

    LightRAGRetrieval -> lightrag_retrieval (not light_r_a_g_retrieval)
    """
    import re

    # Insert underscore between lowercase/digit and uppercase-then-lowercase
    # (keeps acronyms glued to preceding word: LightRAG stays together)
    s1 = re.sub(r"([a-z0-9])([A-Z][a-z])", r"\1_\2", name)
    # Insert underscore between acronym run and next capitalised word
    s2 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s1)
    return s2.lower()
