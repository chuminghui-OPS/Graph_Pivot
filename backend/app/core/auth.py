from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient

from app.core.config import settings


@dataclass
class UserContext:
    user_id: str
    email: str | None
    claims: dict[str, Any]


_jwks_client: PyJWKClient | None = None
_jwks_url: str | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client, _jwks_url
    jwks_url = settings.resolved_supabase_jwks_url
    if not jwks_url:
        raise HTTPException(status_code=500, detail="SUPABASE_JWKS_URL not configured.")
    if _jwks_client is None or _jwks_url != jwks_url:
        _jwks_client = PyJWKClient(jwks_url)
        _jwks_url = jwks_url
    return _jwks_client


def _resolve_signing_key(token: str) -> tuple[Any, str]:
    header = jwt.get_unverified_header(token)
    alg = header.get("alg")
    if not alg:
        raise HTTPException(status_code=401, detail="Invalid JWT header.")
    if alg.lower() == "none":
        raise HTTPException(status_code=401, detail="Invalid JWT algorithm.")
    if alg.startswith("HS"):
        if not settings.supabase_jwt_secret:
            raise HTTPException(
                status_code=500,
                detail="SUPABASE_JWT_SECRET not configured for HS* tokens.",
            )
        return settings.supabase_jwt_secret, alg
    jwks_client = _get_jwks_client()
    signing_key = jwks_client.get_signing_key_from_jwt(token).key
    return signing_key, alg


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    try:
        signing_key, alg = _resolve_signing_key(token)
        issuer = settings.resolved_supabase_jwt_issuer
        if not issuer:
            raise HTTPException(status_code=500, detail="SUPABASE_JWT_ISSUER not configured.")
        return jwt.decode(
            token,
            signing_key,
            algorithms=[alg],
            audience=settings.supabase_jwt_audience,
            issuer=issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid JWT.") from exc


def get_current_user(authorization: str = Header(default="")) -> UserContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing JWT token.")

    claims = verify_supabase_jwt(token)
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid JWT payload.")
    email = claims.get("email")
    return UserContext(user_id=user_id, email=email, claims=claims)


AuthDependency = Depends(get_current_user)
