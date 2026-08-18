from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from rrag_ingestion.config import settings
from rrag_ingestion.core.pipeline import PipelineEngine
from rrag_ingestion.dependencies import AuthContext, get_current_user
from rrag_ingestion.models.pipeline import PipelineConfig

router = APIRouter()


def _pipelines_dir(workspace_id: str) -> Path:
    return Path(settings.configs_dir) / "pipelines" / workspace_id


@router.get("")
async def list_pipelines(
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "viewer")
    pipelines_dir = _pipelines_dir(workspace_id)
    if not pipelines_dir.exists():
        return {"pipelines": []}

    result = []
    for p in pipelines_dir.glob("*.yaml"):
        with open(p) as f:
            raw = yaml.safe_load(f)
        result.append({
            "name": raw.get("name", p.stem),
            "description": raw.get("description", ""),
            "steps": len(raw.get("steps", [])),
        })
    return {"pipelines": result}


def _find_pipeline(name: str, workspace_id: str) -> Path | None:
    """Find a pipeline file by name field or filename stem."""
    pipelines_dir = _pipelines_dir(workspace_id)
    direct = pipelines_dir / f"{name}.yaml"
    if direct.exists():
        return direct
    # Search by name field inside YAML
    if pipelines_dir.exists():
        for p in pipelines_dir.glob("*.yaml"):
            with open(p) as f:
                raw = yaml.safe_load(f)
            if raw and raw.get("name") == name:
                return p
    return None


@router.get("/{name}")
async def get_pipeline(
    name: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "viewer")
    path = _find_pipeline(name, workspace_id)
    if not path:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")
    with open(path) as f:
        return yaml.safe_load(f)


def _sanitize_pipeline_name(name: str) -> str:
    """Sanitize pipeline name to prevent path traversal."""
    # Only use the basename and strip any path separators
    safe = name.replace("/", "_").replace("\\", "_").replace("..", "_").strip("._")
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid pipeline name")
    return safe


@router.post("")
async def create_pipeline(
    pipeline: PipelineConfig,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    safe_name = _sanitize_pipeline_name(pipeline.name)
    pipelines_dir = _pipelines_dir(workspace_id)
    pipelines_dir.mkdir(parents=True, exist_ok=True)
    path = pipelines_dir / f"{safe_name}.yaml"
    data = {
        "name": pipeline.name,
        "description": pipeline.description,
        "steps": [s.model_dump() for s in pipeline.steps],
    }
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    return {"created": pipeline.name}


@router.put("/{name}")
async def update_pipeline(
    name: str,
    pipeline: PipelineConfig,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    path = _find_pipeline(name, workspace_id)
    if not path:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")
    data = {
        "name": pipeline.name,
        "description": pipeline.description,
        "steps": [s.model_dump() for s in pipeline.steps],
    }
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    return {"updated": name}


@router.delete("/{name}")
async def delete_pipeline(
    name: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    path = _find_pipeline(name, workspace_id)
    if not path:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")
    path.unlink()
    return {"deleted": name}


@router.post("/{name}/validate")
async def validate_pipeline(
    name: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    path = _find_pipeline(name, workspace_id)
    if not path:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")

    registry = request.app.state.registry
    engine = PipelineEngine(registry)
    pipeline_def = engine.load_pipeline(path)
    errors = engine.validate_pipeline(pipeline_def)

    return {"valid": len(errors) == 0, "errors": errors}
