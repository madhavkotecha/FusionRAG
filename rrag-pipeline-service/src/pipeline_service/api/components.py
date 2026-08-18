from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..services.component_registry import get_all_components, get_component

router = APIRouter()


def _to_dict(comp) -> dict:
    if isinstance(comp, dict):
        return comp
    result = {
        "type": comp.type,
        "category": comp.category,
        "name": comp.name,
        "description": comp.description,
        "config_schema": comp.config_schema,
        "input_ports": comp.input_ports,
        "output_ports": comp.output_ports,
        "source": getattr(comp, "source", "seed"),
        "is_composite": getattr(comp, "is_composite", False),
        "steps": getattr(comp, "steps", None),
        "workspace_id": getattr(comp, "workspace_id", "_global"),
    }
    if result["workspace_id"] == "_global":
        result["workspace_id"] = None
    return result


@router.get("")
async def list_components(
    request: Request,
    source: str | None = Query(None, description="Filter by source: seed or custom"),
    db: AsyncSession = Depends(get_session),
):
    components = await get_all_components(db, redis=request.app.state.redis)
    result = [_to_dict(c) for c in components]
    if source:
        result = [c for c in result if c.get("source") == source]
    return result


@router.get("/{component_type}")
async def get_component_detail(
    component_type: str, request: Request, db: AsyncSession = Depends(get_session)
):
    comp = await get_component(db, component_type, redis=request.app.state.redis)
    if not comp:
        raise HTTPException(status_code=404, detail="Component not found")
    return _to_dict(comp)
