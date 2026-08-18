"""FastAPI dependencies for authentication and authorization."""

import time
import uuid

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from rrag.auth.permissions import AuthContext, has_permission
from rrag.auth.service import AuthService
from rrag.auth.token import TokenManager
from rrag.config import settings
from rrag.db.session import get_db, get_redis


async def get_token_manager(redis: aioredis.Redis = Depends(get_redis)) -> TokenManager:
    return TokenManager(redis_client=redis)


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
    token_manager: TokenManager = Depends(get_token_manager),
) -> AuthService:
    return AuthService(db=db, token_manager=token_manager)


async def get_current_user(
    request: Request,
    token_manager: TokenManager = Depends(get_token_manager),
) -> AuthContext:
    """Extract and validate JWT from Authorization header.

    Returns an AuthContext with user identity and roles.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = auth_header.removeprefix("Bearer ")

    try:
        payload = token_manager.verify_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Check blacklist
    jti = payload.get("jti", "")
    if await token_manager.is_token_blacklisted(jti):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    return AuthContext(
        user_id=payload["sub"],
        org_id=payload["org_id"],
        org_role=payload["org_role"],
        email=payload.get("email", ""),
        name=payload.get("name", ""),
        workspace_memberships=payload.get("ws_roles", {}),
    )


async def get_optional_user(
    request: Request,
    token_manager: TokenManager = Depends(get_token_manager),
) -> AuthContext | None:
    """Like get_current_user but returns None instead of 401 for unauthenticated."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        return await get_current_user(request, token_manager)
    except HTTPException:
        return None


def require_permission(resource: str, action: str):
    """Factory that creates a dependency checking a specific permission."""

    async def checker(
        request: Request,
        auth: AuthContext = Depends(get_current_user),
    ) -> AuthContext:
        ws_id = request.path_params.get("ws_id")
        if not has_permission(auth, ws_id, resource, action):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions: {resource}:{action}",
            )
        return auth

    return Depends(checker)


def require_org_admin():
    """Dependency that requires the user to be an org admin."""

    async def checker(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
        if auth.org_role != "org_admin" and not auth.is_platform_admin:
            raise HTTPException(status_code=403, detail="Org admin access required")
        return auth

    return Depends(checker)


def require_ws_member():
    """Dependency that requires the user to be a member of the workspace."""

    async def checker(
        request: Request,
        auth: AuthContext = Depends(get_current_user),
    ) -> AuthContext:
        ws_id = request.path_params.get("ws_id")
        if auth.org_role == "org_admin" or auth.is_platform_admin:
            return auth
        if ws_id and ws_id not in auth.workspace_memberships:
            raise HTTPException(status_code=403, detail="Not a member of this workspace")
        return auth

    return Depends(checker)


async def check_rate_limit(
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
    auth: AuthContext | None = Depends(get_optional_user),
) -> None:
    """Rate limiting dependency using Redis sliding window."""
    if auth:
        key = f"rl:user:{auth.user_id}"
        limit = settings.rate_limit_authenticated
    else:
        client_ip = request.client.host if request.client else "unknown"
        key = f"rl:ip:{client_ip}"
        limit = settings.rate_limit_unauthenticated

    now = time.time()
    window = 60  # 1 minute

    pipe = redis.pipeline()
    pipe.zadd(key, {str(now): now})
    pipe.zremrangebyscore(key, 0, now - window)
    pipe.zcard(key)
    pipe.expire(key, window)
    results = await pipe.execute()
    count = results[2]

    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )
