from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from rrag_ingestion.core.base import BaseComponent, ComponentResult
from rrag_ingestion.core.registry import ComponentRegistry

logger = logging.getLogger(__name__)


@dataclass
class PipelineStep:
    component: str
    config: dict = field(default_factory=dict)
    condition: str | None = None


@dataclass
class PipelineDefinition:
    name: str
    description: str = ""
    steps: list[PipelineStep] = field(default_factory=list)


class PipelineEngine:
    """Executes a pipeline by chaining components sequentially."""

    def __init__(self, registry: ComponentRegistry):
        self.registry = registry

    def load_pipeline(self, yaml_path: str | Path) -> PipelineDefinition:
        path = Path(yaml_path)
        with open(path) as f:
            raw = yaml.safe_load(f)

        steps = []
        for step_raw in raw.get("steps", []):
            steps.append(PipelineStep(
                component=step_raw["component"],
                config=step_raw.get("config", {}),
                condition=step_raw.get("condition"),
            ))

        return PipelineDefinition(
            name=raw.get("name", path.stem),
            description=raw.get("description", ""),
            steps=steps,
        )

    async def execute(
        self,
        pipeline: PipelineDefinition,
        initial_input: ComponentResult,
        job_id: str | None = None,
        progress_callback: Any = None,
        sub_progress_callback: Any = None,
        step_start_callback: Any = None,
        skip_steps: int = 0,
        checkpoint_callback: Any = None,
    ) -> ComponentResult:
        """Execute pipeline steps sequentially.

        If ``skip_steps`` > 0, the first N steps are skipped (marked as
        already-completed) and execution resumes from step ``skip_steps``.
        This enables resume-from-failure without re-running completed steps.

        If ``checkpoint_callback`` is provided, it's called after each
        successful step with (step_index, result_data) so intermediate
        results can be persisted to disk for future resume.
        """
        current = initial_input
        total_steps = len(pipeline.steps)

        # Preserve context keys (datastore_id, workspace_id) across all steps
        _context_keys = ("datastore_id", "workspace_id")
        context = {k: initial_input.data.get(k) for k in _context_keys if initial_input.data.get(k)}

        for i, step in enumerate(pipeline.steps):
            # Skip already-completed steps when resuming
            if i < skip_steps:
                logger.info(f"[{pipeline.name}] Skipping step {i + 1}/{total_steps}: {step.component} (already completed)")
                if progress_callback:
                    progress_callback(
                        job_id=job_id,
                        step=i + 1,
                        total=total_steps,
                        component=step.component,
                        status="skipped",
                        result=None,
                    )
                continue

            logger.info(f"[{pipeline.name}] Step {i + 1}/{total_steps}: {step.component}")

            if step_start_callback:
                step_start_callback(step=i + 1, total=total_steps, component=step.component)

            # Inject context keys if missing from current step input
            for k, v in context.items():
                if k not in current.data:
                    current.data[k] = v

            component: BaseComponent = self.registry.create(step.component)
            if sub_progress_callback:
                component._progress_fn = sub_progress_callback
            current = await component.invoke_with_metrics(current, step.config)

            if progress_callback:
                progress_callback(
                    job_id=job_id,
                    step=i + 1,
                    total=total_steps,
                    component=step.component,
                    status="error" if current.errors else "ok",
                    result=current,
                )

            if current.errors:
                logger.warning(f"[{pipeline.name}] Step {step.component} errors: {current.errors}")
            elif checkpoint_callback:
                # Save checkpoint after successful step for resume capability
                try:
                    checkpoint_callback(i, current.data)
                except Exception as e:
                    logger.debug(f"Checkpoint save failed: {e}")

        return current

    def validate_pipeline(self, pipeline: PipelineDefinition) -> list[str]:
        """Check all components exist and configs are valid."""
        errors = []
        for i, step in enumerate(pipeline.steps):
            try:
                cls = self.registry.get(step.component)
                instance = cls()
                step_errors = instance.validate_config(step.config)
                errors.extend(
                    f"Step {i + 1} ({step.component}): {e}" for e in step_errors
                )
            except KeyError as e:
                errors.append(f"Step {i + 1}: {e}")
        return errors
