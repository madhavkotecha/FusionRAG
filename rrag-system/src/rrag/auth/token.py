"""JWT and refresh token management."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import redis.asyncio as aioredis

from rrag.config import settings


class TokenManager:
    """Handles JWT access token issuance/verification and refresh token lifecycle."""

    def __init__(self, redis_client: aioredis.Redis | None = None):
        self.redis = redis_client
        self.algorithm = settings.jwt_algorithm
        self.secret_key = settings.jwt_secret_key
        self.access_token_ttl = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        self.refresh_token_ttl = timedelta(days=settings.jwt_refresh_token_expire_days)

    # ── Access Token (JWT) ──────────────────────────────────────────

    def create_access_token(
        self,
        user_id: str,
        org_id: str,
        org_role: str,
        email: str,
        name: str,
        workspace_roles: dict[str, str],
    ) -> tuple[str, str]:
        """Create a JWT access token.

        Returns (token_string, jti).
        """
        jti = f"tok_{uuid.uuid4().hex[:24]}"
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "org_id": str(org_id),
            "org_role": org_role,
            "email": email,
            "name": name,
            "ws_roles": {str(k): v for k, v in workspace_roles.items()},
            "jti": jti,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + self.access_token_ttl,
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token, jti

    def verify_access_token(self, token: str) -> dict:
        """Verify and decode a JWT access token.

        Raises jwt.InvalidTokenError on failure.
        """
        payload = jwt.decode(
            token,
            self.secret_key,
            algorithms=[self.algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
        return payload

    # ── Refresh Token (Opaque) ──────────────────────────────────────

    @staticmethod
    def generate_refresh_token() -> str:
        """Generate a cryptographically secure opaque refresh token."""
        return secrets.token_urlsafe(48)

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token using SHA-256 for storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    async def store_refresh_token(
        self,
        token_hash: str,
        user_id: str,
        org_id: str,
        device_info: dict | None = None,
    ) -> None:
        """Store a refresh token in Redis with TTL."""
        if self.redis is None:
            return
        import json

        data = json.dumps(
            {
                "user_id": str(user_id),
                "org_id": str(org_id),
                "device_info": device_info,
                "issued_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        ttl_seconds = int(self.refresh_token_ttl.total_seconds())
        await self.redis.setex(f"refresh:{token_hash}", ttl_seconds, data)

    async def validate_refresh_token(self, token_hash: str) -> dict | None:
        """Validate a refresh token exists in Redis.

        Returns the stored data if valid, None otherwise.
        """
        if self.redis is None:
            return None
        import json

        data = await self.redis.get(f"refresh:{token_hash}")
        if data is None:
            return None
        return json.loads(data)

    async def revoke_refresh_token(self, token_hash: str) -> None:
        """Delete a refresh token from Redis (one-time use / revocation)."""
        if self.redis is None:
            return
        await self.redis.delete(f"refresh:{token_hash}")

    async def blacklist_access_token(self, jti: str, remaining_ttl_seconds: int) -> None:
        """Add an access token's jti to the blacklist."""
        if self.redis is None:
            return
        if remaining_ttl_seconds > 0:
            await self.redis.setex(f"blacklist:{jti}", remaining_ttl_seconds, "1")

    async def is_token_blacklisted(self, jti: str) -> bool:
        """Check if an access token has been blacklisted."""
        if self.redis is None:
            return False
        return await self.redis.exists(f"blacklist:{jti}") > 0

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all refresh tokens for a user. Returns count of revoked tokens."""
        if self.redis is None:
            return 0
        pattern = "refresh:*"
        count = 0
        import json

        async for key in self.redis.scan_iter(match=pattern, count=100):
            data = await self.redis.get(key)
            if data:
                token_data = json.loads(data)
                if token_data.get("user_id") == str(user_id):
                    await self.redis.delete(key)
                    count += 1
        return count
