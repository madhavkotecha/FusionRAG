"""Auth API router - all authentication and user management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from rrag.auth.audit import log_audit_event
from rrag.auth.dependencies import (
    get_auth_service,
    get_current_user,
    require_org_admin,
    require_permission,
    require_ws_member,
)
from rrag.auth.permissions import AuthContext
from rrag.auth.schemas import (
    AddMemberRequest,
    APIKeyCreatedResponse,
    APIKeyResponse,
    AuditLogListResponse,
    AuditLogResponse,
    CreateAPIKeyRequest,
    InviteUserRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    SessionResponse,
    SSOConfigRequest,
    SSOConfigResponse,
    TokenResponse,
    UpdateMemberRoleRequest,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
    UserProfileResponse,
    UserResponse,
    WorkspaceMemberResponse,
    WorkspaceMembershipInfo,
)
from rrag.auth.service import AuthError, AuthService
from rrag.config import settings
from rrag.db.session import get_db

router = APIRouter(tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ── Registration & Login ────────────────────────────────────────────


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    svc: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Register a new user with a new organization."""
    try:
        user, org, workspace = await svc.register(
            email=body.email,
            password=body.password,
            name=body.name,
            org_name=body.org_name,
            org_slug=body.org_slug,
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    access_token, refresh_token, _ = await svc.login(
        email=body.email, password=body.password
    )

    await log_audit_event(
        db,
        org_id=str(org.id),
        user_id=str(user.id),
        action="register",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=_client_ip(request),
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        refresh_token=refresh_token,
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    svc: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email + password."""
    try:
        access_token, refresh_token, user = await svc.login(
            email=body.email,
            password=body.password,
            device_info={"ip": _client_ip(request), "user_agent": request.headers.get("User-Agent")},
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    await log_audit_event(
        db,
        org_id=str(user.org_id),
        user_id=str(user.id),
        action="login",
        resource_type="session",
        ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        refresh_token=refresh_token,
    )


@router.post("/auth/token/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    svc: AuthService = Depends(get_auth_service),
):
    """Issue new access + refresh tokens using a valid refresh token."""
    try:
        access_token, new_refresh = await svc.refresh_tokens(body.refresh_token)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        refresh_token=new_refresh,
    )


@router.post("/auth/logout", status_code=200)
async def logout(
    body: LogoutRequest,
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Revoke refresh token and blacklist access token."""
    # Extract jti from current token
    auth_header = request.headers.get("Authorization", "")
    token_str = auth_header.removeprefix("Bearer ")
    try:
        payload = svc.token_manager.verify_access_token(token_str)
        jti = payload.get("jti")
    except Exception:
        jti = None

    await svc.logout(
        refresh_token=body.refresh_token,
        access_token_jti=jti,
        remaining_ttl=settings.jwt_access_token_expire_minutes * 60,
    )

    await log_audit_event(
        db,
        org_id=auth.org_id,
        user_id=auth.user_id,
        action="logout",
        resource_type="session",
        ip_address=_client_ip(request),
    )

    return {"detail": "Logged out successfully"}


@router.post("/auth/logout/all", status_code=200)
async def logout_all(
    auth: AuthContext = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all sessions for the current user."""
    count = await svc.logout_all(auth.user_id)

    await log_audit_event(
        db,
        org_id=auth.org_id,
        user_id=auth.user_id,
        action="logout_all",
        resource_type="session",
        details={"sessions_revoked": count},
    )

    return {"detail": f"Revoked {count} sessions"}


@router.get("/auth/me", response_model=UserProfileResponse)
async def get_me(
    auth: AuthContext = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
):
    """Get the current user's profile."""
    user = await svc.get_user_by_id(auth.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    memberships = []
    for m in user.workspace_memberships:
        ws = m.workspace
        memberships.append(
            WorkspaceMembershipInfo(
                workspace_id=m.workspace_id,
                workspace_name=ws.name if ws else "Unknown",
                role=m.role,
            )
        )

    return UserProfileResponse(
        id=user.id,
        org_id=user.org_id,
        email=user.email,
        name=user.name,
        org_role=user.org_role,
        workspace_memberships=memberships,
    )


@router.get("/auth/sessions", response_model=list[SessionResponse])
async def list_sessions(
    auth: AuthContext = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
):
    """List active sessions for the current user."""
    sessions = await svc.list_user_sessions(auth.user_id)
    return [
        SessionResponse(
            id=s.id,
            device_info=s.device_info,
            last_active_at=s.last_active_at,
            created_at=s.created_at,
        )
        for s in sessions
    ]


@router.delete("/auth/sessions/{session_id}", status_code=200)
async def revoke_session(
    session_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
):
    """Revoke a specific session."""
    try:
        await svc.revoke_session(str(session_id), auth.user_id)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return {"detail": "Session revoked"}


# ── User Management (Org Admin) ────────────────────────────────────


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    auth: AuthContext = require_org_admin(),
    svc: AuthService = Depends(get_auth_service),
):
    """List all users in the organization."""
    users = await svc.list_org_users(auth.org_id)
    return [UserResponse.model_validate(u) for u in users]


@router.post("/users/invite", status_code=201)
async def invite_user(
    body: InviteUserRequest,
    request: Request,
    auth: AuthContext = require_org_admin(),
    svc: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Invite a user to the organization by email."""
    try:
        invitation = await svc.create_invitation(
            org_id=auth.org_id,
            email=body.email,
            invited_by=auth.user_id,
            workspace_id=str(body.workspace_id) if body.workspace_id else None,
            role=body.role,
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    await log_audit_event(
        db,
        org_id=auth.org_id,
        user_id=auth.user_id,
        action="user_invite",
        resource_type="invitation",
        resource_id=str(invitation.id),
        details={"email": body.email, "role": body.role},
        ip_address=_client_ip(request),
    )

    return {"detail": "Invitation sent", "invitation_id": str(invitation.id)}


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    body: UpdateUserRoleRequest,
    auth: AuthContext = require_org_admin(),
    svc: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's organization-level role."""
    try:
        user = await svc.update_user_role(str(user_id), body.org_role)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    await log_audit_event(
        db,
        org_id=auth.org_id,
        user_id=auth.user_id,
        action="role_change",
        resource_type="user",
        resource_id=str(user_id),
        details={"new_role": body.org_role},
    )

    return UserResponse.model_validate(user)


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: uuid.UUID,
    body: UpdateUserStatusRequest,
    auth: AuthContext = require_org_admin(),
    svc: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Suspend, reactivate, or deactivate a user."""
    try:
        user = await svc.update_user_status(str(user_id), body.status)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    await log_audit_event(
        db,
        org_id=auth.org_id,
        user_id=auth.user_id,
        action=f"user_{body.status}",
        resource_type="user",
        resource_id=str(user_id),
    )

    return UserResponse.model_validate(user)


# ── Workspace Members ───────────────────────────────────────────────


@router.get(
    "/workspaces/{ws_id}/members",
    response_model=list[WorkspaceMemberResponse],
)
async def list_workspace_members(
    ws_id: uuid.UUID,
    auth: AuthContext = require_ws_member(),
    svc: AuthService = Depends(get_auth_service),
):
    """List members of a workspace."""
    members = await svc.list_workspace_members(str(ws_id))
    results = []
    for m in members:
        user = m.user
        results.append(
            WorkspaceMemberResponse(
                id=m.id,
                workspace_id=m.workspace_id,
                user_id=m.user_id,
                user_email=user.email if user else None,
                user_name=user.name if user else None,
                role=m.role,
                created_at=m.created_at,
            )
        )
    return results


@router.post("/workspaces/{ws_id}/members", response_model=WorkspaceMemberResponse, status_code=201)
async def add_workspace_member(
    ws_id: uuid.UUID,
    body: AddMemberRequest,
    auth: AuthContext = require_permission("workspace.members", "manage"),
    svc: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Add a member to a workspace."""
    try:
        member = await svc.add_workspace_member(str(ws_id), str(body.user_id), body.role)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    await log_audit_event(
        db,
        org_id=auth.org_id,
        user_id=auth.user_id,
        action="member_add",
        resource_type="workspace_member",
        workspace_id=str(ws_id),
        details={"added_user_id": str(body.user_id), "role": body.role},
    )

    return WorkspaceMemberResponse(
        id=member.id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        role=member.role,
        created_at=member.created_at,
    )


@router.put("/workspaces/{ws_id}/members/{user_id}", response_model=WorkspaceMemberResponse)
async def update_member_role(
    ws_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    auth: AuthContext = require_permission("workspace.members", "manage"),
    svc: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Update a workspace member's role."""
    try:
        member = await svc.update_workspace_member_role(str(ws_id), str(user_id), body.role)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    await log_audit_event(
        db,
        org_id=auth.org_id,
        user_id=auth.user_id,
        action="member_role_change",
        resource_type="workspace_member",
        workspace_id=str(ws_id),
        details={"target_user_id": str(user_id), "new_role": body.role},
    )

    return WorkspaceMemberResponse(
        id=member.id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        role=member.role,
        created_at=member.created_at,
    )


@router.delete("/workspaces/{ws_id}/members/{user_id}", status_code=200)
async def remove_member(
    ws_id: uuid.UUID,
    user_id: uuid.UUID,
    auth: AuthContext = require_permission("workspace.members", "manage"),
    svc: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from a workspace."""
    try:
        await svc.remove_workspace_member(str(ws_id), str(user_id))
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    await log_audit_event(
        db,
        org_id=auth.org_id,
        user_id=auth.user_id,
        action="member_remove",
        resource_type="workspace_member",
        workspace_id=str(ws_id),
        details={"removed_user_id": str(user_id)},
    )

    return {"detail": "Member removed"}


# ── API Keys ────────────────────────────────────────────────────────


@router.get("/workspaces/{ws_id}/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    ws_id: uuid.UUID,
    auth: AuthContext = require_ws_member(),
    svc: AuthService = Depends(get_auth_service),
):
    """List API keys for a workspace (prefix only, never full key)."""
    keys = await svc.list_api_keys(str(ws_id))
    return [APIKeyResponse.model_validate(k) for k in keys]


@router.post(
    "/workspaces/{ws_id}/api-keys",
    response_model=APIKeyCreatedResponse,
    status_code=201,
)
async def create_api_key(
    ws_id: uuid.UUID,
    body: CreateAPIKeyRequest,
    auth: AuthContext = require_permission("api_key", "manage"),
    svc: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key. The full key is shown only in this response."""
    try:
        api_key, raw_key = await svc.create_api_key(
            workspace_id=str(ws_id),
            name=body.name,
            created_by=auth.user_id,
            role=body.role,
            rate_limit_rpm=body.rate_limit_rpm,
            expires_at=body.expires_at,
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    await log_audit_event(
        db,
        org_id=auth.org_id,
        user_id=auth.user_id,
        action="api_key_create",
        resource_type="api_key",
        resource_id=str(api_key.id),
        workspace_id=str(ws_id),
        details={"name": body.name, "role": body.role},
    )

    return APIKeyCreatedResponse(
        id=api_key.id,
        workspace_id=api_key.workspace_id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=raw_key,
        role=api_key.role,
        rate_limit_rpm=api_key.rate_limit_rpm,
        expires_at=api_key.expires_at,
        status=api_key.status,
        created_at=api_key.created_at,
    )


@router.delete("/workspaces/{ws_id}/api-keys/{key_id}", status_code=200)
async def revoke_api_key(
    ws_id: uuid.UUID,
    key_id: uuid.UUID,
    auth: AuthContext = require_permission("api_key", "manage"),
    svc: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key immediately."""
    try:
        await svc.revoke_api_key(str(key_id), str(ws_id))
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    await log_audit_event(
        db,
        org_id=auth.org_id,
        user_id=auth.user_id,
        action="api_key_revoke",
        resource_type="api_key",
        resource_id=str(key_id),
        workspace_id=str(ws_id),
    )

    return {"detail": "API key revoked"}


# ── SSO (Stub endpoints for Phase 3) ───────────────────────────────


@router.get("/org/sso", response_model=SSOConfigResponse | None)
async def get_sso_config(auth: AuthContext = require_org_admin()):
    """Get current SSO configuration. (Phase 3)"""
    raise HTTPException(status_code=501, detail="SSO is not yet implemented (Phase 3)")


@router.put("/org/sso", response_model=SSOConfigResponse)
async def update_sso_config(body: SSOConfigRequest, auth: AuthContext = require_org_admin()):
    """Create or update SSO configuration. (Phase 3)"""
    raise HTTPException(status_code=501, detail="SSO is not yet implemented (Phase 3)")


@router.delete("/org/sso", status_code=200)
async def delete_sso_config(auth: AuthContext = require_org_admin()):
    """Remove SSO configuration. (Phase 3)"""
    raise HTTPException(status_code=501, detail="SSO is not yet implemented (Phase 3)")


@router.post("/org/sso/test", status_code=200)
async def test_sso_config(auth: AuthContext = require_org_admin()):
    """Test SSO configuration. (Phase 3)"""
    raise HTTPException(status_code=501, detail="SSO is not yet implemented (Phase 3)")


# ── Audit Logs ──────────────────────────────────────────────────────


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    workspace_id: uuid.UUID | None = None,
    action: str | None = None,
    user_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
    auth: AuthContext = require_permission("audit_log", "read"),
    svc: AuthService = Depends(get_auth_service),
):
    """Query audit logs with optional filters."""
    logs, total = await svc.query_audit_logs(
        org_id=auth.org_id,
        workspace_id=str(workspace_id) if workspace_id else None,
        action=action,
        user_id=str(user_id) if user_id else None,
        page=page,
        page_size=page_size,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(l) for l in logs],
        total=total,
        page=page,
        page_size=page_size,
    )
