from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import UserContext, get_current_user
from app.core.database import get_db
from app.core.schemas import ApiManagerCreate, ApiManagerOut, ApiManagerUpdate
from app.models import ApiManager
from app.utils.crypto import encrypt_value


router = APIRouter()


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:2]}***{value[-4:]}"


@router.get("", response_model=list[ApiManagerOut])
def list_managers(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> list[ApiManagerOut]:
    rows = db.query(ApiManager).filter(ApiManager.user_id == user.user_id).all()
    return [
        ApiManagerOut(
            id=row.id,
            name=row.name,
            provider=row.provider,
            api_key_masked=_mask(row.api_key_encrypted),
            base_url=row.base_url,
            model=row.model,
            created_at=row.created_at.isoformat() if row.created_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        )
        for row in rows
    ]


@router.post("", response_model=ApiManagerOut)
def create_manager(
    payload: ApiManagerCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ApiManagerOut:
    row = ApiManager(
        id=uuid4().hex,
        user_id=user.user_id,
        name=payload.name,
        provider=payload.provider,
        api_key_encrypted=encrypt_value(payload.api_key),
        base_url=payload.base_url,
        model=payload.model,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    return ApiManagerOut(
        id=row.id,
        name=row.name,
        provider=row.provider,
        api_key_masked=_mask(payload.api_key),
        base_url=row.base_url,
        model=row.model,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


@router.put("/{manager_id}", response_model=ApiManagerOut)
def update_manager(
    manager_id: str,
    payload: ApiManagerUpdate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ApiManagerOut:
    row = db.get(ApiManager, manager_id)
    if not row or row.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Manager not found.")
    if payload.name is not None:
        row.name = payload.name
    if payload.provider is not None:
        row.provider = payload.provider
    if payload.base_url is not None:
        row.base_url = payload.base_url
    if payload.model is not None:
        row.model = payload.model
    if payload.api_key is not None:
        row.api_key_encrypted = encrypt_value(payload.api_key)
    row.updated_at = datetime.utcnow()
    db.commit()
    return ApiManagerOut(
        id=row.id,
        name=row.name,
        provider=row.provider,
        api_key_masked=_mask(payload.api_key or row.api_key_encrypted),
        base_url=row.base_url,
        model=row.model,
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@router.delete("/{manager_id}")
def delete_manager(
    manager_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    row = db.get(ApiManager, manager_id)
    if not row or row.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Manager not found.")
    db.delete(row)
    db.commit()
    return {"ok": True, "id": manager_id}
