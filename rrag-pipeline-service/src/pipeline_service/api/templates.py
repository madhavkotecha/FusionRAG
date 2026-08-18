"""Pipeline templates API - reads from database."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..services.template_store import get_all_templates, get_template

router = APIRouter()


def _parse_definition(defn) -> dict:
    """Ensure definition is a dict, handling double-encoded JSON strings."""
    if isinstance(defn, str):
        try:
            defn = json.loads(defn)
        except (json.JSONDecodeError, TypeError):
            defn = {}
    return defn if isinstance(defn, dict) else {}


def _to_dict(t) -> dict:
    if isinstance(t, dict):
        return {
            "id": t.get("template_id", ""),
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "category": t.get("category", ""),
            "definition": _parse_definition(t.get("definition", {})),
        }
    return {
        "id": t.template_id,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "definition": _parse_definition(t.definition),
    }


@router.get("")
async def list_templates(request: Request, db: AsyncSession = Depends(get_session)):
    """Return all available pipeline templates."""
    templates = await get_all_templates(db, redis=request.app.state.redis)
    return [_to_dict(t) for t in templates]


@router.get("/{template_id}")
async def get_template_detail(
    template_id: str, request: Request, db: AsyncSession = Depends(get_session)
):
    """Return a specific pipeline template."""
    t = await get_template(db, template_id, redis=request.app.state.redis)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return _to_dict(t)
