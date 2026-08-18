"""Pydantic schemas for request/response validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ── Auth ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    refresh_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


# ── Users ───────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    name: str
    status: str
    org_role: str
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    name: str
    org_role: str
    workspace_memberships: list["WorkspaceMembershipInfo"]

    model_config = {"from_attributes": True}


class WorkspaceMembershipInfo(BaseModel):
    workspace_id: uuid.UUID
    workspace_name: str
    role: str


class InviteUserRequest(BaseModel):
    email: EmailStr
    workspace_id: uuid.UUID | None = None
    role: str = Field(default="developer", pattern="^(admin|developer|viewer)$")


class UpdateUserRoleRequest(BaseModel):
    org_role: str = Field(pattern="^(org_admin|member)$")


class UpdateUserStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|suspended|deactivated)$")


# ── Organizations ───────────────────────────────────────────────────

class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=255, pattern="^[a-z0-9-]+$")


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Workspaces ──────────────────────────────────────────────────────

class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=255, pattern="^[a-z0-9-]+$")


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    slug: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Workspace Members ───────────────────────────────────────────────

class AddMemberRequest(BaseModel):
    user_id: uuid.UUID
    role: str = Field(default="developer", pattern="^(admin|developer|viewer)$")


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(pattern="^(admin|developer|viewer)$")


class WorkspaceMemberResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str | None = None
    user_name: str | None = None
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── API Keys ────────────────────────────────────────────────────────

class CreateAPIKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="developer", pattern="^(admin|developer|viewer)$")
    rate_limit_rpm: int = Field(default=600, ge=1, le=10000)
    expires_at: datetime | None = None


class APIKeyResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    key_prefix: str
    role: str
    rate_limit_rpm: int
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreatedResponse(APIKeyResponse):
    """Response for key creation -- includes the full key (shown only once)."""
    key: str


# ── SSO ─────────────────────────────────────────────────────────────

class SSOConfigRequest(BaseModel):
    protocol: str = Field(pattern="^(saml|oidc)$")
    provider_name: str
    metadata_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    issuer_url: str | None = None
    certificate: str | None = None
    group_mapping: dict | None = None
    auto_provision: bool = True
    enforce_sso: bool = False


class SSOConfigResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    protocol: str
    provider_name: str
    metadata_url: str | None = None
    client_id: str | None = None
    issuer_url: str | None = None
    group_mapping: dict | None = None
    auto_provision: bool
    enforce_sso: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Audit Logs ──────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID | None = None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None = None
    workspace_id: uuid.UUID | None = None
    details: dict | None = None
    ip_address: str | None = None
    status: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


# ── Sessions ────────────────────────────────────────────────────────

class SessionResponse(BaseModel):
    id: uuid.UUID
    device_info: dict | None = None
    last_active_at: datetime
    created_at: datetime
    is_current: bool = False

    model_config = {"from_attributes": True}


# ── Registration (for initial setup / free tier) ────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    name: str = Field(min_length=1, max_length=255)
    org_name: str = Field(min_length=2, max_length=255)
    org_slug: str = Field(min_length=2, max_length=255, pattern="^[a-z0-9-]+$")
