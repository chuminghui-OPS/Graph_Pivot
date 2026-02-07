from __future__ import annotations

import os
import shutil
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import (
    ApiAsset,
    ApiManager,
    LLMUsageEvent,
    PublicBook,
    PublicBookFavorite,
    PublicBookRepost,
    UserSettings,
)


router = APIRouter()


def _require_admin(x_admin_key: str | None) -> None:
    if not settings.admin_api_key:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY not configured.")
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized.")


def _read_meminfo() -> dict:
    path = "/proc/meminfo"
    if not os.path.exists(path):
        return {}
    data: dict[str, int] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0].endswith(":"):
                    key = parts[0][:-1]
                    try:
                        data[key] = int(parts[1])
                    except ValueError:
                        continue
    except OSError:
        return {}
    return data


@router.get("/dashboard")
def get_dashboard(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(x_admin_key)

    now = datetime.utcnow().isoformat() + "Z"
    try:
        loadavg = os.getloadavg()
        load = {"1m": loadavg[0], "5m": loadavg[1], "15m": loadavg[2]}
    except Exception:
        load = {}

    disk = {}
    try:
        usage = shutil.disk_usage("/")
        disk = {"total": usage.total, "used": usage.used, "free": usage.free}
    except Exception:
        disk = {}

    meminfo = _read_meminfo()
    mem = {}
    if meminfo:
        # Values are in kB.
        mem = {
            "mem_total_kb": meminfo.get("MemTotal", 0),
            "mem_free_kb": meminfo.get("MemFree", 0),
            "mem_available_kb": meminfo.get("MemAvailable", 0),
        }

    assets_count = db.query(func.count(ApiAsset.id)).scalar() or 0
    managers_count = db.query(func.count(ApiManager.id)).scalar() or 0
    settings_count = db.query(func.count(UserSettings.user_id)).scalar() or 0

    public_books_count = db.query(func.count(PublicBook.id)).scalar() or 0
    favorites_count = db.query(func.count(PublicBookFavorite.id)).scalar() or 0
    reposts_count = db.query(func.count(PublicBookRepost.id)).scalar() or 0

    usage_calls, tokens_in, tokens_out = (
        db.query(
            func.count(LLMUsageEvent.id),
            func.coalesce(func.sum(LLMUsageEvent.tokens_in), 0),
            func.coalesce(func.sum(LLMUsageEvent.tokens_out), 0),
        )
        .one()
    )

    return {
        "time": now,
        "system": {
            "cpu_count": os.cpu_count() or 0,
            "load": load,
            "memory": mem,
            "disk": disk,
        },
        "api_pool": {
            "assets": assets_count,
            "managers": managers_count,
            "user_settings": settings_count,
        },
        "public": {
            "public_books": public_books_count,
            "favorites": favorites_count,
            "reposts": reposts_count,
        },
        "usage": {
            "calls": int(usage_calls or 0),
            "tokens_in": int(tokens_in or 0),
            "tokens_out": int(tokens_out or 0),
        },
    }

