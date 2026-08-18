from __future__ import annotations

from typing import Any

from ..components.base import BaseComponent


class StepContext:
    """Carries data between steps within a composite component."""

    def __init__(self, input_data: dict[str, Any], config: dict[str, Any]):
        self.current_data = dict(input_data)
        self.step_results: dict[str, dict] = {}
        self.route: str | None = None
        self.iteration: int = 0

    def update(self, method_name: str, result: dict[str, Any]) -> None:
        self.step_results[method_name] = result
        self.current_data = {**self.current_data, **result}

    @property
    def final_output(self) -> dict[str, Any]:
        return self.current_data


class CompositeComponent(BaseComponent):
    """Base class for decorator-driven composite components.

    Subclasses do not override execute(). The framework calls
    @step methods in order, handling retry and routing.
    """

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        meta = getattr(self.__class__, "_component_meta", None)
        if not meta or not meta.get("steps"):
            raise RuntimeError(
                f"{self.__class__.__name__} has no _component_meta with steps. "
                "Use @component and @step decorators."
            )

        steps = sorted(meta["steps"], key=lambda s: s["order"])
        context = StepContext(input_data=input_data, config=config)
        max_iterations = config.get("max_iterations", 5)

        await self._run_steps(steps, 0, context, config, max_iterations)
        return context.final_output

    async def _run_steps(
        self,
        steps: list[dict],
        start_index: int,
        context: StepContext,
        config: dict[str, Any],
        max_iterations: int,
    ) -> None:
        for i in range(start_index, len(steps)):
            step_meta = steps[i]
            method = getattr(self, step_meta["method"])

            # Retry loop
            result = None
            max_attempts = step_meta.get("retry", 0) + 1
            for attempt in range(max_attempts):
                result = await method(context.current_data, config)
                if step_meta.get("retry_condition"):
                    if not result.get(step_meta["retry_condition"], False):
                        break
                else:
                    break

            # Output routing
            if step_meta.get("outputs") and result:
                route = result.get("_route", step_meta["outputs"][0])
                context.route = route

                target_index = self._resolve_route_index(steps, route)
                if target_index is not None and target_index < i:
                    context.iteration += 1
                    if context.iteration < max_iterations:
                        context.update(step_meta["method"], result)
                        await self._run_steps(
                            steps, target_index, context, config, max_iterations
                        )
                        return

            context.update(step_meta["method"], result)

    def _resolve_route_index(
        self, steps: list[dict], route: str
    ) -> int | None:
        """Map route string to step index. Match by name or method."""
        for i, s in enumerate(steps):
            if s["name"].lower() == route.lower() or s["method"] == route:
                return i
        return None
