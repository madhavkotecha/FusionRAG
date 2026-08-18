"""Auth service - core business logic for authentication and user management."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from rrag.auth.models import (
    APIKey,
    AuditLog,
    Organization,
    Session,
    User,
    UserInvitation,
    Workspace,
    WorkspaceMember,
)
from rrag.auth.token import TokenManager
from rrag.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthError(Exception):
    """Base auth exception."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthService:
    """Handles authentication, registration, and user management."""

    def __init__(self, db: AsyncSession, token_manager: TokenManager):
        self.db = db
        self.token_manager = token_manager

    # ── Password Utilities ──────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def validate_password(password: str) -> None:
        """Enforce password policy."""
        if len(password) < settings.password_min_length:
            raise AuthError(
                f"Password must be at least {settings.password_min_length} characters",
                status_code=422,
            )
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)
        if not (has_upper and has_lower and has_digit and has_special):
            raise AuthError(
                "Password must contain uppercase, lowercase, digit, and special character",
                status_code=422,
            )

    # ── Registration ────────────────────────────────────────────────

    async def register(
        self,
        email: str,
        password: str,
        name: str,
        org_name: str,
        org_slug: str,
    ) -> tuple[User, Organization, Workspace]:
        """Register a new user with a new organization and default workspace."""
        self.validate_password(password)

        # Check org slug uniqueness
        existing = await self.db.execute(
            select(Organization).where(Organization.slug == org_slug)
        )
        if existing.scalar_one_or_none():
            raise AuthError("Organization slug already taken", status_code=409)

        # Check email uniqueness across orgs
        existing_user = await self.db.execute(select(User).where(User.email == email))
        if existing_user.scalar_one_or_none():
            raise AuthError("Email already registered", status_code=409)

        # Create org
        org = Organization(name=org_name, slug=org_slug)
        self.db.add(org)
        await self.db.flush()

        # Create user as org_admin
        user = User(
            org_id=org.id,
            email=email,
            name=name,
            password_hash=self.hash_password(password),
            status="active",
            org_role="org_admin",
        )
        self.db.add(user)
        await self.db.flush()

        # Create default workspace
        workspace = Workspace(org_id=org.id, name="Default", slug="default")
        self.db.add(workspace)
        await self.db.flush()

        # Add user as workspace admin
        member = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin")
        self.db.add(member)
        await self.db.flush()

        return user, org, workspace

    # ── Login ───────────────────────────────────────────────────────

    async def login(
        self,
        email: str,
        password: str,
        device_info: dict | None = None,
    ) -> tuple[str, str, User]:
        """Authenticate with email+password. Returns (access_token, refresh_token, user)."""
        # Find user by email
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            raise AuthError("Invalid email or password", status_code=401)

        # Check account status
        if user.status != "active":
            raise AuthError(f"Account is {user.status}", status_code=403)

        # Check lockout
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise AuthError("Account temporarily locked due to failed login attempts", status_code=403)

        # Verify password
        if not user.password_hash or not self.verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.password_max_failed_attempts:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.password_lockout_minutes
                )
            await self.db.flush()
            raise AuthError("Invalid email or password", status_code=401)

        # Reset failed attempts on success
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)

        # Build workspace roles map
        ws_roles = {
            str(m.workspace_id): m.role for m in user.workspace_memberships
        }

        # Issue tokens
        access_token, jti = self.token_manager.create_access_token(
            user_id=str(user.id),
            org_id=str(user.org_id),
            org_role=user.org_role,
            email=user.email,
            name=user.name,
            workspace_roles=ws_roles,
        )

        refresh_token = TokenManager.generate_refresh_token()
        refresh_hash = TokenManager.hash_token(refresh_token)

        # Store refresh token in Redis
        await self.token_manager.store_refresh_token(
            token_hash=refresh_hash,
            user_id=str(user.id),
            org_id=str(user.org_id),
            device_info=device_info,
        )

        # Store session in DB for session management UI
        session = Session(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            device_info=device_info,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
        self.db.add(session)
        await self.db.flush()

        return access_token, refresh_token, user

    # ── Token Refresh ───────────────────────────────────────────────

    async def refresh_tokens(self, refresh_token: str) -> tuple[str, str]:
        """Refresh access and refresh tokens (rotation).

        Returns (new_access_token, new_refresh_token).
        """
        old_hash = TokenManager.hash_token(refresh_token)

        # Validate in Redis
        token_data = await self.token_manager.validate_refresh_token(old_hash)
        if token_data is None:
            raise AuthError("Invalid or expired refresh token", status_code=401)

        user_id = token_data["user_id"]

        # Revoke old refresh token (one-time use)
        await self.token_manager.revoke_refresh_token(old_hash)

        # Load user with current roles
        result = await self.db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if user is None or user.status != "active":
            raise AuthError("User not found or inactive", status_code=401)

        ws_roles = {str(m.workspace_id): m.role for m in user.workspace_memberships}

        # Issue new tokens
        new_access, _ = self.token_manager.create_access_token(
            user_id=str(user.id),
            org_id=str(user.org_id),
            org_role=user.org_role,
            email=user.email,
            name=user.name,
            workspace_roles=ws_roles,
        )

        new_refresh = TokenManager.generate_refresh_token()
        new_hash = TokenManager.hash_token(new_refresh)

        await self.token_manager.store_refresh_token(
            token_hash=new_hash,
            user_id=str(user.id),
            org_id=str(user.org_id),
        )

        # Update session in DB
        result = await self.db.execute(
            select(Session).where(Session.refresh_token_hash == old_hash)
        )
        session = result.scalar_one_or_none()
        if session:
            session.refresh_token_hash = new_hash
            session.last_active_at = datetime.now(timezone.utc)
            await self.db.flush()

        return new_access, new_refresh

    # ── Logout ──────────────────────────────────────────────────────

    async def logout(
        self, refresh_token: str | None, access_token_jti: str | None, remaining_ttl: int = 900
    ) -> None:
        """Revoke refresh token and blacklist access token."""
        if refresh_token:
            token_hash = TokenManager.hash_token(refresh_token)
            await self.token_manager.revoke_refresh_token(token_hash)

            # Revoke session in DB
            result = await self.db.execute(
                select(Session).where(Session.refresh_token_hash == token_hash)
            )
            session = result.scalar_one_or_none()
            if session:
                session.revoked_at = datetime.now(timezone.utc)
                await self.db.flush()

        if access_token_jti:
            await self.token_manager.blacklist_access_token(access_token_jti, remaining_ttl)

    async def logout_all(self, user_id: str) -> int:
        """Revoke all sessions for a user."""
        count = await self.token_manager.revoke_all_user_tokens(user_id)

        # Revoke all DB sessions
        result = await self.db.execute(
            select(Session).where(
                Session.user_id == uuid.UUID(user_id),
                Session.revoked_at.is_(None),
            )
        )
        sessions = result.scalars().all()
        for s in sessions:
            s.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()

        return count

    # ── User Management ─────────────────────────────────────────────

    async def get_user_by_id(self, user_id: str | uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == uuid.UUID(str(user_id))))
        return result.scalar_one_or_none()

    async def list_org_users(self, org_id: str) -> list[User]:
        result = await self.db.execute(
            select(User)
            .where(User.org_id == uuid.UUID(org_id))
            .order_by(User.created_at)
        )
        return list(result.scalars().all())

    async def update_user_role(self, user_id: str, org_role: str) -> User:
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise AuthError("User not found", status_code=404)
        user.org_role = org_role
        await self.db.flush()
        return user

    async def update_user_status(self, user_id: str, status: str) -> User:
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise AuthError("User not found", status_code=404)
        user.status = status
        if status == "suspended":
            await self.logout_all(str(user.id))
        await self.db.flush()
        return user

    # ── Invitations ─────────────────────────────────────────────────

    async def create_invitation(
        self,
        org_id: str,
        email: str,
        invited_by: str,
        workspace_id: str | None = None,
        role: str = "developer",
    ) -> UserInvitation:
        # Check if user already exists in org
        result = await self.db.execute(
            select(User).where(User.email == email, User.org_id == uuid.UUID(org_id))
        )
        if result.scalar_one_or_none():
            raise AuthError("User already exists in this organization", status_code=409)

        token = secrets.token_urlsafe(32)
        invitation = UserInvitation(
            org_id=uuid.UUID(org_id),
            email=email,
            workspace_id=uuid.UUID(workspace_id) if workspace_id else None,
            role=role,
            token_hash=TokenManager.hash_token(token),
            invited_by=uuid.UUID(invited_by),
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=settings.invitation_expire_hours),
        )
        self.db.add(invitation)
        await self.db.flush()
        # In production, send email with token. Return token for testing.
        invitation._token = token  # type: ignore[attr-defined]
        return invitation

    async def accept_invitation(
        self, token: str, name: str, password: str
    ) -> tuple[User, Organization]:
        """Accept an invitation and create the user account."""
        self.validate_password(password)
        token_hash = TokenManager.hash_token(token)

        result = await self.db.execute(
            select(UserInvitation).where(
                UserInvitation.token_hash == token_hash,
                UserInvitation.status == "pending",
            )
        )
        invitation = result.scalar_one_or_none()
        if invitation is None:
            raise AuthError("Invalid or expired invitation", status_code=404)

        if invitation.expires_at < datetime.now(timezone.utc):
            invitation.status = "expired"
            await self.db.flush()
            raise AuthError("Invitation has expired", status_code=410)

        # Create user
        user = User(
            org_id=invitation.org_id,
            email=invitation.email,
            name=name,
            password_hash=self.hash_password(password),
            status="active",
            org_role="member",
        )
        self.db.add(user)
        await self.db.flush()

        # Add to workspace if specified
        if invitation.workspace_id:
            member = WorkspaceMember(
                workspace_id=invitation.workspace_id,
                user_id=user.id,
                role=invitation.role,
            )
            self.db.add(member)

        invitation.status = "accepted"
        invitation.accepted_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Load org
        org_result = await self.db.execute(
            select(Organization).where(Organization.id == invitation.org_id)
        )
        org = org_result.scalar_one()

        return user, org

    # ── Workspace Members ───────────────────────────────────────────

    async def list_workspace_members(self, workspace_id: str) -> list[WorkspaceMember]:
        result = await self.db.execute(
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == uuid.UUID(workspace_id))
            .order_by(WorkspaceMember.created_at)
        )
        return list(result.scalars().all())

    async def add_workspace_member(
        self, workspace_id: str, user_id: str, role: str = "developer"
    ) -> WorkspaceMember:
        # Check if already a member
        result = await self.db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == uuid.UUID(workspace_id),
                WorkspaceMember.user_id == uuid.UUID(user_id),
            )
        )
        if result.scalar_one_or_none():
            raise AuthError("User is already a member of this workspace", status_code=409)

        member = WorkspaceMember(
            workspace_id=uuid.UUID(workspace_id),
            user_id=uuid.UUID(user_id),
            role=role,
        )
        self.db.add(member)
        await self.db.flush()
        return member

    async def update_workspace_member_role(
        self, workspace_id: str, user_id: str, role: str
    ) -> WorkspaceMember:
        result = await self.db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == uuid.UUID(workspace_id),
                WorkspaceMember.user_id == uuid.UUID(user_id),
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            raise AuthError("Member not found", status_code=404)
        member.role = role
        await self.db.flush()
        return member

    async def remove_workspace_member(self, workspace_id: str, user_id: str) -> None:
        result = await self.db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == uuid.UUID(workspace_id),
                WorkspaceMember.user_id == uuid.UUID(user_id),
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            raise AuthError("Member not found", status_code=404)
        await self.db.delete(member)
        await self.db.flush()

    # ── API Keys ────────────────────────────────────────────────────

    async def create_api_key(
        self,
        workspace_id: str,
        name: str,
        created_by: str,
        role: str = "developer",
        rate_limit_rpm: int = 600,
        expires_at: datetime | None = None,
    ) -> tuple[APIKey, str]:
        """Create an API key. Returns (api_key_model, raw_key_string)."""
        ws_id_short = workspace_id[:8]
        random_part = secrets.token_urlsafe(32)
        raw_key = f"rrag_ws_{ws_id_short}_{random_part}"

        api_key = APIKey(
            workspace_id=uuid.UUID(workspace_id),
            name=name,
            key_prefix=raw_key[:16],
            key_hash=TokenManager.hash_token(raw_key),
            role=role,
            rate_limit_rpm=rate_limit_rpm,
            expires_at=expires_at,
            created_by=uuid.UUID(created_by),
        )
        self.db.add(api_key)
        await self.db.flush()
        return api_key, raw_key

    async def validate_api_key(self, raw_key: str) -> APIKey | None:
        """Validate an API key and return its model if valid."""
        key_hash = TokenManager.hash_token(raw_key)
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.key_hash == key_hash,
                APIKey.status == "active",
            )
        )
        api_key = result.scalar_one_or_none()
        if api_key is None:
            return None

        # Check expiration
        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            return None

        # Update last_used_at
        api_key.last_used_at = datetime.now(timezone.utc)
        await self.db.flush()
        return api_key

    async def list_api_keys(self, workspace_id: str) -> list[APIKey]:
        result = await self.db.execute(
            select(APIKey)
            .where(APIKey.workspace_id == uuid.UUID(workspace_id))
            .order_by(APIKey.created_at)
        )
        return list(result.scalars().all())

    async def revoke_api_key(self, key_id: str, workspace_id: str) -> APIKey:
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.id == uuid.UUID(key_id),
                APIKey.workspace_id == uuid.UUID(workspace_id),
            )
        )
        api_key = result.scalar_one_or_none()
        if api_key is None:
            raise AuthError("API key not found", status_code=404)
        api_key.status = "revoked"
        api_key.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()
        return api_key

    # ── Sessions ────────────────────────────────────────────────────

    async def list_user_sessions(self, user_id: str) -> list[Session]:
        result = await self.db.execute(
            select(Session)
            .where(
                Session.user_id == uuid.UUID(user_id),
                Session.revoked_at.is_(None),
                Session.expires_at > datetime.now(timezone.utc),
            )
            .order_by(Session.last_active_at.desc())
        )
        return list(result.scalars().all())

    async def revoke_session(self, session_id: str, user_id: str) -> None:
        result = await self.db.execute(
            select(Session).where(
                Session.id == uuid.UUID(session_id),
                Session.user_id == uuid.UUID(user_id),
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise AuthError("Session not found", status_code=404)
        session.revoked_at = datetime.now(timezone.utc)
        # Also revoke in Redis
        await self.token_manager.revoke_refresh_token(session.refresh_token_hash)
        await self.db.flush()

    # ── Audit Logs ──────────────────────────────────────────────────

    async def query_audit_logs(
        self,
        org_id: str,
        workspace_id: str | None = None,
        action: str | None = None,
        user_id: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        query = select(AuditLog).where(AuditLog.org_id == uuid.UUID(org_id))
        count_query = select(func.count(AuditLog.id)).where(
            AuditLog.org_id == uuid.UUID(org_id)
        )

        if workspace_id:
            query = query.where(AuditLog.workspace_id == uuid.UUID(workspace_id))
            count_query = count_query.where(AuditLog.workspace_id == uuid.UUID(workspace_id))
        if action:
            query = query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)
        if user_id:
            query = query.where(AuditLog.user_id == uuid.UUID(user_id))
            count_query = count_query.where(AuditLog.user_id == uuid.UUID(user_id))

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(AuditLog.timestamp.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)

        return list(result.scalars().all()), total
