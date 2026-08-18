from __future__ import annotations

import logging

from rrag_ingestion.components.planners.base import BasePlanner
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)


@register_component
class CoRAGGreedyStrategy(BasePlanner):
    """Greedy single-path strategy from CoRAG."""

    name = "corag.greedy_strategy"
    version = "0.1.0"
    description = "Single sequential retrieval path - fast, deterministic (from CoRAG)"
    config_schema = {
        "max_path_length": {"type": "integer", "default": 3},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        max_length = config.get("max_path_length", 3)
        return ComponentResult(
            data={
                **input_data.data,
                "strategy": "greedy",
                "max_path_length": max_length,
                "num_paths": 1,
            },
            metadata={"strategy": "greedy"},
        )


@register_component
class CoRAGBestOfNStrategy(BasePlanner):
    """Best-of-N parallel sampling strategy from CoRAG."""

    name = "corag.best_of_n_strategy"
    version = "0.1.0"
    description = "Sample N parallel retrieval paths and select best (from CoRAG)"
    config_schema = {
        "n": {"type": "integer", "default": 4},
        "max_path_length": {"type": "integer", "default": 3},
        "temperature": {"type": "number", "default": 0.7},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        n = config.get("n", 4)
        max_length = config.get("max_path_length", 3)
        return ComponentResult(
            data={
                **input_data.data,
                "strategy": "best_of_n",
                "max_path_length": max_length,
                "num_paths": n,
                "temperature": config.get("temperature", 0.7),
            },
            metadata={"strategy": "best_of_n", "n": n},
        )


@register_component
class CoRAGTreeSearchStrategy(BasePlanner):
    """Tree search strategy with BFS expansion from CoRAG."""

    name = "corag.tree_search_strategy"
    version = "0.1.0"
    description = "BFS tree expansion with Monte Carlo rollouts for best path selection (from CoRAG)"
    config_schema = {
        "expand_size": {"type": "integer", "default": 4},
        "num_rollouts": {"type": "integer", "default": 2},
        "beam_size": {"type": "integer", "default": 2},
        "max_path_length": {"type": "integer", "default": 5},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        return ComponentResult(
            data={
                **input_data.data,
                "strategy": "tree_search",
                "expand_size": config.get("expand_size", 4),
                "num_rollouts": config.get("num_rollouts", 2),
                "beam_size": config.get("beam_size", 2),
                "max_path_length": config.get("max_path_length", 5),
            },
            metadata={"strategy": "tree_search"},
        )
