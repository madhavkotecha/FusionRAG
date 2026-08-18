from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from rrag_ingestion.core.base import ComponentType

router = APIRouter()


@router.get("")
async def list_components(request: Request):
    registry = request.app.state.registry
    return {"components": registry.list_all()}


@router.get("/types/{component_type}")
async def list_by_type(component_type: str, request: Request):
    registry = request.app.state.registry
    try:
        ct = ComponentType(component_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown type: {component_type}. Valid types: {[t.value for t in ComponentType]}",
        )
    return {"components": registry.list_by_type(ct)}


@router.get("/{name}")
async def get_component(name: str, request: Request):
    registry = request.app.state.registry
    try:
        cls = registry.get(name)
        return cls.get_info(cls)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Component '{name}' not found")
