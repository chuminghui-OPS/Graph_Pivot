from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import UserContext, get_current_user
from app.core.database import get_db
from app.core.schemas import ApiAssetCreate, ApiAssetOut, ApiAssetUpdate
from app.models import ApiAsset
from app.utils.crypto import decrypt_value, encrypt_value


router = APIRouter()


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:2]}***{value[-4:]}"


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
    row = ApiAsset(
        id=str(uuid4()),
        user_id=user.user_id,
        name=payload.name,
        provider=payload.provider,
        api_mode=payload.api_mode,
        api_key=encrypt_value(payload.api_key),
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
        api_key_masked=_mask(payload.api_key),
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
