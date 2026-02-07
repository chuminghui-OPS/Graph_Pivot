from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    # Supabase user_id (uuid string)
    user_id: Mapped[str] = mapped_column(String, primary_key=True)

    # Default API asset for LLM calls (Chatbox-like "active provider")
    default_asset_id: Mapped[str | None] = mapped_column(String, nullable=True)
    default_model: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
