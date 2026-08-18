"""Generate .py files for seed components and upload to MinIO.

Runs once at startup. Idempotent — skips components that already have files
and version rows.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import textwrap

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..framework.minio_client import (
    COMPONENTS_BUCKET,
    download_component_file,
    ensure_bucket,
    get_minio_client,
    upload_component_file,
)
from ..models.component import Component
from ..models.component_version import ComponentVersion

logger = logging.getLogger("pipeline_service.seed_bootstrap")


def _type_to_class_name(component_type: str) -> str:
    """Convert snake_case type to PascalCase class name."""
    return "".join(word.capitalize() for word in component_type.split("_"))


def _generate_source(comp: dict) -> str:
    """Generate a Python source file from seed component metadata."""
    class_name = _type_to_class_name(comp["type"])
    category = comp["category"]
    name = comp["name"]
    description = comp.get("description", "")
    config_schema = comp.get("config_schema", {})
    input_ports = comp.get("input_ports", [])
    output_ports = comp.get("output_ports", [])

    config_repr = json.dumps(config_schema, indent=4)
    config_lines = config_repr.split("\n")
    config_indented = config_lines[0] + "\n" + "\n".join(
        "        " + line for line in config_lines[1:]
    ) if len(config_lines) > 1 else config_repr

    input_repr = json.dumps(input_ports)
    output_repr = json.dumps(output_ports)

    source = textwrap.dedent(f'''\
        from pipeline_service.framework import component


        @component(
            category="{category}",
            name="{name}",
            description="""{description}""",
            config_schema={config_indented},
            input_ports={input_repr},
            output_ports={output_repr},
        )
        class {class_name}:
            """{name} component.

            {description}
            """

            async def run(self, input_data: dict, config: dict) -> dict:
                """Execute the {name} component."""
                raise NotImplementedError(
                    "{class_name}.run() is a reference stub. "
                    "Replace with actual implementation."
                )
    ''')
    return source


async def bootstrap_seed_files(db: AsyncSession) -> int:
    """Generate .py files for all seed components missing from MinIO.

    Returns the number of components bootstrapped.
    """
    minio = get_minio_client()
    await asyncio.to_thread(ensure_bucket, minio)

    result = await db.execute(
        select(Component).where(Component.source == "seed")
    )
    seed_components = list(result.scalars().all())

    count = 0
    for comp in seed_components:
        comp_type = comp.type
        object_path = f"_global/{comp_type}.py"

        file_exists = False
        try:
            content = await asyncio.to_thread(
                download_component_file, minio, object_path
            )
            file_exists = True
        except Exception:
            content = None

        existing_version = await db.scalar(
            select(ComponentVersion).where(
                ComponentVersion.component_type == comp_type,
                ComponentVersion.workspace_id == "_global",
            ).limit(1)
        )

        if file_exists and existing_version:
            continue

        if not file_exists:
            comp_data = {
                "type": comp.type,
                "category": comp.category,
                "name": comp.name,
                "description": comp.description,
                "config_schema": comp.config_schema,
                "input_ports": comp.input_ports,
                "output_ports": comp.output_ports,
            }
            source = _generate_source(comp_data)
            content = source.encode("utf-8")
            await asyncio.to_thread(
                upload_component_file, minio, "_global", f"{comp_type}.py", content
            )

        if not existing_version:
            code_text = content.decode("utf-8") if isinstance(content, bytes) else content
            file_hash = hashlib.sha256(content if isinstance(content, bytes) else content.encode()).hexdigest()
            ver = ComponentVersion(
                component_type=comp_type,
                workspace_id="_global",
                version=1,
                code=code_text,
                file_hash=file_hash,
                changed_by="system",
                change_reason="Seed component bootstrap",
            )
            db.add(ver)

        await db.execute(
            update(Component)
            .where(Component.type == comp_type, Component.workspace_id == "_global")
            .values(
                file_path=object_path,
                file_hash=hashlib.sha256(content if isinstance(content, bytes) else content.encode()).hexdigest(),
                current_version=1,
            )
        )
        count += 1

    await db.commit()
    logger.info("Bootstrapped %d seed component files", count)
    return count
