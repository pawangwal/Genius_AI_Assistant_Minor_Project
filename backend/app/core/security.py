"""Cryptographic security, JWT authentication, and ownership validation."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, status
import jwt
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

LOCAL_DEFAULT_USER_ID = "local-user"
JWT_ALGORITHM = "HS256"
DEFAULT_TOKEN_EXPIRY_MINUTES = 60
RESERVED_JWT_CLAIMS = frozenset({"sub", "iat", "exp", "nbf", "iss", "aud", "jti"})

def create_access_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None
) -> str:
    """Generates a cryptographically signed HMAC-SHA256 JWT."""
    if not user_id or not str(user_id).strip():
        raise ValueError("User ID ('sub') cannot be empty or whitespace.")

    if extra_claims:
        conflicting = RESERVED_JWT_CLAIMS.intersection(extra_claims.keys())
        if conflicting:
            raise ValueError(
                f"Cannot overwrite reserved JWT claim(s): {', '.join(sorted(conflicting))}. "
                "Reserved claims are set exclusively by the token generation authority."
            )

    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=DEFAULT_TOKEN_EXPIRY_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> Dict[str, Any]:
    """Validates signature, expiration, and claims of a JWT."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]}
        )
        user_id = payload.get("sub")
        if not user_id or not str(user_id).strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims: subject ('sub') is missing or empty.",
                headers={"WWW-Authenticate": "Bearer"}
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Failed JWT token verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token signature or claims.",
            headers={"WWW-Authenticate": "Bearer"}
        )

async def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """Dependency that resolves the current user ID according to the active security profile.

    Profile A (Local Dev, AUTH_REQUIRED=False):
      Returns 'local-user' if unauthenticated, allowing seamless local development.
      If a valid JWT is supplied, resolves the authenticated subject.

    Profile B (Public Deployment, AUTH_REQUIRED=True):
      Enforces mandatory cryptographic JWT validation. Forged, expired, or arbitrary
      bearer strings are strictly rejected with 401 Unauthorized.
    """
    if not settings.AUTH_REQUIRED:
        if authorization and authorization.startswith("Bearer "):
            token = authorization.replace("Bearer ", "").strip()
            if not token:
                return LOCAL_DEFAULT_USER_ID
            # If an authorization token is provided, it must be cryptographically valid.
            # Never reinterpret an invalid credential as an identity.
            payload = decode_access_token(token)
            return str(payload["sub"])
        return LOCAL_DEFAULT_USER_ID

    # Profile B: Cryptographic authentication strictly required
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token cannot be empty.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(token)
    return str(payload["sub"])
