from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import UserContext, get_current_user
from app.core.database import get_db
from app.core.schemas import ApiAssetCreate, ApiAssetOut, ApiAssetUpdate, DiscoverModelsResponse
from app.models import ApiAsset
from app.utils.crypto import decrypt_value, encrypt_value


router = APIRouter()


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:2]}***{value[-4:]}"


def _discover_models_openai_compatible(base_url: str, api_path: str, api_key: str) -> list[str]:
    # OpenAI-compatible: GET {base_url}/models
    # If user configured api_path like "/v1/chat/completions", derive "/v1/models".
    candidates: list[str] = []
    api_path = (api_path or "").strip()
    if api_path:
        if not api_path.startswith("/"):
            api_path = f"/{api_path}"
        if "/chat/completions" in api_path:
            candidates.append(f"{base_url.rstrip('/')}{api_path.replace('/chat/completions', '/models')}")
    candidates.append(f"{base_url.rstrip('/')}/models")
    headers = {"Authorization": f"Bearer {api_key}"}

    data = None
    last_exc: Exception | None = None
    with httpx.Client(timeout=20) as client:
        for url in candidates:
            try:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as exc:  # noqa: BLE001 - surface as 502 in caller
                last_exc = exc
                continue

    if data is None:
        raise last_exc or RuntimeError("No candidate URL succeeded.")

    models: list[str] = []
    if isinstance(data, dict):
        items = data.get("data") or data.get("models") or []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                mid = item.get("id") or item.get("model") or item.get("name")
                if mid:
                    models.append(str(mid))

    # De-dup + stable order
    return sorted(set(m.strip() for m in models if m and str(m).strip()))


@router.get("", response_model=list[ApiAssetOut])
def list_assets(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> list[ApiAssetOut]:
    rows = (
        db.query(ApiAsset)
        .filter(ApiAsset.user_id == user.user_id)
        .order_by(ApiAsset.created_at.desc())
        .all()
    )
    return [
        ApiAssetOut(
            id=row.id,
            name=row.name,
            provider=row.provider,
            api_mode=row.api_mode,
            api_key_masked=_mask(decrypt_value(row.api_key)),
            base_url=row.base_url,
            api_path=row.api_path,
            models=row.models,
            created_at=row.created_at.isoformat() if row.created_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        )
        for row in rows
    ]


@router.post("", response_model=ApiAssetOut)
def create_asset(
    payload: ApiAssetCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ApiAssetOut:
    now = datetime.utcnow()
    api_key_plain = payload.api_key or ""
    row = ApiAsset(
        id=str(uuid4()),
        user_id=user.user_id,
        name=payload.name,
        provider=payload.provider,
        api_mode=payload.api_mode,
        api_key=encrypt_value(api_key_plain),
        base_url=payload.base_url,
        api_path=payload.api_path,
        models=payload.models,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ApiAssetOut(
        id=row.id,
        name=row.name,
        provider=row.provider,
        api_mode=row.api_mode,
        api_key_masked=_mask(api_key_plain),
        base_url=row.base_url,
        api_path=row.api_path,
        models=row.models,
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@router.put("/{asset_id}", response_model=ApiAssetOut)
def update_asset(
    asset_id: str,
    payload: ApiAssetUpdate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ApiAssetOut:
    row = db.get(ApiAsset, asset_id)
    if not row or row.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Asset not found.")

    data = payload.model_dump(exclude_unset=True)
    api_key_plain: str | None = None
    if "api_key" in data:
        api_key_plain = data.pop("api_key")
        if api_key_plain is not None:
            row.api_key = encrypt_value(api_key_plain)
    for field, value in data.items():
        setattr(row, field, value)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return ApiAssetOut(
        id=row.id,
        name=row.name,
        provider=row.provider,
        api_mode=row.api_mode,
        api_key_masked=_mask(api_key_plain or decrypt_value(row.api_key)),
        base_url=row.base_url,
        api_path=row.api_path,
        models=row.models,
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@router.delete("/{asset_id}")
def delete_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    row = db.get(ApiAsset, asset_id)
    if not row or row.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Asset not found.")
    db.delete(row)
    db.commit()
    return {"ok": True, "asset_id": asset_id}


@router.post("/{asset_id}/models/fetch", response_model=ApiAssetOut)
def fetch_models(
    asset_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ApiAssetOut:
    """
    Fetch available models from an OpenAI-compatible provider and persist them to the asset.
    This keeps API keys on the backend (no CORS/leakage in browser).
    """
    row = db.get(ApiAsset, asset_id)
    if not row or row.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Asset not found.")

    api_key_plain = decrypt_value(row.api_key)
    if not api_key_plain:
        raise HTTPException(status_code=400, detail="API key is empty. Please set it first.")

    base_url = (row.base_url or "").strip()
    if not base_url:
        raise HTTPException(status_code=400, detail="Base URL is empty. Please set it first.")

    try:
        models = _discover_models_openai_compatible(base_url, row.api_path or "", api_key_plain)
    except Exception as exc:  # noqa: BLE001 - surface a clear upstream error
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {exc}") from exc

    row.models = models
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return ApiAssetOut(
        id=row.id,
        name=row.name,
        provider=row.provider,
        api_mode=row.api_mode,
        api_key_masked=_mask(api_key_plain),
        base_url=row.base_url,
        api_path=row.api_path,
        models=row.models,
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@router.post("/{asset_id}/models/discover", response_model=DiscoverModelsResponse)
def discover_models(
    asset_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> DiscoverModelsResponse:
    """Discover available models from provider without mutating the asset."""
    row = db.get(ApiAsset, asset_id)
    if not row or row.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Asset not found.")

    api_key_plain = decrypt_value(row.api_key)
    if not api_key_plain:
        raise HTTPException(status_code=400, detail="API key is empty. Please set it first.")

    base_url = (row.base_url or "").strip()
    if not base_url:
        raise HTTPException(status_code=400, detail="Base URL is empty. Please set it first.")

    try:
        models = _discover_models_openai_compatible(base_url, row.api_path or "", api_key_plain)
    except Exception as exc:  # noqa: BLE001 - surface a clear upstream error
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {exc}") from exc

    return DiscoverModelsResponse(models=models)
