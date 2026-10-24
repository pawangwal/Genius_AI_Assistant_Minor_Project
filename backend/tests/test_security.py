"""Tests for Profile A vs Profile B security gates, cryptographic JWT authentication, and configuration validation."""
import pytest
from datetime import timedelta
from unittest.mock import patch
import jwt
from fastapi import HTTPException

from backend.app.core.config import Settings, settings
from backend.app.core.security import (
    get_current_user_id,
    create_access_token,
    decode_access_token,
    LOCAL_DEFAULT_USER_ID
)

@pytest.mark.asyncio
async def test_profile_a_local_dev_unauthenticated_access():
    """In Profile A (local dev), unauthenticated access defaults to local-user."""
    with patch("backend.app.core.security.settings.AUTH_REQUIRED", False):
        user = await get_current_user_id(None)
        assert user == LOCAL_DEFAULT_USER_ID

@pytest.mark.asyncio
async def test_profile_a_with_valid_jwt():
    """In Profile A, if a valid JWT is supplied, the authenticated subject is resolved."""
    with patch("backend.app.core.security.settings.AUTH_REQUIRED", False):
        token = create_access_token(user_id="developer-123")
        user = await get_current_user_id(f"Bearer {token}")
        assert user == "developer-123"

@pytest.mark.asyncio
async def test_profile_a_rejects_invalid_token_without_fallback():
    """In Profile A, invalid or forged tokens are rejected with 401 and never accepted as identity."""
    with patch("backend.app.core.security.settings.AUTH_REQUIRED", False):
        # Plain text arbitrary token
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id("Bearer arbitrary-attacker-id")
        assert exc_info.value.status_code == 401

        # Forged JWT signed with wrong secret
        forged_token = jwt.encode(
            {"sub": "victim-user", "exp": 9999999999, "iat": 1000000000},
            "attacker-secret-wrong-key-testing-12345",
            algorithm="HS256"
        )
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(f"Bearer {forged_token}")
        assert exc_info.value.status_code == 401

@pytest.mark.asyncio
async def test_profile_b_public_deployment_enforces_cryptographic_jwt():
    """In Profile B (public deployment), missing, forged, expired, or plaintext tokens raise 401."""
    with patch("backend.app.core.security.settings.AUTH_REQUIRED", True):
        # 1. Missing Authorization header
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(None)
        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

        # 2. Arbitrary plaintext bearer string (P0 Vulnerability regression check)
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id("Bearer arbitrary-attacker-id")
        assert exc_info.value.status_code == 401
        assert "Invalid authentication token" in exc_info.value.detail

        # 3. Forged JWT signed with a different secret key
        forged_token = jwt.encode(
            {"sub": "victim-user", "exp": 9999999999, "iat": 1000000000},
            "attacker-secret-key-12345-long-key-9988-testing",
            algorithm="HS256"
        )
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(f"Bearer {forged_token}")
        assert exc_info.value.status_code == 401
        assert "Invalid authentication token signature" in exc_info.value.detail

        # 4. Expired JWT
        expired_token = create_access_token(user_id="legit-user", expires_delta=timedelta(seconds=-10))
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(f"Bearer {expired_token}")
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

        # 5. Token without 'sub' claim
        token_no_sub = jwt.encode(
            {"exp": 9999999999, "iat": 1000000000},
            settings.SECRET_KEY,
            algorithm="HS256"
        )
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(f"Bearer {token_no_sub}")
        assert exc_info.value.status_code == 401

        # 6. Valid cryptographically signed JWT succeeds
        valid_token = create_access_token(user_id="verified-user-456")
        resolved_user = await get_current_user_id(f"Bearer {valid_token}")
        assert resolved_user == "verified-user-456"

def test_production_security_profile_validation():
    """Production configuration must fail validation if auth is disabled, default secret is used, or wildcard CORS."""
    # 1. Production with AUTH_REQUIRED=False
    with pytest.raises(ValueError, match="AUTH_REQUIRED must be True in production"):
        s = Settings(APP_ENV="production", AUTH_REQUIRED=False)
        s.validate_security_profile()

    # 2. Production with default secret key
    with pytest.raises(ValueError, match="Insecure default SECRET_KEY"):
        s = Settings(
            APP_ENV="production",
            AUTH_REQUIRED=True,
            SECRET_KEY="dev-secret-key-change-in-production"
        )
        s.validate_security_profile()

    # 3. Production with too-short secret key (< 32 chars)
    with pytest.raises(ValueError, match="at least 32 characters"):
        s = Settings(
            APP_ENV="production",
            AUTH_REQUIRED=True,
            SECRET_KEY="short-secret"
        )
        s.validate_security_profile()

    # 4. Valid production profile passes cleanly
    s = Settings(
        APP_ENV="production",
        AUTH_REQUIRED=True,
        SECRET_KEY="strong-random-production-secret-key-99881122",
        CORS_ORIGINS="https://genius.example.com"
    )
    s.validate_security_profile()
    assert s.is_production is True

def test_create_access_token_rejects_reserved_claim_overrides():
    """Callers cannot override reserved claims (sub, exp, iat) via extra_claims."""
    # 1. Attempt to override 'sub'
    with pytest.raises(ValueError, match="Cannot overwrite reserved JWT claim.*sub"):
        create_access_token(user_id="alice", extra_claims={"sub": "bob"})

    # 2. Attempt to override 'exp'
    with pytest.raises(ValueError, match="Cannot overwrite reserved JWT claim.*exp"):
        create_access_token(user_id="alice", extra_claims={"exp": 9999999999})

    # 3. Attempt to override 'iat'
    with pytest.raises(ValueError, match="Cannot overwrite reserved JWT claim.*iat"):
        create_access_token(user_id="alice", extra_claims={"iat": 1000000000})

    # 4. Attempt to pass empty user_id
    with pytest.raises(ValueError, match="User ID.*cannot be empty"):
        create_access_token(user_id="   ")

def test_create_access_token_allows_valid_custom_claims():
    """Permitted non-reserved claims (e.g. role, scope) are safely encoded into the JWT."""
    token = create_access_token(user_id="admin-user", extra_claims={"role": "superuser", "tenant": "corp"})
    payload = decode_access_token(token)
    assert payload["sub"] == "admin-user"
    assert payload["role"] == "superuser"
    assert payload["tenant"] == "corp"

