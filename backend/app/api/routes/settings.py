from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import UserContext, get_current_user
from app.core.database import get_db
from app.core.schemas import ApiAssetOut, ApiSettingsCreate, SettingsResponse
from app.models import ApiAsset, UserSettings
from app.utils.crypto import decrypt_value, encrypt_value


router = APIRouter()


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:2]}***{value[-4:]}"


def _to_asset_out(row: ApiAsset) -> ApiAssetOut:
    return ApiAssetOut(
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


@router.get("", response_model=SettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> SettingsResponse:
    row = db.get(UserSettings, user.user_id)
    assets = (
        db.query(ApiAsset)
        .filter(ApiAsset.user_id == user.user_id)
        .order_by(ApiAsset.created_at.desc())
        .all()
    )
    return SettingsResponse(
        default_asset_id=row.default_asset_id if row else None,
        default_model=row.default_model if row else None,
        assets=[_to_asset_out(item) for item in assets],
    )


@router.post("", response_model=SettingsResponse)
def create_settings(
    payload: ApiSettingsCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> SettingsResponse:
    now = datetime.utcnow()
    asset_id = str(uuid4())

    asset_models = [payload.model] if payload.model else None
    asset = ApiAsset(
        id=asset_id,
        user_id=user.user_id,
        name=payload.name,
        provider=payload.provider,
        api_mode=payload.api_mode,
        api_key=encrypt_value(payload.api_key),
        base_url=payload.base_url,
        api_path=payload.api_path,
        models=asset_models,
        created_at=now,
        updated_at=now,
    )
    db.add(asset)

    row = db.get(UserSettings, user.user_id)
    if not row:
        row = UserSettings(user_id=user.user_id, created_at=now, updated_at=now)
        db.add(row)

    row.default_asset_id = asset_id
    row.default_model = payload.model
    row.updated_at = now

    db.commit()
    return get_settings(db=db, user=user)

