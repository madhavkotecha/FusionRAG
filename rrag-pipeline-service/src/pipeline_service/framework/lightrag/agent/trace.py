"""Agent execution trace for observability and debugging.

Every step of the agentic loop is recorded in an :class:`AgentTrace` so that
callers can inspect what tools were called, what evidence was gathered, and
how many iterations were required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class TraceStep:
    """A single step within the agent loop."""

    iteration: int
    action: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results_summary: list[dict[str, Any]] = field(default_factory=list)
    evaluation: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "action": self.action,
            "tool_calls": self.tool_calls,
            "tool_results_summary": self.tool_results_summary,
            "evaluation": self.evaluation,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
        }


@dataclass
class AgentTrace:
    """Full execution trace for an agentic retrieval run."""

    query: str = ""
    steps: list[TraceStep] = field(default_factory=list)
    total_iterations: int = 0
    final_sufficient: bool = False
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0

    def add_step(self, step: TraceStep) -> None:
        self.steps.append(step)
        self.total_iterations = max(self.total_iterations, step.iteration + 1)

    def finish(self, sufficient: bool) -> None:
        self.final_sufficient = sufficient
        self.finished_at = time.time()

    @property
    def total_duration_ms(self) -> float:
        if self.finished_at > 0:
            return (self.finished_at - self.started_at) * 1000
        return 0.0

    @property
    def total_tool_calls(self) -> int:
        return sum(len(s.tool_calls) for s in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "total_iterations": self.total_iterations,
            "total_tool_calls": self.total_tool_calls,
            "total_duration_ms": self.total_duration_ms,
            "final_sufficient": self.final_sufficient,
            "steps": [s.to_dict() for s in self.steps],
        }
